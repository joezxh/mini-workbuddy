"""方言注册表：按 data_source.source_type 分派适配器（P2 Task 3）。"""
from __future__ import annotations

from typing import Callable, Dict

from app.ai.dataops.dialect_base import DialectAdapter

_ADAPTER_FACTORIES: Dict[str, Callable[[], DialectAdapter]] = {}


def register_adapter(source_type: str, factory: Callable[[], DialectAdapter]) -> None:
    """注册适配器工厂（模块导入时自注册；测试可覆盖）。"""
    _ADAPTER_FACTORIES[source_type.lower().strip()] = factory


def get_adapter(source_type: str) -> DialectAdapter:
    """按 source_type 构造适配器；未知类型显式失败（不静默降级）。"""
    key = (source_type or "").lower().strip()
    factory = _ADAPTER_FACTORIES.get(key)
    if factory is None:
        raise ValueError(
            f"不支持的数据源类型 {source_type!r}（尚未实现或不存在），已注册："
            f"{', '.join(sorted(_ADAPTER_FACTORIES))}"
        )
    return factory()


def is_registered(source_type: str) -> bool:
    """适配器是否已注册（保存前的能力门禁：字典启用 ≠ 驱动已实现）。"""
    return (source_type or "").lower().strip() in _ADAPTER_FACTORIES


def _register_builtins() -> None:
    from app.ai.dataops.dialects.clickhouse import ClickhouseAdapter
    from app.ai.dataops.dialects.dm import DmAdapter
    from app.ai.dataops.dialects.doris import DorisAdapter
    from app.ai.dataops.dialects.es import EsAdapter
    from app.ai.dataops.dialects.excel_pg import ExcelPgAdapter
    from app.ai.dataops.dialects.kingbase import KingbaseAdapter
    from app.ai.dataops.dialects.mysql import MysqlAdapter
    from app.ai.dataops.dialects.oracle import OracleAdapter
    from app.ai.dataops.dialects.postgres import PostgresAdapter
    from app.ai.dataops.dialects.sqlserver import SqlserverAdapter
    from app.ai.dataops.dialects.starrocks import StarrocksAdapter

    register_adapter("postgresql", PostgresAdapter)
    register_adapter("kingbase", KingbaseAdapter)      # PG 协议兼容子类
    register_adapter("mysql", MysqlAdapter)
    register_adapter("doris", DorisAdapter)
    register_adapter("starrocks", StarrocksAdapter)    # MySQL 协议兼容子类
    register_adapter("oracle", OracleAdapter)
    register_adapter("sqlserver", SqlserverAdapter)
    register_adapter("clickhouse", ClickhouseAdapter)
    register_adapter("dm", DmAdapter)
    register_adapter("es", EsAdapter)
    register_adapter("excel", ExcelPgAdapter)


_register_builtins()
