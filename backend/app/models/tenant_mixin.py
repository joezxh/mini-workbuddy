"""所有需要租户隔离的 ORM 模型继承此 Mixin。"""
from sqlalchemy import Column, BigInteger


class TenantMixin:
    """为模型添加 tenant_id 列，用于行级多租户隔离。

    用法：
        class MyModel(Base, TenantMixin):
            __tablename__ = "my_table"
            id = Column(BigInteger, primary_key=True)
            # tenant_id 自动继承
    """
    tenant_id = Column(BigInteger, nullable=True, index=True, comment="租户ID")
