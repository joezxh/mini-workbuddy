"""kb_ref 服务（P1 Task 9）：租户侧 KB 注册表，映射到 AgentScope user_id。

kb_ref 是 MWB 侧对「知识库」的登记：每个租户可登记若干 KB，每个 KB 映射到
AgentScope RAG Service 的一个 ``user_id`` 命名空间（由 ``UserIdMapper`` 生成）。
所有读写强制按 tenant_id 隔离（纵深防御，P1 Task 6）。
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb.kb_ref import KbRef
from app.services.kb.user_id_mapper import to_as_user_id


class KbRefService:
    """kb_ref 行级服务：以 tenant_id 为隔离边界操作 KB 登记。"""

    def __init__(self, db: Session, tenant_id: int) -> None:
        if tenant_id is None:
            raise ValueError("KbRefService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def create_kb_ref(
        self,
        name: str,
        description: Optional[str] = None,
        creator_id: Optional[int] = None,
    ) -> KbRef:
        obj = KbRef(
            tenant_id=self.tenant_id,
            kb_id=uuid.uuid4().hex,
            name=name,
            description=description,
            as_user_id=to_as_user_id(self.tenant_id),
            creator_id=creator_id,
            doc_count=0,
            segment_count=0,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_kb_refs(self) -> List[KbRef]:
        return list(
            self.db.execute(
                select(KbRef)
                .where(KbRef.tenant_id == self.tenant_id)
                .order_by(KbRef.name)
            )
            .scalars()
            .all()
        )

    def get_kb_ref(self, kb_id: str) -> Optional[KbRef]:
        return self.db.execute(
            select(KbRef).where(
                KbRef.tenant_id == self.tenant_id, KbRef.kb_id == kb_id
            )
        ).scalar_one_or_none()

    def delete_kb_ref(self, kb_id: str) -> bool:
        obj = self.get_kb_ref(kb_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True

    def update_counts(self, kb_id: str, doc_count: int, segment_count: int) -> Optional[KbRef]:
        obj = self.get_kb_ref(kb_id)
        if obj is None:
            return None
        obj.doc_count = doc_count
        obj.segment_count = segment_count
        self.db.flush()
        return obj
