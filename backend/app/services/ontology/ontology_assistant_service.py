"""嵌入式建模助手（P0-12：E37 四档 intent + E38 链路拓扑，spec §5.6 / §5.7 / §6.6 / §6.1）。

**四档**（§5.6，写入副作用重新切分）：
- ``ask``：零写入，转 §6.4 ``browse``/``resolve``/``manifest``；
- ``explain``：只写 ``onto_ontology_semantic(field=review_hint, status=suggested)``；
- ``propose_scope``：只写 ``onto_ontology.draft_scope_json``，**不建任务**；表名逐个对真实
  ``meta_table`` 校验，臆造丢弃计 ``hallucination_dropped``；
- ``build``（rev.2 新增，D3 改动唯一原因）：**两步提交**——``commit=false`` 零写入返回预览 +
  指纹；``commit=true`` 且回传指纹与服务端重算一致，才落 ``build_item(origin='llm', status='suggested')``
  （防线①写死 suggested；跳步/指纹不符 → ``ASSISTANT_BUILD_PREVIEW_STALE``）。

硬约束：助手**绝不建 build_job / 不调 review / 不调 publish**。build 候选挂到该本体一个
**固定虚拟 job**（``idempotency_key='assistant-virtual-{ontology_id}'``）以复用
``uq(job_id, element_kind, element_code)`` 去重约束，且不产生新构建任务。
LLM 不可用一律降级（degraded / 回退 browse），**不阻断主链路**。
"""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ASSISTANT_BUILD_EMPTY, ASSISTANT_BUILD_PREVIEW_STALE,
    ASSISTANT_INTENT_UNSUPPORTED, ONTOLOGY_NOT_FOUND,
)
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.ontology.ontology import (
    MetaOntology, MetaOntologyBuildItem, MetaOntologyBuildJob, MetaOntologyPublish, MetaOntologySemantic,
)
from app.services.ontology.ontology_agent_service import OntologyAgentService
from app.services.ontology.ontology_asset_service import OntologyAssetService
from app.services.ontology.ontology_publish_service import OntologyPublishService

_INTENTS = {"ask", "explain", "propose_scope", "build"}
_PROMPT_VERSION = "onto-assistant-1"


class OntologyAssistantService:
    """建模助手四档 + 链路拓扑（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyAssistantService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    # ------------------------------------------------------------- E37 统一入口

    def handle(self, ontology_id: int, *, intent: str, utterance: str = "",
               context: Optional[dict] = None, commit: bool = False,
               user_id: Optional[int] = None) -> dict:
        # 白名单硬校：未知 intent 直接报错，不给默认分支（§5.6 约束 1）
        if intent not in _INTENTS:
            raise ApiError(ASSISTANT_INTENT_UNSUPPORTED, f"不支持的 intent: {intent}",
                           http_status=400, detail={"intent": intent, "supported": sorted(_INTENTS)})
        self._ontology_or_404(ontology_id)
        ctx = context or {}
        if intent == "ask":
            return self._ask(ontology_id, utterance)
        if intent == "explain":
            return self._explain(ontology_id, utterance, ctx)
        if intent == "propose_scope":
            return self._propose_scope(ontology_id, utterance, ctx)
        return self._build(ontology_id, utterance, ctx, commit=commit)

    # ------------------------------------------------------------- ask（零写入）

    def _ask(self, ontology_id: int, utterance: str) -> dict:
        agent = OntologyAgentService(self.db, self.tenant_id)
        kw = (utterance or "").strip()
        if not kw:
            return {"intent": "ask", "mode": "manifest", "manifest": agent.manifest(ontology_id)}
        browsed = agent.browse(ontology_id, kw)
        return {"intent": "ask", "mode": "browse", "used": ["browse"],
                "degraded": bool(browsed.get("rejected")), "result": browsed}

    # ------------------------------------------------------------- explain（仅语义表）

    def _explain(self, ontology_id: int, utterance: str, ctx: dict) -> dict:
        kind = ctx.get("element_kind") or "object"
        code = ctx.get("element_code") or ""
        if not code:
            return {"intent": "explain", "degraded": True, "review_hint": None,
                    "reason": "missing_element_code"}
        evidence = OntologyPublishService(self.db, self.tenant_id).build_snapshot(ontology_id)
        raw = self._llm_or_none(self._explain_prompt(kind, code, utterance, evidence), ctx.get("model_id"))
        if raw is None:  # 降级：不写建议，返回原始证据链
            return {"intent": "explain", "degraded": True, "review_hint": None,
                    "element_kind": kind, "element_code": code,
                    "fallback": "raw_evidence"}
        hint = (raw.get("review_hint") or "").strip() if isinstance(raw, dict) else ""
        conf = self._clamp(raw.get("confidence")) if isinstance(raw, dict) else None
        if hint:
            self._upsert_review_hint(ontology_id, kind, code, hint, conf, ctx.get("model_id"))
        return {"intent": "explain", "degraded": False, "element_kind": kind,
                "element_code": code, "review_hint": hint or "暂无 AI 提示",
                "confidence": conf}

    def _explain_prompt(self, kind: str, code: str, utterance: str, evidence: dict) -> str:
        return (
            "你是本体审阅助手。针对给定元素生成一句中文审阅提示（风险/存疑点），不确定就留空。\n"
            "只输出 JSON：{\"review_hint\": str, \"confidence\": number(0~1)}，无 markdown。\n"
            f"元素: kind={kind} code={code}\n用户问题={utterance}\n"
            f"证据上下文={json.dumps({'objects': evidence['objects'][:8], 'relations': evidence['relations'][:8]}, ensure_ascii=False)[:3000]}"
        )

    def _upsert_review_hint(self, ontology_id: int, kind: str, code: str, hint: str,
                            conf, model_id) -> None:
        model = f"model#{model_id}" if model_id else "default"
        existing = self.db.execute(
            select(MetaOntologySemantic).where(
                MetaOntologySemantic.tenant_id == self.tenant_id,
                MetaOntologySemantic.ontology_id == ontology_id,
                MetaOntologySemantic.element_kind == kind,
                MetaOntologySemantic.element_code == code,
                MetaOntologySemantic.field == "review_hint",
                MetaOntologySemantic.model == model,
            )
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(MetaOntologySemantic(
                tenant_id=self.tenant_id, ontology_id=ontology_id, element_kind=kind,
                element_code=code, field="review_hint", value=hint, confidence=conf,
                model=model, prompt_version=_PROMPT_VERSION, status="suggested",
            ))
        else:
            existing.value = hint
            existing.confidence = conf
            existing.status = "suggested"
        self.db.flush()

    # ------------------------------------------------------ propose_scope（仅写草稿）

    def _propose_scope(self, ontology_id: int, utterance: str, ctx: dict) -> dict:
        raw = self._llm_or_none(self._scope_prompt(utterance, ctx), ctx.get("model_id"))
        if raw is None:
            return {"intent": "propose_scope", "degraded": True, "tables": [],
                    "hallucination_dropped": 0, "written": False}
        proposed = (raw.get("tables") if isinstance(raw, dict) else None) or []
        valid, dropped = self._validate_tables(proposed)
        if not valid:
            return {"intent": "propose_scope", "degraded": False, "tables": [],
                    "hallucination_dropped": dropped, "written": False}
        source_id = valid[0]["source_id"]
        scope = {"mode": "tables", "source_id": source_id,
                 "tables": [v["table"] for v in valid], "origin": "assistant"}
        OntologyAssetService(self.db, self.tenant_id).put_draft_scope(ontology_id, scope)
        return {"intent": "propose_scope", "degraded": False, "tables": valid,
                "hallucination_dropped": dropped, "written": True, "source_id": source_id}

    def _scope_prompt(self, utterance: str, ctx: dict) -> str:
        return (
            "你是本体建模助手。把用户意图转成应纳入建模的数据表候选。\n"
            "只输出 JSON：{\"tables\": [{\"table\": str, \"reason\": str, \"matched_on\": \"name|comment|tag\"}]}，无 markdown。\n"
            "只能来自真实存在的表，禁止臆造。用户意图=" + (utterance or "") + "\n"
            f"上下文={json.dumps(ctx.get('scope') or {}, ensure_ascii=False)[:1500]}"
        )

    def _validate_tables(self, proposed: List[dict]) -> Tuple[List[dict], int]:
        names = [p.get("table") for p in proposed if isinstance(p, dict) and p.get("table")]
        if not names:
            return [], len(proposed)
        rows = self.db.execute(
            select(MetaTable.table_name, MetaTable.source_id).where(
                MetaTable.tenant_id == self.tenant_id, MetaTable.table_name.in_(names)
            )
        ).all()
        real = {tn: sid for tn, sid in rows}
        out = []
        for p in proposed:
            tn = p.get("table")
            if tn in real:
                out.append({"table": tn, "source_id": real[tn],
                            "reason": p.get("reason") or "", "matched_on": p.get("matched_on") or "name"})
        return out, len(proposed) - len(out)

    # ------------------------------------------------------------- build（两步）

    def _build(self, ontology_id: int, utterance: str, ctx: dict, *, commit: bool) -> dict:
        if not commit:
            return self._build_preview(ontology_id, utterance, ctx)
        return self._build_commit(ontology_id, ctx)

    def _build_preview(self, ontology_id: int, utterance: str, ctx: dict) -> dict:
        raw = self._llm_or_none(self._build_prompt(utterance, ctx), ctx.get("model_id"))
        cands = (raw.get("candidates") if isinstance(raw, dict) else None) or []
        cands, dropped = self._normalize_candidates(cands)
        if not cands:
            return {"intent": "build", "commit": False, "degraded": True,
                    "code": ASSISTANT_BUILD_EMPTY, "preview": [], "fingerprint": None,
                    "hallucination_dropped": dropped}
        fp = self._fingerprint(cands)
        return {"intent": "build", "commit": False, "degraded": False, "preview": cands,
                "fingerprint": fp, "hallucination_dropped": dropped,
                "next": "确认后带 commit=true 且原样回传 candidates + fingerprint 提交"}

    def _build_commit(self, ontology_id: int, ctx: dict) -> dict:
        cands = ctx.get("candidates") or []
        provided_fp = ctx.get("fingerprint")
        norm, dropped = self._normalize_candidates(cands, validate_target=False)
        if not norm:
            raise ApiError(ASSISTANT_BUILD_EMPTY, "build 提交无可写入候选",
                           http_status=400, detail={"hallucination_dropped": dropped})
        # 指纹一致性（防线②：跳步/篡改即拒），不参与降级
        if not provided_fp or provided_fp != self._fingerprint(norm):
            raise ApiError(ASSISTANT_BUILD_PREVIEW_STALE, "预览指纹不匹配，请重新预览后再提交",
                           http_status=409, detail={"expected": self._fingerprint(norm)})
        job_id = self._assistant_job_id(ontology_id)
        existing_codes = self._existing_element_codes(ontology_id)
        committed = skipped = 0
        for c in norm:
            dup = c["element_code"] in existing_codes
            self._record_llm_item(job_id, c, skipped=dup)
            if dup:
                skipped += 1
            else:
                committed += 1
        self.db.flush()
        return {"intent": "build", "commit": True, "job_id": job_id, "committed": committed,
                "skipped_duplicated_by_rule": skipped, "hallucination_dropped": dropped,
                "fingerprint": provided_fp}

    def _build_prompt(self, utterance: str, ctx: dict) -> str:
        return (
            "你是本体建模助手。把用户意图转成对象/关系候选（仅草拟，不入库）。\n"
            "只输出 JSON：{\"candidates\": [{\"element_kind\": \"object|relation\", "
            "\"element_code\": str(snake_case), \"name\": str, \"delta\": {..}, \"confidence\": number(0~1)}]}，无 markdown。\n"
            "element_code 用 snake_case，禁止 PascalCase；不确定给低分。\n"
            f"用户意图={utterance or ''}\n上下文={json.dumps(ctx.get('scope') or {}, ensure_ascii=False)[:1500]}"
        )

    def _normalize_candidates(self, raw: List[dict], *, validate_target: bool = True):
        out: List[dict] = []
        dropped = 0
        for c in raw:
            if not isinstance(c, dict):
                dropped += 1
                continue
            kind = c.get("element_kind")
            code = (c.get("element_code") or "").strip()
            if kind not in ("object", "relation") or not code:
                dropped += 1
                continue
            delta = c.get("delta") or {}
            # 引用校验（§5.3 第三道）：命中表/列必须真实（对象带 table 时）
            if validate_target and delta.get("table"):
                if not self._table_exists(delta["table"]):
                    dropped += 1
                    continue
            out.append({
                "element_kind": kind, "element_code": code,
                "action": "insert", "delta": delta,
                "name": c.get("name") or code,
                "confidence": self._clamp(c.get("confidence")),
            })
        return out, dropped

    def _table_exists(self, name: str) -> bool:
        return self.db.execute(
            select(func.count()).select_from(MetaTable).where(
                MetaTable.tenant_id == self.tenant_id, MetaTable.table_name == name
            )
        ).scalar_one() > 0

    @staticmethod
    def _fingerprint(cands: List[dict]) -> str:
        canon = json.dumps(
            sorted(({"k": c["element_kind"], "c": c["element_code"], "d": c["delta"]} for c in cands),
                   key=lambda x: (x["k"], x["c"])),
            ensure_ascii=False, sort_keys=True,
        )
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def _existing_element_codes(self, ontology_id: int) -> set:
        """该本体真实构建任务里已出现的候选 code（用于同 code 规则优先去重）。"""
        job_ids = [j for j in self.db.execute(
            select(MetaOntologyBuildJob.id).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.ontology_id == ontology_id,
                MetaOntologyBuildJob.idempotency_key != f"assistant-virtual-{ontology_id}",
            )
        ).scalars().all()]
        if not job_ids:
            return set()
        codes = self.db.execute(
            select(MetaOntologyBuildItem.element_code).where(
                MetaOntologyBuildItem.tenant_id == self.tenant_id,
                MetaOntologyBuildItem.job_id.in_(job_ids),
            )
        ).scalars().all()
        return set(codes)

    def _assistant_job_id(self, ontology_id: int) -> int:
        """固定虚拟 job（不产生新构建任务）：承载 LLM build 候选并复用唯一约束。"""
        key = f"assistant-virtual-{ontology_id}"
        job = self.db.execute(
            select(MetaOntologyBuildJob).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.idempotency_key == key,
            )
        ).scalar_one_or_none()
        if job is None:
            job = MetaOntologyBuildJob(
                tenant_id=self.tenant_id, ontology_id=ontology_id, idempotency_key=key,
                mode="assistant", scope_json={"mode": "assistant"}, status="succeeded", progress=1.0,
            )
            self.db.add(job)
            self.db.flush()
        return job.id

    def _record_llm_item(self, job_id: int, c: dict, *, skipped: bool) -> None:
        """防线①：LLM 候选 ``origin='llm'`` 且 ``status`` 写死 ``suggested``，永不自动采纳。"""
        existing = self.db.execute(
            select(MetaOntologyBuildItem).where(
                MetaOntologyBuildItem.job_id == job_id,
                MetaOntologyBuildItem.element_kind == c["element_kind"],
                MetaOntologyBuildItem.element_code == c["element_code"],
            )
        ).scalar_one_or_none()
        action = "skip" if skipped else c["action"]
        reason = "duplicated_by_rule" if skipped else None
        if existing is None:
            self.db.add(MetaOntologyBuildItem(
                tenant_id=self.tenant_id, job_id=job_id, element_kind=c["element_kind"],
                element_code=c["element_code"], action=action, origin="llm",
                delta_json=c["delta"], confidence=c["confidence"], status="suggested",
                verdict="no_verdict", verdict_reason=reason,
            ))
        else:
            existing.action = action
            existing.delta_json = c["delta"]
            existing.confidence = c["confidence"]
            existing.status = "suggested"  # 防线①写死
            existing.verdict_reason = reason

    # ------------------------------------------------------------- E38 链路拓扑

    def pipeline(self, ontology_id: int) -> dict:
        ontology = self._ontology_or_404(ontology_id)
        scope = ontology.draft_scope_json or {}
        tables_scope = len(scope.get("tables") or [])

        latest = self.db.execute(
            select(MetaOntologyBuildJob.stats_json, MetaOntologyBuildJob.status)
            .where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.ontology_id == ontology_id,
                MetaOntologyBuildJob.idempotency_key != f"assistant-virtual-{ontology_id}",
            )
            .order_by(MetaOntologyBuildJob.id.desc()).limit(1)
        ).first()
        proc_stats = (latest[0] or {}) if latest else {}
        proc_done = bool(latest and latest[1] == "succeeded")

        job_ids = [j for j in self.db.execute(
            select(MetaOntologyBuildJob.id).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.ontology_id == ontology_id,
            )
        ).scalars().all()]
        pending = accepted = 0
        if job_ids:
            rows = dict(self.db.execute(
                select(MetaOntologyBuildItem.status, func.count()).where(
                    MetaOntologyBuildItem.tenant_id == self.tenant_id,
                    MetaOntologyBuildItem.job_id.in_(job_ids),
                ).group_by(MetaOntologyBuildItem.status)
            ).all())
            pending = int(rows.get("suggested", 0))
            accepted = int(rows.get("accepted", 0))

        version = int(ontology.current_version or 0)
        enabled_pub = int(self.db.execute(
            select(func.count()).select_from(MetaOntologyPublish).where(
                MetaOntologyPublish.tenant_id == self.tenant_id,
                MetaOntologyPublish.ontology_id == ontology_id,
                MetaOntologyPublish.status == "enabled",
            )
        ).scalar_one())

        steps = [
            {"step": 1, "code": "datasource", "label": "数据源表",
             "counts": {"tables": tables_scope}, "done": tables_scope > 0},
            {"step": 2, "code": "processing", "label": "数据处理",
             "counts": {"tables": proc_stats.get("tables", 0), "last_status": (latest[1] if latest else None)},
             "done": proc_done},
            {"step": 3, "code": "modeling", "label": "子图建模",
             "counts": {"suggested": pending, "accepted": accepted}, "done": pending == 0 and accepted > 0},
            {"step": 4, "code": "ontology", "label": "本体库",
             "counts": {"current_version": version}, "done": version >= 1},
            {"step": 5, "code": "application", "label": "本体应用",
             "counts": {"enabled": enabled_pub}, "done": enabled_pub >= 1,
             "blocking": False},
        ]
        return {"ontology_id": ontology_id, "current_version": version, "steps": steps}

    # ------------------------------------------------------------- 通用工具

    def _llm_or_none(self, prompt: str, model_id):
        from app.ai.research.llm import llm_json
        import asyncio
        try:
            result = asyncio.run(llm_json(prompt, model_id=model_id))
        except Exception as exc:  # noqa: BLE001 - 助手降级，不阻断主链路
            logger.warning(f"建模助手 LLM 调用失败（降级）: {exc}")
            return None
        return result if isinstance(result, dict) else None

    @staticmethod
    def _clamp(val):
        try:
            f = float(val)
        except (TypeError, ValueError):
            return None
        if f < 0 or f > 1 or f != f:
            return None
        return f
