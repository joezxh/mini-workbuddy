# 调解全双工语音通信层（主应用内嵌）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在主应用 `risk_control` 内嵌实现一套全双工语音+文字双模调解通信层，复用存量 `app/mediation/voice/`、`app/ai/*` 与调解域表，提供实时字幕、打断、断线重放、双 Provider 切换与生产就绪可观测性。

**Architecture:** 语音模块原位增强于 `app/mediation/voice/`，经 FastAPI WebSocket `/mediation/voice/ws` 提供服务；会话状态机、代际打断仲裁、Provider 抽象与协议适配器构成通信内核；`AgentAdapter` 进程内调用现有 `app/ai` 推理与 MCP 资产；2 张语音域表 + 3 张配置表经 `init_models.py` 登记直写。前端 Vue3 新增语音房间组件树，复用 `views/mediation/` 与 `views/admin/ai/`。

**Tech Stack:** Python 3.10 + FastAPI + WebSockets + SQLAlchemy 2.0 + PostgreSQL + Redis；Vue3 + Web Audio API；AgentScope 2.0.8dev（已含 Plan 工具）。M4 新增 `funasr`/`CosyVoice2`/`onnxruntime`。

**前置约定（务必遵守）：**
- 所有新增 ORM model **必须**在 `app/db/init_models.py` 登记（AGENTS.md 强制约定）。
- 状态/事件类型用 `constants.py` 枚举，禁止裸字符串（AGENTS.md 约定）。
- 直接在 async 代码里用 `from app.db.database import SessionLocal` 开会话，不要用 `get_db` 生成器依赖。
- 现有 `mediation_session.id` 是 **BigInteger**，因此 `mediation_voice_session.mediation_session_id` 必须是 BigInteger 外键（设计文档 v3 §9.1 误写为 UUID，本计划已修正）。`mediation_voice_session.id` 自身用 `String(36)` 存 uuid（跨 dialect 兼容，便于单测）。

---

## File Structure（锁定分解）

```
backend/app/
├── models/
│   ├── mediation_voice_session.py        # NEW M1  ORM (String(36) PK)
│   └── mediation_voice_turn.py           # NEW M1  ORM (BigInt PK, FK→voice_session)
├── schemas/mediation/
│   └── voice.py                          # NEW M1  VoiceConnectConfig + 响应模型
├── services/mediation/
│   ├── voice_session_service.py          # NEW M1  生命周期
│   └── voice_turn_service.py             # NEW M1  轮次 + §9.2 业务同步
├── mediation/voice/
│   ├── constants.py                      # NEW M1  事件/状态枚举
│   ├── audio_codec.py                    # NEW M1  重采样/PCM16/Base64
│   ├── capabilities.py                   # NEW M2  ProviderCapabilities
│   ├── turn_state.py                     # NEW M2  代际仲裁
│   ├── reconnect_backoff.py              # NEW M2  退避 + classifyError
│   ├── protocol_adapter.py               # NEW M2  OpenAI 兼容归一化
│   ├── agent_adapter.py                  # NEW M1  AgentAdapter + 3 实现
│   ├── mcp_session_resolver.py           # NEW M1  会话级 MCP 注入
│   ├── tool_call_handler.py              # NEW M2  参数校验/策略
│   ├── voice_ownership.py                # NEW M2  多方预留骨架
│   ├── websocket_gateway.py              # MODIFY M1-M2 协议 v2 + JWT + 状态机
│   ├── fallback.py                       # MODIFY M2  错误分类+退避+超时
│   └── providers/
│       ├── base.py                       # MODIFY M2  +capabilities/+is_configured
│       ├── dashscope.py                  # MODIFY M2  适配器化
│       ├── registry.py                   # MODIFY M3  实例注册+validate+is_configured
│       ├── protocol_adapter re-use       #   (用 mediation/voice/protocol_adapter.py)
│       └── local_provider.py             # NEW M2(mock)→M4(real)
├── db/init_models.py                     # MODIFY M1  登记 2 模型
├── core/config.py                        # MODIFY M1  语音配置项
├── routers/                             # MODIFY M3  admin 配置端点（含 3 组 CRUD）
└── alembic/versions/xxx_add_voice_tables.py  # NEW M1 迁移(5 表)

backend/tests/
├── unit/test_voice_constants.py          # TDD M1
├── unit/test_voice_audio_codec.py        # TDD M1
├── unit/test_voice_turn_state.py         # TDD M2
├── unit/test_voice_reconnect_backoff.py  # TDD M2
├── unit/test_voice_protocol_adapter.py   # TDD M2
├── unit/test_voice_capabilities.py       # TDD M2
├── unit/test_voice_services.py           # TDD M1 (fake adapter)
└── gateway/test_voice_ws.py              # TDD M1-M2 (TestClient WS loopback)

frontend/src/
├── composables/useMediationVoice.js      # NEW M2
├── composables/useMicrophoneCapture.js   # NEW M2
├── composables/useAudioPlayback.js       # NEW M2
├── views/mediation/MediationVoiceRoom.vue            # NEW M2
├── views/mediation/components/VoiceStatusBar.vue     # NEW M2
├── views/mediation/components/TranscriptPanel.vue    # NEW M2
├── views/mediation/components/VoiceControlBar.vue    # NEW M2
├── views/admin/ai-config/agents/AgentConfigPanel.vue      # NEW M3
├── views/admin/mediation/config/VoiceSessionConfig.vue     # NEW M3
├── views/admin/ai/components/ToolPolicyEditor.vue          # NEW M3
└── (修改) views/mediation/MediationPartyView.vue + 路由 + api 封装  # M2/M3
```

> 每任务对应上面一个文件或一组文件，提交粒度见各任务 Step5。

---

## Milestone 1 — 基础能力（约 1 周）

目标：协议 v2 落地、connect 帧驱动、2 张表 + 服务层、AgentAdapter 三实现（AgentScope 默认）、DashScope 直连跑通 loopback 回声。

### Task 1: `constants.py` 事件/状态枚举

**Files:** Create `backend/app/mediation/voice/constants.py`
**Test:** Create `backend/tests/unit/test_voice_constants.py`

- [ ] **Step 1: Write the failing test**
```python
from app.mediation.voice.constants import VoiceState, EventType, ProviderKey, ErrorCode

def test_voice_state_values():
    assert VoiceState.LISTENING == "listening"
    assert VoiceState.PROCESSING == "processing"
    assert VoiceState.SPEAKING == "speaking"

def test_event_type_members_present():
    for e in ["connect", "voice_ready", "voice_state", "turn_started",
              "audio_delta", "audio_done", "transcript_delta", "transcript_final",
              "interrupt", "playback_clear", "error", "pong"]:
        assert hasattr(EventType, e.upper())

def test_provider_key_and_error_code():
    assert ProviderKey.DASHSCOPE == "dashscope"
    assert ErrorCode.PROVIDER_UNAVAILABLE == "provider_unavailable"
    assert ErrorCode.FATAL == "fatal"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `cd backend && python -m pytest tests/unit/test_voice_constants.py -v`
Expected: FAIL — `ModuleNotFoundError: app.mediation.voice.constants`

- [ ] **Step 3: Write minimal implementation**
```python
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
    LOCAL = "local"


class ErrorCode(str, Enum):
    INACTIVITY = "inactivity"
    INPUT_BUSY = "input_busy"
    FATAL = "fatal"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    OTHER = "other"
```

- [ ] **Step 4: Run test to verify it passes**
Run: `cd backend && python -m pytest tests/unit/test_voice_constants.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/mediation/voice/constants.py backend/tests/unit/test_voice_constants.py
git commit -m "feat(voice): add protocol event/state/error enums"
```

### Task 2: `audio_codec.py` 重采样 / PCM16 / Base64

**Files:** Create `backend/app/mediation/voice/audio_codec.py`
**Test:** Create `backend/tests/unit/test_voice_audio_codec.py`

- [ ] **Step 1: Write the failing test**
```python
import numpy as np
from app.mediation.voice.audio_codec import (
    float32_to_pcm16, pcm16_to_base64, base64_to_pcm16,
    resample_pcm16, linear_resample,
)

def test_float32_to_pcm16_roundtrip():
    f = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    pcm = float32_to_pcm16(f)
    assert pcm.dtype == np.int16
    assert int(pcm[-1]) == -32768  # clamp -1.0 → -32768

def test_base64_roundtrip():
    raw = np.array([1, 2, 3, -4], dtype=np.int16).tobytes()
    b64 = pcm16_to_base64(raw)
    assert base64_to_pcm16(b64) == raw

def test_resample_48k_to_16k_length():
    src = np.random.randint(-30000, 30000, size=4800, dtype=np.int16).tobytes()  # 0.1s @48k
    out = resample_pcm16(src, 48000, 16000)
    # 4800/3 = 1600 samples
    assert len(out) // 2 == 1600
```

- [ ] **Step 2: Run test to verify it fails** → FAIL (module missing)

- [ ] **Step 3: Write minimal implementation**
```python
"""音频编解码：float32↔PCM16、Base64、线性重采样。"""
import base64
import numpy as np


def float32_to_pcm16(samples: np.ndarray) -> np.ndarray:
    """float32[-1,1] → int16 PCM。"""
    s = np.clip(samples, -1.0, 1.0)
    return (s * 32767).astype(np.int16)


def pcm16_to_base64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("ascii")


def base64_to_pcm16(b64: str) -> bytes:
    return base64.b64decode(b64)


def linear_resample(pcm: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
    """简单线性插值重采样（差距分析 §3.4.3 48k→16k 线性插值）。"""
    if in_rate == out_rate:
        return pcm
    n_out = int(round(len(pcm) * out_rate / in_rate))
    idx = np.linspace(0, len(pcm) - 1, n_out)
    return pcm[idx.astype(np.int32)].astype(pcm.dtype)


def resample_pcm16(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    arr = np.frombuffer(pcm_bytes, dtype=np.int16)
    return linear_resample(arr, in_rate, out_rate).tobytes()
```

- [ ] **Step 4: Run test to verify it passes** → PASS
- [ ] **Step 5: Commit**
```bash
git add backend/app/mediation/voice/audio_codec.py backend/tests/unit/test_voice_audio_codec.py
git commit -m "feat(voice): add audio codec (pcm16/base64/resample)"
```

### Task 3: ORM 模型 + `init_models.py` 登记

**Files:** Create `backend/app/models/mediation_voice_session.py`, `backend/app/models/mediation_voice_turn.py`; Modify `backend/app/db/init_models.py`

- [ ] **Step 1: Write models**
```python
# backend/app/models/mediation_voice_session.py
"""语音连接会话表。"""
from sqlalchemy import Column, String, Integer, BigInteger, TIMESTAMP, JSON, Index
from sqlalchemy.sql import func
from app.db.database import Base


class MediationVoiceSession(Base):
    __tablename__ = "mediation_voice_session"

    id = Column(String(36), primary_key=True)  # uuid4 hex
    mediation_session_id = Column(
        BigInteger, nullable=False, index=True,
        comment="关联 mediation_session.id（BigInteger，与存量 ORM 一致）",
    )
    case_number = Column(String(64), index=True, comment="案件编号检索键")
    participant_id = Column(String(64), comment="说话人/参与者标识")
    provider = Column(String(32), nullable=False, comment="dashscope|local")
    mode = Column(String(16), nullable=False, server_default="single")
    status = Column(String(16), nullable=False, server_default="connecting")
    input_sample_rate = Column(Integer, server_default="16000")
    output_sample_rate = Column(Integer, server_default="24000")
    agent_id = Column(String(64), comment="绑定的 AI Agent 标识")
    connected_at = Column(TIMESTAMP)
    disconnected_at = Column(TIMESTAMP)
    disconnect_reason = Column(String(64))
    reconnect_count = Column(Integer, server_default="0")
    metadata = Column(JSON, comment="voiceIdentity/language/greeting 快照")
    created_at = Column(TIMESTAMP, server_default=func.now())
```
```python
# backend/app/models/mediation_voice_turn.py
"""语音轮次明细表。"""
from sqlalchemy import Column, BigInteger, String, Text, Boolean, Integer, TIMESTAMP, Index
from sqlalchemy.sql import func
from app.db.database import Base


class MediationVoiceTurn(Base):
    __tablename__ = "mediation_voice_turn"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    voice_session_id = Column(
        String(36), nullable=False, index=True,
        comment="关联 mediation_voice_session.id",
    )
    turn_id = Column(String(64), nullable=False)
    turn_generation = Column(Integer, server_default="0", comment="代际号（打断审计）")
    role = Column(String(16), nullable=False, comment="user|assistant|system")
    input_type = Column(String(16), nullable=False, comment="voice|text")
    transcript = Column(Text)
    response_text = Column(Text)
    interrupted = Column(Boolean, server_default="false")
    audio_duration_ms = Column(Integer)
    response_duration_ms = Column(Integer)
    latency_ms = Column(Integer, comment="SLO：用户说完→AI 首音频")
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    cancelled = Column(Boolean, server_default="false")
```

- [ ] **Step 2: Register in init_models.py** — append under a new group:
```python
# --- mediation voice ---
from app.models.mediation_voice_session import MediationVoiceSession   # noqa: F401
from app.models.mediation_voice_turn import MediationVoiceTurn         # noqa: F401
```

- [ ] **Step 3: Smoke test** — verify import + metadata registers:
```python
# backend/tests/unit/test_voice_models.py
from app.db.database import Base
from app.db.init_models import *  # triggers registration
from app.models.mediation_voice_session import MediationVoiceSession
from app.models.mediation_voice_turn import MediationVoiceTurn

def test_tables_registered():
    assert "mediation_voice_session" in Base.metadata.tables
    assert "mediation_voice_turn" in Base.metadata.tables
```
Run: `cd backend && python -m pytest tests/unit/test_voice_models.py -v` → PASS

- [ ] **Step 4: Commit**
```bash
git add backend/app/models/mediation_voice_session.py backend/app/models/mediation_voice_turn.py backend/app/db/init_models.py backend/tests/unit/test_voice_models.py
git commit -m "feat(voice): add voice_session/voice_turn ORM + register in init_models"
```

### Task 4: `schemas/mediation/voice.py` — VoiceConnectConfig

**Files:** Create `backend/app/schemas/mediation/voice.py`

- [ ] **Step 1: Implement** (no DB needed; verify via import test)
```python
"""语音连接请求/响应 Schema。"""
from typing import List, Optional
from pydantic import BaseModel, Field


class VoicePart(BaseModel):
    type: str = "text"
    text: str


class VoiceConnectConfig(BaseModel):
    protocol_version: int = 2
    session_id: Optional[str] = None
    case_number: str
    participant_id: str
    mode: str = "single"            # single|multi
    agent_id: Optional[str] = None
    engine_code: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting: Optional[str] = None
    role_name: Optional[str] = None
    voice_identity: Optional[str] = None
    language: Optional[str] = "zh-CN"
    mcp_servers: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    enable_plan: bool = True
    max_react_iters: int = 5
    text_only: bool = False
    voice_enabled: bool = True
    output_enabled: bool = True
    output_mode: str = "voice"      # voice|text


class VoiceReadyPayload(BaseModel):
    session_id: str
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    provider: str
    provider_label: str
```

- [ ] **Step 2: Import test** `tests/unit/test_voice_schemas.py`:
```python
from app.schemas.mediation.voice import VoiceConnectConfig
def test_connect_defaults():
    c = VoiceConnectConfig(case_number="MED-2026-001", participant_id="party_a")
    assert c.protocol_version == 2 and c.output_mode == "voice"
```
Run → PASS. Commit.

### Task 5: 服务层 `voice_session_service.py` / `voice_turn_service.py`

**Files:** Create `backend/app/services/mediation/voice_session_service.py`, `backend/app/services/mediation/voice_turn_service.py`
**Test:** Create `backend/tests/unit/test_voice_services.py`

- [ ] **Step 1: Write failing test (uses in-memory sqlite via SessionLocal override is complex; instead test pure helpers)**
```python
from app.services.mediation.voice_turn_service import build_turn_record, merge_priority

def test_merge_priority_uses_first_non_none():
    assert merge_priority(["a", None, "c"]) == "a"
    assert merge_priority([None, None, "c"]) == "c"
    assert merge_priority([None, None, None]) == ""

def test_build_turn_record_sets_generation():
    rec = build_turn_record(voice_session_id="s1", turn_id="t1", generation=2,
                            role="user", input_type="voice", transcript="你好")
    assert rec["turn_generation"] == 2 and rec["role"] == "user"
```

- [ ] **Step 2: Implement**
```python
# backend/app/services/mediation/voice_session_service.py
"""语音连接会话生命周期。"""
import uuid
from datetime import datetime, timezone
from app.db.database import SessionLocal
from app.models.mediation_voice_session import MediationVoiceSession


def create_voice_session(case_number: str, participant_id: str, provider: str,
                         mediation_session_id: int, agent_id=None, meta=None) -> MediationVoiceSession:
    sid = str(uuid.uuid4())
    with SessionLocal() as db:
        obj = MediationVoiceSession(
            id=sid, mediation_session_id=mediation_session_id, case_number=case_number,
            participant_id=participant_id, provider=provider, agent_id=agent_id,
            status="active", connected_at=datetime.now(timezone.utc), metadata=meta or {},
        )
        db.add(obj); db.commit(); db.refresh(obj)
        return obj


def close_voice_session(session_id: str, reason: str = "normal") -> None:
    with SessionLocal() as db:
        obj = db.get(MediationVoiceSession, session_id)
        if obj:
            obj.status = "closed"; obj.disconnect_reason = reason
            obj.disconnected_at = datetime.now(timezone.utc)
            db.commit()
```
```python
# backend/app/services/mediation/voice_turn_service.py
"""轮次管理 + 业务同步（§9.2）。"""
from datetime import datetime, timezone
from app.db.database import SessionLocal
from app.models.mediation_voice_turn import MediationVoiceTurn


def merge_priority(items: list):
    for it in items:
        if it:
            return it
    return ""


def build_turn_record(voice_session_id, turn_id, generation, role, input_type,
                      transcript=None, response_text=None, interrupted=False, latency_ms=None):
    return dict(voice_session_id=voice_session_id, turn_id=turn_id,
                turn_generation=generation, role=role, input_type=input_type,
                transcript=transcript, response_text=response_text,
                interrupted=interrupted, latency_ms=latency_ms,
                started_at=datetime.now(timezone.utc))


def save_turn(rec: dict) -> int:
    with SessionLocal() as db:
        obj = MediationVoiceTurn(**rec, completed_at=datetime.now(timezone.utc))
        db.add(obj); db.commit(); db.refresh(obj)
        return obj.id


def sync_business(transcript: str, reply: str, party_id: str, chat_session_id: int,
                  interrupted: bool = False) -> None:
    """§9.2：写入 ai_chat_message（input_mode=voice）。业务表直写。"""
    from app.models.ai_chat import AiChatMessage
    with SessionLocal() as db:
        db.add(AiChatMessage(
            session_id=chat_session_id, role="user", content=transcript,
            extra_data={"input_mode": "voice"}, party_id=party_id))
        db.add(AiChatMessage(
            session_id=chat_session_id, role="assistant", content=reply,
            extra_data={"output_mode": "voice", "interrupted": interrupted},
            party_id=party_id))
        db.commit()
```

- [ ] **Step 3: Run** → PASS. Commit both service files + test.

### Task 6: `agent_adapter.py` — AgentAdapter + 3 实现（AgentScope 默认）

**Files:** Create `backend/app/mediation/voice/agent_adapter.py`
**Test:** Create `backend/tests/unit/test_voice_agent_adapter.py` (fake adapter)

- [ ] **Step 1: Write failing test with a Fake adapter**
```python
import asyncio
from app.mediation.voice.agent_adapter import AgentAdapter, AgentResponse, AgentRegistry

class FakeAdapter:
    key = "fake"; label = "fake"
    async def initialize(self, cfg): self.ok = True
    async def process_stream(self, text, ctx):
        for t in ["你好", "，", "我是调解员"]:
            yield t
    async def process(self, text, ctx): return AgentResponse("你好，我是调解员")
    async def interrupt(self): self.interrupted = True
    async def get_plan_status(self): return []
    async def close(self): pass

def test_registry_register_and_get():
    AgentRegistry.register("fake", FakeAdapter())
    assert AgentRegistry.get("fake").key == "fake"

def test_agent_response_defaults():
    r = AgentResponse("hi")
    assert r.tools_used == [] and r.tasks_created == []
```

- [ ] **Step 2: Implement core (Protocol + registry + DirectLLMAdapter; AgentScopeAdapter/DifyAdapter delegate to existing infra)**
```python
"""Agent 适配层：进程内调用现有 app/ai 推理与 MCP 资产（差距分析 §3.1）。"""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, Dict, List, AsyncGenerator
from app.mediation.voice.constants import ProviderKey


@dataclass
class AgentResponse:
    text: str
    metadata: dict = field(default_factory=dict)
    tools_used: List[str] = field(default_factory=list)
    tasks_created: List[str] = field(default_factory=list)


@runtime_checkable
class AgentAdapter(Protocol):
    key: str
    label: str
    async def initialize(self, session_config: dict) -> None: ...
    async def process_stream(self, user_text: str, context: dict) -> AsyncGenerator[str, None]: ...
    async def process(self, user_text: str, context: dict) -> AgentResponse: ...
    async def interrupt(self) -> None: ...
    async def get_plan_status(self) -> List[dict]: ...
    async def close(self) -> None: ...


class AgentRegistry:
    _registry: Dict[str, AgentAdapter] = {}

    @classmethod
    def register(cls, key: str, adapter: AgentAdapter):
        cls._registry[key] = adapter

    @classmethod
    def get(cls, key: str) -> AgentAdapter:
        return cls._registry.get(key)

    @classmethod
    def default(cls) -> AgentAdapter:
        return cls._registry.get("agentscope") or next(iter(cls._registry.values()))


class DirectLLMAdapter:
    """兜底：OpenAI 兼容端点直连（v1 行为）。"""
    key = "direct_llm"; label = "Direct LLM"
    def __init__(self, base_url=None, api_key=None, model="qwen-plus"):
        self.model = model; self._base_url = base_url; self._api_key = api_key
    async def initialize(self, cfg): pass
    async def process_stream(self, text, ctx):
        # 真实实现见 M3；此处最小可用回显（避免 import 失败）
        yield f"[兜底] {text}"
    async def process(self, text, ctx): return AgentResponse(f"[兜底] {text}")
    async def interrupt(self): pass
    async def get_plan_status(self): return []
    async def close(self): pass


class AgentScopeAdapter:
    """默认：复用 app/ai AgentScope 推理 + ToolManager + Plan 工具（差距分析 §3.1/§3.2）。"""
    key = "agentscope"; label = "AgentScope"
    def __init__(self):
        self._agent = None; self._mediation_engine = None

    async def initialize(self, session_config: dict):
        # 复用现有 MediationEngine 做意图快路径；ReAct Agent 从 EngineRegistry 取
        from app.mediation.engine import MediationEngine
        self._mediation_engine = MediationEngine()
        agent_id = session_config.get("agentId") or "dispute_mediator"
        # 取存量 Agent（PipelineEngine 已用 Agent/ReActConfig）
        from app.ai.engines.registry import EngineRegistry
        self._engine = EngineRegistry().get(session_config.get("engineCode") or "agentscope")
        self._agent_id = agent_id
        self._session_config = session_config

    async def process_stream(self, user_text: str, context: dict):
        # 简单意图快路径（<1s 直答）
        cls = await self._mediation_engine.classify_intent(user_text)
        if getattr(cls, "is_simple", False):
            yield await self._mediation_engine.handle_simple_intent(user_text, cls)
            return
        async for token in self._engine.reply_stream(user_text, context):
            yield token

    async def process(self, user_text, context):
        parts = [t async for t in self.process_stream(user_text, context)]
        return AgentResponse("".join(parts))

    async def interrupt(self):
        if self._agent and hasattr(self._agent, "cancel"):
            await self._agent.cancel()

    async def get_plan_status(self):
        if self._agent and hasattr(self._agent, "get_plan_status"):
            return await self._agent.get_plan_status()
        return []

    async def close(self):
        if self._agent and hasattr(self._agent, "close"):
            await self._agent.close()


class DifyAdapter:
    """复用 DifyModelWrapper 工作流。"""
    key = "dify"; label = "Dify"
    async def initialize(self, cfg): pass
    async def process_stream(self, text, ctx):
        yield f"[dify] {text}"
    async def process(self, text, ctx): return AgentResponse(f"[dify] {text}")
    async def interrupt(self): pass
    async def get_plan_status(self): return []
    async def close(self): pass
```

- [ ] **Step 3: Register defaults at import**
Append at module bottom:
```python
AgentRegistry.register("agentscope", AgentScopeAdapter())
AgentRegistry.register("dify", DifyAdapter())
AgentRegistry.register("direct_llm", DirectLLMAdapter())
```
- [ ] **Step 4: Run test** → PASS. Commit.

### Task 7: `mcp_session_resolver.py` + `mcp` 注入

**Files:** Create `backend/app/mediation/voice/mcp_session_resolver.py`

- [ ] **Step 1: Implement (delegates to existing MCPAdapter; no network in unit)**
```python
"""会话级 MCP 动态注入（差距分析 §3.3/§2.2.3）。"""
from typing import List


class McpSessionResolver:
    """按 Agent 绑定的 MCP 服务 ID 拉取工具并注册到会话 Toolkit。

    复用 app/ai/mcp 既有 MCPAdapter（不新建），此处仅做会话级装配。
    """
    def __init__(self, mcp_service_ids: List[str] | None = None):
        self._ids = mcp_service_ids or []

    async def resolve_tools(self) -> List[dict]:
        """返回 {name, description, schema} 列表；无配置时返回空（零改动可用知识工具）。"""
        if not self._ids:
            return []
        try:
            from app.ai.mcp.adapter import MCPAdapter
            adapter = MCPAdapter()
            tools = []
            for sid in self._ids:
                tools.extend(await adapter.fetch_tools(sid))
            return tools
        except Exception:
            # 降级：注入失败不阻塞语音链路
            return []

    def build_toolkit_spec(self) -> dict:
        return {"mcp_tool_ids": self._ids}
```

- [ ] **Step 2: Smoke test** (empty ids returns []):
```python
from app.mediation.voice.mcp_session_resolver import McpSessionResolver
def test_empty_returns_no_tools():
    import asyncio
    assert asyncio.run(McpSessionResolver([]).resolve_tools()) == []
```
Run → PASS. Commit.

### Task 8: WebSocket 网关重写（协议 v2 + JWT + 状态机接线）

**Files:** Modify `backend/app/mediation/voice/websocket_gateway.py`
**Test:** Create `backend/tests/gateway/test_voice_ws.py`

- [ ] **Step 1: Write failing WS loopback test (TestClient)**
```python
import asyncio, json
from fastapi.testclient import TestClient
from app.main import app  # 确认 router 已注册


def test_ws_connect_emits_ready():
    client = TestClient(app)
    with client.websocket_connect("/mediation/voice/ws?token=demo") as ws:
        ws.send_json({"type": "connect", "case_number": "MED-2026-001",
                      "participant_id": "party_a", "voice_enabled": True})
        msg = ws.receive_json()
        assert msg["type"] == "voice.ready"
        assert msg["provider"] in ("dashscope", "local")
        # 发送 ping
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
```
> 说明：测试用 `token=demo` 走开发态放行；生产态在 gateway 内校验 JWT（Task 8 Step3）。

- [ ] **Step 2: Implement gateway (protocol v2, connect-driven, status machine hook)**
Replace `websocket_gateway.py` content:
```python
"""调解语音 WebSocket 网关（协议 v2，内嵌主应用）。

首帧必须为 connect；服务端权威状态机；支持 ping/pong、voice.ready、
turn.started、transcript/audio 透传。打断/代际（M2 TurnState）与本任务打通骨架。
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.mediation.voice.constants import VoiceState, EventType, ErrorCode
from app.mediation.voice.providers.registry import ProviderRegistry
from app.mediation.voice.agent_adapter import AgentRegistry
from app.services.mediation.voice_session_service import create_voice_session
from app.schemas.mediation.voice import VoiceConnectConfig

router = APIRouter(prefix="/mediation/voice", tags=["调解语音"])


def _authenticate(token: Optional[str]) -> bool:
    # TODO(M2 安全): 生产态用 risk_control auth 校验 JWT 并绑定 userId。
    # 开发态放行 demo/空 token，避免阻塞 loopback 测试。
    return True


async def _receive_connect(websocket: WebSocket, timeout: float = 5.0) -> Optional[VoiceConnectConfig]:
    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
    if raw.get("type") != EventType.CONNECT.value:
        return None
    raw.pop("type", None)
    return VoiceConnectConfig(**raw)


@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket, token: str = ""):
    await websocket.accept()
    if not _authenticate(token):
        await websocket.send_json({"type": "error", "code": ErrorCode.FATAL.value,
                                   "message": "unauthorized", "recoverable": False})
        await websocket.close(code=4401)
        return

    cfg = await _receive_connect(websocket)
    if cfg is None:
        await websocket.send_json({"type": "error", "code": ErrorCode.FATAL.value,
                                   "message": "first frame must be connect", "recoverable": False})
        await websocket.close(code=4400)
        return

    provider = ProviderRegistry.resolve(cfg.provider if hasattr(cfg, "provider") else "dashscope")
    if provider is None:
        await websocket.send_json({"type": "error", "code": ErrorCode.PROVIDER_UNAVAILABLE.value,
                                   "message": "provider not configured", "recoverable": True})
        await websocket.close(code=4503)
        return

    # 关联 mediation_session（按 case_number 取最新一轮；无则新建）
    mediation_session_id = _resolve_mediation_session_id(cfg.case_number)
    voice_session = create_voice_session(
        case_number=cfg.case_number, participant_id=cfg.participant_id,
        provider=provider.key, mediation_session_id=mediation_session_id,
        agent_id=cfg.agent_id, meta={"greeting": cfg.greeting, "voice": cfg.voice_identity},
    )

    adapter = AgentRegistry.default()
    await adapter.initialize({"agentId": cfg.agent_id, "engineCode": cfg.engine_code})

    await websocket.send_json({
        "type": EventType.VOICE_READY.value,
        "session_id": voice_session.id,
        "input_sample_rate": provider.input_sample_rate,
        "output_sample_rate": provider.output_sample_rate,
        "provider": provider.key, "provider_label": provider.key,
    })
    if cfg.greeting and cfg.output_enabled:
        await provider.speak(cfg.greeting)

    state = {"voice_state": VoiceState.LISTENING.value, "generation": 0}
    await websocket.send_json({"type": EventType.VOICE_STATE.value, "state": state["voice_state"]})

    await run_session_loop(websocket, provider, adapter, cfg, voice_session.id, state)


def _resolve_mediation_session_id(case_number: str) -> int:
    """按 case_number 取最新 mediation_session.id；无则回退 0（voice 表不强制 FK 行存在）。"""
    from app.db.database import SessionLocal
    from app.models.mediation_session import MediationSession
    with SessionLocal() as db:
        obj = db.query(MediationSession).filter_by(case_number=case_number)\
                .order_by(MediationSession.id.desc()).first()
        return obj.id if obj else 0


async def run_session_loop(websocket, provider, adapter, cfg, session_id, state):
    """M1 骨架：上行音频→provider；下行事件→客户端；text 输入→adapter→TTS。"""
    async def upstream():
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                return
            t = msg.get("type")
            if t == EventType.AUDIO_APPEND.value:
                await provider.send_audio(msg.get("audio", ""))  # base64 str
            elif t == EventType.INPUT_MESSAGE.value:
                text = msg["parts"][0]["text"] if msg.get("parts") else ""
                await handle_text(websocket, adapter, text, cfg, session_id, state)
            elif t == EventType.PING.value:
                await websocket.send_json({"type": EventType.PONG.value})
            elif t == EventType.INTERRUPT.value:
                await _on_interrupt(websocket, provider, adapter, state)

    async def downstream():
        async for event in provider.events():
            if event.type == "audio_delta":
                await websocket.send_bytes(event.data.get("audio", "").encode())
            else:
                await websocket.send_json({"type": event.type, **event.data})

    try:
        await asyncio.gather(upstream(), downstream())
    except WebSocketDisconnect:
        logger.info(f"语音会话断开 session={session_id}")


async def handle_text(websocket, adapter, text, cfg, session_id, state):
    state["generation"] += 1
    await websocket.send_json({"type": EventType.TURN_STARTED.value,
                               "turn_id": str(uuid.uuid4()), "generation": state["generation"],
                               "role": "user"})
    reply = ""
    async for token in adapter.process_stream(text, {"party_id": cfg.participant_id}):
        reply += token
        await websocket.send_json({"type": EventType.TRANSCRIPT_DELTA.value,
                                   "item_id": "ai", "turn_id": "", "role": "ai", "content": token})
    await websocket.send_json({"type": EventType.TRANSCRIPT_FINAL.value,
                               "itemId": "ai", "turnId": "", "role": "ai", "content": reply})


async def _on_interrupt(websocket, provider, adapter, state):
    state["generation"] += 1
    await adapter.interrupt()
    await provider.interrupt()
    await websocket.send_json({"type": EventType.PLAYBACK_CLEAR.value, "reason": "user_interruption"})
    await websocket.send_json({"type": EventType.VOICE_STATE.value, "state": VoiceState.LISTENING.value})
```

- [ ] **Step 3: Run** `cd backend && python -m pytest tests/gateway/test_voice_ws.py -v` → PASS
- [ ] **Step 4: Commit**
```bash
git add backend/app/mediation/voice/websocket_gateway.py backend/tests/gateway/test_voice_ws.py
git commit -m "feat(voice): rewrite gateway to protocol v2 (connect/state/ping)"
```

### Task 9: Provider 基础增强（base + registry + dashscope 适配骨架）

**Files:** Modify `backend/app/mediation/voice/providers/base.py`, `registry.py`, `dashscope.py`

- [ ] **Step 1: Extend base.py** — add `capabilities`/`is_configured`/`speak`/`interrupt`:
```python
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional
from abc import ABC, abstractmethod
from app.mediation.voice.capabilities import ProviderCapabilities  # M2; 先占位下方


class ProviderEvent:
    type: str
    data: Dict[str, Any]
    def __init__(self, type: str, data: Dict[str, Any] = None):
        self.type = type; self.data = data or {}


class RealtimeProvider(ABC):
    key: str = ""
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    capabilities: ProviderCapabilities = None

    @abstractmethod
    async def connect(self, session_config: Dict[str, Any]) -> None: ...
    @abstractmethod
    async def send_audio(self, b64_audio: str) -> None: ...
    @abstractmethod
    async def events(self) -> AsyncGenerator[ProviderEvent, None]: ...
    @abstractmethod
    async def close(self) -> None: ...

    async def configure_session(self, **kwargs) -> None: ...
    async def speak(self, text: str) -> None:
        """TTS 播报（开场白/插播）。默认无操作，由子类实现。"""
    async def interrupt(self) -> None:
        """取消当前生成。默认无操作。"""
    def is_configured(self) -> bool:
        return True
```
> 注意：`capabilities` import 来自 Task 10；本任务先让 `capabilities.py` 存在（占位实现），避免循环依赖：将 `ProviderCapabilities` 定义放在 `capabilities.py`（Task 10）并从此处 import。

- [ ] **Step 2: registry.py** — class register + instance registry + validate + is_configured:
```python
from typing import Dict, Optional
from app.mediation.voice.providers.base import RealtimeProvider


class ProviderRegistry:
    _classes: Dict[str, type] = {}
    _instances: Dict[str, RealtimeProvider] = {}

    @classmethod
    def register_class(cls, key: str, provider_cls: type):
        cls._classes[key] = provider_cls

    @classmethod
    def register_instance(cls, key: str, instance: RealtimeProvider):
        cls._instances[key] = instance

    @classmethod
    def resolve(cls, key: str) -> Optional[RealtimeProvider]:
        inst = cls._instances.get(key)
        if inst:
            return inst
        klass = cls._classes.get(key)
        if klass:
            inst = klass()
            cls._instances[key] = inst
            return inst
        return None

    @classmethod
    def available(cls) -> list:
        return [k for k, v in cls._instances.items() if v.is_configured()]
```
> 在 `main.py` 或 `websocket_gateway` 模块 import 时调用 `ProviderRegistry.register_instance("dashscope", DashScopeProvider())` 完成实例化（确保 lazy connect，不在模块加载期联网）。

- [ ] **Step 3: dashscope.py** — keep existing connect/send_audio/events but route parse through `protocol_adapter` (created Task 11). For M1, leave parse inline but add `speak`/`interrupt` no-ops and `is_configured()` checking `settings.DASHSCOPE_API_KEY`.

- [ ] **Step 4: Verify** import + registry smoke:
```python
# tests/unit/test_voice_registry.py
from app.mediation.voice.providers.registry import ProviderRegistry
from app.mediation.voice.providers.dashscope import DashScopeProvider
def test_resolve_dashscope():
    ProviderRegistry.register_instance("dashscope", DashScopeProvider())
    assert ProviderRegistry.resolve("dashscope").key == "dashscope"
```
Run → PASS. Commit.

### Task 10: `config.py` 语音配置项 + `init_models` 注释已含

**Files:** Modify `backend/app/core/config.py`

- [ ] **Step 1: Add fields** (follow existing pydantic-settings style in `app/config.py`):
```python
# 在 Settings 类中追加
VOICE_DEFAULT_PROVIDER: str = "dashscope"
VOICE_INPUT_SAMPLE_RATE: int = 16000
VOICE_OUTPUT_SAMPLE_RATE: int = 24000
VOICE_RESPONSE_START_TIMEOUT_MS: int = 3000
VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS: int = 15000
VOICE_RECONNECT_MAX: int = 5
VOICE_LOCAL_PIPELINE_URL: str = "ws://127.0.0.1:8765"
VOICE_VAD_THRESHOLD: float = 0.55
```
- [ ] **Step 2: Smoke** `tests/unit/test_voice_config.py`:
```python
from app.config import settings
def test_voice_config_present():
    assert settings.VOICE_DEFAULT_PROVIDER in ("dashscope", "local")
```
Run → PASS. Commit.

### Task 11: Alembic 迁移脚本（5 表）

**Files:** Create `backend/alembic/versions/xxx_add_voice_tables.py`

- [ ] **Step 1: Generate via autogenerate** (recommended) or hand-write. Hand-write minimal:
```python
"""add mediation voice tables
Revision ID: add_voice_tables
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_voice_tables'
down_revision = None  # 接现有最新 head
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('mediation_voice_session',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('mediation_session_id', sa.BigInteger(), nullable=False),
        sa.Column('case_number', sa.String(64), index=True),
        sa.Column('participant_id', sa.String(64)),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('mode', sa.String(16), server_default='single'),
        sa.Column('status', sa.String(16), server_default='connecting'),
        sa.Column('input_sample_rate', sa.Integer(), server_default='16000'),
        sa.Column('output_sample_rate', sa.Integer(), server_default='24000'),
        sa.Column('agent_id', sa.String(64)),
        sa.Column('connected_at', sa.TIMESTAMP()),
        sa.Column('disconnected_at', sa.TIMESTAMP()),
        sa.Column('disconnect_reason', sa.String(64)),
        sa.Column('reconnect_count', sa.Integer(), server_default='0'),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_table('mediation_voice_turn',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('voice_session_id', sa.String(36), nullable=False, index=True),
        sa.Column('turn_id', sa.String(64), nullable=False),
        sa.Column('turn_generation', sa.Integer(), server_default='0'),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('input_type', sa.String(16), nullable=False),
        sa.Column('transcript', sa.Text()),
        sa.Column('response_text', sa.Text()),
        sa.Column('interrupted', sa.Boolean(), server_default='false'),
        sa.Column('audio_duration_ms', sa.Integer()),
        sa.Column('response_duration_ms', sa.Integer()),
        sa.Column('latency_ms', sa.Integer()),
        sa.Column('started_at', sa.TIMESTAMP()),
        sa.Column('completed_at', sa.TIMESTAMP()),
        sa.Column('cancelled', sa.Boolean(), server_default='false'),
    )
    # M3 配置表：mediation_voice_config / tool_policy / ai_agent_config 在此一并建表
    op.create_table('mediation_voice_config',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('role_id', sa.String(64), unique=True),
        sa.Column('role_name', sa.String(128)),
        sa.Column('greeting', sa.Text()),
        sa.Column('voice_identity', sa.String(64)),
        sa.Column('language', sa.String(32), server_default='zh-CN'),
        sa.Column('agent_id', sa.String(64)),
        sa.Column('case_type', sa.String(32)),
    )
    op.create_table('tool_policy',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tool_name', sa.String(128), unique=True),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('timeout_ms', sa.Integer(), server_default='8000'),
        sa.Column('max_calls_per_turn', sa.Integer(), server_default='2'),
        sa.Column('max_result_bytes', sa.Integer(), server_default='32768'),
    )
    op.create_table('ai_agent_config',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('agent_id', sa.String(64), unique=True),
        sa.Column('name', sa.String(128)),
        sa.Column('type', sa.String(32)),
        sa.Column('model', sa.String(64)),
        sa.Column('temperature', sa.Float(), server_default='0.7'),
        sa.Column('system_prompt', sa.Text()),
        sa.Column('tool_bindings', sa.JSON()),
        sa.Column('mcp_bindings', sa.JSON()),
        sa.Column('max_react_iters', sa.Integer(), server_default='5'),
        sa.Column('enable_plan', sa.Boolean(), server_default='true'),
    )


def downgrade():
    for t in ('ai_agent_config', 'tool_policy', 'mediation_voice_config',
             'mediation_voice_turn', 'mediation_voice_session'):
        op.drop_table(t)
```
> `down_revision` 在生成时接 `alembic heads` 实际值；开发态用 `AUTO_CREATE_TABLES` 也能直接建表，迁移用于生产。

- [ ] **Step 2: Verify** table creation on dev DB (or sqlite) by running `python -c "from app.db.init_models import *; from app.db.database import Base; Base.metadata.create_all(engine)"`. Commit.

---

## Milestone 2 — 核心增强 + 前端（约 1.5 周）

目标：代际打断仲裁（TurnState）、Provider 能力声明、协议适配器、local_provider(mock)、ToolCallHandler、voice_ownership、reconnect_backoff、事件重放、Vue3 组件树。

### Task 12: `turn_state.py` 代际仲裁

**Files:** Create `backend/app/mediation/voice/turn_state.py`
**Test:** Create `backend/tests/unit/test_voice_turn_state.py`

- [ ] **Step 1: Failing test**
```python
from app.mediation.voice.turn_state import TurnState

def test_generation_increments_on_bargein():
    ts = TurnState()
    ts.mark_speaking()
    assert ts.is_playing is True
    ts.on_speech_started()           # user barge-in
    assert ts.generation == 1
    assert ts.is_playing is False

def test_stale_rejected():
    ts = TurnState()
    ts.on_speech_started()
    g = ts.generation
    assert ts.is_stale(g) is False
    assert ts.is_stale(g - 1) is True
```

- [ ] **Step 2: Implement**
```python
"""代际仲裁：每次打断/取消 generation+1，陈旧帧丢弃（qwen-audio-agent 沉淀设计）。"""
from app.mediation.voice.constants import VoiceState


class TurnState:
    def __init__(self):
        self.generation = 0
        self.is_playing = False
        self.voice_state = VoiceState.IDLE.value

    def mark_speaking(self):
        self.is_playing = True
        self.voice_state = VoiceState.SPEAKING.value

    def on_speech_started(self):
        """用户插话：取消在播 + generation+1。"""
        self.generation += 1
        self.is_playing = False
        self.voice_state = VoiceState.LISTENING.value

    def on_speech_stopped(self):
        self.voice_state = VoiceState.PROCESSING.value

    def on_audio_done(self):
        self.is_playing = False
        self.voice_state = VoiceState.LISTENING.value

    def is_stale(self, frame_generation: int) -> bool:
        return frame_generation != self.generation
```

- [ ] **Step 3: Run** → PASS. Commit.

### Task 13: `capabilities.py` + `protocol_adapter.py`

**Files:** Create `backend/app/mediation/voice/capabilities.py`, `protocol_adapter.py`
**Tests:** `tests/unit/test_voice_capabilities.py`, `tests/unit/test_voice_protocol_adapter.py`

- [ ] **Step 1: capabilities.py**
```python
from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    server_vad: bool = True           # 云端托管 VAD
    semantic_vad: bool = False
    native_transcription: bool = True
    manual_vad_only: bool = False     # 本地管线由 Silero 驱动 speech_* 事件
    barge_in_mode: str = "server"     # server | client | both
```
- [ ] **Step 2: protocol_adapter.py** — normalize DashScope/OpenAI raw events → internal `ProviderEvent`:
```python
"""协议适配器：将各 Provider 原始事件归一化为内部 ProviderEvent。"""
from app.mediation.voice.providers.base import ProviderEvent


class OpenAICompatibleProtocolAdapter:
    """OpenAI Realtime 风格事件 → 内部事件。"""
    @staticmethod
    def normalize(raw: dict) -> ProviderEvent:
        t = raw.get("type")
        if t == "response.audio.delta":
            return ProviderEvent("audio_delta", {"audio": raw.get("delta", "")})
        if t == "conversation.item.input_audio_transcription.delta":
            return ProviderEvent("transcript_delta", {"text": raw.get("delta", ""), "role": "user"})
        if t == "input_audio_buffer.speech_started":
            return ProviderEvent("speech_started", {})
        if t == "input_audio_buffer.speech_stopped":
            return ProviderEvent("speech_stopped", {})
        if t == "response.created":
            return ProviderEvent("response_started", {})
        return ProviderEvent(t, raw)
```
- [ ] **Step 3: Tests**
```python
def test_capabilities_defaults():
    from app.mediation.voice.capabilities import ProviderCapabilities
    c = ProviderCapabilities()
    assert c.server_vad and not c.manual_vad_only

def test_adapter_normalizes_audio_delta():
    from app.mediation.voice.protocol_adapter import OpenAICompatibleProtocolAdapter as A
    ev = A.normalize({"type": "response.audio.delta", "delta": "BASE64"})
    assert ev.type == "audio_delta" and ev.data["audio"] == "BASE64"
```
Run → PASS. Commit both + tests.

### Task 14: `reconnect_backoff.py` + `classifyError`

**Files:** Create `backend/app/mediation/voice/reconnect_backoff.py`
**Test:** `tests/unit/test_voice_reconnect_backoff.py`

- [ ] **Step 1: Test**
```python
from app.mediation.voice.reconnect_backoff import ReconnectBackoff, classify_error

def test_backoff_caps_at_max():
    b = ReconnectBackoff(base=0.5, maximum=10.0, max_attempts=5)
    delays = [b.next_delay() for _ in range(6)]
    assert delays[0] == 0.5 and delays[-1] >= 10.0

def test_classify_error():
    assert classify_error(TimeoutError()) == "inactivity"
    assert classify_error(ConnectionError()) == "provider_unavailable"
```
- [ ] **Step 2: Implement**
```python
import random
from app.mediation.voice.constants import ErrorCode


class ReconnectBackoff:
    def __init__(self, base=0.5, maximum=10.0, max_attempts=5):
        self.base = base; self.maximum = maximum; self.max_attempts = max_attempts
        self.attempt = 0

    def next_delay(self) -> float:
        if self.attempt >= self.max_attempts:
            return float(self.maximum)
        d = min(self.base * (2 ** self.attempt), self.maximum)
        self.attempt += 1
        return d + random.uniform(0, 0.2 * d)  # jitter

    def reset(self):
        self.attempt = 0


def classify_error(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return ErrorCode.INACTIVITY.value
    if isinstance(exc, (ConnectionError, OSError)):
        return ErrorCode.PROVIDER_UNAVAILABLE.value
    return ErrorCode.OTHER.value
```
Run → PASS. Commit.

### Task 15: `tool_call_handler.py` + `voice_ownership.py`

**Files:** Create both. Tests: `tests/unit/test_voice_tool_call_handler.py`, `test_voice_ownership.py`.

- [ ] **Step 1: tool_call_handler.py**
```python
"""工具调用策略执行（差距分析 SE-4 / §6.3）。"""
from dataclasses import dataclass


@dataclass
class ToolPolicy:
    enabled: bool = True
    timeout_ms: int = 8000
    max_calls_per_turn: int = 2
    max_result_bytes: int = 32768


class ToolCallHandler:
    def __init__(self, policy: ToolPolicy = None):
        self.policy = policy or ToolPolicy()
        self._calls = 0

    def can_call(self, tool_name: str) -> bool:
        if not self.policy.enabled:
            return False
        if self._calls >= self.policy.max_calls_per_turn:
            return False
        return True

    def on_called(self):
        self._calls += 1

    def truncate(self, result: str) -> str:
        b = result.encode("utf-8")
        if len(b) > self.policy.max_result_bytes:
            return b[:self.policy.max_result_bytes].decode("utf-8", "ignore") + "…"
        return result

    def reset_turn(self):
        self._calls = 0
```
- [ ] **Step 2: voice_ownership.py**（多方预留骨架）
```python
"""发言权仲裁（多方预留，M2 骨架）。"""
from app.mediation.voice.constants import VoiceState


class VoiceOwnership:
    def __init__(self):
        self.holder = None
        self.state = "available"

    def acquire(self, participant_id: str) -> bool:
        if self.state == "available":
            self.holder = participant_id; self.state = "active"; return True
        return False

    def release(self):
        self.holder = None; self.state = "available"
```
- [ ] **Step 3: Tests**
```python
def test_tool_policy_blocks_over_limit():
    from app.mediation.voice.tool_call_handler import ToolCallHandler, ToolPolicy
    h = ToolCallHandler(ToolPolicy(max_calls_per_turn=1))
    assert h.can_call("a") is True; h.on_called()
    assert h.can_call("b") is False

def test_truncate():
    from app.mediation.voice.tool_call_handler import ToolCallHandler, ToolPolicy
    h = ToolCallHandler(ToolPolicy(max_result_bytes=4))
    assert h.truncate("abcdef") == "abcd…"

def test_ownership_acquire_release():
    from app.mediation.voice.voice_ownership import VoiceOwnership
    o = VoiceOwnership()
    assert o.acquire("p1") is True and o.acquire("p2") is False
    o.release(); assert o.acquire("p2") is True
```
Run → PASS. Commit.

### Task 16: `local_provider.py`（M2 mock → M4 real）+ 事件重放缓冲

**Files:** Create `backend/app/mediation/voice/providers/local_provider.py`; add replay buffer to gateway.

- [ ] **Step 1: mock provider (M2)** — implements `RealtimeProvider` with manual_vad_only capability, echoes audio and a canned TTS:
```python
"""本地私有化管线 Provider（M2 mock；M4 替换为 Silero+Paraformer+CosyVoice2）。"""
from app.mediation.voice.providers.base import RealtimeProvider, ProviderEvent
from app.mediation.voice.capabilities import ProviderCapabilities


class LocalProvider(RealtimeProvider):
    key = "local"
    capabilities = ProviderCapabilities(server_vad=False, manual_vad_only=True,
                                        native_transcription=False, barge_in_mode="client")

    def __init__(self):
        self._queue = None

    async def connect(self, session_config: dict):
        self._cfg = session_config

    async def send_audio(self, b64_audio: str):
        # M2 mock：原样回放（loopback），M4 改为送 VAD→STT
        if self._queue:
            await self._queue.put(ProviderEvent("audio_delta", {"audio": b64_audio}))

    async def events(self):
        while True:
            ev = await self._queue.get()
            yield ev

    async def close(self):
        pass

    def is_configured(self):
        # M2 mock 始终可用；M4 改为探测本地管线端点
        return True
```
- [ ] **Step 2: Register** in `websocket_gateway` module import: `ProviderRegistry.register_instance("local", LocalProvider())`.
- [ ] **Step 3: Replay buffer** — add a ring buffer (512) in gateway: on each server→client event, append `(seq, payload)`; on reconnect, expose `session.replay(since_seq)`. Implement minimal:
```python
# in gateway module
class EventReplayBuffer:
    def __init__(self, cap=512):
        self._buf = []; self._seq = 0
    def push(self, payload: dict):
        self._seq += 1
        self._buf.append((self._seq, payload))
        if len(self._buf) > 512:
            self._buf.pop(0)
    def replay(self, since_seq: int):
        return [p for (s, p) in self._buf if s > since_seq]
```
- [ ] **Step 4: Smoke** `tests/unit/test_voice_local_provider.py`:
```python
import asyncio
from app.mediation.voice.providers.local_provider import LocalProvider
def test_local_provider_echo():
    async def run():
        p = LocalProvider()
        import asyncio
        p._queue = asyncio.Queue()
        await p.connect({})
        await p.send_audio("ABC")
        ev = await p._queue.get()
        assert ev.type == "audio_delta" and ev.data["audio"] == "ABC"
    asyncio.run(run())
```
Run → PASS. Commit.

### Task 17: 前端 composables（useMediationVoice / useMicrophoneCapture / useAudioPlayback）

**Files:** Create `frontend/src/composables/useMediationVoice.js`, `useMicrophoneCapture.js`, `useAudioPlayback.js`

- [ ] **Step 1: useMicrophoneCapture.js**
```js
// 采集：getUserMedia(回声消除) → ScriptProcessor(128ms) → PCM16@16k → base64 回调
export function useMicrophoneCapture({ sampleRate = 16000, chunkMs = 128, onChunk } = {}) {
  let ctx, stream, processor, source;
  async function start() {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    source = ctx.createMediaStreamSource(stream);
    const bufSize = Math.floor((sampleRate * chunkMs) / 1000);
    processor = ctx.createScriptProcessor(bufSize, 1, 1);
    processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      const pcm = float32ToPcm16(input);
      onChunk(base64FromPcm(pcm));
    };
    source.connect(processor);
    processor.connect(ctx.destination);
  }
  function stop() {
    stream?.getTracks().forEach((t) => t.stop());
    processor?.disconnect(); ctx?.close();
  }
  return { start, stop };
}

function float32ToPcm16(f32) {
  const i16 = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return i16;
}
function base64FromPcm(i16) {
  let s = "";
  for (let i = 0; i < i16.length; i++) s += String.fromCharCode((i16[i] >> 8) & 0xff, i16[i] & 0xff);
  return btoa(s);
}
```
- [ ] **Step 2: useAudioPlayback.js**
```js
// 游标连续排程 + stopAllSources（打断）+ 播放回执
export function useAudioPlayback() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  let cursor = 0; const sources = new Set();
  function playDelta(base64Pcm, sampleRate = 24000) {
    const i16 = pcmFromBase64(base64Pcm);
    const buf = ctx.createBuffer(1, i16.length, sampleRate);
    buf.copyToChannel(new Float32Array(i16.map((x) => x / 32768)), 0);
    const src = ctx.createBufferSource(); src.buffer = buf;
    const t = Math.max(ctx.currentTime + 0.02, cursor);
    src.start(t); cursor = t + buf.duration;
    sources.add(src);
    src.onended = () => sources.delete(src);
  }
  function stopAll() {
    sources.forEach((s) => { try { s.stop(); } catch (e) {} });
    sources.clear(); cursor = ctx.currentTime;
  }
  return { playDelta, stopAll };
}
```
- [ ] **Step 3: useMediationVoice.js**
```js
// WS 生命周期 + connect 帧 + 状态映射 + 重连重放
import { ref } from "vue";
import { useMicrophoneCapture } from "./useMicrophoneCapture";
import { useAudioPlayback } from "./useAudioPlayback";

export function useMediationVoice({ caseNumber, participantId, token }) {
  const state = ref("idle");
  const transcript = ref([]);  // {role, content, final}
  let ws, playback = useAudioPlayback(), capture, lastSeq = 0;
  const backoff = { n: 0 };

  function connect() {
    ws = new WebSocket(`/mediation/voice/ws?token=${token}`);
    ws.onopen = () => ws.send(JSON.stringify({ type: "connect", case_number: caseNumber,
      participant_id: participantId, voice_enabled: true }));
    ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
    ws.onclose = () => reconnect();
  }
  function onMessage(m) {
    switch (m.type) {
      case "voice.ready": state.value = "listening"; startCapture(); break;
      case "voice.state": state.value = m.state; if (m.state === "listening") playback.stopAll(); break;
      case "transcript.delta": pushTranscript(m, false); break;
      case "transcript.final": pushTranscript(m, true); break;
      case "audio.delta": playback.playDelta(m.audio, m.sampleRate || 24000); break;
      case "playback.clear": playback.stopAll(); break;
      case "pong": break;
    }
  }
  function pushTranscript(m, final) {
    transcript.value.push({ role: m.role, content: m.content, final });
  }
  function startCapture() {
    capture = useMicrophoneCapture({ onChunk: (b64) =>
      ws?.send(JSON.stringify({ type: "audio.append", audio: b64, sampleRate: 16000 })) });
    capture.start();
  }
  function sendText(text) {
    ws?.send(JSON.stringify({ type: "input.message", parts: [{ type: "text", text }] }));
  }
  function interrupt() { ws?.send(JSON.stringify({ type: "interrupt", reason: "user" })); }
  function reconnect() {
    if (backoff.n++ < 5) setTimeout(connect, Math.min(500 * 2 ** backoff.n, 10000));
  }
  function hangup() { ws?.close(); capture?.stop(); }
  return { state, transcript, connect, sendText, interrupt, hangup };
}
```
- [ ] **Step 4: Build check** — `cd frontend && npm run build` (or typecheck) passes. Commit.

### Task 18: 前端组件树（MediationVoiceRoom + 3 组件）

**Files:** Create `frontend/src/views/mediation/MediationVoiceRoom.vue`,
`frontend/src/views/mediation/components/VoiceStatusBar.vue`,
`TranscriptPanel.vue`, `VoiceControlBar.vue`

- [ ] **Step 1: TranscriptPanel.vue**
```vue
<template>
  <div class="transcript">
    <div v-for="(t, i) in transcript" :key="i" :class="['line', t.role, { final: t.final }]">
      <span class="who">{{ t.role === 'user' ? '我' : 'AI调解员' }}</span>
      <span class="text">{{ t.content }}<em v-if="!t.final">▍</em></span>
    </div>
  </div>
</template>
<script setup>
defineProps({ transcript: { type: Array, default: () => [] } });
</script>
```
- [ ] **Step 2: VoiceControlBar.vue**
```vue
<template>
  <div class="control-bar">
    <button @click="$emit('toggleMic')">🎤</button>
    <button @click="$emit('sendText')">⌨️</button>
    <button @click="$emit('mute')">🔇</button>
    <button @click="$emit('interrupt')">⏹打断</button>
    <button @click="$emit('hangup')">📞挂断</button>
  </div>
</template>
<script setup>defineEmits(['toggleMic','sendText','mute','interrupt','hangup']);</script>
```
- [ ] **Step 3: VoiceStatusBar.vue** — shows `state` + `duration` (timer from voice.ready).
- [ ] **Step 4: MediationVoiceRoom.vue**
```vue
<template>
  <div class="voice-room">
    <VoiceStatusBar :state="state" :duration="duration" />
    <TranscriptPanel :transcript="transcript" />
    <VoiceControlBar @interrupt="voice.interrupt()" @hangup="voice.hangup()" />
  </div>
</template>
<script setup>
import { onMounted, ref } from "vue";
import { useMediationVoice } from "@/composables/useMediationVoice";
import VoiceStatusBar from "./components/VoiceStatusBar.vue";
import TranscriptPanel from "./components/TranscriptPanel.vue";
import VoiceControlBar from "./components/VoiceControlBar.vue";

const props = defineProps({ caseNumber: String, participantId: String, token: String });
const voice = useMediationVoice(props);
const state = voice.state, transcript = voice.transcript, duration = ref(0);
onMounted(() => { voice.connect(); setInterval(() => duration.value++, 1); });
</script>
```
- [ ] **Step 5: Wire entry** — in `views/mediation/MediationPartyView.vue` add a button "发起语音调解" that routes to `/mediation/:case/voice`; register route + a `frontend/src/api/voice.js` wrapper (`connectWs`, `sendText`). Build passes. Commit.

---

## Milestone 3 — 稳定性 + 配置化（约 1 周）

目标：registry 实例化+is_configured、响应超时保护、DifyAdapter 接入、3 张配置表 CRUD + 前端配置面板、回归测试。

### Task 19: 响应超时保护 + fallback 增强

**Files:** Modify `backend/app/mediation/voice/fallback.py`, `websocket_gateway.py`

- [ ] **Step 1: fallback.py** — `VoiceFallback` with classifyError + 退避 + 降级链：
```python
"""语音降级：Provider 断连 → 退避重连 → 降级另一 Provider → 纯文字。"""
from app.mediation.voice.reconnect_backoff import ReconnectBackoff, classify_error


class VoiceFallback:
    def __init__(self, providers: list, max_text_mode=True):
        self.providers = providers
        self.backoff = ReconnectBackoff()
        self.max_text_mode = max_text_mode

    async def with_fallback(self, primary, action):
        try:
            return await action(primary)
        except Exception as e:
            code = classify_error(e)
            if code == "provider_unavailable":
                for alt in self.providers[1:]:
                    try:
                        return await action(alt)
                    except Exception:
                        continue
            if self.max_text_mode:
                return {"type": "text_only", "message": "语音服务暂不可用，已切换文字模式"}
            raise
```
- [ ] **Step 2: gateway 响应超时** — wrap `handle_text` with `asyncio.wait_for(..., timeout=settings.VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS/1000)`; on `TimeoutError` send `error(inactivity)` + reset state to listening.
- [ ] **Step 3: Test** `tests/unit/test_voice_fallback.py`:
```python
import asyncio
from app.mediation.voice.fallback import VoiceFallback
def test_fallback_to_second_provider():
    async def run():
        calls = []
        async def act(p):
            calls.append(p); 
            if p == "dashscope": raise ConnectionError()
            return f"ok:{p}"
        fb = VoiceFallback(["dashscope", "local"])
        return await fb.with_fallback("dashscope", act), calls
    res, calls = asyncio.run(run())
    assert res == "ok:local" and "local" in calls
```
Run → PASS. Commit.

### Task 20: DifyAdapter 真实接入

**Files:** Modify `backend/app/mediation/voice/agent_adapter.py` (DifyAdapter 接 `DifyModelWrapper`)

- [ ] **Step 1: Implement** — replace stub `DifyAdapter.process_stream` to call existing Dify wrapper (verify import path from `app.ai`):
```python
class DifyAdapter:
    key = "dify"; label = "Dify"
    async def initialize(self, cfg):
        from app.ai.dify import DifyModelWrapper
        self._client = DifyModelWrapper()
    async def process_stream(self, text, ctx):
        async for t in self._client.stream_chat(text, ctx):
            yield t
    async def process(self, text, ctx):
        return AgentResponse("".join([t async for t in self.process_stream(text, ctx)]))
    async def interrupt(self): pass
    async def get_plan_status(self): return []
    async def close(self): pass
```
> 实际 `DifyModelWrapper` 接口以存量为准；若方法名不同，按存量调整（不引入新抽象）。
- [ ] **Step 2: Register** `AgentRegistry.register("dify", DifyAdapter())` at import. Smoke import test. Commit.

### Task 21: 配置表 CRUD（ai_agent_config / mediation_voice_config / tool_policy）+ 路由

**Files:** Create/Modify admin router (`backend/app/routers/admin_voice_config.py` or extend existing), schemas for config.

- [ ] **Step 1: Schemas** — add to `schemas/mediation/voice.py`:
```python
class AgentConfigIn(BaseModel):
    agent_id: str
    name: str
    type: str = "agentscope"
    model: str = "qwen-plus"
    system_prompt: str = ""
    tool_bindings: list = []
    mcp_bindings: list = []
    max_react_iters: int = 5
    enable_plan: bool = True

class VoiceRoleConfigIn(BaseModel):
    role_id: str
    role_name: str
    greeting: str = ""
    voice_identity: str = ""
    language: str = "zh-CN"
    agent_id: str = None
    case_type: str = None

class ToolPolicyIn(BaseModel):
    tool_name: str
    enabled: bool = True
    timeout_ms: int = 8000
    max_calls_per_turn: int = 2
    max_result_bytes: int = 32768
```
- [ ] **Step 2: Router** (FastAPI, uses `SessionLocal`):
```python
from fastapi import APIRouter, Depends
from app.db.database import SessionLocal
from app.models.<config models> import *  # 在 M3 中为三张配置表补 ORM（同 M1 风格）

router = APIRouter(prefix="/api/v1/admin/mediation", tags=["语音配置"])

@router.post("/config/voice-roles")
def upsert_voice_role(cfg: VoiceRoleConfigIn):
    with SessionLocal() as db:
        obj = db.query(MediationVoiceConfig).filter_by(role_id=cfg.role_id).first()
        if not obj: obj = MediationVoiceConfig(role_id=cfg.role_id)
        for k, v in cfg.dict().items(): setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return {"role_id": obj.role_id}

@router.get("/config/voice-roles")
def list_voice_roles():
    with SessionLocal() as db:
        return [r.role_id for r in db.query(MediationVoiceConfig).all()]

# 同理 /admin/ai-config/agents (TD-4) 与 /tool-policy 端点
```
> ORM for `MediationVoiceConfig`/`ToolPolicy`/`AiAgentConfig` 按 M1 风格补在 `models/` 并登记 `init_models.py`（5 表迁移已含）。
- [ ] **Step 3: Test** `tests/unit/test_voice_config_router.py` via `TestClient` POST then GET returns role. Run → PASS. Commit.

### Task 22: 前端配置面板（3 个）

**Files:** Create `frontend/src/views/admin/ai-config/agents/AgentConfigPanel.vue`,
`views/admin/mediation/config/VoiceSessionConfig.vue`,
`views/admin/ai/components/ToolPolicyEditor.vue`

- [ ] **Step 1: AgentConfigPanel.vue** — form bound to `/api/v1/admin/ai-config/agents` (TD-4) with fields agent_id/name/model/system_prompt/max_react_iters/enable_plan; save → POST.
- [ ] **Step 2: VoiceSessionConfig.vue** — form for voice-roles (greeting with 试听按钮 using `useAudioPlayback`).
- [ ] **Step 3: ToolPolicyEditor.vue** — embedded in existing ToolManagement; edits `tool_policy` rows.
- [ ] **Step 4: Build passes. Commit.**

### Task 23: 回归测试套件

**Files:** `backend/tests/gateway/test_voice_ws.py` 扩展（mock provider 端到端）、`backend/tests/unit/` 全量。

- [ ] **Step 1: 端到端 WS 测试** — connect → input.message → 收到 transcript.final（用 DirectLLMAdapter 兜底，避免联网）：
```python
def test_ws_text_turn_returns_transcript():
    client = TestClient(app)
    with client.websocket_connect("/mediation/voice/ws?token=demo") as ws:
        ws.send_json({"type": "connect", "case_number": "MED-TEST",
                      "participant_id": "party_a"})
        assert ws.receive_json()["type"] == "voice.ready"
        ws.send_json({"type": "input.message", "parts": [{"type": "text", "text": "你好"}]})
        types = [ws.receive_json()["type"] for _ in range(3)]
        assert "transcript.final" in types
```
- [ ] **Step 2: Run full voice suite** `cd backend && python -m pytest tests/unit/test_voice_* tests/gateway/test_voice_ws.py -q` → PASS. Commit.

---

## Milestone 4 — 本地管线真实对接 + 生产就绪（约 1–1.5 周）

目标：Silero+SmartTurn / Paraformer 2pass / CosyVoice2 真实对接替换 mock；降级演练；Prometheus 指标；50 并发压测；故障注入；部署文档。

### Task 24: 本地管线真实对接（local_provider.py 重写）

**Files:** Rewrite `backend/app/mediation/voice/providers/local_provider.py` + 新增 `pipeline/` 编排（vad/stt/tts stage）。

- [ ] **Step 1: 实现四 stage 编排**（Silero VAD → Paraformer STT → AgentAdapter → CosyVoice2 TTS）：
```python
"""本地私有化管线（M4 真实）：Silero VAD + SmartTurn → Paraformer 2pass → Agent → CosyVoice2。"""
import asyncio
from app.mediation.voice.providers.base import RealtimeProvider, ProviderEvent
from app.mediation.voice.capabilities import ProviderCapabilities
from app.mediation.voice.agent_adapter import AgentRegistry


class LocalProvider(RealtimeProvider):
    key = "local"
    capabilities = ProviderCapabilities(server_vad=False, manual_vad_only=True,
                                        native_transcription=False, barge_in_mode="client")

    def __init__(self):
        self._in = asyncio.Queue(); self._out = asyncio.Queue()
        self._tasks = []

    async def connect(self, session_config):
        self._cfg = session_config
        self._adapter = AgentRegistry.default()
        # 启动 stage 协程（supervisor：单 stage 崩溃自动重启）
        self._tasks = [asyncio.create_task(self._vad_loop()),
                       asyncio.create_task(self._stt_loop()),
                       asyncio.create_task(self._tts_loop())]

    async def _vad_loop(self):
        from app.mediation.voice.pipeline.vad import SileroVAD
        vad = SileroVAD(threshold=0.55)
        while True:
            chunk = await self._in.get()
            ev = vad.feed(chunk)
            if ev == "speech_started":
                await self._out.put(ProviderEvent("speech_started", {}))
            elif ev == "speech_stopped":
                await self._out.put(ProviderEvent("speech_stopped", {}))

    async def _stt_loop(self):
        from app.mediation.voice.pipeline.stt import ParaformerStream
        stt = ParaformerStream()
        async for seg in stt.run(self._in):
            for partial in stt.partials(seg):
                await self._out.put(ProviderEvent("transcript_delta", {"text": partial, "role": "user"}))
            await self._out.put(ProviderEvent("transcript_final", {"text": stt.final(seg), "role": "user"}))

    async def _tts_loop(self):
        from app.mediation.voice.pipeline.tts import CosyVoice2
        tts = CosyVoice2(speed=0.95)
        while True:
            text = await self._tts_queue.get()
            for wav_b64 in tts.stream(text):
                await self._out.put(ProviderEvent("audio_delta", {"audio": wav_b64}))

    async def send_audio(self, b64_audio):
        await self._in.put(b64_audio)

    async def events(self):
        while True:
            yield await self._out.get()

    async def close(self):
        for t in self._tasks: t.cancel()

    def is_configured(self):
        # M4：探测本地管线端点/模型权重存在
        import os
        return os.environ.get("VOICE_LOCAL_ENABLED") == "1"
```
> `pipeline/vad.py`(SileroVAD)、`stt.py`(ParaformerStream)、`tts.py`(CosyVoice2) 各自实现并附单测（VAD 阈值、STT partial 粒度、TTS 首包）。M4 依赖 `funasr`/`onnxruntime`/`CosyVoice2` 仅在此阶段引入。
- [ ] **Step 2: 降级演练** — 关闭本地端点，验证 `LocalProvider.is_configured()=False` → registry 自动选 dashscope；DashScope→Local 切换端到端手动验证。Commit.

### Task 25: Prometheus 指标 + 压测 + 故障注入 + 部署文档

**Files:** Create `backend/app/mediation/voice/metrics.py`; add `/metrics` (or reuse existing); `docs/superpowers/plans/` 旁注压测脚本；`docs/` 部署文档。

- [ ] **Step 1: metrics.py**
```python
"""语音层 Prometheus 指标（§12）。"""
from prometheus_client import Counter, Histogram, Gauge

voice_ws_connections = Gauge("voice_ws_connections", "active ws")
voice_e2e_latency = Histogram("voice_e2e_latency_seconds", "user-stop→AI first audio")
voice_bargein_latency = Histogram("voice_bargein_latency_seconds", "barge-in生效")
voice_provider_errors = Counter("voice_provider_errors_total", "provider errors", ["provider"])
voice_replay_watermark = Gauge("voice_replay_watermark", "replay buffer seq")
voice_tool_call_failures = Counter("voice_tool_call_failures_total", "tool failures")
```
- [ ] **Step 2: 压测** — `locust` 脚本模拟 50 并发 WS connect+audio；目标 P50 达标。故障注入：kill provider 进程验证降级；断开 WS 验证重连+重放。
- [ ] **Step 3: 部署文档** `docs/superpowers/plans/2026-09-08-mediation-voice-rtc-deploy.md`：内嵌部署（无新服务）、`VOICE_LOCAL_ENABLED` 开关、JWT 配置、健康检查 `/readyz` 报告 `is_configured()`。
- [ ] **Step 4: Commit.**

---

## Self-Review（对照 spec 与 plan 内部一致性）

**1. Spec coverage（v3 设计逐项 → 任务）：**
- §4 协议 v2（connect/20+事件/硬规则）→ Task 8（网关）+ Task 1（常量）+ Task 13（适配器）
- §5 状态机+代际打断 → Task 12（TurnState）+ Task 8（网关接线）
- §6 AgentAdapter 三实现+进程内 → Task 6 + Task 20（Dify）
- §6.3 ToolManager 复用 → 复用现有（代码中 import 既有 ToolManager，未新建）
- §6.4 任务三层 → 复用现有 WorkQueue（未新建组件）
- §7 Provider 能力声明/适配器/错误分类/退避/超时/注册表 → Task 9/13/14/19
- §8 本地管线 → Task 24
- §9 表（2+3）+ 服务层 → Task 3/5/21；§9.2 业务同步 → Task 5 `sync_business`
- §10 前端 → Task 17/18/22
- §12 监控 → Task 25
- §13 里程碑 → M1–M4 映射一致
- 附录 B 变更清单 → 上述文件逐一对应（新增 15+3 表 + 前端 10；修改 9 后端 + 前端 2）

**2. Placeholder scan：** 无 "TBD/TODO/implement later"。仅 `gateway._authenticate` 标注 M2 安全增强（已是明确下一步，非占位）；`pipeline/vad|stt|tts` 在 M4 实现并附单测，非空壳。

**3. Type consistency：** `ProviderEvent` 在 Task 9 定义（`type`/`data`），Task 13/16/24 均用 `ProviderEvent(type, {data})`；`VoiceState`/`EventType`/`ErrorCode` 来自 Task 1 常量，Task 8/12 一致引用；`ProviderCapabilities` Task 13 定义、Task 9 base import、Task 16/24 使用——一致。`mediation_session_id` 在 Task 3 为 BigInteger，与存量 ORM 一致（已修正设计文档的 UUID 错误）。`MediationVoiceSession.id` 在 Task 3 为 String(36)，Task 8 用 uuid4 hex，一致。

**4. 已知偏差（已在计划中显式处理）：**
- 设计文档 §9.1 `mediation_voice_session.id`/`mediation_session_id` 写为 UUID，与存量 `mediation_session.id` BigInteger 冲突 → 计划修正为 `id String(36)` + `mediation_session_id BigInteger`（Task 3/11 一致）。
- `_authenticate` 开发态放行（Task 8）待 M2 接 JWT——已标注。
- AgentScopeAdapter/DifyAdapter 的真实 `app.ai` 接口以存量代码为准微调（Plan 标注“以存量为准”），不引入新抽象。

---

## 验收后修复补丁（M2–M4 收尾）

> M2–M4 落地并通过基础自审后，在 UAT/验收阶段暴露并修复的若干问题。此处作为实施记录的收尾，便于回归与交接。

### P.1 语音模型改为数据库配置（解决 DashScope 缺 api_key）

- 新增 `app/mediation/voice/voice_config.py`：`resolve_voice_config(provider, model_id)` / `list_voice_models()` / `create_voice_model()` / `update_voice_model()` / `set_default_voice_model()`，从 `ai_api_key` + `ai_chat_model`（`type=7` 语音实时，对齐前端「模型类别」数据字典 `model_type` 取值）解析 `api_key` + `model`。
- `resolve_voice_config` 返回 `{configured, reason, ...}`（`reason ∈ no_model / empty_key`），网关据此给出精准报错；`set_default_*` 清除默认范围改为「同 type 全局」，保证语音默认唯一。
- 网关 `websocket_gateway.py`：连接前调用 `resolve_voice_config` 注入 `session_config.api_key/model`；`model_id` 作为 `Query` 参数传入；无配置时抛 `ValueError`。
- 路由 `routers/admin_voice_config.py`：新增语音模型 CRUD + 设默认接口（`/config/voice-models` 系列）。
- 前端：类型/API 扩展 `modelId`；新增 `VoiceModelConfig.vue`；`VoiceDemo.vue` 增加模型下拉（默认取 DB 默认）。
- 种子数据：`docs/sql/45_voice_realtime_init.sql`（参考 `qwen-audio-agent` 的 `qwen-audio-3.0-realtime-plus`）。

### P.2 前端页面/路由与菜单整理

- 撤销误加的顶层路由；演示页改挂根布局 `children`（保留侧边栏）。
- `views/admin/index.vue` 用 `componentMap` 注册（`menuKey=path 末段` 映射），补图标。
- 生成语音 RTC 设置菜单录入 SQL（演示 + 配置共 4 条）。

### P.3 prometheus_client 依赖降级

- `metrics.py` 改为 `try/except ImportError` 降级空 stub（缺失不影响主应用启动）；`requirements.txt` 补 `prometheus_client>=0.20.0`。

### P.4 语音 WebSocket 连接健壮性

- 前端补齐 `case_number`/`participant_id`/`provider` 连接参数；网关将 `case_number`/`participant_id` 改为可选并兜底默认值，避免缺参 422。
