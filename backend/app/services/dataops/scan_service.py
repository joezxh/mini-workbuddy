"""元数据扫描编排（P2 Task 7，消费 Task 3 方言适配器）。

职责：创建扫描任务 → 建连 → 调适配器取表/列/画像 → 幂等写 ``meta_table`` /
``meta_column`` → 进度/统计/状态回写。

幂等：每次扫描先删除该 ``(source_id, database)`` 下的旧快照（``meta_table`` 级联
删 ``meta_column``），再写入新快照（spec §6.2「重新扫描覆盖」）。
"""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.dataops.connection import build_engine
from app.ai.dataops.dialects.registry import get_adapter
from app.models.dataops.data_source import DataSource
from app.models.dataops.meta import MetaColumn, MetaScanJob, MetaTable
from app.services.dataops.data_source_service import DataSourceService


class MetaScanService:
    """元数据扫描编排（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaScanService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._ds = DataSourceService(db, tenant_id)

    def get_or_404(self, job_id: int) -> MetaScanJob:
        obj = self.db.execute(
            select(MetaScanJob).where(
                MetaScanJob.tenant_id == self.tenant_id, MetaScanJob.id == job_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise KeyError(job_id)
        return obj

    def start_scan(
        self,
        source_id: int,
        database: str,
        with_profile: bool = False,
        creator_id: Optional[int] = None,
    ) -> MetaScanJob:
        """创建扫描任务并同步执行（本阶段无独立任务队列，执行在请求内完成）。"""
        ds = self._ds.get_or_404(source_id)  # 租户隔离校验
        job = MetaScanJob(
            tenant_id=self.tenant_id,
            source_id=source_id,
            database=database,
            job_kind="profile" if with_profile else "scan",
            status="pending",
            with_profile=bool(with_profile),
            creator_id=creator_id,
        )
        self.db.add(job)
        self.db.flush()
        self._run(job, ds)
        self.db.commit()
        return job

    # ------------------------------------------------------------------ #
    def _run(self, job: MetaScanJob, ds: DataSource) -> None:
        job.status = "running"
        job.started_at = self._now()
        started = time.perf_counter()
        try:
            password = self._ds.reveal_password(ds.id)
            engine = build_engine(
                ds.source_type, ds.host, ds.port, ds.username, password, ds.database
            )
        except Exception as exc:  # noqa: BLE001
            self._fail(job, exc)
            return

        try:
            adapter = get_adapter(ds.source_type)
            with engine.connect() as conn:
                tables = adapter.list_tables(conn, job.database)
                total = len(tables) or 1
                column_total = 0
                truncated = False

                # 幂等覆盖：清旧快照
                self.db.execute(
                    delete(MetaTable).where(
                        MetaTable.source_id == ds.id, MetaTable.database == job.database
                    )
                )

                for idx, t in enumerate(tables):
                    mt = MetaTable(
                        tenant_id=self.tenant_id,
                        source_id=ds.id,
                        database=job.database,
                        table_name=t.name,
                        table_type=t.table_type,
                        table_comment=t.comment,
                        row_count=t.row_count,
                        engine=t.engine,
                    )
                    self.db.add(mt)
                    self.db.flush()

                    cols = adapter.list_columns(conn, job.database, [t.name]).get(t.name, [])
                    for c in cols:
                        mc = MetaColumn(
                            tenant_id=self.tenant_id,
                            table_id=mt.id,
                            column_name=c.name,
                            ordinal=c.ordinal,
                            data_type=c.data_type,
                            column_type=c.column_type,
                            nullable=bool(c.nullable),
                            column_key=c.column_key,
                            column_default=(c.column_default or None),
                            extra=c.extra,
                            column_comment=c.comment,
                        )
                        if job.with_profile:
                            profile = adapter.profile_column(
                                conn, job.database, t.name, c.name, 1000
                            )
                            mc.profile_json = asdict(profile)
                        self.db.add(mc)
                    column_total += len(cols)
                    job.progress = round((idx + 1) / total * 100, 2)
                    self.db.flush()

                if len(tables) == 0:
                    job.progress = 100.0
                    truncated = False
                elif column_total > 5000:  # 超大扫描提示（软上限，不中断）
                    truncated = True

                job.tables_json = [t.name for t in tables]
                job.stats_json = {
                    "table_count": len(tables),
                    "column_count": column_total,
                    "truncated": truncated,
                }
                job.status = "succeeded"
        except Exception as exc:  # noqa: BLE001
            self._fail(job, exc)
            return
        finally:
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001
                pass

        job.finished_at = self._now()
        job.duration_ms = int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _now():
        from sqlalchemy import func

        return func.now()

    def _fail(self, job: MetaScanJob, exc: Exception) -> None:
        job.status = "failed"
        job.error_detail = f"{type(exc).__name__}: {exc}"[:2000]
        job.finished_at = self._now()
        try:
            self.db.commit()
        except Exception:  # noqa: BLE001
            self.db.rollback()
