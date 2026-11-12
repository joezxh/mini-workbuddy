按 6 列整理。`[xxx]` 表示官方 extra（`uv add "pipecat-ai[xxx]"`），方括号内是包名/`git:` 前缀的为社区独立包（`uv add <包名>` 或 `uv pip install git+https://github.com/<...>`），`内置` 表示无需额外依赖。id `C01–C13` 为典型组合；`C14–C60` 用于列全其余所有可选包，三列**可任意交叉替换**，非固定推荐搭配。

| id | ASR 模型 | LLM 模型 | TTS 模型 | 说明 | 是否典型组合 |
|---|---|---|---|---|---|
| C01 | Deepgram `[deepgram]` | OpenAI `[openai]` | Cartesia `[cartesia]` | 官方低延迟经典三段式 | 是 |
| C02 | AssemblyAI `[assemblyai]` | Anthropic `[anthropic]` | ElevenLabs `[elevenlabs]` | 官方高质量英文语音 | 是 |
| C03 | OpenAI Whisper `[openai]` | OpenAI Responses `[openai]` | OpenAI `[openai]` | 单一厂商全家桶 | 是 |
| C04 | Whisper Local `[whisper]` | Ollama `内置` | Kokoro `[kokoro]` | 全本地离线、零 API Key | 是 |
| C05 | FunASR `[funasr]` | Qwen `[qwen]` | MiniMax `内置` | 国内网络/中文，Qwen 改 `base_url` 走百炼 | 是 |
| C06 | Google STT `[google]` | Google Gemini `[google]` | Google TTS `[google]` | GCP 全家桶 | 是 |
| C07 | Azure Speech `[azure]` | Azure OpenAI `[azure]` | Azure TTS `[azure]` | Azure 全家桶 | 是 |
| C08 | AWS Transcribe `[aws]` | AWS Bedrock `[aws]` | AWS Polly `[aws]` | AWS 全家桶 | 是 |
| C09 | Sarvam `[sarvam]` | Sarvam `[sarvam]` | Sarvam `[sarvam]` | 印度语言全家桶 | 是 |
| C10 | Groq Whisper `[groq]` | Cerebras `[cerebras]` | Rime `[rime]` | 极速推理 + 低延迟 TTS | 是 |
| C11 | Floe `[pipecat-floe]` | Floe `[pipecat-floe]` | Floe `[pipecat-floe]` | 社区单包覆盖三段 | 是 |
| C12 | Simplismart `[pipecat-simplismart]` | Simplismart `[pipecat-simplismart]` | Simplismart `[pipecat-simplismart]` | 社区单包覆盖三段 | 是 |
| C13 | Moonshine `[moonshine]` | Ollama `内置` | Piper `[piper]` | 轻量全离线（含 CPU 可跑） | 是 |
| C14 | Cartesia `[cartesia]` | Anannas `[pipecat-anannas]` | AssemblyAI `[assemblyai]` | 覆盖项：仅文档列出 AssemblyAI TTS，本地 checkout 无实现 | 否 |
| C15 | ElevenLabs `[elevenlabs]` | Baseten `[baseten]` | Async `[asyncai]` | 覆盖项：官方 extra | 否 |
| C16 | Fal Wizper `[fal]` | Crusoe `[crusoe]` | Bland `[bland]` | 覆盖项：官方 extra | 否 |
| C17 | Gladia `[gladia]` | DeepSeek `[deepseek]` | Camb AI `[camb]` | 覆盖项：官方 extra | 否 |
| C18 | Gradium `[gradium]` | Fireworks `[fireworks]` | Deepdub `[pipecat-deepdub-tts]` | 覆盖项：TTS 为社区独立包 | 否 |
| C19 | Meta `[meta]` | Google Vertex AI `[google]` | Deepgram `[deepgram]` | 覆盖项：官方 extra | 否 |
| C20 | Mistral `[mistral]` | Grok `[grok]` | Fish `[fish]` | 覆盖项：本地注册表用 `[xai]`，文档用 `[grok]` | 否 |
| C21 | NVIDIA Riva `[nvidia]` | Groq `[groq]` | Gandr `[pipecat-gandr]` | 覆盖项：TTS 社区包 | 否 |
| C22 | Smallest `[smallest]` | Inception `[inception]` | Gnani `[pipecat-gnani]` | 覆盖项：TTS 社区包 | 否 |
| C23 | Soniox `[soniox]` | Mistral `[mistral]` | Giggy `[pipecat-giggy]` | 覆盖项：TTS 社区包 | 否 |
| C24 | Speechmatics `[speechmatics]` | Nebius `[nebius]` | Gradium `[gradium]` | 覆盖项：官方 extra | 否 |
| C25 | Together `[together]` | Novita `[novita]` | Groq `[groq]` | 覆盖项：官方 extra | 否 |
| C26 | xAI `[xai]` | NVIDIA NIM `[nvidia]` | Hakim `[git:tryHakimAI]` | 覆盖项：TTS 需 git 安装 | 否 |
| C27 | Zoom AI `[zoom-ai]` | NVIDIA Omni `[nvidia]` | Hume `[hume]` | 覆盖项：`zoom-ai` 仅文档列出 | 否 |
| C28 | .wave `[pipecat-dotwave]` | OpenRouter `[openrouter]` | Inworld `[inworld]` | 覆盖项：ASR 社区包 | 否 |
| C29 | Audrey p99lab `[git:P99Lab]` | Perplexity `[perplexity]` | Kalpa `[pipecat-kalpa]` | 覆盖项：ASR/TTS 均为社区包 | 否 |
| C30 | Giggy `[pipecat-giggy>=0.2.0]` | SambaNova `[sambanova]` | Lokutor `[pipecat-lokutor]` | 覆盖项：ASR 需带版本约束 | 否 |
| C31 | Gnani `[pipecat-gnani]` | Smallest `[smallest]` | Maya `[git:MayaResearch@v0.1.0]` | 覆盖项：TTS 需 git + tag | 否 |
| C32 | Hakim `[git:tryHakimAI]` | Sprag `[pipecat-sprag]` | Mirai `[pipecat-mirai]` | 覆盖项：全社区包组合 | 否 |
| C33 | Oruk `[pipecat-oruk==0.1.0rc1]` | Together `[together]` | Mistral `[mistral]` | 覆盖项：ASR 为 rc 版需锁版本 | 否 |
| C34 | Quickdial `[pipecat-quickdial]` | OpenAI `[openai]` | Murf AI `[pipecat-murf-tts]` | 覆盖项：复用已列 LLM | 否 |
| C35 | Ringg AI `[git:Stonkr]` | Google Gemini `[google]` | Neuphonic `[neuphonic]` | 覆盖项：ASR 需 git 安装 | 否 |
| C36 | RTZR `[pipecat-rtzr]` | Ollama `内置` | NVIDIA `[nvidia]` | 覆盖项：复用已列 LLM | 否 |
| C37 | SLNG `[pipecat-slng]` | Qwen `[qwen]` | TTS Cache `[pipecat-tts-cache]` | 覆盖项：缓存层可叠加任意 TTS | 否 |
| C38 | Sprag `[pipecat-sprag]` | Sarvam `[sarvam]` | Pocket TTS `[pocket-tts]` | 覆盖项：TTS 可本地运行 | 否 |
| C39 | Uplift AI `[git:havkerboi123-stt]` | Cerebras `[cerebras]` | ReadAloud `[pipecat-readaloud]` | 覆盖项：Uplift 的 STT/TTS 是两个不同包 | 否 |
| C40 | Deepgram `[deepgram]` | Anthropic `[anthropic]` | ResembleAI `[resembleai]` | 覆盖项：复用已列 ASR/LLM | 否 |
| C41 | OpenAI Whisper `[openai]` | Groq `[groq]` | Respeecher `[pipecat-respeecher]` | 覆盖项：TTS 社区包 | 否 |
| C42 | Whisper Local `[whisper]` | Ollama `内置` | Quickdial `[pipecat-quickdial]` | 覆盖项：TTS 社区包 | 否 |
| C43 | Google STT `[google]` | Google Gemini `[google]` | Rumik `[pipecat-rumik]` | 覆盖项：TTS 社区包 | 否 |
| C44 | Azure Speech `[azure]` | Azure OpenAI `[azure]` | SILMA `[pipecat-silma]` | 覆盖项：TTS 社区包 | 否 |
| C45 | AWS Transcribe `[aws]` | AWS Bedrock `[aws]` | SLNG `[pipecat-slng]` | 覆盖项：TTS 社区包 | 否 |
| C46 | Sarvam `[sarvam]` | Sarvam `[sarvam]` | Smallest AI `[smallest]` | 覆盖项：官方 extra | 否 |
| C47 | FunASR `[funasr]` | Qwen `[qwen]` | SonexLabs `[pipecat-sonex]` | 覆盖项：TTS 社区包 | 否 |
| C48 | Groq Whisper `[groq]` | Cerebras `[cerebras]` | Soniox `[soniox]` | 覆盖项：官方 extra | 否 |
| C49 | Floe `[pipecat-floe]` | Floe `[pipecat-floe]` | Speechify `[speechify]` | 覆盖项：官方 extra | 否 |
| C50 | Simplismart `[pipecat-simplismart]` | Simplismart `[pipecat-simplismart]` | Speechmatics `[speechmatics]` | 覆盖项：官方 extra | 否 |
| C51 | Moonshine `[moonshine]` | Ollama `内置` | Sprag `[pipecat-sprag]` | 覆盖项：TTS 社区包 | 否 |
| C52 | AssemblyAI `[assemblyai]` | Anthropic `[anthropic]` | Supertonic `[pipecat-supertonic]` | 覆盖项：TTS 社区包 | 否 |
| C53 | Deepgram `[deepgram]` | OpenAI `[openai]` | Together AI `[together]` | 覆盖项：官方 extra | 否 |
| C54 | OpenAI Whisper `[openai]` | OpenAI Responses `[openai]` | Typecast `[pipecat-ai-typecast]` | 覆盖项：TTS 社区包 | 否 |
| C55 | Whisper Local `[whisper]` | Ollama `内置` | Uplift AI `[git:havkerboi123-tts]` | 覆盖项：TTS 需 git 安装 | 否 |
| C56 | FunASR `[funasr]` | Qwen `[qwen]` | Vakyam `[pipecat-vakyam]` | 覆盖项：TTS 社区包 | 否 |
| C57 | Google STT `[google]` | Google Gemini `[google]` | Voice.ai `[git:voice-ai-tts]` | 覆盖项：TTS 需 git 安装 | 否 |
| C58 | Azure Speech `[azure]` | Azure OpenAI `[azure]` | xAI `[xai]` | 覆盖项：官方 extra | 否 |
| C59 | AWS Transcribe `[aws]` | AWS Bedrock `[aws]` | XTTS `内置` | 覆盖项：XTTS 已弃用，不建议新项目 | 否 |
| C60 | Sarvam `[sarvam]` | Sarvam `[sarvam]` | XTTS-vLLM `[pipecat-xtts-vllm]` | 覆盖项：TTS 社区包，替代 XTTS | 否 |

**补充约束**

- 表格覆盖 39 个 ASR、32 个 LLM、60 个 TTS（合计 131 项），三列之间无耦合，任意行可换其中任意一格。
- **不可与三段链路组合**：Realtime/S2S 服务是替代整条链路的另一条路线 —— OpenAI Realtime/GPT-Live、Gemini Live(含 Vertex)、AWS Nova Sonic、Azure Voice Live、Grok Voice、Inworld Realtime、Ultravox，以及社区 `pipecat-boson`、`pipecat-thunderphone`。
- 官方 extra 可一次安装多个：`uv add "pipecat-ai[deepgram,openai,cartesia]"`；社区包各自独立发版，问题反馈到其源码仓库。
- 版本差异：`zoom-ai`、AssemblyAI TTS 等仅见于官方文档，当前 checkout 的 `pyproject.toml` / `src/pipecat/services/` 中无对应实现；以实际安装版本的 `src/pipecat/cli/registry/service_metadata.py` 为准。