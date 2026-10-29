"""标准项服务（P2 Task 11，标准库维护）。

提供 ``MetaStandard`` 的租户安全 CRUD 与内置标准种子（``BUILTIN_STANDARDS``）。
标准项是规则引擎做字段绑定的「口径字典」。
"""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.dataops.rule_engine import BUILTIN_STANDARDS
from app.models.dataops.standard import MetaStandard
from app.services.dataops import alias_json


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
            aliases_json=alias_json.build(aliases),
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

    def update(self, standard_id: int, **fields: Any) -> MetaStandard:
        """更新标准项可编辑字段（None 值表示「不修改」）。

        :raises ValueError: 编码与其它标准项冲突
        """
        obj = self.get_or_404(standard_id)
        new_code = fields.get("code")
        if new_code is not None and new_code != obj.code:
            conflict = self.get_by_code(new_code)
            if conflict is not None and conflict.id != obj.id:
                raise ValueError(f"标准项编码已存在: {new_code}")
        for key, value in fields.items():
            if value is None:
                continue
            if key == "aliases":
                obj.aliases_json = alias_json.with_aliases(obj.aliases_json, value)
                continue
            setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, standard_id: int) -> None:
        """删除标准项（先解绑列级绑定；被对象/关系引用时拒绝）。

        :raises ValueError: 仍被对象标准引用，或被关系标准的连接键引用

        删除保护链对齐 spec §10：属性是全局字典，被引用时不允许静默删除，
        否则只能靠 DB 外键 RESTRICT 报 IntegrityError，前端拿不到可读原因。
        """
        obj = self.get_or_404(standard_id)
        from app.models.dataops.standard import MetaColumnStandard  # 局部导入避免循环依赖
        from app.models.dataops.standard_cdm import MetaObjectStandardAttribute

        ref_objects = self.db.execute(
            select(func.count()).select_from(MetaObjectStandardAttribute).where(
                MetaObjectStandardAttribute.tenant_id == self.tenant_id,
                MetaObjectStandardAttribute.standard_id == standard_id,
            )
        ).scalar_one()
        if ref_objects:
            raise ValueError(
                f"属性标准 {obj.code} 仍被 {ref_objects} 个对象标准引用，请先在对象中移除该属性"
            )
        rel_codes = self._relation_codes_using(standard_id)
        if rel_codes:
            shown = "、".join(rel_codes[:5])
            raise ValueError(
                f"属性标准 {obj.code} 仍被关系标准的连接键引用（{shown}），请先调整关系"
            )
        self.db.query(MetaColumnStandard).filter(
            MetaColumnStandard.standard_id == standard_id
        ).delete(synchronize_session=False)
        self.db.delete(obj)
        self.db.flush()

    def _relation_codes_using(self, standard_id: int) -> List[str]:
        """连接键（``via_attribute_ids`` JSONB 数组）引用了该属性的关系 code 列表。

        JSONB 包含查询在各方言下写法不一，这里按租户取回后比对；关系标准是
        人工维护的小集合，成本可接受且行为确定。
        """
        from app.models.dataops.standard_cdm import MetaObjectRelation

        rows = self.db.execute(
            select(MetaObjectRelation.code, MetaObjectRelation.via_attribute_ids).where(
                MetaObjectRelation.tenant_id == self.tenant_id
            )
        ).all()
        target = str(standard_id)
        return [code for code, ids in rows if target in {str(x) for x in (ids or [])}]

    def usage_counts(self) -> dict:
        """各属性标准的引用计数 ``{standard_id: {columns, objects, relations}}``。

        供「属性字典治理」视图识别孤儿属性与高耦合属性：列绑定 / 对象引用 /
        关系连接键三类引用分别计数，缺失的属性不出现（前端按 0 兜底）。
        """
        from app.models.dataops.standard import MetaColumnStandard
        from app.models.dataops.standard_cdm import (
            MetaObjectRelation, MetaObjectStandardAttribute,
        )

        counts: dict = {}

        def bump(standard_id: Any, key: str) -> None:
            row = counts.setdefault(int(standard_id), {"columns": 0, "objects": 0, "relations": 0})
            row[key] += 1

        for (sid,) in self.db.execute(
            select(MetaColumnStandard.standard_id).where(
                MetaColumnStandard.tenant_id == self.tenant_id
            )
        ).all():
            bump(sid, "columns")
        for (sid,) in self.db.execute(
            select(MetaObjectStandardAttribute.standard_id).where(
                MetaObjectStandardAttribute.tenant_id == self.tenant_id
            )
        ).all():
            bump(sid, "objects")
        for (ids,) in self.db.execute(
            select(MetaObjectRelation.via_attribute_ids).where(
                MetaObjectRelation.tenant_id == self.tenant_id
            )
        ).all():
            # 同一条关系重复引用同一属性只计一次
            for sid in {str(x) for x in (ids or [])}:
                if sid.isdigit():
                    bump(int(sid), "relations")
        return counts

    def seed_builtins(self, *, only_missing: bool = True) -> int:
        """按 ``BUILTIN_STANDARDS`` 为本租户播种标准项。

        :param only_missing: True 时仅插入尚不存在（同 code）的项，幂等；
            False 时全部重建（先清后插，被对象/关系引用时整体拒绝）。
        :return: 本次新建的标准项数量
        :raises ValueError: 重建时命中属性删除保护（被对象或关系引用）
        """
        if not only_missing:
            for existing in self.list_standards():
                self.delete(existing.id)
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
            "aliases": alias_json.aliases_list(s.aliases_json),
            "semantic_type": s.semantic_type,
            "security_level": s.security_level,
            "data_type_expect": s.data_type_expect,
            "domain": s.domain,
        }
