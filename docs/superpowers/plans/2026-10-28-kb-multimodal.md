# KB 多模态支持实现计划（图片 / 语音 / 视频 / DXF）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 知识库支持四类多模态文件（图片/音频/视频/DXF）摄取：内容经 VLM/ASR/ezdxf 转为分段文本入库，复用现有向量+关键词+RRF 检索链路，检索命中带时间轴/帧号/图层定位。

**Architecture:** 方案 C（spec `docs/superpowers/specs/2026-10-28-kb-multimodal-design.md`）：新增 `app/services/kb/media/` 提取器包统一输出 `MediaExtraction`（分段文本+locator），复用 `content_service._insert_via_kb` 的「直接构造 AgentScope Chunk → KnowledgeBase.insert_document」通道（嵌入内部完成，`chunk_type` 由 metadata 自动投影 D14）。**零 DDL**：locator 走 `kms_segment.metadata_` JSONB（不新增 `kb_segment_asset.locator` 列，spec §4.3 据此简化——asset 表仅存预览图，结构与现状兼容）。

**Tech Stack:** httpx（OpenAI 兼容 VLM chat/completions + ASR audio/transcriptions）、ffmpeg CLI（抽帧/提音轨）、ezdxf（DXF 解析+qsave 预览）、pgvector 现有链路、EmbeddingGemma 2（GPUStack，768 维）。

## Global Constraints

- 限制（超限拒收）：单文件 ≤100MB；音频 ≤2h；视频 ≤30min；DXF ≤50MB（spec §2.4）
- 抽帧 1 帧/10s；中间文件（帧图/临时音轨）处理后即删，不落 UPLOAD_DIR 长存（spec §8）
- provider 失败重试 2 次指数退避；VLM/ASR 超时 120s（spec §8）
- 部分成功：视频帧级失败不致整篇失败，≥1 成功分段即 completed；音频 ASR 全失败=整篇 failed（spec §5）
- 新函数中文 docstring；错误显式失败不静默降级；`media_kind=document` 过滤 = `chunk_type IN (text,qa,table_row,parent,child)`（spec §7）
- 不改 `pg_vector_store`、不改检索算法本体；不做 DWG；不做图搜图
- 后端测试命令：`cd backend && python -m pytest tests/kb -x -q`（fixtures 风格对齐 `tests/kb` 现有 conftest；测试目录无 `__init__.py`，不得跨测试模块 import 夹具）

---

### Task 1: MediaSettings 配置

**Files:**
- Create: `backend/app/config/_media.py`
- Modify: `backend/app/config/__init__.py:24-47`（import 与 Settings 混入，同 EmbeddingSettings 方式）
- Test: `backend/tests/kb/test_media_settings.py`

**Interfaces:**
- Produces: `settings.MEDIA_VISION_PROVIDER/MEDIA_VISION_MODEL/MEDIA_ASR_PROVIDER/MEDIA_ASR_MODEL/MEDIA_VISION_BASE_URL/MEDIA_ASR_BASE_URL/MEDIA_VISION_API_KEY/MEDIA_ASR_API_KEY/MEDIA_MAX_FILE_MB/MEDIA_MAX_AUDIO_HOURS/MEDIA_MAX_VIDEO_MINUTES/MEDIA_MAX_DXF_MB`（后续 Task 全部经 `get_settings()` 读取）

- [ ] **Step 1: 写失败测试**

```python
"""MediaSettings 默认值与校验。"""
from app.config import get_settings


def test_media_settings_defaults():
    s = get_settings()
    assert s.MEDIA_VISION_PROVIDER == "gpustack"
    assert s.MEDIA_ASR_PROVIDER == "gpustack"
    assert s.MEDIA_MAX_FILE_MB == 100
    assert s.MEDIA_MAX_AUDIO_HOURS == 2
    assert s.MEDIA_MAX_VIDEO_MINUTES == 30
    assert s.MEDIA_MAX_DXF_MB == 50
```

- [ ] **Step 2: 运行确认失败** — `cd backend && python -m pytest tests/kb/test_media_settings.py -x -q`，预期 FAIL（`MEDIA_VISION_PROVIDER` 不存在）
- [ ] **Step 3: 实现 `app/config/_media.py`**

```python
"""多模态媒体处理配置（vision / asr provider，spec §6）。

均走 OpenAI 兼容协议；provider 仅影响默认 base_url/model 取值，
实际以模型管理（type=6 vision / type=7 asr）优先、env 兜底（见 media/provider_client.py）。
"""
from pydantic import BaseModel


class MediaSettings(BaseModel):
    """媒体摄取配置"""
    MEDIA_VISION_PROVIDER: str = "gpustack"   # gpustack | dashscope
    MEDIA_VISION_BASE_URL: str = "http://192.168.40.30/v1"
    MEDIA_VISION_API_KEY: str = ""
    MEDIA_VISION_MODEL: str = "Qwen3-VL-32B"

    MEDIA_ASR_PROVIDER: str = "gpustack"      # gpustack | dashscope
    MEDIA_ASR_BASE_URL: str = "http://192.168.40.30/v1"
    MEDIA_ASR_API_KEY: str = ""
    MEDIA_ASR_MODEL: str = "Qwen3-ASR-1.7B"

    # 成本边界（spec §2.4），超限拒收
    MEDIA_MAX_FILE_MB: int = 100
    MEDIA_MAX_AUDIO_HOURS: int = 2
    MEDIA_MAX_VIDEO_MINUTES: int = 30
    MEDIA_MAX_DXF_MB: int = 50
```

- [ ] **Step 4: `app/config/__init__.py` 混入**：import 区加 `from ._media import MediaSettings`，Settings 基类元组里加 `MediaSettings,`（与 `EmbeddingSettings,` 并列，L39-47 两处）
- [ ] **Step 5: 运行测试通过** 后提交 `git commit -m "feat(kb): MediaSettings 媒体 provider 配置"`

### Task 2: 媒体 provider 客户端与配置解析

**Files:**
- Create: `backend/app/services/kb/media/__init__.py`、`media/provider_client.py`
- Test: `backend/tests/kb/test_media_provider_client.py`（respx 或 monkeypatch httpx）

**Interfaces:**
- Produces:
  - `@dataclass MediaProviderConfig(provider, base_url, api_key, model)`
  - `resolve_vision_config(db, override: dict | None = None) -> MediaProviderConfig` / `resolve_asr_config(db, override: dict | None = None) -> MediaProviderConfig`（**模型管理 type=6/7 默认优先 → collection 级 override（`kb_collection.retrieval_settings` 的 `vision_model`/`asr_model`，spec §6）→ env 兜底**；override 中的 model 替换 cfg.model，镜像 `embedding_config.resolve_default_embedding_from_db` L158-204 的 AiChatModel+AiApiKey 查询）
  - `async describe_image(cfg, image_bytes, mime, prompt) -> str`
  - `async transcribe_audio(cfg, audio_bytes, filename) -> list[dict]`（返回 `[{"start": float, "end": float, "text": str}]`；verbose_json 无 segments 时返回单段 `start=0,end=0`）

- [ ] **Step 1: 写失败测试**（monkeypatch `httpx.AsyncClient.post`，断言 describe_image 拼 `messages[].content` 为 `[{type:"text"},{type:"image_url",image_url:{url:"data:image/png;base64,..."}}]`、请求头带 Bearer；transcribe_audio 解析 verbose_json `{"segments":[{"start":0.0,"end":2.5,"text":"你好"}]}`；无 segments 键时返回单段兜底）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `media/provider_client.py`**

```python
"""媒体 provider 客户端（OpenAI 兼容）：VLM 图片描述 + ASR 转写。

配置解析镜像 embedding_config：模型管理默认（type=6 vision / type=7 asr，
is_default + status=1 + 关联密钥可用）优先，未配置回落 env（MediaSettings）。
重试 2 次指数退避，超时 120s（spec §8）。
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings

_TIMEOUT = 120.0
_RETRIES = 2
_VISION_MODEL_TYPE = 6
_ASR_MODEL_TYPE = 7


@dataclass
class MediaProviderConfig:
    provider: str
    base_url: str
    api_key: str
    model: str


def _base_url_ok(url: str) -> bool:
    return bool((url or "").strip())


def _from_model_mgmt(db: Session, model_type: int, label: str) -> Optional[MediaProviderConfig]:
    """模型管理默认模型（type=N + is_default + status=1）→ 配置；不完整返回 None。"""
    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    row = db.execute(
        select(AiChatModel).where(
            AiChatModel.type == model_type,
            AiChatModel.is_default.is_(True),
            AiChatModel.status == 1,
        ).order_by(AiChatModel.sort.desc(), AiChatModel.id.asc())
    ).scalars().first()
    if row is None:
        return None
    key = db.get(AiApiKey, row.key_id)
    if key is None or key.status != 1 or not _base_url_ok(key.url):
        logger.warning(f"[Media] 模型管理默认{label} {row.code or row.id} 密钥/地址不可用，回落 env")
        return None
    return MediaProviderConfig(
        provider=f"model_mgmt:{row.code or row.id}",
        base_url=(key.url or "").strip().rstrip("/") + "/v1",
        api_key=key.api_key or "",
        model=row.model,
    )


def _from_env(kind: str) -> MediaProviderConfig:
    s = get_settings()
    if kind == "vision":
        return MediaProviderConfig(s.MEDIA_VISION_PROVIDER, s.MEDIA_VISION_BASE_URL.rstrip("/"),
                                   s.MEDIA_VISION_API_KEY, s.MEDIA_VISION_MODEL)
    return MediaProviderConfig(s.MEDIA_ASR_PROVIDER, s.MEDIA_ASR_BASE_URL.rstrip("/"),
                               s.MEDIA_ASR_API_KEY, s.MEDIA_ASR_MODEL)


def _apply_override(cfg: MediaProviderConfig, override: dict | None, key: str) -> MediaProviderConfig:
    """collection 级覆盖（spec §6）：retrieval_settings.vision_model/asr_model 替换 model。"""
    model = (override or {}).get(key)
    if model and str(model).strip():
        return MediaProviderConfig(cfg.provider, cfg.base_url, cfg.api_key, str(model).strip())
    return cfg


def resolve_vision_config(db: Session, override: dict | None = None) -> MediaProviderConfig:
    cfg = _from_model_mgmt(db, _VISION_MODEL_TYPE, "视觉模型") or _from_env("vision")
    return _apply_override(cfg, override, "vision_model")


def resolve_asr_config(db: Session, override: dict | None = None) -> MediaProviderConfig:
    cfg = _from_model_mgmt(db, _ASR_MODEL_TYPE, "语音模型") or _from_env("asr")
    return _apply_override(cfg, override, "asr_model")


async def _post_with_retry(url: str, *, json=None, data=None, files=None,
                           headers: dict) -> httpx.Response:
    """POST + 重试 2 次指数退避；非 2xx 显式抛错。"""
    last: Exception | httpx.Response
    for attempt in range(_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=json, data=data, files=files,
                                         headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp
        except Exception as exc:  # noqa: BLE001 - 统一退避重试
            last = exc
            if attempt < _RETRIES:
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"媒体 provider 调用失败（已重试 {_RETRIES} 次）: {last}")


async def describe_image(cfg: MediaProviderConfig, image_bytes: bytes,
                         mime: str, prompt: str) -> str:
    """VLM 描述图片（OpenAI 兼容 chat/completions，图片 base64 data URI）。"""
    b64 = base64.b64encode(image_bytes).decode()
    resp = await _post_with_retry(
        f"{cfg.base_url}/chat/completions",
        json={
            "model": cfg.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
        },
        headers={"Authorization": f"Bearer {cfg.api_key or 'not-required'}"},
    )
    choice = (resp.json().get("choices") or [{}])[0]
    return (choice.get("message") or {}).get("content") or ""


async def transcribe_audio(cfg: MediaProviderConfig, audio_bytes: bytes,
                           filename: str) -> list[dict]:
    """ASR 转写（OpenAI 兼容 /audio/transcriptions，verbose_json 取时间轴分段）。

    返回 [{"start": 秒, "end": 秒, "text": 文本}]；服务端不支持 verbose_json
    segments 时降级为单段（start=end=0），不做词级对齐假设。
    """
    resp = await _post_with_retry(
        f"{cfg.base_url}/audio/transcriptions",
        data={"model": cfg.model, "response_format": "verbose_json"},
        files={"file": (filename, audio_bytes)},
        headers={"Authorization": f"Bearer {cfg.api_key or 'not-required'}"},
    )
    body = resp.json()
    segs = body.get("segments") or []
    if segs:
        return [{"start": float(s.get("start") or 0), "end": float(s.get("end") or 0),
                 "text": (s.get("text") or "").strip()} for s in segs
                if (s.get("text") or "").strip()]
    text = (body.get("text") or "").strip()
    return [{"start": 0.0, "end": 0.0, "text": text}] if text else []
```

- [ ] **Step 4: 测试通过**；`media/__init__.py` 导出上述 4 个名字
- [ ] **Step 5: 提交** `feat(kb): 媒体 provider 客户端（VLM/ASR OpenAI 兼容 + 模型管理优先解析）`

### Task 3: 提取器抽象 + ImageExtractor

**Files:**
- Create: `backend/app/services/kb/media/base.py`、`media/image_extractor.py`
- Test: `backend/tests/kb/test_media_extractors.py`

**Interfaces:**
- Produces:
  - `@dataclass MediaSegment(text: str, locator: dict)`
  - `@dataclass MediaExtraction(kind: str, segments: list[MediaSegment], meta: dict)`
  - `class MediaExtractor(Protocol)`: `async extract(data: bytes, filename: str) -> MediaExtraction`
  - `get_extractor(kind: str, db) -> MediaExtractor`（注册表分发，未知 kind 抛 `ValueError`）
  - `detect_media_kind(filename) -> str | None`（扩展名→image/audio/video/drawing，None=非媒体）

- [ ] **Step 1: 写失败测试**（fake vision cfg 断言：ImageExtractor 对 png 产出 1 个 segment，text 含 fake VLM 返回，locator=={}；detect_media_kind 对 `.mp3/.wav/.m4a/.mp4/.mov/.dxf/.png/.jpg` 返回正确 kind、`.pdf` 返回 None）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `media/base.py`**

```python
"""媒体提取器抽象（spec §4.1）：统一输出 分段文本 + 定位器。

locator 约定：音频/视频 {"start_ms": int, "end_ms": int}；视频帧描述附带
{"frame_index": int}；DXF {"layer": str}；图片 {}。经 Chunk.metadata 落
kms_segment.metadata_（零 DDL，spec 简化说明）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.services.kb.media.provider_client import (
    MediaProviderConfig, describe_image, resolve_vision_config,
)

_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
_AUDIO_EXTS = {"mp3", "wav", "m4a"}
_VIDEO_EXTS = {"mp4", "mov"}
_DRAWING_EXTS = {"dxf"}
EXT_KIND_MAP = {**{e: "image" for e in _IMAGE_EXTS},
                **{e: "audio" for e in _AUDIO_EXTS},
                **{e: "video" for e in _VIDEO_EXTS},
                **{e: "drawing" for e in _DRAWING_EXTS}}

_KIND_TO_EXTRACTOR: dict[str, str] = {}   # 尾部注册表，见 get_extractor


@dataclass
class MediaSegment:
    text: str
    locator: dict = field(default_factory=dict)


@dataclass
class MediaExtraction:
    kind: str
    segments: list[MediaSegment]
    meta: dict = field(default_factory=dict)


class MediaExtractor(Protocol):
    async def extract(self, data: bytes, filename: str) -> MediaExtraction: ...


def detect_media_kind(filename: str) -> Optional[str]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXT_KIND_MAP.get(ext)


def register_extractor(kind: str, cls) -> None:
    _KIND_TO_EXTRACTOR[kind] = cls


def get_extractor(kind: str, db, override: dict | None = None) -> "MediaExtractor":
    cls = _KIND_TO_EXTRACTOR.get(kind)
    if cls is None:
        raise ValueError(f"不支持的媒体类型: {kind!r}")
    return cls(db, override)


def default_vision_prompt() -> str:
    return ("请用中文详细描述这张图片的内容；若图中有文字（OCR），逐条原样列出。"
            "不要输出与图片无关的内容。")
```

- [ ] **Step 4: 实现 `media/image_extractor.py`**

```python
"""图片提取器：VLM 描述 + OCR（单段，locator={}）。"""
from __future__ import annotations

from app.services.kb.media.base import MediaExtraction, MediaSegment, default_vision_prompt
from app.services.kb.media.provider_client import describe_image, resolve_vision_config


class ImageExtractor:
    def __init__(self, db, override: dict | None = None):
        self.cfg: MediaProviderConfig = resolve_vision_config(db, override)

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        text = await describe_image(self.cfg, data, mime, default_vision_prompt())
        if not text.strip():
            raise ValueError(f"图片 {filename} 未产出任何描述文本（VLM 返回为空）")
        return MediaExtraction(
            kind="image", segments=[MediaSegment(text=text.strip(), locator={})],
            meta={"vision_model": self.cfg.model},
        )


def register() -> None:
    from app.services.kb.media.base import register_extractor
    register_extractor("image", ImageExtractor)


register()
```

- [ ] **Step 5: 测试通过 → 提交** `feat(kb): 媒体提取器抽象 + 图片提取器`

### Task 4: AudioExtractor（ffmpeg 探测 + ASR 时间轴分段）

**Files:**
- Create: `backend/app/services/kb/media/audio_extractor.py`、`media/ffmpeg_utils.py`
- Test: `backend/tests/kb/test_audio_extractor.py`

**Interfaces:**
- Consumes: Task 2 `transcribe_audio`、Task 3 `MediaSegment/MediaExtraction/register_extractor`
- Produces:
  - `ffmpeg_utils.ensure_ffmpeg() -> None`（`shutil.which("ffmpeg")` 为空抛 `RuntimeError("缺少 ffmpeg，请安装后重试")`）
  - `ffmpeg_utils.probe_duration_seconds(path) -> float`（`ffprobe -v error -show_entries format=duration -of json`）
  - `AudioExtractor.extract`：先校验时长 ≤ `MEDIA_MAX_AUDIO_HOURS`，整文件送 ASR，逐段映射 `MediaSegment(text, {"start_ms": int(s*1000), "end_ms": int(e*1000)})`；空转写抛错（整篇 failed，spec 部分成功语义）

- [ ] **Step 1: 写失败测试**（monkeypatch `transcribe_audio` 返回两段 + monkeypatch `probe_duration_seconds`=3600 断言抛超限错、=600 正常产出 2 段且 locator 毫秒正确）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `ffmpeg_utils.py` 与 `audio_extractor.py`**

```python
"""ffmpeg/ffprobe 工具：存在性探测 + 时长探测（音视频共用）。"""
from __future__ import annotations

import json
import shutil
import subprocess


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("缺少 ffmpeg，请安装后重试（音视频摄取依赖）")


def probe_duration_seconds(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])
```

```python
"""音频提取器：整文件 ASR，按转写分段映射 MediaSegment。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from app.config import get_settings
from app.services.kb.media.base import MediaExtraction, MediaSegment
from app.services.kb.media.ffmpeg_utils import ensure_ffmpeg, probe_duration_seconds
from app.services.kb.media.provider_client import resolve_asr_config, transcribe_audio


class AudioExtractor:
    def __init__(self, db, override: dict | None = None):
        self.cfg = resolve_asr_config(db, override)

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        ensure_ffmpeg()
        with tempfile.TemporaryDirectory(prefix="kb_media_") as tmp:
            path = Path(tmp) / filename
            path.write_bytes(data)
            max_seconds = get_settings().MEDIA_MAX_AUDIO_HOURS * 3600
            duration = probe_duration_seconds(str(path))
            if duration > max_seconds:
                raise ValueError(
                    f"音频时长 {duration/3600:.1f}h 超过上限 {max_seconds/3600:.0f}h")
        segs = await transcribe_audio(self.cfg, data, filename)
        if not segs:
            raise ValueError(f"音频 {filename} 转写结果为空（ASR 无输出）")
        segments = [MediaSegment(
            text=s["text"],
            locator={"start_ms": int(s["start"] * 1000), "end_ms": int(s["end"] * 1000)},
        ) for s in segs]
        return MediaExtraction(kind="audio", segments=segments,
                               meta={"asr_model": self.cfg.model, "duration": duration})


def register() -> None:
    from app.services.kb.media.base import register_extractor
    register_extractor("audio", AudioExtractor)


register()
```

- [ ] **Step 4: 测试通过 → 提交** `feat(kb): 音频提取器（ffmpeg 探测 + ASR 时间轴分段）`

### Task 5: VideoExtractor（抽帧 + 帧描述 + 音轨转写 + 首帧缩略图）

**Files:**
- Create: `backend/app/services/kb/media/video_extractor.py`
- Test: `backend/tests/kb/test_video_extractor.py`

**Interfaces:**
- Consumes: Task 2 `describe_image/transcribe_audio/resolve_*`、Task 3 base、Task 4 ffmpeg_utils
- Produces:
  - `VideoExtractor.extract`：时长 ≤ `MEDIA_MAX_VIDEO_MINUTES` 校验；`ffmpeg -i in -vf fps=1/10 -q:v 5 frame_%04d.jpg` 抽帧（临时目录）；音轨 `ffmpeg -i in -vn -ac 1 -ar 16000 out.wav` → 复用 `transcribe_audio`；帧描述按 `frame_index` 升序产出 `MediaSegment(text, {"frame_index": i})`，转写段产出 `MediaSegment(text, {"start_ms","end_ms"})`；单帧 VLM 失败记入 `meta["partial_errors"]` 继续（spec 部分成功）
  - `VideoExtractor.thumbnail_bytes(data, filename) -> bytes`（首帧 JPEG，供 asset；实现为 `ffmpeg -i - -frames:v 1 -f image2pipe -`）

- [ ] **Step 1: 写失败测试**（monkeypatch `describe_image`/`transcribe_audio`/ffmpeg 子进程：用一个 monkeypatch 的 `_run_ffmpeg` 伪造抽帧输出目录写 3 个 jpg + wav，断言产出 3 帧段 + N 转写段、帧段 locator 带 frame_index、某帧 describe 抛错时 meta["partial_errors"] 记录且整体成功）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `video_extractor.py`**

```python
"""视频提取器：抽帧(1帧/10s)→VLM 逐帧描述 + 音轨 ASR（spec §5）。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from app.config import get_settings
from app.services.kb.media.audio_extractor import AudioExtractor
from app.services.kb.media.base import MediaExtraction, MediaSegment, default_vision_prompt
from app.services.kb.media.ffmpeg_utils import ensure_ffmpeg, probe_duration_seconds
from app.services.kb.media.provider_client import describe_image, resolve_vision_config

FRAME_INTERVAL_SEC = 10


def _run_ffmpeg(args: list[str]) -> None:
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                   capture_output=True, timeout=600, check=True)


class VideoExtractor:
    def __init__(self, db, override: dict | None = None):
        self.vision_cfg = resolve_vision_config(db, override)
        self._audio = AudioExtractor(db, override)

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        ensure_ffmpeg()
        segments: list[MediaSegment] = []
        partial: list[str] = []
        frame_files: list[Path] = []
        with tempfile.TemporaryDirectory(prefix="kb_video_") as tmp:
            src = Path(tmp) / filename
            src.write_bytes(data)
            max_seconds = get_settings().MEDIA_MAX_VIDEO_MINUTES * 60
            duration = probe_duration_seconds(str(src))
            if duration > max_seconds:
                raise ValueError(
                    f"视频时长 {duration/60:.0f}min 超过上限 {max_seconds/60:.0f}min")
            # 抽帧（JPEG）+ 提音轨（16k 单声道 wav，临时文件用后即删）
            _run_ffmpeg(["-i", str(src), "-vf", f"fps=1/{FRAME_INTERVAL_SEC}",
                         "-q:v", "5", str(Path(tmp) / "frame_%04d.jpg")])
            audio_wav = Path(tmp) / "audio.wav"
            _run_ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                         str(audio_wav)])
            frame_files = sorted((Path(tmp)).glob("frame_*.jpg"))
            # 帧描述：单帧失败不致整篇失败（spec 部分成功）
            for idx, fp in enumerate(frame_files):
                try:
                    text = await describe_image(self.vision_cfg, fp.read_bytes(),
                                                "image/jpeg", default_vision_prompt())
                    if text.strip():
                        segments.append(MediaSegment(text=text.strip(),
                                                     locator={"frame_index": idx}))
                except Exception as exc:  # noqa: BLE001 - 帧级失败继续
                    partial.append(f"frame_{idx}: {exc}")
            # 音轨转写段
            if audio_wav.exists():
                for s in await transcribe_audio(self._audio.cfg, audio_wav.read_bytes(),
                                                "audio.wav"):
                    if s["text"].strip():
                        segments.append(MediaSegment(
                            text=s["text"],
                            locator={"start_ms": int(s["start"] * 1000),
                                     "end_ms": int(s["end"] * 1000)}))
            if not segments:
                raise ValueError(f"视频 {filename} 未产出任何分段（帧描述与音轨转写均为空）")
        return MediaExtraction(kind="video", segments=segments, meta={
            "vision_model": self.vision_cfg.model, "asr_model": self._audio.cfg.model,
            "duration": duration, "frame_count": len(frame_files),
            "partial_errors": partial,
        })

    def thumbnail_bytes(self, data: bytes, filename: str) -> bytes:
        """首帧 JPEG（供 asset 预览）；失败抛错由调用方决定降级。"""
        import subprocess
        proc = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-frames:v", "1",
             "-q:v", "5", "-f", "image2pipe", "-"],
            input=data, capture_output=True, timeout=120, check=True)
        return proc.stdout


def register() -> None:
    from app.services.kb.media.base import register_extractor
    register_extractor("video", VideoExtractor)


register()
```

- [ ] **Step 4: 测试通过 → 提交** `feat(kb): 视频提取器（抽帧+VLM+音轨ASR+首帧缩略图）`

### Task 6: DxfExtractor（ezdxf 解析 + qsave 预览）

**Files:**
- Create: `backend/app/services/kb/media/dxf_extractor.py`
- Modify: `backend/requirements.txt`（或 pyproject 依赖清单，按仓库实际）加 `ezdxf>=1.3`
- Test: `backend/tests/kb/test_dxf_extractor.py`

**Interfaces:**
- Produces: `DxfExtractor.extract`（size ≤ `MEDIA_MAX_DXF_MB` 校验）→ segments：每个含文字的图层一段（`{"layer": 图层名}`），文本取 `msp.query("TEXT MTEXT ATTRIB")` 的 `dxf.text/plain_text`，按图层聚合；`meta` 含 `layer_count/entity_count`；空标注时产出单段文件名+图元统计兜底（保证可检索）。`preview_png_bytes(data) -> bytes`（`ezdxf.addons.drawing.matplotlib` 渲染 modelspace，供 asset）

- [ ] **Step 1: 安装依赖** `cd backend && uv pip install ezdxf` 并写入依赖清单
- [ ] **Step 2: 写失败测试**（conftest 内用 ezdxf 编程生成最小 DXF fixture：两层，LAYER-A 两个 TEXT、LAYER-B 一个 MTEXT；断言 2 个 segment、layer locator 正确、文本聚合无遗漏）
- [ ] **Step 3: 实现 `dxf_extractor.py`**

```python
"""DXF 图纸提取器：图层名 + TEXT/MTEXT/ATTRIB 标注 → 结构化文本（spec §1）。"""
from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path

from app.config import get_settings
from app.services.kb.media.base import MediaExtraction, MediaSegment


class DxfExtractor:
    def __init__(self, db, override: dict | None = None):   # override 不用，统一构造签名
        self.max_mb = get_settings().MEDIA_MAX_DXF_MB

    def _load(self, data: bytes, filename: str):
        import ezdxf
        if len(data) > self.max_mb * 1024 * 1024:
            raise ValueError(f"DXF 大小超过上限 {self.max_mb}MB")
        import io
        return ezdxf.readstream(io.BytesIO(data))

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        doc = self._load(data, filename)
        msp = doc.modelspace()
        by_layer: dict[str, list[str]] = defaultdict(list)
        for e in msp.query("TEXT MTEXT ATTRIB"):
            if e.dxftype() == "MTEXT":
                text = e.plain_text()
            else:
                text = e.dxf.get("text", "") or ""
            text = (text or "").strip()
            if text:
                by_layer[e.dxf.layer].append(text)
        segments = [MediaSegment(
            text=f"图层 {layer}：\n" + "\n".join(texts), locator={"layer": layer})
            for layer, texts in sorted(by_layer.items())]
        if not segments:   # 纯图形无标注：文件名+统计兜底，保证可检索
            segments = [MediaSegment(
                text=f"图纸 {filename}（无文字标注，图元 {len(msp)} 个）", locator={})]
        return MediaExtraction(kind="drawing", segments=segments, meta={
            "layer_count": len(by_layer), "entity_count": len(msp)})

    def preview_png_bytes(self, data: bytes) -> bytes:
        """modelspace 渲染 PNG（ezdxf drawing add-on + matplotlib 后端）。"""
        import io
        import ezdxf
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        doc = ezdxf.read(io.BytesIO(data))
        msp = doc.modelspace()
        buf = io.BytesIO()
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1])
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return buf.getvalue()


def register() -> None:
    from app.services.kb.media.base import register_extractor
    register_extractor("drawing", DxfExtractor)


register()
```

- [ ] **Step 4: 测试通过 → 提交** `feat(kb): DXF 图纸提取器（ezdxf 图层/标注 + 预览渲染）`

### Task 7: 媒体摄取编排（run_media_ingest）

**Files:**
- Create: `backend/app/services/kb/media/ingest.py`
- Test: `backend/tests/kb/test_media_ingest.py`

**Interfaces:**
- Consumes: Task 3-6 `get_extractor/detect_media_kind`；`content_service._insert_via_kb`（签名 L31-41：`(session_factory, *, db, collection, tenant_id, document_id, chunks, kb_factory=None, document_metadata=None)`）；AgentScope `Chunk(content=TextBlock(text=...), source, chunk_index, total_chunks, metadata)`
- Produces: `run_media_ingest(db, tenant_id, doc_id, file_bytes, filename, session_factory=None, kb_factory=None) -> int`（返回切片数；状态机/失败语义与 `document_pipeline.run_document_ingest` 一致：pending→processing→completed/failed + `meta.failed_step` 取 `extract`/`embed`）

- [ ] **Step 1: 写失败测试**（fake extractor（monkeypatch `get_extractor`）返回 2 段；fake kb_factory 捕获传入 chunks；断言：chunk 数=2、`metadata["chunk_type"]` ∈ {audio,...}、`metadata["media_locator"]` 透传、`doc.meta["media"]["kind"]` 与 `partial_errors` 落库、status=completed、返回 2；extractor 抛错时 status=failed 且 `meta["failed_step"]=="extract"`）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `media/ingest.py`**

```python
"""媒体摄取编排：extract → 构造 Chunk → _insert_via_kb（嵌入内部完成）。

复用 content_service 的「不经 parser/chunker 直接入库」通道（D15）：
Chunk.metadata["chunk_type"] 由 pg_vector_store 投影到 kms_segment.chunk_type（D14），
media_locator/media_kind 留在 kms_segment.metadata_ JSONB（零 DDL）。
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument


def _fail(db: Session, doc_id: int, step: str, exc: Exception) -> None:
    doc = db.get(KbDocument, doc_id)
    if doc is not None:
        doc.status = "failed"
        doc.error_detail = f"[{step}] {type(exc).__name__}: {exc}"
        doc.meta = {**(doc.meta or {}), "failed_step": step}
        db.commit()
    logger.error(f"[KB 媒体] 文档 {doc_id} 在 {step} 步失败: {exc}")


def run_media_ingest(
    db: Session,
    tenant_id: int,
    doc_id: int,
    file_bytes: bytes,
    filename: str,
    session_factory: Optional[Callable] = None,
    kb_factory: Optional[Callable] = None,
) -> int:
    """同步执行媒体摄取；返回切片数。失败落 failed 后原样抛出。"""
    from agentscope.rag import Chunk
    from agentscope.message import TextBlock

    from app.models.kb.kb_collection import KbCollection
    from app.services.kb.media.base import detect_media_kind, get_extractor
    from app.services.kb.rag.content_service import _insert_via_kb

    doc = db.get(KbDocument, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: {doc_id}")
    kind = detect_media_kind(filename)
    if kind is None:
        raise ValueError(f"非媒体文件: {filename}")
    doc.status = "processing"
    doc.error_detail = None
    db.commit()

    try:
        # collection 级 provider 覆盖（spec §6）：kb_collection.retrieval_settings
        col = db.query(KbCollection).filter(KbCollection.name == doc.collection).first()
        override = (col.retrieval_settings or {}) if col is not None else {}
        extractor = get_extractor(kind, db, override)

        async def _extract():
            return await extractor.extract(file_bytes, filename)

        try:
            extraction = asyncio.run(_extract())
        except Exception as exc:  # noqa: BLE001 - 标注 extract 步名
            db.rollback()
            raise RuntimeError(f"extract: {exc}") from exc

        chunks = [
            Chunk(
                content=TextBlock(text=seg.text),
                source=filename,
                chunk_index=i,
                total_chunks=len(extraction.segments),
                metadata={
                    "chunk_type": extraction.kind,
                    "media_kind": extraction.kind,
                    "media_locator": seg.locator,
                    "media_meta": extraction.meta,
                },
            )
            for i, seg in enumerate(extraction.segments)
        ]
        document_id = doc.uuid_code
        try:
            _insert_via_kb(
                session_factory, db=db, collection=doc.collection, tenant_id=tenant_id,
                document_id=document_id, chunks=chunks, kb_factory=kb_factory,
                document_metadata={"source": f"media:{kind}", "filename": filename},
            )
        except Exception as exc:  # noqa: BLE001 - 标注 embed 步名
            db.rollback()
            raise RuntimeError(f"embed: {exc}") from exc

        doc.status = "completed"
        doc.segment_count = len(chunks)
        doc.meta = {
            **(doc.meta or {}),
            "media": {"kind": kind, **extraction.meta},
            "failed_step": None,
        }
        db.commit()
        logger.info(f"[KB 媒体] {filename} 摄取完成：{len(chunks)} 段（{kind}）")
        return len(chunks)
    except Exception as exc:  # noqa: BLE001 - 与 document_pipeline 相同的失败落库语义
        step = "extract" if str(exc).startswith("extract") else "embed"
        db.rollback()
        _fail(db, doc_id, step, exc)
        raise
```

（实现注意：`TextBlock` 的导入路径以仓库内 `content_service.py` L470-476 与 `chunker_factory.py` 的实际用法为准——两处均已构造 `Chunk(content=TextBlock(...))`，照抄其 import。）

- [ ] **Step 4: 测试通过 → 提交** `feat(kb): 媒体摄取编排（extract→Chunk→insert_via_kb）`

### Task 8: 上传入口接线（parser_selector + document_pipeline 分支）

**Files:**
- Modify: `backend/app/services/kb/parser_selector.py:49-58`（`_EXT_MEDIA` 增加媒体扩展名）
- Modify: `backend/app/services/kb/document_pipeline.py:78-110`（`run_document_ingest` 开头媒体分支）
- Test: `backend/tests/kb/test_media_pipeline_branch.py`

**Interfaces:**
- Consumes: Task 3 `detect_media_kind`、Task 7 `run_media_ingest`
- Produces: `run_document_ingest(...)` 对媒体文件自动走 `run_media_ingest`（返回值语义一致=切片数）；`guess_media_type` 对 `mp3/wav/m4a/mp4/mov/dxf` 返回 IANA mime

- [ ] **Step 1: 写失败测试**（fake `run_media_ingest`（monkeypatch）断言：`run_document_ingest` 收到 `.mp3` 文件名时被调用且原 parse/chunk 分支未执行；`.md` 不分支）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 修改 `parser_selector.py`**

```python
# _EXT_MEDIA 追加（Task 8）：
"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
"mp4": "video/mp4", "mov": "video/quicktime",
"dxf": "image/vnd.dxf",
```

- [ ] **Step 4: 修改 `document_pipeline.run_document_ingest`**：在 `doc.status = "processing"` 之前插入分支

```python
        # 媒体文件（图片/音频/视频/DXF）不走 parser/chunker，直接媒体提取路径（spec §5）
        from app.services.kb.media.base import detect_media_kind

        if detect_media_kind(filename) is not None:
            from app.services.kb.media.ingest import run_media_ingest

            return run_media_ingest(
                db, tenant_id, doc_id, file_bytes or b"", filename,
                session_factory=None, kb_factory=knowledge_factory,
            )
```

- [ ] **Step 5: 测试通过；跑既有回归** `python -m pytest tests/kb -q`（基线 372 passed / 1 skipped 不得回退）→ 提交 `feat(kb): 摄取管线媒体文件分支接入`

### Task 9: 上传校验（multimodal 开关 + 大小 + 预检）

**Files:**
- Modify: `backend/app/routers/kb/kb.py`（上传端点：文件名→`detect_media_kind` 命中时校验）
- Create: `backend/app/services/kb/media/validation.py`
- Test: `backend/tests/kb/test_media_validation.py`

**Interfaces:**
- Produces: `validate_media_upload(knowledge, filename, size) -> None`（命中媒体且 `not knowledge.multimodal_enabled` → `ValueError("该知识库未启用多模态，无法上传媒体文件")`；size 超 `MEDIA_MAX_FILE_MB`/按 kind 上限 → `ValueError` 带具体上限；调用方转 422）。上传端点在写库前调用，`ValueError` → `raise HTTPException(422, detail=str(exc))`

- [ ] **Step 1: 写失败测试**（multimodal_enabled=False 抛错；enabled + 99MB 通过；mp4 40min 抛错；pdf 任意大小直接放行——非媒体不校验）
- [ ] **Step 2: 确认失败 → Step 3: 实现 `validation.py`**（`MEDIA_LIMITS_BY_KIND = {"audio": hours*3600, "video": minutes*60, "drawing": MB}`；图片仅受通用 100MB 限制）→ **Step 4: 在 kb.py 上传端点落库前调用并转 422**（端点内已有文件大小/类型校验区，插入调用即可）→ **Step 5: 测试通过 → 提交** `feat(kb): 媒体上传校验（多模态开关/大小/时长）`

### Task 10: 检索增强（media_kind 过滤 + media 结果块）

**Files:**
- Modify: `backend/app/services/kb/retrieval_service.py`（`search_by_text` / `hybrid_search_by_text` 增加可选 `media_kind: Optional[str]`）
- Test: `backend/tests/kb/test_media_retrieval.py`

**Interfaces:**
- Consumes: `kms_segment.chunk_type` 列（Task 7 投影写入）；`kms_segment.metadata_->media_locator/media_kind`
- Produces: 两条检索函数返回的每条结果增加 `media` 块（chunk_type ∈ 媒体类时）：`{"kind": chunk_type, "locator": metadata.get("media_locator"), "file_path": document.meta.get("file_path")}`；`media_kind="document"` → SQL `chunk_type IN ('text','qa','table_row','parent','child')`，其余 → `chunk_type == media_kind`；参数经 `chunk_type` SQL 过滤实现（加入现有 WHERE，不改 RRF 融合）

- [ ] **Step 1: 写失败测试**（integration 风格，对齐 tests/kb 现有检索测试夹具：入库 1 文本段 + 1 audio 段（locator {"start_ms":1000,"end_ms":4000}）；断言默认检索两者都回、`media_kind="audio"` 只回 audio 段且结果带 `media.locator.start_ms==1000`、`media_kind="document"` 排除 audio 段）
- [ ] **Step 2: 确认失败 → Step 3: 实现**（在两条检索函数的 WHERE 构造处加 chunk_type 条件；结果组装处按 `row.chunk_type` 附加 media 块，file_path 由同查询 join `kb_document.meta->'file_path'` 取）→ **Step 4: 通过 → Step 5: 提交** `feat(kb): 检索 media_kind 过滤与媒体定位结果块`

### Task 11: 前端（向导/上传/结果展示）

**Files:**
- Modify: `frontend/src/views/kms/KnowledgeBaseManager.vue`（L223-245 多模态区块、L456 `isVisionModel`、L844-848 提交校验）
- Modify: `frontend/src/views/kms/kb/KbDocumentPane.vue`（上传 accept 列表）
- Modify: `frontend/src/api/kb.ts`（检索结果类型加 `media?` 块）
- Test: `cd frontend && npx vue-tsc --noEmit 2>&1 | Select-String "kms"`（全仓 vue-tsc 有既有红，只看本模块无新增错误）

**Interfaces:**
- Consumes: Task 10 返回体 `media` 块
- Produces: 「多模态」开关开启时展示 视觉模型 / 语音模型 两个文本输入（默认值取 `settings` 经后端 config 接口或留空=走服务端默认），替换原「Vision Embedding 模型」硬编码下拉（`qwen3-vl-embedding/multimodal-embedding-v1/text-embedding-v4` 三个 option 删除）；上传 accept 追加 `.mp3,.wav,.m4a,.mp4,.mov,.dxf`；检索/分段列表对 `row.media` 渲染：audio/video → 行内 `<audio controls :src>` / `<video controls>` 且 `@loadedmetadata` 后 `currentTime = media.locator.start_ms/1000`；drawing/image → 显示定位（图层/帧号）

- [ ] **Step 1: KnowledgeBaseManager.vue**：删除 `isVisionModel` 正则校验（L456）与 L844-848 的 vision 强校验；多模态区块（L223-245）改为 开关 + 视觉模型输入 + 语音模型输入（`v-model="form.mediaVisionModel"` / `form.mediaAsrModel"`，均可空=服务端默认）
- [ ] **Step 2: KbDocumentPane.vue** 上传按钮 `:accept` 追加上述扩展名；前端预校验 100MB（超限 message.error 直接拦截，不发请求）
- [ ] **Step 3: api/kb.ts** 检索结果 interface 追加 `media?: { kind: string; locator: Record<string, number|string> | null; file_path: string | null }`
- [ ] **Step 4: 检索结果/分段列表渲染 media 块**（音频/视频播放器 + seek、drawing 显示 `图层 {locator.layer}`、image 无额外渲染）
- [ ] **Step 5: vue-tsc 过滤自检 + 提交** `feat(kb-front): 多模态上传/模型选择/媒体命中展示`

### Task 12: 端到端集成测试与冒烟清单

**Files:**
- Test: `backend/tests/kb/test_media_e2e.py`

- [ ] **Step 1: E2E**（fake provider）：fake kb_factory + fake extractor 全链路——上传(.dxf) → validate → run_document_ingest 分支 → 2 段入库（断言 kb_factory 收到的 chunks 的 chunk_type/locator）→ 检索 `media_kind="drawing"` 命中且带 media 块
- [ ] **Step 2: 全量回归** `cd backend && python -m pytest tests/kb tests/unit -q`（基线 372/1 与 tests/unit 不回退）
- [ ] **Step 3: 手动冒烟清单写入 PR 描述**（不进 CI）：① GPUStack 部署 EmbeddingGemma 2 + Qwen3-VL + Qwen3-ASR 后真实图片/音频/视频/DXF 各传 1 份；② 检索命中后音频 seek 正确；③ ffmpeg 未装容器内传 mp4 得到可读 422
- [ ] **Step 4: 提交** `test(kb): 媒体摄取端到端集成测试`
