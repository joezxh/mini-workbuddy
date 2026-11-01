"""本体构建服务（P0-3：任务生命周期 + 规则流水线 + 后台 worker + SSE 数据源）。

设计真源：docs/superpowers/specs/2026-10-31-ontology-capability-design.md §4.1-4.4 / §5.4 / §6.1 E4-E8 / §6.2。

职责切分：
- **生命周期**（请求线程，用请求 Session）：``create_build_job``（幂等 + 校验）、
  ``list_build_jobs`` / ``get_build_job`` / ``cancel_build_job``；事务边界在路由层。
- **流水线**（后台 worker，``SessionLocal()`` 新建 Session）：``run_pipeline`` 逐批
  extract→align→judge→merge，upsert CDM 结构 + 落 ``build_item``/``evidence``，
  批次级 SAVEPOINT、任务级先 rollback 再标 failed（修 OntoMind R2）。

硬约束（决策基线）：
- D3 rev.2 防线①：``origin='llm'`` 候选只能 ``status='suggested'``；本服务是**规则通道**，
  产出 ``origin='rule'``，自动采纳仅对 ``tier(conf) >= 0.85`` 生效（§5.4，复用 rule_engine 单一真源）。
- §4.2：已 ``review_status=accepted`` 的元素再抽到 → ``action=skip``，不覆盖人工结论；
  落库按 code upsert（``ON CONFLICT`` 语义），属性/映射不再 IntegrityError（修 R1）。
- §4.7：作用域空即 ``BUILD_SCOPE_EMPTY``；本体 ``stopped`` 即 ``ONTOLOGY_STOPPED``；跨源拒绝（单 source_id）。
- §4.4：LLM 缺席/降级不污染 source；本 P0-3 不调 LLM（P0-8 接语义补全），``stats.semantic='skipped'``。
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.dataops.rule_engine import CONF_AUTO_ACCEPT, RuleEngine, tier
from app.core.api_error import (
    ApiError, BUILD_ALREADY_RUNNING, BUILD_SCOPE_EMPTY, ONTOLOGY_NOT_FOUND, ONTOLOGY_STOPPED,
)
from app.db.database import SessionLocal
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.meta_relation import MetaRelation
from app.models.dataops.ontology import (
    MetaOntology, MetaOntologyBuildItem, MetaOntologyBuildJob, MetaOntologyEvidence,
)
from app.models.dataops.standard import MetaColumnStandard
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute, MetaTableStandard,
)
from app.services.dataops import alias_json
from app.services.dataops.standard_service import MetaStandardService

#: 分层前缀（编码归一剥离，§4.1 align：code 归一）
_LAYER_PREFIX_RE = re.compile(r"^(ods|stg|raw|dw|dwd|dws|ads|dim|fact|dm|tmp|mid)_", re.I)

JOB_TIMEOUT_SECONDS = 30 * 60
"""running 任务超过此阈值视为幽灵任务（§4.3），由健康检查兜底标 failed。"""

_BATCH_SIZE = 20


def _norm_object_code(table_name: str) -> str:
    """物理表名 → 对象 code（剥分层前缀 + 归一 snake + obj_ 前缀）。"""
    base = _LAYER_PREFIX_RE.sub("", (table_name or "").strip().lower())
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return f"obj_{base}" if base else "obj_unknown"


def _norm_relation_code(obj_from: str, obj_to: str) -> str:
    a = obj_from[4:] if obj_from.startswith("obj_") else obj_from
    b = obj_to[4:] if obj_to.startswith("obj_") else obj_to
    return (f"rel_{a}__{b}")[:64]


@dataclass
class BatchStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    rejected: int = 0


@dataclass
class BuildStats:
    tables: int = 0
    objects_created: int = 0
    objects_updated: int = 0
    properties: int = 0
    relations: int = 0
    mappings: int = 0
    skipped_human: int = 0
    semantic: str = "skipped"       # P0-3 不调 LLM；P0-8 接语义补全后改写
    semantic_failed: int = 0
    degraded: bool = False
    degraded_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 后台 worker 执行器（线程池，每任务一条流水线，独立 Session）
# ---------------------------------------------------------------------------
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ont_build")


def submit_build(job_id: int, tenant_id: int) -> None:
    """投递后台构建（请求已提交 pending job 之后调用）。"""
    _EXECUTOR.submit(_run_in_worker, job_id, tenant_id)


def _run_in_worker(job_id: int, tenant_id: int) -> None:
    db = SessionLocal()
    try:
        OntologyBuildService(db, tenant_id).run_pipeline(job_id)
    except Exception as exc:  # noqa: BLE001 - worker 边界，任何异常都要落 failed 不外逃
        logger.exception(f"本体构建 worker 异常 job={job_id}: {exc}")
        db.rollback()
        try:
            job = db.get(MetaOntologyBuildJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_code = "BUILD_FAILED"
                job.error_detail = str(exc)[:2000]
                job.finished_at = func.now()
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


class OntologyBuildService:
    """本体构建（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyBuildService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------ 生命周期

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    def create_build_job(
        self,
        ontology_id: int,
        *,
        mode: str,
        scope: dict,
        idempotency_key: str,
    ) -> Tuple[MetaOntologyBuildJob, bool]:
        """幂等创建构建任务；返回 ``(job, created)``，``created=False`` 表示命中既有任务不重复启动。"""
        ontology = self._ontology_or_404(ontology_id)
        if ontology.status == "stopped":
            raise ApiError(ONTOLOGY_STOPPED, f"本体已停止，拒绝构建: {ontology.code}")
        if mode not in ("rules", "rules+semantic"):
            mode = "rules"
        # 作用域校验（§4.7）
        source_id = scope.get("source_id")
        tables = [t for t in (scope.get("tables") or []) if t]
        if not source_id or (scope.get("mode", "tables") == "tables" and not tables):
            raise ApiError(BUILD_SCOPE_EMPTY, "构建作用域为空（需 source_id + tables）")
        if idempotency_key:
            existing = self.db.execute(
                select(MetaOntologyBuildJob).where(
                    MetaOntologyBuildJob.tenant_id == self.tenant_id,
                    MetaOntologyBuildJob.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing, False
        job = MetaOntologyBuildJob(
            tenant_id=self.tenant_id,
            ontology_id=ontology_id,
            idempotency_key=idempotency_key or f"job_{int(time.time() * 1000)}",
            mode=mode,
            scope_json=scope,
            status="pending",
            progress=0,
        )
        self.db.add(job)
        self.db.flush()
        return job, True

    def _job_or_404(self, job_id: int) -> MetaOntologyBuildJob:
        job = self.db.execute(
            select(MetaOntologyBuildJob).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.id == job_id,
            )
        ).scalar_one_or_none()
        if job is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "构建任务不存在", http_status=404, detail={"job_id": job_id})
        return job

    def list_build_jobs(self, ontology_id: int) -> List[dict]:
        self._ontology_or_404(ontology_id)
        jobs = self.db.execute(
            select(MetaOntologyBuildJob)
            .where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.ontology_id == ontology_id,
            )
            .order_by(MetaOntologyBuildJob.id.desc())
        ).scalars().all()
        return [self.serialize_job(j) for j in jobs]

    def get_build_job(self, job_id: int) -> dict:
        """任务详情（不含 item 的 delta 大字段，§6.1 E6）。"""
        job = self._job_or_404(job_id)
        items = self.db.execute(
            select(
                MetaOntologyBuildItem.element_kind,
                MetaOntologyBuildItem.element_code,
                MetaOntologyBuildItem.action,
                MetaOntologyBuildItem.origin,
                MetaOntologyBuildItem.verdict,
                MetaOntologyBuildItem.confidence,
                MetaOntologyBuildItem.status,
            ).where(MetaOntologyBuildItem.job_id == job_id)
            .order_by(MetaOntologyBuildItem.id)
        ).all()
        payload = self.serialize_job(job)
        payload["items"] = [
            {
                "element_kind": r.element_kind, "element_code": r.element_code,
                "action": r.action, "origin": r.origin, "verdict": r.verdict,
                "confidence": r.confidence, "status": r.status,
            }
            for r in items
        ]
        return payload

    def cancel_build_job(self, job_id: int) -> MetaOntologyBuildJob:
        """协作式取消：pending/running → cancelled，worker 每批次轮询该状态后主动收尾。"""
        job = self._job_or_404(job_id)
        if job.status in ("succeeded", "failed", "cancelled"):
            raise ApiError(
                BUILD_ALREADY_RUNNING if job.status == "running" else BUILD_ALREADY_RUNNING,
                f"任务已处于终态: {job.status}", detail={"job_id": job_id, "status": job.status},
            )
        job.status = "cancelled"
        self.db.flush()
        return job

    @staticmethod
    def serialize_job(j: MetaOntologyBuildJob) -> dict:
        return {
            "id": j.id,
            "ontology_id": j.ontology_id,
            "mode": j.mode,
            "status": j.status,
            "phase": j.phase,
            "progress": j.progress,
            "idempotency_key": j.idempotency_key,
            "stats": j.stats_json,
            "error_code": j.error_code,
            "error_detail": j.error_detail,
            "duration_ms": j.duration_ms,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }

    def job_snapshot(self, job_id: int) -> Optional[dict]:
        """SSE 轮询用轻量快照（独立于请求 Session）。"""
        j = self.db.execute(
            select(MetaOntologyBuildJob).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.id == job_id,
            )
        ).scalar_one_or_none()
        if j is None:
            return None
        return {"status": j.status, "phase": j.phase, "progress": j.progress, "stats": j.stats_json,
                "error_code": j.error_code}

    # ------------------------------------------------------------ 流水线

    def run_pipeline(self, job_id: int) -> None:
        """后台 worker 入口：跑完整流水线并管理提交/回滚（§4.3）。"""
        job = self._job_or_404(job_id)
        if job.status not in ("pending",):
            return
        job.status = "running"
        job.phase = "extract"
        job.started_at = func.now()
        self.db.commit()

        stats = BuildStats()
        t0 = time.monotonic()
        try:
            tables = self._resolve_scope(job.scope_json or {})
            stats.tables = len(tables)
            if not tables:
                raise ApiError(BUILD_SCOPE_EMPTY, "解析后可构建表为空")

            standards = [
                MetaStandardService.serialize(s)
                for s in MetaStandardService(self.db, self.tenant_id).list_standards(status="published")
            ]
            catalog_id = self._ontology_or_404(job.ontology_id).root_catalog_id

            total = max(1, (len(tables) + _BATCH_SIZE - 1) // _BATCH_SIZE)
            for bi, batch in enumerate(self._chunks(tables, _BATCH_SIZE), start=1):
                if self._is_cancelled(job_id):
                    self._finish(job, "cancelled", stats, t0)
                    return
                job.phase = "merge"
                job.progress = round(bi / total, 4)
                # 批次级 SAVEPOINT：单条失败只回滚该条（§4.3）
                sp = self.db.begin_nested()
                try:
                    for table in batch:
                        self._process_table(job, table, standards, catalog_id, stats)
                    sp.commit()
                except Exception as exc:  # noqa: BLE001
                    sp.rollback()
                    logger.warning(f"构建批次 {bi} 回滚: {exc}")
                self.db.commit()

            # 关系推断（scope 内表↔表），落 relation 候选
            self._build_relations(job, tables, catalog_id, stats)

            self._finish(job, "succeeded", stats, t0)
        except ApiError as exc:
            self.db.rollback()
            job = self._job_or_404(job_id)
            job.status = "failed"
            job.error_code = exc.code
            job.error_detail = str(exc)[:2000]
            job.stats_json = self._stats_dict(stats)
            job.finished_at = func.now()
            job.duration_ms = int((time.monotonic() - t0) * 1000)
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            job = self._job_or_404(job_id)
            job.status = "failed"
            job.error_code = "BUILD_FAILED"
            job.error_detail = str(exc)[:2000]
            job.finished_at = func.now()
            job.duration_ms = int((time.monotonic() - t0) * 1000)
            self.db.commit()

    def _resolve_scope(self, scope: dict) -> List[MetaTable]:
        """三种圈定入口归一为 MetaTable 列表（§4.7）：tables / tags / catalog。"""
        source_id = scope.get("source_id")
        stmt = select(MetaTable).where(MetaTable.tenant_id == self.tenant_id)
        if source_id:
            stmt = stmt.where(MetaTable.source_id == source_id)
        db_name = scope.get("database") or scope.get("db_name")
        if db_name:
            stmt = stmt.where(MetaTable.database == db_name)
        mode = scope.get("mode", "tables")
        if mode == "tables":
            names = scope.get("tables") or []
            if names:
                stmt = stmt.where(MetaTable.table_name.in_(names))
        elif mode == "tags":
            tag_ids = scope.get("tag_ids") or []
            from app.models.dataops.asset_tag import MetaAssetTagBinding
            table_ids = self.db.execute(
                select(MetaAssetTagBinding.asset_id).where(
                    MetaAssetTagBinding.tenant_id == self.tenant_id,
                    MetaAssetTagBinding.asset_kind == "table",
                    MetaAssetTagBinding.tag_id.in_(tag_ids),
                )
            ).scalars().all()
            stmt = stmt.where(MetaTable.id.in_(list(table_ids)))
        elif mode == "catalog":
            catalog_ids = scope.get("catalog_ids") or []
            obj_ids = self.db.execute(
                select(MetaObjectStandard.id).where(
                    MetaObjectStandard.tenant_id == self.tenant_id,
                    MetaObjectStandard.catalog_id.in_(catalog_ids),
                )
            ).scalars().all()
            tids = self.db.execute(
                select(MetaTableStandard.table_id).where(
                    MetaTableStandard.tenant_id == self.tenant_id,
                    MetaTableStandard.object_standard_id.in_(list(obj_ids)),
                )
            ).scalars().all()
            stmt = stmt.where(MetaTable.id.in_(list(tids)))
        return list(self.db.execute(stmt).scalars().all())

    def _process_table(
        self, job: MetaOntologyBuildJob, table: MetaTable,
        standards: List[dict], catalog_id: Optional[int], stats: BuildStats,
    ) -> None:
        obj_code = _norm_object_code(table.table_name)
        verdict, reason = self._judge_object(table, obj_code)
        obj = self._upsert_object(job, table, obj_code, catalog_id, verdict, reason, stats)
        # 表 → 对象 映射
        self._upsert_table_mapping(job, table, obj, stats)
        # 列 → 属性 + 列 → 标准 映射
        cols = self.db.execute(
            select(MetaColumn).where(MetaColumn.table_id == table.id).order_by(MetaColumn.ordinal)
        ).scalars().all()
        for col in cols:
            self._process_column(job, obj, col, standards, stats)

    def _process_column(
        self, job: MetaOntologyBuildJob, obj: MetaObjectStandard,
        col: MetaColumn, standards: List[dict], stats: BuildStats,
    ) -> None:
        ann = RuleEngine.detect_semantic(
            col.column_name, data_type=col.data_type, comment=col.column_comment,
            profile_top_values=(col.profile_json or {}).get("top_values"),
        )
        matched = RuleEngine.match_standard(
            col.column_name, col.column_comment, col.data_type, standards
        )
        if matched is None or matched.standard_id is None:
            return
        status = tier(matched.confidence)
        if status == "drop":
            return
        prop_code = f"{obj.code}.{matched.standard_code}"
        # 属性绑定 object↔standard（幂等 upsert）
        attr = self.db.execute(
            select(MetaObjectStandardAttribute).where(
                MetaObjectStandardAttribute.object_id == obj.id,
                MetaObjectStandardAttribute.standard_id == matched.standard_id,
            )
        ).scalar_one_or_none()
        action = "insert"
        if attr is None:
            attr = MetaObjectStandardAttribute(
                tenant_id=self.tenant_id, object_id=obj.id, standard_id=matched.standard_id,
                required=(col.column_key == "PRI"), review_status=status,
            )
            self.db.add(attr)
            self.db.flush()
        else:
            if attr.review_status == "accepted":
                action = "skip"  # §4.2 不覆盖人工结论
            else:
                attr.review_status = status
                action = "update"
        # 列 → 标准 映射（meta_column_standard，尊重人工 accepted）
        self._upsert_column_mapping(job, col, matched, status, stats)
        stats.properties += 1
        self._record_item(
            job, "property", prop_code, action, "rule",
            delta={"object_code": obj.code, "standard_code": matched.standard_code,
                   "column": col.column_name, "semantic_type": ann.semantic_type,
                   "pii_level": ann.pii_level},
            verdict=("pass" if status == "accepted" else "warn"),
            confidence=matched.confidence, status=status, element_id=attr.id,
        )

    def _build_relations(
        self, job: MetaOntologyBuildJob, tables: List[MetaTable],
        catalog_id: Optional[int], stats: BuildStats,
    ) -> None:
        """scope 内基于已落 object 映射的表，用推断关系产 relation 候选（低置信默认 suggested）。"""
        if job.mode not in ("rules", "rules+semantic"):
            return
        by_table = {t.table_name: t for t in tables}
        source_ids = {t.source_id for t in tables}
        if not source_ids:
            return
        db_names = {t.database for t in tables}
        inferred = self.db.execute(
            select(MetaRelation).where(
                MetaRelation.tenant_id == self.tenant_id,
                MetaRelation.source_id.in_(list(source_ids)),
                MetaRelation.database.in_(list(db_names)),
            )
        ).scalars().all()
        # 表名 → 对象
        table_to_obj: Dict[str, MetaObjectStandard] = {}
        for t in tables:
            ts = self.db.execute(
                select(MetaTableStandard).where(MetaTableStandard.table_id == t.id)
            ).scalar_one_or_none()
            if ts is not None:
                obj = self.db.get(MetaObjectStandard, ts.object_standard_id)
                if obj is not None:
                    table_to_obj[t.table_name] = obj
        for rel in inferred:
            left_obj = table_to_obj.get(rel.left_table)
            right_obj = table_to_obj.get(rel.right_table)
            if left_obj is None or right_obj is None or left_obj.id == right_obj.id:
                continue
            code = _norm_relation_code(left_obj.code, right_obj.code)
            conf = float(rel.confidence or 0.6)
            status = tier(conf) if conf >= 0.65 else "suggested"
            existing = self.db.execute(
                select(MetaObjectRelation).where(
                    MetaObjectRelation.tenant_id == self.tenant_id,
                    MetaObjectRelation.code == code,
                )
            ).scalar_one_or_none()
            action = "insert"
            if existing is None:
                existing = MetaObjectRelation(
                    tenant_id=self.tenant_id, catalog_id=catalog_id, code=code,
                    name=f"{left_obj.name}→{right_obj.name}",
                    from_object_id=left_obj.id, to_object_id=right_obj.id,
                    relation_type="N:1", status="draft", source="rule",
                    review_status=status, confidence=conf,
                )
                self.db.add(existing)
                self.db.flush()
            else:
                if existing.review_status == "accepted":
                    action = "skip"
                else:
                    existing.review_status = status
                    existing.confidence = conf
                    action = "update"
            stats.relations += 1
            self._add_evidence(job.ontology_id, "relation", code, "overlap",
                              {"left": rel.left_table, "right": rel.right_table}, conf)
            self._record_item(
                job, "relation", code, action, "rule",
                delta={"from": left_obj.code, "to": right_obj.code, "relation_type": "N:1"},
                verdict="warn", confidence=conf, status=status, element_id=existing.id,
            )

    # ---------------------------------------------------------- upsert 内部

    def _upsert_object(
        self, job: MetaOntologyBuildJob, table: MetaTable, code: str,
        catalog_id: Optional[int], verdict: str, reason: Optional[str], stats: BuildStats,
    ) -> MetaObjectStandard:
        name = table.table_comment or table.biz_name or table.table_name
        conf = 0.66
        if table.table_comment:
            conf += 0.1
        if table.biz_name:
            conf += 0.1
        conf = round(min(conf, 0.95), 4)
        status = tier(conf) if verdict != "fail" else "suggested"
        existing = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id, MetaObjectStandard.code == code
            )
        ).scalar_one_or_none()
        action = "insert"
        if existing is None:
            existing = MetaObjectStandard(
                tenant_id=self.tenant_id, catalog_id=catalog_id, code=code, name=name[:200],
                description=table.biz_description, domain=None, status="draft",
                source="rule", review_status=status, confidence=conf,
            )
            self.db.add(existing)
            self.db.flush()
            stats.objects_created += 1
        else:
            if existing.review_status == "accepted":
                action = "skip"
                stats.skipped_human += 1
            else:
                if catalog_id and not existing.catalog_id:
                    existing.catalog_id = catalog_id
                existing.confidence = conf
                existing.review_status = status
                action = "update"
                stats.objects_updated += 1
        ev_id = self._add_evidence(
            job.ontology_id, "object", code, "naming",
            {"rule": "layer_prefix_strip", "table": table.table_name, "score": conf, "why": reason},
            conf,
        )
        existing.evidence_ref = ev_id
        self._record_item(
            job, "object", code, action, "rule",
            delta={"name": name, "table": table.table_name, "definition": table.biz_description},
            verdict=verdict, verdict_reason=reason, confidence=conf, status=status, element_id=existing.id,
        )
        return existing

    def _upsert_table_mapping(
        self, job: MetaOntologyBuildJob, table: MetaTable, obj: MetaObjectStandard, stats: BuildStats,
    ) -> None:
        existing = self.db.execute(
            select(MetaTableStandard).where(MetaTableStandard.table_id == table.id)
        ).scalar_one_or_none()
        code = f"map:{table.id}->obj:{obj.code}"
        status = obj.review_status
        action = "insert"
        if existing is None:
            self.db.add(MetaTableStandard(
                tenant_id=self.tenant_id, table_id=table.id, object_standard_id=obj.id,
                status=status, source="rule", confidence=obj.confidence,
            ))
            stats.mappings += 1
        else:
            if existing.source == "human" and existing.status == "accepted":
                action = "skip"
                stats.skipped_human += 1
            else:
                existing.object_standard_id = obj.id
                existing.status = status
                existing.source = "rule"
                action = "update"
                stats.mappings += 1
        self.db.flush()
        self._record_item(job, "mapping", code, action, "rule",
                          delta={"table": table.table_name, "object_code": obj.code},
                          verdict="pass", confidence=obj.confidence, status=status)

    def _upsert_column_mapping(
        self, job: MetaOntologyBuildJob, col: MetaColumn, matched, status: str, stats: BuildStats,
    ) -> None:
        existing = self.db.execute(
            select(MetaColumnStandard).where(MetaColumnStandard.column_id == col.id)
        ).scalar_one_or_none()
        code = f"map:col:{col.id}->std:{matched.standard_code}"
        action = "insert"
        if existing is None:
            self.db.add(MetaColumnStandard(
                tenant_id=self.tenant_id, column_id=col.id, standard_id=matched.standard_id,
                confidence=matched.confidence, evidence_json=matched.evidence,
                status=status, source="rule",
            ))
            stats.mappings += 1
        else:
            if existing.source == "human" and existing.status == "accepted":
                action = "skip"
                stats.skipped_human += 1
            else:
                existing.standard_id = matched.standard_id
                existing.confidence = matched.confidence
                existing.evidence_json = matched.evidence
                existing.status = status
                existing.source = "rule"
                action = "update"
                stats.mappings += 1
        self.db.flush()
        self._record_item(job, "mapping", code, action, "rule",
                          delta={"column": col.column_name, "standard_code": matched.standard_code},
                          verdict="pass", confidence=matched.confidence, status=status)

    # ---------------------------------------------------------- item / evidence

    def _record_item(
        self, job: MetaOntologyBuildJob, kind: str, code: str, action: str, origin: str,
        *, delta: dict, verdict: Optional[str] = None, verdict_reason: Optional[str] = None,
        confidence: Optional[float] = None, status: str = "suggested", element_id: Optional[int] = None,
    ) -> None:
        """按 (job_id, kind, code) 唯一 upsert 候选明细（§4.2 同任务同元素只留最终态）。

        D3 rev.2 防线①：``origin='llm'`` 强制 ``status='suggested'``（本规则通道只产 rule）。
        """
        if origin == "llm":
            status = "suggested"
        elif status == "drop":
            status = "dropped"
        existing = self.db.execute(
            select(MetaOntologyBuildItem).where(
                MetaOntologyBuildItem.job_id == job.id,
                MetaOntologyBuildItem.element_kind == kind,
                MetaOntologyBuildItem.element_code == code,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = MetaOntologyBuildItem(
                tenant_id=self.tenant_id, job_id=job.id, element_kind=kind, element_code=code[:200],
                origin=origin,
            )
            self.db.add(existing)
        existing.action = action
        existing.delta_json = delta
        existing.verdict = verdict
        existing.verdict_reason = verdict_reason
        existing.confidence = confidence
        existing.status = status
        existing.element_id = element_id
        self.db.flush()

    def _add_evidence(
        self, ontology_id: int, kind: str, code: str, evidence_kind: str, payload: dict,
        confidence: Optional[float],
    ) -> int:
        ev = MetaOntologyEvidence(
            tenant_id=self.tenant_id, ontology_id=ontology_id, element_kind=kind,
            element_code=code[:200], evidence_kind=evidence_kind, payload_json=payload,
            confidence=confidence,
        )
        self.db.add(ev)
        self.db.flush()
        return ev.id

    # ---------------------------------------------------------- judge（8 类机械校验）

    @staticmethod
    def _judge_object(table: MetaTable, code: str) -> Tuple[str, Optional[str]]:
        """机械校验：空码/超长/无注释/前缀残留/命名不规范/类型/PII/重复。返回 (verdict, reason)。"""
        reasons: List[str] = []
        if code == "obj_unknown":
            return "fail", "empty_or_invalid_code"
        if len(code) > 64:
            reasons.append("code_too_long")
        if not table.table_comment and not table.biz_name:
            reasons.append("no_comment")           # 缺注释 → 置信度降级（§4.1 NO_COMMENT）
        if _LAYER_PREFIX_RE.match((table.table_name or "").strip()):
            reasons.append("layer_prefix_residue")
        if re.search(r"[A-Z]", table.table_name or ""):
            reasons.append("uppercase_in_name")
        if (table.column_count or 0) == 0:
            reasons.append("zero_columns")
        if not reasons:
            return "pass", None
        return "warn", ",".join(reasons)

    # ---------------------------------------------------------- 收尾

    def _is_cancelled(self, job_id: int) -> bool:
        st = self.db.execute(
            select(MetaOntologyBuildJob.status).where(MetaOntologyBuildJob.id == job_id)
        ).scalar_one_or_none()
        return st == "cancelled"

    def _stats_dict(self, s: BuildStats) -> dict:
        return {
            "tables": s.tables, "objects_created": s.objects_created,
            "objects_updated": s.objects_updated, "properties": s.properties,
            "relations": s.relations, "mappings": s.mappings,
            "skipped_human": s.skipped_human, "semantic": s.semantic,
            "semantic_failed": s.semantic_failed, "degraded": s.degraded,
            "degraded_reason": s.degraded_reason,
        }

    def _finish(
        self, job: MetaOntologyBuildJob, status: str, stats: BuildStats, t0: float,
        stats_json: Optional[dict] = None,
    ) -> None:
        job.status = status
        job.phase = "done"
        job.progress = 1.0 if status == "succeeded" else job.progress
        job.stats_json = stats_json or self._stats_dict(stats)
        job.finished_at = func.now()
        job.duration_ms = int((time.monotonic() - t0) * 1000)
        self.db.commit()

    @staticmethod
    def _chunks(items: list, size: int):
        for i in range(0, len(items), size):
            yield items[i:i + size]
