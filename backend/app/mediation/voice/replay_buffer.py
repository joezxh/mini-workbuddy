"""事件重放缓冲（网关内）：断线重连时回放遗漏的下行帧。

客户端断线重连后，可能错过重连期间产生的 transcript / turn 等状态帧。
按调解会话（session_id）维护一个有界缓冲，重连时先回放缓冲帧再接入实时流。
（音频 PCM 二进制帧不缓冲，仅缓冲可 JSON 序列化的状态帧。）
"""
from collections import deque
from typing import Dict, List


class ReplayBuffer:
    def __init__(self, maxlen: int = 200):
        self._buf: deque = deque(maxlen=maxlen)

    def push(self, frame: dict) -> None:
        self._buf.append(frame)

    def drain(self) -> List[dict]:
        frames = list(self._buf)
        self._buf.clear()
        return frames

    def __len__(self) -> int:
        return len(self._buf)


# 按调解会话 session_id 维护重放缓冲（跨 WS 连接共享）
SESSION_REPLAY_BUFFERS: Dict[str, ReplayBuffer] = {}
