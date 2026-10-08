# speech-to-speech —— 实时语音对话 pipeline

容器 `s2s-pipeline` 负责 **VAD → STT → LLM → TTS** 全链路，端口 **8765**（WebSocket/HTTP）。
LLM 有两种接法：

| 编排文件 | 形态 | 适用 |
|---------|------|------|
| `docker-compose.yml` | 内置 llama.cpp 容器跑 LLM | 单机独立运行 |
| `docker-compose.gpustack.yml` | LLM 走 GPUStack 的 OpenAI 兼容接口 | 已有 GPUStack，推荐（单容器，省显存） |

## 构建前的硬前置：Silero VAD

`src/speech_to_speech/VAD/vad_handler.py` 用：

```python
torch.hub.load("/opt/silero-vad", "silero_vad", source="local", trust_repo=True, skip_validation=True)
```

容器内**连不上 github.com**，在线拉取必然失败 → `FileNotFoundError: hubconf.py` → pipeline 崩了、8765 无人监听。
所以必须在宿主机准备好仓库再 COPY 进镜像：

```bash
git clone --depth 1 https://github.com/snakers4/silero-vad.git
cp -r silero-vad/* docker/speech-to-speech/silero-vad/
```

`build.ps1` / `build.sh` 会校验 `silero-vad/hubconf.py` 是否存在，缺失直接报错退出，并把目录搬进构建上下文。

## 构建

```powershell
# Windows
cd d:\projects\MinWorkBuddy\docker\speech-to-speech
.\build.ps1 -SourceRoot D:\work\speech-to-speech
```

```bash
# Linux
./build.sh --source-root /opt/speech-to-speech
```

## 三个必须知道的坑（都已在 Dockerfile / 补丁里处理）

### 1. torch 版本不匹配 → 静默退回 CPU

默认安装出来的 torch 是 **cu130** wheel，与宿主驱动 **12.8** 不兼容，
`torch.cuda.is_available()` 返回 `False`，STT/TTS 全部退 CPU：

| 配置 | Qwen3-TTS RTF |
|------|---------------|
| ggml 后端（CPU） | 3.7（4s 音频要 15s） |
| torch 后端 + cuda | 0.69（接近实时） |

Dockerfile 里默认从 cu128 索引重装 torch/torchaudio（`--no-deps`，不改依赖树），
并在 compose 里显式携带 `--qwen3_tts_backend torch --qwen3_tts_device cuda`。
不需要时用 `--build-arg SKIP_TORCH_REINSTALL=1` 跳过。

### 2. nltk punkt 缺失 → 助手一直说套话

`sent_tokenize_preserving_markdown_code` 调 `nltk.sent_tokenize`，需要 punkt 资源。
容器里 `nltk.org` 常被安全代理拦截（典型：`Security Violation: SSRF attempt to restricted IP`），
LookupError 被上层捕获后直接走兜底文案
**"I'm having trouble responding right now. Please try again."**。

`patches/apply_patches.py` 把调用点换成带正则兜底的 `sent_tokenize`，
即使完全没有 punkt 资源也能正常断句。补丁幂等，重复构建不会叠加。

### 3. transformers 新版无 rope_theta → TTS 加载崩溃

transformers ≥ 5.15 的 `MimiConfig` 没有 `rope_theta` 字段，
`qwen_tts/_transformers_compat.py` 里的 `base = config.rope_theta` 直接 AttributeError。
补丁改为 `getattr(config, "rope_theta", 10000.0)`。

## 国内化要点

| 层 | 处理 |
|----|------|
| 基础镜像 | `${BASE_REGISTRY}/nvidia-cuda:12.8.1-cudnn-runtime-ubuntu24.04`（中转，避免加速器卡死） |
| apt | 阿里云（ubuntu.sources 新格式也一并 sed） |
| pip / uv | 阿里云 PyPI，`UV_HTTP_TIMEOUT=180` |
| torch | 阿里云 pytorch-wheels/cu128 索引 |
| HuggingFace | `HF_ENDPOINT=https://hf-mirror.com`（Parakeet / Qwen3-TTS / Smart Turn 从这里下） |
| github | 完全不可达 → Silero VAD 走离线预置 |
| nltk | 下载失败不致命（有正则兜底） |

## 运行

```bash
cp .env.example .env
docker compose -f docker-compose.gpustack.yml --env-file .env up -d
docker compose logs -f pipeline
```

健康检查：

```bash
docker inspect --format '{{.State.Health.Status}}' speech-to-speech-pipeline-1
python -c "import socket;socket.create_connection(('127.0.0.1',8765),3)"
```

## 已知非致命告警

- `SoX could not be found`：镜像已安装 sox 与 libsox-fmt-all，正常情况下不再出现。

## 安全提示

GPUStack API Key 请通过 `.env` 注入（已被 `.gitignore` 忽略），不要写进 compose 或 Dockerfile。
