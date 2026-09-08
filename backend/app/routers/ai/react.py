"""ReAct HITL REST API — 暂停/恢复/确认/取消运行中的 ReAct 编排器。

通过 REACT_REGISTRY 全局注册表触达运行中的 ReActOrchestrator 实例，
提供 REST 端点供前端 HITL 面板调用。
"""
from fastapi import APIRouter, HTTPException

from app.schemas.agent.react_schemas import ReactRespondRequest

router = APIRouter(prefix="/react", tags=["ReAct HITL"])


def _get_orchestrator(run_id: str):
    """从全局注册表获取运行中的 ReActOrchestrator。"""
    from app.ai.react.orchestrator import REACT_REGISTRY

    orch = REACT_REGISTRY.get(run_id)
    if not orch:
        raise HTTPException(
            status_code=404,
            detail=f"ReAct 运行不存在或已结束: {run_id}",
        )
    return orch


@router.get("/{run_id}/status")
async def get_status(run_id: str):
    """获取当前执行状态和计划。"""
    orch = _get_orchestrator(run_id)
    return orch.get_status()


@router.post("/{run_id}/approve")
async def approve_plan(run_id: str):
    """批准计划（approve 模式）。"""
    orch = _get_orchestrator(run_id)
    orch.resume()
    return {"message": "计划已批准"}


@router.post("/{run_id}/respond")
async def respond(run_id: str, req: ReactRespondRequest):
    """响应确认请求（confirm_steps 模式）。"""
    orch = _get_orchestrator(run_id)
    if req.action == "cancel":
        orch.cancel()
        return {"message": "已取消"}
    if req.action == "skip":
        orch.resume(answer="__skip__")
        return {"message": "已跳过"}
    orch.resume(answer=req.answer)
    return {"message": "已确认"}


@router.post("/{run_id}/pause")
async def pause(run_id: str):
    """暂停执行。"""
    orch = _get_orchestrator(run_id)
    orch.request_pause()
    return {"message": "已暂停"}


@router.post("/{run_id}/resume")
async def resume(run_id: str):
    """恢复执行。"""
    orch = _get_orchestrator(run_id)
    orch.resume()
    return {"message": "已恢复"}


@router.post("/{run_id}/cancel")
async def cancel(run_id: str):
    """取消执行。"""
    orch = _get_orchestrator(run_id)
    orch.cancel()
    return {"message": "已取消"}
