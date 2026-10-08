# Gander —— 全双工多模态交互

两个镜像，对应双机部署的两半：

| 变体 | 镜像 | 跑在 | 端口 | 职责 |
|------|------|------|------|------|
| `local` | `gander-asr` | 本地客户端 | 80 / 8995 | faster-whisper ASR + Nginx 反代到远端 Web |
| `remote` | `gander-thinker` | 远端 GPU 服务器 | 8000 | 视觉/音频编码器 + Talker TTS |

```
浏览器 → 本地 Nginx:80 → 远端 Thinker:8000（Web + WebSocket）
远端 Thinker → 本地 ASR:8995
远端 Thinker → GPUStack /v1（LLM，可选）
```

## ⚠️ 先看能力边界

MiniCPM-o 4.5 的 Thinker 管线把音频/视觉嵌入**直接注入 LLM 内部**（`inputs_embeds`），
并从 LLM 中间层取 `hidden_states` 驱动 Talker TTS。纯 OpenAI 兼容 API 三者都做不到：

| MiniCPM-o 需要 | OpenAI 兼容 API 提供 |
|---|---|
| `inputs_embeds`（原始向量注入） | 仅 `input_ids`（文本 token） |
| `hidden_states`（中间层输出） | 仅返回生成文本 |
| KV cache 直接控制 | 服务端管理 |

所以 `configs/serve_remote.yaml` 里的「远程 LLM 模式」目前是**参考模板**，完整实现需要自研
`RemoteLlmBackend` 适配层（改造点列在该文件底部注释里）。

当前可行的折中：

1. GPUStack 只作为 Codex Brain（替代 `worker.provider=codex`），不替代 Thinker LLM；
2. 纯文本模式，跳过音频/视觉编码；
3. 本地跑完整 MiniCPM-o（INT4 量化），GPUStack 仅作备份。

**构建镜像可行，端到端 duplex 能力目前受限。**

## 构建

```powershell
# Windows
cd d:\projects\MinWorkBuddy\docker\gander
.\build.ps1 -Variant local
.\build.ps1 -Variant all -SourceRoot D:\projects\Omni-Interaction-Agent
```

```bash
# Linux
./build.sh --variant local
./build.sh --variant all --source-root /opt/Omni-Interaction-Agent
```

构建上下文是源码仓库根（需要 `minicpm_ft/` 与 `gander_runtime/`），
脚本会把 `nginx/default.conf.tmpl` 与 `entrypoint_local.sh` 暂存到源码根的 `.docker-build/`。

## 国内化要点

| 层 | 处理 |
|----|------|
| 基础镜像 | `${BASE_REGISTRY}/nvidia-cuda:12.4.1-cudnn-devel-ubuntu22.04`（中转） |
| apt | 阿里云 |
| pip | 阿里云 PyPI |
| torch | 上游用 `https://download.pytorch.org/whl/cu124`（国内极慢）→ 改为阿里云 PyTorch 镜像 `cu124` 索引，可用 `--torch-index-url` 覆盖 |

## 目录结构

```
gander/
├── Dockerfile.local          # ASR + Nginx
├── Dockerfile.remote         # Thinker（编码器 + Talker）
├── nginx/default.conf.tmpl   # 反代模板（REMOTE_THINKER_HOST 由 entrypoint 替换）
├── entrypoint_local.sh       # 容器入口
├── configs/serve_remote.yaml # 远程 LLM 模式配置模板
├── docker-compose.yml        # 本地 GPU 模式
├── docker-compose.cpu.yml    # CPU 覆盖层
├── build.{ps1,sh} / push.{ps1,sh}
├── .env.example
└── README.md
```

## 运行

```bash
cp .env.example .env
docker compose up -d                                              # GPU
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d   # CPU
```

验证：

```bash
curl http://localhost:8995/health     # ASR
curl -I http://localhost:8080         # Nginx 入口（默认已避开 80）
```

## 前置

| 项目 | 最低要求 |
|------|---------|
| GPU（local 变体） | ≥2GB VRAM，无 GPU 时改 CPU 模式 |
| GPU（remote 变体） | ≥12GB VRAM（模型 ~6GB + KV Cache ~4GB） |
| NVIDIA Driver | ≥535 |
| Docker | ≥24.0 + nvidia-container-toolkit |
| 网络 | 远端 ⇄ 本地 ASR:8995 双向可达 |
