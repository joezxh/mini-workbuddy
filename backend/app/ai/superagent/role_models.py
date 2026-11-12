"""RoleModel —— 按角色路由模型配置（Task 7.3）。

对齐 dsh-superagent RoleModel / spec.md「Background Jev 决策模型」：
orchestrator / worker / reflector 三角色各自可配置 provider + model +
reasoning_effort，从 ai_workspace config JSON 的 ``role_models`` 字段构建，
在 Agent 首次请求前注入（不修改全局默认模型配置）。
"""
from __future__ import annotations

from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel


class RoleModel(BaseModel):
    """单角色的模型配置。"""

    provider: str
    model: str
    reasoning_effort: Optional[str] = None


class RoleModelConfig(BaseModel):
    """三角色模型路由配置。"""

    orchestrator: Optional[RoleModel] = None  # AssessorService / Eval
    worker: Optional[RoleModel] = None        # WorkerSession
    reflector: Optional[RoleModel] = None     # ReflectorService


def role_model_config_from_workspace(cfg: dict | None) -> RoleModelConfig:
    """workspace config JSON 的 role_models 字段 → RoleModelConfig（容错解析）。

    非法条目（缺 model / 类型错误）记 warning 并跳过，不抛异常。
    """
    rm = (cfg or {}).get("role_models") or {}

    def _one(v: Any) -> Optional[RoleModel]:
        if not isinstance(v, dict) or not str(v.get("model") or "").strip():
            return None
        try:
            return RoleModel(**v)
        except Exception as e:
            logger.warning(f"role_model_config_from_workspace · 非法 role_model 配置 {v}: {e}")
            return None

    return RoleModelConfig(
        orchestrator=_one(rm.get("orchestrator")),
        worker=_one(rm.get("worker")),
        reflector=_one(rm.get("reflector")),
    )


def _try_build_model(role: RoleModel) -> Any | None:
    """role → AgentScope ChatModelBase（复用 factory_ext.build_model）。

    任何失败（agentscope 未安装 / provider 未知 / 凭据缺失）返回 None，
    调用方降级为标识注入。
    """
    try:
        from app.ai.strategy.factory_ext import build_model
        return build_model({"provider": role.provider, "model": role.model})
    except Exception as e:
        logger.warning(f"initialize_role_model · build_model 失败（降级为标识注入）: {e}")
        return None


def initialize_role_model(agent: Any, role: RoleModel) -> bool:
    """在 Agent 首次请求前注入 model 配置，不修改全局默认。

    优先构建真实 ChatModelBase 覆盖 ``agent.model``；构建不可用时降级为
    写入 model 标识字符串。reasoning_effort 一并注入（供请求参数 / 可观测）。
    任何失败只 warning + return False，不抛异常。
    """
    if agent is None or role is None or not str(role.model or "").strip():
        logger.warning("initialize_role_model · 缺少 agent 或 role.model —— 跳过注入")
        return False
    try:
        model = _try_build_model(role)
        setattr(agent, "model", model if model is not None else role.model)
        if role.reasoning_effort:
            try:
                setattr(agent, "reasoning_effort", role.reasoning_effort)
            except Exception:
                pass
        try:
            setattr(agent, "_role_model", role)
        except Exception:
            pass
        logger.info(
            f"initialize_role_model · 注入 model={role.model} · "
            f"provider={role.provider} · real_model={model is not None}"
        )
        return True
    except Exception as e:
        logger.warning(f"initialize_role_model failed · model={role.model}: {e}")
        return False
