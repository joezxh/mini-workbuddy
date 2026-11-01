"""配置元素服务（spec §3.6 / §4.1 sandbox_element_service，S13–S15）。

统一承载因果边 / 规则 / 目标 / 未来事件模板四类 element 的 CRUD、D3 人审采纳，
以及 LLM 辅助建模草稿（S14）。**D3 三层防线（V2/A8）在此落地**：

1. :meth:`upsert_element` 对 ``origin='llm'`` 强制 ``status='suggested'``（应用层）；
2. 数据库级 CHECK ``NOT (origin='llm' AND status<>'suggested')``（Task 1 兜底）；
3. :meth:`review_element` 采纳 = 把候选**转为 human 署名**的 ``accepted``（而非翻转
   llm 行），确保「LLM 产出永不直接生效，只有人担责署名后才参与引擎求值」；
   :meth:`load_accepted` 只暴露 ``accepted`` 且按 ``(kind, code)`` 固定序（A1 前提）。

LLM 调用姿势照 ``ontology_assistant_service._llm_or_none``：``asyncio.run`` + try/except
降级；S14 结果逐条用 :func:`ast_eval.eval_expr` 以恒 0 源试编译，坏 AST 条丢弃。
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.research.llm import llm_json
from app.core.api_error import ApiError, SCENE_NOT_FOUND
from app.models.sandbox.sandbox import SandboxElement, SandboxEntity, SandboxScene
from app.services.sandbox.ast_eval import eval_expr

logger = logging.getLogger(__name__)

_KINDS = ("causal_edge", "rule", "goal", "future_event")
# payload 可写的模型列（scene_id/tenant/origin/status 由方法单独管控）
_MUTABLE_COLS = ("kind", "code", "label", "from_ref", "to_ref",
                 "condition_expr_json", "effect_expr_json", "activation_tick", "confidence")


class SandboxElementService:
    """配置元素（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("SandboxElementService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------ 内部

    def _scene_or_404(self, scene_id: int) -> SandboxScene:
        s = self.db.execute(select(SandboxScene).where(
            SandboxScene.tenant_id == self.tenant_id, SandboxScene.id == scene_id
        )).scalar_one_or_none()
        if s is None:
            raise ApiError(SCENE_NOT_FOUND, "场景不存在", http_status=404)
        return s

    def _get_or_404(self, element_id: int) -> SandboxElement:
        el = self.db.get(SandboxElement, element_id)
        if el is None or el.tenant_id != self.tenant_id:
            raise ApiError("ELEMENT_NOT_FOUND", "配置元素不存在", http_status=404)
        return el

    @staticmethod
    def _to_dict(el: SandboxElement) -> dict:
        return {c: getattr(el, c) for c in
                ("id", "scene_id", "kind", "code", "label", "from_ref", "to_ref",
                 "condition_expr_json", "effect_expr_json", "activation_tick",
                 "origin", "status", "confidence")}

    # ------------------------------------------------------------------ CRUD

    def list_elements(self, scene_id: int, *, kind: Optional[str] = None,
                      status: Optional[str] = None) -> list[dict]:
        self._scene_or_404(scene_id)
        q = select(SandboxElement).where(
            SandboxElement.tenant_id == self.tenant_id, SandboxElement.scene_id == scene_id)
        if kind:
            q = q.where(SandboxElement.kind == kind)
        if status:
            q = q.where(SandboxElement.status == status)
        rows = self.db.execute(q.order_by(SandboxElement.kind, SandboxElement.code)).scalars().all()
        return [self._to_dict(r) for r in rows]

    def upsert_element(self, scene_id: int, payload: dict, *, origin: str = "human",
                       creator_id: Optional[int] = None) -> dict:
        """(scene,kind,code) 命中即覆盖非空字段；llm 来源强制 suggested（D3 应用层）。"""
        self._scene_or_404(scene_id)
        kind, code = payload.get("kind"), payload.get("code")
        if kind not in _KINDS:
            raise ApiError("ELEMENT_KIND_INVALID", f"kind 非法: {kind!r}", http_status=400)
        if not code:
            raise ApiError("ELEMENT_CODE_REQUIRED", "缺少 code", http_status=400)
        fields = {c: payload[c] for c in _MUTABLE_COLS
                  if payload.get(c) is not None and payload.get(c) != ""}
        if origin not in ("human", "llm", "rule"):
            origin = "human"
        existing = self.db.execute(select(SandboxElement).where(
            SandboxElement.tenant_id == self.tenant_id, SandboxElement.scene_id == scene_id,
            SandboxElement.kind == kind, SandboxElement.code == code)).scalar_one_or_none()
        if existing is None:
            status = "suggested" if origin == "llm" else payload.get("status", "suggested")
            el = SandboxElement(tenant_id=self.tenant_id, scene_id=scene_id, origin=origin,
                                status=status, creator_id=creator_id, **fields)
            self.db.add(el)
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.origin = origin
            if origin == "llm":
                existing.status = "suggested"
            el = existing
        self.db.flush()
        return self._to_dict(el)

    def delete_element(self, element_id: int) -> None:
        el = self._get_or_404(element_id)
        self.db.delete(el)
        self.db.commit()

    def update_element(self, element_id: int, payload: dict) -> dict:
        """S13 PUT：按现有 (scene,kind,code) 覆盖非空字段（键不变，复用 upsert 语义）。"""
        el = self._get_or_404(element_id)
        merged = {k: getattr(el, k) for k in ("kind", "code")}
        merged.update({k: v for k, v in payload.items() if k in _MUTABLE_COLS})
        return self.upsert_element(el.scene_id, merged, origin=el.origin)

    # ------------------------------------------------------------------ D3 审阅

    def review_element(self, element_id: int, decision: str) -> dict:
        """S15：仅 suggested 可审阅；accept 把 llm 候选转 human 署名后生效（D3 执行点）。"""
        el = self._get_or_404(element_id)
        if decision not in ("accept", "reject"):
            raise ApiError("ELEMENT_REVIEW_DECISION", f"decision 非法: {decision!r}", http_status=400)
        if el.status != "suggested":
            raise ApiError("ELEMENT_REVIEW_STATE", "仅 suggested 候选可审阅", http_status=400)
        if decision == "accept":
            el.status = "accepted"
            if el.origin == "llm":          # 人担责署名，规避 llm+accepted 违反 CHECK
                el.origin = "human"
        else:
            el.status = "rejected"
        self.db.commit()
        return self._to_dict(el)

    def load_accepted(self, scene_id: int) -> list[dict]:
        """引擎加载入口：仅 accepted，按 (kind, code) 字符串元组固定序（A1 前提）。"""
        rows = self.db.execute(select(SandboxElement).where(
            SandboxElement.tenant_id == self.tenant_id, SandboxElement.scene_id == scene_id,
            SandboxElement.status == "accepted")).scalars().all()
        return sorted((self._to_dict(r) for r in rows), key=lambda d: (d["kind"], d["code"]))

    # ------------------------------------------------------------------ LLM 草稿

    def _call_llm(self, prompt: str, model_id: Optional[int]):
        """兼容真实 async llm_json 与测试注入 sync 假函数；异常/空 → None（降级不抛）。"""
        try:
            out = llm_json(prompt, model_id=model_id)
            if inspect.isawaitable(out):
                out = asyncio.run(out)
            return out if isinstance(out, dict) else None
        except Exception as exc:  # noqa: BLE001 - 建模助手降级，不阻断主链路
            logger.warning(f"沙盘 LLM 辅助建模调用失败（降级）: {exc}")
            return None

    @staticmethod
    def _try_compile(node) -> bool:
        """以恒 0 prop/param 源试编译 AST；None 视为合法，抛 AstEvalError/其他异常拒绝。"""
        if node is None:
            return True
        try:
            eval_expr(node, lambda e, k: Decimal(0), lambda k: Decimal(0))
            return True
        except Exception:  # noqa: BLE001 - 含 AstEvalError 在内，任意求值异常即拒
            return False

    def draft_llm(self, scene_id: int, branch_id: Optional[int] = None,
                  model_id: Optional[int] = None) -> list[dict]:
        """S14：按世界实体清单生成候选，AST 校验后落 origin='llm'/suggested。"""
        scene = self._scene_or_404(scene_id)
        codes = [c for (c,) in self.db.execute(
            select(SandboxEntity.entity_code).where(
                SandboxEntity.tenant_id == self.tenant_id,
                SandboxEntity.scene_id == scene_id,
                SandboxEntity.checkpoint_id.is_(None)).distinct())]
        prompt = self._build_prompt(scene.name, codes)
        out = self._call_llm(prompt, model_id)
        if not out or not isinstance(out.get("elements"), list):
            return []
        created: list[dict] = []
        for item in out["elements"]:
            if not isinstance(item, dict):
                continue
            if item.get("kind") not in _KINDS or not item.get("code") or not item.get("label"):
                continue
            if not self._try_compile(item.get("condition_expr_json")):
                continue
            if not self._try_compile(item.get("effect_expr_json")):
                continue
            created.append(self.upsert_element(scene_id, item, origin="llm"))
        self.db.commit()
        return created

    @staticmethod
    def _build_prompt(scene_name: str, entity_codes: list) -> str:
        return (
            f"你是供应链推演建模助手。场景：{scene_name}。世界实体清单：{entity_codes}。\n"
            "请仅输出 JSON：{\"elements\":[{\"kind\":\"causal_edge|rule|goal|future_event\","
            "\"code\":\"场景内唯一\",\"label\":\"展示名\",\"from_ref\":\"...\",\"to_ref\":\"...\","
            "\"condition_expr_json\":{受控AST},\"effect_expr_json\":{受控AST}}]}。\n"
            "AST 文法仅允许 op: num/prop/param/add/sub/mul/div/mod/gt/ge/lt/le/eq/ne/"
            "and/or/not/min/max/sum/avg/count/clip/if，禁止其它算子。"
        )
