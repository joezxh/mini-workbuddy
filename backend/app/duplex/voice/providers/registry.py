"""Provider 注册表。

管理 RealtimeProvider 实现的注册和解析。
"""
from typing import Dict, Optional, Type

from loguru import logger

from app.duplex.voice.providers.base import RealtimeProvider


class ProviderRegistry:
    """Provider 注册表。"""

    _providers: Dict[str, Type[RealtimeProvider]] = {}
    _default_key: str = "dashscope"

    @classmethod
    def register(cls, provider_cls: Type[RealtimeProvider]) -> None:
        """注册一个 Provider 实现。"""
        if provider_cls.key is None:
            return
        cls._providers[provider_cls.key] = provider_cls
        logger.debug(f"ProviderRegistry: 注册 {provider_cls.key}")

    @classmethod
    def _ensure_defaults(cls) -> None:
        """惰性确保默认 Provider 已注册（幂等）。

        用于规避某些环境下 ProviderRegistry 模块被重复加载、
        导致默认注册未生效的问题（见测试跨目录运行时默认 Provider 丢失）。
        """
        if "dashscope" not in cls._providers:
            try:
                from app.duplex.voice.providers.dashscope import DashScopeProvider
                cls.register(DashScopeProvider)
            except Exception as e:  # noqa: BLE001 - 注册失败不应中断调用方
                logger.warning(f"默认 Provider dashscope 注册失败: {e}")
        if "local" not in cls._providers:
            try:
                from app.duplex.voice.providers.local import LocalProvider
                cls.register(LocalProvider)
            except Exception as e:  # noqa: BLE001 - 注册失败不应中断调用方
                logger.warning(f"本地回退 Provider local 注册失败: {e}")
        if "s2s" not in cls._providers:
            try:
                from app.duplex.voice.providers.s2s import S2SProvider
                cls.register(S2SProvider)
            except Exception as e:  # noqa: BLE001 - 注册失败不应中断调用方
                logger.warning(f"本地 S2S Provider 注册失败: {e}")

    @classmethod
    def resolve(cls, key: Optional[str] = None) -> RealtimeProvider:
        """解析 Provider 实例。"""
        key = key or cls._default_key
        provider_cls = cls._providers.get(key)
        if not provider_cls:
            raise ValueError(f"未知 Provider: {key}，已注册: {list(cls._providers.keys())}")
        return provider_cls()

    @classmethod
    def resolve_backup(cls, current: str) -> Optional[str]:
        """获取备选 Provider（降级用）。"""
        return {"dashscope": "openai", "openai": "dashscope"}.get(current)

    @classmethod
    def list_available(cls) -> list:
        """列出所有已注册的 Provider。"""
        return list(cls._providers.keys())

    @classmethod
    def is_configured(cls, key: str) -> bool:
        """Provider 是否已完成配置（用于降级选型）。

        未声明 `is_configured()` 的 Provider（如 dashscope）视为已配置。
        """
        provider_cls = cls._providers.get(key)
        if provider_cls is None:
            cls._ensure_defaults()  # 惰性补齐默认注册后再查
            provider_cls = cls._providers.get(key)
        if provider_cls is None:
            return False
        if not hasattr(provider_cls, "is_configured"):
            return True
        try:
            return bool(provider_cls().is_configured())
        except Exception as e:  # noqa: BLE001 - 探测失败视为未配置
            logger.warning(f"Provider {key} 配置探测失败: {e}")
            return False

    @classmethod
    def select(cls, preferred: str = None) -> str:
        """选择可用 Provider。

        优先 preferred；其未配置时回退到**默认 Provider**（而非任意已注册者，
        避免选中测试桩等临时注册项）；默认也不可用时才退而求其次。
        """
        cls._ensure_defaults()
        if preferred and cls.is_configured(preferred):
            return preferred
        if cls.is_configured(cls._default_key):
            if preferred:
                logger.warning(
                    f"Provider {preferred} 未配置，降级到默认 {cls._default_key}"
                )
            return cls._default_key
        for key in cls._providers:
            if cls.is_configured(key):
                logger.warning(f"默认 Provider 不可用，降级到 {key}")
                return key
        return cls._default_key


def _register_defaults() -> None:
    """默认注册存量 Provider（差距分析 §2：保留 DashScope）。

    延迟到模块尾部导入，避免与 dashscope 的 registry 反向导入形成循环。
    """
    from app.duplex.voice.providers.dashscope import DashScopeProvider
    ProviderRegistry.register(DashScopeProvider)


_register_defaults()


def get_provider(key: str) -> Type[RealtimeProvider]:
    """按 key 返回 Provider 类（不实例化）。"""
    ProviderRegistry._ensure_defaults()
    if key not in ProviderRegistry._providers:
        raise KeyError(f"unknown provider: {key}")
    return ProviderRegistry._providers[key]


def register_provider(key: str, cls: Type[RealtimeProvider]) -> None:
    """按 key 显式注册 Provider 类。"""
    ProviderRegistry._providers[key] = cls
