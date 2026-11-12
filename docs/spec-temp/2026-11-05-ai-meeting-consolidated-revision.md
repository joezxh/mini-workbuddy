# AI 视频会议：原型 / 组件 / 四份 Spec 一致性审阅与可落地修订方案

> 日期：2026-11-05　状态：**待用户复核**（本文件为修订方案，不改动四份 spec 正文，不解除任何门禁）
> 审阅对象：
> - 原型 `Demo-web/prototype/meeting-room.html`（925 行，单文件 HTML）
> - 组件 `Demo-web/src/views/ai/meeting/MeetingRoom.vue` + 15 个组件 / 5 个 composable
> - S1 `2026-11-04-meeting-room-ui-design.md`（SP-1/2）
> - S5 `2026-11-04-party-identity-verification-design.md`（SP-5）
> - S4 `2026-11-04-acoustic-ser-design.md`（SP-4）
> - S3 `2026-11-04-face-vision-analysis-design.md`（SP-3，含 2026-11-05 覆盖性修订总纲）
> - 定版参照 R `2026-11-04-meeting-ai-spec-review-and-revision.md`、P `plans/2026-11-05-meeting-ai-specs-implementation.md`
>
> **本文只做「设计订正 + 前端可落地完善」；不写 Java 核验代码、不改 worker 视频轨、不部署业务链路。**

---

## 0. 工程事实基线（2026-11-05 实测，作为一切修订的前提）

### 0.1 远端部署拓扑（用户 2026-11-05 补充）

| 组件 | 地址 | 凭据 / 说明 | 实测 |
|---|---|---|---|
| LiveKit 信令 | `ws://192.168.110.169:7880` | `devkey / secret` | TCP 可达 ✅ |
| CompreFace 业务网关 | `http://192.168.110.169:8050` | 外层 `X-API-Key`；仅放行 `detection/verify`，1:N 404 | TCP + 端到端 detect/verify 200 ✅ |
| CompreFace 控制台 | `http://192.168.110.169:8051` | `COMPREFACE_UI_BIND=0.0.0.0`，内网可达（无外层 key 保护） | ✅ |
| 共享 PostgreSQL | `192.168.100.80:5432` | `postgres / postgres@2026!`，库 `compreface` | ✅（空库已由 liquibase 建表并完成服务引导） |
| ai-server | 本地 dev `localhost:8086`（Vite `/api` 代理） | 生产以网关为准 | 未在远端核实 |
| 前端 Vite dev | `VITE_AI_PROXY_TARGET=http://localhost:8086` | `VITE_API_BASE_URL=/api` | — |

**LiveKit 配置对照（重要）**：`Demo-ai/.../application.yaml:371-377` 为

```yaml
livekit:
  server-url: ${LIVEKIT_SERVER_URL:ws://localhost:7880}   # 下发给浏览器的信令地址
  api-url:    ${LIVEKIT_API_URL:http://localhost:7880}     # 服务端探活地址
  api-key:    ${LIVEKIT_API_KEY:devkey}
  api-secret: ${LIVEKIT_API_SECRET:secret}
```

`MeetingRoomServiceImpl.resolvePublicServerUrl(clientOrigin)` 已实现：配置为回环且客户端经非回环 host 访问时，用客户端 host 替换回环 host、并按 https→wss 升级；非回环配置原样下发。

**结论**：用户给的 `ws://192.168.110.169:7880` / `devkey / secret` 与现有代码契约完全吻合。若 ai-server 与 LiveKit 同机（192.168.110.169），保持默认 `localhost:7880` 即可由改写逻辑下发正确地址；**若 ai-server 在别处**（例如本机 8086 而 LiveKit 只在远端），必须显式设：

```bash
LIVEKIT_SERVER_URL=ws://192.168.110.169:7880      # 浏览器可达
LIVEKIT_API_URL=http://192.168.110.169:7880       # 服务端可达
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

否则浏览器会连到「ai-server 所在机器的 localhost:7880」而失败。**这是一个部署期必须确认的硬配置项，四份 spec 全部未写。**

**混合内容边界**：前端若经 HTTPS 提供，`ws://` 会被浏览器按 Mixed Content 拒绝；`describeConnectFailure()` 已给出明确提示，但部署规范必须写明「HTTP 内网 → ws；HTTPS → 必须 wss + 证书」，现有 spec 零覆盖。

### 0.2 前端现状（实测）

- `MeetingRoom.vue` 已是原型的**组件化 + LiveKit 真实化移植**：四区 Grid（48/320/68/96）、暗舞台+亮外壳、4 个侧栏 Tab、舞台稳定 key、告警/字幕/说话高亮只改 dataset，均与原型的刻意约定一致。
- 已修复的原型缺陷：gallery 共享重复 tile、远端音频挂在 muted video 上、字幕按钮高亮不同步（Vue 用 computed 绑定）。
- **没有任何人脸抓帧 / 核验 API / 结果 UI**：只有 `video` 能力卡（`available=false` + 服务端 reason）、`videoChannel` 字段与图例文字。原型同样没有 canvas/toDataURL。
- 分析数据源：真实后端 `MeetingAnalyzeController` 已完整实现（前端 `api/ai/meeting.ts:157` 的「后端尚无实现」注释**已过期**）；DEV 演示态 `demoStatuses()` 仍只造 2 张卡，而后端 `AnalyzeKind = voice|ser|video` 三值。
- 门禁：`application.yaml:384-390` `video-gate-passed=${MEETING_G3_VIDEO:false}`、`ser-gate-passed=false`、`voice-gate-passed=true`；`MEETING_FACE_POC_PASSED=false`、`video.available` 恒 `false`（S3:417、CompreFace README）。
- 工具链：`pnpm type-check` 有 2 条 `MeetingList.vue` 既有基线错误；`eslint`/`prettier` 未装进 devDependencies，`lint/verify` 不可用；vitest 会议相关 7 个 spec / 46 用例为绿。

---

## 1. 四方一致性对照（结论先行）

| 维度 | 原型 | MeetingRoom.vue | Spec（定版 R/P） | 现状裁决 |
|---|---|---|---|---|
| 视频卡命名 | 「视频行为分析 / SP-3 / ready:false」 | 「人像到场一致性核验（CompreFace 1:1）」 | R:70/C06 要求改为「人像到场一致性核验」 | **以 spec 定版为准**，原型为历史命名；不要回退 |
| 视频卡交互 | 可点但即时回弹 + toast 回显服务端 reason | 无权限才置灰；`available=false` 时拒绝点亮 | S1:67「点击无效」/ S3:1077「disabled」/ R:300「可点、回弹、toast」 | **定版 R:300**：可点 + 回弹 + toast，前端现实现更接近定版 |
| 能力卡数量 | 2 张（voice/video） | 组件按服务端数组渲染（不硬编码），DEV 演示态造 2 张 | R:142 三值 `voice\|ser\|video`、前端不硬编码 | 组件正确；**演示态需补 ser** |
| 身份来源 | 参会轨 identity（非人脸推断） | 同 | 同 | 一致 |
| 人脸核验流程 | 无 | 无 | 门禁通过后才允许 Task 11 | **门禁前保持无**，不是缺陷 |
| 成员名单 | 5 人 mock（含未入会） | LiveKit 真实轨；未入会恒空、角色靠 identity 前缀猜 | S1:92 已知缺口 | 真实数据优先；未入会名单需后端接口（P1） |
| 信令 | 无（本地 getUserMedia） | LiveKit token → serverUrl | 四份 spec 零覆盖 | 见 §0.1，需补部署契约 |

---

## 2. 冲突清单（按处理优先级）

> 影响范围列中的「前端 / 后端 / DDL / 部署 / 合规」用于排期。

### P0（补充，2026-11-05 实读发现）

| # | 问题 | 证据 | 影响 | 处置 |
|---|---|---|---|---|
| C00 | **RSA 私钥硬编码在前端源码**：`jsencrypt.ts:8-16` 内含完整 `privateKey`，与 `DEFAULT_PUBLIC_KEY` 配对。任何能拿到前端 bundle 的人都能解密用户登录密码；前端私钥本身也否定了非对称加密的意义 | `Demo-web/src/utils/jsencrypt.ts` | **全站账号安全** | 立刻从前端删除私钥（仅保留公钥）；私钥只留后端；轮换该密钥对；审计是否曾提交进仓库历史。本轮只登记，**未擅自改动登录链路** |

### P0 —— 会直接导致做错系统或上线事故

| # | 冲突 / 问题 | 证据 | 影响范围 | 优化建议 | 优先 |
|---|---|---|---|---|---|
| C01 | **用户要求「人脸识别使用远端 CompreFace」 vs 门禁 `MEETING_FACE_POC_PASSED=false` / Task 11 前置** | S3:48,417,1160；P:592,630；CompreFace README | 合规 + 业务链路 | 远端服务仅作**契约取证/联调环境**；前端继续完全由 `/analyze/status` 的 `available/reason` 驱动，保持 `available=false`、不抓帧、不产画面结论。`MEETING_FACE_POC_PASSED` 只在 G0–G3 四项留档齐备并人工确认后才置位。**本轮不接业务链路** | 1 |
| C02 | **S3 正文 1100+ 行作废内容未清除**：`ai_face_gallery` DDL、512 维 `embeddingBase64`、`X-Verify-Token`、insightface Dockerfile、enroll/gallery 端点、28 条旧测试 | S3:3-38 总纲作废 vs S3:465-488,743-757,1051-1053,1168 正文 | 全链路 | 将 S3 正文 §3–§13 整体移入 `docs/.../deprecated/` 或加统一「整章作废」banner；另出**单一生效版 SP-3 精简 spec**（本文 §4 可作为骨架）。禁止开发者按正文实施 | 2 |
| C03 | **「已完成 / 未完成」事实互相打脸**：S3:86/1164 称部署 PoC 9/9 已落地，R:218/234 与 P:813 称镜像未构建、服务未部署 | 同上 | 交付/验收 | 以实测为准：本地 + 远端 CompreFace 均已部署并 9/9 通过；把 R/P 的状态登记改为「部署 PoC 已完成（契约层），门禁未通过」，四份 spec 顶部状态同步 | 3 |
| C04 | **门禁公式三处不一致**：S1:239「video 可翻 true」/ S4:70,170「video 恒 false」/ S3:381「按探活计算」；S4:292-299 的 ser `available` 判定不含 `g3Passed`；S3:413 不含同意项 | R:143、P:17 | 后端 + 合规 | 定版为**唯一公式**：`available(kind) = platformEnabled(kind) AND probeOk(kind) AND g3Passed(kind) AND noticeConfirmed AND validConsent(scope)`；`g3Passed(video)=MEETING_FACE_POC_PASSED`、`g3Passed(ser)=MEETING_SER_POC_PASSED`（**新增开关**）、`g3Passed(voice)=true`。未通过时 `enabled=false, available=false, reason=真实原因, 不写开关行, 不产该 kind 告警` | 4 |
| C05 | **DDL 硬缺口**：`ai_meeting_alert.video_channel` 列在 V3.49/55/56 全部缺失；V3.56 缺 `room_id` 且 `verify_type VARCHAR(16)` 与定版 VARCHAR(24) 冲突 | S3:111,393 vs S3:461-532；S4:365-399；P:42 | DDL | 在 V3.56 一次性补 `video_channel VARCHAR(16)`、`room_id BIGINT`、`verify_type VARCHAR(24)`；`uk_ai_meeting_alert_transcript` 按 S4 改为 `(transcript_id, kind)` 部分唯一 | 5 |

### P1 —— 契约与状态定义不清，前端会写错

| # | 问题 | 证据 | 影响范围 | 优化建议 |
|---|---|---|---|---|
| C06 | `AnalyzeStatus.kind` 合法集：S1 两值 `voice\|video`、S4 加 `ser`、R/P 定版三值；卡片数 S1「两张」/ S4「第三张」硬编码 | S1:157,236,376；S4:980；R:142 | 前端 + 后端 | 前端**只渲染服务端返回数组**（现组件已做到）；`createDemoSource()` 补 `ser`；TS 联合类型固定三值、VO 由后端驱动 |
| C07 | `noticeConfirmed` 语义自相矛盾：D2 降级为「操作人确认动作、前端固定携带」，S1:240 仍保留 `1_040_061_006` 判定行 | S1:13,240,260；S4:298；P:18 | 后端 | 二选一并写进测试：若前端固定 true，则删除该错误码判定；若保留，则明确它是「审计确认」而非「单独同意凭据」，且同意校验走 `consentId + scope` |
| C08 | 同意范围枚举：S1 四值 / S5 五值（含 `VOICEPRINT_VERIFY`）/ R 四值 / P 五值定版 | S1:13；S5:6,300,317；R:97；P:18 | 合规 + 前端 | 定版**五值**；`FACE_COMPARE` 单独同意**不能**充当 `IDCARD_VERIFY` 凭据（已有测试断言，保留） |
| C09 | FACE_* 判定族未定版：S3:27 废弃 `FACE_NO_BASE/BASE_STALE`、新增 `FACE_SOURCE_UNAVAILABLE/SERVICE_UNAVAILABLE`，正文 S3:313-322 仍是旧 8 值；S3:1080 要前端映射 18 个 verdict，S5:445 只写 10 个 | S3:27,313-322,1080；S5:445；R:190-191 | 前端 + 后端 + 测试 | 出**唯一 verdict 枚举表**（含 unknown 类、PENDING、服务不可用三类），前端映射表由该表生成；`FACE_MISMATCH` 是唯一红色不通过，其余一律「疑似/未完成」而非失败 |
| C10 | 「离席提示」子开关无落点；快照结构三份不同（固定 `{voice,ser,video}` + 可选 `serPolicy/facePolicy`，缺失 fail-closed） | S3:294；S4:128-129；S3:224-225；R:146 | 后端 + worker | 删除「离席提示」子开关或立项为 SP-6；快照结构钉死为 `R:146`，worker 读取缺失字段一律 fail-closed |
| C11 | 阈值冲突：`0.45` 余弦占位已作废 vs 正文仍用；极差 `>0.25` vs G2 标定阈值；`det-score-threshold 0.5` vs `minQuality`；128 维 vs 512 维 | S3:82,328,430,441,446,469,635 | 后端 | 生效口径：SFace **128 维**、平台不持有向量、**阈值 G2 本地标定前为空**、检测器口径 `box.probability ≥ 0.5`；正文旧值全部作废 |
| C12 | `video` 卡 `available=false` 时三种交互（点击无效 / disabled / 可点回弹）并存 | S1:67；S3:1077；R:300 | 前端 | 定版 R:300：可点击、不点亮、toast 回显服务端 reason；**仅无权限**时开关整体置灰。现 Vue 实现已符合，勿回退 |
| C13 | 声学侧「关闭后最长 30s 仍在采集」未在 UI 呈现；`serEmotion=null` 时不得显示默认 `calm` | S4:877,910,938 | 前端 | 在 SER 卡描述与会议信息 notice 增加该文案；依据栏 `serEmotion` 为空时不渲染该行 |
| C14 | 接口数据结构不完整：`FaceEventReqVO` 仍含 `embeddingBase64/embeddingDim`（与「平台不持有向量」冲突）；`/verification/verify` 请求/响应契约四份 spec 均未定义 | S3:243,389,397；S3:23 | 后端 + 契约 | 删净 `embedding*` 字段；用本轮实测契约定版：`POST /face/api/v1/verification/verify`（`source_image`/`target_image`）→ `result[0].face_matches[0].similarity`；detect → `result[].box.probability`；实测同人 0.919 / 异人 0.078 仅为参考点，**G2 阈值另标定** |

### P1（续）—— 工程能力不匹配

| # | 问题 | 证据 | 优化建议 |
|---|---|---|---|
| C15 | **G0 未证实**：`worker.py:84` 显式丢弃非音频轨，视频帧能否到达 worker 无真机证据 | S3:99,139-141,547 | 维持门禁；G0 取证只做「双人真机各开摄像头 + 观察 2 条 KIND_VIDEO 日志」，不改判断分支。G0 不过则 SP-3 全链路不得开工 |
| C16 | 前端 `firstVideo()` 未按 `Track.Source` 过滤，屏幕共享轨可能被当成摄像头轨渲染 | `useRoomSession.ts:41-47` | **本轮已修**：仅取 `Camera` / `Microphone` 源 |
| C17 | `api/ai/meeting.ts:157` 注释「后端尚无实现」与 `MeetingAnalyzeController.java` 已实现矛盾 | 同上 | **本轮已修注释**，并在修订方案登记真实端点 |
| C18 | S1:255 仍写 `hasPermission`、S1:688 仍写改 `styles/variables.css`，与现实现 `accessStore.hasAccess` / 独立 `meeting.css` 不符 | S1:15,216；R:42 | 订正为现实现，避免后续按错文档改代码 |
| C19 | 权限点：前端只校验 3 个（create/analyze/alert-ack），后端另有 join/query/update；路由无权限守卫 | router/index.ts:475-480 | 路由 `meta` 补 `requiresAuth + permission`；`/ai/meeting/live` 至少要求 `ai:meeting:join` |
| C20 | 菜单/端口/迁移号三方重叠：9505/9506、8030/8031 vs 8050/8051、V3.58 归属 | S3:7,31,1140,1147；S4:353,442；P:43 | 定版 P:D4/D5：SP-3 只留 9506、端口 8050/8051、V3.56；SP-4 复议 9512/9513、8020/8021；SP-6 V3.58–3.60 |

### P2 —— 边界、安全、隐私、职责

| # | 问题 | 建议 |
|---|---|---|
| C21 | 无活体检测，1:1 可被照片欺骗（S3:161,1095-1097） | 结论措辞强制「疑似不一致，请现场确认」，永不自动改 `party_identity.status`；告知文案三点审定列为 G3 必答 |
| C22 | CompreFace 侧无「无持久化」保证：管理库含账号/服务 key，撤回后删除流程未定义 | G3 必答项保留；本部署已移除内置 PG 卷、复用 192.168.100.80 外部库，删除流程须走数据删除审批 |
| C23 | 远端 8051 控制台已 `0.0.0.0` 暴露且无外层 key 保护 | 加 ufw 网段白名单；`devkey/secret` 属 Demo 密钥，生产必须 ≥32 位随机串并走环境变量 |
| C24 | 转录原文/告警 `text_snippet` 长期留存、无查阅删除权 | 补留存期与删除权设计（跨 spec 缺口，S4:876 自认） |
| C25 | `PartyApi` 设为 `@PermitAll` 仅靠内网隔离；`/rpc-api` 不对外路由「须在网关验证」 | 上线前实测网关路由；敏感字段（完整身份证号、证件照 URL、图片字节）禁出 VO |
| C26 | `MediaAnalysisServiceImpl` 恒返 `calm`、`getCapabilities()` 四项全 true；`MediaCapture.vue` 伪造 `analyzed` | 关服务时零假数据：不出现 `kind=ser` 新行、不显示默认 calm；假能力不得进评审演示 |
| C27 | 模块归属：S3:371「全部置于 controller.admin.meeting」vs S5:255「controller.admin.party」vs P:58-59 两处并存 | 定版：`PartyVerifyController`（admin/party）负责核验编排，`MeetingFaceEventService`（service/meeting）负责事件落地，不新建 Controller 包 |
| C28 | S5 二次授予语义、PENDING 轮询间隔/超时/重入、核验任务取消/超时/并发 `identity→partyId` 映射均未定义 | 补「任务生命周期状态机 + 幂等键 + 超时」章节，测试用例钉死 |
| C29 | `lint/verify` 工具链损坏（eslint/prettier 未入 devDependencies，旧式 `.eslintrc.cjs`） | 单独立项修工具链；本轮验证改用 `type-check`（过滤 meeting 路径）+ `vitest run` 会议室相关 spec |

---

## 3. 原型 / 组件 / Spec 三方冲突的明确裁决

1. **原型「视频行为分析」vs 组件/spec「人像到场一致性核验」** → 以 **spec 定版（R:70/C06）** 为准；原型为 11-04 旧名，不回退。
2. **原型 `ready:false` 硬编码 vs 组件服务端 `available/reason`** → 以**组件**为准；前端绝不本地判定能力可用性。
3. **原型 2 张能力卡 vs 后端 3 个 kind** → 组件不硬编码（正确），DEV 演示源补 `ser`（本轮已修）。
4. **用户「接远端 CompreFace」vs 门禁未过** → 远端服务作为**契约取证环境**；前端能力卡保持 `available=false`、reason 显示真实门禁原因；**不新增抓帧/核验 UI、不产画面结论、不展示示例数据**。这是本轮唯一「不按用户字面执行」的点，须经用户确认 G0–G3 后再开 Task 11。
5. **原型 mock 成员/Case号 vs 组件真实 LiveKit 轨** → 以真实数据为准；原型 mock 只作为视觉对齐参照，不回灌。

---

## 4. 定版修订方案（可直接落地）

### 4.1 唯一门禁公式（覆盖 S1/S3/S4 各自表述）

```
available(kind) =
    meeting.analyze.enabled
    AND platformEnabled(kind)          # voice / ser / video 各自开关
    AND probeOk(kind)                  # 远端服务探活：CompreFace :8050 / SER :8020
    AND g3Passed(kind)                 # video=MEETING_FACE_POC_PASSED；ser=MEETING_SER_POC_PASSED（新增）；voice=true
    AND noticeConfirmed                # 操作人确认（审计），非同意凭据
    AND validConsent(scope)            # FACE_COMPARE / SER_ANALYSIS / VOICE_ANALYZE 单独同意

未通过 → enabled=false, available=false, reason=具体原因, 不写开关行, 不产该 kind 告警
```

### 4.2 服务端驱动契约（前端不得越权）

| 对象 | 定版结构 |
|---|---|
| `AnalyzeStatus[]` | `kind: 'voice'\|'ser'\|'video'`, `label`, `sp`, `phase`, `enabled`, `available`, `reason: string\|null`；**条目数量与顺序由服务端决定** |
| `MeetingAlert` | 合并 S1/S4/S3 全部可空字段：`videoChannel`, `faceSimilarity`, `faceFramesUsed/Total`, `faceServiceModel`, `serEmotion`, `serConfidence`, `serModel`；`serEmotion=null` 不渲染该行 |
| 快照 | 固定 `{voice, ser, video}` + 可选 `serPolicy`/`facePolicy`；缺字段 fail-closed |
| CompreFace 1:1 | `POST http://192.168.110.169:8050/face/api/v1/verification/verify`，头 `X-API-Key`，multipart `source_image`/`target_image` → `result[0].face_matches[0].similarity`；`detect` → `result[].box.probability`；1:N 路径网关 404 |
| 门禁纪律 | `MEETING_FACE_POC_PASSED=false`、`MEETING_G3_VIDEO=false`、`video.available=false`、`V3.56+` 迁移与菜单 9506/Task 11 全部冻结 |

### 4.3 远端部署契约（四份 spec 缺失，本轮补）

```bash
# ai-server（与 LiveKit 同机时可省略 SERVER_URL，由 resolvePublicServerUrl 改写）
LIVEKIT_SERVER_URL=ws://192.168.110.169:7880
LIVEKIT_API_URL=http://192.168.110.169:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
# CompreFace（仅契约取证；门禁通过后才允许进入业务编排）
COMPREFACE_BASE_URL=http://192.168.110.169:8050
COMPREFACE_API_KEY=<外层 X-API-Key>
DB_HOST=192.168.100.80  DB_PORT=5432  DB_USER=postgres  DB_PASSWORD=***  DB_NAME=compreface
# 门禁（保持 false）
MEETING_G3_VIDEO=false  MEETING_SER_POC_PASSED=false  MEETING_FACE_POC_PASSED=false
```

> 前端**不持有** `devkey/secret`、不持有 CompreFace 服务 key：LiveKit token 与 CompreFace 调用都由后端签发/转发。HTTPS 部署时必须把 `ws://` 换 `wss://` 并配证书（否则 Mixed Content 拦截）。

### 4.4 交互状态定版（补齐 S1 未定义项）

- 能力卡 `available=false`：**可点 → 即时回弹 → toast 回显服务端 reason**；仅无权限时整体置灰。
- 三卡独立：`toggle(ser)` 不改 `voice`；关闭后 UI 明示「最长 30s 仍在采集/处理」。
- danger 红条：15s 自动撤下或全部 ack 后撤下；**新 danger 重置计时**；红条只改 `stage.dataset.risk` + 独立 `RiskBanner`，绝不重建 tile DOM。
- 未读角标：0 时隐藏；多实例 SSE 各自维护订阅，不假设广播可达。
- 连接态：`connecting/connected/reconnecting/disconnected` + `lastError` 分层文案（现有 `describeConnectFailure` 已覆盖密钥/时钟/权限/混合内容/网络五类，保留）。

### 4.5 前端职责边界（本轮实现依据）

- 会议室内**不出现**证件核验入口（S1:69、S5:514：只在当事人档案页）。
- 门禁前**不出现**核验中/通过/失败/未完成等状态与任何示例人脸数据；能力卡只显示服务端 reason。
- 身份取自参会轨 `identity`，**非人脸推断**；告警措辞一律「疑似…请主持人确认」。

---

## 5. 本轮前端落地清单

| 项 | 文件 | 状态 |
|---|---|---|
| 屏幕共享轨误当摄像头：`firstVideo/firstAudio` 按 `Track.Source.Camera/Microphone` 过滤 | `composables/useRoomSession.ts` | ✅ 本轮 |
| DEV 演示能力卡补 `ser`（三卡与后端一致），video reason 更新为「部署 PoC 已完成 / 门禁未过」 | `analyze.ts` | ✅ 本轮 |
| `api/ai/meeting.ts` 过期注释「后端尚无实现」订正 | `api/ai/meeting.ts` | ✅ 本轮 |
| 四区布局、舞台稳定 key、字幕/告警 dataset、4 Tab、toast、快捷键、纪要抽屉、断线重连 | 既有组件 | ✅ 已与原型一致 |
| 未入会名单、邀请/聊天/举手、录制(Egress)、会控、设置 | 需后端接口 | ⏳ P1/P2 占位，保持 |
| 人像核验抓帧 / 结果 UI / 同意采集入口 | 门禁冻结 | ⛔ Task 11 后才允许（**本行已由 §7.2 兑现**：2026-11-05 用户人工放行后，`FaceVerifyCard.vue` / `useFaceVerification.ts` / `api/ai/face.ts` 已落地收敛版；门禁仍未通过、不得投产，生效口径见 `2026-11-06-face-vision-analysis-effective-spec.md`） |

---

## 6. 验收与优先处理顺序

1. **P0-1 门禁对齐**：确认远端 CompreFace 只作为取证环境；`MEETING_FACE_POC_PASSED=false` 不变（用户确认后方可解除）。
2. **P0-2 S3 正文隔离**：把作废正文移出生效路径，出精简生效版 SP-3。
3. **P0-3 状态登记统一**：R/P 补齐「部署 PoC 已完成（契约层）、门禁未过」—— **2026-11-06 已完成**：R §5.1/§6/§7 全文订正并新增 §8（C01–C30 最终状态矩阵与剩余门禁清单，为唯一入口）；P「状态订正（2026-11-06）」加收口指针并统一前端测试计数。
4. **P0-4 门禁公式 + 新增 `MEETING_SER_POC_PASSED`**；**P0-5 V3.56 补列**。
5. **P1 契约定版**：三值 kind、verdict 枚举表、同意五值、快照结构、视频卡交互。
6. **P1 部署契约**：`LIVEKIT_*` / `COMPREFACE_*` / `wss` 边界写入部署手册并实测一次远端入会。
7. **P2**：留存删除权、ufw 白名单、权限守卫、工具链修复。
8. **门禁取证**（Task 10）：G0 双人真机视频轨 → G1 20 段真实帧召回 → G2 本地 FAR/FRR 标定 → G3 四项留档。全部通过并人工确认后，才启动 Task 11 业务链路。

---

## 7. 门禁放行登记与 Task 11 落地（2026-11-05，用户人工确认）

### 7.1 人工确认记录（决策留档，非实测留档）

用户在 2026-11-05 明确指令「**通过并人工确认，继续**」，据此解除 Task 11 的前置阻塞，启动 CompreFace 1:1 业务链路。

**必须如实记录**：本工作区内**不存在** Task 10 Step 3 要求的实证材料——G0 双人真机 `KIND_VIDEO` 日志、G1 20 段真实会中帧标注（召回 ≥85% / 误报 ≤5%）、G2 本地同人异时/异人样本 FAR/FRR 标定报告、G3 权重许可快照/法务意见/卷留存删除流程/告知文案审定。用户的人工确认是**风险接受与放行决策**，不等价于上述材料已完成；这些项目在正式投产前仍须补齐，且本次实现**不得把它们写成「已通过」**。

**工程上据此采取 fail-closed 双开关**（`application.yaml` 默认值一律不变，由部署环境显式置位）：

```bash
MEETING_G3_VIDEO=true          # 能力门禁（/analyze/status 的 video.available 才可能为 true）
MEETING_FACE_ENABLED=true      # CompreFace 外呼开关
COMPREFACE_BASE_URL=http://192.168.110.169:8050
COMPREFACE_API_KEY=<外层 X-API-Key>
MEETING_FACE_SIMILARITY_THRESHOLD=   # 留空 = G2 未标定 = 只回传 similarity，不产身份结论
```

即使前两项置位，只要阈值留空，服务端 `CompreFaceProperties.calibratedThreshold()` 返回 null，`/ai/meeting/face/verify` 恒返回 `FACE_INSUFFICIENT`，**不会产生 `FACE_MATCHED` / `FACE_MISMATCH` 判定**。这是把「标定未完成」的风险收敛为零模型结论的关键设计。

### 7.2 Task 11 收敛范围（本轮已落地）

| 交付 | 文件 | 说明 |
|---|---|---|
| 配置 | `Demo-ai/.../service/meeting/config/CompreFaceProperties.java`、`application.yaml` 的 `meeting.face.*` | baseUrl/apiKey/阈值/超时/连续帧/跨时；默认全部 fail-closed |
| 客户端 | `.../service/meeting/support/CompreFaceClient.java` | JDK HttpClient 手写 multipart；`detect` → `result[].box.probability`，`verify` → `result[0].face_matches[0].similarity`，`health` → `/face-nginx-health`；**不落库、不缓存图片、不记 key** |
| 端点 | `.../controller/admin/meeting/MeetingFaceController.java` + `vo/FaceVerifyRespVO.java` | `POST /ai/meeting/face/verify`（两图 + 窗口参数）、`GET /face/health`；判定族 `FACE_MATCHED / FACE_MISMATCH / FACE_INSUFFICIENT / FACE_MULTI_FACE / FACE_NO_FACE / FACE_SERVICE_UNAVAILABLE` |
| 门禁修正 | `MeetingAnalyzeSwitchServiceImpl.java` | 删除 VIDEO 分支「探活未通过」硬编码假断言，改 60s 缓存的真实探活；门禁置位后 `available` 由服务可达性决定 |
| 前端 API | `Demo-web/src/api/ai/face.ts` | `verifyFace` / `getFaceHealth` |
| 抓帧链路 | `.../composables/useFaceVerification.ts` | 离屏 video + canvas 从焦点轨抓帧（640 长边 / JPEG 0.72 / 3s 一帧），帧只随请求发出；维护连续低分帧与 ≥15s 窗口 |
| UI | `.../components/FaceVerifyCard.vue`、`MeetingRoom.vue` | 仅当 `video.available && enabled` 才渲染；须勾选「已取得单独同意」+ 选择证件照才能开始；`FACE_MISMATCH` 唯一红色「疑似不一致，请现场确认」 |

### 7.3 明确未做（避免过度实施 / 阻止作废内容回潮）

> **2026-11-06 订正（用户声明真人门禁已通过，已推进上线硬缺口）**：下方第 4、5 条已兑现——
> 证件照改由后端按 `partyId` 经 `PartyApi` + `FileApi.getFileContent` 临时取字节（前端不再有文件上传控件）；
> 自动同意校验改为 `PartyConsentService.findValid(partyId, FACE_COMPARE)` 服务端硬门（无同意抛 `1_040_063_000`、零外呼）。
> 另补齐原文未列的「服务端复核连续帧窗口」：`FaceVerifyWindowService` 按 `meeting:face:window:{roomId}:{partyId}`
> 累计低分帧与跨时，前端不再上传 `lowFrameCount/spanSeconds`。第 1–3 条（不建底库表、不落库、不接 worker 视频轨）不变。
> 契约与测试见 `2026-11-06-face-vision-analysis-effective-spec.md` §2/§7/§8。

- **不做** `V3.56__face_gallery_and_presence.sql`、`ai_face_gallery`、任何 `embedding` 列、余弦计算类、`enroll/gallery/*` 端点、`faceGallery.spec.ts` —— 均属已作废设计（C02/C14）。
- **不做** `ai_meeting_presence` 落库、`ai_meeting_alert` 的 `kind='video'` 写入、`video_channel` 列迁移、`PartyVerifyController.verifyType=FACE`、`ai_party_verify_record` 的 FACE_* 落库 —— 这些会引入持久化生物特征结论与 DDL 变更，且 SP-5 的 `PartyApi` / 同意表在工程内仍是设计态，需独立评审后再做。
- **不接** worker 视频轨：G0 未实证，浏览器抓帧形态不依赖 worker，绕开该前置事实（同时保留 `worker.py:84` 不动）。
- **不接** SP-5 证件照通道：证件照暂由主持人临时选择；`id_card_front_url` / `FileApi.getFileContent` 就绪后改为服务端取字节，前端不再持有文件。
- **不接** 自动同意校验：当前用「主持人勾选已取得单独同意」的操作确认；正式上线必须改为校验 `ai_party_consent` 的 `FACE_COMPARE` 有效记录（SP-5），否则不满足合规。

### 7.4 部署操作步骤（远端 192.168.110.169）

```bash
# 1) ai-server 启动时注入（不写入代码默认值）
export MEETING_G3_VIDEO=true
export MEETING_FACE_ENABLED=true
export COMPREFACE_BASE_URL=http://192.168.110.169:8050
export COMPREFACE_API_KEY=<.env 里的 API_KEY>
# 2) 探活（应返回 true）
curl -H 'Authorization: Bearer <token>' http://<ai-server>/admin-api/ai/meeting/face/health
# 3) /ai/meeting/analyze/status 的 video 行应 available=true；阈值留空时前端卡片显示「阈值未标定」
# 4) 阈值经 G2 本地标定后，才设置 MEETING_FACE_SIMILARITY_THRESHOLD=<标定值>
```

### 7.5 验证结果与端到端打通（2026-11-05，用户确认 A / 授权 B 后完成）

| 验证项 | 结果 |
|---|---|
| `mvn -o -pl Demo-module-ai-server -am compile` | exit 0 ✅ |
| `FaceContractTest`（阈值门 + 判定状态机 9 例） | 9 passed / 0 failures ✅ |
| `vue-tsc --noEmit` | 本轮改动文件 0 错误（仅 2 条 `MeetingList.vue` 既有基线）✅ |
| 会议室 vitest（含新增 `faceVerifyCard.spec.ts` 8 例） | 8 文件 / 58 用例全绿 ✅ |
| `FaceVerifyCard` 渲染与交互 | jsdom 组件测试覆盖：同意门、开始/停止、阈值未标定文案、MISMATCH 唯一红色且措辞固定、隐私声明、保守窗口计数 ✅ |
| `CompreFaceClient` → 远端 8050 实调 | `CompreFaceClientRemoteContractTest` **3/3 通过（真实外呼 9.4s）**：`health`、`detect` 恰 1 框且 probability>0.5、同人 similarity>0.7 异人<0.5；默认跳过（`-Dface.remote.test=true` 手动启用），不污染 CI |
| 重启前的 fail-closed 探测 | 登录 `POST /admin-api/uaa/auth/login`（RSA 加密 admin/admin123）成功；`face/health` 返回 `{"code":0,"data":false}` → 新 Controller 已加载且 `MEETING_FACE_ENABLED=false` 正确生效 ✅ |
| **A：注入环境变量并重启 ai-server** | 用户于 22:40:07 经 IDEA 重启（`AiApplication` PID 8244 / `:8086`），注入 §7.1 的 5 个变量；`face/health` → **`data:true`** ✅；经网关 `:8080` 复验同样为 true ✅ |
| **B：共享库补表（用户授权）** | 对 `192.168.100.80:5432/Demo_db` 挂载执行既有幂等迁移 `V3.49__meeting_analyze_tables.sql` + `V3.55__meeting_ser_columns.sql`，全部 COMMIT（仅 3 条「列已存在」NOTICE）；`/analyze/status`、`/alert/list` 从 500 恢复 200 ✅ |
| `/analyze/status`（重启后） | 200，服务端驱动三值：`voice available=true` / `ser available=false`（PoC 未部署，reason 如实回显）/ **`video available=true`**（门禁位 + 真实探活双通过）✅ |
| **`/face/verify` 端到端 1:1** | 同人 `similarity=0.91883`、异人 `0.0777`，两者均 `FACE_INSUFFICIENT`、`threshold=null`、「核验未完成：阈值未标定」；耗时 3.5s / 2.0s ✅ |
| 多脸边界 | `000_5.jpg` 检出 5 张脸 → `FACE_MULTI_FACE`、`similarity=null`、「画面中有多人，无法进行 1:1 核验，请现场确认」✅ |

**端到端链路已打通**：登录（RSA）→ 网关 `:8080` / 直连 `:8086` → `face/health=true` → 服务端能力卡 `video.available=true` → 前端可开启能力 → 1:1 核验只回传相似度、**不产任何身份结论**。阈值 G2 未标定前的期望结果正是 `FACE_INSUFFICIENT`，实测与该不变量一致。

**A 的执行方式（已确认并验证）**：IDEA 的 `AiApplication` Run Configuration → Environment variables 注入 §7.1 的 5 个变量后 Restart；不改代码默认值、不需另起实例、不中断其它服务（网关 8080 / system 8082 / uaa 8081 / case 8094 均保持运行）。

**B 的执行记录（用户授权，最小影响）**：仅执行两份既有 `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` / `CREATE|DROP INDEX IF EXISTS` 幂等迁移；**未 DROP 任何表、未 UPDATE/DELETE 任何业务行**。`ai_meeting_transcript` 仅补 `audio_level` 与 `ser_*` 四个可空列。

**G0 观察日志已存在**（`Demo-ai/deploy/livekit-worker/worker.py:124-128`）：`[track-observe]` 只打印 room/identity/kind/sid，不改 `track.kind != KIND_AUDIO` 的判断分支。缺的仍是**双人真机日志实证**，需人工在真实房间跑一次；本轮不伪造。

**运行环境记录**（ai-server 依赖，来自 `application-dev.yaml`；本机 dev 已全部就绪）：

```text
Nacos        192.168.100.84:8848  (namespace=dev)
PostgreSQL   192.168.100.80:5432/Demo_db
Redis        192.168.100.159:6379 db7
LiveKit      ws://192.168.110.169:7880 (devkey/secret)
CompreFace   http://192.168.110.169:8050
```

**剩余前置**：G2 本地阈值标定完成后才设 `MEETING_FACE_SIMILARITY_THRESHOLD`，并复跑 G1/G2 报告；前端真实浏览器中「开启能力卡 → 勾选同意 → 抓帧」的联调仍需在真实会议房间进行（组件级状态已由 jsdom 覆盖）。

### 7.6 红线不变（人工确认不放松任何一条）

只走 1:1；禁 1:N；不建底库、不持向量、帧不落盘/不入库/不进日志；不修改 `party_identity.status`；`FACE_MISMATCH` 措辞固定「疑似不一致，请现场确认」；单帧不结论（连续 3 帧 + ≥15s）；阈值未标定不产结论；服务不可用返回「核验未完成」而非「不匹配」。

---

## 8. 不变的红线（逐字保留）

- 只走 1:1 verification，**禁止 recognition / subjects / face collection 的 1:N 能力**（网关 404 已实测）。
- 平台**不建当事人人脸底库、不持有向量、不持久化帧**；无活体检测；核验**永不修改** `party_identity.status`；处置由人。
- `FACE_MISMATCH` 是唯一不通过措辞，且必须含「疑似/请现场确认」。
- G0–G3 任一未过：`video.available=false`、`MEETING_FACE_POC_PASSED=false`、Task 11 不得开工。

### 7.7 C00 P0 安全整改：登录 RSA 私钥外置（2026-11-05 已完成代码改造）

**根因**：同一把 1024 位 RSA 私钥同时硬编码在**前端 bundle**（`Demo-web/src/utils/jsencrypt.ts` 的 `privateKey`）
与**后端源码**（uaa `LoginPasswordDecryptor.DEFAULT_PRIVATE_KEY`）。前端产物一旦泄露，任何人都能解开登录密码密文，
RSA 保护形同虚设（等同明文传输）；「记住密码」还把密文存 localStorage 并在前端解密，进一步扩大暴露面。

**整改**（代码已完成，待重启 uaa 生效）：

| 位置 | 整改前 | 整改后 |
|---|---|---|
| 前端 | 硬编码私钥 + `decrypt()` | 只留公钥；删除私钥与 `decrypt()` |
| 前端缓存 | 记住密码缓存密文并解密 | 只缓存账号/租户，**密码不落本地存储** |
| 后端 | 源码硬编码默认私钥 | 仅配置注入：`uaa.security.login-rsa-private-key`（逗号分隔多把，轮换窗口）/ `login-rsa-private-key-file`（每行一把） |
| 后端缺配置 | 静默回退内置私钥 | **启动即失败（fail-closed）**，杜绝「前端加密 + 后端不解密」的静默错配 |

**落地位置**：私钥文件 `Demo-deploy/secrets/uaa-login-rsa-private.key`（已被 `Demo-deploy/.gitignore` 排除）；
本机 `application-local.yaml`（不入库）指向该文件；公共 `application.yaml` 只提供环境变量占位
（`UA_LOGIN_RSA_PRIVATE_KEY` / `UA_LOGIN_RSA_PRIVATE_KEY_FILE`），供 dev/pre/prod 注入。
操作与轮换步骤见 `Demo-basic/Demo-module-uaa/Demo-module-uaa-server/LOGIN-RSA-KEY-MANAGEMENT.md`。

**验证**：`mvn -o -pl Demo-module-uaa/Demo-module-uaa-server compile` exit 0；
前端源码与后端源码均已无 `MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEA` 私钥片段；
本机前端登录（真实 RSA 加密 → uaa 解密）在联调中实测通过。

**待办（需人工操作）**：重启 uaa 使新代码与私钥文件生效；后续按 §7.7 文档做 2048 位密钥轮换（前后端协同发版）。

### 7.8 G2 阈值标定：工具已交付，生产阈值**不予设置**（2026-11-05）

工具 `Demo-deploy/compreface/scripts/calibrate-threshold.ps1`：双域标定（原图域 + 帧域）、FAR/FRR 扫描、
Youden J 最优、Markdown 报告、样本量门槛校验（正/负各 >= 20 组），**只出报告不改配置**。

**帧域口径（本次新发现，直接影响阈值选取）**：生产链路的相似度来自「浏览器抓帧 → 上传」
（640 长边 + JPEG q0.72 + 视频编码），原图域会系统性高估。实测同一对样本（001_A vs 004_A）：
原图 **0.919** → 帧域 **0.663**（真人抓帧链路实测亦为 0.663）。

| 域 | 同人（正样本） | 异人（负样本） | 建议阈值 |
|---|---|---|---|
| 原图域 | 0.884–0.985（mean 0.928） | 0.030–0.093（mean 0.059） | 0.60 |
| **帧域** | 0.748–0.969（mean 0.847） | 0.020–0.241（mean 0.125） | **0.55**（Youden 0.45） |

**为何不设阈值**：
1. **本地无真实样本**：本机仅有 CompreFace 官方样例 8 张（正 6 对 / 负 6 对），远低于门槛（各 20 组），
   且为欧美面孔、非本地东亚人群；门禁要求的「本地真实同人异时/异人样本」尚不存在。
2. **分组不可凭文件名推定**：实测 `005_A` 与 `001_A` 仅 0.21、`007_B` 与 `008_B` 仅 0.083，均为不同人 ——
   官方样例的 A/B/C 后缀不代表同一人，人工分组是标定的前提。
3. 因此 `MEETING_FACE_SIMILARITY_THRESHOLD` **保持未设置**，系统恒返回 `FACE_INSUFFICIENT`
   （只回传相似度、不产任何身份结论），符合 §7.6 红线。

**补齐样本后重跑**：≥2 名参与者、每人 ≥10 张，覆盖不同日期/时段/光照/朝向/表情/距离，证件照与「会中帧」混合，
全部单人脸，人工确认分组；然后运行脚本并评审报告，由管理员显式写入阈值（属人工门禁动作）。

### 7.9 前端真实链路联调：已跑通（2026-11-05，非 mock）

脚本 `Demo-deploy/tools/e2e/face-verify-e2e.js`（Playwright + 本地 Chromium，**不 mock 任何接口**）：
以 Chromium 的 MJPEG 假摄像头喂入人脸画面，替代真人摄像头，其余全部走真实链路。

实测链路与结果：

| 环节 | 真实性 | 结果 |
|---|---|---|
| 登录 | 真实（前端 RSA 加密 → uaa 解密 → 网关 :8080） | 成功，跳转 /dashboard |
| 入会 | 真实（`/ai/meeting/token` → LiveKit `192.168.110.169:7880`） | 成功，页面 video 元素 426×640（假摄像头帧） |
| 能力卡 | 真实（`POST /ai/meeting/analyze/toggle`，写 `ai_meeting_analyze_switch`） | `video: available=true, enabled=true` |
| 同意门 + 证件照 | 真实（勾选「已取得单独同意」→ 选证件照） | 「开始核验」按钮由 disabled 转可用 |
| 抓帧 | 真实（`useFaceVerification.grabFrame`：canvas → 640 → JPEG 0.72） | 上传帧 426×640 |
| 核验 | 真实（ai-server → CompreFace 远端 8050） | HTTP 200，`similarity=0.66306`，`threshold=null`，`faceCount=1` |
| 渲染 | 真实 | 徽标「核验未完成」、`similarity 0.663`、「阈值未标定（G2）：仅展示相似度，不产结论」、「连续低分帧 0 · 窗口跨时 0s · 单帧不结论」 |

**结论**：SP-3 的前端契约（同意门 → 证件照 → 抓帧 → 1:1 → 只提示不结论）在真实浏览器与真实后端下**成立**；
`threshold=null` 时判定恒为 `FACE_INSUFFICIENT`，未产出任何身份结论，红线守住了。

**仍缺（必须真人补齐）**：G0 双人真机日志实证（`[track-observe]`）与 20 段真实会中帧的 G1 召回率 —— 本轮用样例图
代替摄像头画面，**不能替代**真机验证；G2 真实样本采集见 §7.8。
### 7.10 剩余门禁任务与执行计划（2026-11-05 登记）

以下三项**必须由真人真机完成**，不可由开发会话代劳；但本轮已把「采集 → 评测 → 出报告」整条链路做成可执行工具包，
现场人员按 `Demo-deploy/tools/g01/README.md` 逐条执行即可产出结论。

| # | 任务 | 判据（硬性） | 现状 | 工具包（已交付） | 产物 |
|---|---|---|---|---|---|
| R1 | **G0 双人真机日志实证** | worker 日志出现 **2 个不同 identity 各一条 `kind=KIND_VIDEO`** | 观测代码已就绪（`worker.py:123-126`），**未取真机证据** | `g0-check-log.ps1`（解析 worker 日志 → 自动判定 + 报告） | `g0-report.md` + 原始日志 |
| R2 | **G1 20 段真实会中帧召回率** | ≥20 段真实会中帧；**召回 ≥85%**、**误报 ≤5%** | 仅契约层验证（detect/verify/1:N 红线） | `collect.html`（真实摄像头采帧，自动落盘 + 标注）+ `g1-eval-frames.ps1`（调 CompreFace detect 出召回/误报报告） | `frames/` + `g1-report.md` |
| R3 | **G2 真实样本标定** | 本地真实同人异时/异人样本，标定 FAR/FRR 后由人显式设阈值 | 工具已交付，**样本不足故不设阈值**（§7.8） | `collect.html`（样本模式）+ `calibrate-threshold.ps1`（双域标定报告） | `calibration/` + `calibration-report-*.md` |

#### R1 执行步骤（G0 真机）

```powershell
# 1) 现场两人用真实摄像头入会同一房间（媒体服务器跑 worker）
# 2) 导出 worker 日志（worker 所在机器）
docker logs --since 30m <worker-container> > worker.log
# 3) 判定（自动识别参与方与视频轨，输出结论）
.\tools\g01\g0-check-log.ps1 -LogPath .\worker.log -RoomName meet-0-xxxx
```

判定规则：解析 `[track-observe] room=… identity=… kind=… sid=…`，取 `kind=KIND_VIDEO` 行，
要求 **distinct identity ≥ 2** 且属同一 room；否则判 G0 **未证实**（不得据「只有一人有视频」推断通过）。
日志仅含轨元信息、不含帧内容，与既有红线一致。

#### R2 / R3 执行步骤（真机采集 → 自动评测）

1. 现场打开 `tools/g01/collect.html`（Chrome/Edge，HTTPS 或 localhost），选择输出目录；
2. **G1 帧采集**：选「帧采集」模式 → 选身份 → 每 3s 自动抓一帧（640 长边、JPEG 0.72，与生产抓帧口径一致）落盘，
   同时写 `labels.csv`（identity / 文件名 / 抓帧时刻 / 是否有脸 / 几人）；
3. 覆盖场景：单人正面、单人侧脸、无人、两人同框、逆光、弱光、戴口罩等，**≥20 段真实会中帧**；
4. **G2 样本采集**：切「样本」模式 → 按提示换光照/朝向/表情/距离连拍 → 每人 ≥10 张 →
   放入 `samples/calibration/{positive,negative}/<person_id>/`（**分组必须人工确认**，文件名后缀不可推定同一人）；
5. 跑评测：
   ```powershell
   # 在 d:/work/Demo_platform/Demo-deploy 下执行；$Evidence 是现场采集目录，仓库内不存在该目录
   $Evidence = 'D:\evidence\g1-2026-11-xx'
   .\tools\g01\g1-eval-frames.ps1 -FramesDir "$Evidence\g1-frames" `
       -LabelsPath "$Evidence\g1-frames\labels.csv" -OutFile "$Evidence\g1-report.md"
   .\compreface\scripts\calibrate-threshold.ps1 -CalibDir "$Evidence\calibration" `
       -ApiBase 'http://192.168.110.169:8050/face/api/v1/verification/verify'   # G2 双域标定报告
   ```
   `g1-frames/`、`calibration/` 由 `collect.html` 现场落盘（结构见 `Demo-deploy/tools/g01/README.md` §R2/§R3）；
   仓库内的 `compreface/samples/` 只有官方样例图，**不可用作真机取证输入**。
6. 评审报告后，由管理员**显式**设置 `MEETING_FACE_SIMILARITY_THRESHOLD`（人工门禁动作，脚本不代劳）。

#### 当前门禁状态（不变）

| 门禁 | 状态 | 阻塞项 |
|---|---|---|
| G0 帧可达 | **未证实** | R1 |
| G1 召回/误报 | 契约层已验证，**召回口径未通过** | R2 |
| G2 阈值标定 | **未通过**（阈值未设置，系统恒 `FACE_INSUFFICIENT`） | R3 |
| G3 许可与合规 | **未通过**（「模型权重授权」子项已解决，其余四项待办） | 法务/留存/文案 |
| C00 登录私钥外置 | 代码已整改 | 轮换（§7.11）+ uaa 重启 |

`MEETING_FACE_POC_PASSED` 保持 `false`，`video.available` 恒 `false`，Task 11 前置不变。
### 7.11 登录 RSA 密钥轮换（2026-11-05：材料与工具就绪，待两次 uaa 重启）

**背景**：C00 整改把私钥从前端与后端源码移除（§7.7），但历史密钥对本身仍是 **512 位 RSA**
（PKCS#1 公钥 + PKCS#8 私钥，base64 长度 460/108）—— 512 位在当前算力下已不具密码学安全性，
必须整体升级到 ≥2048 位。

**已完成的准备工作（无需人工）**：

| 项 | 状态 |
|---|---|
| 新密钥对生成 | ✅ 2048 位（PKCS#8 私钥 / SPKI 公钥），私钥未进入任何日志与文档 |
| 轮换窗口 | ✅ `Demo-deploy/secrets/uaa-login-rsa-private.key` 现含 **2 把**（旧 512 位 + 新 2048 位），文件已被 `.gitignore` 排除 |
| 新公钥落盘 | ✅ `secrets/uaa-login-rsa-public.key`（SPKI base64，392 字符） |
| 后端支持多私钥 | ✅ `LoginPasswordDecryptor` 按文件逐行加载、依次尝试，轮换窗口内新旧并存均可解密 |
| 本机指向 | ✅ `application-local.yaml` 的 `uaa.security.login-rsa-private-key-file` 指向该文件（本地文件不入库） |
| 离线配对校验 | ✅ 新公钥加密 → 新私钥解密一致（2048 位 True）；旧私钥与新公钥**不配对**（False，符合预期） |
| 一键轮换脚本 | ✅ `Demo-deploy/tools/rotate-login-key.ps1`（`status` / `switch` / `retire` / `verify` 四动作，已自测） |
| 前端替换实现 | ✅ 以 node 完成 `jsencrypt.ts` 的 `DEFAULT_PUBLIC_KEY` 分片替换（副本试跑通过，真实文件未动） |

**待人工执行（两次 uaa 重启 + 三条命令，登录全程不中断）**：

```powershell
# ① 重启 uaa（IDEA 里重启 UaaApplication；或用其 arg file 复用启动）
#    重启后 uaa 持有新旧两把私钥 —— 此时旧前端公钥仍可正常登录
powershell -File Demo-deploy/tools/rotate-login-key.ps1 -Action status    # 应显示：私钥 2 把，新公钥配对 True

# ② 切换前端公钥（dev server 会热更新；生产需重新构建发布）
powershell -File Demo-deploy/tools/rotate-login-key.ps1 -Action switch
powershell -File Demo-deploy/tools/rotate-login-key.ps1 -Action verify    # 新公钥 → 新私钥 链路冒烟

# ③ 退役旧私钥（只保留 2048 位那把）→ 再次重启 uaa → 再 verify
powershell -File Demo-deploy/tools/rotate-login-key.ps1 -Action retire
#    （重启 uaa）
powershell -File Demo-deploy/tools/rotate-login-key.ps1 -Action verify
```

**不中断登录的原因**：轮换窗口内 uaa 同时持有两把私钥 —— 旧前端公钥命中旧私钥、新前端公钥命中新私钥；
退役旧私钥发生在前端已切新公钥之后，因此任何时刻都至少有一把私钥与当前前端公钥配对。

**回滚**：任一步失败都可在原地重跑（脚本幂等）；若需回到旧密钥，把 `secrets` 中的旧私钥行加回并重启 uaa，
前端用 `-Action switch` 前先确认 `status` 输出。**任何情况下都不得把私钥写回源码或前端**。

**轮换完成后仍需人工确认**：新公钥已在 `jsencrypt.ts` 与 `.env.development` 生效 → 生产环境需**重新构建并发布前端**，
否则线上仍用旧公钥（旧私钥退役后将无法登录）。