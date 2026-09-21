"""语音通信层枚举常量（禁止裸字符串）。"""
from enum import Enum


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class EventType(str, Enum):
    CONNECT = "connect"
    VOICE_READY = "voice.ready"
    VOICE_STATE = "voice.state"
    VOICE_OWNERSHIP = "voice.ownership"
    TURN_STARTED = "turn.started"
    AUDIO_APPEND = "audio.append"
    AUDIO_DELTA = "audio.delta"
    AUDIO_DONE = "audio.done"
    INPUT_MESSAGE = "input.message"
    INPUT_MUTE = "input.mute"
    INPUT_UNMUTE = "input.unmute"
    OUTPUT_MODE = "output.mode"
    INTERRUPT = "interrupt"
    RESPONSE_STARTED = "response.started"
    RESPONSE_INTERRUPTED = "response.interrupted"
    PLAYBACK_STARTED = "playback.started"
    PLAYBACK_ENDED = "playback.ended"
    PLAYBACK_CANCELLED = "playback.cancelled"
    PLAYBACK_CLEAR = "playback.clear"
    TRANSCRIPT_DELTA = "transcript.delta"
    TRANSCRIPT_FINAL = "transcript.final"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    # 扩展（D6 冻结）
    EXPERT_JOIN = "expert.join"
    EXPERT_LEAVE = "expert.leave"
    AGENT_ACTIVITY = "agent.activity"
    INSIGHT_DELTA = "insight.delta"
    RESPONSE_REQUEST = "response.request"
    PARTICIPANT_JOINED = "participant.joined"
    PARTICIPANT_LEFT = "participant.left"


class ProviderKey(str, Enum):
    DASHSCOPE = "dashscope"
    OPENAI = "openai"


class ErrorCode(str, Enum):
    INACTIVITY = "inactivity"
    INPUT_BUSY = "input_busy"
    FATAL = "fatal"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    OTHER = "other"
