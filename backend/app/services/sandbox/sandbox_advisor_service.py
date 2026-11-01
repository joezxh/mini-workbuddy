"""AI 顾问服务（spec §4.1 sandbox_advisor_service，S20）。

**只读**：注册三个确定性证据法（世界概览 / 因果回溯 / 最近观察），把证据 + 沙箱上下文摘要
拼进提示词交 :func:`llm_json` 解释；**零 DB 写路径**（A8——本服务不开任何 add/delete/update/commit）。
LLM 失败降级为「证据拼接文本」（与 ``ontology_assistant_service`` 降级先例一致），不抛异常。
回答可溯源：``degraded=false`` 时 ``cited_evidence`` 归一到证据编号 {1,2,3}。

MVP 走同步 JSON（非 SSE，主规格 U8 收口前不引入第四种流式封装）。
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.research.llm import llm_json
from app.core.api_error import ApiError, SCENE_NOT_FOUND
from app.models.sandbox.sandbox import SandboxObservation, SandboxScene
from app.services.sandbox.sandbox_element_service import SandboxElementService
from app.services.sandbox.sandbox_engine_service import SandboxEngineService

logger = logging.getLogger(__name__)


class SandboxAdvisorService:
    """AI 顾问（按 tenant_id 隔离；无租户拒绝构造；全只读）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("SandboxAdvisorService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._engine = SandboxEngineService(db, tenant_id)
        self._elements = SandboxElementService(db, tenant_id)

    def _scene(self, scene_id: int) -> SandboxScene:
        s = self.db.execute(select(SandboxScene).where(
            SandboxScene.tenant_id == self.tenant_id, SandboxScene.id == scene_id
        )).scalar_one_or_none()
        if s is None:
            raise ApiError(SCENE_NOT_FOUND, "场景不存在", http_status=404)
        return s

    # ------------------------------------------------------------- 证据一：世界概览

    def _evidence_world(self, scene_id: int, branch_id: int) -> str:
        world = self._engine.load_world(scene_id, branch_id)
        tick = self._engine._branch(branch_id).tick_now
        lines = [f"当前 Tick={tick}，实体数={len(world.entities)}："]
        for code in sorted(world.entities):
            e = world.entities[code]
            lines.append(f"  {code}({e['object_code']}) risk={e['risk_score']} "
                         f"masked={e['masked']} props={sorted(e['props'])}")
        kpi = self.db.execute(select(SandboxObservation).where(
            SandboxObservation.tenant_id == self.tenant_id, SandboxObservation.branch_id == branch_id,
            SandboxObservation.kind == "kpi_point").order_by(SandboxObservation.tick.desc())).scalars().first()
        if kpi is not None:
            lines.append(f"最新 KPI：{kpi.detail_json}")
        for g in [x for x in world.elements if x["kind"] == "goal"]:
            lines.append(f"目标 {g['code']}: {g['label']}")
        return "\n".join(lines)

    # ------------------------------------------------------------- 证据二：因果回溯

    def _evidence_trace(self, scene_id: int, branch_id: int, entity_code: str) -> list[dict]:
        """从目标实体沿 accepted causal_edge 反向追溯（depth≤4，固定序），取命中观察。"""
        edges = [e for e in self._elements.load_accepted(scene_id) if e["kind"] == "causal_edge"]
        chain: list[dict] = []
        frontier = {entity_code}
        seen: set[str] = set()
        for _ in range(4):
            nxt: set[str] = set()
            for e in edges:
                target = self._edge_target_entity(e.get("to_ref"))
                if target in frontier and e["code"] not in seen:
                    seen.add(e["code"])
                    obs = self.db.execute(select(SandboxObservation).where(
                        SandboxObservation.tenant_id == self.tenant_id,
                        SandboxObservation.branch_id == branch_id,
                        SandboxObservation.kind.in_(["edge_fired", "rule_fired"]),
                        SandboxObservation.detail_json["element_code"].as_string() == e["code"],
                    ).order_by(SandboxObservation.tick.desc())).scalars().first()
                    chain.append({"element_code": e["code"], "from": e.get("from_ref"),
                                  "to": e.get("to_ref"), "tick": obs.tick if obs else None,
                                  "title": obs.title if obs else e["label"]})
                    if e.get("from_ref"):
                        nxt.add(e["from_ref"])
            if not nxt or nxt == frontier:
                break
            frontier = nxt
        return chain

    @staticmethod
    def _edge_target_entity(to_ref) -> Optional[str]:
        if not to_ref:
            return None
        if "." in to_ref:
            return to_ref.split(".", 1)[0]
        return None

    # ------------------------------------------------------------- 证据三：最近观察

    def _evidence_observations(self, scene_id: int, branch_id: int, last_n: int = 20) -> list[dict]:
        rows = self.db.execute(select(SandboxObservation).where(
            SandboxObservation.tenant_id == self.tenant_id, SandboxObservation.scene_id == scene_id,
            SandboxObservation.branch_id == branch_id, SandboxObservation.source == "engine",
        ).order_by(SandboxObservation.tick.desc(), SandboxObservation.id.desc()).limit(last_n)).scalars().all()
        return [{"tick": o.tick, "kind": o.kind, "severity": o.severity, "title": o.title} for o in rows]

    # ------------------------------------------------------------- ask（S20）

    def _call_llm(self, prompt: str, model_id: Optional[int]):
        try:
            out = llm_json(prompt, model_id=model_id)
            if inspect.isawaitable(out):
                out = asyncio.run(out)
            return out if isinstance(out, dict) else None
        except Exception as exc:  # noqa: BLE001 - 顾问降级，不抛
            logger.warning(f"沙盘顾问 LLM 调用失败（降级）: {exc}")
            return None

    def ask(self, scene_id: int, branch_id: int, question: str, model_id: Optional[int] = None) -> dict:
        self._scene(scene_id)
        world = self._engine.load_world(scene_id, branch_id)
        top = max(world.entities.items(), key=lambda kv: kv[1]["risk_score"])[0] if world.entities else ""
        ev1 = self._evidence_world(scene_id, branch_id)
        ev2 = self._evidence_trace(scene_id, branch_id, top) if top else []
        ev3 = self._evidence_observations(scene_id, branch_id)
        prompt = self._build_prompt(question, ev1, ev2, ev3)
        out = self._call_llm(prompt, model_id)
        if out and isinstance(out.get("answer"), str) and out["answer"].strip():
            cited = [c for c in (out.get("cited_evidence") or []) if c in (1, 2, 3)]
            return {"answer": out["answer"], "cited_evidence": cited, "degraded": False}
        # 降级：证据拼接文本，不开 LLM 也算得出确定性摘要
        degraded_answer = f"【证据摘要】\n1. 世界概览：\n{ev1}\n2. 因果回溯：{ev2}\n3. 最近观察：{ev3}"
        return {"answer": degraded_answer, "cited_evidence": [], "degraded": True}

    @staticmethod
    def _build_prompt(question: str, ev1: str, ev2: list, ev3: list) -> str:
        return (
            "你是推演沙盘顾问，仅解释与归因，不得编造证据之外的实体或数值。\n"
            f"问题：{question}\n"
            f"【证据1 世界概览】\n{ev1}\n"
            f"【证据2 因果回溯】{ev2}\n"
            f"【证据3 最近观察】{ev3}\n"
            '仅输出 JSON：{"answer":"...","cited_evidence":[1,2,3 中的编号]}，回答须标注引用的证据编号。'
        )
