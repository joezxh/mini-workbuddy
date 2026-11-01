"""图谱构建编排（P3）—— 两阶段、可断点续跑、单库互斥。

Spec: §5.2 两阶段 / §5.4 幂等与增量 / §5.5 后台作业与互斥 / §5.6 失败可观测

为什么分两阶段
--------------
LLM 抽取最贵，Neo4j 投影与向量写入都可能失败。把状态机拆成
``graph_structure_indexed``（阶段 1）与 ``graph_indexed``（阶段 2）后，
任一阶段失败都能**跳过已完成阶段**重跑，杜绝重复付费抽取
（Yuxi ``service.py:447-457`` 同款；这两个标志是**对外契约**）。

幂等保证
--------
* 实体按 ``entity_key``、关系按 (起点, 类型, 终点) upsert（``KgService`` 已保证）
* 提及按 ``(entity|triple, segment)`` 唯一约束 upsert
* Neo4j 侧全部 ``MERGE``（ID 由内容确定性计算）
→ **重复执行同一文档不产生任何重复行**。

失败可观测
----------
单切片抽取失败：写 ``graph_extraction_details`` 与文档 ``error_detail``
（形如 ``[graph_extract] …``），**但文档保持 completed**——切片已可用，
图谱只是未就绪。降级必须**显式**，不得静默伪装成功。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_entity_mention import KgEntityMention
from app.models.kb.kg_triple import KgTriple
from app.models.kb.kg_triple_mention import KgTripleMention
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment

GRAPH_STEP = "graph_extract"

# ── 单库互斥（进程内；同一知识库同时只允许一个图谱任务）──────────────────
_LOCK_GUARD = threading.Lock()
_KB_LOCKS: dict[int, bool] = {}


def try_acquire(kb_id: int) -> bool:
    """尝试获取知识库构建锁；已被占用返回 False（调用方返回 409）。"""
    with _LOCK_GUARD:
        if _KB_LOCKS.get(kb_id):
            return False
        _KB_LOCKS[kb_id] = True
        return True


def release(kb_id: int) -> None:
    with _LOCK_GUARD:
        _KB_LOCKS.pop(kb_id, None)


def is_locked(kb_id: int) -> bool:
    with _LOCK_GUARD:
        return bool(_KB_LOCKS.get(kb_id))


def reset_locks() -> None:
    """仅测试用：清空全部锁。"""
    with _LOCK_GUARD:
        _KB_LOCKS.clear()


@dataclass
class BuildReport:
    action: str = "build"
    segments_scanned: int = 0
    structure_done: int = 0
    structure_failed: int = 0
    vector_done: int = 0
    vector_failed: int = 0
    entities: int = 0
    relations: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "segments_scanned": self.segments_scanned,
            "structure_done": self.structure_done,
            "structure_failed": self.structure_failed,
            "vector_done": self.vector_done,
            "vector_failed": self.vector_failed,
            "entities": self.entities,
            "relations": self.relations,
            "errors": self.errors[:10],
        }


def _embed(texts: list[str], embed_fn: Optional[Callable]) -> list[list[float]]:
    """批量嵌入；``embed_fn`` 为测试注入点（同步：texts → 向量列表）。

    复用 kb 的 ``build_embedding_model``（**不另起一套 embedder**，R5）：
    实体/三元组向量必须与 chunk 向量同模型同空间，否则检索融合无从谈起。
    """
    if embed_fn is not None:
        return embed_fn(texts)
    import asyncio

    from app.services.kb.rag.embedding_factory import build_embedding_model

    model = build_embedding_model(None)

    async def _run(batch: list[str]):
        resp = await model(batch)
        return list(resp.embeddings)

    return asyncio.run(_run(texts))


class KgBuildService:
    """图谱构建编排。

    :param embed_fn: 测试注入的嵌入函数；生产为 ``None``（走 kb 的 embedding 工厂）
    :param extractor: 测试注入的抽取器（签名同 :func:`kg_extractor.extract`）
    """

    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int],
        knowledge_id: int,
        *,
        embed_fn: Optional[Callable] = None,
        extractor: Optional[Callable] = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.knowledge_id = knowledge_id
        self._embed_fn = embed_fn
        self._extractor = extractor
        # LLM 通道是否被降级到规则抽取（由 _build_llm 置位，供阶段 1 判定用）
        self._llm_degraded = False

    # ── 服务与配置 ──────────────────────────────────────────────────────
    def _svc(self):
        from app.services.kb.kg.kg_service import KgService

        return KgService(self.db, tenant_id=self.tenant_id,
                         knowledge_id=self.knowledge_id)

    def _config(self) -> dict:
        from app.services.kb.kg.kg_config import get_graph_config

        return get_graph_config(self.db, self.knowledge_id)

    def _schema_hint(self, cfg: dict) -> str:
        from app.services.kb.kg.kg_extractor import build_schema_hint

        return build_schema_hint(
            self.db,
            schema_source=cfg.get("schema_source", "free_text"),
            catalog_id=cfg.get("catalog_id"),
            free_text=cfg.get("schema", "") or "",
            tenant_id=self.tenant_id,
        )

    def _segment_query(self, document_uuid: Optional[str] = None):
        """切片查询条件（构建扫描与前置校验共用，避免两处口径漂移）。"""
        stmt = select(KbSegment).where(
            KbSegment.collection == f"kb_{self.knowledge_id}"
        )
        if self.tenant_id is not None:
            stmt = stmt.where(KbSegment.tenant_id == self.tenant_id)
        if document_uuid:
            stmt = stmt.where(KbSegment.document_id == document_uuid)
        return stmt

    def _segments(self, document_uuid: Optional[str] = None, limit: int = 10000):
        stmt = self._segment_query(document_uuid).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_segments(self, document_uuid: Optional[str] = None) -> int:
        """切片数量（不加载行）：路由据此在提交前判断「有没有可抽内容」。"""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(
            self._segment_query(document_uuid).order_by(None).subquery()
        )
        return int(self.db.execute(stmt).scalar() or 0)

    # ── 阶段 1：结构写入 ─────────────────────────────────────────────────
    def _build_llm(self, cfg: dict, report: BuildReport):
        """按图谱配置构造 LLM 抽取通道；不可用返回 ``None`` 并**显式**记下降级原因。

        静默退回规则通道会让前端看到「构建成功、 0 实体」（本轮就这么错过去一次），
        所以降级原因一定写进报告。已注入 ``extractor``（测试）时不构造：
        走哪条通道由注入方负责。``extractor_type=rule`` 是用户**显式选择**的通道，
        不属于降级，不记告警。
        """
        from app.services.kb.kg import kg_llm_extractor

        if (cfg.get("extractor_type") or "llm") == "rule":
            return None

        llm, note = kg_llm_extractor.build_llm_extractor(self.db, cfg)
        if llm is None:
            self._llm_degraded = True
            msg = f"LLM 抽取通道不可用，本次降级为规则抽取: {note}"
            logger.warning(f"[kg] kb={self.knowledge_id} {msg}")
            report.errors.append(msg)
            return None
        logger.info(f"[kg] kb={self.knowledge_id} LLM 抽取通道: {llm.model_desc}")
        return llm

    def _extract_concurrently(self, segments, extract, hint, llm, cfg: dict) -> list:
        """只并发**抽取**（纯外部调用），返回 ``[(seg, result|None, exc|None, ms)]``。

        落库仍在主线程串行：SQLAlchemy Session 不是线程安全的，并发写会直接把
        构建带崩。抽取是最贵的一段（逐切片等 LLM），所以并发只包这一层，
        ``concurrency_count`` 在此真正生效。``pool.map`` 保证结果与输入同序。
        """
        jobs = [(seg, seg.content or "") for seg in segments]
        if not jobs:
            return []

        def _one(job):
            seg, text = job
            started = time.time()
            kwargs: dict = {"schema_hint": hint, "tenant_id": self.tenant_id}
            if llm is not None:
                kwargs["llm"] = llm
            try:
                return seg, extract(text, **kwargs), None, _ms(started)
            except Exception as exc:  # noqa: BLE001 - 单切片失败不中断整批
                return seg, None, exc, _ms(started)

        workers = max(1, int(cfg.get("concurrency_count") or 1))
        if workers == 1 or len(jobs) == 1:
            return [_one(j) for j in jobs]
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(
            max_workers=min(workers, len(jobs)), thread_name_prefix="kg-extract"
        ) as pool:
            return list(pool.map(_one, jobs))

    def _run_structure(self, segments, cfg: dict, report: BuildReport) -> None:
        from app.services.kb.kg import kg_extractor, kg_graph_store

        svc = self._svc()
        hint = self._schema_hint(cfg)
        extract = self._extractor or kg_extractor.extract
        llm = None if self._extractor is not None else self._build_llm(cfg, report)

        pending = [s for s in segments if s.graph_structure_indexed is not True]
        for seg, result, exc, elapsed_ms in self._extract_concurrently(
            pending, extract, hint, llm, cfg
        ):
            if exc is not None:
                seg.graph_structure_indexed = False
                seg.graph_extraction_details = {
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_ms": elapsed_ms,
                }
                self.db.commit()
                report.structure_failed += 1
                report.errors.append(f"segment={seg.id} 抽取失败: {exc}")
                continue
            if (result.errors or self._llm_degraded) and not (
                result.entities or result.relations
            ):
                # 抽取器报错、或 LLM 通道被降级后零产出（规则通道对中文几乎无召回）
                # → 该切片归为**失败**（标志置 False）。
                # 否则切片会停在「已抽取但空」的真状态里永不重试——前端看起来
                # 像成功，这正是本轮最难发现的那类静默降级；配好模型后能续跑。
                seg.graph_structure_indexed = False
                seg.graph_extraction_details = result.as_details(elapsed_ms)
                self.db.commit()
                report.structure_failed += 1
                reason = (
                    result.errors[0] if result.errors
                    else "规则抽取零产出（LLM 通道已降级）"
                )
                report.errors.append(f"segment={seg.id} 抽取失败: {reason}")
                continue

            entity_ids: dict[str, int] = {}
            for ent in result.entities:
                try:
                    row = svc.create_entity(
                        name=ent["name"],
                        entity_key=ent["normalized"],
                        type_code=ent.get("label") or None,
                        aliases=ent.get("aliases") or [],
                        properties=ent.get("properties") or {},
                        source_segment_ids=[seg.id],
                        source_document_ids=[seg.document_id] if seg.document_id else [],
                    )
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"实体落库失败 {ent.get('name')}: {exc}")
                    continue
                entity_ids[ent["normalized"]] = row.id
                self._add_mention(KgEntityMention, "kg_entity_id", row.id, seg)

            for rel in result.relations:
                src = entity_ids.get(_norm(rel["source"]))
                tgt = entity_ids.get(_norm(rel["target"]))
                if src is None or tgt is None:
                    continue
                try:
                    triple = svc.create_triple(
                        from_entity_id=src,
                        to_entity_id=tgt,
                        relation_code=rel["relation_type"],
                        predicate=rel.get("text") or None,
                        evidence={"text": rel.get("text", "")} if rel.get("text") else None,
                        source_segment_ids=[seg.id],
                        source_document_ids=[seg.document_id] if seg.document_id else [],
                    )
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"关系落库失败 {rel}: {exc}")
                    continue
                self._add_mention(
                    KgTripleMention, "kg_triple_id", triple.id, seg,
                    # 提及带上原文依据：评审时可就地核对，不必回到切片重找
                    evidence=({"text": rel["text"]} if rel.get("text") else None),
                )

            # Chunk → Entity 的图投影（检索 PPR 需要 Chunk 节点）
            for eid in entity_ids.values():
                ent_row = self.db.get(KgEntity, eid)
                if ent_row is not None:
                    kg_graph_store.project_mention(
                        kb_id=self.knowledge_id,
                        document_id=seg.document_id or "",
                        chunk_index=seg.chunk_index,
                        entity=ent_row,
                        content_preview=(seg.content or "")[:500],
                    )

            seg.graph_structure_indexed = True
            seg.graph_extraction_details = result.as_details(elapsed_ms)
            self.db.commit()
            report.structure_done += 1
            report.entities += len(result.entities)
            report.relations += len(result.relations)

    def _add_mention(
        self, model, fk_name: str, fk_value: int, seg: KbSegment,
        *, evidence: Optional[dict] = None,
    ) -> None:
        """写入提及（幂等：已存在即跳过）。"""
        try:
            exists = self.db.execute(
                select(model.id).where(
                    getattr(model, fk_name) == fk_value,
                    model.segment_id == seg.id,
                )
            ).scalar_one_or_none()
            if exists:
                return
            row = model(
                tenant_id=self.tenant_id,
                **{fk_name: fk_value},
                segment_id=seg.id,
                document_id=seg.document_id,
                evidence=evidence,
            )
            self.db.add(row)
            self.db.flush()
        except Exception as exc:  # noqa: BLE001 - 提及失败不影响事实本身
            logger.debug(f"[kg] 提及写入跳过 {model.__name__}={fk_value}: {exc}")
            self.db.rollback()

    # ── 阶段 2：向量索引 ─────────────────────────────────────────────────
    def _run_vectors(self, segments, report: BuildReport) -> None:
        from app.services.kb.vector_utils import fit_vector_dimension

        dim = settings.EMBEDDING_DIMENSION
        for seg in segments:
            if seg.graph_indexed is True:
                continue
            try:
                ents = list(
                    self.db.execute(
                        select(KgEntity).where(
                            KgEntity.knowledge_id == self.knowledge_id,
                            KgEntity.embedding.is_(None),
                        ).limit(500)
                    ).scalars().all()
                )
                tris = list(
                    self.db.execute(
                        select(KgTriple).where(
                            KgTriple.knowledge_id == self.knowledge_id,
                            KgTriple.embedding.is_(None),
                        ).limit(500)
                    ).scalars().all()
                )
                if ents:
                    texts = [
                        "｜".join(
                            [e.name, e.type_code or "", "、".join(e.aliases or [])]
                        ).strip("｜")
                        for e in ents
                    ]
                    vecs = _embed(texts, self._embed_fn)
                    for e, v in zip(ents, vecs):
                        e.embedding = fit_vector_dimension(v, dim)
                if tris:
                    names = {
                        e.id: e.name for e in self.db.execute(
                            select(KgEntity).where(
                                KgEntity.knowledge_id == self.knowledge_id
                            ).limit(2000)
                        ).scalars().all()
                    }
                    texts = [
                        "{} → {} → {}".format(
                            names.get(t.from_entity_id, ""),
                            t.relation_code or "",
                            names.get(t.to_entity_id, ""),
                        )
                        for t in tris
                    ]
                    vecs = _embed(texts, self._embed_fn)
                    for t, v in zip(tris, vecs):
                        t.embedding = fit_vector_dimension(v, dim)
                seg.graph_indexed = True
                self.db.commit()
                report.vector_done += 1
            except Exception as exc:  # noqa: BLE001 - 向量失败不回滚结构阶段
                self.db.rollback()
                seg.graph_indexed = False
                self.db.commit()
                report.vector_failed += 1
                report.errors.append(f"segment={seg.id} 向量化失败: {exc}")

    # ── 动作分发 ────────────────────────────────────────────────────────
    def run(
        self,
        action: str = "build",
        document_uuid: Optional[str] = None,
        *,
        limit: int = 10000,
    ) -> BuildReport:
        """同步执行一次构建动作（后台任务与测试都走这里）。"""
        report = BuildReport(action=action)
        started = time.time()
        cfg = self._config()

        try:
            if action == "clear_document":
                self.clear_document(document_uuid)
                return report
            if action == "rebuild":
                if document_uuid:
                    # 单文档重抽 = 撤销本文档贡献（引用计数归零才删实体/边）后重抽。
                    # 不得走全库 ``rebuild()``：那会把整库实例层清空并把**所有**
                    # 切片的 graph_* 标志置 None，表现在前端就是「点一个文档，其余
                    # 全部变成未抽取」。
                    self.clear_document(document_uuid)
                else:
                    self.rebuild()
            elif action == "reconcile":
                from app.services.kb.kg import kg_graph_store

                kg_graph_store.reconcile(self.db, self.knowledge_id, self.tenant_id)
                return report

            segments = self._segments(document_uuid=document_uuid, limit=limit)
            report.segments_scanned = len(segments)
            self._run_structure(segments, cfg, report)
            self._run_vectors(segments, report)

            # 失败可观测：写文档的 error_detail（形如 [graph_extract] …），
            # 但**不改文档状态**（切片已可用，仅图谱未就绪）
            if report.structure_failed or report.vector_failed:
                self._mark_document_error(document_uuid, report)
            return report
        finally:
            # 概览卡的「最近构建 / 耗时 / 失败步骤」来源于此（不新增列）
            self._save_build_meta(report, started)

    def _save_build_meta(self, report: BuildReport, started: float) -> None:
        """记录最近一次构建的时间与耗时；失败不影响主流程。"""
        from datetime import datetime

        from app.services.kb.kg.kg_config import save_build_meta

        try:
            save_build_meta(
                self.db,
                self.knowledge_id,
                {
                    "action": report.action,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "duration_seconds": round(time.time() - started, 1),
                    "structure_failed": report.structure_failed,
                    "vector_failed": report.vector_failed,
                    "entities": report.entities,
                    "relations": report.relations,
                },
            )
        except Exception as exc:  # noqa: BLE001 - 元信息落库失败不应对构建报错
            logger.warning(f"[kg] 构建元信息写入失败 kb={self.knowledge_id}: {exc}")

    def _mark_document_error(self, document_uuid: Optional[str], report: BuildReport):
        if not document_uuid:
            return
        doc = self.db.execute(
            select(KbDocument).where(KbDocument.uuid_code == document_uuid)
        ).scalar_one_or_none()
        if doc is None:
            return
        detail = (
            f"[{GRAPH_STEP}] 结构失败 {report.structure_failed} 段，"
            f"向量失败 {report.vector_failed} 段"
        )
        doc.error_detail = detail
        doc.meta = {
            **(doc.meta or {}),
            "graph_extract": report.as_dict(),
        }
        self.db.commit()

    # ── 撤销 ────────────────────────────────────────────────────────────
    def clear_document(self, document_uuid: Optional[str]) -> dict:
        """撤销某文档对图谱的全部贡献（提及 → 失去全部提及的实体/边）。

        实体被多个文档共享时**不删**（引用计数归零才删），避免误删。
        """
        from app.services.kb.kg import kg_graph_store

        if not document_uuid:
            return {"cleared": 0}
        segs = self._segments(document_uuid=document_uuid)
        seg_ids = [s.id for s in segs]

        ent_mentions = list(
            self.db.execute(
                select(KgEntityMention).where(
                    KgEntityMention.segment_id.in_(seg_ids) if seg_ids else False
                )
            ).scalars().all()
        ) if seg_ids else []
        tri_mentions = list(
            self.db.execute(
                select(KgTripleMention).where(
                    KgTripleMention.segment_id.in_(seg_ids) if seg_ids else False
                )
            ).scalars().all()
        ) if seg_ids else []

        affected_entities = {m.kg_entity_id for m in ent_mentions}
        affected_triples = {m.kg_triple_id for m in tri_mentions}

        for m in ent_mentions + tri_mentions:
            self.db.delete(m)
        for s in segs:
            s.graph_structure_indexed = None
            s.graph_indexed = None
            s.graph_extraction_details = None
        self.db.flush()

        # 引用计数归零的实体/边才删除
        deleted_entities = 0
        for eid in affected_entities:
            still = self.db.execute(
                select(KgEntityMention.id).where(KgEntityMention.kg_entity_id == eid)
            ).first()
            if still is None:
                row = self.db.get(KgEntity, eid)
                if row is not None:
                    kg_graph_store.unproject_entities(self.knowledge_id, [row])
                    self.db.delete(row)
                    deleted_entities += 1
        deleted_triples = 0
        for tid in affected_triples:
            still = self.db.execute(
                select(KgTripleMention.id).where(KgTripleMention.kg_triple_id == tid)
            ).first()
            if still is None:
                row = self.db.get(KgTriple, tid)
                if row is not None:
                    kg_graph_store.unproject_relations(self.db, [row])
                    self.db.delete(row)
                    deleted_triples += 1

        kg_graph_store.unproject_chunks(
            self.knowledge_id, document_uuid, [s.chunk_index for s in segs]
        )
        self.db.commit()
        return {
            "cleared": len(ent_mentions) + len(tri_mentions),
            "deleted_entities": deleted_entities,
            "deleted_triples": deleted_triples,
        }

    def rebuild(self) -> dict:
        """全量重建：清空该库实例层 + Neo4j 投影，随后重新抽取。"""
        from app.services.kb.kg import kg_graph_store

        kg_graph_store.unproject_kb(self.knowledge_id)
        self.db.execute(
            KgEntity.__table__.delete().where(
                KgEntity.knowledge_id == self.knowledge_id
            )
        )
        self.db.execute(
            KgTriple.__table__.delete().where(
                KgTriple.knowledge_id == self.knowledge_id
            )
        )
        for s in self._segments():
            s.graph_structure_indexed = None
            s.graph_indexed = None
            s.graph_extraction_details = None
        self.db.commit()
        return {"rebuilt": True}


def _norm(name: str) -> str:
    from app.services.kb.kg.kg_extractor import normalize_entity_name

    return normalize_entity_name(name)


def _ms(started: float) -> int:
    """自 ``started`` 起的毫秒耗时（抽取详情与报告共用同一计时口径）。"""
    return int((time.time() - started) * 1000)


# ── 后台提交（job_runner + 单库互斥）────────────────────────────────────
def submit_build(
    *,
    tenant_id: Optional[int],
    knowledge_id: int,
    action: str = "build",
    document_uuid: Optional[str] = None,
) -> dict:
    """提交后台构建任务。

    任务函数**自建并关闭 Session**（``job_runner`` 硬约束）。
    同一知识库已有任务在执行则返回 ``accepted=False``（调用方给 409）。
    """
    if not try_acquire(knowledge_id):
        return {"accepted": False, "reason": "该知识库已有图谱任务在执行"}

    def _task() -> None:
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            KgBuildService(db, tenant_id, knowledge_id).run(
                action, document_uuid
            )
        except Exception as exc:  # noqa: BLE001 - 后台任务失败只记日志
            logger.warning(f"[kg] 图谱构建失败 kb={knowledge_id}: {exc}")
        finally:
            release(knowledge_id)
            db.close()

    from app.core.job_runner import run_in_background

    run_in_background(_task, name=f"kg-build-{knowledge_id}-{action}")
    return {"accepted": True, "action": action, "knowledge_id": knowledge_id}
