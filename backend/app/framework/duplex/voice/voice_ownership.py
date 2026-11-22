"""语音所有权仲裁（谁当前持有麦克风/发言权）。

调解场景下可能有多个当事人端同时连接，需要明确「当前哪一方在说话」，
避免多方音频同时写入同一会话造成混乱。VoiceOwnership 提供授予/撤销/
查询能力。
"""
from typing import Optional


class VoiceOwnership:
    def __init__(self):
        self._holder: Optional[str] = None
        self._turn_id: Optional[str] = None

    def grant(self, party_id: str, turn_id: Optional[str] = None) -> None:
        self._holder = party_id
        self._turn_id = turn_id

    def current(self) -> Optional[str]:
        return self._holder

    def revoke(self, party_id: str) -> bool:
        if self._holder == party_id:
            self._holder = None
            self._turn_id = None
            return True
        return False

    def is_granted(self, party_id: str) -> bool:
        return self._holder == party_id
