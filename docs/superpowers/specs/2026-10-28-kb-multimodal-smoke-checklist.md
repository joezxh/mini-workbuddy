# KB 多模态手动冒烟清单

- 日期：2026-10-28
- 关联 spec：`2026-10-28-kb-multimodal-design.md`
- 关联 plan：`docs/superpowers/plans/2026-10-28-kb-multimodal.md`
- 性质：**不进 CI**（依赖真实 provider 与 GPUStack 模型）；上线/部署后逐项人工勾验

## 0. 前置条件

- [ ] GPUStack（192.168.40.30）已部署：
  - [ ] **EmbeddingGemma 2**（768 维文本向量，与现有 `vector(768)` 列兼容）
  - [ ] 视觉模型（默认 `Qwen3-VL-32B`，可用 `MEDIA_VISION_MODEL` 覆盖）
  - [ ] 语音模型（默认 `Qwen3-ASR-1.7B`，可用 `MEDIA_ASR_MODEL` 覆盖）
- [ ] 部署环境已安装 **ffmpeg/ffprobe**（缺失时音视频上传会得到可读报错，属预期）
- [ ] `pip install -r requirements.txt`（新增 `ezdxf==1.4.5`、`matplotlib==3.11.2`）
- [ ] 模型管理已按需配置默认视觉（type=6）/语音（type=7）模型（未配置则走 env）

## 1. 创建知识库

- [ ] 新建 type=2/document 知识库，开启「多模态」开关
- [ ] 视觉/语音模型输入框可填可空（留空=服务端默认），保存后 `pipeline_config.media` 落库
- [ ] 未开启多模态的库上传 `.mp3` → 前端/后端 422「该知识库未启用多模态」

## 2. 图片

- [ ] 上传 1 张含文字的 PNG/JPG：文档状态 completed，segment_count=1
- [ ] 分段详情：`chunk_type=image`、`metadata.media_kind=image`
- [ ] 文本检索图片里的文字（OCR）与画面内容（描述）均可命中，结果带 media 块

## 3. 音频

- [ ] 上传 1 段 <2h 的 mp3/wav：completed，多段（ASR 句段）
- [ ] 分段 metadata 带 `{start_ms,end_ms}` 时间轴
- [ ] 检索命中音频段 → 行内播放器出现，点击自动 seek 到命中时间点（核心体验项）
- [ ] 上传 >2h 音频 → 422/failed 且 error_detail 含时长超限提示

## 4. 视频

- [ ] 上传 1 段 <30min 的 mp4/mov：completed，段数 ≈ 帧描述 + 转写段
- [ ] 单帧 VLM 失败不致整篇失败：`meta.media.partial_errors` 有记录且 status=completed
- [ ] 检索命中视频段 → 行内播放器 + seek；抽帧首帧缩略图可见
- [ ] 上传 >30min 视频 → 422/failed 含时长超限提示

## 5. DXF 图纸

- [ ] 上传 1 个含多图层文字标注的 DXF：completed，每图层 1 段（locator `{layer}`）
- [ ] 纯图形无标注 DXF → 单段兜底（文件名+图元统计），可检索
- [ ] 检索命中 → 显示「图层 X」标签
- [ ] 预览图（ezdxf+matplotlib 渲染）生成成功（浏览器可见）
- [ ] `.DWG` 文件 → 拒收并提示先转 DXF（本期非目标，属预期）

## 6. 检索过滤与混合链路

- [ ] 同一库混入文本文档 + 媒体文件后默认检索两者均回
- [ ] `media_kind=drawing/audio/video/image` 过滤只回对应类型
- [ ] `media_kind=document` 排除全部媒体段
- [ ] economy 模式知识库：媒体段走关键词链路仍可命中（NULL 向量不报错）

## 7. 边界与失败

- [ ] 通用 >100MB → 422；DXF >50MB → 422
- [ ] provider 断网/超时：文档 failed，`meta.failed_step` = extract/embed，error_detail 可读
- [ ] provider 恢复后「重试」按钮可重新摄取（复用 upload_store 落盘文件）

## 8. 观测

- [ ] 后端日志出现 `[KB 媒体] {filename} 摄取完成：N 段（kind）`
- [ ] 失败日志出现 `[KB 媒体] 文档 {id} 在 {step} 步失败`
