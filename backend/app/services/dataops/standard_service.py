"""标准项服务（P2 Task 11，标准库维护）。

提供 ``MetaStandard`` 的租户安全 CRUD 与内置标准种子（``BUILTIN_STANDARDS``）。
标准项是规则引擎做字段绑定的「口径字典」。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.dataops.rule_engine import BUILTIN_STANDARDS
from app.models.dataops.standard import MetaStandard


class MetaStandardService:
    """标准项读写（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaStandardService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def get_or_404(self, standard_id: int) -> MetaStandard:
        obj = self.db.execute(
            select(MetaStandard).where(
                MetaStandard.tenant_id == self.tenant_id, MetaStandard.id == standard_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise KeyError(standard_id)
        return obj

    def get_by_code(self, code: str) -> Optional[MetaStandard]:
        return self.db.execute(
            select(MetaStandard).where(
                MetaStandard.tenant_id == self.tenant_id, MetaStandard.code == code
            )
        ).scalar_one_or_none()

    def list_standards(self, status: Optional[str] = None) -> List[MetaStandard]:
        stmt = select(MetaStandard).where(MetaStandard.tenant_id == self.tenant_id)
        if status:
            stmt = stmt.where(MetaStandard.status == status)
        return list(self.db.execute(stmt.order_by(MetaStandard.code)).scalars().all())

    def create(
        self,
        code: str,
        name: str,
        *,
        aliases: Optional[list] = None,
        semantic_type: Optional[str] = None,
        security_level: Optional[str] = None,
        data_type_expect: Optional[str] = None,
        domain: Optional[str] = None,
        creator_id: Optional[int] = None,
    ) -> MetaStandard:
        if self.get_by_code(code) is not None:
            raise ValueError(f"标准项编码已存在: {code}")
        obj = MetaStandard(
            tenant_id=self.tenant_id,
            code=code,
            name=name,
            aliases_json=aliases or [],
            semantic_type=semantic_type,
            security_level=security_level,
            data_type_expect=data_type_expect,
            domain=domain,
            status="published",
            creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def seed_builtins(self, *, only_missing: bool = True) -> int:
        """按 ``BUILTIN_STANDARDS`` 为本租户播种标准项。

        :param only_missing: True 时仅插入尚不存在（同 code）的项，幂等；
            False 时全部重建（先清后插）。
        :return: 本次新建的标准项数量。
        """
        if not only_missing:
            for existing in self.list_standards():
                self.db.delete(existing)
            self.db.flush()
        created = 0
        for spec in BUILTIN_STANDARDS:
            if only_missing and self.get_by_code(spec["code"]) is not None:
                continue
            self.create(
                code=spec["code"],
                name=spec["name"],
                aliases=spec["aliases"],
                semantic_type=spec["semantic_type"],
                security_level=spec["security_level"],
                data_type_expect=spec.get("data_type_expect") or None,
                domain=spec.get("domain"),
            )
            created += 1
        return created

    @staticmethod
    def serialize(s: MetaStandard) -> dict:
        """序列化为规则引擎可消费的字典（含 id，供绑定回写）。"""
        return {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "aliases": s.aliases_json or [],
            "semantic_type": s.semantic_type,
            "security_level": s.security_level,
            "data_type_expect": s.data_type_expect,
            "domain": s.domain,
        }
