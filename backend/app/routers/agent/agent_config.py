"""Agent 配置管理 API"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.agent.agent import (
    AgentConfigCreate,
    AgentConfigResponse,
    AgentConfigListResponse,
    AgentRegistryResponse,
)
from app.services.agent.agent_config_service import AgentConfigService
from app.models.agent.agent_config import AgentConfig
from app.models.ai.ai_chat import AiChatSession
from app.models.agent.agent_trace import AgentTrace


router = APIRouter(prefix="/api/v1/agent-config", tags=["AgentConfig"])


@router.get("/stats/overview")
def get_stats_overview(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 Agent 监控统计概览"""
    try:
        total_agents = db.query(func.count(AgentConfig.id)).filter(
            AgentConfig.is_deleted == False
        ).scalar() or 0

        active_agents = db.query(func.count(AgentConfig.id)).filter(
            AgentConfig.is_deleted == False,
            AgentConfig.is_active == True,
        ).scalar() or 0

        inactive_agents = total_agents - active_agents

        active_sessions = db.query(func.count(AiChatSession.session_id)).filter(
            AiChatSession.status == 'active'
        ).scalar() or 0

        total_sessions = db.query(func.count(AiChatSession.session_id)).scalar() or 0

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        today_total = db.query(func.count(AgentTrace.id)).filter(
            AgentTrace.start_time >= today_start
        ).scalar() or 0

        today_success = db.query(func.count(AgentTrace.id)).filter(
            AgentTrace.start_time >= today_start,
            AgentTrace.status == 'OK',
        ).scalar() or 0

        today_error = today_total - today_success

        avg_duration = db.query(func.avg(AgentTrace.duration_ms)).filter(
            AgentTrace.start_time >= today_start,
            AgentTrace.duration_ms.isnot(None),
        ).scalar() or 0

        total_traces = db.query(func.count(AgentTrace.id)).scalar() or 0

        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "inactive_agents": inactive_agents,
            "active_sessions": active_sessions,
            "total_sessions": total_sessions,
            "today_invocations": today_total,
            "today_success": today_success,
            "today_error": today_error,
            "avg_duration_ms": int(avg_duration) if avg_duration else 0,
            "total_traces": total_traces,
        }
    except Exception as e:
        return {
            "total_agents": 0,
            "active_agents": 0,
            "inactive_agents": 0,
            "active_sessions": 0,
            "total_sessions": 0,
            "today_invocations": 0,
            "today_success": 0,
            "today_error": 0,
            "avg_duration_ms": 0,
            "total_traces": 0,
            "error": str(e),
        }


@router.get("", response_model=AgentConfigListResponse)
def list_agents(
    agent_type: Optional[str] = Query(None, description="实现类型: CHAT/WORKFLOW/SKILL"),
    category: Optional[str] = Query(None, description="用途分类"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 Agent 配置列表"""
    svc = AgentConfigService()
    total, agents = svc.list_agents(db, agent_type, is_active, page, page_size, category=category)
    return {"total": total, "items": [AgentConfigResponse.model_validate(a) for a in agents]}


@router.get("/registry", response_model=AgentRegistryResponse)
def get_agent_registry(
    category: Optional[str] = Query(None, description="用途分类过滤"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 Agent 注册表（参考技能获取接口），按 category 分组便于前端分类展示。

    - 返回全部启用的 Agent 配置，并按 category 分组
    - agent_team 标识 AgentTeam 多智能体协作能力（后端暂未实现）
    """
    svc = AgentConfigService()
    # 拉取全部启用的 Agent（单页上限放大以满足前端整列展示）
    total, agents = svc.list_agents(
        db, agent_type=None, is_active=True, page=1, page_size=1000, category=category
    )
    grouped: dict = {}
    for a in agents:
        cat = a.category or "default"
        grouped.setdefault(cat, []).append(AgentConfigResponse.model_validate(a))
    return {
        "total": total,
        "agents": [AgentConfigResponse.model_validate(a) for a in agents],
        "grouped": grouped,
        "categories": list(grouped.keys()),
        "agent_team": {"available": False, "message": "AgentTeam 后端暂未实现"},
    }


@router.get("/{agent_id}", response_model=AgentConfigResponse)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取单个 Agent 配置"""
    svc = AgentConfigService()
    agent = svc.get_by_id(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return agent


def _flatten_create(req: "AgentConfigCreate") -> dict:
    """将嵌套的 AgentConfigCreate 展平为 AgentConfig 模型列字段。

    真实 schema 结构（populate_by_name=True）：
        strategy: {strategy_code, execution_mode, system_prompt}
        tools:    {tools, skills, mcp_servers, knowledge_bases}
        llm_config(model_config 别名): {provider, model, base_url, temperature, max_tokens, api_key_ref}
        execution:{hitl_config, react_config, context_config}
    """
    def _as_dict(v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        return v.model_dump()

    strategy = req.strategy
    tools_cfg = req.tools
    model_cfg = req.llm_config
    execution = req.execution

    return {
        "strategy_code": strategy.strategy_code if strategy else None,
        "execution_mode": strategy.execution_mode if strategy else "llm",
        "system_prompt": strategy.system_prompt if strategy else None,
        "tools": list(tools_cfg.tools) if tools_cfg and tools_cfg.tools else [],
        "skills": list(tools_cfg.skills) if tools_cfg and tools_cfg.skills else [],
        "mcp_servers": list(tools_cfg.mcp_servers) if tools_cfg and tools_cfg.mcp_servers else [],
        "knowledge_bases": list(tools_cfg.knowledge_bases) if tools_cfg and tools_cfg.knowledge_bases else [],
        "llm_config": _as_dict(model_cfg),
        "hitl_config": execution.hitl_config if execution else None,
        "react_config": execution.react_config if execution else None,
        "context_config": execution.context_config if execution else None,
        "category": req.category,
        "description": req.description,
        "config": req.config,
        "is_active": req.is_active,
        "sort_order": req.sort_order,
    }


@router.post("", response_model=AgentConfigResponse, status_code=201)
def create_agent(
    req: AgentConfigCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建 Agent 配置（持久化结构化配置：策略/模型/MCP/tools/skills/提示词等）"""
    svc = AgentConfigService()
    existing = svc.get_by_code(db, req.agent_code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent code '{req.agent_code}' 已存在")

    flat = _flatten_create(req)
    agent = svc.create(
        db,
        agent_code=req.agent_code,
        name=req.name,
        agent_type=req.agent_type,
        created_by=current_user.user_id,
        **flat,
    )
    return agent


@router.put("/{agent_id}", response_model=AgentConfigResponse)
def update_agent(
    agent_id: int,
    req: AgentConfigCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新 Agent 配置（全量结构化字段）"""
    svc = AgentConfigService()
    flat = _flatten_create(req)
    # 保留标量 identity 字段
    flat["name"] = req.name
    flat["agent_type"] = req.agent_type
    agent = svc.update(db, agent_id, **flat)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return agent


@router.post("/{agent_id}/toggle", response_model=AgentConfigResponse)
def toggle_agent(
    agent_id: int,
    is_active: Optional[bool] = Query(None, description="目标状态；不传则翻转当前状态"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """启用/禁用 Agent"""
    svc = AgentConfigService()
    agent = svc.toggle_active(db, agent_id, is_active)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return agent


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除 Agent 配置（软删除）"""
    svc = AgentConfigService()
    ok = svc.delete(db, agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return {"deleted": True}
