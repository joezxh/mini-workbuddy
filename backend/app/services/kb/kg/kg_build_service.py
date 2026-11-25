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
from app.services.kb.kg import kg_failure

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


# ── 分布式互斥（PG advisory lock，会话级）────────────────────────────────
# 进程内锁在多 uvicorn worker / 多实例部署下互斥失效 → 同库并发构建、
# LLM 重复付费。真正的互斥交给数据库：advisory lock 绑定在**连接**上，
# 持锁连接由后台任务持有到构建结束，会话断开自动释放（进程崩溃不残留）。
# 键用两段 int 形式 (namespace, kb_id)：namespace 固定，避免与库内其他
# advisory lock 用途撞车。
_ADVISORY_NS = 1_802_217_321  # "kgui" 四字节的 ASCII 整数值


def try_acquire_advisory(db: Session, kb_id: int) -> bool:
    """尝试获取知识库级 advisory 锁；失败或非 PG 后端返回 False/True 语义如下：

    * PG 且锁空闲 → True（调用方必须用**同一 session** 调 :func:`release_advisory`）；
    * PG 且被占 → False（调用方返回 409）；
    * 非 PG 后端（单测 SQLite）→ True，降级为仅进程内锁互斥。
    """
    from sqlalchemy import text

    try:
        if (db.get_bind().dialect.name or "") != "postgresql":
            return True
        return bool(
            db.execute(
                text("SELECT pg_try_advisory_lock(:ns, :kb)"),
                {"ns": _ADVISORY_NS, "kb": kb_id},
            ).scalar()
        )
    except Exception as exc:  # noqa: BLE001 - 锁探测失败不阻断构建（降级进程内锁）
        logger.opt(exception=True).warning(
            f"[kg] advisory lock 探测失败，降级为进程内锁 kb={kb_id}: {exc}"
        )
        return True


def release_advisory(db: Session, kb_id: int) -> None:
    """释放 advisory 锁（必须与获取时同一 session/连接；失败仅记日志）。"""
    from sqlalchemy import text

    try:
        if (db.get_bind().dialect.name or "") != "postgresql":
            return
        db.execute(
            text("SELECT pg_advisory_unlock(:ns, :kb)"),
            {"ns": _ADVISORY_NS, "kb": kb_id},
        )
    except Exception:  # noqa: BLE001 - 连接已断时锁随之自动释放
        logger.opt(exception=True).warning(
            f"[kg] advisory lock 释放失败（连接可能已断开，锁将随之自动释放）kb={kb_id}"
        )


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
    #: 关系 LLM 二次复核摘要（None = 未跑：无通道 / 配置关闭）
    review: Optional[dict] = None

    def as_dict(self) -> dict:
        out = {
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
        if self.review is not None:
            out["review"] = self.review
        return out


def _embed(texts: list[str], embed_fn: Optional[Callable]) -> list[list[float]]:
    """批量嵌入；``embed_fn`` 为测试注入点（同步：texts → 向量列表）。

    复用 kb 的 ``build_embedding_model``（**不另起一套 embedder**，R5）：
    实体/三元组向量必须与 chunk 向量同模型同空间，否则检索融合无从谈起。
    """
    if embed_fn is not None:
        return embed_fn(texts)
    import asyncio
    import time

    from app.services.kb.rag.embedding_factory import build_embedding_model

    model = build_embedding_model(None)

    async def _run(batch: list[str]):
        resp = await model(batch)
        return list(resp.embeddings)

    # 分批 + 短重试：GPUStack 等代理型嵌入服务对大请求体/瞬时抖动会回
    # 502/Connection error（供应链库实测），整批一次性发 500 条必炸
    out: list[list[float]] = []
    for i in range(0, len(texts), 64):
        batch = texts[i:i + 64]
        for attempt in range(3):
            try:
                out.extend(asyncio.run(_run(batch)))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
    return out


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
        # 降级原因原文（写进单切片详情，让失败清单直接说出「模型不可用」）
        self._llm_degraded_reason = ""
        # 库内实体别名索引（懒构建缓存，见 _kb_alias_index）
        self._kb_alias_cache: Optional[dict[str, int]] = None
        # 本轮构建可用的 LLM 通道（_run_structure 置位；关系复核复用它）
        self._llm_channel = None

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

    def _kb_alias_index(self) -> dict[str, int]:
        """库内实体的「归一名/别名 → id」索引（懒构建，一次构建运行内缓存）。

        为什么需要别名索引（供应链库实测）：模型常用简称输出关系端点
        （华创/启明/京仓），实体表里存的是全名（华创制造/启明电子/北京仓），
        aliases 才是简称。旧实现只按 name 精确匹配，这类端点全部悬空丢弃。
        一次全量加载（上限 20000 行）建 dict，端点解析 O(1)，避免逐端点查库 N+1。
        """
        if self._kb_alias_cache is None:
            idx: dict[str, int] = {}
            rows = self.db.execute(
                select(KgEntity.id, KgEntity.name, KgEntity.aliases).where(
                    KgEntity.knowledge_id == self.knowledge_id,
                    *([KgEntity.tenant_id == self.tenant_id]
                      if self.tenant_id is not None else []),
                ).limit(20000)
            ).all()
            for eid, name, aliases in rows:
                for key in [name, *(aliases or [])]:
                    k = _norm(str(key or ""))
                    if k and k not in idx:
                        idx[k] = eid
            self._kb_alias_cache = idx
        return self._kb_alias_cache

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
            # 降级原因同时留给单切片留痕用：只写「规则抽取零产出」会把真正可修
            # 的「对话模型不可用」藏到报告里，切片清单上看不出该改哪里。
            self._llm_degraded_reason = msg
            logger.warning(f"[kg] kb={self.knowledge_id} {msg}")
            report.errors.append(msg)
            return None
        logger.info(f"[kg] kb={self.knowledge_id} LLM 抽取通道: {llm.model_desc}")
        return llm

    # ── 失败留痕（阶段 + 错误码 + 技术原文）───────────────────────────────
    def _record_failure(
        self,
        seg: KbSegment,
        *,
        stage: str,
        code: str,
        error: str,
        details: Optional[dict] = None,
    ) -> None:
        """把「哪一阶段、什么原因」写进切片抽取详情（JSONB，不新增列）。

        两套键名按阶段分开：结构失败的切片也会走向量阶段，若共用 ``error``，
        「LLM 输出被截断」会在界面上被显示成「嵌入模型调不通」——两者的修法完全不同。

        * 结构：``stage`` / ``error`` / ``error_code``
        * 向量：``vector_stage`` / ``vector_error`` / ``vector_error_code``

        ``error`` 存技术原文（悬浮与排障用），``error_code`` 存稳定码
        （前端 :mod:`kgFailureReason` 按码取 i18n 文案）。
        """
        merged = dict(seg.graph_extraction_details or {})
        merged.update(details or {})
        if stage == kg_failure.STAGE_VECTOR:
            merged.update({
                "vector_stage": kg_failure.STAGE_VECTOR,
                "vector_error": error,
                "vector_error_code": code,
            })
        else:
            merged.update({
                "stage": kg_failure.STAGE_STRUCTURE,
                "error": error,
                "error_code": code,
            })
        seg.graph_extraction_details = merged

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
                # 堆栈只在报错当场打（事后拿到的 exc 对象虽带 traceback，
                # 但并发线程里再记会失去当时的上下文）。片段正文只记长度，
                # 不写全文，避免文档正文大面积进日志。
                logger.exception(
                    f"[kg] kb={self.knowledge_id} segment={seg.id} 抽取异常"
                    f"（text_len={len(text or '')}, elapsed={_ms(started)}ms）: {exc}"
                )
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
        self._llm_channel = llm

        pending = [s for s in segments if s.graph_structure_indexed is not True]
        for seg, result, exc, elapsed_ms in self._extract_concurrently(
            pending, extract, hint, llm, cfg
        ):
            if exc is not None:
                seg.graph_structure_indexed = False
                self._record_failure(
                    seg,
                    stage=kg_failure.STAGE_STRUCTURE,
                    code=kg_failure.classify(exc, stage=kg_failure.STAGE_STRUCTURE),
                    error=kg_failure.format_error(exc),
                    details={"elapsed_ms": elapsed_ms},
                )
                self.db.commit()
                report.structure_failed += 1
                report.errors.append(f"segment={seg.id} 抽取失败: {exc}")
                logger.error(
                    f"[kg] kb={self.knowledge_id} 结构抽取失败 segment={seg.id}"
                    f"（耗时 {elapsed_ms}ms）: {type(exc).__name__}: {exc}"
                )
                continue
            if (result.errors or self._llm_degraded) and not (
                result.entities or result.relations
            ):
                # 抽取器报错、或 LLM 通道被降级后零产出（规则通道对中文几乎无召回）
                # → 该切片归为**失败**（标志置 False）。
                # 否则切片会停在「已抽取但空」的真状态里永不重试——前端看起来
                # 像成功，这正是本轮最难发现的那类静默降级；配好模型后能续跑。
                seg.graph_structure_indexed = False
                base = result.as_details(elapsed_ms)
                reason = (
                    result.errors[0] if result.errors
                    else (self._llm_degraded_reason
                          or "规则抽取零产出（LLM 通道已降级）")
                )
                # 码优先用抽取器当场定的（``ExtractionResult.codes``），
                # 降级零产出这条没有异常可分类，故按消息判定。
                self._record_failure(
                    seg,
                    stage=kg_failure.STAGE_STRUCTURE,
                    code=base.get("error_code") or kg_failure.classify_message(
                        reason, stage=kg_failure.STAGE_STRUCTURE
                    ),
                    error=reason,
                    details=base,
                )
                self.db.commit()
                report.structure_failed += 1
                report.errors.append(f"segment={seg.id} 抽取失败: {reason}")
                logger.error(
                    f"[kg] kb={self.knowledge_id} 结构抽取失败（零产出）"
                    f" segment={seg.id}（耗时 {elapsed_ms}ms）: {reason}"
                )
                continue

            entity_ids: dict[str, int] = {}
            seg_alias_ids: dict[str, int] = {}
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
                    logger.exception(
                        f"[kg] kb={self.knowledge_id} 实体落库失败"
                        f" segment={seg.id} name={ent.get('name')!r}: {exc}"
                    )
                    report.errors.append(f"实体落库失败 {ent.get('name')}: {exc}")
                    continue
                entity_ids[ent["normalized"]] = row.id
                # 片段级别名表：本片段实体自己的 name/aliases 也可作端点表述
                # （模型给端点用简称、给实体名用全名是供应链语料的常态）
                for alias in [ent.get("name"), *(ent.get("aliases") or [])]:
                    ak = _norm(str(alias or ""))
                    if ak and ak not in seg_alias_ids:
                        seg_alias_ids[ak] = row.id
                self._add_mention(KgEntityMention, "kg_entity_id", row.id, seg)

            # 端点解析：本片段实体（name）→ 本片段别名 → 库内既有实体（name）
            # → 库内别名索引 → 丢弃。
            # 抽取器不再做悬空边判定（实体清单可能被输出预算裁剪，而实体本身
            # 或已在库内——前一片段/其他文档创建过），跨片段关系在这里补回；
            # 别名匹配救回「端点用简称」的关系（旧实现这类关系全部悬空丢弃）。
            # 命中库内实体时给本片段补写提及与 Chunk→Entity 投影，PPR 才能从
            # 当前片段检索到这条边。四处都解析不到才丢弃（悬空边仍不入库）。
            unresolved = 0

            def _resolve_endpoint(raw_name: str) -> Optional[int]:
                nonlocal unresolved
                key = _norm(raw_name)
                if key in entity_ids:
                    return entity_ids[key]
                if key in seg_alias_ids:
                    eid = seg_alias_ids[key]
                    entity_ids[key] = eid
                    self._add_mention(KgEntityMention, "kg_entity_id", eid, seg)
                    return eid
                candidates = {(raw_name or "").strip(), key} - {""}
                row = self.db.execute(
                    select(KgEntity).where(
                        KgEntity.knowledge_id == self.knowledge_id,
                        KgEntity.name.in_(candidates),
                        *([KgEntity.tenant_id == self.tenant_id]
                          if self.tenant_id is not None else []),
                    ).order_by(KgEntity.id)
                ).scalars().first()
                if row is not None:
                    entity_ids[key] = row.id
                    self._add_mention(KgEntityMention, "kg_entity_id", row.id, seg)
                    return row.id
                eid = self._kb_alias_index().get(key)
                if eid is not None:
                    entity_ids[key] = eid
                    self._add_mention(KgEntityMention, "kg_entity_id", eid, seg)
                    return eid
                unresolved += 1
                return None

            for rel in result.relations:
                src = _resolve_endpoint(rel["source"])
                tgt = _resolve_endpoint(rel["target"])
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
                    logger.exception(
                        f"[kg] kb={self.knowledge_id} 关系落库失败"
                        f" segment={seg.id} rel={rel}: {exc}"
                    )
                    report.errors.append(f"关系落库失败 {rel}: {exc}")
                    continue
                self._add_mention(
                    KgTripleMention, "kg_triple_id", triple.id, seg,
                    # 提及带上原文依据：评审时可就地核对，不必回到切片重找
                    evidence=({"text": rel["text"]} if rel.get("text") else None),
                )

            if unresolved:
                logger.warning(
                    f"[kg] kb={self.knowledge_id} segment={seg.id} "
                    f"{unresolved} 条关系端点在片段内与库内均解析不到，已丢弃"
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
            if result.truncation:
                # 只告警、不改标志位、不进失败清单：残缺结果已入库且可用，但
                # 「逐段都在裁剪」就是预算不够的信号（该调大 max_output_tokens
                # 或缩短切片）。正文本身不写进日志，只写长度与数值。
                t = result.truncation
                logger.warning(
                    f"[kg] kb={self.knowledge_id} 抽取输出被裁剪后已补齐 segment={seg.id}"
                    f"（保住 entity={t.get('kept_entities')}"
                    f" relation={t.get('kept_relations')}"
                    f" 丢弃字符={t.get('dropped_chars')}"
                    f" output_tokens={t.get('output_tokens')}"
                    f" budget={t.get('budget')}"
                    f" thinking_chars={t.get('thinking_chars')}）"
                )
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
            # 级别保持 debug（噪声大且不影响结果），但补堆栈：Neo4j 投影与 JSONB
            # 类型不兼容在这条分支里会被静吞，只留 str(exc) 时事后看不出色因。
            logger.opt(exception=True).debug(
                f"[kg] 提及写入跳过 {model.__name__}={fk_value}: {exc}"
            )
            self.db.rollback()

    # ── 阶段 3：关系 LLM 二次复核（只标记，不流转评审状态）────────────────
    def _run_relation_review(self, cfg: dict, report: BuildReport) -> None:
        """构建完成后对（默认 suggested 的）关系跑一轮证据复核。

        无 LLM 通道（注入抽取器 / 规则模式 / 模型不可用）时跳过——手动端点
        ``POST /graph/relations/review-batch`` 可随时补跑。复核失败不影响
        构建结果（降级但显式，写日志）。
        """
        if not bool(cfg.get("relation_review_enabled", True)):
            return
        channel = self._llm_channel
        if channel is None:
            return
        try:
            from app.services.kb.kg import kg_relation_reviewer

            summary = kg_relation_reviewer.run_review(
                self.db,
                tenant_id=self.tenant_id,
                knowledge_id=self.knowledge_id,
                complete=channel.complete,
                limit=int(cfg.get("review_batch_size") or 200),
                concurrency=int(cfg.get("review_concurrency") or 4),
                skip_reviewed=True,  # 增量：只复核新关系，不覆盖已有复核结论
            )
            report.review = summary
        except Exception as exc:  # noqa: BLE001 - 复核失败不推翻构建结果
            logger.opt(exception=True).warning(
                f"[kg] kb={self.knowledge_id} 关系复核失败（不影响构建结果）: {exc}"
            )

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
                    # 嵌入是外部调用（可达分钟级）：先结束读事务再调，
                    # 不让 kms_segment/kg_entity 的 ACCESS SHARE 锁跨调用持有
                    self.db.commit()
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
                    self.db.commit()  # 同上：嵌入调用前结束读事务
                    vecs = _embed(texts, self._embed_fn)
                    for t, v in zip(tris, vecs):
                        t.embedding = fit_vector_dimension(v, dim)
                seg.graph_indexed = True
                self.db.commit()
                report.vector_done += 1
            except Exception as exc:  # noqa: BLE001 - 向量失败不回滚结构阶段
                self.db.rollback()
                seg.graph_indexed = False
                # 向量阶段以前从不写 details，前端只能看到一句「向量阶段失败」，
                # 看不出是嵌入模型调不通还是写库时维度对不上。
                self._record_failure(
                    seg,
                    stage=kg_failure.STAGE_VECTOR,
                    code=kg_failure.classify(exc, stage=kg_failure.STAGE_VECTOR),
                    error=kg_failure.format_error(exc),
                )
                self.db.commit()
                report.vector_failed += 1
                report.errors.append(f"segment={seg.id} 向量化失败: {exc}")
                logger.exception(
                    f"[kg] kb={self.knowledge_id} 向量化失败 segment={seg.id}: {exc}"
                )

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
            # 读事务到此结束（2026-11-25 复盘）：结构抽取/向量化/复核是分钟级
            # 外部调用，旧实现把整段夹在 _segments() 开启的读事务里——
            # kms_segment 的 ACCESS SHARE 锁全程不放，足以把启动迁移的
            # ALTER TABLE 堵死在 PG 锁队列（启动卡死根因之一）。
            # expire_on_commit=False：commit 后 segments 等已加载对象保持属性
            # 可用，避免并发线程访问过期属性触发 refresh SELECT（那既会重新
            # 打开事务，也是跨线程使用 Session）。advisory lock 是会话级，
            # 不受 commit 影响。
            self.db.expire_on_commit = False
            self.db.commit()
            try:
                self._run_structure(segments, cfg, report)
                self._run_vectors(segments, report)
                self._run_relation_review(cfg, report)
            finally:
                self.db.expire_on_commit = True

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
            logger.opt(exception=True).warning(
                f"[kg] 构建元信息写入失败 kb={self.knowledge_id}: {exc}"
            )

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

    两层互斥：进程内锁做快速路径（省一次 DB 往返，测试也依赖它注入冲突），
    PG advisory lock 做真正的分布式互斥（多 worker / 多实例部署）。
    advisory 锁的持锁连接由后台任务持有到构建结束——会话断开自动释放，
    进程崩溃不残留，无需人工清锁。
    """
    if not try_acquire(knowledge_id):
        return {"accepted": False, "reason": "该知识库已有图谱任务在执行"}

    from app.db.database import SessionLocal

    # advisory 锁必须在**提交线程**先行获取：拿不到直接 409 回给前端，
    # 而不是让任务启动后再静默退出（用户会看到「已提交」却毫无进展）。
    lock_db = SessionLocal()
    if not try_acquire_advisory(lock_db, knowledge_id):
        lock_db.close()
        release(knowledge_id)
        return {"accepted": False, "reason": "该知识库已有图谱任务在执行（其他实例）"}

    def _task() -> None:
        db = SessionLocal()
        try:
            KgBuildService(db, tenant_id, knowledge_id).run(
                action, document_uuid
            )
        except Exception as exc:  # noqa: BLE001 - 后台任务失败只记日志
            logger.exception(f"[kg] 图谱构建失败 kb={knowledge_id}: {exc}")
        finally:
            release_advisory(lock_db, knowledge_id)
            lock_db.close()
            release(knowledge_id)
            db.close()

    from app.core.job_runner import run_in_background

    run_in_background(_task, name=f"kg-build-{knowledge_id}-{action}")
    return {"accepted": True, "action": action, "knowledge_id": knowledge_id}
