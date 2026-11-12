# 会中人脸与视觉分析（SP-3：帧采样 ＋ 人像 1:1 到场核验）设计

> ## 覆盖性修订总纲：改用 CompreFace（2026-11-04，用户裁决 Q1）
>
> **用户指令**：「insightface 无商用授权，人脸识别采用 CompreFace」。本文**下半部原文整体保留作为设计对照**，但凡与 insightface 自建容器相关的设计一律以下述结论为准；完整冲突分析、失效-替换对照表与统一契约见 `2026-11-04-meeting-ai-spec-review-and-revision.md` §4。本轮只做「设计 + 部署件」，**不接业务链路**（不写 Java 核验代码、不改 worker 视频轨、不部署运行）。
>
> **实施定版指针（2026-11-05）**：本文实施以 `2026-11-05-meeting-ai-specs-implementation.md` 的 D1–D6 为准；`ai_party_verify_record.verify_type VARCHAR(24)` 由 V3.56 一次性建立（D4），菜单只保留 9506（D5），G0–G3 门禁未过不得置 `MEETING_FACE_POC_PASSED=true`。
>
> **生效版指针（2026-11-06，C02/P0-2 收口）**：本文 §3–§13 的 2026-11-04 原文已整体隔离为历史设计对照，**不得作为实施依据**。后续开发、评审、验收一律以 `2026-11-06-face-vision-analysis-effective-spec.md`（单一生效版精简 spec）为准；本文顶部总纲 A–E、D-2 段、`2026-11-04-meeting-ai-spec-review-and-revision.md` §3 统一契约、`2026-11-05-ai-meeting-consolidated-revision.md` §4/§7 为该生效版的上位依据。门禁状态与剩余真机/法务任务见生效版 §9。
>
> **事实订正（2026-11-06，评审方案 C20/C21/C29）**：下列三句属 2026-11-04 时点结论，现已失效 —— ①「本轮只做设计 + 部署件、不接业务链路」：自定义 core 镜像（YuNet + SFace）已构建并部署到 `192.168.110.169:8050`，`verify.ps1` 9/9 通过，用户人工放行后落地收敛版 1:1 链路（生效版 §2/§7）；但 **G0/G1/G2 未取证、G3 整体未通过、`MEETING_FACE_POC_PASSED=false`、阈值留空恒 `FACE_INSUFFICIENT`**，仍不得投产。②「`PartyApi` / `PartyIdentityForVerifyRespDTO` 为设计态、代码零命中」：SP-5（Task 7）已在 `Demo-module-uaa-api` 落地这两个对象，实施顺序 `SP-1/2 → SP-5 → SP-4 → SP-3` 不可颠倒这一结论仍然有效。③「CompreFace REST 端点全部待实测」：detect / verify 返回结构已实测，1:N 路径 404 已验证。
>
> ### A. 新增差异登记（接 §0 的 T5–T8）
>
> | # | 上游原文 | 本修订的决定 | 理由 |
> |---|---|---|---|
> | T5 | 全文以 insightface `buffalo_l` 自建 `insightface-svc/app.py` 为模型服务 | **整体替换为 CompreFace 自托管平台**，走 `POST /api/v1/verification/verify` 的 1:1 两图比对；不做 1:N 检索、不建 subject 底库 | 用户裁决；CompreFace 提供 REST 化的人脸服务，避免自建模型容器与权重分发 |
> | T6 | §5 以 `ai_face_gallery.embedding REAL[]` + Java `FaceSimilarityCalculator` 余弦为底库方案 | **整表废弃**，业务侧只存 `similarity`、结论、依据摘要与模型标识 | CompreFace 直接返回相似度；平台不再持有生物特征向量，撤回即无副本可残留 |
> | T7 | §8.4.1-L1 判定「G3 现状为未通过」原因是 insightface 预置模型非商用 | **G3 保留且仍为未通过**，但原因改写为「CompreFace 所选具体模型权重的商用许可待核实 + 法务留档」 | 换件不等于自动取得模型权重商用授权，见 D 段 |
> | T8 | §3.3/§9.4 要求服务侧 `persistence:false`、不挂任何卷 | 改写为「CompreFace 自带 Postgres 命名卷，靠**禁用 recognition/subject 能力**把业务侧生物特征落库面收敛为零」 | 平台级持久化无法关闭，只能约束使用方式；卷的留存期/备份加密/删除流程列为 G3 必答项 |
>
> ### B. 逐章替换结论
>
> | 原章节 | 处置 | 替换结论 |
> |---|---|---|
> | §3.1 帧从哪里取 | 保留结论 | worker 服务端取帧仍为选定形态；**G0「视频轨能否到达 worker」仍是唯一实施前置且至今未证实**，本轮不触碰 `worker.py:84` |
> | §3.2 端到端链路 | 改写步骤 3–6 | `FaceProvider.detect` → `POST /api/v1/detection/detect`（`result[].box{x_min,y_min,x_max,y_max,probability}`）；`FaceProvider.embed` 取消；改为核验任务期把「证件照字节 + 会中帧」送 `POST /api/v1/verification/verify` 取 `similarity`；多人同框由适配层按 `result.length > 1` 拒答（不再依赖服务返 409 `MULTI_FACE`）；质量门用 `box.probability` 与框尺寸替代原 `minQuality` |
> | §3.3 服务契约 | 废弃重写 | 请求头 `x-api-key`（服务 key）+ 外层 nginx `X-API-Key`；不再有 `/v1/face/embed`、`embeddingBase64`、`embeddingDim`、`X-Verify-Token` HMAC；任务窗口守卫上移到 Java「核验任务期 + 单独同意 + 一次性 verifyId」 |
> | §4.1 在场事实/告警分离 | **保留** | 未检出人脸不等于离席、默认不告警、`skipped` 不进连续计数 —— 与模型服务无关，继续有效 |
> | §4.2 只在显式任务期核验 | **保留并强化** | 每次核验临时取证件照字节（SP-5 `FileApi.getFileContent`），不在服务端建当事人底库；无 `FACE_COMPARE` 有效同意零外呼 |
> | §4.3 判定表 11–18 | 重定义 | `FACE_NO_BASE`/`FACE_BASE_STALE` 废弃（无底库）→ 改 `FACE_SOURCE_UNAVAILABLE`（证件照取不到）、`FACE_SERVICE_UNAVAILABLE`；`FACE_UNSTABLE` 改为「窗口内多次 similarity 极差超过 G2 标定阈值」；阈值 `similarity-threshold` 按 CompreFace 口径由 G2 本地标定，**不得沿用余弦 0.45**；`FACE_MISMATCH` 仍是唯一不通过值，文案仍只能是「疑似不一致，请主持人现场确认」 |
> | §4.4 相似度计算位置 | 废弃 | Java 不再算余弦、不再有 `embedding-dim` 常量与畸形向量用例 |
> | §5 底库与数据通路 | 废弃重写 | 无 `ai_face_gallery`、无 pgvector/REAL[] 取舍、无 `source_url_hash`；`ai_party_verify_record` 增 `face_similarity`/`face_frames_used`/`face_service_model`；与 SP-5 的接缝保留 `PartyApi`（**2026-11-06 订正：该 Feign 与 `PartyIdentityForVerifyRespDTO` 已由 SP-5 落地，见顶部事实订正②**）、`FileApi.getFileContent`、`ai_party_consent`、`status` 不改、处置由人 |
> | §6 接口契约 | 废弃三端点 | `enroll`/`gallery/status`/`gallery/delete` 删除；保留 `verifyType=FACE` 走 SP-5 `/ai/party/verify/idcard` 扩展与 `GET /ai/party/verify/get`；`video.available` 探活改为 CompreFace 健康探针，仍受 §3 统一门禁约束；菜单 9505/9507 收缩，仅保留 9506 等人像核验发起相关权限行 |
> | §7 DDL | 重写 | V3.56 改为「`ai_meeting_presence` + `ai_party_verify_record` 增列 + kind 注释同步」，**删除 `ai_face_gallery` 建表与唯一索引**；执行前置仍为 V3.52(SP-5) 与 V3.49(SP-1/2)，实施顺序不变 |
> | §8.1 四道门禁 | 保留 G0–G2、改写 G3 | G0 帧可达、G1 检测可用率、G2 FAR/FRR 标定继续有效（G2 改为按 CompreFace similarity 口径）；G3 见 D 段 |
> | §8.2/§8.3 算力与降级 | 保留结构、改数值来源 | A/B 双分支与断路器/降级阈值结构保留，具体延迟与采样值改为 CompreFace 实测后回写 |
> | §8.4 部署形态 | **整体替换** | 指向 `Demo-deploy/compreface/`（官方多容器 compose + nginx 模板 + 4 个 ps1 + .env.example + README）；端口避开 8011/8020/8021/8080/80；`insightface-svc/{app.py,Dockerfile,requirements.txt,models/buffalo_l}`、§8.4.4–8.4.6 的 Dockerfile/requirements/app.py 全部作废 |
> | §8.4.9 待实测项 | 重写 | V1–V6 换成：多容器健康与启动顺序、detection 返回结构、verification 返回 similarity 字段、CPU 分支 P50/P95、中文东亚面孔本地 FAR/FRR、模型权重许可与替换件接口一致性；未回写 README 前不得置启用开关 |
> | §9 合规与安全 | 保留原则、改写 §9.3/§9.4 | 单独同意、`FACE_COMPARE` 独立于 `IDCARD_VERIFY`、告知必答三点（不存图像 / 无活体检测 / 不改状态）、定性措辞禁令、1:N 与跨会议聚合红线**全部保留**；§9.3 的「向量物理删除」改为「平台不持有向量，删除的是核验记录与 CompreFace 侧可能残留的管理数据，撤回流程为 G3 必答项」；§9.4 禁止清单中的「帧落盘/日志无 base64 长串」继续有效 |
> | §10 测试 | 重写用例 | `FaceSimilarityCalculatorTest`、`FaceGalleryServiceTest` 作废；换 `CompreFaceClientContractTest`（请求/返回解析、多人同框、无脸、探活失败、任务窗口外拒发）与 `PartyFaceVerdictTest`（重定义后的 FACE_* 判定）；`verify.ps1` 四段式成为部署侧唯一可执行证明 |
> | §11/§12/§13 | 同步 | 风险表、自检表、交付清单按 A/B 段与本表逐项替换；号段划分（错误码 `1_040_065_*`、迁移 `V3.56/V3.57`、菜单 `9505–9507` 区间）保留，具体条目按 §6/§7 收缩 |
>
> ### C. 官方资料取证状态（不得当作已坐实）
>
> 本环境 `raw.githubusercontent.com`、GitHub 页面、deepwiki 的 `web_fetch` 均超时或 429，CompreFace 官方 REST 文档全文**未能取到**。上述端点路径、请求体与返回字段最初来自公开检索摘要并标注「待实测」；**2026-11-06 订正**：`Demo-deploy/compreface/scripts/verify.ps1` 已扩为 9 段并实测 9/9 通过（detect `box.probability`、verify `face_matches[0].similarity`、1:N 404、权重 SHA256），端点契约不再是「待实测」。但实测仅证明契约层，**G0/G1/G2 未取证、G3 整体未通过**，`MEETING_FACE_POC_PASSED` 仍保持 `false`。
>
> ### D. 权重选型与 G3 门禁改写（授权认知，只解决「权重授权」子项）
>
> **2026-11-05 用户裁决**：CompreFace 部署不再沿用平台内置可能限非商用研究的模型权重，改用**可商用开源权重**（见 D-2 段）。CompreFace 平台代码为 Apache-2.0，可用于商业项目，但公开资料显示其内置模型仍含 FaceNet（自定义许可）、SubCenter-ArcFace / InsightFace 系模型，部分权重可能限非商业研究；换件解决的是「自建 insightface 容器」这条路径，不等于自动取得任何模型权重的商用授权。
>
> 因此 G3 的处置收敛为**子项级结论**：**「模型权重授权」子项已解决**（已选定可商用开源权重，就所选权重许可证条款而言不再有非商用限制）；**G3 整体仍为未通过** —— 其余四项待办逐条保留：①模型名与版本清单 ②权重许可全文快照与法务确认留档 ③内置 Postgres 命名卷的留存期/备份加密/撤回删除流程 ④告知文案三点审定。G0/G1/G2 未取证状态不变，`MEETING_FACE_POC_PASSED` 保持 `false`，`video.available` 恒 `false`，实施计划 Task 11「仅当 Task 10 全部通过」的前置一字不改。
>
> 禁止把本段扩大表述为「G3 已通过」「授权问题已整体解决」或「允许置启用开关」。
>
> ### D-2. 可商用开源权重选型（2026-11-05 定版）
>
> 用户给出的候选为 dlib ResNet、OpenFace、SFace、MediaPipe FaceDetector / YuNet（且「不限于」）。本场景是**证件照与会议画面的一对一（1:1）到场一致性核验**：中文东亚面孔为主、侧脸/低光/遮挡、离屏 1–2m、CPU-only（不假设 GPU）、G1 要求召回 ≥85%，G2 要求本地 FAR/FRR 标定。**检测器与识别器必须配对**，四个候选里 Detector/YuNet、MediaPipe 属检测侧，dlib ResNet、OpenFace、SFace 属识别侧。
>
> #### 主选组合
>
> | 角色 | 模型 | 权重文件 | 许可分层（代码 / 权重 / 训练数据） | 选它的理由 |
> |---|---|---|---|---|
> | 检测（替换原 SCRFD） | **YuNet**（OpenCV Zoo） | `face_detection_yunet_2023mar.onnx` | 代码与权重同仓、OpenCV 系 Apache-2.0；**训练数据（WIDER FACE 等）许可须单独核实并留档** | ONNX、CPU 友好、小目标与侧脸召回较好、输入尺寸可配；与识别侧同属 OpenCV 生态，可共用 `FaceDetectorYN` / `FaceRecognizerSF` |
> | 识别 / 1:1 比对 | **SFace**（OpenCV Zoo；DeepFace 等库以其为后端之一） | `face_recognition_sface_2021dec.onnx` | 同上；**训练数据许可与来源须单独留档** | 128 维 L2 归一化特征、余弦/L2 比对由 OpenCV 原生支持、单次推理开销低、无需 GPU；适合证件照 vs 会中帧的 1:1 比对 |
>
> #### 备选与不选理由
>
> | 候选 | 判定 | 理由 |
> |---|---|---|
> | dlib ResNet（`face_recognition` 那套） | 备选（门禁式简单场景） | Boost Software License 对**代码**免费商用；128 维、精度低于 ArcFace 系；其预训练 `.dat` 权重与训练数据集（LFW 类）的商用边界须单独核实，不能把 Boost 当作权重许可结论 |
> | OpenFace | 不选 | Apache-2.0 可商用，但 nn4.small2 属 Torch7/Lua 老栈、维护停滞，ONNX / CompreFace 插件生态适配代价高，精度不占优 |
> | MediaPipe FaceDetector / BlazeFace | 检测侧备选 | Apache-2.0 可商用，TFLite 偏近距大脸，与 CompreFace 的 Python/ONNX 插件生态不契合；离屏 1–2m 场景不如 YuNet |
> | 其它扩展候选（「但不限于」） | 需先过三层核实 | 任何新增候选必须先给出**代码许可、权重许可、训练数据集许可**三层出处，才可进入备选表 |
>
> #### 三层许可核实清单（G3 权重授权子项的边界）
>
> 1. **代码许可**：OpenCV / OpenCV Zoo、dlib、OpenFace、MediaPipe 各自的源码许可，可查、可留档。
> 2. **权重许可**：`.onnx` / `.dat` / `.t7` 预训练权重自身的许可，**与代码许可不等价**；须取得许可全文与出处链接。
> 3. **训练数据集许可**：WIDER FACE / CASIA-WebFace / LFW / VGGFace2 等数据集常含「仅研究用途」条款，须逐项核实并留档。
>
> **平台代码 Apache-2.0 ≠ 权重可商用；Boost / MIT / Apache-2.0 是代码许可，不能直接当作权重许可结论。** 本轮按用户裁决只把「权重授权」子项判为已解决，许可快照、法务意见、模型清单等仍属 G3 待办。
>
> #### 换权重对设计的连带影响（已同步到 §6.5 / §8.1 / §13）
>
> - 识别维度由 `512` → **128**：删除 `embedding-dim` 配置（且 CompreFace 1:1 架构下平台本就不持有向量）。
> - 相似度分布随模型改变：余弦占位 `0.45` **作废**，G2 必须按 YuNet + SFace 在本地同人异时/异人样本重标定 FAR/FRR，标定前阈值不得写入生产配置。
> - 不建 subject 底库：删除 `gallery-retention-days`；自建 embed 服务取消，`task-secret` HMAC 任务凭据一并删除。
> - `facePolicy` 的 `long-edge` / `jpeg-quality` 与 YuNet 输入尺寸对齐，具体值由 G1 标定后回写；`min-quality`（SCRFD 口径）改按 YuNet `box.score` 门槛表达。
> - **接入形态**：官方 `exadel/compreface-core` 镜像内置模型不能仅靠环境变量切换，须走**自定义构建路径**。按用户 Q1 裁决，本轮原只声明模型来源与校验；**2026-11-05 部署 PoC 补记**：插件适配层已实现并落地——`Demo-deploy/compreface/build/core-build/`（yunet/sface 插件 + Dockerfile）构建出 `compreface-core-yunet-sface:1.2.0`，权重已下载并过 SHA256 校验，`docker compose up` 实际部署成功，`verify.ps1` 9/9 通过（detect box、verify 同人 0.919 / 异人 0.078、1:N 红线 404），实测口径回写部署件 README §6/§7。**仍不接业务链路**；G1 真实帧召回率、G2 阈值标定、G3 其余项状态不变，`MEETING_FACE_POC_PASSED` 保持 `false`。
> - 红线不变：只走 1:1 verification、禁止 recognition/subject/face collection、平台不持有向量、`FACE_COMPARE` 独立单独同意、核验永不修改 `party_identity.status`、帧不落盘不进日志、`FACE_MISMATCH` 唯一不通过且措辞含「疑似/请现场确认」。
>
> ### E. 未受影响的保留结论
>
> G0 未证实前不得开工；单帧不结论（连续帧 + 跨时长 + 质量达标）；`FACE_MISMATCH` 唯一不通过且措辞含「疑似/请现场确认」；不改 `party_identity.status`、处置由人；在场事实与告警分离；实施顺序 **SP-1/2 → SP-5 → SP-4 → SP-3**；SP-1/2 的 `MeetingAlertDO`、`ai_party_verify_record`、`PartyApi` 均为设计态（见评审方案 C20）。

- 日期：2026-11-04
- 状态：待用户复核（**模型服务已按用户裁决改 CompreFace，见上方覆盖性修订总纲；本轮不接业务链路**）
- 上游文档：`2026-11-04-meeting-room-ui-design.md`（SP-1/SP-2，本文**作废**其 §8 不变量② 与 §1.2 的一条非目标）、`2026-11-04-acoustic-ser-design.md`（SP-4，本文复用其开关快照与降级机制）、`2026-11-04-party-identity-verification-design.md`（SP-5，本文是其所预留 `FACE_MISMATCH` 的唯一生产者）
- 落地范围：`Demo-ai/deploy/livekit-worker`（视频轨接入；G0 未证实前只提交观测日志）、`Demo-module-ai-server`（核验编排，本轮不接业务链路）、`Demo-basic/Demo-module-uaa`（复用 SP-5 的 `PartyApi`）、`Demo-web`（视频卡片翻转与录入入口）、`Demo-deploy/compreface`（**替换原 `Demo-deploy/face`**；采用可商用开源权重的自定义构建路径；**2026-11-05 部署 PoC 已完成**：插件适配层、自定义镜像、权重下载与 SHA256 留档、容器化部署与契约实测均已落地，仍不接业务链路）
- 本文所有类名、行号、端点、错误码段、迁移号、菜单 ID 均以**实读代码 ＋ 全仓扫描**为准，出处逐条列在 §2
- 算力前提（与 SP-4 同，用户未裁定，按 C 方案执行）：**本文不假设任何 GPU 可用**，A/B 双分支加切换阈值见 §8
- **本文有一个前置事实至今未证实**：视频帧能否到达 worker。因此 §8.1 把「G0 帧可达」设为第一道门禁，G0 未通过时本文其余部分一律不得开工

---

## 0. 与已交付设计的差异登记（评审先读这里）

> **2026-11-05 修订索引（可商用开源权重）**：①顶部总纲 D 段改写为「仅权重授权子项已解决、G3 整体未通过」，新增 **D-2 段**给出 YuNet + SFace 选型与三层许可核实清单；②§1.1 目标 4 改为 CompreFace 1:1 ＋ 可商用权重；③§6.4 钉死换权重不改变门禁公式；④§6.5 删除 `task-secret` / `embedding-dim: 512` / `gallery-retention-days` / 余弦占位 `0.45` 并重定阈值与 YuNet 策略口径；⑤§8.1 G3 行、§8.4 入口、§11/§12/§13 加作废指针；⑥CompreFace 部署件同步模型来源、镜像标识、权重校验位与探针断言。**G0/G1/G2 未取证状态、`MEETING_FACE_POC_PASSED=false`、Task 11 前置均不变。**

| # | 上游原文 | 本文的决定 | 差异性质 | 理由 |
|---|---|---|---|---|
| T1 | SP-1/SP-2 §8 不变量②「`video` 永远不产出 `kind='video'` 告警行」，§1.2 把视频行为分析整体列为非目标，§9 对齐表把视频卡片钉为 `ready:false` | **作废该不变量，但分期作废**：本文交付设计；`video` 卡片的 `available` 只有在 §8.1 的 G0–G3 四道门禁全部通过后才能翻为 `true`，在此之前实现仍须保持 `available=false`、不写开关行、不产告警 | 受门禁约束的修订 | 这条不变量当初是为了防止「界面上像已具备」，它约束的是**上线状态**而不是设计上限。若本文一栏笔就把它删掉，会出现设计已写、能力未证、界面已开三重错误叠加；把翻转条件写成可验证门禁，才能既推进又不重演伪能力 |
| T2 | SP-5 §1.2 预留 `verdict` 取值 `FACE_MISMATCH` 并注明「SP-3 前恒不出现」；SP-5 §7.1 的 `ai_party_consent.scope` 注释预留 `FACE_COMPARE(SP-3)` | 本文是这两个预留值的**唯一生产者**；核验记录直接写入 SP-5 的 `ai_party_verify_record`（增列），同意复用 `ai_party_consent`（scope 取 `FACE_COMPARE`），**不新建第二套核验或同意表** | 兑现预留 | 一次读码确认 SP-5 的 `PartyIdentityForVerifyRespDTO` 已含 `idCardFrontUrl`（SP-5 §3.3 L143）——证件照底库通道已就绪，本文无需扩展 `PartyApi`。若本文另建核验表，同一当事人会出现两条互不相认的「核验历史」 |
| T3 | SP-4 §0-S1 把开关 `kind` 合法集扩为 `voice`、`ser`、`video` | 本文**沿用 `video` 这个既有取值**，不新增第四值；`video` 的语义由「视频行为分析（未交付）」收敛为「人像到场核验」，并在 `ai_meeting_alert` 行上用新列 `video_channel` 区分 `presence` 与 `identity` | 收敛而非扩集 | 上游三处（§1.2、§9、§7.1 的 `kind` 注释）都写死 `video`，再造一个 `face` 值要把这三处外加 SP-4 一处全部改一遍，收益只是命名好看；语义收窄 ＋ 子通道列可控得多 |
| T4 | 上游未规定帧从哪里取 | 选定 **worker 服务端取帧**（§3.1），并明确禁止复用前端 `MediaCapture.vue` 的抓帧链路 | 新增决定 | 该组件的 `uploadMedia` 是**假上传**（§0.1），且前端只拿得到本地摄像头的流与已渲染的远端元素，覆盖面与门控都不成立 |

### 0.1 本文顺带坐实的第二处伪能力（前端假上传，与 SP-4 §0.1 同源不同处）

`Demo-web/src/views/ai/disputehall/components/Demo/MediaCapture.vue`：

```javascript
// L151-170：所谓「上传」
const uploadMedia = async (blob: Blob, type: string) => {
  const formData = new FormData();
  formData.append('file', blob, `${type}_${Date.now()}`);   // 组装了 FormData
  formData.append('sessionId', props.sessionId.toString());
  formData.append('type', type);
  console.log('上传媒体:', type, blob.size);                 // ← 只打印，从未发送
  if (autoAnalyze.value) {
    const result = { id: Date.now(), type: ..., data: { summary: '分析结果...' }, ... };
    emit('analyzed', result);                               // ← 伪造分析结论
  }
  message.success('上传成功');                               // ← 无论如何都报成功
};
// L177-198：canvas 抓帧本身是真实的（drawImage → toDataURL('image/jpeg') → fetch(blob)）
```

三处失真叠加：图像从未离开浏览器、分析结果是硬编码字符串、用户每次都收到「上传成功」。抓帧技术动作可用，**上传与分析部分不可复用**。SP-3 实施时不得把这条链路接进真实核验，否则「人像核验通过」的结论会建立在一个 blob 都没出过浏览器的链路上。建议与 SP-3 同期改造：`uploadMedia` 真接 `FileApi` 上传端点，`autoAnalyze` 在未实现前显式提示「分析能力未开通」，与 SP-5 里 `recognizeByLocalModel` 的诚实未实现写法一致。

### 0.2 worker 自身声明「从未联调」，这条自陈对 SP-3 是决定性的

`deploy/livekit-worker/README.md:57-59` 原文：`worker.py` 是集成件、非单元 TDD，完整链路依赖真实 LiveKit 房间，`livekit-agents~=0.12` 的逐轨 VAD 事件签名「以安装版本为准」，「本实施会话环境无真实房间，未运行联调」。

也就是说：**连音频链路都未经运行时验证**，而 SP-3 要在其上叠加视频轨。`worker.py:84` 那句 `if track.kind != rtc.TrackKind.KIND_AUDIO: return` 证明代码路径里有视频轨被丢弃的分支，但**没有任何证据表明视频轨真的会到达这个回调**——`connect(auto_subscribe=rtc.AutoSubscribe.ALL_NON_SILENT)`（`worker.py:91`）在该版本下是否投递视频轨、远端未开摄像头时的回调时序、`.on("track_subscribed")` 的入参顺序（`worker.py:99` 用 lambda 三参）全部属未证实。本文因此把 G0 定为「先取证再动工」，见 §8.1。

---

## 1. 目标与范围

### 1.1 本期目标（P1，且 G0–G3 全部通过后方可上线）

1. **G0 取证件先行**：在 `worker.py` 的视频轨丢弃分支加一行结构化观测日志（轨种类、参与方、`track.sid`、是否附帧），行为零改变，用真实双人房间跑一次并把输出留档为本文的实施前置证据。
2. **帧采样**：G0 通过后，按参与方每 `5s`（默认）取一帧，长边下采样到 `640`、JPEG 质量 `0.7`，只在内存中存在，送内网人脸服务后即弃。
3. **可插拔 FaceProvider**：与 `asr_provider.py`、SP-4 的 `ser_provider.py` **三件套同构**，`FACE_PROVIDER` 未配置时 `get_face_provider()` 显式 `raise`，默认不启用。
4. **人像 1:1 到场核验**（3B）：证件照 `id_card_front_url` 仅在核验任务期经 `FileApi` 临时取字节，与会中帧一起送 CompreFace 1:1 verification（采用总纲 D-2 段选定的可商用开源权重 YuNet + SFace）；业务侧只存 similarity、结论与依据摘要，**不建 subject 底库、不持有向量**，产出 `FACE_*` 系列结论写入 SP-5 的核验记录表。
5. **保守判定**：单帧不结论；须连续 `3` 帧、跨时长 `≥ 15s` 全部低于阈值才产「疑似非本人到场」提示，且**绝不自动改变 `party_identity.status`**（与 SP-5「处置由人」一致）。
6. **在场记录**（3A）：检测到人脸与否只写 `ai_meeting_presence` 事实表，**默认不产告警**（§4.1 说明为什么这条看起来"没用"的能力反而是唯一诚实的做法）。
7. 复用 SP-4 的开关快照与降级机制，`video` 的开关、告知确认、审计、SSE 事件全部走 SP-1/SP-2 既有那套，不新开端点或事件名。

### 1.2 非目标（逐条给归属，不留悬空）

| 项 | 归属 | 本文如何交代 |
|---|---|---|
| 活体检测（防照片、防换脸、防屏幕翻拍） | 不做，且列为已知局限 | 用当事人证件照做 1:1，天然无法区分「本人到场」与「有人举着他的证件照对着摄像头」；§4.3 把这条写成结论措辞的硬约束（只能说「疑似不一致」，不能说「不是本人」），§9 要求告知文案原文点出该风险 |
| 1:N 人脸检索、以脸搜人 | 不做，**红线** | 不做检索即不需要可搜索底库，向量存储只按 `party_id` 单条取（§5.2）；§9 列为禁止项并给出可执行的检查（比对入参必须带 `party_id`） |
| 跨会议人脸聚类、会中人物库、再犯识别 | 不做，**红线** | 不建任何按自然人跨房间聚合的表或视图 |
| 说话人验证（声纹 vs 人脸，判断「说的是不是画面里的人」） | 后续 | 与 SP-4 有天然协同，但需要时序对齐与第二套同意；本文不实现，只在 §11 记为后续可立项项 |
| 口型/表情/视线/姿态等行为分析 | 不做 | 上游 §1.2 那句「视频行为分析」里的「行为」本文一项都不做，只做到场一致性；§3.6 说明这一收敛如何避免把 SP-3 做成无法验收的大杂烩 |
| 录像、录屏、帧留存 | 不做 | 全仓无 Egress 部署（事实 9），本文也不引入；帧不落盘、不入数据库、不进日志 |
| 视频轨的音频分离或多路重采样 | 不做 | 音频链路完全不动，`worker.py:84` 的分支只加日志、不改判 |

---

## 2. 读码核实的事实基线（本设计的唯一依据）

| # | 事实 | 出处 |
|---|---|---|
| 1 | `worker.py:84` `if track.kind != rtc.TrackKind.KIND_AUDIO: return` 是视频轨唯一丢弃点；`_handle_track` 由「已在房内」遍历（`worker.py:94-97`）与 `track_subscribed` 事件（`worker.py:99-100`）两处调用 | `deploy/livekit-worker/worker.py:83-100` |
| 2 | `entrypoint` 用 `await ctx.connect(auto_subscribe=rtc.AutoSubscribe.ALL_NON_SILENT)`，视频轨是否随之投递**未证实** | `worker.py:91` |
| 3 | worker 自陈从未联调、API 签名以安装版本为准、本会话无真实房间 | `deploy/livekit-worker/README.md:54-59` |
| 4 | 依赖 `livekit-agents[silero]~=0.12`、`livekit-plugins-silero~=0.7`、`requests`；`Dockerfile` 仅 162B，无 CUDA 基础镜像（即当前 worker 容器为 CPU） | `deploy/livekit-worker/requirements.txt`、`Dockerfile` |
| 5 | worker 与 Java 的既有内部通道：`POST /admin-api/ai/meeting/internal/transcript` ＋ `X-Internal-Token`（`worker.py:39-50`、`MeetingTranscriptInternalController.java:42`、`MeetingTranscriptServiceImpl.java:43`）；SP-4 已在同一路径段新增 `/analyze/switch` | 三处实读 ＋ SP-4 §3.3 |
| 6 | 服务探活既有范式两处：`VoiceGatewayClient.alive()` 用 `GET {base}/v1/pool`，源码注释「137 无 /health」（`service/voice/client/VoiceGatewayClient.java:72-76`）；`MeetingRoomServiceImpl` 向 `${livekit.api-url}` 发短超时 GET，未配置则跳过，注释标为 advisory（`service/meeting/impl/MeetingRoomServiceImpl.java:44,48,91`） | 实读 |
| 7 | LiveKit 为本地单实例 Demo 配置：`server-url: ws://localhost:7880`、`api-url: http://localhost:7880`、`api-key: devkey`、`api-secret: secret`、`token-ttl: 3600`，YAML 注释要求生产走环境变量 | `Demo-module-ai-server/src/main/resources/application.yaml:371-376` |
| 8 | 音频链路中，PCM 在 `END_OF_SPEECH` 已整段在手（`worker.py:65-70`）；SP-4 已把该点作为 SER 挂载点并定义了段长门、并发门、断路器三件套 | `worker.py:65-70` ＋ SP-4 §4.3 |
| 9 | **全仓无 LiveKit Egress 部署**：对 `Demo-ai`、`Demo-deploy`、`Demo-docs` 三仓以词边界搜 `egress`，仅命中 `regression` 一类误匹配；livekit 相关命中只有 server 地址、密钥与 worker README | 跨仓 grep（首轮无边界匹配被 `regression` 污染，已用 `\begress\b` 重查） |
| 10 | `ai_meeting_participant` 全部列：`id`、`room_id`、`identity`、`display_name`、`role`（0 主持人 1 参会人 2 转录 worker）、`join_time`、`leave_time` ＋ 审计与 `tenant_id`；**无任何人像、帧或向量列** | `docs/sql/V3.45__meeting_tables.sql:29-46` |
| 11 | 同文件另有 `ai_meeting_room`（`room_sid` 唯一、`case_id`、`host_user_id`、`status`）、`ai_meeting_transcript`（`speaker_identity`、`seq`）、`ai_meeting_minutes`（`content JSONB`、`status DRAFT/CONFIRMED`） | `V3.45__meeting_tables.sql:7-86` |
| 12 | 当事人身份底库实体 `PartyIdentityDO` 位于 uaa 服务，含 `identityNo`、`realName`、`idCardFrontUrl`、`idCardBackUrl`、`status`、`authType`；`PartyIdentityController.java:33-42` 的分页接口直接返回该 DO（SP-5 §0.1 已登记为明文暴露缺陷） | `Demo-basic/Demo-module-uaa/Demo-module-uaa-server/.../dal/dataobject/party/PartyIdentityDO.java` ＋ `controller/admin/party/PartyIdentityController.java:33-42` |
| 13 | `Demo-module-uaa-api` 现暴露 11 个 `*Api`（`DeptApi`、`PostApi`、`LoginLogApi`、`MediatorApi`、`OrgApi`、`OrganizationApi`、`PermissionApi`、`RoleApi`、`SocialClientApi`、`SocialUserApi`、`AdminUserApi`），**全 uaa 模块 grep `PartyApi` 零命中**；SP-5 §3.3 已设计 `PartyApi.getIdentityForVerify`，其 `PartyIdentityForVerifyRespDTO` **已含 `idCardFrontUrl`** → 本文直接复用，不扩展该 Feign | `Demo-module-uaa-api` 目录列举（计数 11，与 system-api 巧合同为 11，已各自核）＋ SP-5 §3.3 L132-143 |
| 14 | SP-5 已建 `ai_party_verify_record` 与 `ai_party_consent`（`V3.52`），`scope` 注释含 `FACE_COMPARE(SP-3)`，`verdict` 枚举预留 `FACE_MISMATCH` 并注明 SP-3 前恒不出现 | `2026-11-04-party-identity-verification-design.md` §4 L155-166、§7.1 L289 |
| 15 | SP-1/SP-2 把 `video` 钉为不可用三处：§6.1 表格行「`kind=video`（本期未交付）→ `enabled=false`、`available=false`、不写开关行」；§7.1 `COMMENT ON COLUMN ai_meeting_analyze_switch.kind IS '…（SP-3 前不会被置为 true）'`；§8 不变量② | `2026-11-04-meeting-room-ui-design.md` L225、L462、L549 |
| 16 | SP-4 已把开关合法集扩为三值并把告警唯一索引改为 `(transcript_id, kind)` 部分唯一（`V3.55`） | `2026-11-04-acoustic-ser-design.md` §0-S1、§0-S2、§7 |
| 17 | 错误码段位实况：代码已用 `1_040_060_*`、`1_040_061_000-004`、`1_040_062_000-006`；设计已分配 `1_040_061_005-007`（SP-1/2）、`1_040_063_*`（SP-5）、`1_040_064_*`（SP-4）→ **`1_040_065_*` 归本文** | `util/ErrorCodeConstants.java` ＋ 四份 spec 交叉扫描 |
| 18 | 迁移号实况：真实最新 `V3.48`；`V3.49-3.51` SP-1/2、`V3.52-3.54` SP-5、`V3.55` SP-4；全仓无 `V3.56+` → **`V3.56`、`V3.57` 归本文**，`V3.58` 起留给后续 | `docs/sql` 目录列举 ＋ 全仓 `*.sql` 文件名扫描 |
| 19 | 菜单 ID 实况：`9490-9494`、`9495-9498`、`9499-9500`、`9501-9504` 已占；`9505` 起作 `uaa_menu.id` 全仓无占用 → **本文取 `9505-9507`** | 全仓 SQL 扫描（`docs/uaa_menu.sql:724-773` 的 `9510` 等确认为 `sort` 列取值） |
| 20 | pgvector 在本平台**真实存在但不宜承载人脸底库**：向量存储经 Spring AI `PgVectorStore` 构建（`core/factory/AiVectorStoreFactory.java:235-319`），其连接参数来自 `ai_vector_store.properties`（独立 `host`、`port`、`database`，见 L246、L267 的报错文案），`idType` 固定 `TEXT`，表结构与维度由该工厂管理 | 实读 `AiVectorStoreFactory.java` |
| 21 | 前端已有 canvas 抓帧实现（`views/ai/disputehall/components/Demo/MediaCapture.vue:177-198`），但其 `uploadMedia`（L151-170）从未发出请求，且 `autoAnalyze` 伪造结论；同仓 `LocalTile.vue:16-31` 与 `RemoteTile.vue` 的 `<video>` 均仅在 `tile.videoTrack` 存在时渲染元素 | 实读（见 §0.1） |
| 22 | 可复制的内网模型服务部署范式：`docker-compose.yml` ＋ `nginx/default.conf.template`（对外唯一入口 ＋ `X-API-Key`）＋ `app.py` ＋ `Dockerfile` ＋ 离线 `wheels/` ＋ `scripts/{deploy,status,stop,verify}.ps1` ＋ `.env.example`，服务 `GET /health` 返回 `gpu_available` | `Demo-deploy/paddle/`（15 文件目录树） |
| 23 | GPU 可用性证据自相矛盾（与 SP-4 事实 20 同一条）：`paddle/.env` 声称本机 RTX 5070 Ti 并备好 `sm120` 镜像，`paddle/README.md` L6-8 称 VL 因 CUDA 12.8 冲突撤下，`docker-compose.yml` 现仅 CPU 版 OCR，Java 实际调用 `192.168.40.30:8080` | 四处实读 |

---

> # 【整章作废】§3–§13 为 2026-11-04 insightface 方案历史原文，仅作设计对照
>
> **生效口径**：`2026-11-06-face-vision-analysis-effective-spec.md`；本文顶部总纲 A–E、D-2 段；修订方案 §4/§7。
> 以下整段（§3 架构、§4.3/§4.4 判定、§5 底库、§6 端点与错误码、§7 DDL、§8.4 部署、§9.3/§9.4 留存、§10 测试、§11–§13 风险/自检/交付）**全部不得实施、不得引用为契约、不得作为验收依据**，原因见顶部总纲 B 段逐章替换表：
>
> - `ai_face_gallery` / `embedding REAL[]` / `embeddingBase64` / 512 维 / Java 余弦 `FaceSimilarityCalculator` / 余弦占位 `0.45` —— **整表整类作废**，平台不持有向量、不建 subject 底库；
> - `enroll`、`gallery/status`、`gallery/delete`、`/v1/face/embed`、`X-Verify-Token` HMAC、`MULTI_FACE` 409、`/health` 的 `persistence:false` —— **端点与契约作废**；
> - `insightface-svc/{app.py,Dockerfile,requirements.txt,models/buffalo_l}`、`8030/8031`、V1–V6 实测项 —— **部署形态作废**；
> - `V3.56__face_gallery_and_presence.sql` 的建表部分、菜单 `9505/9507`、28 条旧用例、§13 交付清单中的 `face_provider.py` / `FaceGalleryDO` / `Demo-deploy/face/` —— **交付物作废**。
>
> **仍然生效的原则性结论（不受作废影响）**：§1.2 非目标与红线（只做 1:1、禁 1:N、不建跨会议人物库、无活体检测、帧不落盘）、§4.1 在场事实与告警分离、§4.2 只在显式核验任务期且单独同意下比对、§9.1 单独同意 `FACE_COMPARE`、§9.2 告知三点、「`FACE_MISMATCH` 唯一不通过且措辞含疑似/请现场确认」「不改 `party_identity.status`、处置由人」、G0–G3 门禁未过不得置 `MEETING_FACE_POC_PASSED=true`。这些原则已由生效版 §1/§9 逐条承接。
>
> 各易误用章节另加就地作废指针（§4.3、§6.1、§7、§10）；§13 沿用其 2026-11-05 作废指针。

## 3. 架构与数据通路（【作废】历史对照，见上方整章作废 banner）

### 3.1 帧从哪里取：三形态对比与选定

| 形态 | 做法 | 判定 | 理由 |
|---|---|---|---|
| ① worker 订阅视频轨取帧 | 放开 `worker.py:84` 的分支，用 `rtc.VideoStream` 读帧，按参与方抽稀后送人脸服务 | **选定（G0 通过后）** | 采集点唯一，与音频同进程、同一身份来源（`participant.identity`），门控可复用 SP-4 的开关快照；帧只在内存（§9）；不依赖任何参会者浏览器状态 |
| ② 前端 canvas 抓帧上传 | 复用 `MediaCapture.vue` 的手法，各端自己抓自己再上传 | 否 | 三个硬伤：该链路上传部分是假的（§0.1）；每个客户端只能抓自己与页面上已渲染的远端元素（`LocalTile.vue:31` 的 `v-if` 说明无视频轨时元素不存在），画廊隐藏或切到专注视图即取不到；采集由客户端自律，主持人关开关后无法证明某端没在传 |
| ③ LiveKit Egress 出流 | 服务端房间合成出一路视频再抽帧 | 否（本期） | 事实 9：全仓无 Egress 部署；引入它等于多一个基础设施与一路新的留存介质（Egress 产物天然是文件），与 §9 的最小化取向直接冲突 |

代价与前置：形态 ① 依赖 `livekit-agents~=0.12` 是否把视频轨投给 agent，属未证实（事实 2、3），因此 §8.1 的 G0 是本文第一个、也是唯一的实施前置。

### 3.2 端到端链路（含每步失败出口）

```
0 G0 取证（本文唯一改 worker 行为的步骤之前的观察件）
  worker.py 的 _handle_track 在 return 之前 print 一行结构化记录：
    [track-observe] room=<name> identity=<id> kind=<KIND_VIDEO> sid=<sid>
  通过判据：双人真机各开摄像头，观察到 2 个参与方各有 KIND_VIDEO 到达，
           且开关未开启时日志行数与帧处理数均为 0（门控有效性一并验证）

1 开关快照（复用 SP-4 §3.2 步骤 1 的端点，本文只扩一个策略块）
  GET /admin-api/ai/meeting/internal/analyze/switch?roomSid=...
  → { voice, ser, video, serPolicy, facePolicy:{sampleIntervalMs, longEdge, jpegQuality,
      maxConcurrentFrames, minQuality, consecutiveFrames, failThreshold, cooldownSec} }
    - 取不到或畸形 → video=false（fail-closed，与 SP-4 同）

2 每参与方一个 VideoStream；采样器按 facePolicy.sampleIntervalMs 取帧
    - 距上次取样不足一个周期 → 跳过（不排队积压，绝不追帧）
    - 长边 > longEdge → 等比缩小；JPEG 编码 q=jpegQuality
    - 并发门（Semaphore(maxConcurrentFrames)）非阻塞获取失败 → 放弃本帧，faceSkipped++

3 FaceProvider.detect(jpeg) → {has_face, quality, boxes}
    - has_face=false → 记 presence=false（仅事实，不告警，§4.1）
    - quality < minQuality → 记 presence=true 但 faceQualityLow=true，不进入比对
    - 异常 → 断路计数 +1，连续 failThreshold 次 OPEN，冷却 cooldownSec

4 FaceProvider.embed(jpeg) → {dim, embedding}（仅当 video 开关开 且 该房间处于核验任务进行中）
    - 与 SP-4 的关键差别：**不是常态轮询提取生物特征**，而是核验任务存续期内才提向量（§4.2）
      核验任务由主持人显式发起，有明确起止、有同意前置（§9）

5 push 到 Java：POST /admin-api/ai/meeting/internal/face-event   （头 X-Internal-Token）
  body: [{identity, ts, hasFace, quality, faceBoxCount, embeddingBase64|null, embeddingDim, skipped}]
    - HTTP 失败：打印状态码 ＋ 响应体前 200 字符，不阻断音频与字幕（同 worker.py:39-50 的取向）
    - embeddingBase64 仅在核验任务期非空：512 维 float32 约 2KB，采样 5s 一级，不构成带宽压力

6 Java MeetingFaceEventService
    - 密钥校验 → 不符 1_040_064_003 同款处置，本文用 1_040_065_000（§6.3）
    - 守卫：video 开关为 false 或 meeting.face.enabled=false → 整条事件丢弃并 log.warn，不落库
    - presence 写 ai_meeting_presence（事实）
    - 有 embedding → 取 SP-5 底库向量（按 party_id 单条取，不做检索）→ 余弦 → §4 判定
    - 结论写 ai_party_verify_record（SP-5 表，增列）＋ 满足保守条件时产 ai_meeting_alert
```

### 3.3 人脸服务契约（对新容器的要求，不是对既有服务的描述）

严格沿用事实 22 的部署范式与 SP-4 §4.2 的鉴权形态（`X-API-Key` 经 nginx，`/health` 报 `gpu_available`）：

```
GET  {base}/health          → {"status":"ok","gpu_available":<bool>,"model":"<服务自报>",
                              "dim":512,"ready":<bool>,"persistence":false}
POST {base}/v1/face/detect  → multipart file=<jpeg>（无其他参数）
   → {"hasFace":true,"faces":[{"box":[x,y,w,h],"quality":0.71,"detScore":0.83}]}
   → 0 张脸是正常事实不是错误：返回 {"hasFace":false,"faces":[]} 且 HTTP 200（§4.1 要的就是这个）
POST {base}/v1/face/embed   → multipart file=<jpeg> ＋ Form verifyId/identity/expiresAt
                              ＋ 请求头 X-Verify-Token: hmac(verifyId|identity|expiresAt)
   → {"dim":512,"embeddingBase64":"<float32 LE 数组>","model":"<服务自报>","quality":0.71,"box":[x,y,w,h]}
   → 403 任务窗口无效或凭据缺失 / 409 NO_FACE 或 MULTI_FACE / 400 图像非法
```

参数不逐请求下发的理由：`minFacePx`、`maxFaces`、`detSize` 是服务侧质量口径，必须与 §6.5 的 `policy`（Java 单一来源）一致；若允许调用方逐次传，同一个房间的不同调用方可拿到不同质量口径的结论，判定表（§4.3）就失去可比性。参数一律走容器环境变量，由 §8.4.3 的 compose 注入。

三个刻意的设计约束：

1. **`embed` 不接受任意图**：请求必须带 `verifyId`（Java 签发的核验任务号）＋ `X-Verify-Token`（§8.4.6 的 HMAC 任务凭据），服务侧在任务窗口外或验签不符直接 403，防止该服务被当成通用的「照片转特征」工具使用。
2. **多人同框不代平台做决定**：一帧内多脸直接 409 `MULTI_FACE`，不由服务侧猜「提哪张」（猜错即身份错认）；调用方需逐位参与方分轨取帧（§3.2 按参与方建流）。
3. 服务侧不存任何输入图像与特征副本，`/health` 需报告其是否具备持久化（预期 `persistence: false`）。平台侧不接受带存储的第三方人脸实现。

---

## 4. 判定规则

### 4.1 在场事实与在场告警的分离（本文最重要的一条保守决定）

`hasFace=false` **不等于**该参会者离席：Demo会中低头填表、侧身取材料、背对摄像头、镜头被文件遮挡都是正常行为；`quality` 低也可能是光线问题。若把「没检测到脸」做成告警，面板会被无意义的提醒淹没，而主持人对「某人不在场」其实有比模型更好的判断手段——他能直接看见或喊人。

因此本文规定：

| 检测状态 | 落库 | 是否告警 |
|---|---|---|
| `hasFace=true` 且质量达标 | `ai_meeting_presence(face=true)` | 否 |
| `hasFace=true` 但质量不足 | `presence(face=true, low_quality=true)` | 否 |
| `hasFace=false` | `presence(face=false)` | 否 |
| 同一参与方连续 `presence.sampleIntervalMs × 4` 以上全部 `face=false` **且** 其音频轨同期静默 | `presence(face=false, idle_streak=N)` | 仅在该房间已开启「离席提示」子开关（默认关）时产 `info` 一条，文案「画面中暂未检测到本人，可能是遮挡或离开——请主持人确认」 |

最后一行是唯一可能产告警的在场场景，且默认关闭、等级封顶 `info`、措辞包含「可能」两种以上解释。

### 4.2 人像核验只在显式任务期内进行

不存在「后台持续比对所有人的脸」这种运行形态。核验任务的生命周期：

1. 主持人或管理员对**某个特定当事人**发起（§6.1），须已有 `ai_party_consent` 中 scope=`FACE_COMPARE` 的有效同意（复用 SP-5 §8.1 的前置硬门，无同意则拒绝发起、零外呼）。
2. Java 签发 `verifyId`，向 worker 下发该任务的 `(identity, partyId, 截止时刻)`；worker 只对该身份在任务窗口内提取向量。
3. 任务到期、被取消、或连续取满 `maxFramesPerVerify`（默认 `6`）帧即结束，之后不再提取。
4. 结论只写 `ai_party_verify_record`，**不改变 `party_identity.status`**（SP-5 已定「处置由人」，本文继承）。

这条设计同时压制三件事：常态生物特征采集、无同意采集、以及把比对结果自动变成业务状态变更。

### 4.3 人像一致性判定表（`PartyVerifyVerdict` 的 `FACE_*` 扩展，自上而下短路）【整节作废】

> **就地作废指针**：本表 11–18 的 `FACE_NO_BASE` / `FACE_BASE_STALE` / `FACE_UNAVAILABLE`、余弦阈值 `0.45`、极差 `0.25` 均为 insightface 底库方案口径。生效的 6 值判定族与保守窗口见 `2026-11-06-face-vision-analysis-effective-spec.md` §5。

> 序号从 `11` 起是**刻意的**：本表是 SP-5 §4 那张十行判定表（其序 1–10，其 L418 明写「§4 十行判定表」）的续段，两段共用同一个 `PartyVerifyVerdict` 枚举与同一条短路语义，因此序 11 直接接在 SP-5 的序 10 之后，全文合起来是 18 值。看到「本表没有 1–10」不是编号遗漏。

| 序 | 条件 | `verdict` | 中文文案 | 是否计入「不通过」 |
|---|---|---|---|---|
| 11 | 底库无该 `party_id` 的向量（未从证件照生成过） | `FACE_NO_BASE` | 未建立人像底库，无法核验 | 否 |
| 12 | 底库向量存在但源证件照已变更（`idCardFrontUrl` 与建库时不一致） | `FACE_BASE_STALE` | 证件照已更新，需重新建立人像底库 | 否 |
| 13 | 任务窗口内一帧人脸都没有 | `FACE_NO_FRAME` | 会中未采集到有效人脸画面，核验未完成 | 否 |
| 14 | 有效帧数低于 `minFrames`（默认 `2`） | `FACE_INSUFFICIENT` | 有效画面不足，核验未完成 | 否 |
| 15 | 全部帧的最高相似度 `≥ similarity-threshold` | `FACE_MATCHED` | 会中画面与登记人像一致 | 否 |
| 16 | 相似度低于阈值的帧数 `≥ consecutiveFrames`（默认 `3`）且跨时长 `≥ 15s`，同时**存在至少一帧质量达标** | `FACE_MISMATCH` | 会中画面与登记人像**疑似**不一致，请主持人现场确认 | **是** |
| 17 | 帧间相似度离散（最高与最低差 `> 0.25`，说明采样到了不同画面或攻击样本） | `FACE_UNSTABLE` | 采样画面不稳定，无法得出人像结论 | 否 |
| 18 | 人脸服务不可达或返回异常 | `FACE_UNAVAILABLE` | 人像核验服务不可用，核验未完成 | 否 |

三条必须钉死的措辞与实现约束：

- 16 行是唯一「不通过」，且其文案只能是「疑似不一致，请现场确认」；**禁止**出现「不是本人」「冒名」「顶替」等定性表述——本文没有活体检测（§1.2），一张证件照就能骗过这条链路，所以任何定性表述都是在撒谎。
- 17 行的存在是诚实处理：帧间离散时硬判「一致」或「不一致」都错，只能承认测不出。
- 阈值 `similarity-threshold` **不得取模型文档默认值**，必须由 §8.1 的 G2 用本地样本标定 FAR/FRR 后写入配置；默认值 `0.45` 仅作为待标定的占位上界，配置文件注释须写明「G2 标定前不得用于生产判定」。

### 4.4 相似度计算位置

余弦在 **Java 应用层**计算，不在人脸服务侧。理由：底库向量在业务 PG（Java 侧），若把底库送到服务侧比对，就在服务进程里形成了第二份生物特征副本（违反 §9 最小化）；若把会中向量送到服务侧比对则同理。服务只输出「这张脸的特征」，比对与判定全在平台内，可审计、可换模型。

`FaceSimilarityCalculator` 写成纯函数（两个 `float[]` 返回 `BigDecimal`），单测覆盖零向量、维度不等、NaN、长度越界四种畸形输入（一律抛 `1_040_065_001`，不返回 0 分——返回 0 会被读成「明显不是同一人」，而实际是数据坏了）。

---

## 5. 底库与数据通路

### 5.1 底库建立的唯一来源

`ai_face_gallery.embedding` **只能**由 SP-5 的 `PartyApi.getIdentityForVerify` 返回的 `idCardFrontUrl` 经人脸服务提取而来（§6.1 的 `enroll` 端点），不接受任意上传照片建库。这一条把「拿别人照片建底库」的攻击路径关掉，也让底库与证件照之间可追溯（记录证件照路径的摘要 `source_url_hash` 与 `enrolled_at`；**存摘要而非 URL 明文**，理由见 §7 DDL 的列注释——URL 本身含可定位到当事人的对象路径，属于最小化范围）。

建库同样需要同意：`enroll` 前置检查 scope=`FACE_COMPARE` 的有效同意，与核验共用同一道门。

### 5.2 为什么不用 pgvector（事实 20 的取舍）

| 方案 | 判定 | 理由 |
|---|---|---|
| 复用 Spring AI `PgVectorStore` | 否 | 它的连接指向**独立配置的库**（`ai_vector_store.properties` 的 host/port/database），与 `ai_party_verify_record`、`ai_meeting_presence` 所在业务 PG 不同源，无法在同一事务内做租户隔离与同意校验；表结构由框架管理，插入的是「文档」语义，装不下 `party_id`、`consent_id`、`source_url` 这套治理字段；`idType` 固定 `TEXT` 也与本文主键风格不符 |
| 业务 PG 加 `vector(512)` ＋ ivfflat | 备选，本期不取 | 需确认扩展已安装；且本文**不做 1:N 检索**（§1.2 红线），没有相似搜索性能需求，索引是多余的能力面 |
| 业务 PG 用 `REAL[]` ＋ 应用层余弦 | **选定** | 零扩展依赖；按 `party_id` 单条取回，天然不需要检索；规模可控（单租户底库量级为当事人数的千级以内，且只在核验任务期被逐条取用）；删除即物理删（§9.3），不受索引与向量表清理策略牵制 |

### 5.3 与 SP-5 的接缝（逐条对上，不留口头）

| SP-5 已交付项 | 本文用法 |
|---|---|
| `PartyApi.getIdentityForVerify` 与 `PartyIdentityForVerifyRespDTO.idCardFrontUrl`（事实 13） | `enroll` 直接取该字段拿证件照字节，无需扩展 Feign |
| `FileApi.getFileContent(path, code)` 取图片字节（SP-5 §0-P3） | 同一通道，本文不新开文件读取路径 |
| `ai_party_consent`，scope 预留 `FACE_COMPARE(SP-3)`（事实 14） | 本文启用该 scope，`version` 语义与 SP-5 一致 |
| `ai_party_verify_record` 与 `verdict` 预留 `FACE_MISMATCH`（事实 14） | 本文在同一张表增列（`face_similarity`、`face_frames_used`、`face_frames_total`、`face_service_model`），`verdict` 取 §4.3 的 `FACE_*` |
| 「不自动改 `status`，处置走 `/audit`」 | 完整继承，本文任何结论都不触发状态机 |
| SP-5 的明文脱敏改造（其 §8.3） | 本文要求 `enroll` 与 `verify` 的日志同样禁打 URL 全串与图像字节 |

---

## 6. 接口契约

### 6.1 端点【整节作废】

> **就地作废指针**：`enroll` / `gallery/status` / `gallery/delete` / `internal/face-event` 四端点与菜单 9505/9507 已整体废弃；生效端点见 `2026-11-06-face-vision-analysis-effective-spec.md` §4（`POST /ai/meeting/face/verify`、`GET /ai/meeting/face/health`）。

全部置于既有 `controller.admin.meeting`（框架按包名追加 `/admin-api`，映射字面量不含前缀——遵循 SP-1/2 §6.5 与 SP-4 §3.3 的双前缀教训），**不新建 Controller 包**。

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/ai/meeting/face/enroll` | POST | `ai:meeting:face-enroll`（菜单 9505） | 从证件照建立人像底库；body `{partyId:Long@NotNull}`；前置校验 `FACE_COMPARE` 同意，无同意抛 `1_040_063_000`（复用 SP-5 错误码，同一道门不该有第二个码） |
| `/ai/meeting/face/gallery/delete` | POST | `ai:face:gallery-delete`（菜单 9507） | 物理删除向量（§9.3）；body `{partyId}`；写审计 |
| `/ai/meeting/face/gallery/status` | GET | `ai:meeting:query` | 只返回 `{hasGallery:Boolean, enrolledAt, sourceAuthType, model}`，**不返回向量、不返回图片 URL** |
| `/ai/party/verify/idcard`（SP-5 既有） | POST | `ai:party-verify:idcard`；**当 `verifyType=FACE` 时额外要求 `ai:party-verify:face`（菜单 9506）** | 请求体增 `verifyType`（`IDCARD` 默认，或 `FACE`）；`FACE` 时走 §4.2 任务链路，返回 `verifyId` ＋ `status=PENDING`。人像核验单独挂一个权限，是因为它的敏感度高于证件 OCR，必须可单独授权与单独回收——与当事人同意相互独立是同一道理（§9.1） |
| `/ai/party/verify/get`（SP-5 既有） | GET | `ai:party-verify:query` | 无变更，`verdict` 取值集合扩展 §4.3 八项 |
| `/ai/meeting/internal/face-event` | POST | 内部密钥 | worker 回推（§3.2 步骤 5），`FaceEventReqVO` 数组 |
| `/ai/meeting/internal/analyze/switch`（SP-4 既有） | GET | 内部密钥 | 快照增 `facePolicy` 块；`video` 由 `false` 常量改为按 §6.4 探活计算 |

核验入口刻意**扩展 SP-5 的端点**而不是新建 `/ai/meeting/face/verify`：同一次「当事人身份核验」的两条支路（证件 OCR 与人像比对）必须在同一条历史记录里可读，分两个端点会分叉出两套状态、两套错误码、两套前端轮询，而业务上它们是一个动作。

### 6.2 VO 扩展

```
FaceEventReqVO { identity:String, ts:Long, hasFace:Boolean, quality:BigDecimal|null,
                 faceBoxCount:Integer, embeddingBase64:String|null, embeddingDim:Integer|null,
                 verifyId:Long|null, skipped:Boolean }
PartyVerifyRecordVO 增字段：verifyType:String, faceSimilarity:BigDecimal|null,
                 faceFramesUsed:Integer, faceFramesTotal:Integer, faceServiceModel:String|null
MeetingAlertVO 增字段：videoChannel:String   -- presence / identity（§0-T3）
AnalyzeStatusRespVO：video 行 sp="SP-3", phase="P1"，available 见 §6.4
```

**任何 VO 与日志都不得出现**：`embeddingBase64` 回显、证件照 URL 全串、帧图像字节、人脸框坐标以外的原始像素信息。

### 6.3 错误码（`1_040_065_*`，事实 17 确认该段空闲）

```
1_040_065_000  人脸事件内部回推密钥无效
1_040_065_001  人脸特征数据不合规（维度不符 / 零向量 / 含 NaN）
1_040_065_002  人像核验服务不可用: {}
1_040_065_003  人像底库不存在，请先建立底库: {}
1_040_065_004  证件照已更新，人像底库需重新建立
1_040_065_005  人脸检测未得到有效人脸，无法提取特征
1_040_065_006  人像核验任务不存在或已结束: {}
```

### 6.4 `video` 卡片的 `available` 计算（T1 的门禁实现）

`available = meeting.face.enabled AND 探活成功 AND g3Passed`。其中 `g3Passed` 不是一个配置项的默认值，而是**必须由运维显式置位的开关**：`meeting.face.jailed-by-poc: ${MEETING_FACE_POC_PASSED:false}`，默认 `false`。

效果：即使代码与容器全部就位，视频卡片仍显示 `available=false`、reason 为「人像核验服务尚未通过选型标定，暂不可用」，直到 G0–G3 的留档结论被人工确认并把该环境变量置 `true`。这把 T1 的「分期作废」落成一个可关断的开关，而不是一个靠记忆维持的承诺。

**2026-11-05 修订**：采用可商用开源权重（总纲 D-2 段）只解决 G3 的「模型权重授权」子项，**不改变本公式、不改 `jailed-by-poc` 默认值、不减少 G0–G3 任一项留档要求**。`video.available` 仍恒 `false`，`MEETING_FACE_POC_PASSED` 仍保持 `false`。

探活沿用事实 6 的范式：短超时 `GET {base}/health`，结果按 `health-cache-ttl-seconds` 缓存；`MeetingRoomServiceImpl` 的 advisory 探活是同类先例。

### 6.5 配置项

```yaml
meeting:
  face:
    enabled: ${MEETING_FACE_ENABLED:false}          # 默认关；G0-G3 留档齐备前不得开
    base-url: ${MEETING_FACE_BASE_URL:}             # 自定义 core 镜像对外地址（未实测）
    api-key: ${MEETING_FACE_API_KEY:}
    jailed-by-poc: ${MEETING_FACE_POC_PASSED:false} # §6.4；G0-G3 留档齐备后人工置 true，本轮恒 false
    similarity-threshold: ${MEETING_FACE_SIMILARITY_THRESHOLD:} # G2 按 YuNet + SFace 本地标定后回填；标定前为空，禁止用于生产判定（余弦占位 0.45 已作废）
    min-frames: 2
    consecutive-frames: 3
    min-window-seconds: 15
    max-frames-per-verify: 6
    health-cache-ttl-seconds: 30
    policy:                                         # 下发给 worker 的 facePolicy 快照（G0 证实取帧形态后才生效）
      sample-interval-ms: 5000
      long-edge: 640                                # 与 YuNet 输入尺寸对齐；G1 标定后回写
      jpeg-quality: 0.7                            # 同上
      max-concurrent-frames: 2
      det-score-threshold: 0.5                     # YuNet box.score 门槛；替代原 min-quality（SCRFD 口径）
      fail-threshold: 3
      cooldown-seconds: 60
```

**2026-11-05 删除且不得恢复的旧口径**（详见总纲 D-2 段）：`task-secret`（自建 embed 服务的 HMAC 任务凭据）、`embedding-dim: 512`（CompreFace 1:1 架构下平台不持有向量，SFace 为 128 维且不落库）、`gallery-retention-days`（不建 subject 底库）、`similarity-threshold: 0.45`（余弦占位，须按 YuNet + SFace 由 G2 重标定）。`det-score-threshold` 替代原 `min-quality`（SCRFD 口径）。

worker 环境变量（追加到 `deploy/livekit-worker/README.md` 的环境变量表，与事实 5 的既有变量同处登记）：`FACE_PROVIDER`（默认 `none`）、`FACE_GATEWAY_BASE_URL`、`FACE_API_KEY`。帧参数不在 worker 配，走快照下发（与 SP-4 同一条防漂移决定）。

---

## 7. 数据表与迁移（PG 方言，对齐事实 10、11 的 V3.45 风格）【整章作废】

> **就地作废指针（C02 点名的高风险项）**：下方 `CREATE TABLE ai_face_gallery(embedding REAL[], embedding_dim, source_url_hash)`、`uk_ai_face_gallery_party`、`V3.57` 菜单 9505–9507、以及 `embedding-dim:512` 注释**一律不得执行、不得复制进任何迁移**。生效版 SP-3 收敛实现不新增任何表/列（无 `V3.56`/`V3.57`、无 `verify_type`、无 `video_channel`），详见 `2026-11-06-face-vision-analysis-effective-spec.md` §7。若后续经独立评审确需落库，须另起迁移与合规评审，不得复用本段 DDL。

| 文件 | 内容 |
|---|---|
| `V3.56__face_gallery_and_presence.sql` | 两张新表 ＋ `ai_party_verify_record` 增列 ＋ kind 注释修订 |
| `V3.57__face_menu.sql` | 菜单 `9505-9507` ＋ 超管授权（沿用 V3.46 防呆与幂等写法） |

`V3.58` 起留空未用，本文不预留；`ai_meeting_participant` **不加列**（事实 10），因为「某人此刻是否有脸」是随时间变化的事实，属于事件表（presence），不属于身份表；把它塞进 participant 表会导致该行被高频更新，与 `join_time` 这类低频事实混在一起，也让「底库不存在时会不会改错表」变成不必要的问题。

```sql
BEGIN;

-- 1) 人像底库（一人一向量，物理删除，见 §9.3）
CREATE TABLE IF NOT EXISTS ai_face_gallery (
  id                BIGSERIAL    NOT NULL,
  party_id          BIGINT       NOT NULL,
  embedding         REAL[]       NOT NULL,               -- 应用层余弦，不做检索（§5.2）
  embedding_dim     SMALLINT     NOT NULL,               -- 与 meeting.face.embedding-dim 不符即拒（1_040_065_001）
  model             VARCHAR(64)  NOT NULL,               -- 特征来源模型自报标识
  source_url_hash   VARCHAR(64)  NOT NULL,               -- 建库时证件照路径的 SHA-256，用于 BASE_STALE 判定（§4.3-12）
  consent_id        BIGINT       NOT NULL,               -- 建库时依据的同意记录（ai_party_consent.id）
  enrolled_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at      TIMESTAMP,                            -- 超 retention-days 未复用即清理
  creator           VARCHAR(64)  DEFAULT '',
  create_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater           VARCHAR(64)  DEFAULT '',
  update_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id         BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_face_gallery IS '当事人人像特征底库（仅由证件照派生，撤回或超期即物理删除）';
COMMENT ON COLUMN ai_face_gallery.source_url_hash IS '证件照路径摘要，不存 URL 明文，用于检测底库是否已过期';
COMMENT ON COLUMN ai_face_gallery.embedding IS '生物特征向量，明文列存储依赖库级加密与访问控制，禁止出现在任何查询接口返回值';
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_face_gallery_party
  ON ai_face_gallery (tenant_id, party_id) WHERE deleted = FALSE;   -- 一人一底库，杜绝多脸并存
CREATE INDEX IF NOT EXISTS idx_ai_face_gallery_last_used ON ai_face_gallery (last_used_at);

-- 2) 在场事实（只增不查人脸，默认不产告警，§4.1）
CREATE TABLE IF NOT EXISTS ai_meeting_presence (
  id            BIGSERIAL    NOT NULL,
  room_id       BIGINT       NOT NULL,
  participant_identity VARCHAR(128) NOT NULL,
  sampled_at    BIGINT       NOT NULL,                   -- 采样时刻(ms)
  has_face      BOOLEAN      NOT NULL,
  face_quality  NUMERIC(4,3),
  face_box_count SMALLINT    NOT NULL DEFAULT 0,
  low_quality   BOOLEAN      NOT NULL DEFAULT FALSE,
  skipped       BOOLEAN      NOT NULL DEFAULT FALSE,     -- 被并发门或开关丢弃（区分「没脸」与「没采样」）
  creator       VARCHAR(64)  DEFAULT '',
  create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater       VARCHAR(64)  DEFAULT '',
  update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id     BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_meeting_presence.skipped IS 'true 表示本帧未被采样（并发门或降级），不得计入「未检测到人脸」的连续计数';
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_meeting_presence_sample
  ON ai_meeting_presence (room_id, participant_identity, sampled_at) WHERE deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_ai_meeting_presence_room_time ON ai_meeting_presence (room_id, sampled_at);

-- 3) SP-5 核验记录表增列（该表由 V3.52 创建，本文只增列，不重建）
ALTER TABLE ai_party_verify_record ADD COLUMN IF NOT EXISTS verify_type        VARCHAR(16) NOT NULL DEFAULT 'IDCARD';
ALTER TABLE ai_party_verify_record ADD COLUMN IF NOT EXISTS face_similarity     NUMERIC(5,4);
ALTER TABLE ai_party_verify_record ADD COLUMN IF NOT EXISTS face_frames_used    SMALLINT;
ALTER TABLE ai_party_verify_record ADD COLUMN IF NOT EXISTS face_frames_total   SMALLINT;
ALTER TABLE ai_party_verify_record ADD COLUMN IF NOT EXISTS face_service_model   VARCHAR(64);
COMMENT ON COLUMN ai_party_verify_record.verify_type IS 'IDCARD 证件OCR一致性（V3.52 原语义）/ FACE 人像到场比对（SP-3）';
COMMENT ON COLUMN ai_party_verify_record.face_similarity IS '最高余弦相似度；判定阈值由 meeting.face.similarity-threshold 给出，非本表常量';
COMMENT ON COLUMN ai_party_verify_record.verdict IS 'FACE_* 取值族由 SP-3 §4.3 产生；FACE_MISMATCH 为本族唯一不通过值';

-- 4) 开关表 kind 注释同步（原文写「SP-3 前不会被置为 true」）
COMMENT ON COLUMN ai_meeting_analyze_switch.kind
  IS 'voice 文本语义 / ser 声学情感（SP-4）/ video 人像到场（SP-3，G0-G3 门禁通过后方可置 true）';

COMMIT;
-- 回滚：DROP TABLE IF EXISTS ai_meeting_presence, ai_face_gallery;
--       ALTER TABLE ai_party_verify_record DROP COLUMN IF EXISTS verify_type, ...（五列逐一 DROP）;
--       注意：ai_party_verify_record.verify_type 有 DEFAULT，回滚后既有 FACE 行的语义会退化为 IDCARD，
--             回滚前须先 DELETE 掉 verify_type='FACE' 的行并留数据变更单。
```

**执行前置**：`V3.52`（SP-5）与 `V3.49`（SP-1/2）必须已落地——本文要 `ALTER` 的 `ai_party_verify_record` 来自 V3.52，要改注释的 `ai_meeting_analyze_switch` 来自 V3.49。缺任一则 V3.56 报错终止（期望行为，不是缺陷）。实施顺序因此固定为 **SP-1/2 → SP-5 → SP-4 → SP-3**（与 SP-4 §11 的同一结论互相印证）。

Java 侧新增 `FaceGalleryDO`、`MeetingPresenceDO`（继承 `TenantBaseDO`，与事实 10 的既有 DO 一致）；`FaceSimilarityCalculator` 纯函数类；`MeetingFaceEventService`、`FaceGalleryService`、`PartyFaceVerifyService`；`MeetingVerifySwitchCacheService` 扩展快照组装。

---

## 8. 算力、门禁与容量

### 8.1 四道门禁（顺序执行，任一不过则本文停在原地）

| 门禁 | 内容 | 通过判据 | 未过的后果 |
|---|---|---|---|
| **G0 帧可达** | 事实 2、3：视频轨能否到达 worker 完全未证实 | 双人真机各开摄像头，`[track-observe]` 日志出现 2 个参与方的 `KIND_VIDEO`；关闭开关时该日志有、帧处理计数为 0 | **本文 §3 之后全部不实施**；结论若为「agent 收不到视频轨」，则形态 ① 直接否掉，本文须改写为形态 ② ＋ 真实上传（并连带修好 §0.1），这是一次重设计而非调整 |
| **G1 检测可用性** | 人脸检测在真实会中画面（侧脸、低光、遮挡、离屏幕 1–2m）上的可用率 | 采 20 段真实会中帧人工标注，检测召回 ≥ 85%，误报（把非人形图案判为脸）≤ 5% | 停在这一步；`min-quality` 与 `sample-interval` 无标定依据 |
| **G2 阈值标定** | 同人异时（同一人在不同会中、不同光线）与异人（同性别年龄段易混对）样本上的 FAR/FRR | 在真实或经同意的合成对上标定，报告 FAR、FRR 与选定阈值；**FRR 高意味着大量 `FACE_UNSTABLE`/误判不一致，FAR 低才是重点**（放过冒名比误伤本人后果重） | `similarity-threshold` 不得写入生产配置，§6.4 的 `jailed-by-poc` 保持 `false` |
| **G3 许可与合规** | 模型与权重的商用许可、算法备案、告知文案审定 | 许可证留档并经法务确认；告知文案含 §9.2 的三条必答项；命名卷留存/删除流程留档 | **未通过**：2026-11-05 已选定可商用开源权重（总纲 D-2 段），**仅「模型权重授权」子项判为已解决**；其余四项（模型名与版本清单、许可快照与法务确认、卷留存与删除、告知文案审定）仍待办。G3 整体不得写成已通过，`MEETING_FACE_POC_PASSED` 保持 `false`，`video.available` 恒 `false`。原 §8.4.1-L1 的 insightface 权重结论已随换件作废 |

G0 之前只允许提交观察件（一行日志），这是刻意的设计：**用一个几乎零成本的动作先证伪整个方案，再谈建表与容器**。本文其余章节都成立在 G0 为真之上，读者评审时应优先质疑 G0，而不是质疑 §7 的列宽。

### 8.2 分支 A（有 GPU）与分支 B（仅 CPU）

| 维度 | 分支 A：新增内网 GPU | 分支 B：仅复用现有 CPU |
|---|---|---|
| 采样密度 | `sample-interval-ms: 5000`，核验任务期内最多 6 帧 | `sample-interval-ms: 15000`，`max-frames-per-verify: 4` |
| 服务并发 | 2 路并行，检测与特征可同进程 | 1 路串行，检测与特征分两次请求以控制内存峰值 |
| 在场记录 | 常态开启（默认不告警，§4.1） | 常态开启，但 CPU 负载高时自动降频到 30s |
| 适用判断 | G1/G2 达标后长期使用 | 试点、低频核验 |

分支 B 的可行性依据：本文**不做常态轮询比对**（§4.2），单次核验最多 4–6 帧，一场会哪怕十次核验也只是几十次推理，远低于「持续视频分析」的负载。这是把 SP-3 从算力困境里救出来的关键设计——**T1 的保守分期同时是容量策略**。

### 8.3 降级阈值（可判定，与 SP-4 §8.3 同构）

| 触发 | 动作 |
|---|---|
| 断路器 5 分钟内 OPEN ≥ 2 次 | A 切 B |
| B 下仍 OPEN，或帧处理 P95 > 3000ms 持续 5 分钟 | Java 侧 `video.available=false`、快照下发 `video=false`（真断流，不止提示）、审计记一条 `MEETING_FACE_DEGRADED` |
| 恢复：`/health` 连续 3 次成功 ＋ P95 < 1500ms 持续 10 分钟 | 逐级回升 B → A，不跳级 |
| 核验任务期内所有帧都失败 | 该任务结论 `FACE_UNAVAILABLE`（§4.3-18），**不写「一致」也不写「不一致」** |

### 8.4 部署形态（insightface 内网容器，逐文件）—— 【2026-11-05 整章作废，仅作设计对照】

> **作废指针**：本章及 §8.4.1–§8.4.9 全部基于 insightface `buffalo_l` 自建容器、512 维向量底库、HMAC 任务凭据与余弦 `0.45` 阈值，已被「insightface 无商用授权 → 采用 CompreFace」与 2026-11-05「可商用开源权重」两次裁决**整体作废**。生效口径以顶部总纲 A–E、**D-2 段**与 §6.4/§6.5 为准；本章的模型名、端口 `8030/8031`、`X-Verify-Token`、`normed_embedding`、`minQuality`、`MULTI_FACE` 409、V1–V6 实测项**均不得作为实施依据**。
>
> 现行部署形态：`Demo-deploy/compreface/`，官方核心镜像走自定义构建路径换入 **YuNet + SFace 可商用开源权重**。**2026-11-05 部署 PoC 已完成**：插件适配层（`build/core-build/`）、自定义镜像 `compreface-core-yunet-sface:1.2.0`、权重下载与 SHA256 校验、宿主 PostgreSQL 复用、compose 部署与 `verify.ps1` 9/9 契约实测均已落地（实测口径见部署件 README §6/§7）；**仍不接业务链路、不可投产**。门禁状态见 §8.1。

模型选型已确定（用户 2026-11-04 指令）：**insightface `buffalo_l`** 作为检测＋特征提取件，具体构成与约束见下。（本句为作废原文，保留作对照）

#### 8.4.1 两条先决事实（读完再决定要不要开工）

| # | 事实 | 出处 | 对 SP-3 的直接后果 |
|---|---|---|---|
| L1 | insightface 的 **源代码是 MIT**，但预置模型包（含 `buffalo_l`、`antelopev2`）官方明写「**available for non-commercial research purposes only**」 | PyPI `insightface` 项目页 Model Zoo 一节的原文注记 | **G3 现状为未通过**。本项目是商用Demo平台，直接跑 `buffalo_l` 权重即构成违约。官方同时提供了唯一正当路径：「Use Your Own Licensed Model」——在 `~/.insightface/models/<zoo>/` 下用自有或已商用授权的 ONNX 替换，代码与接口不变。本文 §8.4.2 的结构止是按照「**模型可换、服务与平台代码不动**」来写的，因此本条不是设计阻塞，而是**上线阻塞** |
| L2 | 官方给出的 `buffalo_l` 分族准确率（MR-ALL）：**East Asian `74.96`，Caucasian `94.70`**，LFW `99.83` | 同上 Model Zoo Recognition Accuracy 表 | 本项目当事人几乎全为东亚面孔，**能引用的参考值是 `74.96` 而不是 `99.83`**。这两个数相差 20 个百分点，直接决定 G1/G2 的标定必须用**本地样本**，且阈值不得取任何论文默认值；也直接决定 §4.3 为何要把 `FACE_UNSTABLE` 与「只提示不定性」做成硬约束——高 FRR 是本模型族在本场景下的预期行为，不是故障 |

因此本文给出一句必须写在评审首页的话：**SP-3 可以在无 GPU、无商用授权模型两种情况下完成设计与代码实现，但两者缺任一都不得将 `video` 卡片置为 `available=true`。** 这正是 §8.4.9 与 §6.4 `jailed-by-poc` 存有的理由。

#### 8.4.2 目录与端口

```
Demo-deploy/face/
  docker-compose.yml
  .env.example          .env（deploy.ps1 首次自动生成）
  insightface-svc/      app.py  Dockerfile  requirements.txt
                        models/buffalo_l/      五个 .onnx（或由运维换成已授权模型）
  nginx/default.conf.template
  scripts/              deploy.ps1  status.ps1  verify.ps1  stop.ps1
  README.md
```

| 服务 | 监听 | 默认端口 | 说明 |
|---|---|---|---|
| insightface-svc | 容器 8000，宿主 `127.0.0.1:${FACE_PORT}` | `8031` | 只绑回环；与 SER 的 `8021`、OCR 的 `8011` 不冲 |
| face-nginx | 容器 80，宿主 `0.0.0.0:${FACE_NGINX_PORT}` | `8030` | 唯一对外入口，`X-API-Key` 鉴权 |

#### 8.4.3 `docker-compose.yml`

```yaml
# insightface 人脸检测＋特征服务：推理容器（默认 CPU）＋ Nginx 反代鉴权
#
# 端口约定与 paddle/ser 两套同一取向：推理容器只监听 127.0.0.1，Nginx 是唯一对外入口。
# 对外路径（均需 X-API-Key）：/face/health , /face/v1/face/detect , /face/v1/face/embed
#
# 特别提醒：本 compose **不挂载任何模型或图像卷**。模型走镜像内置（构建期 COPY），
# 图像不落盘（§9）——不挂 volume 就是这一条在部署层的保证手段。

services:
  insightface-svc:
    build:
      context: ./insightface-svc
      dockerfile: Dockerfile
    image: ${FACE_IMAGE:-insightface-svc:1.0}
    container_name: insightface-svc
    restart: unless-stopped
    ports:
      - "127.0.0.1:${FACE_PORT:-8031}:8000"
    environment:
      FACE_MODEL_ZOO: ${FACE_MODEL_ZOO:-buffalo_l}
      FACE_DEVICE: ${FACE_DEVICE:-cpu}          # cpu 或 cuda，分支 A 才改
      FACE_DET_SIZE: ${FACE_DET_SIZE:-640}
      FACE_MIN_DET_SCORE: ${FACE_MIN_DET_SCORE:-0.5}
      FACE_MIN_FACE_PX: ${FACE_MIN_FACE_PX:-40}
      FACE_MAX_FACES: ${FACE_MAX_FACES:-5}
      FACE_TASK_SECRET: ${FACE_TASK_SECRET:?与 Java 侧 meeting.face.task-secret 完全一致}
      FACE_MAX_INFLIGHT: ${FACE_MAX_INFLIGHT:-1}
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://127.0.0.1:8000/health || exit 1"]
      interval: 30s
      timeout: 5s
      start_period: 60s
      retries: 3
    deploy:
      resources:
        limits:
          memory: ${FACE_MEM_LIMIT:-4g}

  face-nginx:
    image: ${NGINX_IMAGE:-docker.m.daocloud.io/library/nginx:1.27-alpine}
    container_name: face-nginx
    restart: unless-stopped
    depends_on:
      - insightface-svc
    ports:
      - "${FACE_NGINX_PORT:-8030}:80"
    environment:
      API_KEY: ${API_KEY:?请先在 .env 中设置 API_KEY}
      FACE_UPSTREAM: http://insightface-svc:8000
    volumes:
      - ./nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/face-nginx-health >/dev/null || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
```

#### 8.4.4 `insightface-svc/Dockerfile`

模型预热与 paddle 不同：paddle 靠运行库自动下载，而 insightface 的 `buffalo_l` 从 GitHub Release 拉 zip，内网基本不可达——所以本文直接把模型目录当构建上下文的一部分 COPY 进去。

```dockerfile
# insightface 人脸服务镜像 —— 默认 CPU（onnxruntime），可切 GPU（分支 A）
# 构建上下文：Demo-deploy/face/insightface-svc
#
# 模型来源：models/<zoo>/*.onnx 作为构建上下文的一部分 COPY 进镜像，运行期零联网。
#   目录内容须为 §8.4.1-L1 所说的「已商用授权或自有训练」的 ONNX；
#   名字叫 buffalo_l 也可以，但授权责任归放置该目录的人，不归本文。

FROM docker.m.daocloud.io/library/python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=https://pypi.org/simple \
    PIP_EXTRA_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST="pypi.tuna.tsinghua.edu.cn pypi.org" \
    PYTHONUNBUFFERED=1

# insightface 含 Cython 扩展，没有 gcc 与 python 头文件时 pip 编译会失败（非可选依赖）
RUN sed -i 's#deb.debian.org#mirrors.tuna.tsinghua.edu.cn#g' \
        /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ make python3-dev \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 1) onnxruntime：默认 CPU；分支 A 改装 onnxruntime-gpu（注意与 SER 共用 torch 时的
#    CUDA 冲突教训，见 Demo-deploy/paddle/README.md 第八章）
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 2) 模型入镜像（不走 ~/.insightface 自动下载）
COPY models /opt/models

# 3) 构建期预热：加载失败必须在此处暴露，而不是上线当天
RUN python -c "from insightface.app import FaceAnalysis; \\\napp = FaceAnalysis(name='buffalo_l', root='/opt/models', \\\nallowed_modules=['detection','identification']); \\\napp.prepare(ctx_id=-1, det_size=(640,640)); \\\nprint('[build] face models loaded ok')"

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 8.4.5 `insightface-svc/requirements.txt`

```
# 人脸服务依赖（版本写死保证可复现）
# 前四个版本与 paddle/pp-ocrv6/requirements.txt 逐字一致，同一目的：共用 pip 缓存层
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.20
numpy==1.26.4
insightface==0.2.1
onnxruntime==1.19.2
opencv-python-headless==4.10.0.84
pillow==11.0.0
```

分支 A（有 GPU）只需把 `onnxruntime` 换为 `onnxruntime-gpu` 并重建镜像，应用层零代码变更（`ctx_id` 由 `-1` 改 `0`，走环境变量）。

#### 8.4.6 `insightface-svc/app.py`

三个不写在代码里就能被绕过的设计约束，都在本件里钉住：**① `embed` 必须带任务凭据**（§3.3 约束 1，防止本服务被当成通用「照片转特征」工具）；**② 不返回未归一化向量**（`w600k_r50` 输出的 `.embedding` 是未归一化的，直接用会让余弦失去意义，必须用 `.normed_embedding`）；**③ 图像与向量都不落盘**。

```python
"""insightface 人脸检测＋特征服务（§3.3 契约的实现件）。

端点
----
GET  /health                  -> {"status":"ok","gpu_available":<bool>,"model":<zoo>,
                                  "dim":512,"ready":<bool>,"persistence":false}
POST /v1/face/detect (multipart file=<jpeg>)
   -> {"hasFace":true,"faces":[{"box":[x,y,w,h],"quality":0.71,"detScore":0.83}]}
   -> 0 张脸不是错误：返回 {"hasFace":false,"faces":[]}（§4.1 要的就是这个事实）
POST /v1/face/embed  (multipart file=<jpeg>, Form verifyId/identity/expiresAt,
                      头 X-Verify-Token: hmac(verifyId|identity|expiresAt))
   -> {"dim":512,"embeddingBase64":"<float32 LE>","model":<zoo>,"quality":0.71,"box":[...]}
   -> 非 2xx：400 图像非法 / 403 任务窗口无效 / 409 NO_FACE 或 MULTI_FACE
             / 429 并发满 / 500 推理失败

为什么 embed 不接图就算完：人脸特征提取工具一旦被开放调用，就是可搜底库的制造机。
Java 签发的任务凭据（与 §4.2 的 verifyId 同源）把可用窗口限定在「已发起且未过期的核验任务」
内，超窗口或签名不符直接 403，服务侧不保留任何任务状态（既不能查库也不联网验凭据，仅验签与验期）。
"""
import asyncio, base64, hashlib, hmac, os, threading, time
from io import BytesIO

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

app = FastAPI(title="insightface Face Service", version="1.0.0")

ZOO = os.environ.get("FACE_MODEL_ZOO", "buffalo_l")
MODEL_ROOT = os.environ.get("FACE_MODEL_ROOT", "/opt/models")
DEVICE = os.environ.get("FACE_DEVICE", "cpu")
DET_SIZE = int(os.environ.get("FACE_DET_SIZE", "640"))
MIN_DET = float(os.environ.get("FACE_MIN_DET_SCORE", "0.5"))
MIN_PX = int(os.environ.get("FACE_MIN_FACE_PX", "40"))
MAX_FACES = int(os.environ.get("FACE_MAX_FACES", "5"))
EMBED_DIM = 512
TASK_SECRET = os.environ.get("FACE_TASK_SECRET", "").encode()
INFLIGHT = int(os.environ.get("FACE_MAX_INFLIGHT", "1"))

_lock, _sem = threading.Lock(), threading.Semaphore(INFLIGHT)
_app = None


def get_app():
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                from insightface.app import FaceAnalysis
                # 只加载检测与识别；对齐/性别年龄属多余能力面，按最小化不开
                fa = FaceAnalysis(name=ZOO, root=MODEL_ROOT,
                                  allowed_modules=["detection", "identification"])
                fa.prepare(ctx_id=(-1 if DEVICE == "cpu" else 0),
                           det_size=(DET_SIZE, DET_SIZE))
                _app = fa
    return _app


def _bgr(data: bytes):
    if not data:
        raise HTTPException(status_code=400, detail="empty image")
    try:
        import cv2
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}")
    if img is None:
        raise HTTPException(status_code=400, detail="undecodable image")
    return img


def _task_ok(verify_id: str, identity: str, expires_at: int, token: str | None) -> bool:
    """HMAC 验任务窗口：不查库、不联网，仅验签与验期。"""
    if not TASK_SECRET or not token:
        return False
    msg = f"{verify_id}|{identity}|{expires_at}".encode()
    want = hmac.new(TASK_SECRET, msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, token.strip()):
        return False
    return int(time.time()) <= int(expires_at)


def _detect(data: bytes) -> dict:
    faces = get_app().get(_bgr(data))
    out = []
    for f in list(faces)[:MAX_FACES]:
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        w, h = x2 - x1, y2 - y1
        score = float(f.det_score)
        # 质量 = 检测分，但脸太小直接归零：低分辨率下特征向量不可信（§4.3-14）
        quality = 0.0 if min(w, h) < MIN_PX else round(score, 4)
        out.append({"box": [x1, y1, w, h], "quality": quality, "detScore": round(score, 4)})
    return {"hasFace": bool(out), "faces": out}


def _embed(data: bytes, verify_id: str, identity: str,
           expires_at: int, token: str | None) -> dict:
    if not _task_ok(verify_id, identity, expires_at, token):
        raise HTTPException(status_code=403, detail="verify window invalid or expired")
    if not _sem.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="face busy, retry later")
    try:
        t0 = time.monotonic()
        faces = get_app().get(_bgr(data))
        if not faces:
            raise HTTPException(status_code=409, detail="NO_FACE")
        if len(faces) > 1:
            # 多人同框时“提哪张”必须由调用方指定，否则服务侧在替平台做身份决定
            raise HTTPException(status_code=409, detail="MULTI_FACE")
        f = faces[0]
        vec = np.asarray(f.normed_embedding, dtype=np.float32)   # L2 已归一化
        if vec.shape[0] != EMBED_DIM:
            # 模型换了维度却未同步配置，宁断不猜（§6.5 embedding-dim）
            raise HTTPException(status_code=502,
                                detail=f"embedding dim {vec.shape[0]} != {EMBED_DIM}")
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        return {
            "dim": EMBED_DIM,
            "embeddingBase64": base64.b64encode(vec.tobytes()).decode(),
            "model": f"{ZOO}/{getattr(f, 'provider', DEVICE)}",
            "quality": round(float(f.det_score), 4),
            "box": [x1, y1, x2 - x1, y2 - y1],
            "latencyMs": int((time.monotonic() - t0) * 1000),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"face failed: {exc}")
    finally:
        _sem.release()


@app.get("/health")
def health():
    import onnxruntime as ort
    return {"status": "ok",
            "gpu_available": any(p.startswith("CUDA") for p in ort.get_available_providers()),
            "device": DEVICE, "model": ZOO, "dim": EMBED_DIM,
            "ready": _app is not None, "persistence": False}


@app.post("/v1/face/detect")
async def detect(file: UploadFile = File(...)):
    return await asyncio.to_thread(_detect, await file.read())


@app.post("/v1/face/embed")
async def embed(file: UploadFile = File(...), verify_id: str = Form(..., alias="verifyId"),
                identity: str = Form(...), expires_at: int = Form(..., alias="expiresAt"),
                x_verify_token: str | None = Header(None, alias="X-Verify-Token")):
    return await asyncio.to_thread(_embed, await file.read(),
                                   verify_id, identity, expires_at, x_verify_token)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

与 Java 侧的配套义务（属 §6 契约的一部分，不写清就会在这里漏掉）：Java 签发 `verifyId` 时必须同时算出 `X-Verify-Token = HMAC_SHA256(meeting.face.task-secret, "verifyId|identity|expiresAt")` 下发给 worker，worker 原样透传。**密钥不得进镜像或仓库**，与 §6.5 的 `api-key` 同一处理。

#### 8.4.7 `nginx/default.conf.template` 与 `.env.example`

```nginx
# 人脸服务 Nginx 反代 + API Key 鉴权（结构照抄 paddle/nginx/default.conf.template）
# 仅 ${VAR} 被 envsubst，$host 等 nginx 变量原样保留。

server {
    listen 80;
    server_name _;
    default_type application/json;

    client_max_body_size 4m;          # 640px JPEG 帧远小于此，上限故意收紧
    proxy_connect_timeout 10s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_buffering off;

    location = /face-nginx-health {
        return 200 '{"status":"ok","service":"face-nginx"}';
    }

    # 外部 /face/... -> 容器 /...
    location /face/ {
        if ($http_x_api_key != "${API_KEY}") {
            return 401 '{"error":"unauthorized","message":"missing or invalid X-API-Key"}';
        }
        proxy_pass ${FACE_UPSTREAM}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        return 404 '{"error":"not found","routes":["/face/health","/face/v1/face/detect","/face/v1/face/embed"]}';
    }
}
```

```bash
# ===== 复制为 .env 后再启动：Copy-Item .env.example .env =====

# ---------- 对外鉴权 ----------
API_KEY=change-me-please-use-a-long-random-string

# ---------- 任务凭据密钥（与 Java 侧 meeting.face.task-secret 完全一致） ----------
# 没有这一项时 embed 必须整体不可用（app.py 里 TASK_SECRET 为空即 403），默认故意不给
FACE_TASK_SECRET=

# ---------- 端口（推理容器只绑 127.0.0.1） ----------
FACE_NGINX_PORT=8030
FACE_PORT=8031

# ---------- 模型与算力 ----------
# 上游为 GitHub 路径时不可替换：本目录的 models/ 必须已按 §8.4.1-L1 完成授权核实
FACE_MODEL_ZOO=buffalo_l
FACE_DEVICE=cpu            # cpu = 分支 B（默认）；cuda = 分支 A，需先过 §8.2 的延迟实测
FACE_DET_SIZE=640
FACE_MIN_DET_SCORE=0.5     # 与 insightface 默认一致；G1 标定后按本地实测值改
FACE_MIN_FACE_PX=40
FACE_MAX_FACES=5
FACE_MAX_INFLIGHT=1        # 分支 B 串行；分支 A 可提到 2
FACE_MEM_LIMIT=4g

# ---------- 镜像 ----------
FACE_IMAGE=insightface-svc:1.0
NGINX_IMAGE=docker.m.daocloud.io/library/nginx:1.27-alpine
```

四个 ps1 与 SER 的三个原样同构（同样的 `$ErrorActionPreference='Continue'`＋`$LASTEXITCODE` 显式检查、同样的随机 40 位 `API_KEY` 生成、同样的 `curl.exe -F` 而非 `Invoke-RestMethod -Form`）。`verify.ps1` 的四段式必验项：

1. `/face-nginx-health` 存活；
2. 无 `X-API-Key` 打 `/face/v1/face/detect` 应 401；
3. **不带 `X-Verify-Token` 直接打 `/face/v1/face/embed` 应 403**——这条是 §3.3 约束 1 的唯一可执行证明，缺它则整个「不当通用特征工具」的设计只是口头声明；
4. 用 `samples/` 下一张正面照走 detect → 断 `hasFace=true`；再走一次带正确凭据的 embed → 断 `dim=512` 且 `embeddingBase64` 解码后长 2048 字节。

#### 8.4.8 worker 如何访问本服务（一个仓库里无法完全定论的问题）

worker 容器在 LiveKit 那个网络上（`deploy/livekit-worker/README.md:49` 的 `docker run --network <livekit-net>`，注意这是占位写法，仓内无 compose 文件固定网络名），而本服务在 `face-nginx` 上。三种取法：

| 方案 | 做法 | 判定 |
|---|---|---|
| 走宿主 LAN IP | worker 配 `FACE_GATEWAY_BASE_URL=http://<face-宿主内网地址>:8030` | **选定**：与现状一致（Java 就是这么调 OCR 的，事实 20 里的 `192.168.40.30:8080/ocr/v6/ocr`）；不需改两边的 compose |
| worker 多挂一个网络 | `docker run` 时连两个 `--network` | 备选；依赖运维对 LiveKit 网络的控制权，且会改变 worker 现有的部署写法 |
| 人脸服务加入 livekit 网络 | compose 里写 `external: true` 的网络 | 否：把业务推理服务挂进信令网络，blast radius 变大，且网络名仍是外物 |

本表不包业务假设：具体地址进 `FACE_GATEWAY_BASE_URL`，与 SER 同一个环境变量族，不由代码拼接。

#### 8.4.9 未实测项与上线后置门禁

与 paddle 不同，`face/` 是一套**尚不存在**的部署，因此本文不写「故障排查（已踩过的坑）」那一章——那是实测产物。以下必须实测并回写 `Demo-deploy/face/README.md`：

| # | 待实测项 | 为何不能先猜 |
|---|---|---|
| V1 | `insightface==0.2.1` 与 `onnxruntime==1.19.2` 的组合能否在 py3.10-slim 内编译通过（Cython 扩展） | 版本号是设计值，仓内无这两个包的任何记录；编不过就得换版本或走预编轮子 |
| V2 | `FaceAnalysis(root=...)` 指向 `/opt/models` 能否真的不走 `~/.insightface` | 若仍走家目录，则镜像预热失效，内网首次调用会去 GitHub 拉包并挂掉 |
| V3 | `normed_embedding` 在当前版 `Face` 对象上是否存在（旧版叫法不一） | §8.4.6 注释里的未归一化风险取决于此；若不存在则服务侧手动 L2，但必须留测试 |
| V4 | 一帧 640px 在分支 B 下的 P50/P95（检测＋识别两次推理） | §8.3 的 `3000 ms` 与 §8.2 的采样间隔都是设计值 |
| V5 | 中文东亚面孔上的本地 FAR/FRR（§8.4.1-L2 要求的那项） | 官方分族值已经提示这里会差，但具体差多少只能本地测 |
| V6 | `buffalo_l` 的商用替代件（自训或已授权 ONNX）放入 `models/` 后接口行为一致 | §8.4.1-L1 的唯一正当路径就建在本服务代码不依赖模型名这一点上，必须实测坐实 |



---

## 9. 合规与安全（生物识别，全文最严的一章）

### 9.1 分类与同意

人脸特征属《个人信息保护法》第 28 条的生物识别信息。本文要求：处理前须有 `ai_party_consent` 中 scope=`FACE_COMPARE` 的有效同意（独立于 SP-5 证件 OCR 的 `IDCARD_VERIFY` 同意，**两项同意不互相覆盖**，因为处理目的不同）；同意必须是核验与建库的前置硬门，无同意时零外呼（复用 SP-5 §8.1 的机制与错误码 `1_040_063_000`）。

### 9.2 告知文案必须点名的三件事（缺一项即为误导）

1. 采集的是会中摄像头画面中的人脸特征，不是录像，不保存图像；
2. 该比对**不含活体检测**，因此「一致」仅代表画面像本人，不代表本人亲自在场；「不一致」仅代表疑似，须现场确认；
3. 核验结果不会自动改变其实名认证状态，任何处置都有经办人与审计记录。

第 2 条最容易被省略，也最不能省略：没有活体检测的「人脸一致」在业务上接近无价值（一张照片即可骗过），若告知文案写成「系统已确认本人到场」，平台就是在为一个虚假保证背书。

### 9.3 留存与删除（本文与 SP-5 的一处有意分歧）

| 数据 | 处置 | 与 SP-5 的分歧说明 |
|---|---|---|
| `ai_party_consent` 同意留痕 | 撤回只置 `revoked_at`，不物理删除（SP-5 原设计） | 无分歧 |
| `ai_face_gallery.embedding` | **物理删除**：同意撤回、当事人注销、或 `last_used_at` 超 `gallery-retention-days`（默认 365）时 `DELETE`；只保留一条删除事实（时间、操作人、原因），不留向量 | **有意分歧**：留痕要求「可举证曾取得同意」，生物特征要求「撤回后不留副本」，两者方向相反。把向量行软删除会留下一个 `deleted=true` 但 `embedding` 仍在表里的副本，这在撤回场景下是不可接受的 |
| `ai_meeting_presence` | 随 `ai_meeting_transcript` 既有清理策略；本文不擅自定他表留存期（与 SP-4 §9 同一取向） | 无分歧 |
| `ai_party_verify_record` 的 FACE 行 | 随 SP-5 留存策略（其 §8.2 的 `party.verify.retention-days`） | 无分歧 |

删除操作必须可在实现里被断言：`FaceGalleryService.deleteByParty(partyId, reason)` 走 `DELETE`，测试用「删后 `SELECT count(*)` 含未删除视图仍为 0」验证，而不是验证 `deleted=true`。

### 9.4 禁止清单（写成可检查的形式）

| 禁止 | 检查手段 |
|---|---|
| 1:N 检索 | 不存在「取回多条向量再排序」的代码路径；`FaceGalleryMapper` 只提供 `selectByPartyId`，单测断言其是唯一查询方法 |
| 跨会议人脸聚合 | 不建按 `party_id` 跨 `room_id` 聚合的物化视图或定时任务；上线前做一次代码扫描（grep `group by` 与人脸表的组合） |
| 任意照片建库 | `enroll` 只接受 `partyId` 且内部走 `PartyApi`，无文件上传参数（§6.1）——从接口签名上就关死这条路 |
| 帧或图像落盘、入日志 | 与 SP-4 §10.4 步骤 7 同款容器内文件核查；日志负向测试断言不含 base64 长串（正则 `[A-Za-z0-9+/=]{200,}` 命中即失败） |
| 定性表述 | §4.3 文案表是唯一来源，前端不得拼接；`AlertLevel` 与 `PartyVerifyVerdict` 枚举的中文文案做一次 grep 核查，出现「确认不是本人」「冒名」「顶替」即测试失败 |

---

## 10. 测试与验收【整章作废】

> **就地作废指针（C02 点名的高风险项）**：`FaceSimilarityCalculatorTest`、`FaceGalleryServiceTest`、28 条旧编号用例、18 值 verdict 映射、`enroll`/`gallery` 冒烟步骤、`embed` 403 断言全部作废。生效测试基线见 `2026-11-06-face-vision-analysis-effective-spec.md` §8（`FaceContractTest` 9 例、`faceVerifyCard.spec.ts` 8 例、`CompreFaceClientRemoteContractTest` 3/3、真实浏览器 E2E）。

### 10.1 后端单测（JUnit5 ＋ Mockito）

| 测试类 | 必录用例 |
|---|---|
| `FaceSimilarityCalculatorTest` | ①同向量得 1.0；②正交向量得 0；③零向量、④维度不等、⑤含 NaN、⑥数组长度超 `embedding-dim` 四种输入均抛 `1_040_065_001`（断言不返回 0） |
| `PartyFaceVerifyServiceTest` | ⑦底库缺失 → `FACE_NO_BASE`；⑧证件照 URL 变更（hash 不符）→ `FACE_BASE_STALE`；⑨窗口内无有效帧 → `FACE_NO_FRAME`；⑩有效帧 1 张（`< min-frames`）→ `FACE_INSUFFICIENT`；⑪**底库存在且 4 帧均达标、极差 ≤ 0.25 → `FACE_MATCHED`，`face_similarity` 取最高帧值、`face_frames_used = 4`**（唯一正面结论，缺此例则短路顺序写错也不会报警）；⑫**只有 2 帧低于阈值 → 不产 `FACE_MISMATCH`**（`consecutiveFrames=3` 未满足）；⑬3 帧低且跨 20s → `FACE_MISMATCH`；⑭3 帧低但跨 10s（不足 15s）→ 不产不通过；⑮帧间极差 > 0.25 → `FACE_UNSTABLE`；⑯服务不可达 → `FACE_UNAVAILABLE` 且**零 `FACE_MATCHED`**；⑰无 `FACE_COMPARE` 同意 → 抛 `1_040_063_000` 且零外呼（`verify(faceClient, never())`）；⑱任何结论都不调 `partyIdentityService` 的状态变更方法 |
| `FaceGalleryServiceTest` | ⑲撤回同意后 `embedding` 行数为 0（物理删，断言不是 `deleted=true`）；⑳`source_url_hash` 与证件照一致才允许复用；㉑一人一底库：二次 `enroll` 覆盖而非新增行（`uk_ai_face_gallery_party`） |
| `MeetingFaceEventGuardTest` | ㉒开关关闭或 `enabled=false` → 事件整条丢弃、零落库、`log.warn` 一次；㉓`skipped=true` 的行不计入「未检测到人脸」连续计数（§4.1 注释所承诺的行为）；㉔密钥不符 → `1_040_065_000` |
| `MeetingFaceAvailabilityTest` | ㉕探活失败 → `video.available=false`；㉖探活成功但 `jailed-by-poc=false` → `available=false` 且 reason 含「选型标定」（**门禁优先于可用性**，这是 T1 的实现钉子）；㉗两者都真 → `available=true` |
| `FaceEventMappingTest` | ㉘`@SpringBootTest` 断言 `/admin-api/ai/meeting/internal/face-event` 命中 handler，且 handler 路径集合中不存在任何 `admin-api/admin-api` 前缀 |

编号说明：本文用例从 ① 起连续编到 ㉘，与 §4.3 的判定表序号（11–18，延续 SP-5）是**两套独立编号**，不得互推。SP-4 的用例编到 ⑫ 为止，本文不接其号。

### 10.2 worker 侧（pytest 纯函数 ＋ 一个集成观测件）

| 用例 | 断言 |
|---|---|
| `get_face_provider()` | `FACE_PROVIDER` 未设或为 `none` → `ValueError`（默认不启用，与音频侧同范式） |
| 采样器 | 两次采样间隔不足 `sampleIntervalMs` 时第二次被丢弃且不排队（断言队列长度恒 ≤ 1） |
| 并发门 | 信号量满时返回 `skipped=true`，绝不等位 |
| 断路器 | 连续 `failThreshold` 次失败 OPEN，冷却内零请求 |
| 快照解析 | `facePolicy` 缺字段或类型错 → 视为 `video=false`（fail-closed） |
| 下采样 | 800×600 帧按 `long-edge=640` 得 640×480，且不超过该尺寸 |
| 任务窗口 | `verifyId=null` 时只调 `detect` 不调 `embed`（生物特征只在任务期提取，§4.2） |
| 三 provider 同构 | 断言 `asr_provider`、`ser_provider`、`face_provider` 的「未知名字即 raise」分支行为一致（参数化跑同一组输入） |

### 10.3 前端 vitest

| 用例 | 断言 |
|---|---|
| `analyze.spec.ts` 扩展 | `video` 卡 `available=false` 时 `disabled` ＋ 显示 `reason`；`available=true` 时切换仍须 `noticeConfirmed`（复用 SP-1/2 的告知条逻辑，不得因新能力而绕过旧门） |
| `alertCard.spec.ts` 扩展 | `videoChannel='identity'` 的卡片文案含「疑似」且不含「确认不是本人」；`presence` 通道卡片默认不出现（因 §4.1 不产告警） |
| `faceGallery.spec.ts` | `gallery/status` 返回 `hasGallery=false` 时显示「建立底库」入口且提示需当事人同意；任何响应体里无 `embedding` 字段 |
| `partyVerify.spec.ts` 扩展 | SP-5 原定「`verdict → 展示态` 映射覆盖全部 10 个取值」（其 §10 L434），本文增 8 值后须覆盖 **18 个**；其中仅 `FACE_MISMATCH` 渲染为不通过（红），其余 7 个 `FACE_*` 不得出现红色样式；新增取值落入 unknown 分支时测试失败（而不是默认渲染成通过） |

### 10.4 端到端冒烟（内网，需人脸服务可达 ＋ 双人真机）

```powershell
# 1) G0：双人入会各开摄像头，抓 worker 日志
#    期望出现 2 条 [track-observe] ... kind=KIND_VIDEO；随后关掉 video 开关再入会，
#    期望观察日志仍在、但帧处理与人脸服务访问日志均为 0
# 2) G1 采样件：把 20 段真实会中帧（从双人录制里抽）逐张打 /v1/face/detect
#    人工标注后算召回与误报，结果存 Demo-docs 作为 G1 留档
# 3) enroll：对已有 FACE_COMPARE 同意的当事人建库 → gallery/status.hasGallery=true
#    无同意时 → {"code":1040063000,...}，且人脸服务侧访问日志 0 条
# 4) 本人发起核验（verifyType=FACE）→ verdict=FACE_MATCHED，face_similarity 有值
# 5) 换人对着摄像头坐满 20s 再核验 → verdict=FACE_MISMATCH，
#    且 party_identity.status 核验前后逐字段相同（SQL 快照对比）
# 6) 用同一张证件照打印出来举到摄像头前（攻击样本）→ 期望得到 FACE_MATCHED 或 FACE_UNSTABLE，
#    并**必须**在告知文案与 UI 上已声明无活体检测；此用例用于让所有人亲眼看到该风险的真实性，
#    不是用来证明能力，而是用来限定结论措辞
# 7) 停掉人脸服务 → 60s 内 available=false，进行中的核验任务落 FACE_UNAVAILABLE
# 8) 隐私核查：跑完 3-7 后，worker 与人脸容器内 find 最近 10 分钟内 >50KB 的文件
#    → 不得出现 jpg/jpeg/png/wav/bin；Java 日志 grep '[A-Za-z0-9+/=]{200,}' → 0 命中
# 9) 双前缀回归：/admin-api/admin-api/ai/meeting/internal/face-event 必须非 2xx
```

### 10.5 验收指标

| 指标 | 阈值 | 口径 |
|---|---|---|
| 定性表述 | 0 | 枚举文案 ＋ 前端拼接的 grep 核查（§9.4） |
| 单帧即结论 | 0 | `face_frames_used ≥ minFrames` 恒成立（§4.3-14 的实现证据） |
| 服务故障时误判 | 必须为 `FACE_UNAVAILABLE`，不得为 `MATCHED` 或 `MISMATCH` | 用例⑯ ＋ 上线后周报巡检 |
| 帧落盘 | 0 文件 | §10.4 步骤 8 |
| 撤回后向量残留 | 0 行（物理删除） | 用例⑲ ＋ 生产抽检 SQL |
| 门禁翻转 | `jailed-by-poc=false` 时任何环境都不产 `kind='video'` 告警行 | 用例㉖ ＋ §10.4 步骤 7 ＋ SQL 巡检 |
| 核验时延 | 任务发起到终态 ≤ 45s（P95，分支 B 下 4 帧 × 15s 间隔的算术上界） | `face_frames_total` 与时间戳 |
| 在场记录正确性 | `skipped` 行不进入「连续无脸」计数 | 用例㉓ |
| 特征服务被当成通用工具 | 无 `X-Verify-Token` 打 `embed` 必须 403 | §10.2 「任务窗口」行（worker 侧无任务即不外呼）＋ §8.4.7 `verify.ps1` 第三段（服务侧 403）；本文不假设 Java 侧能验证服务侧的拒答行为，所以两边各自钉一条 |

---

## 11. 风险与遗留

| 项 | 状态 | 处置 |
|---|---|---|
| **G0 未证实，形态 ① 可能被整体否决** | 本文最大的单点风险 | 第一步只提交观察日志；若视频轨不可达，本文须改写为形态 ②（并连带真做 §0.1 的上传修复），届时这是一次重设计，须重新评审 |
| 无活体检测，「一致」结论可被照片欺骗 | 已确认的能力边界 | §4.3 措辞硬约束 ＋ §9.2 告知必答 ＋ §10.4 步骤 6 让评审亲眼验证该风险；**不接受**任何「已确认本人到场」的业务表述 |
| 相似度阈值缺本地标定 | 高 | G2 门禁；标定前 `jailed-by-poc` 保持 `false` |
| ~~insightface 预置模型包（`buffalo_l`）官方声明仅非商业研究用途~~ | **已随换件作废**（2026-11-05） | 已改用 CompreFace ＋ 可商用开源权重（总纲 D-2）：**「模型权重授权」子项已解决**；但 **G3 整体仍未通过** —— 模型名与版本清单、许可快照与法务留档、命名卷留存/删除、告知文案审定四项待办保留，`MEETING_FACE_POC_PASSED` 保持 `false`。原 §8.4.1-L1 与 §8.4.9-V6 的处置路径不再适用 |
| 误判「疑似非本人」的社会成本极高（涉及诚信与责任认定） | 高 | 三重保守：连续帧 ＋ 跨时长 ＋ 质量达标（§4.3-16）；只提示不定性；不改状态；处置由人 |
| SP-1/SP-2、SP-5 尚未实现，本文依赖其对象均不存在（`MeetingAlertDO`、`ai_party_verify_record`、`PartyApi` 均为设计态） | 事实 | 实施顺序固定 SP-1/2 → SP-5 → SP-4 → SP-3（§7 执行前置）；本文不得先行落地，否则 V3.56 直接失败 |
| worker 单实例本期串行 2–4 轨（`worker.py` 注释 L15），叠加视频解码与 SP-4 的 SER 后会成为性能瓶颈 | 中 | 三路任务各自 `to_thread`；帧并发默认 `2` 且非阻塞；多副本评估属既有 M20 范畴，本文不扩 |
| LiveKit 与密钥仍是 Demo 级（事实 7 的 `devkey`/`secret`、`localhost:7880`） | 现存问题 | 生产化属会议模块整体上线清单，本文只在 §6.4 探活上依赖它可达；不另开一项 |
| ~~`embedding` 以明文列存储~~ | **已随 CompreFace 1:1 架构作废** | `ai_face_gallery` 整表废弃、平台不持有向量（总纲 B/T6）；现行 G3 必答项改为 CompreFace 内置 Postgres 命名卷的留存期/备份加密/撤回删除流程（部署件 README §2/§3）。`jailed-by-poc` 仍不得置 `true`（§6.4） |
| 「声纹 vs 人脸」的说话人一致性 | 后续立项 | 与 SP-4 有天然协同（同一 PCM ＋ 同一帧），但需独立同意与阈值标定，登记为可立项项，本文不实现 |
| `MediaCapture.vue` 的假上传已在前端可见（用户每次都看到「上传成功」） | 现存缺陷，不属本文 | 建议与 SP-3 同期改造（§0.1）；若不同期，须在争议大厅侧先隐藏该提示，否则 SP-3 上线时评审会把它当作真实链路 |

---

## 12. Spec 自检（写完后逐条核对）

> **2026-11-05 作废指针**：下表是 2026-11-04 insightface 方案的自检结论，其中「内部一致性 / 号段冲突 / 未验证即写入的内容」等行提到的 `9505`/`9507`、`8030/8031`、`buffalo_l`、`512 维`、`normed_embedding`、`X-Verify-Token`、`minQuality`、`MULTI_FACE` 409 均为**已作废旧口径**；以顶部总纲 A–E、D-2 段与 §6.5/§8.1 为准。号段按 D5 收缩为**菜单仅保留 `9506`**，端口为 `8050/8051`。本表保留原文作对照，不作为实施验收依据。

| 检查项 | 结论 |
|---|---|
| 占位符 | 无 `TODO`、`TBD`、`FIXME`、`待定`、`待补充`、`待办`、`xxx`（§0.1 与 §0.2 里的引述是在**罗列被审代码的现状缺陷**，不是本文遗留）；每张表每格均有内容；§8.4.9 的 V1–V6 与 §11 的「移交运维决策」行也不是占位，它们各自带验收人与「未完成即不得置启用开关」的后果 |
| 内部一致性 | `kind='video'` 全文保持单一取值（§0-T3 明确不新增第四值），子通道用 `video_channel` 列；§4.3 的 8 个 `FACE_*` verdict 与 §10.1 用例⑦–⑯逐一对应（⑦NO_BASE ⑧BASE_STALE ⑨NO_FRAME ⑩INSUFFICIENT ⑪MATCHED ⑫⑬⑭为 MISMATCH 的三态正反例 ⑮UNSTABLE ⑯UNAVAILABLE）；错误码只用 `1_040_065_*` 七条，引用 SP-5 的 `1_040_063_000` 两处均已标明是复用；迁移号只用 `V3.56`、`V3.57`；菜单 `9505`（建库）`9506`（人像核验发起）`9507`（底库物理删除）三 ID 各有归属且与 §6.1 逐行对得上；§3.3 契约与 §8.4.6 实现件已对平（detect 无逐请求参数、embed 需 `verifyId` ＋ `X-Verify-Token`、`MULTI_FACE` 走 409），首稿 §3.3 写的 `request={"minFacePx":40,"maxFaces":5}` 与 `faceBox` 已确认与实现件矛盾并本轮抽修（参数一律走容器环境变量，与 §6.5 的 Java 单一来源对齐） |
| 编号体系 | 全文三套编号互不混用：§4.3 判定表序号 `11–18`（延续 SP-5 §4 的十行表，非笔误，已在该节开头声明）、§10.1 用例号 `①–㉘`（本文自起仍连续，不接 SP-4 的 ⑫）、§10.4 冒烟步骤 `1–9`。本行是修订后补的：首稿把用例误从 ⑫ 起编（把 SP-4 的尾号接了过来）且缺 `FACE_MATCHED` 用例，两者均已于自检时抽修。§10.5 的指标口径引用已随重排同步（⑯⑲㉖㉓），不再指向不存在的 ㉚。 |
| 号段冲突 | 事实 17、18、19 与 SP-1/2、SP-5、SP-4 四份交叉核查：`065`、`V3.56-3.57`、`9505-9507` 均不重叠；`V3.58` 起明确留空；deploy 端口本文取 `8030/8031`，与 OCR 的 `8011`、SP-4 的 `8020/8021` 互不冲突 |
| 对上游的修订是否显式 | 四条（T1–T4）在 §0，其中 T1 标注为「受门禁约束的作废」并给出可关断实现（§6.4 `jailed-by-poc`）；§5.3 逐条对齐 SP-5 的六个接缝；§7 第 4 步同步修订 SP-1/2 的 `kind` 注释 |
| 未验证即写入的内容 | 人脸模型选型已按用户指令定为 insightface `buffalo_l`（§8.4），但本文明确区分两类内容：**已核实的官方事实**（L1 许可声明、L2 分族准确率、SCRFD-10GF ＋ ResNet50@WebFace600K 结构与 512 维未归一化输出，均附出处）与**尚未实测的设计值**（§8.4.9 V1–V6：onnxruntime 线程行为、`normed_embedding` 字段名、镜像体积、内网分发路径等）。因为 `Demo-deploy/face/` 是一套**还不存在**的部署，本文不写「故障排查（已踩过的坑）」那一章；同样不声明视频轨可达（§0.2 与 §8.1 把「未证实」当第一约束）、不声明 Egress 存在（事实 9 明确其为空缺） |
| 行内代码跨行 | 已检查，无反引号跨行 |
| 表格内裸竖线 | 已检查，单元格内并列一律用「＋」或文字「或」，未出现未转义竖线（本轮 SP-4 曾在此自破一次，本文写作时已规避同一写法） |
| ASCII 图示对齐 | §3.2、§8.1、§8.4（目录树）、§10.4 为纯文本缩进与命令，行首前缀统一 ASCII 减号，无制表符边框字符（歧义宽度字符在中文环境按全角渲染会散架，SP-1/2 已踩过，本轮插入 §8.4 后重新实测，本文 `BOXDRAW=0`、`BAD_ROWS=0`、`EMPTY_CELL=0`） |
| 编码与换行 | UTF-8 无 BOM、LF、无制表符、无替换字符 |
| 硬约束遵循 | 未修改任何生产代码；未 git commit；接口路径、类名、列名、行号全部来自 §2 实读出处；本文无 UI 样式变更，不涉及色值 |

---

## 13. 交付清单（G0–G3 通过后逐项存在）

> **2026-11-05 作废指针**：下列清单是 insightface 自建容器方案的交付物，`FaceGalleryDO` / `FaceSimilarityCalculator` / `FaceGalleryService`、`face_provider.py`、`Demo-deploy/face/`、`gallery/status` ＋ `enroll` 入口、菜单 `9505`/`9507`、端口 `8030/8031` 等**已整体作废**；生效交付物见顶部总纲 B 段与 D-2 段（CompreFace ＋ YuNet/SFace 可商用权重、只做 1:1 verification、平台不持有向量、菜单仅保留 `9506`）。**G0–G3 未过前本清单仍一项都不得开工**，`MEETING_FACE_POC_PASSED` 保持 `false`，Task 11 前置不变。
>
> 本轮（设计 + 部署件配置）新增的交付物**仅限于**：SP-3 本文的 D-2 选型章节与作废指针、`Demo-deploy/compreface/` 的 `docker-compose.yml` / `.env.example` / `scripts/{deploy,verify}.ps1` 中的模型来源、自定义镜像标识、SHA256 期望值与离线校验断言、以及部署件 README 的门禁与留档口径同步。**不含 Java 业务链路或 `V3.56+` 迁移。**
>
> **2026-11-05 部署 PoC 补记**：上述「不含插件适配层、权重文件、下载脚本、自定义镜像 Dockerfile」的边界已按用户指令解除——插件适配层（`build/core-build/`）、YuNet/SFace 权重下载与 SHA256 留档、自定义镜像 `compreface-core-yunet-sface:1.2.0`、`scripts/build-core.ps1` 与 REST 引导流程、`verify.ps1` 9/9 契约实测记录均已交付。**门禁语义不变**：G1 真实帧召回率、G2 阈值标定、G3 其余四项仍待办，`MEETING_FACE_POC_PASSED` 保持 `false`。

- **G0 观察件（唯一可先于门禁提交的东西）**：`Demo-ai/deploy/livekit-worker/worker.py` 的 `[track-observe]` 日志 ＋ 双人真机日志留档
- `Demo-ai/deploy/livekit-worker/`：`face_provider.py`（`FaceProvider`、`HttpFaceProvider`、`get_face_provider`、采样器、并发门、断路器）；`worker.py` 放开视频轨分支并按参与方建流；`README.md` 环境变量表追加 `FACE_PROVIDER`、`FACE_GATEWAY_BASE_URL`、`FACE_API_KEY`；`requirements.txt` 与 `Dockerfile` 不因本文变更（图像编码走 `livekit` 自带帧缓冲 ＋ 标准库）
- `Demo-module-ai-server`：`FaceGalleryDO`、`MeetingPresenceDO` 及 Mapper（仅提供 `selectByPartyId`）；`FaceSimilarityCalculator`；`FaceGalleryService`、`PartyFaceVerifyService`、`MeetingFaceEventService`、`MeetingFaceAvailabilityService`；`controller/admin/meeting` 内新增 `face-event` 与 `face/*` 端点；`PartyVerifyReqVO` 增 `verifyType`；`ErrorCodeConstants` 加 `1_040_065_000-006`；`PartyVerifyVerdict` 增 §4.3 八值；`AlertLevel` 增「疑似非本人到场」与「离席提示」两条文案；`config/MeetingFaceProperties`
- `Demo-ai/docs/sql`：`V3.56__face_gallery_and_presence.sql`、`V3.57__face_menu.sql`
- `Demo-web`：视频卡片 `available` 由服务端驱动（G0–G3 未过时仍显示不可用与 reason）；`gallery/status` 与 `enroll` 入口（当事人档案页 ＋ 会议面板两处同源）；告警卡 `videoChannel` 分支
- `Demo-deploy/face/`：`docker-compose.yml`、`nginx/default.conf.template`、`insightface-svc/{app.py,Dockerfile,requirements.txt,models/<zoo>/*.onnx}`、`scripts/{deploy,status,verify,stop}.ps1`、`.env.example`、`README.md`；逐文件内容见 §8.4，其中 `verify.ps1` 的「无凭据打 embed 应 403」一条缺位即视为未交付（§8.4.7）
- 测试：Java 6 个测试类（§10.1，共 28 条编号用例）、worker pytest（§10.2 八组）、前端 vitest（§10.3 四组，含 verdict 映射扩至 18 值）、冒烟九步（§10.4）
- 文档留档：G1 检测可用率标注报告、G2（**按 YuNet + SFace 重标定**）FAR/FRR 报告、G3 剩余四项（模型名与版本清单、权重许可快照与法务意见、命名卷留存/删除流程、告知文案三点审定）；**上述齐备并经人工确认后方可置 `MEETING_FACE_POC_PASSED=true`**。2026-11-05 选定可商用权重只解决「权重授权」子项，不构成上述任一报告的替代
- 上游修订同步：SP-1/2 spec 的 §8 不变量②、§1.2 非目标行、§9 对齐表三处须加「SP-3 已设计，翻转受 `jailed-by-poc` 约束」的指针（本文单向声明，不代改其原文）
