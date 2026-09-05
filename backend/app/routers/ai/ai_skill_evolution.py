"""Skill 进化管理 API - 指标查看/配置管理/手动触发进化/版本回滚"""
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.ai.ai_skill_metrics import AiSkillMetrics
from app.models.ai.ai_skill_version import AiSkillVersion
from app.models.ai.ai_skill_evolution_log import AiSkillEvolutionLog
from app.models.ai.ai_skill_evolution_config import AiSkillEvolutionConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/skill-evolution", tags=["SkillEvolution"])

# 熔断：单技能每日最多进化次数
MAX_EVOLUTION_PER_DAY = 3


# ── Schemas ──────────────────────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    skill_id: str
    execution_count: int = 0
    success_rate: float = 0.0
    avg_latency: float = 0.0
    user_rating: float = 0.0


class ConfigResponse(BaseModel):
    skill_id: str
    threshold: float = 0.7
    weight_success: float = 0.4
    weight_latency: float = 0.2
    weight_user_rating: float = 0.3
    resource_score: float = 0.8
    is_auto_enabled: bool = False
    model_code: Optional[str] = None


class ConfigUpdate(BaseModel):
    threshold: Optional[float] = Field(None, ge=0.1, le=1.0)
    weight_success: Optional[float] = Field(None, ge=0, le=1)
    weight_latency: Optional[float] = Field(None, ge=0, le=1)
    weight_user_rating: Optional[float] = Field(None, ge=0, le=1)
    resource_score: Optional[float] = Field(None, ge=0, le=1)
    is_auto_enabled: Optional[bool] = None
    model_code: Optional[str] = None


class EvolveResponse(BaseModel):
    success: bool
    score: float
    evolved: bool
    message: str


class VersionItem(BaseModel):
    version_number: int
    is_stable: bool
    changes: Optional[dict] = None
    created_at: Optional[str] = None


class EvolutionLogItem(BaseModel):
    id: int
    skill_id: str
    from_version: Optional[int] = None
    to_version: Optional[int] = None
    trigger_type: str
    result: str
    created_at: Optional[str] = None


# ── 指标 ─────────────────────────────────────────────────────────────────────

@router.get("/{skill_id}/metrics", response_model=MetricsResponse)
def get_metrics(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取技能执行指标"""
    metrics = db.query(AiSkillMetrics).filter(AiSkillMetrics.skill_id == skill_id).first()
    if not metrics:
        return MetricsResponse(skill_id=skill_id)
    return MetricsResponse(
        skill_id=metrics.skill_id,
        execution_count=metrics.execution_count or 0,
        success_rate=metrics.success_rate or 0.0,
        avg_latency=metrics.avg_latency or 0.0,
        user_rating=metrics.user_rating or 0.0,
    )


# ── 配置 ─────────────────────────────────────────────────────────────────────

@router.get("/{skill_id}/config", response_model=ConfigResponse)
def get_config(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取进化配置（不存在则返回默认值）"""
    config = db.query(AiSkillEvolutionConfig).filter(
        AiSkillEvolutionConfig.skill_id == skill_id
    ).first()
    if not config:
        return ConfigResponse(skill_id=skill_id)
    return ConfigResponse(
        skill_id=config.skill_id,
        threshold=config.threshold,
        weight_success=config.weight_success,
        weight_latency=config.weight_latency,
        weight_user_rating=config.weight_user_rating,
        resource_score=config.resource_score,
        is_auto_enabled=config.is_auto_enabled,
        model_code=config.model_code,
    )


@router.put("/{skill_id}/config", response_model=ConfigResponse)
def update_config(
    skill_id: str,
    body: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新进化配置（不存在则创建）"""
    config = db.query(AiSkillEvolutionConfig).filter(
        AiSkillEvolutionConfig.skill_id == skill_id
    ).first()

    if not config:
        config = AiSkillEvolutionConfig(skill_id=skill_id)
        db.add(config)

    if body.threshold is not None:
        config.threshold = body.threshold
    if body.weight_success is not None:
        config.weight_success = body.weight_success
    if body.weight_latency is not None:
        config.weight_latency = body.weight_latency
    if body.weight_user_rating is not None:
        config.weight_user_rating = body.weight_user_rating
    if body.resource_score is not None:
        config.resource_score = body.resource_score
    if body.is_auto_enabled is not None:
        config.is_auto_enabled = body.is_auto_enabled
    if body.model_code is not None:
        config.model_code = body.model_code or None

    db.commit()
    db.refresh(config)
    return ConfigResponse(
        skill_id=config.skill_id,
        threshold=config.threshold,
        weight_success=config.weight_success,
        weight_latency=config.weight_latency,
        weight_user_rating=config.weight_user_rating,
        resource_score=config.resource_score,
        is_auto_enabled=config.is_auto_enabled,
        model_code=config.model_code,
    )


# ── 进化触发 ─────────────────────────────────────────────────────────────────

@router.post("/{skill_id}/evolve", response_model=EvolveResponse)
def trigger_evolution(
    skill_id: str,
    model_code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """手动触发进化评估

    model_code: 可选，指定进化使用的 LLM 文本模型（关联 ai_chat_model.code）。
                不传则使用配置表中的 model_code，若仍为空则用默认模型。
    """
    # 熔断检查：今日进化次数
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_count = db.query(AiSkillEvolutionLog).filter(
        AiSkillEvolutionLog.skill_id == skill_id,
        AiSkillEvolutionLog.created_at >= today_start,
    ).count()
    if today_count >= MAX_EVOLUTION_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"今日进化次数已达上限（{MAX_EVOLUTION_PER_DAY} 次），请明日再试"
        )

    try:
        from app.ai.skills.evolution.engine import SkillEvolutionEngine

        # 从配置表读取阈值与默认模型
        config = db.query(AiSkillEvolutionConfig).filter(
            AiSkillEvolutionConfig.skill_id == skill_id
        ).first()
        threshold = config.threshold if config else 0.7
        # 优先级：请求参数 → 配置表 model_code → 默认（None）
        effective_model_code = model_code or (config.model_code if config else None)

        engine = SkillEvolutionEngine(db=db, threshold=threshold)
        score = engine.evaluate(skill_id)
        evolved = engine.evolve_if_needed(
            skill_id, trigger="manual", model_code=effective_model_code
        )

        return EvolveResponse(
            success=True,
            score=round(score, 4),
            evolved=evolved,
            message="进化成功，已生成新版本" if evolved else f"得分 {score:.3f} >= 阈值 {threshold}，无需进化",
        )
    except Exception as e:
        logger.exception("evolution failed for %s", skill_id)
        raise HTTPException(status_code=500, detail=f"进化执行失败: {str(e)}")


# ── 可选 LLM 文本模型列表 ──────────────────────────────────────────────────────

class ChatModelItem(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None


@router.get("/chat-models", response_model=list[ChatModelItem])
def list_chat_models(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出系统已配置且可用的 LLM 文本模型（供进化选择）。

    过滤：类型 = 对话/文本（type=1），状态 = 启用（status=1）。
    """
    from app.models.ai.ai_api_key import AiChatModel
    rows = (
        db.query(AiChatModel)
        .filter(AiChatModel.type == 1, AiChatModel.status == 1)
        .order_by(AiChatModel.sort.desc().nullslast(), AiChatModel.id.asc())
        .all()
    )
    return [
        ChatModelItem(
            code=r.code or "",
            name=r.name,
            model=r.model,
            platform=r.platform,
        )
        for r in rows
    ]


# ── 版本管理 ─────────────────────────────────────────────────────────────────

@router.get("/{skill_id}/versions", response_model=list[VersionItem])
def list_versions(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出技能所有历史版本"""
    rows = db.query(AiSkillVersion).filter(
        AiSkillVersion.skill_id == skill_id
    ).order_by(AiSkillVersion.version_number.desc()).all()
    return [
        VersionItem(
            version_number=r.version_number,
            is_stable=r.is_stable,
            changes=r.changes,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.post("/{skill_id}/rollback")
def rollback_version(
    skill_id: str,
    version: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """回滚到指定版本"""
    try:
        from app.ai.skills.evolution.engine import SkillEvolutionEngine

        engine = SkillEvolutionEngine(db=db)
        engine.rollback(skill_id, version)
        return {"success": True, "message": f"已回滚到版本 {version}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("rollback failed for %s", skill_id)
        raise HTTPException(status_code=500, detail=f"回滚失败: {str(e)}")


# ── 进化日志 ─────────────────────────────────────────────────────────────────

@router.get("/{skill_id}/logs", response_model=list[EvolutionLogItem])
def list_evolution_logs(
    skill_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """查看进化日志"""
    rows = db.query(AiSkillEvolutionLog).filter(
        AiSkillEvolutionLog.skill_id == skill_id
    ).order_by(AiSkillEvolutionLog.created_at.desc()).limit(limit).all()
    return [
        EvolutionLogItem(
            id=r.id,
            skill_id=r.skill_id,
            from_version=r.from_version,
            to_version=r.to_version,
            trigger_type=r.trigger_type,
            result=r.result,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
