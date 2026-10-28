"""元数据扫描编排（P2 Task 7；类型体系扩展后统一走 DialectAdapter.open）。

职责：创建扫描任务 → 建连 → 调适配器取表/列/画像 → 幂等写 ``meta_table`` /
``meta_column`` → 进度/统计/状态回写；并承载数据源探活、远端库表浏览与
SQLBot 式「选表导入」动作。

连接约定（改造点）：
- 不再直接 ``build_engine``：dm/es 为原生驱动族、excel 复用系统引擎，
  统一经 ``adapter.open(ds)`` 分发，返回 ``(conn, cleanup)``；
- 密码由 ``_prepare`` 解密后挂 ``ds._password_plain`` 临时属性（协议约定），
  适配器层不触碰 ``password_enc``。

幂等：每次扫描先删除该 ``(source_id, database)`` 下的旧快照（``meta_table`` 级联
删 ``meta_column``），再写入新快照（spec §6.2「重新扫描覆盖」）；选表导入按
单表粒度覆盖，不影响未勾选的既有快照。
"""
from __future__ import annotations

import time
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.dataops.dialects.registry import get_adapter
from app.ai.dataops.connection import resolve_family
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

    # ------------------------------------------------------------------ #
    # 连接准备与探活（类型体系扩展新增）
    # ------------------------------------------------------------------ #
    def _prepare(self, ds: DataSource) -> DataSource:
        """解密密码挂到临时属性（DialectAdapter.open 协议约定）。"""
        ds._password_plain = self._ds.reveal_password(ds.id)  # noqa: SLF001
        return ds

    def test_saved(self, source_id: int) -> Tuple[bool, Optional[str]]:
        """已保存数据源探活：(ok, error)。"""
        ds = self._prepare(self._ds.get_or_404(source_id))
        return get_adapter(ds.source_type).test_connect(ds)

    def test_draft(self, *, source_type: str, host: str = "", port: int = 0,
                   username: Optional[str] = None, password: Optional[str] = None,
                   database: Optional[str] = None,
                   config: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """未保存表单探活（新建/编辑弹窗的「测试连接」）：不落库、只试连。"""
        t = DataSourceService.validate_source_type(source_type, self.db, self.tenant_id)
        DataSourceService.validate_config(t, config)
        draft = SimpleNamespace(source_type=t, host=host, port=port, username=username,
                                database=database, config_json=config or {})
        draft._password_plain = password  # noqa: SLF001
        return get_adapter(t).test_connect(draft)

    # ------------------------------------------------------------------ #
    # 远端浏览（选表导入的前置，不落快照）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _has_schema(source_type: str) -> bool:
        """PG 族（postgresql/kingbase）才有「物理库 → schema → 表」三级作用域。"""
        try:
            return resolve_family(source_type) == "pg"
        except ValueError:
            return False

    @staticmethod
    def _resolve_scope(schema: Optional[str], database: str) -> str:
        """表/列限定的作用域名：传了 schema 用 schema，否则沿用 database（兼容旧语义）。"""
        return schema or database

    def _physical_db(self, ds: DataSource, *, scope: str,
                     connect_database: Optional[str]) -> str:
        """``meta_table.db_name``（三级作用域第一级）：
        - PG 族：重连/配置的物理库（``connect_database`` 优先），与表限定
          的 schema 分开存，从而支持跨物理库同名 schema 的隔离与过滤；
        - 其余族：无独立物理库维度，db_name 与作用域（库名）同值。"""
        if self._has_schema(ds.source_type):
            return connect_database or ds.database or scope
        return scope

    def _with_conn(self, source_id: int, action, connect_database: Optional[str] = None):
        """打开数据源连接执行单个动作后归还（excel/dm/es/SQLAlchemy 族统一路径）。

        ``connect_database``：PG 族跨物理库浏览时的连接目标覆盖，缺省连 ds.database。"""
        ds = self._prepare(self._ds.get_or_404(source_id))
        adapter = get_adapter(ds.source_type)
        conn, cleanup = adapter.open(ds, connect_database=connect_database)
        try:
            return action(adapter, conn)
        finally:
            cleanup()

    def list_remote_databases(self, source_id: int) -> List[str]:
        return self._with_conn(source_id, lambda a, c: a.list_databases(c))

    def list_remote_schemas(self, source_id: int, database: str) -> List[str]:
        """PG 族导入向导第二级：连到所选物理库 ``database``，列其用户 schema。"""
        ds = self._ds.get_or_404(source_id)
        if not self._has_schema(ds.source_type):
            return []
        return self._with_conn(
            source_id, lambda a, c: a.list_schemas(c), connect_database=database)

    def list_remote_tables(self, source_id: int, database: str,
                           schema: Optional[str] = None) -> List[dict]:
        # PG 族：database=物理库(重连目标)、schema=表限定；其余族保持 database 作限定不重连
        connect_db = database if schema else None
        scope = self._resolve_scope(schema, database)
        return [asdict(t) for t in
                self._with_conn(source_id, lambda a, c: a.list_tables(c, scope),
                                connect_database=connect_db)]

    def list_remote_columns(self, source_id: int, database: str, table: str,
                            schema: Optional[str] = None) -> List[dict]:
        connect_db = database if schema else None
        scope = self._resolve_scope(schema, database)
        cols = self._with_conn(
            source_id,
            lambda a, c: a.list_columns(c, scope, [table]).get(table, []),
            connect_database=connect_db)
        return [asdict(col) for col in cols]

    # ------------------------------------------------------------------ #
    # 全量扫描
    # ------------------------------------------------------------------ #
    def start_scan(
        self,
        source_id: int,
        database: str,
        with_profile: bool = False,
        creator_id: Optional[int] = None,
        connect_database: Optional[str] = None,
    ) -> MetaScanJob:
        """创建扫描任务并同步执行（本阶段无独立任务队列，执行在请求内完成）。

        ``database``＝待扫描作用域（MySQL 族=库名；PG 族=schema）；
        ``connect_database``＝PG 族跨物理库扫描时的连接目标覆盖，缺省连 ds.database。"""
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
        self._run(job, ds, connect_database=connect_database)
        self.db.commit()
        return job

    # ------------------------------------------------------------------ #
    # 选表导入（SQLBot 式：勾选远端表写入元数据快照）
    # ------------------------------------------------------------------ #
    def import_tables(self, source_id: int, database: str, tables: List[str],
                      with_profile: bool = False,
                      creator_id: Optional[int] = None,
                      schema: Optional[str] = None) -> Dict[str, Any]:
        """按勾选表导入元数据；单表覆盖，远端不存在的表记入 failed。

        PG 族三级导入：``database``=物理库（重连目标）、``schema``=表所在模式
        （快照 meta_table.database 存模式，与下游 ``{schema}.{table}`` 限定一致）。"""
        if not tables:
            raise ValueError("请至少勾选一张待导入的表")
        ds = self._prepare(self._ds.get_or_404(source_id))
        scope = self._resolve_scope(schema, database)
        connect_db = database if schema else None
        # 快照第一级（meta_table.db_name）：按族语义解析物理库
        physical = self._physical_db(ds, scope=scope, connect_database=connect_db)
        job = MetaScanJob(
            tenant_id=self.tenant_id, source_id=source_id, database=database,
            job_kind="import", status="running", with_profile=bool(with_profile),
            tables_json=list(tables), creator_id=creator_id, started_at=self._now(),
        )
        self.db.add(job)
        self.db.flush()
        adapter = get_adapter(ds.source_type)
        imported = 0
        column_total = 0
        failed: List[Dict[str, str]] = []
        started = time.perf_counter()
        conn, cleanup = adapter.open(ds, connect_database=connect_db)
        try:
            present = {t.name: t for t in adapter.list_tables(conn, scope)}
            for name in tables:
                t = present.get(name)
                if t is None:
                    failed.append({"table": name, "error": "远端不存在该表（可能已删除）"})
                    continue
                column_total += self._sync_table(adapter, conn, source_id, physical,
                                                 scope, t, with_profile=bool(with_profile))
                imported += 1
                job.progress = round(imported / len(tables) * 100, 2)
                self.db.flush()
            job.stats_json = {"table_count": imported, "column_count": column_total,
                              "failed": failed}
            job.status = "succeeded" if imported or not failed else "failed"
            if not imported and failed:
                job.error_detail = "所选表均未导入成功"
        except Exception as exc:  # noqa: BLE001
            self._fail(job, exc)
            self.db.commit()
            raise
        finally:
            cleanup()
        job.finished_at = self._now()
        job.duration_ms = int((time.perf_counter() - started) * 1000)
        self.db.commit()
        return {"job_id": job.id, "imported": imported, "columns": column_total,
                "failed": failed}

    # ------------------------------------------------------------------ #
    def _run(self, job: MetaScanJob, ds: DataSource, connect_database: Optional[str] = None) -> None:
        job.status = "running"
        job.started_at = self._now()
        started = time.perf_counter()
        try:
            adapter = get_adapter(ds.source_type)
            conn, cleanup = adapter.open(self._prepare(ds), connect_database=connect_database)
        except Exception as exc:  # noqa: BLE001
            self._fail(job, exc)
            return

        physical = self._physical_db(ds, scope=job.database, connect_database=connect_database)
        try:
            tables = adapter.list_tables(conn, job.database)
            total = len(tables) or 1
            column_total = 0
            truncated = False

            # 幂等覆盖：清旧快照（按 物理库+作用域 两级界定，跨库同名 schema 互不覆盖）
            self.db.execute(
                delete(MetaTable).where(
                    MetaTable.source_id == ds.id,
                    MetaTable.db_name == physical,
                    MetaTable.database == job.database,
                )
            )

            for idx, t in enumerate(tables):
                column_total += self._sync_table(adapter, conn, ds.id, physical,
                                                 job.database, t,
                                                 with_profile=bool(job.with_profile))
                job.progress = round((idx + 1) / total * 100, 2)
                self.db.flush()

            if len(tables) == 0:
                job.progress = 100.0
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
            cleanup()

        job.finished_at = self._now()
        job.duration_ms = int((time.perf_counter() - started) * 1000)

    def _sync_table(self, adapter, conn, source_id: int, physical_db: str, database: str,
                    t, with_profile: bool) -> int:
        """单表快照覆盖写（全量扫描与选表导入共用）；返回写入列数。

        ``physical_db``=物理库（meta_table.db_name，PG 族三级第一级），
        ``database``=限定作用域（PG 族=schema，其余族=库名）。"""
        self.db.execute(
            delete(MetaTable).where(
                MetaTable.source_id == source_id,
                MetaTable.db_name == physical_db,
                MetaTable.database == database,
                MetaTable.table_name == t.name,
            )
        )
        mt = MetaTable(
            tenant_id=self.tenant_id,
            source_id=source_id,
            db_name=physical_db,
            database=database,
            table_name=t.name,
            table_type=t.table_type,
            table_comment=t.comment,
            row_count=t.row_count,
            engine=t.engine,
        )
        self.db.add(mt)
        self.db.flush()

        cols = adapter.list_columns(conn, database, [t.name]).get(t.name, [])
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
            if with_profile:
                profile = adapter.profile_column(conn, database, t.name, c.name, 1000)
                mc.profile_json = asdict(profile)
            self.db.add(mc)
        mt.column_count = len(cols)
        self.db.flush()
        return len(cols)

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
