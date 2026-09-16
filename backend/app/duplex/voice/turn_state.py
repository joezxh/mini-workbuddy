"""轮次代际仲裁状态机（差距分析 §3.4.1 轮次状态机）。

在同一调解会话中，说话方（当事人 / 系统）会反复开始与结束发言。
当一次「助手续说」的音频帧在传输链路上晚于一次新的「当事人说话」
到达时，需要一个代际(generation)计数器来丢弃过期帧，避免把旧回答
播放到新语境里。

TurnState 是这一仲裁的纯状态原语，不依赖任何 I/O。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.duplex.voice.constants import VoiceState


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TurnState:
    """单次发言的状态与代际。"""

    turn_id: str = ""
    generation: int = 0
    voice_state: str = VoiceState.IDLE.value
    started_at: Optional[datetime] = None
    final_transcript: str = ""
    assistant_text: str = ""

    def mark_speaking(self) -> None:
        """助手续说：代际 +1 并进入 SPEAKING（覆盖任何旧代际）。"""
        self.generation += 1
        self.voice_state = VoiceState.SPEAKING.value

    def on_speech_started(self) -> None:
        """当事人开始说话：代际 +1 并进入 LISTENING。"""
        self.generation += 1
        self.voice_state = VoiceState.LISTENING.value

    def on_speech_stopped(self) -> None:
        self.voice_state = VoiceState.IDLE.value

    def on_audio_done(self) -> None:
        self.voice_state = VoiceState.IDLE.value

    def on_assistant_start(self) -> None:
        self.voice_state = VoiceState.PROCESSING.value

    def on_interrupt(self) -> None:
        """被打断：回到空闲，等待下一轮。"""
        self.voice_state = VoiceState.IDLE.value

    def reset_listening(self) -> None:
        """响应超时后回到聆听态（不推进代际，区别于 on_speech_started）。"""
        self.voice_state = VoiceState.LISTENING.value

    def is_stale(self, g: int) -> bool:
        """传入事件所属代际 g 小于当前代际 → 已过期，应丢弃。"""
        return self.generation > g

    def is_playing(self) -> bool:
        return self.voice_state == VoiceState.SPEAKING.value
