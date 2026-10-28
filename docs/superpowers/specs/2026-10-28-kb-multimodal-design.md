# 知识库多模态支持设计（图片 / 语音 / 视频 / DXF 图纸）

- 日期：2026-10-28
- 状态：已确认（方案 C，待实现计划）
- 范围：MinWorkBuddy KB（`backend/app/services/kb/**`、`frontend/src/views/kms/**`）

## 1. 背景与目标

知识库现有能力以文本文档为主（document/table/qa/connector/proxy 形态），图片仅有「caption 手填 → 文搜图」雏形。目标是为知识库增加四类多模态文件的摄取与检索：

| 媒体类型 | 内容理解 | 检索依据 |
|---|---|---|
| 图片 | VLM 描述 + OCR | 描述/OCR 文本 |
| 音频 | ASR 转写（按句分段） | 转写文本 |
| 视频 | ffmpeg 抽帧(1帧/10s) → VLM 描述 + 音轨 ASR | 帧描述 + 转写文本 |
| DXF 图纸 | ezdxf 提取图层名 / TEXT / MTEXT 标注 / 块名 / 块属性 | 结构化文本 |

非目标（本期不做）：

- DWG 解析（要求用户先转 DXF；后续可加 ODA File Converter）
- 图搜图 / 音搜音（同模态互搜需第二套向量空间，无真实场景驱动）
- 多模态对齐向量空间（qwen3-vl-embedding / multimodal-embedding-v1 类）——架构预留，见 §3

## 2. 已确认的关键决策

1. **检索入口**：纯文本查询（文搜多媒体）。四类媒体各自经「内容→文本」提取器后，全部进入现有检索链路。
2. **DWG**：第一期只支持 `.DXF`（ezdxf 纯 Python 解析，零外部依赖）。
3. **模型服务**：vision / asr 各建一套可配置 provider（gpuastack | dashscope），对齐现有 embedding provider 体系。
4. **成本边界**：单文件 ≤100MB；音频 ≤2h；视频 ≤30min；DXF ≤50MB；超限拒收并明确提示。
5. **Embedding**：EmbeddingGemma 2（GPUStack 本地部署，原生 768 维），与现有 `kb_segment.embedding vector(768)` 列天然兼容，媒体转写文本与文档文本同向量空间。

## 3. 总体方案（A 为主 + 预留 B 扩展点）

媒体内容统一转成「分段文本 + 定位器」后复用现有 chunk→embed→pgvector(向量+trgm+RRF) 链路；检索算法零改动。架构预留未来多模态向量空间的扩展点：segment `metadata_` 完整保留模态溯源（时间轴/帧号/图层），届时可对存量段回填第二向量列而无需重传文件。

## 4. 架构

### 4.1 新增 `app/services/kb/media/` 包

```
extractor.py       MediaExtractor Protocol + 注册表（按 media_kind 分发）
image_extractor.py 图片 → VLM 描述 + OCR
audio_extractor.py 音频 → ASR 转写，按语义句边界分段
video_extractor.py 视频 → ffmpeg 抽帧(1帧/10s)→VLM 批量描述 + 音轨 ASR
dxf_extractor.py   DXF → ezdxf 解析图层/标注/块 → 结构化文本
```

统一输出：

```python
@dataclass
class MediaSegment:
    text: str                      # 转写/描述/标注文本
    locator: dict                  # {start_ms,end_ms} | {frame_index} | {layer}

@dataclass
class MediaExtraction:
    kind: str                      # image | audio | video | drawing
    segments: list[MediaSegment]
    meta: dict                     # duration / frame_count / partial_errors 等
```

### 4.2 分段策略

媒体分段**直接映射为 `KbSegment`，跳过通用 chunker**：ASR 句段、帧描述、图层标注本身是自然语义边界，再切只会破坏上下文。

### 4.3 数据模型变更（最小化）

- `kb_segment.chunk_type` 枚举扩展：`audio | video | drawing`（`image` 已有）
- `kb_segment_asset` 新增 `locator JSONB`（可空），mime 白名单扩为 `audio/*`、`video/*`
- 原文件沿用 `upload_store` 落盘（`kb_document.meta['file_path']`），不复制不转存
- `kb_document.meta['media']` 记录 `{kind, vision_provider, vision_model, asr_provider, asr_model, duration, frame_count, partial_errors}` 溯源

## 5. 摄取管线

- 接入点：`parser_selector.select_parser` 按扩展名分发到新增 `MediaParser`（audio: mp3/wav/m4a；video: mp4/mov；drawing: dxf）
- 管线状态机（pending→processing→completed/failed）与 `meta.failed_step` 复用；`pipeline_runner` 对媒体类型自动切换为 `extract → embed` 两步
- 提取在后台任务执行（长视频转写耗时分钟级，不阻塞上传响应）
- **部分成功语义**：视频单帧 VLM 失败不导致整篇失败，失败帧记入 `meta.media.partial_errors`，有 ≥1 个成功分段即 completed；音频 ASR 全失败 = 无内容，整篇 failed
- 依赖检查：摄取前探测 `ffmpeg`（音视频必需，缺失则拒收并提示）与 `ezdxf` 包

## 6. Provider 配置

新增 `app/core/config/_media.py`：

```python
MEDIA_VISION_PROVIDER   # gpuastack | dashscope（默认 gpuastack）
MEDIA_VISION_MODEL      # 如 Qwen3-VL（GPUStack）或 qwen-vl-max-latest（百炼）
MEDIA_ASR_PROVIDER      # gpuastack | dashscope
MEDIA_ASR_MODEL         # 如 Qwen3-ASR（本地）或 paraformer-v2（百炼）
```

- 两者均走 OpenAI 兼容协议：VLM 用 `chat/completions`（图片 base64 进 content），ASR 用 `audio/transcriptions`（Whisper 协议）；provider 差异只在 base_url/api_key/model，一套客户端代码通吃
- 复用「模型管理默认模型（type=5+is_default）优先，env 兜底」解析链，新增模型类型：type=6 vision、type=7 asr
- collection 级覆盖：`kb_collection.retrieval_settings` 增加可选键 `vision_model` / `asr_model`

## 7. 检索与前端

**检索侧（零算法改动）**：媒体文本段天然进入现有 向量+trgm 关键词+RRF 混合链路（EmbeddingGemma 2 与文档文本同空间）。

**结果增强**：

- 命中媒体段时返回体增加 `media` 块：`{kind, file_path, locator, asset_url}`；音频/视频带 `{start_ms,end_ms}`，DXF 带预览图
- 新增可选过滤参数 `media_kind`（image/audio/video/drawing/document）：前四者映射为对应 `chunk_type` 精确匹配；`document` 表示「排除媒体段」，映射为 `chunk_type IN (text, qa, table_row, parent, child)`（即现有全部文本类 chunk_type）

**前端**：

- 上传：接受 `.mp3/.wav/.m4a/.mp4/.mov/.dxf`，超限前端预校验 + 后端强校验
- 创建向导：`multimodal_enabled` 语义落地为「启用媒体摄取」，vision/asr 模型选择替换现有硬编码 Vision embedding 下拉；未启用时拒收媒体文件
- 结果展示（DocumentPane / 检索面板）：音频/视频行内播放器点击 seek 到 `start_ms`；视频抽帧首帧缩略图；DXF 预览图 + 图层命中列表；分段详情显示定位信息

## 8. 错误处理

- 媒体处理失败 → 文档 `status=failed` + `error_detail`（沿用现有状态机），`meta.failed_step` 标记 `extract` / `transcribe` / `embed`
- provider 调用失败重试 2 次（指数退避）；超时 VLM 120s/帧、ASR 120s/段
- 抽帧 / ASR 产生的中间文件（帧图片、临时音轨）处理后即删，不落 `UPLOAD_DIR` 长存

## 9. 测试策略（对齐 tests/kb 既有风格，fake provider 注入）

- 单元：4 个提取器正常 / 空内容 / 超限 / 损坏文件；DXF 最小 fixture；ASR 句段边界；locator 序列化
- 摄取集成：fake vision/asr provider 走完整 extract→embed→检索命中，断言 chunk_type、locator、asset 落库
- 检索：media_kind 过滤、媒体段参与 RRF、命中返回 media 块
- API：上传超限 422、未启用 multimodal 拒收、部分成功时文档状态
- 真实 provider 冒烟不进 CI（标记 slow / manual）

## 10. 风险与开放点

- EmbeddingGemma 2 需在 GPUStack 上先行部署并确认 768 维输出；部署前媒体摄取可先用现有默认 embedding 模型联调
- 视频抽帧 VLM 成本（30min ≈ 180 次调用）在并发摄取时可能触发 provider 限流，提取器需按 provider 限速（串行/低并发）
- 前端 `isVisionModel` 正则与硬编码模型选项需同步清理，避免旧语义残留
