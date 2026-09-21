"""实时语音 Provider 抽象基类。

定义 RealtimeProvider 接口和 ProviderEvent 数据模型。
所有语音服务供应商（DashScope/OpenAI/S2S）必须实现此接口。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

from app.duplex.voice.capabilities import ProviderCapabilities


@dataclass
class ProviderEvent:
    """Provider 产生的事件。"""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    capabilities: Optional[ProviderCapabilities] = None


class RealtimeProvider(ABC):
    """实时语音 Provider 抽象基类。"""

    key: str = ""
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000

    @abstractmethod
    async def connect(self, session_config: Dict[str, Any]) -> None:
        """建立与供应商的连接。"""

    @abstractmethod
    async def send_audio(self, pcm_data: bytes) -> None:
        """发送音频数据到供应商。"""

    @abstractmethod
    async def configure_session(self, **kwargs) -> None:
        """配置会话参数（instructions/tools/voice）。"""

    @abstractmethod
    async def events(self) -> AsyncGenerator[ProviderEvent, None]:
        """产出供应商事件流。"""
        yield ProviderEvent(type="")

    @abstractmethod
    async def close(self) -> None:
        """关闭连接。"""

    async def send_text(self, text: str) -> None:
        """向对端发送文本（文本模式 / 打断时）。默认 no-op，子类按需实现。"""
        return None

    async def interrupt(self) -> None:
        """请求打断当前回复（子类按需实现；默认 no-op 兼容测试桩）。"""
        return None

    async def resolve_confirm(self, confirm_id: str, approved: bool) -> None:
        """回传工具确认结果（子类按需实现）。"""
        return None

    def get_capabilities(self) -> ProviderCapabilities:
        """返回 Provider 能力声明（子类可覆盖）。"""
        return ProviderCapabilities()
