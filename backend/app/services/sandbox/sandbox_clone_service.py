"""世界克隆服务（spec §4.1 sandbox_clone_service）。

克隆唯一入口 = :class:`ReadonlyQueryService.run`（只读下推 SELECT，明文不出源库）。
脱敏在 SELECT 层以 ``'***' AS <col>`` 字面量替换（V4/A3），命中判定：
``MetaStandard.mask_rule`` 非空 **或** ``MetaColumn.pii_level == 'L3'``。
产出物只有沙箱行（entity 当前态 + 基线检查点 seq=0 及其快照行），绝不回写生产。

后台线程执行照 ``ontology_build_service`` 的 ``_EXECUTOR`` + ``SessionLocal`` 独立会话模式。
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import ApiError, CLONE_LIMIT_EXCEEDED
from app.db.database import SessionLocal
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.standard import MetaStandard
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxCheckpoint, SandboxEntity, SandboxScene,
)

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sandbox-clone")

_MASK_LITERAL = "***"


def submit_clone(scene_id: int, tenant_id: int) -> None:
    """投递后台克隆（建景请求已提交 draft 之后调用）。"""
    _EXECUTOR.submit(_run_clone, scene_id, tenant_id)


def _run_clone(scene_id: int, tenant_id: int) -> None:
    db = SessionLocal()
    try:
        SandboxCloneService(db, tenant_id).clone_scene(scene_id)
    except Exception as exc:  # noqa: BLE001 - worker 边界，任何异常落 failed 不外逃
        logger.exception(f"沙箱克隆 worker 异常 scene={scene_id}: {exc}")
        db.rollback()
        s = db.get(SandboxScene, scene_id)
        if s is not None and s.tenant_id == tenant_id:
            s.status = "failed"
            s.error_detail = str(exc)[:2000]
            db.commit()
    finally:
        db.close()


class SandboxCloneService:
    """世界克隆（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(
        self, db: Session, tenant_id: Optional[int],
        fetcher: Optional[Callable[[int, str, int], dict]] = None,
    ) -> None:
        if tenant_id is None:
            raise ValueError("SandboxCloneService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._fetcher = fetcher

    # ------------------------------------------------------------- 纯函数：SQL 计划

    def build_select(self, snapshot: dict, object_code: str, masked_out: list) -> Optional[tuple]:
        """由发布快照派生下推 SELECT；脱敏列在字段层以 '***' 字面量替换。

        返回 ``(sql, meta)``；meta={source_id, db, table, masked_columns[], pk_column}。
        对象无任何映射列 → 返回 None（无数据可克隆）。
        """
        obj = next((o for o in snapshot.get("objects", []) if o["code"] == object_code), None)
        if obj is None:
            return None
        table_ids = [tm["table_id"] for tm in snapshot.get("mappings", {}).get("table", [])
                     if tm["object_standard_id"] == obj["id"]]
        if not table_ids:
            return None
        std_ids = {p["standard_id"] for p in snapshot.get("properties", [])
                   if p["object_id"] == obj["id"]}
        # 命中本对象标准项的映射列（且属于本对象映射的表）
        column_ids = [cm["column_id"] for cm in snapshot.get("mappings", {}).get("column", [])
                      if cm["standard_id"] in std_ids]
        if not column_ids:
            return None
        cols = list(self.db.execute(
            select(MetaColumn).where(
                MetaColumn.tenant_id == self.tenant_id,
                MetaColumn.id.in_(column_ids),
                MetaColumn.table_id.in_(table_ids),
            )
        ).scalars().all())
        if not cols:
            return None
        tbl = self.db.get(MetaTable, cols[0].table_id)
        if tbl is None or tbl.tenant_id != self.tenant_id:
            return None

        std_by_id = {}
        for std_id in {cm["standard_id"] for cm in snapshot.get("mappings", {}).get("column", [])
                       if cm["column_id"] in {c.id for c in cols}}:
            st = self.db.get(MetaStandard, std_id)
            if st is not None:
                std_by_id[std_id] = st
        col_to_std = {}
        for cm in snapshot.get("mappings", {}).get("column", []):
            if cm["column_id"] in {c.id for c in cols}:
                col_to_std[cm["column_id"]] = cm["standard_id"]

        select_parts = []
        masked_cols = []
        # 列序固定（按 column_id 升序）保证取数确定性
        for c in sorted(cols, key=lambda x: x.id):
            std = std_by_id.get(col_to_std.get(c.id))
            if (std is not None and std.mask_rule) or c.pii_level == "L3":
                select_parts.append(f"'{_MASK_LITERAL}' AS {c.column_name}")
                masked_cols.append(c.column_name)
            else:
                select_parts.append(f'"{c.column_name}"')

        table_ref = f'"{tbl.database}"."{tbl.table_name}"'
        max_entities = (masked_out or {}).get("max_entities")  # masked_out 兼容为 scope dict 传入
        limit = int(max_entities) + 1 if max_entities else 5001
        sql = f"SELECT {', '.join(select_parts)} FROM {table_ref} ORDER BY 1 LIMIT {limit}"
        return sql, {
            "source_id": tbl.source_id, "db": tbl.database, "table": tbl.table_name,
            "masked_columns": masked_cols, "pk_column": sorted(cols, key=lambda x: x.id)[0].column_name,
        }

    # ------------------------------------------------------------- 端到端克隆

    def clone_scene(self, scene_id: int) -> None:
        """幂等：仅 status in (draft, failed) 可跑；产出 entity 当前态 + 基线检查点及快照行。"""
        scene = self.db.execute(
            select(SandboxScene).where(
                SandboxScene.tenant_id == self.tenant_id, SandboxScene.id == scene_id
            )
        ).scalar_one_or_none()
        if scene is None:
            return
        if scene.status not in ("draft", "failed"):
            return  # 幂等：已 running/其他态不重复克隆

        scene.status = "cloning"
        self.db.commit()

        from app.models.ontology.ontology import MetaOntologyVersion
        ver = self.db.execute(
            select(MetaOntologyVersion).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == scene.ontology_id,
                MetaOntologyVersion.version == scene.ontology_version,
            )
        ).scalar_one_or_none()
        snapshot = ver.snapshot_json or {}
        scope = scene.clone_scope_json or {}
        object_codes = scope.get("object_codes") or [o["code"] for o in snapshot.get("objects", [])]
        max_entities = int(scope.get("max_entities", 500))

        branch = self.db.execute(
            select(SandboxBranch).where(
                SandboxBranch.tenant_id == self.tenant_id,
                SandboxBranch.scene_id == scene.id,
                SandboxBranch.base_checkpoint_id.is_(None),
            ).order_by(SandboxBranch.id)
        ).scalars().first()

        all_masked: list[str] = []
        total = 0
        for object_code in object_codes:
            built = self.build_select(snapshot, object_code, {"max_entities": max_entities})
            if built is None:
                continue
            sql, meta = built
            if meta["masked_columns"]:
                all_masked.extend(meta["masked_columns"])
            result = self._fetch(meta["source_id"], sql, max_entities + 1)
            rows = result.get("rows", [])
            columns = result.get("columns", [])
            if len(rows) > max_entities:
                raise ApiError(CLONE_LIMIT_EXCEEDED, f"对象 {object_code} 行数超上限",
                               http_status=400, detail={"object_code": object_code, "count": len(rows)})
            prefix = object_code[:3].upper()
            for i, row in enumerate(rows):
                props = {}
                row_masked = False
                for j, col in enumerate(columns):
                    val = row[j] if j < len(row) else None
                    if val == _MASK_LITERAL:
                        row_masked = True
                    props[col] = "" if val is None else str(val)
                entity_code = f"{prefix}{i:03d}"
                pk_val = props.get(meta["pk_column"], "")
                self.db.add(SandboxEntity(
                    tenant_id=self.tenant_id, scene_id=scene.id, branch_id=branch.id,
                    entity_code=entity_code, object_code=object_code, props_json=props,
                    masked=row_masked, origin="clone",
                    source_ref_json={"source_id": meta["source_id"], "db": meta["db"],
                                     "table": meta["table"], "pk": pk_val},
                ))
                total += 1
            self.db.flush()

        # 基线检查点（seq=0，占 1 格上限）+ 其快照行
        cp = SandboxCheckpoint(
            tenant_id=self.tenant_id, scene_id=scene.id, branch_id=branch.id,
            tick=0, seq=0, label="基线快照",
            stats_json={"entities": total, "relations": 0, "kpi": {}},
        )
        self.db.add(cp)
        self.db.flush()
        current_rows = self.db.execute(
            select(SandboxEntity).where(
                SandboxEntity.tenant_id == self.tenant_id,
                SandboxEntity.branch_id == branch.id,
                SandboxEntity.checkpoint_id.is_(None),
            )
        ).scalars().all()
        for e in current_rows:
            self.db.add(SandboxEntity(
                tenant_id=self.tenant_id, scene_id=scene.id, branch_id=branch.id,
                checkpoint_id=cp.id, entity_code=e.entity_code, object_code=e.object_code,
                props_json=dict(e.props_json or {}), risk_score=e.risk_score, masked=e.masked,
                source_ref_json=e.source_ref_json, origin="clone",
            ))

        scene.status = "running"
        scene.clone_stats_json = {"entities": total, "relations": 0, "masked_columns": sorted(set(all_masked))}
        self.db.commit()

    def _fetch(self, source_id: int, sql: str, limit: int) -> dict:
        if self._fetcher is not None:
            return self._fetcher(source_id, sql, limit)
        from app.services.dataops.query_service import ReadonlyQueryService
        return ReadonlyQueryService(self.db, self.tenant_id).run(source_id, sql, limit)
