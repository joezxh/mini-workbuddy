"""连接器注册表（P3 Task 1）：按 connector_type 分派工厂。

与 dataops 方言注册表 / tool 注册表同构：模块导入时自注册；未知类型显式失败。
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from app.connectors.base import BaseConnector, ConnectorConfig


_FACTORIES: Dict[str, Callable[[ConnectorConfig], BaseConnector]] = {}


def register_connector(connector_type: str, factory: Callable[[ConnectorConfig], BaseConnector]) -> None:
    _FACTORIES[connector_type.lower().strip()] = factory


def get_connector(connector_type: str, config: ConnectorConfig) -> BaseConnector:
    key = (connector_type or "").lower().strip()
    factory = _FACTORIES.get(key)
    if factory is None:
        raise ValueError(
            f"不支持的连接器类型 {connector_type!r}（尚未实现或不存在），已注册："
            f"{', '.join(sorted(_FACTORIES))}"
        )
    return factory(config)


def _register_builtins() -> None:
    from app.connectors.http import HttpConnector
    from app.connectors.types.dingtalk import DingtalkConnector
    from app.connectors.types.feishu import FeishuConnector
    from app.connectors.types.wecom import WeComConnector

    register_connector("http", HttpConnector)
    register_connector("dingtalk", DingtalkConnector)
    register_connector("feishu", FeishuConnector)
    register_connector("wecom", WeComConnector)


_register_builtins()
