"""数据源管理服务（P2 Task 2；类型体系扩展后改为字典驱动）。

凭据规则（spec 7.1）：
- 密码只在创建/更新时经 encrypt_secret 加密落库；
- API 响应永不返回密码，只回 has_password；
- reveal_password 仅供方言适配器建连接使用（Task 3），绝不走 API 出口。

类型合法性（字典驱动）：
- 取值以 ``sys_dictionary_item``（dict_code=data_source_type，启用且未删除）为准；
- 字典为空/不可用时退回内置种子（source_types.builtin_types，仿 skills/categories 降级）；
- 类型已启用但适配器未注册 → 拒绝保存（避免建立不可用数据源）。

更新语义：password 传 None/空串表示不改；source_type 不可改（避免
凭据/方言语义错位），需重建数据源。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.dataops.crypto import decrypt_secret, encrypt_secret
from app.ai.dataops.dialects.registry import is_registered
from app.models.dataops.data_source import DataSource
from app.models.sys.sys_dictionary import SysDictionaryItem
from app.services.dataops import source_types as st

SUPPORTED_SOURCE_TYPES = tuple(st.builtin_types())  # 内置种子（兼容旧引用）；合法集以字典为准

_UPDATABLE_FIELDS = (
    "name", "host", "port", "username", "database", "charset", "config_json",
    "is_default", "status", "updater_id",
)

#: config_json 中禁止出现的键（凭据必须走 password 字段加密链路）
_CONFIG_FORBIDDEN_KEYS = {"password", "pwd", "token", "secret"}


def enabled_types(db: Session, tenant_id: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
    """字典启用项 {item_code: 元数据}；字典无数据时退回内置种子。

    元数据 = {item_name, color, sort, family, default_port, fields}；family/
    default_port/fields 取自 extra_data，缺失时按内置种子补齐。
    """
    query: List[SysDictionaryItem] = []
    try:
        query = list(db.execute(
            select(SysDictionaryItem).where(
                SysDictionaryItem.dict_code == st.DICT_CODE_DATA_SOURCE_TYPE,
                SysDictionaryItem.is_active == True,   # noqa: E712
                SysDictionaryItem.is_deleted == False,  # noqa: E712
                or_(SysDictionaryItem.tenant_id == tenant_id, SysDictionaryItem.tenant_id.is_(None))
                if tenant_id is not None else SysDictionaryItem.tenant_id.is_(None),
            ).order_by(SysDictionaryItem.sort_order, SysDictionaryItem.item_id)
        ).scalars().all())
    except Exception:  # noqa: BLE001 - 字典表不存在/不可查：退回内置种子（仿 skills/categories 降级）
        db.rollback()
        query = []
    result: Dict[str, Dict[str, Any]] = {}
    for it in query:
        extra = it.extra_data or {}
        base = st.meta_for(it.item_code) or {}
        result[it.item_code] = {
            "item_name": it.item_name,
            "color": it.color,
            "sort": it.sort_order or 0,
            "family": extra.get("family") or base.get("family"),
            "default_port": extra.get("default_port", base.get("default_port")),
            "fields": extra.get("fields") or base.get("fields") or [],
        }
    if result:
        return result
    # 降级：字典表未 seed / 查询无结果时用内置种子，避免所有保存被拒
    for code, meta in st.TYPE_META.items():
        result[code] = {
            "item_name": meta["item_name"], "color": meta.get("color"), "sort": meta.get("sort", 0),
            "family": meta["family"], "default_port": meta.get("default_port"),
            "fields": meta.get("fields", []),
        }
    return result


class DataSourceService:
    """数据源 CRUD（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("DataSourceService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    @staticmethod
    def validate_source_type(source_type: str, db: Optional[Session] = None,
                             tenant_id: Optional[int] = None) -> str:
        """字典驱动校验：有会话时以字典启用项为准，否则退回内置种子。

        额外要求适配器已注册（字典配了但驱动未开发 → 拒绝，错误信息区分两种情形）。
        """
        t = (source_type or "").lower().strip()
        allowed = enabled_types(db, tenant_id) if db is not None else {
            c: {} for c in st.builtin_types()
        }
        if t not in allowed:
            raise ValueError(
                f"数据源类型 {source_type!r} 未在数据字典中启用（data_source_type），"
                f"可选：{', '.join(sorted(allowed)) or '（字典为空）'}"
            )
        if not is_registered(t):
            raise ValueError(f"数据源类型 {t} 的方言适配器尚未实现，无法保存")
        return t

    @staticmethod
    def validate_config(source_type: str, config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """清洗类型特有参数：拒绝凭据类键（密码必须走加密字段）；None 原样返回。"""
        if config is None:
            return None
        if not isinstance(config, dict):
            raise ValueError("config 必须为 JSON 对象")
        for key in config:
            if str(key).lower() in _CONFIG_FORBIDDEN_KEYS or str(key).lower().endswith("password"):
                raise ValueError(f"config 不允许包含凭据字段 {key!r}，密码请填入 password 参数")
        return dict(config)

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
        config: Optional[Dict[str, Any]] = None,
    ) -> DataSource:
        t = self.validate_source_type(source_type, self.db, self.tenant_id)
        if not (name or "").strip():
            raise ValueError("数据源名称不能为空")
        # excel（文件上传落库）型无真实主机/端口：落占位值，其余类型严格校验
        if (st.meta_for(t) or {}).get("family") == "excel":
            host, port = (host or "").strip(), int(port or 0)
        else:
            if not (host or "").strip():
                raise ValueError("主机地址不能为空")
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError(f"端口非法：{port}")
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
            config_json=self.validate_config(t, config),
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
        if "config" in fields:
            fields["config_json"] = self.validate_config(obj.source_type, fields.pop("config"))
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
            "config": obj.config_json or {},
            "status": obj.status,
            "is_default": bool(obj.is_default),
            "has_password": bool(obj.password_enc),
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }
