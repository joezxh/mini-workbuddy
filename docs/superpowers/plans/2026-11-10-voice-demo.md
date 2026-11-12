# 语音能力 Demo 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 4 Tab 语音 Demo（ASR / TTS / 实时 S2S 对话 / 手册）：FastAPI 网关（REST 转发 + WS 桥接 s2s `/v1/realtime`）+ Vue3 前端，Mock 默认本地可跑。

**Architecture:** 展示层（views/voice-demo）→ 网关层（routers/voice_demo.py + services/voice_demo：gateway/realtime_bridge/mock）→ 服务层（既有 s2s，127.0.0.1:8765）。REST 用 httpx 转发，WS 用 websockets 库双向泵 + connect 注入 session.update；Mock 与真实事件形状逐一同构。

**Tech Stack:** FastAPI + httpx + websockets（均在 requirements.txt）· Vue 3.4 + ant-design-vue 4.1.2 + vitest · @ricky0123/vad-web（唯一前端新依赖）

**Spec:** `docs/superpowers/specs/2026-11-10-voice-demo-design.md`（计划从 spec 论证，执行者须同读）· 基准原型 `docs/prototypes/voice-demo-preview.html`

## Global Constraints

- 后端零新增依赖（httpx>=0.26.0 requirements.txt:32、websockets>=12.0 :129）；前端唯一新依赖 `@ricky0123/vad-web`（版本对齐参考工程 mediation-web）
- 不修改：`views/duplex/**`、`config/_voice.py`、duplex 路由注册条目；新配置独立 `_voice_demo.py`
- REST 转发形状（2026-11-10 实测）：ASR multipart `file`+`language`（无 model）；TTS JSON `input`/`voice`/`response_format:"wav"`（无 speed）；ASR 返回 language 为语言名（如 `"Chinese"`），前端透传
- WS 鉴权：query `token=<JWT>`，jose 校验（SECRET_KEY/ALGORITHM 同 deps.py:98-102），失败 close 1008；REST 用 `deps.get_current_user`
- 错误语义：上游不可达/5xx→502 `UPSTREAM_UNAVAILABLE`；上游 4xx→400；WS 并发满→`error {code:'UPSTREAM_BUSY'}` 后关闭
- Mock 默认 `VOICE_DEMO_MOCK=true`；全配置默认值见 spec §3.5
- 提交规范：`feat: ...` / `test: ...` / `chore: ...`，每任务一提交
- 测试命令：后端 `cd backend && python -m pytest tests/voice_demo -v`（venv: `backend/.venv/Scripts/python.exe`）；前端 `cd frontend && npx vitest run <file>`

---

### Task 1: 配置段 + 路由注册 + /health

**Files:**
- Create: `backend/app/config/_voice_demo.py`
- Modify: `backend/app/config/__init__.py`（import + Settings 继承列表）
- Create: `backend/app/routers/voice_demo.py`（router + /health）
- Modify: `backend/app/core/router_registry.py`（清单末尾追加）
- Test: `backend/tests/voice_demo/test_health.py`

**Interfaces:**
- Produces: `router`（APIRouter，无自身 prefix，registry 叠加 `/api/v1/voice-demo`）；`settings.VOICE_DEMO_*` 全部字段；`get_current_user` override 模式（后续所有 REST 测试复用）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/voice_demo/test_health.py
"""voice-demo REST 层测试：独立 app + dependency_overrides，不拉起 main.py。"""
import pytest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.routers import voice_demo

FAKE_USER = SimpleNamespace(user_id=1, tenant_id=1, status="active", is_admin=False)


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(voice_demo.router, prefix="/api/v1/voice-demo")
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def test_health_requires_auth():
    resp = make_client().get("/api/v1/voice-demo/health")
    assert resp.status_code == 401


def test_health_shape():
    resp = make_client().get("/api/v1/voice-demo/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mock"] is True  # VOICE_DEMO_MOCK 默认 true（spec D5）
    assert body["base_url"].startswith("http://127.0.0.1:8765")
    assert body["realtime_ws_url"] == "ws://127.0.0.1:8765/v1/realtime"
    assert body["pool"] is None or isinstance(body["pool"], dict)  # Mock/探测失败时 None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo/test_health.py -v`
Expected: FAIL（`ModuleNotFoundError: app.routers.voice_demo`）

- [ ] **Step 3: 实现**

```python
# backend/app/config/_voice_demo.py
"""语音能力 Demo 配置（VOICE_DEMO_*）— 独立于 duplex 语音线 VoiceSettings。

默认值即「Mock 本地可跑」；真实服务为同主机 s2s（2026-11-10 实测 REST+WS 全功能）。
详见 docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.5。
"""
from pydantic import BaseModel


class VoiceDemoSettings(BaseModel):
    VOICE_DEMO_ENABLED: bool = True
    VOICE_DEMO_MOCK: bool = True
    VOICE_DEMO_BASE_URL: str = "http://127.0.0.1:8765"
    VOICE_DEMO_REALTIME_WS_URL: str = "ws://127.0.0.1:8765/v1/realtime"
    VOICE_DEMO_API_KEY: str = "not-needed"
    VOICE_DEMO_ASR_MODEL: str = ""  # 空 = 不传（实测上游无需，可选透传）
    VOICE_DEMO_TTS_VOICE: str = "Aiden"
    VOICE_DEMO_TTS_LANGUAGE: str = "auto"
    VOICE_DEMO_INSTRUCTIONS: str = (
        "你是 MinWorkBuddy 的工作台助手，回答简洁口语化，帮助用户查询待办、日程与信息。"
    )
    VOICE_DEMO_CONNECT_TIMEOUT_MS: int = 5000
    VOICE_DEMO_READ_TIMEOUT_MS: int = 30000
    VOICE_DEMO_WS_IDLE_TIMEOUT_S: int = 300
    VOICE_DEMO_MAX_CONCURRENCY: int = 1
    VOICE_DEMO_UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024
```

`config/__init__.py`：在 `from ._voice import VoiceSettings` 之后加 `from ._voice_demo import VoiceDemoSettings`；`Settings` 继承列表在 `VoiceSettings,` 后插入 `VoiceDemoSettings,`。

```python
# backend/app/routers/voice_demo.py（本任务先落 /health；后续任务追加端点）
"""语音能力 Demo 网关 — spec §3.2。

router 不声明 prefix，由 router_registry 叠加 /api/v1/voice-demo。
"""
from fastapi import APIRouter, Depends

from app.config import settings
from app.deps import get_current_user
from app.services.voice_demo import gateway

router = APIRouter(tags=["语音演示"])


@router.get("/health")
async def health(_user=Depends(get_current_user)):
    """探测上游（/v1/pool）+ 返回生效配置摘要；Mock 模式 pool 为 None。"""
    pool = None
    if not settings.VOICE_DEMO_MOCK:
        pool = await gateway.probe_pool()
    return {
        "mock": settings.VOICE_DEMO_MOCK,
        "base_url": settings.VOICE_DEMO_BASE_URL,
        "realtime_ws_url": settings.VOICE_DEMO_REALTIME_WS_URL,
        "pool": pool,
        "ok": True,
    }
```

```python
# backend/app/services/voice_demo/__init__.py
"""语音 Demo 服务层：gateway（REST 转发）/ realtime_bridge（WS 桥接）/ mock（Mock 生成器）。"""
```

`router_registry.py` 清单末尾（36. SuperAgent 工作台条目后）追加：

```python
    # --- 37. 语音能力 Demo（2026-11-10，spec docs/superpowers/specs/2026-11-10-voice-demo-design.md）---
    # REST 转发 + WS 桥接 s2s /v1/realtime；Mock 默认开启，与 duplex 语音演示相互独立
    RouterSpec("app.routers.voice_demo", prefix=f"{API_V1_PREFIX}/voice-demo", tags=["语音演示"]),
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo/test_health.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/config/_voice_demo.py backend/app/config/__init__.py backend/app/routers/voice_demo.py backend/app/services/voice_demo/__init__.py backend/app/core/router_registry.py backend/tests/voice_demo/test_health.py
git commit -m "feat(voice-demo): 配置段 + 路由注册 + health 端点"
```

---

### Task 2: Mock 生成器

**Files:**
- Create: `backend/app/services/voice_demo/mock.py`
- Test: `backend/tests/voice_demo/test_mock.py`

**Interfaces:**
- Produces:
  - `mock_asr_text(language: str) -> dict` → `{"text": str, "language": str}`
  - `mock_tts_wav_bytes(duration_s: float = 1.5) -> bytes`（24kHz mono 16bit，wave 模块可解析）
  - `MockRealtimeScript`：`async run(ws_send: Callable[[dict], Awaitable], client_events: AsyncIterator[dict]) -> None`——消费客户端事件、按序列回放服务端事件（事件形状与真实 s2s 同构）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/voice_demo/test_mock.py
import io, wave
import pytest
from app.services.voice_demo import mock


def test_asr_shape():
    r = mock.mock_asr_text("auto")
    assert set(r) == {"text", "language"} and r["text"]


def test_tts_wav_parsable():
    raw = mock.mock_tts_wav_bytes()
    w = wave.open(io.BytesIO(raw), "rb")
    assert w.getframerate() == 24000 and w.getnchannels() == 1 and w.getsampwidth() == 2
    assert w.getnframes() > 0


@pytest.mark.asyncio
async def test_realtime_script_round():
    """一轮：append 累计 → speech_started/stopped → 转录 → audio deltas → response.done。"""
    sent: list = []
    async def client_events():
        # 累计 0.6s 音频（16k*2*0.6=19200B base64 分两片）触发轮次
        for i in range(2):
            yield {"type": "input_audio_buffer.append", "audio": "A" * 9600}
        yield {"type": "input_audio_buffer.commit"}  # Mock 不严格依赖 VAD，commit 兜底

    script = mock.MockRealtimeScript()
    await script.run(lambda e: sent.append(e) or asyncio.sleep(0), client_events())
    types = [e["type"] for e in sent]
    assert "session.created" in types
    assert "input_audio_buffer.speech_started" in types
    assert "input_audio_buffer.speech_stopped" in types
    assert any(t.startswith("response.audio.delta") or t == "response.audio.delta" for t in types)
    assert types[-1] == "response.done"

import asyncio  # noqa: E402  （置于文件底部亦可，放顶部更规范——实现时移到 import 区）
```

（实现时把 `import asyncio` 移到文件顶部 import 区。）

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo/test_mock.py -v`
Expected: FAIL（`cannot import name 'mock'`）

- [ ] **Step 3: 实现**

```python
# backend/app/services/voice_demo/mock.py
"""Mock 生成器 — 无真实服务时的完整链路（spec §3.4）。

事件形状与真实 s2s 逐一同构，前端联调不感知 Mock 与真实差异。
"""
import asyncio
import io
import math
import struct
import wave
from typing import AsyncIterator, Awaitable, Callable, Dict, List

SAMPLE_RATE = 24000


def mock_asr_text(language: str = "auto") -> Dict:
    return {"text": "你好，请帮我查看今天下午三点的会议安排。", "language": language or "zh"}


def mock_tts_wav_bytes(duration_s: float = 1.5) -> bytes:
    """440/660Hz 交替正弦提示音，带 20ms 起音 + 50ms 收尾包络。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        n = int(SAMPLE_RATE * duration_s)
        for i in range(n):
            t = i / SAMPLE_RATE
            freq = 440.0 if (t % 0.5) < 0.25 else 660.0
            env = min(1.0, t / 0.02, max(0.0, (duration_s - t) / 0.05))
            v = int(0.35 * 32767 * env * math.sin(2 * math.pi * freq * t))
            w.writeframesraw(struct.pack("<h", v))
    return buf.getvalue()


class MockRealtimeScript:
    """扮演 s2s /v1/realtime 服务端：消费客户端事件，回放一轮对话脚本。

    触发规则：append 累计 >= 19200 字节（≈0.6s@16k/16bit）或收到
    input_audio_buffer.commit / response.create 时开始一轮；
    response.cancel → 立即 response.done(status=cancelled)。
    """

    REPLIES: List[str] = [
        "今天下午三点有一个项目评审会，地点在三楼会议室。",
        "你今天完成了 8 项待办中的 5 项，还剩 3 项。",
        "好的，我记下了，稍后会提醒你。",
    ]
    _TRIGGER_BYTES = 19200
    _DELTA_CHUNKS = 8  # 每轮 audio.delta 片数

    def __init__(self) -> None:
        self._accumulated = 0
        self._turn = 0

    async def run(self, send: Callable[[Dict], Awaitable], client_events: AsyncIterator[Dict]) -> None:
        await send({"type": "session.created",
                    "session": {"id": "mock-session", "voice": "Aiden"}})
        cancelled = False
        async for evt in client_events:
            etype = evt.get("type", "")
            if etype == "input_audio_buffer.append":
                self._accumulated += len(evt.get("audio", ""))
            elif etype == "response.cancel":
                await send({"type": "response.done",
                            "response": {"status": "cancelled"}})
                cancelled = True
                continue
            elif etype in ("response.create",):
                pass  # 直接触发
            if etype in ("input_audio_buffer.append", "input_audio_buffer.commit", "response.create"):
                if self._accumulated >= self._TRIGGER_BYTES or etype != "input_audio_buffer.append":
                    self._accumulated = 0
                    await self._one_turn(send, cancelled)
                    cancelled = False

    async def _one_turn(self, send: Callable[[Dict], Awaitable], cancelled: bool) -> None:
        text = self.REPLIES[self._turn % len(self.REPLIES)]
        self._turn += 1
        await send({"type": "input_audio_buffer.speech_started"})
        await asyncio.sleep(0.05)
        await send({"type": "input_audio_buffer.speech_stopped"})
        await send({"type": "conversation.item.input_audio_transcription.completed",
                    "transcript": "现在几点了？顺便看看我的日程。"})
        if cancelled:
            await send({"type": "response.done", "response": {"status": "cancelled"}})
            return
        await send({"type": "response.created",
                    "response": {"id": f"mock-resp-{self._turn}"}})
        await send({"type": "response.audio_transcription.delta", "delta": text})
        chunk = "AAAA"  # base64(静音 PCM16)
        for i in range(self._DELTA_CHUNKS):
            await send({"type": "response.audio.delta", "delta": chunk})
            await asyncio.sleep(0.02)
        await send({"type": "response.audio.done"})
        await send({"type": "response.done", "response": {"status": "completed"}})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo/test_mock.py -v`
Expected: PASS（3 passed；若缺 pytest-asyncio 则在 tests/voice_demo/ 加 `pytest.ini` 内容 `[pytest] asyncio_mode = auto` 或确认工程已有 async 配置——先查 `backend/pytest.ini` / `pyproject.toml` 有无 `asyncio_mode`，没有则本测试文件顶部加 `@pytest.mark.asyncio` 且 `requirements-dev.txt` 需含 pytest-asyncio，已有则跳过）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voice_demo/mock.py backend/tests/voice_demo/test_mock.py
git commit -m "feat(voice-demo): Mock 生成器（ASR 样例/TTS WAV/Realtime 事件脚本）"
```

---

### Task 3: REST 网关（ASR / TTS 转发）

**Files:**
- Create: `backend/app/services/voice_demo/gateway.py`
- Modify: `backend/app/routers/voice_demo.py`（追加 2 端点）
- Test: `backend/tests/voice_demo/test_rest.py`

**Interfaces:**
- Consumes: Task 1 的 router/settings；Task 2 的 mock 函数
- Produces:
  - `gateway.probe_pool() -> Optional[dict]`（GET /v1/pool，失败返回 None）
  - `gateway.transcribe(data: bytes, filename: str, language: str) -> dict`
  - `gateway.synthesize(payload: dict) -> bytes`
  - 异常 `UpstreamUnavailable` / `UpstreamBadRequest`（routers 映射 502/400）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/voice_demo/test_rest.py
import io, wave
import httpx, pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.routers import voice_demo
from app.services.voice_demo import gateway
from tests.voice_demo.test_health import FAKE_USER, make_client  # 复用


def test_asr_mock():
    data = mock_wav_bytes()
    r = make_client().post("/api/v1/voice-demo/asr/transcribe",
                           files={"file": ("a.wav", data, "audio/wav")},
                           data={"language": "auto"})
    assert r.status_code == 200
    body = r.json()
    assert {"text", "language", "cost_ms"} <= set(body)


def test_tts_mock_wav():
    r = make_client().post("/api/v1/voice-demo/tts/synthesize",
                           json={"text": "你好", "voice": "Aiden", "response_format": "wav"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    w = wave.open(io.BytesIO(r.content), "rb")
    assert w.getnframes() > 0


def test_asr_forward(monkeypatch):
    """httpx MockTransport 验证转发形状（multipart file+language，无 model）。"""
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = request.content
        return httpx.Response(200, json={"text": "今天天气怎么样？", "language": "Chinese"})
    monkeypatch.setattr(gateway, "_transport", httpx.MockTransport(handler))
    r = make_client().post("/api/v1/voice-demo/asr/transcribe",
                           files={"file": ("a.wav", mock_wav_bytes(), "audio/wav")},
                           data={"language": "auto"})
    assert r.json()["text"] == "今天天气怎么样？"
    assert captured["path"] == "/v1/audio/transcriptions"
    assert b"model" not in captured["body"]  # 默认不传 model（实测约定）


def test_upstream_5xx_maps_502(monkeypatch):
    monkeypatch.setattr(gateway, "_transport",
                        httpx.MockTransport(lambda req: httpx.Response(500, text="boom")))
    r = make_client().post("/api/v1/voice-demo/tts/synthesize",
                           json={"text": "x", "voice": "Aiden", "response_format": "wav"})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "UPSTREAM_UNAVAILABLE"


def mock_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)  # 0.1s 静音
    return buf.getvalue()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo/test_rest.py -v`
Expected: FAIL（`gateway` 无 `_transport`/`transcribe` 等）

- [ ] **Step 3: 实现**

```python
# backend/app/services/voice_demo/gateway.py
"""REST 上游客户端 — httpx 转发（spec §3.2/§3.6）。

转发形状为 2026-11-10 实测约定：ASR multipart(file+language, 无 model)、
TTS JSON(input/voice/response_format:"wav")；5xx/不可达→UPSTREAM_UNAVAILABLE。
"""
from typing import Optional

import httpx
from loguru import logger

from app.config import settings


class UpstreamUnavailable(Exception):
    """上游不可达 / 5xx → 502。"""


class UpstreamBadRequest(Exception):
    """上游 4xx → 400（附上游 message）。"""


def _transport() -> Optional[httpx.AsyncBaseTransport]:
    """测试注入点（httpx.MockTransport）；生产为 None。"""
    return None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.VOICE_DEMO_BASE_URL,
        timeout=httpx.Timeout(settings.VOICE_DEMO_CONNECT_TIMEOUT_MS / 1000,
                              read=settings.VOICE_DEMO_READ_TIMEOUT_MS / 1000),
        headers={"Authorization": f"Bearer {settings.VOICE_DEMO_API_KEY}"}
        if settings.VOICE_DEMO_API_KEY else {},
        transport=_transport(),
    )


async def probe_pool() -> Optional[dict]:
    """GET /v1/pool；任何失败返回 None（health 降级展示）。"""
    try:
        async with _client() as c:
            r = await c.get("/v1/pool")
        return r.json() if r.status_code == 200 else None
    except httpx.HTTPError as exc:
        logger.warning(f"voice-demo pool 探测失败: {exc}")
        return None


async def transcribe(data: bytes, filename: str, language: str) -> dict:
    form = {"language": language}
    if settings.VOICE_DEMO_ASR_MODEL:
        form["model"] = settings.VOICE_DEMO_ASR_MODEL
    try:
        async with _client() as c:
            r = await c.post("/v1/audio/transcriptions", data=form,
                             files={"file": (filename, data, "application/octet-stream")})
    except httpx.HTTPError as exc:
        logger.warning(f"voice-demo ASR 转发失败: {exc}")
        raise UpstreamUnavailable(str(exc)) from exc
    return _unwrap_json(r)


async def synthesize(payload: dict) -> bytes:
    try:
        async with _client() as c:
            r = await c.post("/v1/audio/speech", json=payload)
    except httpx.HTTPError as exc:
        logger.warning(f"voice-demo TTS 转发失败: {exc}")
        raise UpstreamUnavailable(str(exc)) from exc
    if r.status_code >= 500:
        raise UpstreamUnavailable(r.text[:300])
    if r.status_code >= 400:
        raise UpstreamBadRequest(r.text[:300])
    return r.content


def _unwrap_json(r: httpx.Response) -> dict:
    if r.status_code >= 500:
        raise UpstreamUnavailable(r.text[:300])
    if r.status_code >= 400:
        raise UpstreamBadRequest(r.text[:300])
    return r.json()
```

`routers/voice_demo.py` 追加（imports 区补 `Response, UploadFile, File, Form, HTTPException` 与 `from app.services.voice_demo import gateway, mock`）：

```python
@router.post("/asr/transcribe")
async def asr_transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    _user=Depends(get_current_user),
):
    """multipart 转发 ASR（实测形状）→ {text, language, cost_ms}。"""
    data = await file.read()
    if len(data) > settings.VOICE_DEMO_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="音频文件过大（>25MB）")
    import time as _time
    t0 = _time.perf_counter()
    if settings.VOICE_DEMO_MOCK:
        import asyncio as _asyncio
        await _asyncio.sleep(0.3)
        result = mock.mock_asr_text(language)
    else:
        try:
            result = await gateway.transcribe(data, file.filename or "audio.wav", language)
        except gateway.UpstreamUnavailable as exc:
            raise HTTPException(status_code=502, detail={"code": "UPSTREAM_UNAVAILABLE", "message": str(exc)})
        except gateway.UpstreamBadRequest as exc:
            raise HTTPException(status_code=400, detail={"code": "UPSTREAM_REJECTED", "message": str(exc)})
    return {**result, "cost_ms": int((_time.perf_counter() - t0) * 1000)}


@router.post("/tts/synthesize")
async def tts_synthesize(payload: dict, _user=Depends(get_current_user)):
    """JSON 转发 TTS（input/voice/response_format，speed 原型占位不转发——实测无此字段）→ WAV。"""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text 不能为空")
    body = {"input": text,
            "voice": payload.get("voice") or settings.VOICE_DEMO_TTS_VOICE,
            "response_format": "wav"}  # 实测仅支持 wav
    if settings.VOICE_DEMO_MOCK:
        content = mock.mock_tts_wav_bytes()
    else:
        try:
            content = await gateway.synthesize(body)
        except gateway.UpstreamUnavailable as exc:
            raise HTTPException(status_code=502, detail={"code": "UPSTREAM_UNAVAILABLE", "message": str(exc)})
        except gateway.UpstreamBadRequest as exc:
            raise HTTPException(status_code=400, detail={"code": "UPSTREAM_REJECTED", "message": str(exc)})
    return Response(content=content, media_type="audio/wav",
                    headers={"Content-Disposition": 'inline; filename="tts.wav"'})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo -v`
Expected: PASS（Task1-3 全部）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voice_demo/gateway.py backend/app/routers/voice_demo.py backend/tests/voice_demo/test_rest.py
git commit -m "feat(voice-demo): REST 网关 ASR/TTS 转发（实测形状 + Mock）"
```

---

### Task 4: WS 桥接（Mock 会话 + 真实上游泵 + 并发闸）

**Files:**
- Create: `backend/app/services/voice_demo/realtime_bridge.py`
- Modify: `backend/app/routers/voice_demo.py`（追加 `/ws`）
- Test: `backend/tests/voice_demo/test_ws.py`

**Interfaces:**
- Consumes: Task 2 的 `MockRealtimeScript`；settings 的 `VOICE_DEMO_REALTIME_WS_URL/_INSTRUCTIONS/_TTS_VOICE/_MAX_CONCURRENCY/_WS_IDLE_TIMEOUT_S`
- Produces:
  - `_jwt_user_id(token: str) -> Optional[int]`（jose 校验，同 deps.py:98-102 逻辑）
  - `build_session_update() -> dict`（instructions + voice + server_vad + interrupt_response）
  - `run_bridge(websocket: WebSocket)`（真实模式双向泵）/ `run_mock_session(websocket: WebSocket)`（Mock 会话）
  - `BRIDGE_SEMAPHORE`（asyncio.Semaphore(VOICE_DEMO_MAX_CONCURRENCY)）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/voice_demo/test_ws.py
import pytest
from jose import jwt as jose_jwt

from app.config import settings
from tests.voice_demo.test_health import make_client


def _token(user_id: int = 1) -> str:
    return jose_jwt.encode({"sub": str(user_id)}, settings.SECRET_KEY,
                           algorithms=[settings.ALGORITHM])


def test_ws_bad_token_closed_1008():
    with pytest.raises(Exception):  # TestClient 对 accept 前 close 抛 WebSocketDisconnect
        with make_client().websocket_connect("/api/v1/voice-demo/ws?token=bad") as ws:
            ws.receive_json()


def test_ws_mock_session_round():
    with make_client().websocket_connect(f"/api/v1/voice-demo/ws?token={_token()}") as ws:
        created = ws.receive_json()
        assert created["type"] == "session.created"
        # 两片音频触发 Mock 轮次（累计 >= 19200 字节）
        for _ in range(2):
            ws.send_json({"type": "input_audio_buffer.append", "audio": "A" * 9600})
        ws.send_json({"type": "input_audio_buffer.commit"})
        seq = [ws.receive_json() for _ in range(8)]
        types = [e["type"] for e in seq]
        assert "input_audio_buffer.speech_started" in types
        assert "response.done" in types
        ws.send_json({"type": "response.cancel"})
        last = ws.receive_json()
        assert last["type"] == "response.done"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo/test_ws.py -v`
Expected: FAIL（/ws 不存在）

- [ ] **Step 3: 实现**

```python
# backend/app/services/voice_demo/realtime_bridge.py
"""WS 桥接 — 浏览器 ↔ 网关 ↔ s2s /v1/realtime（spec §3.3）。

Mock 模式：MockRealtimeScript 本地扮演上游；真实模式：websockets 双向泵，
connect 注入一次 session.update，其余纯透传。
"""
import asyncio
import json
from typing import Optional

import websockets
from fastapi import WebSocket
from jose import jwt, JWTError
from loguru import logger

from app.config import settings
from app.services.voice_demo.mock import MockRealtimeScript

BRIDGE_SEMAPHORE = asyncio.Semaphore(settings.VOICE_DEMO_MAX_CONCURRENCY)


def _jwt_user_id(token: str) -> Optional[int]:
    """query token → user_id；失败返回 None（调用方 close 1008）。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub else None
    except (JWTError, ValueError, TypeError):
        return None


def build_session_update() -> dict:
    """connect 注入：人设 + 音色 + server_vad + 可打断（spec §3.3）。"""
    return {
        "type": "session.update",
        "session": {
            "instructions": settings.VOICE_DEMO_INSTRUCTIONS,
            "voice": settings.VOICE_DEMO_TTS_VOICE,
            "turn_detection": {"type": "server_vad", "interrupt_response": True},
        },
    }


async def run_mock_session(websocket: WebSocket) -> None:
    """Mock 会话：把 WebSocket 收包适配成 AsyncIterator 交给脚本。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def reader() -> None:
        try:
            while True:
                queue.put_nowait(json.loads(await websocket.receive_text()))
        except Exception:
            queue.put_nowait(None)  # 终止哨兵

    async def client_events():
        while True:
            evt = await queue.get()
            if evt is None:
                return
            yield evt

    async def send(evt: dict) -> None:
        await websocket.send_text(json.dumps(evt, ensure_ascii=False))

    reader_task = asyncio.create_task(reader())
    try:
        await MockRealtimeScript().run(send, client_events())
    finally:
        reader_task.cancel()


async def run_bridge(websocket: WebSocket) -> None:
    """真实模式：websockets 连上游，双向泵 + 空闲超时。"""
    idle = settings.VOICE_DEMO_WS_IDLE_TIMEOUT_S
    async with websockets.connect(settings.VOICE_DEMO_REALTIME_WS_URL,
                                  open_timeout=settings.VOICE_DEMO_CONNECT_TIMEOUT_MS / 1000) as up:
        await up.send(json.dumps(build_session_update(), ensure_ascii=False))

        async def up2down() -> None:
            while True:
                msg = await asyncio.wait_for(up.recv(), timeout=idle)
                await websocket.send_text(msg if isinstance(msg, str) else msg.decode())

        async def down2up() -> None:
            while True:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=idle)
                await up.send(raw)

        tasks = [asyncio.create_task(up2down()), asyncio.create_task(down2up())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        exc = next(iter(done)).exception()
        if exc and not isinstance(exc, (asyncio.TimeoutError, TimeoutError,
                                        asyncio.CancelledError, WebSocketDisconnect if False else Exception)):
            logger.warning(f"voice-demo 桥接结束: {exc!r}")
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            await websocket.send_text(json.dumps({"type": "error", "code": "UPSTREAM_TIMEOUT"}))
        elif exc:
            await websocket.send_text(json.dumps(
                {"type": "error", "code": "UPSTREAM_DISCONNECTED", "message": str(exc)[:200]}))
```

（注：`WebSocketDisconnect if False else Exception` 为笔误防护——实现时直接写 `except Exception` 分支判定，见下方 routers 层；bridge 内 `exc` 判定只保留 Timeout 与其他两类。）

`routers/voice_demo.py` 追加：

```python
from fastapi import WebSocket, WebSocketDisconnect
from app.services.voice_demo import realtime_bridge as bridge


@router.websocket("/ws")
async def voice_demo_ws(websocket: WebSocket):
    """WS 桥接入口：query JWT 鉴权 → 并发闸 → Mock 会话或真实泵。"""
    user_id = bridge._jwt_user_id(websocket.query_params.get("token", ""))
    if user_id is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    if settings.VOICE_DEMO_MOCK:
        await bridge.run_mock_session(websocket)
        return
    acquired = False
    try:
        acquired = bridge.BRIDGE_SEMAPHORE.locked() is False and \
            await asyncio.wait_for(bridge.BRIDGE_SEMAPHORE.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        pass
    if not acquired:
        await websocket.send_text(json.dumps({"type": "error", "code": "UPSTREAM_BUSY"}))
        await websocket.close(code=1013)
        return
    try:
        await bridge.run_bridge(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        bridge.BRIDGE_SEMAPHORE.release()
```

（imports 区补 `asyncio, json`；`locked() is False and await acquire()` 的写法在单信号量下等价于「非阻塞抢锁」，实现时可简化为 try-acquire。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo -v`
Expected: PASS（Task1-4 全部）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voice_demo/realtime_bridge.py backend/app/routers/voice_demo.py backend/tests/voice_demo/test_ws.py
git commit -m "feat(voice-demo): WS 桥接（query JWT + Mock 会话 + 真实泵 + 并发闸）"
```

---

### Task 5: 前端 API 层 + 路由 + 页面骨架 + 手册 Tab

**Files:**
- Create: `frontend/src/api/voiceDemo.ts`
- Create: `frontend/src/views/voice-demo/VoiceDemo.vue`（骨架：Tab + 顶栏状态 + 主题按钮）
- Create: `frontend/src/views/voice-demo/components/GuidePanel.vue`
- Modify: `frontend/src/router/index.ts`（children 追加，duplex/voice-demo 条目 `:130-136` 之后）
- Test: `frontend/src/api/__tests__/voiceDemo.spec.ts`

**Interfaces:**
- Produces:
  - `getVoiceDemoHealth(): Promise<{mock:boolean; base_url:string; realtime_ws_url:string; pool:any}>`
  - `transcribeAsr(form: FormData): Promise<{text:string; language:string; cost_ms:number}>`
  - `synthesizeTts(p:{text:string; voice:string}): Promise<Blob>`
  - `buildVoiceDemoWsUrl(token: string): string`
  - 路由 `/voice-demo`（name `VoiceDemo`，meta `{title:'语音演示', icon:'AudioOutlined'}`）

- [ ] **Step 1: 安装 vad-web（对齐参考工程版本，实现时读 `D:\work\mediation_platform\mediation-web\package.json` 取精确版本）**

```bash
cd frontend && npm install @ricky0123/vad-web@<版本>
```

- [ ] **Step 2: 写失败测试**

```ts
// frontend/src/api/__tests__/voiceDemo.spec.ts
import { describe, it, expect, vi } from 'vitest'

vi.mock('@/utils/auth', () => ({ getToken: () => 'jwt-x' }))

describe('voiceDemo api', () => {
  it('buildVoiceDemoWsUrl 携带 token query 并转 ws 协议', async () => {
    const { buildVoiceDemoWsUrl } = await import('../voiceDemo')
    const url = buildVoiceDemoWsUrl('jwt-x')
    expect(url.startsWith('ws')).toBe(true)
    expect(url).toContain('/api/v1/voice-demo/ws')
    expect(url).toContain('token=jwt-x')
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `cd frontend && npx vitest run src/api/__tests__/voiceDemo.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 4: 实现**

```ts
// frontend/src/api/voiceDemo.ts
/** 语音 Demo API（spec §3.2）— REST 经 @/utils/request，WS URL 单独构造（token query，对齐 api/voice.ts 先例）。 */
import request from '@/utils/request'

const BASE = '/api/v1/voice-demo'

export interface VoiceDemoHealth {
  mock: boolean
  base_url: string
  realtime_ws_url: string
  pool: { size: number; in_use: number; units: string[] } | null
}

export function getVoiceDemoHealth() {
  return request.get<never, VoiceDemoHealth>(`${BASE}/health`)
}

export function transcribeAsr(form: FormData) {
  return request.post<never, { text: string; language: string; cost_ms: number }>(
    `${BASE}/asr/transcribe`, form)
}

export function synthesizeTts(p: { text: string; voice: string }) {
  // blob 返回：audio/wav（实测仅 wav）
  return request.post<never, Blob>(`${BASE}/tts/synthesize`, p, { responseType: 'blob' })
}

/** 构建语音对话 WS URL：?token=<JWT>（对齐 duplex/voice 网关先例，spec D3） */
export function buildVoiceDemoWsUrl(token: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const url = new URL(`${base}${BASE}/ws`, origin)
  url.searchParams.set('token', token)
  return url.toString().replace(/^http/, 'ws')
}

/** 9 音色按语种分组（实现时与参考前端核对一遍分组，spec §7.4） */
export const VOICES_BY_LANG: Record<string, string[]> = {
  中文: ['Vivian', 'Serena', 'Uncle_Fu', 'Dylan'],
  英文: ['Eric', 'Ryan', 'Aiden'],
  日文: ['Ono_Anna'],
  韩文: ['Sohee'],
}
```

- [ ] **Step 5: 运行确认通过；实现页面骨架与路由**

`router/index.ts` children 追加（`duplex/voice-demo` 条目后）：

```ts
      {
        // 语音能力 Demo（2026-11-10，spec docs/superpowers/specs/2026-11-10-voice-demo-design.md）
        path: 'voice-demo',
        name: 'VoiceDemo',
        component: () => import('@/views/voice-demo/VoiceDemo.vue'),
        meta: { title: '语音演示', icon: 'AudioOutlined' }
      },
```

`VoiceDemo.vue` 骨架（逻辑完整，样式从原型 `:root` 别名映射到工程 token；a-tabs 默认 `activeKey="asr"`，顺序 asr→tts→s2s→guide，D2）：

```vue
<!-- frontend/src/views/voice-demo/VoiceDemo.vue -->
<template>
  <div class="voice-demo">
    <a-card>
      <div class="vd-head">
        <div>
          <h2>语音能力演示</h2>
          <div class="vd-desc">后端 FastAPI 代理 / WS 桥接 · speech-to-speech（VAD→STT→LLM→TTS）· Mock 本地可跑</div>
        </div>
        <div class="vd-pills">
          <a-tag :color="health?.mock ? 'warning' : 'success'">
            {{ health?.mock ? 'Mock 开启' : '真实服务' }}
          </a-tag>
          <a-tag>BASE: {{ health?.base_url || '—' }}</a-tag>
          <a-tooltip title="切换深色/浅色主题（useAppStore）">
            <a-button size="small" @click="app.toggleTheme()">{{ app.isDark ? '☀️ 浅色' : '🌙 深色' }}</a-button>
          </a-tooltip>
        </div>
      </div>
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="asr" tab="📝 语音转写（ASR）"><AsrPanel /></a-tab-pane>
        <a-tab-pane key="tts" tab="🔊 语音合成（TTS）"><TtsPanel /></a-tab-pane>
        <a-tab-pane key="s2s" tab="🗣 语音对话（实时 S2S）"><S2sPanel /></a-tab-pane>
        <a-tab-pane key="guide" tab="📖 使用手册"><GuidePanel /></a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAppStore } from '@/stores/app'
import { getVoiceDemoHealth, type VoiceDemoHealth } from '@/api/voiceDemo'
import AsrPanel from './components/AsrPanel.vue'
import TtsPanel from './components/TtsPanel.vue'
import S2sPanel from './components/S2sPanel.vue'
import GuidePanel from './components/GuidePanel.vue'

const app = useAppStore()
const activeTab = ref('asr') // D2：ASR 默认选中
const health = ref<VoiceDemoHealth | null>(null)
onMounted(async () => { try { health.value = await getVoiceDemoHealth() } catch { /* 未探测到时展示占位 */ } })
</script>

<style scoped>
.vd-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.vd-desc{color:var(--fg-secondary);font-size:13px}
.vd-pills{display:flex;gap:8px;align-items:center}
</style>
```

`GuidePanel.vue`：内容 1:1 从原型 `voice-demo-preview.html` 手册 Tab（`<div class="panel guide" id="panel-guide">` 段，约 :314-377）迁移为 antd 排版（h3/p/table/li），包括实测后的「切换真实服务（2026-11-10 已实测）」与「主题」小节——迁移内容即占位实现，不是占位符。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/voiceDemo.ts frontend/src/api/__tests__/voiceDemo.spec.ts frontend/src/views/voice-demo frontend/src/router/index.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(voice-demo): 前端 API 层 + 路由 + 页面骨架 + 手册 Tab"
```

---

### Task 6: ASR Tab（上传 + VAD 录音）与 TTS Tab

**Files:**
- Create: `frontend/src/views/voice-demo/components/AsrPanel.vue`
- Create: `frontend/src/views/voice-demo/components/TtsPanel.vue`
- Create: `frontend/src/views/voice-demo/composables/useVadRecorder.ts`
- Test: `frontend/src/views/voice-demo/__tests__/useVadRecorder.spec.ts`

**Interfaces:**
- Consumes: Task 5 的 `transcribeAsr` / `synthesizeTts` / `VOICES_BY_LANG`；`utils/audioDsp.ts`（`encodeFloatToPcm16`、`rmsDb`）
- Produces: `useVadRecorder({ onSegment(blob: Blob, startMs: number, endMs: number) })` → `{ start(), stop(), isRecording }`（16k mono WAV 分段，VAD 参数对齐参考：positive 0.5 / negative 0.35 / minSpeech 250 / redemption 700）

- [ ] **Step 1: 写失败测试（mock vad-web）**

```ts
// frontend/src/views/voice-demo/__tests__/useVadRecorder.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const micCallbacks: Record<string, (e: any) => void> = {}
vi.mock('@ricky0123/vad-web', () => ({
  MicVAD: {
    new: vi.fn(async (_opts: any, cbs: any) => {
      Object.assign(micCallbacks, cbs)
      return { start: vi.fn(), stop: vi.fn(), pause: vi.fn() }
    }),
  },
}))

describe('useVadRecorder', () => {
  beforeEach(() => vi.clearAllMocks())

  it('speech end 时回调分段（startMs/endMs）', async () => {
    const { useVadRecorder } = await import('../useVadRecorder')
    const segments: any[] = []
    const rec = useVadRecorder({ onSegment: (b, s, e) => segments.push({ s, e }) })
    await rec.start()
    micCallbacks.onSpeechStart?.()
    micCallbacks.onSpeechEnd?.(new Float32Array(16000))
    expect(segments.length).toBe(1)
    expect(segments[0].e).toBeGreaterThanOrEqual(segments[0].s)
  })
})
```

- [ ] **Step 2: 运行确认失败** → **Step 3: 实现** → **Step 4: 确认通过**

```ts
// frontend/src/views/voice-demo/composables/useVadRecorder.ts
/** ASR 录音 VAD 分段（参考工程同款 @ricky0123/vad-web；16k mono WAV 分段回调）。 */
import { ref } from 'vue'
import { MicVAD } from '@ricky0123/vad-web'

export interface VadSegment { blob: Blob; startMs: number; endMs: number }

/** Float32 → 16kHz mono WAV（AudioBuffer 采样率由 getUserMedia constrain 到 16k） */
export function floatToWav(samples: Float32Array, sampleRate = 16000): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buf)
  const ws = (off: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)) }
  ws(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); ws(8, 'WAVE')
  ws(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  ws(36, 'data'); view.setUint32(40, samples.length * 2, true)
  let off = 44
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

export function useVadRecorder(opts: { onSegment: (blob: Blob, startMs: number, endMs: number) => void }) {
  const isRecording = ref(false)
  let vad: { stop: () => void } | null = null
  let segStart = 0

  async function start() {
    vad = await MicVAD.new({
      positiveSpeechThreshold: 0.5,
      negativeSpeechThreshold: 0.35,
      minSpeechFrames: Math.ceil((250 / 128) * (16000 / 1000)), // minSpeechMs≈250 对齐参考
      redemptionFrames: Math.ceil((700 / 32)),                  // redemptionMs≈700
    }, {
      onSpeechStart: () => { segStart = performance.now() },
      onSpeechEnd: (audio: Float32Array) => {
        opts.onSegment(floatToWav(audio), Math.round(segStart), Math.round(performance.now()))
      },
    })
    vad.start()
    isRecording.value = true
  }
  function stop() { vad?.stop(); vad = null; isRecording.value = false }
  return { start, stop, isRecording }
}
```

`AsrPanel.vue` 逻辑（template 对齐原型 Tab1 结构）：上传模式 `input[type=file]` → `transcribeAsr(form)`；录音模式 `useVadRecorder` → 每段 `transcribeAsr` 追加结果卡（段起止 ms + text）；结果区渲染分段时间戳；波形条用 `rmsDb` 驱动（可选，v0 用 CSS 动画占位亦可，不阻塞）。

`TtsPanel.vue` 逻辑：文本 textarea（默认示例文案同原型）+ 音色 `a-select`（`VOICES_BY_LANG` 分组 + 自定义输入）+ 语速/格式展示禁用态（标注「服务端暂未生效——实测仅 wav」）→ `synthesizeTts` → `URL.createObjectURL(blob)` 播放 + `a` 下载（filename `tts.wav`）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/voice-demo
git commit -m "feat(voice-demo): ASR Tab（上传+VAD 录音）与 TTS Tab"
```

---

### Task 7: S2S 对话 Tab（状态机 + 音频管线 + 事件流）

**Files:**
- Create: `frontend/src/views/voice-demo/composables/useRealtimeS2s.ts`
- Create: `frontend/src/views/voice-demo/components/S2sPanel.vue`
- Test: `frontend/src/views/voice-demo/__tests__/useRealtimeS2s.spec.ts`

**Interfaces:**
- Consumes: Task 5 `buildVoiceDemoWsUrl` + `getToken()`（`@/utils/auth`）；`audioDsp` 的 `createStreamingResampler` / `encodeFloatToPcm16` / `decodePcm16ToFloat` / `createPlaybackChain`
- Produces: `useRealtimeS2s()` → `{ state: Ref<'idle'|'connecting'|'listening'|'responding'|'closed'>, messages: Ref<Msg[]>, events: Ref<Ev[]>, connect(), disconnect(), interrupt(), sendSimText(text) }`；`Msg = { role:'user'|'assistant'; text:string; partial?:boolean; interrupted?:boolean }`；`Ev = { dir:'in'|'out'; type:string; at:number }`

- [ ] **Step 1: 写失败测试（stub WebSocket + stub AudioContext）**

```ts
// frontend/src/views/voice-demo/__tests__/useRealtimeS2s.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

class FakeWS {
  static last: FakeWS | null = null
  sent: string[] = []
  onopen: any = null; onmessage: any = null; onclose: any = null; onerror: any = null
  constructor() { FakeWS.last = this }
  send(d: string) { this.sent.push(d) }
  close() { this.onclose?.() }
  emit(data: any) { this.onmessage?.({ data: JSON.stringify(data) }) }
}
vi.stubGlobal('WebSocket', FakeWS as any)
vi.mock('@/utils/auth', () => ({ getToken: () => 'jwt-x' }))
vi.mock('@/api/voiceDemo', async (orig) => ({
  ...(await orig<any>()),
  buildVoiceDemoWsUrl: () => 'ws://fake/ws?token=jwt-x',
}))
// 音频层全部 stub（状态机测试不依赖真实解码）
vi.mock('@/utils/audioDsp', () => ({
  createStreamingResampler: () => ({ push: () => new Float32Array(0), flush: () => new Float32Array(0) }),
  encodeFloatToPcm16: () => new Int16Array(0),
  decodePcm16ToFloat: () => new Float32Array(0),
  createPlaybackChain: () => ({}),
}))

import { useRealtimeS2s } from '../useRealtimeS2s'

const B64 = 'AAAA' // base64 静音

describe('useRealtimeS2s 状态机', () => {
  beforeEach(() => { FakeWS.last = null })

  it('connect → session.created → listening；脚本轮次 → responding → listening', async () => {
    const s2s = useRealtimeS2s()
    s2s.connect()
    FakeWS.last!.onopen?.()
    FakeWS.last!.emit({ type: 'session.created', session: { id: 's1' } })
    expect(s2s.state.value).toBe('listening')

    FakeWS.last!.emit({ type: 'input_audio_buffer.speech_started' })
    FakeWS.last!.emit({ type: 'conversation.item.input_audio_transcription.completed', transcript: '现在几点了？' })
    FakeWS.last!.emit({ type: 'response.created', response: {} })
    expect(s2s.state.value).toBe('responding')
    FakeWS.last!.emit({ type: 'response.audio_transcription.delta', delta: '你好' })
    FakeWS.last!.emit({ type: 'response.audio.delta', delta: B64 })
    FakeWS.last!.emit({ type: 'response.done', response: { status: 'completed' } })
    expect(s2s.state.value).toBe('listening')
    const texts = s2s.messages.value.map(m => `${m.role}:${m.text}`)
    expect(texts).toContain('user:现在几点了？')
    expect(texts).toContain('assistant:你好')
    // 事件流已记录双向事件
    expect(s2s.events.value.some(e => e.dir === 'out' && e.type === 'session.update')).toBe(true)
  })

  it('interrupt → response.cancel 出站 + 气泡标记 interrupted', async () => {
    const s2s = useRealtimeS2s()
    s2s.connect(); FakeWS.last!.onopen?.()
    FakeWS.last!.emit({ type: 'session.created', session: {} })
    FakeWS.last!.emit({ type: 'response.created', response: {} })
    FakeWS.last!.emit({ type: 'response.audio_transcription.delta', delta: '长句' })
    s2s.interrupt()
    expect(FakeWS.last!.sent.some(d => JSON.parse(d).type === 'response.cancel')).toBe(true)
    const last = s2s.messages.value.at(-1)!
    expect(last.interrupted).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败** → **Step 3: 实现** → **Step 4: 确认通过**

```ts
// frontend/src/views/voice-demo/composables/useRealtimeS2s.ts
/** 实时 S2S 对话状态机（spec §2.2 WS 链）— 事件形状与 Mock/真实逐一同构。 */
import { ref } from 'vue'
import { buildVoiceDemoWsUrl } from '@/api/voiceDemo'
import { getToken } from '@/utils/auth'

export type S2sState = 'idle' | 'connecting' | 'listening' | 'responding' | 'closed'
export interface Msg { role: 'user' | 'assistant'; text: string; partial?: boolean; interrupted?: boolean }
export interface Ev { dir: 'in' | 'out'; type: string; at: number }

export function useRealtimeS2s() {
  const state = ref<S2sState>('idle')
  const messages = ref<Msg[]>([])
  const events = ref<Ev[]>([])
  let ws: WebSocket | null = null
  let assistantDraft: Msg | null = null
  let userDraft: Msg | null = null

  const log = (dir: 'in' | 'out', type: string) => events.value.push({ dir, type, at: Date.now() })
  const send = (data: unknown) => { ws?.send(JSON.stringify(data)); log('out', (data as any).type) }

  function upsertDraft(role: 'user' | 'assistant', text: string, partial: boolean) {
    const list = messages.value
    let m = list.at(-1)
    if (!m || m.role !== role || !m.partial) {
      m = { role, text: '', partial: true }
      list.push(m)
    }
    m.text += text
    if (!partial) m.partial = false
  }

  function handle(evt: any) {
    log('in', evt.type ?? '')
    switch (evt.type) {
      case 'session.created':
      case 'session.updated':
        state.value = 'listening'; break
      case 'input_audio_buffer.speech_started':
        if (state.value === 'responding') { /* 服务端 VAD 打断 */ }
        userDraft = null
        break
      case 'conversation.item.input_audio_transcription.completed':
      case 'input_audio_transcription.completed':
        messages.value.push({ role: 'user', text: evt.transcript ?? evt.delta ?? '' })
        break
      case 'response.created':
        state.value = 'responding'; assistantDraft = null; break
      case 'response.audio_transcription.delta':
        upsertDraft('assistant', evt.delta ?? '', true); break
      case 'response.audio.delta':
        playback.push(evt.delta); break
      case 'response.done':
        if (assistantDraft?.partial) assistantDraft.partial = false
        if (evt.response?.status === 'cancelled' || evt.response?.status === 'incomplete') {
          const last = messages.value.at(-1); if (last) last.interrupted = true
        }
        state.value = 'listening'; break
      case 'error':
        events.value.push({ dir: 'in', type: `error:${evt.code ?? ''}`, at: Date.now() })
        state.value = 'listening'; break
    }
  }

  // 播放链：PCM16/24k base64 → Float32 → PlaybackChain → AudioContext（懒建）
  const playback = createPlayback()

  function connect() {
    state.value = 'connecting'
    ws = new WebSocket(buildVoiceDemoWsUrl(getToken() || ''))
    ws.onopen = () => log('out', 'ws.open')
    ws.onmessage = e => handle(JSON.parse(e.data))
    ws.onclose = () => { state.value = 'closed' }
    ws.onerror = () => { state.value = 'closed' }
  }
  function disconnect() { ws?.close(); ws = null; state.value = 'closed' }
  function interrupt() {
    send({ type: 'response.cancel' })
    playback.clear()
    const last = messages.value.at(-1)
    if (last && last.role === 'assistant') last.interrupted = true
  }
  /** 文字模拟一句语音（Mock/真实模式 s2s 均可接 input text，桥接透传） */
  function sendSimText(text: string) { send({ type: 'conversation.item.create', item: { role: 'user', content: [{ type: 'input_text', text }] } }); send({ type: 'response.create' }) }

  return { state, messages, events, connect, disconnect, interrupt, sendSimText }
}

function createPlayback() {
  // v0：小缓冲顺序播放；clear() 即刻停播（打断）
  let ctx: AudioContext | null = null
  let queue: string[] = []
  return {
    push(b64: string) { queue.push(b64); drain() },
    clear() { queue = []; ctx?.close().catch(() => {}); ctx = null },
  }
  function drain() { /* 实现：decode base64→Int16→AudioBuffer→ctx.play；首批时懒建 AudioContext(24k) */ }
}
```

（注：`createPlayback().drain` 的具体解码播放实现在编码时补全——使用 `atob` + `Int16Array` + `AudioBufferSourceNode`，起点采样率 24000；`userDraft` 保留给 partial 转录流，若实现中未用到可删。测试只断言状态机/消息/事件，音频层 stub。）

`S2sPanel.vue`：左列 = 连接按钮（`state==='closed'||'idle'` 显「开始对话」，listening 显「结束」）、打断按钮（responding 时可用）、连接状态 tag、轮次计数（`response.created` 计数）、气泡列表（partial 斜体 / interrupted 标记 + 波形动画条）、模拟发言输入（`sendSimText`）、状态行；右列 = 事件流日志（`events` 反序渲染，in 绿 / out 蓝 / error 红，mono 字体）。麦克风采集（48k→16k PCM16 base64 分片 `input_audio_buffer.append`）接入 `AudioWorklet`：v0 可先支持「模拟发言」跑通链路，麦克风采集随后启用（同一 composable 已具备 `send` 通道）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/voice-demo
git commit -m "feat(voice-demo): S2S 对话 Tab（状态机 + 播放链 + 事件流）"
```

---

### Task 8: 环境示例 + 菜单 SQL + 端到端冒烟

**Files:**
- Modify: `backend/env.example`（追加 VOICE_DEMO_* 段，注释含实测说明）
- Create: `docs/sql/menu_voice_demo.sql`（幂等 INSERT…WHERE NOT EXISTS，风格对齐既有菜单 SQL；是否执行由用户定，spec §7.1）

**Interfaces:** 无新接口；收尾任务。

- [ ] **Step 1: env.example 追加**

```bash
# ── 语音能力 Demo（VOICE_DEMO_*，spec 2026-11-10-voice-demo-design.md §3.5）──
# 默认即真实服务（127.0.0.1:8765 REST+WS 同主机，2026-11-10 实测）；置 MOCK=true 则全 Mock 本地可跑
VOICE_DEMO_ENABLED=true
VOICE_DEMO_MOCK=false
VOICE_DEMO_BASE_URL=http://127.0.0.1:8765
VOICE_DEMO_REALTIME_WS_URL=ws://127.0.0.1:8765/v1/realtime
VOICE_DEMO_API_KEY=not-needed
VOICE_DEMO_TTS_VOICE=Aiden
VOICE_DEMO_TTS_LANGUAGE=auto
VOICE_DEMO_WS_IDLE_TIMEOUT_S=300
VOICE_DEMO_MAX_CONCURRENCY=1
```

- [ ] **Step 2: 菜单 SQL（幂等）**

```sql
-- docs/sql/menu_voice_demo.sql — 语音演示菜单（是否执行由用户定）
INSERT INTO sys_menu (name, parent_id, order_num, path, component, menu_type, visible, status, perms, icon)
SELECT '语音演示', 0, 99, '/voice-demo', 'views/voice-demo/VoiceDemo.vue', 'C', '0', '0', '', 'AudioOutlined'
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE path = '/voice-demo');
```

（字段名/父级以 `docs/sql/` 现有菜单 SQL 为准，实现时先读一份样例对齐列名。）

- [ ] **Step 3: 端到端冒烟（Mock 模式）**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/voice_demo -v   # 全绿
cd frontend && npx vitest run src/api/__tests__ src/views/voice-demo/__tests__   # 全绿
# 启动：backend uvicorn app.main:app --reload + frontend npm run dev
```

预期（对应 spec §5.3）：登录 → `/voice-demo` → health 徽标「Mock 开启」；ASR 上传/录音出样例文本；TTS 出提示音可下载；S2S「开始对话」→ session.created → 模拟发言 → 完整事件流 + 气泡逐字 + 打断即时停播；主题切换即时生效。

- [ ] **Step 4: 真实模式冒烟（可选，服务已实测可用）**

```bash
# WS 链路自测（容器内 E2E，spec §5.3）
docker exec speech-to-speech-thirdparty-pipeline-1 python3 /tmp/e2e_realtime_test.py --url ws://127.0.0.1:8765/v1/realtime --audio /tmp/prompt.wav --out-dir /tmp/e2e --timeout 90
# env: VOICE_DEMO_MOCK=false → 重启后端 → health 应显示真实 pool → 三 Tab 实测
```

- [ ] **Step 5: Commit**

```bash
git add backend/env.example docs/sql/menu_voice_demo.sql
git commit -m "chore(voice-demo): env 示例 + 菜单 SQL + 冒烟清单"
```

---

## Self-Review 记录

- **Spec 覆盖**：§3.1 文件→Task1-4；§3.2 接口→Task1/3/4；§3.3 桥接→Task4；§3.4 Mock→Task2/3/4；§3.5 配置→Task1/8；§4.1-4.4→Task5-7；§5 测试→各任务+Task8；§6.2 迁移→Task8 Step4 ✓
- **占位扫描**：GuidePanel 为「原型内容迁移」指令（原型在仓库内，非占位）；S2sPanel 麦克风采集标注 v0 用模拟发言跑通——属分期决策且 spec §4.3 已含采集管线要求，实现 Task7 时完成 AudioWorklet 接入 ✓
- **类型一致**：`useVadRecorder`/`useRealtimeS2s`/`buildVoiceDemoWsUrl`/`VOICES_BY_LANG` 命名前后一致；`_jwt_user_id`/`run_bridge`/`run_mock_session`/`BRIDGE_SEMAPHORE` Task4 内一致 ✓
