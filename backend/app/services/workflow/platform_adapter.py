"""平台适配器抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PlatformResponse:
    """适配器统一输出"""
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0
    platform_trace: Optional[Dict[str, Any]] = None


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    def __init__(self, base_url: str, api_key: str, config: Optional[Dict] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    async def invoke(
        self,
        flow_type: str,
        inputs: Dict[str, Any],
        user_id: str,
        timeout: float = 600.0,
        **kwargs,
    ) -> PlatformResponse:
        """调用平台 API"""

    @abstractmethod
    def extract_output(self, result: Dict[str, Any], flow_type: str) -> str:
        """从平台响应中提取最终文本"""

    async def health_check(self) -> bool:
        """平台连通性检查（可选实现）"""
        return True
