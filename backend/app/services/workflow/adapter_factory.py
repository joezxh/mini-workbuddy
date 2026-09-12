"""适配器工厂 — 支持运行时注册"""
from typing import Dict, Optional, Type

from app.services.workflow.platform_adapter import PlatformAdapter
from app.services.workflow.adapters.dify_adapter import DifyAdapter
from app.services.workflow.adapters.coze_adapter import CozeAdapter
from app.services.workflow.adapters.custom_adapter import CustomHTTPAdapter


class AdapterFactory:
    """适配器工厂"""

    _registry: Dict[str, Type[PlatformAdapter]] = {
        "dify": DifyAdapter,
        "coze": CozeAdapter,
        "custom_http": CustomHTTPAdapter,
    }

    @classmethod
    def create(cls, platform_type: str, base_url: str, api_key: str,
               config: Optional[Dict] = None) -> PlatformAdapter:
        adapter_cls = cls._registry.get(platform_type)
        if not adapter_cls:
            raise ValueError(f"不支持的平台类型: {platform_type}，已注册: {list(cls._registry.keys())}")
        return adapter_cls(base_url=base_url, api_key=api_key, config=config)

    @classmethod
    def register(cls, platform_type: str, adapter_cls: Type[PlatformAdapter]):
        """运行时注册新适配器"""
        cls._registry[platform_type] = adapter_cls

    @classmethod
    def list_platforms(cls):
        return list(cls._registry.keys())
