"""行动门禁与两段式确认服务（spec §5.3/§5.4，S16–S18）。

六步求值序列（顺序即验收语义 A3/A4/A5）：

1. ``exec_mode=='replay'`` → denied(MODE_READONLY)，落审计后返回（**非 403**）；
2. 无 ``sandbox:act`` 功能权限 → denied(NO_ACTION_PERMISSION)，落审计；
3. 目标实体 ``masked`` → denied(MASKED_TARGET)，落审计（A3：脱敏目标禁施加行动）；
4. 模板 disabled / 参数不合 schema → **400**（非法请求不进门禁、不留痕，spec §5.3）；
5. ``exec_mode=='stepwise'`` → pending + confirm_token，落审计；确认超时 5 分钟 → CONFIRM_EXPIRED；
6. ``exec_mode=='auto'`` → allowed → 写 SimEvent（derived 实体行）+ 目标属性改写 → run_tick 推进 1 Tick。

**未经确认的 pending 行动绝不改变世界**（A4）。denied 一律先落 :class:`SandboxAction` 审计再返回。
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ACTION_TEMPLATE_DISABLED, CONFIRM_EXPIRED, SCENE_NOT_FOUND,
)
from app.models.sandbox.action_template import SandboxActionTemplate
from app.models.sandbox.sandbox import (
    SandboxAction, SandboxBranch, SandboxEntity, SandboxScene,
)
from app.services.sandbox.ast_eval import eval_expr
from app.services.sandbox.sandbox_engine_service import SandboxEngineService, _Q

logger = logging.getLogger(__name__)

_CONFIRM_TTL = timedelta(seconds=300)


def _validate_params(schema: dict, params: dict) -> None:
    """参数不合 param_schema_json → 400（取首条 jsonschema 错误入 detail，不入门禁留痕）。"""
    import jsonschema
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(params), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        raise ApiError("PARAM_INVALID", "行动参数不符合模板 schema", http_status=400,
                       detail={"path": list(e.path), "message": e.message})


class SandboxActionService:
    """行动门禁（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: Optional[int] = None,
                 *, has_act_permission: bool = True) -> None:
        if tenant_id is None:
            raise ValueError("SandboxActionService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.has_act_permission = has_act_permission
        self._engine = SandboxEngineService(db, tenant_id)

    # ------------------------------------------------------------------ 内部

    def _scene(self, scene_id: int) -> SandboxScene:
        s = self.db.execute(select(SandboxScene).where(
            SandboxScene.tenant_id == self.tenant_id, SandboxScene.id == scene_id
        )).scalar_one_or_none()
        if s is None:
            raise ApiError(SCENE_NOT_FOUND, "场景不存在", http_status=404)
        return s

    def _branch_tick(self, branch_id: int) -> int:
        br = self.db.get(SandboxBranch, branch_id)
        return br.tick_now if br else 0

    def _deny(self, scene_id: int, branch_id: int, tick: int, reason: str,
              *, template_code: str, target_entity_code: str, params: dict) -> dict:
        act = SandboxAction(tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id,
                            tick=tick, template_code=template_code, target_entity_code=target_entity_code,
                            params_json=params, gate_result="denied", gate_reason=reason,
                            operator_id=self.user_id)
        self.db.add(act)
        self.db.commit()
        return {"gate_result": "denied", "action_id": act.id, "reason": reason}

    # ------------------------------------------------------------------ S16

    def list_templates(self) -> list[dict]:
        rows = self.db.execute(select(SandboxActionTemplate).where(
            SandboxActionTemplate.status == "enabled").order_by(SandboxActionTemplate.code)).scalars().all()
        return [{"code": t.code, "name": t.name, "description": t.description,
                 "domain_hint": t.domain_hint, "param_schema_json": t.param_schema_json,
                 "effect_spec_json": t.effect_spec_json} for t in rows]

    # ------------------------------------------------------------------ S17 六步门禁

    def apply_action(self, scene_id: int, branch_id: int, *, template_code: str,
                     target_entity_code: str, params: dict) -> dict:
        scene = self._scene(scene_id)
        tick = self._branch_tick(branch_id)
        params = params or {}
        # ① replay 只读
        if scene.exec_mode == "replay":
            return self._deny(scene_id, branch_id, tick, "MODE_READONLY",
                              template_code=template_code, target_entity_code=target_entity_code, params=params)
        # ② 功能权限
        if not self.has_act_permission:
            return self._deny(scene_id, branch_id, tick, "NO_ACTION_PERMISSION",
                              template_code=template_code, target_entity_code=target_entity_code, params=params)
        # ③ 脱敏目标
        target = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.tenant_id == self.tenant_id, SandboxEntity.branch_id == branch_id,
            SandboxEntity.entity_code == target_entity_code,
            SandboxEntity.checkpoint_id.is_(None))).scalar_one_or_none()
        if target is not None and target.masked:
            return self._deny(scene_id, branch_id, tick, "MASKED_TARGET",
                              template_code=template_code, target_entity_code=target_entity_code, params=params)
        # ④ 模板可用性 + 参数 schema（非法 → 400，不留痕）
        tpl = self.db.execute(select(SandboxActionTemplate).where(
            SandboxActionTemplate.code == template_code)).scalar_one_or_none()
        if tpl is None or tpl.status != "enabled":
            raise ApiError(ACTION_TEMPLATE_DISABLED, f"行动模板不可用: {template_code}", http_status=400)
        _validate_params(tpl.param_schema_json or {}, params)
        if target is None:
            raise ApiError("PARAM_INVALID", "目标实体不存在", http_status=400)
        # ⑤ stepwise → pending（不写世界，A4）
        if scene.exec_mode == "stepwise":
            token = secrets.token_urlsafe(24)
            act = SandboxAction(tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id,
                                tick=tick, template_code=template_code, target_entity_code=target_entity_code,
                                params_json=params, gate_result="pending", confirm_token=token,
                                operator_id=self.user_id)
            self.db.add(act)
            self.db.commit()
            return {"gate_result": "pending", "action_id": act.id, "confirm_token": token}
        # ⑥ auto → allowed，落事件 + 改写 + 推进
        act = SandboxAction(tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id,
                            tick=tick, template_code=template_code, target_entity_code=target_entity_code,
                            params_json=params, gate_result="allowed", operator_id=self.user_id)
        self.db.add(act)
        self._execute_effect(scene_id, branch_id, tick, target_entity_code, tpl, params)
        self.db.commit()
        after = self._engine.run_tick(scene_id, branch_id)
        return {"gate_result": "allowed", "action_id": act.id, "tick_after": after}

    # ------------------------------------------------------------------ S17b 确认

    def confirm_action(self, scene_id: int, action_id: int, *, token: str) -> dict:
        act = self.db.get(SandboxAction, action_id)
        if act is None or act.tenant_id != self.tenant_id or act.scene_id != scene_id:
            raise ApiError("PARAM_INVALID", "行动不存在", http_status=400)
        if act.gate_result != "pending" or act.confirm_token != token:
            raise ApiError(CONFIRM_EXPIRED, "确认令牌无效或行动已处理", http_status=400)
        if act.created_at is None or act.created_at + _CONFIRM_TTL < datetime.now():
            raise ApiError(CONFIRM_EXPIRED, "确认已超时（5 分钟）", http_status=400)
        tpl = self.db.execute(select(SandboxActionTemplate).where(
            SandboxActionTemplate.code == act.template_code)).scalar_one()
        self._execute_effect(scene_id, act.branch_id, act.tick, act.target_entity_code, tpl, act.params_json or {})
        act.gate_result = "allowed"
        act.confirm_token = None
        self.db.commit()
        after = self._engine.run_tick(scene_id, act.branch_id)
        return {"gate_result": "allowed", "action_id": act.id, "tick_after": after}

    # ------------------------------------------------------------------ 生效写入

    def _execute_effect(self, scene_id: int, branch_id: int, tick: int, target_entity_code: str,
                        tpl: SandboxActionTemplate, params: dict) -> None:
        """写 SimEvent（derived 实体行）+ 目标属性改写（AST 求值，get_param 取 params）。"""
        spec = tpl.effect_spec_json or {}
        delay = int(spec.get("fire_delay_tick", 1))
        ev_code = f"EV{tick + delay:03d}"
        world = self._engine.load_world(scene_id, branch_id)

        def get_prop(code: str, key: str) -> Decimal:
            return world.get_prop(code if code != "<target>" else target_entity_code, key)

        def get_param(key: str) -> Decimal:
            return Decimal(str(params.get(key, 0)))

        gp = lambda code, key: get_prop(code, key)  # noqa: E731
        gm = get_param
        for w in spec.get("writes", []):
            ent = w["entity"] if w["entity"] != "<target>" else target_entity_code
            val = Decimal(str(eval_expr(w["expr"], gp, gm))).quantize(_Q)
            if ent in world.entities:
                world.set_prop(ent, w["prop"], val)
        # SimEvent：derived 实体行，activation_tick=tick+delay，供引擎 _fire_events 到期生效
        self.db.add(SandboxEntity(
            tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id, checkpoint_id=None,
            entity_code=f"{ev_code}_{target_entity_code}", object_code="SimEvent",
            props_json={"activation_tick": str(tick + delay), "template": tpl.code,
                        "target": target_entity_code}, risk_score=0.0, masked=False, origin="derived"))
        # 目标改写落库
        for code, e in world.entities.items():
            if code == target_entity_code:
                row = self.db.execute(select(SandboxEntity).where(
                    SandboxEntity.branch_id == branch_id, SandboxEntity.entity_code == code,
                    SandboxEntity.checkpoint_id.is_(None))).scalar_one()
                row.props_json = {k: str(v) for k, v in e["props"].items()}
                row.risk_score = float(e["risk_score"])
        self.db.flush()

    # ------------------------------------------------------------------ S18

    def list_actions(self, scene_id: int, *, branch_id: Optional[int] = None,
                     result: Optional[str] = None) -> list[dict]:
        q = select(SandboxAction).where(SandboxAction.tenant_id == self.tenant_id,
                                       SandboxAction.scene_id == scene_id)
        if branch_id is not None:
            q = q.where(SandboxAction.branch_id == branch_id)
        if result:
            q = q.where(SandboxAction.gate_result == result)
        rows = self.db.execute(q.order_by(SandboxAction.id)).scalars().all()
        return [{"id": a.id, "branch_id": a.branch_id, "tick": a.tick, "template_code": a.template_code,
                 "target_entity_code": a.target_entity_code, "gate_result": a.gate_result,
                 "gate_reason": a.gate_reason, "params_json": a.params_json} for a in rows]
