"""数据源管理服务（P2 Task 2）：CRUD + 凭据加密 + 租户隔离。

凭据规则（spec 7.1）：
- 密码只在创建/更新时经 encrypt_secret 加密落库；
- API 响应永不返回密码，只回 has_password；
- reveal_password 仅供方言适配器建连接使用（Task 3），绝不走 API 出口。

更新语义：password 传 None/空串表示不改；source_type 不可改（避免
凭据/方言语义错位），需重建数据源。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.dataops.crypto import decrypt_secret, encrypt_secret
from app.models.dataops.data_source import DataSource

SUPPORTED_SOURCE_TYPES = ("mysql", "doris", "postgresql")

_UPDATABLE_FIELDS = (
    "name", "host", "port", "username", "database", "charset",
    "is_default", "status", "updater_id",
)


class DataSourceService:
    """数据源 CRUD（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("DataSourceService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    @staticmethod
    def validate_source_type(source_type: str) -> str:
        t = (source_type or "").lower().strip()
        if t not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(
                f"不支持的数据源类型 {source_type!r}，可选：{', '.join(SUPPORTED_SOURCE_TYPES)}"
            )
        return t

    def create(
        self,
        name: str,
        source_type: str,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        charset: str = "utf8mb4",
        is_default: bool = False,
        creator_id: Optional[int] = None,
    ) -> DataSource:
        t = self.validate_source_type(source_type)
        if not (name or "").strip():
            raise ValueError("数据源名称不能为空")
        obj = DataSource(
            tenant_id=self.tenant_id,
            name=name.strip(),
            source_type=t,
            host=host,
            port=int(port),
            username=username,
            password_enc=encrypt_secret(password) if password else None,
            database=database,
            charset=charset or "utf8mb4",
            is_default=bool(is_default),
            creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        if obj.is_default:
            self._clear_other_defaults(obj.id)
        return obj

    def list_sources(self) -> List[DataSource]:
        return list(
            self.db.execute(
                select(DataSource)
                .where(DataSource.tenant_id == self.tenant_id)
                .order_by(DataSource.id)
            )
            .scalars()
            .all()
        )

    def get(self, source_id: int) -> Optional[DataSource]:
        return self.db.execute(
            select(DataSource).where(
                DataSource.tenant_id == self.tenant_id,
                DataSource.id == source_id,
            )
        ).scalar_one_or_none()

    def get_or_404(self, source_id: int) -> DataSource:
        obj = self.get(source_id)
        if obj is None:
            raise KeyError(source_id)
        return obj


    def update(self, source_id: int, updater_id: Optional[int] = None, **fields) -> DataSource:
        """部分更新；password=None/空串表示不改；source_type 不可改。"""
        obj = self.get_or_404(source_id)
        fields.pop("source_type", None)
        if "password" in fields:
            pwd = fields.pop("password")
            if pwd:
                obj.password_enc = encrypt_secret(pwd)
        for key, value in fields.items():
            if value is None or key not in _UPDATABLE_FIELDS:
                continue
            if key == "name" and not str(value).strip():
                raise ValueError("数据源名称不能为空")
            setattr(obj, key, value)
        obj.updater_id = updater_id
        self.db.flush()
        if obj.is_default:
            self._clear_other_defaults(obj.id)
        return obj

    def delete(self, source_id: int) -> bool:
        """删除数据源（级联删除扫描任务与元数据快照）；不存在返回 False。"""
        obj = self.get(source_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True

    def reveal_password(self, source_id: int) -> Optional[str]:
        """解密密码（仅供建连接：方言适配器/探活），严禁出现在 API 响应里。"""
        obj = self.get_or_404(source_id)
        if not obj.password_enc:
            return None
        return decrypt_secret(obj.password_enc)

    def _clear_other_defaults(self, keep_id: int) -> None:
        """is_default 互斥：同租户内只保留一个默认数据源。"""
        for other in self.list_sources():
            if other.id != keep_id and other.is_default:
                other.is_default = False
        self.db.flush()

    @staticmethod
    def to_dict(obj: DataSource) -> dict:
        """API 出口：绝不包含 password_enc，只回 has_password。"""
        return {
            "id": obj.id,
            "name": obj.name,
            "source_type": obj.source_type,
            "host": obj.host,
            "port": obj.port,
            "username": obj.username,
            "database": obj.database,
            "charset": obj.charset,
            "status": obj.status,
            "is_default": bool(obj.is_default),
            "has_password": bool(obj.password_enc),
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }
