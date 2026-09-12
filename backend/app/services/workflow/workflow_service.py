"""工作流 CRUD 服务"""
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.workflow.workflow_flow import WorkflowFlow
from app.models.workflow.workflow_execution_log import WorkflowExecutionLog
from app.models.workflow.workflow_chain import WorkflowChain
from app.services.workflow.crypto import encrypt_api_key


class WorkflowService:
    """工作流管理服务"""

    # ── Flow CRUD ────────────────────────────────────────────

    def list_flows(self, db: Session, tenant_id: Optional[int] = None,
                   platform_type: Optional[str] = None, flow_type: Optional[str] = None,
                   is_active: Optional[bool] = None,
                   page: int = 1, page_size: int = 20) -> Tuple[int, List[WorkflowFlow]]:
        q = select(WorkflowFlow).where(WorkflowFlow.is_deleted == False)
        if tenant_id:
            q = q.where(WorkflowFlow.tenant_id == tenant_id)
        if platform_type:
            q = q.where(WorkflowFlow.platform_type == platform_type)
        if flow_type:
            q = q.where(WorkflowFlow.flow_type == flow_type)
        if is_active is not None:
            q = q.where(WorkflowFlow.is_active == is_active)

        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = q.order_by(WorkflowFlow.sort_order, WorkflowFlow.id)
        q = q.offset((page - 1) * page_size).limit(page_size)
        return total, list(db.scalars(q).all())

    def get_flow(self, db: Session, flow_id: int) -> Optional[WorkflowFlow]:
        return db.scalars(select(WorkflowFlow).where(
            WorkflowFlow.id == flow_id, WorkflowFlow.is_deleted == False
        )).first()

    def create_flow(self, db: Session, data: dict) -> WorkflowFlow:
        api_key_plain = data.pop("api_key")
        data["api_key_enc"] = encrypt_api_key(api_key_plain)
        flow = WorkflowFlow(**data)
        db.add(flow)
        db.flush()
        return flow

    def update_flow(self, db: Session, flow: WorkflowFlow, data: dict) -> WorkflowFlow:
        api_key = data.pop("api_key", None)
        for k, v in data.items():
            if v is not None:
                setattr(flow, k, v)
        if api_key:
            flow.api_key_enc = encrypt_api_key(api_key)
        db.flush()
        return flow

    def delete_flow(self, db: Session, flow: WorkflowFlow):
        flow.is_deleted = True
        db.flush()

    # ── Execution Log ────────────────────────────────────────

    def list_executions(self, db: Session, flow_id: Optional[int] = None,
                        status: Optional[str] = None,
                        page: int = 1, page_size: int = 20) -> Tuple[int, List[WorkflowExecutionLog]]:
        q = select(WorkflowExecutionLog)
        if flow_id:
            q = q.where(WorkflowExecutionLog.flow_id == flow_id)
        if status:
            q = q.where(WorkflowExecutionLog.status == status)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = q.order_by(WorkflowExecutionLog.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        return total, list(db.scalars(q).all())

    # ── Chain CRUD ───────────────────────────────────────────

    def list_chains(self, db: Session, tenant_id: Optional[int] = None,
                    page: int = 1, page_size: int = 20) -> Tuple[int, List[WorkflowChain]]:
        q = select(WorkflowChain).where(WorkflowChain.is_deleted == False)
        if tenant_id:
            q = q.where(WorkflowChain.tenant_id == tenant_id)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = q.order_by(WorkflowChain.id.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        return total, list(db.scalars(q).all())

    def create_chain(self, db: Session, data: dict) -> WorkflowChain:
        chain = WorkflowChain(**data)
        db.add(chain)
        db.flush()
        return chain

    def update_chain(self, db: Session, chain: WorkflowChain, data: dict) -> WorkflowChain:
        for k, v in data.items():
            if v is not None:
                setattr(chain, k, v)
        db.flush()
        return chain

    def delete_chain(self, db: Session, chain: WorkflowChain):
        chain.is_deleted = True
        db.flush()
