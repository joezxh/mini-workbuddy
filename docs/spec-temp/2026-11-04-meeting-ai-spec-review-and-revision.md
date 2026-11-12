# AI 视频会议 Spec 评审与修订方案（CompreFace 版）

- 日期：2026-11-04
- 评审对象：`2026-11-04-meeting-room-ui-design.md`（SP-1/SP-2）、`2026-11-04-face-vision-analysis-design.md`（SP-3）、`2026-11-04-party-identity-verification-design.md`（SP-5）、`2026-11-04-acoustic-ser-design.md`（SP-4），上游 `2026-11-03-meeting-ai-capability-design.md`
- 对照基线：`Demo-web/prototype/meeting-room.html`（925 行，已评审原型）、`Demo-web/src/views/ai/meeting/MeetingRoom.vue` 及 8 个子组件、当前工程实读代码
- 用户裁决（本方案约束来源）：**Q1** 人脸识别改用 CompreFace，本轮做「设计 + 部署件」，**不接业务链路**；**Q2** AI 分析面板「真实接口优先 + DEV 演示兜底」；**Q3** 视觉**按原型绿 `#00A870`**，会议模块局部覆盖，全局主题变量不动；**Q4** 新增本评审方案 + 对四份 spec 做**最小必要订正**，保留 qwen3.8 原文主体。
- 本方案不修改后端 Java 业务代码、网关配置、livekit-worker、共享数据库与原型文件。
- **状态总订正（2026-11-06）**：本文 §1「事实基线」是 **2026-11-04 读码时点快照**，不是当前工程状态；§5/§6/§7 的 2026-11-05 首轮登记亦已被后续实测与实施推翻。本轮已按 §8 把 30 项冲突的剩余开发任务收口、就地订正过时事实并统一状态登记；**§8 是「尚未完成的任务」的唯一入口**，所有门禁结论以 `2026-11-06-face-vision-analysis-effective-spec.md` §9 为准。

---

## 0. 结论摘要

四份 spec 的**读码类事实断言绝大部分属实**（双前缀缺陷、`MediaAnalysisServiceImpl` 伪能力、`TranscriptSegmentVO` 四字段、worker 未联调、错误码/迁移号/菜单号段、`PartyIdentityController` 明文返回 DO），设计思路（服务端权威开关、一级门控成本、告警「疑似」措辞、生物特征最小化）整体可取，四份之间通过 §0 差异登记建立了可追溯关系。

但存在四类必须处理的问题：

| 类别 | 数量 | 性质 |
|---|---|---|
| **A. 阻断落地的事实误判** | 6 项 | 把「设计态」写成「已就绪/已部署/已实测」，或把「不存在」写成「已具备」；照此实施第一步就失败 |
| **B. 四份 spec 互相冲突** | 7 项 | 同一端点/枚举/开关/不变量被反复改写，前后端都无稳定契约可定版 |
| **C. 与原型或现有工程不一致** | 12 项 | 视觉、分期语义、组件契约、数据链路、权限 API、测试基线 |
| **D. 合规与隐私缺口** | 4 项 | 三套同意口径、生物特征留存边界、明文敏感字段、留存期未定 |

**最高优先级不是「补功能」，而是先统一定版契约**（§3）：否则前端每接一个后端能力都要返工。本轮交付把契约定版后，用 `AnalyzeSource` 适配层让 UI 与后端解耦，后端就绪即零改切换。

**关键提醒（CompreFace 授权）**：用户以「insightface 无商用授权」为由改选 CompreFace。CompreFace **平台代码**为 Apache-2.0，但公开资料显示其内置模型仍含 FaceNet / SubCenter-ArcFace（InsightFace 系）等，权重许可需独立核实。因此 **G3 门禁不得删除**，必须改写为「按所选 CompreFace 具体模型核实权重商用许可 + 法务留档」，不得写成「授权问题已解决」。详见 §4.4。**2026-11-05 修订**：部署权重改用可商用开源组合 YuNet + SFace（选型与三层许可核实见 SP-3 总纲 D-2 与本文 §4.4），据此**仅「模型权重授权」子项已解决**；G3 整体仍为未通过，其余四项待办与 `MEETING_FACE_POC_PASSED=false` 不变，禁止把子项结论扩大为整体授权已解决。

---

## 1. 事实基线（读码核验，非 spec 转述）

| # | 事实 | 证据 |
|---|---|---|
| F1 | `MeetingTranscriptInternalController` 类级 `/admin-api/ai/meeting/internal` 且包名 `**.controller.admin.meeting`；框架 `WebProperties.java:22` `new Api("/admin-api","**.controller.admin.**")` + `TianqueWebAutoConfiguration.java:46-55,71-77` 追加前缀 → 实际注册 **`/admin-api/admin-api/ai/meeting/internal/transcript`**；worker 推单前缀，网关 `Path=/admin-api/ai/**` 无 StripPrefix，`WhiteListConfig` 不含内部路径 → 转录回推当前不通 | 三仓实读 |
| F2 | `MeetingTranscriptServiceImpl` SSE 事件名 `transcript`，data 为整个 `MeetingTranscriptDO`，自管理 `ConcurrentHashMap`；`TranscriptSegmentVO` 仅 `speakerIdentity/text/startTs/endTs`；worker `END_OF_SPEECH` 时整段 PCM 在手，`:84` 丢弃非音频轨，`README.md:54-59` 自陈「未运行联调」 | 实读 |
| F3 | `util/ai/SseEmitterPool.java` **实际存在**且被 chat 模块使用；`MeetingTranscriptServiceImpl.java:28` 注释「本仓无 SseEmitterPool 组件」不实；上游 11-03 spec 声称会议字幕复用 SseEmitterPool 亦不成立 | 实读 |
| F4 | 以下对象在 `*.{java,sql,xml,py,yaml,yml,json,properties,ts,vue,js}` 中**零命中**，全部为设计态：`MeetingAnalyzeController/Service`、`MeetingAlertDO`、`MeetingAnalyzeSwitchDO`、`ai_meeting_alert`、`ai_meeting_analyze_switch`、`ai_party_verify_record`、`ai_party_consent`、`PartyApi`、`PartyIdentityForVerifyRespDTO`、`FaceGalleryDO`、`MeetingPresenceDO`、`ai_face_gallery`、`ser_provider.py`、`face_provider.py`；以及 `/ai/meeting/analyze/{status,toggle,cost}`、`/ai/meeting/alert/{list,ack}`、`/ai/party/verify/idcard`、`/ai/meeting/internal/analyze/switch`、`/ai/meeting/internal/face-event`；配置块 `meeting.analyze.*`/`meeting.ser.*`/`meeting.face.*`/`party.verify.*` | 全仓精确检索 |
| F5 | 错误码已用 `1_040_061_000~004`、`1_040_062_000~006`；`Demo-ai/docs/sql` 最新 **V3.48**，无 V3.49+；菜单 9490-9494（V3.46）、9495-9498（V3.47）已占，9499+ 空闲 | 实读 |
| F6 | `MediaAnalysisServiceImpl` 情感/STT/图像/视频全为硬编码 mock，`getCapabilities()` 四项全 `true`；`PaddleOcrClient`/`OcrEngine*` 真实存在且有测试；`PartyIdentityController.page` 直接返回 `PartyIdentityDO`（含完整身份证号与证件照 URL） | 实读 |
| F7 | `Demo-deploy/paddle/` 有完整部署范式；`Demo-deploy/ser/`、`face/`、`compreface/` **均不存在**；仓库只能证明 OCR 配置指向 `192.168.40.30:8080` 与部署件存在，**无运行/联调证据** | 目录列举 |
| F8 | 前端会议目录仅 8 个流式布局组件 + 2 个 spec；无 `composables/`、`analyze.ts`、四区组件；`livekit-client@2.23` 已具备屏幕共享与 `ConnectionQuality` API，但 `src` 内 `createScreenVideoTrack/publishTrack/startAudio/ConnectionQuality/getDisplayMedia` **零命中** | 实读 |
| F9 | 前端权限判断实际为 `accessStore.hasAccess(code)`，**无 `hasPermission`**；`request.ts` 导出 `get/post/put/del/upload/download/postSSE`，**无 `patch`、删除叫 `del`**；`vitest.config.ts` `environment:'jsdom'`、`include:['src/**/__tests__/**/*.spec.ts',...]` | 实读 |
| F10 | 列表页跳会议室只传 `{roomId, identity}`，无 title/caseCode/role；`getRoom` 已定义但会议目录从未调用；`MeetingRoom` 类型只有数字 `caseId`，无Case编号字符串 | `MeetingList.vue:100-103,114`、`api/ai/meeting.ts` |
| F11 | 原型 `meeting-room.html` 被 `.gitignore:55 /prototype/` 忽略；全仓无原型 jsdom 断言脚本；spec §10.3「79 断言全绿」**不可复现、不在仓库**；vitest include 也不收集 prototype 目录 | 实读 |
| F12 | `variables.css` 注释为中文乱码，仅 `main.ts:13` import；`index.scss:3` 要求颜色/阴影/圆角引用变量；会议目录 `var(--)` **零命中** | 实读 |
| F13 | `RemoteTile.vue:22-25` 的「无画面时把音频挂到同一元素」分支不可达（`<video v-if>` 元素不存在），`onBeforeUnmount` 才 detach audio → **远端参会者听不到声音**，属真实必修缺陷 | 实读 |

> **时点声明（2026-11-06）**：以上 F1–F13 是 2026-11-04 评审当天的读码结论，用于解释「当时为什么必须修」，**不得当作当前工程状态引用**。已被后续实施推翻的主要项：F1 双前缀已修（`@RequestMapping("/ai/meeting/internal")` + MVC 注册路径回归）；F2 的 VO 已扩可空字段（但仍只发 final `transcript`）；F3 的注释已改为「不复用 chat 模块的 SseEmitterPool」，11-03 上游表述已订正；F4 中 `MeetingAnalyzeController`、`MeetingAlertDO`、`MeetingAnalyzeSwitchDO`、三张表、`PartyApi`/DTO、`ser_provider.py`、四个配置块、5 个分析端点均已落地（仍零命中的只剩 `FaceGalleryDO`、`MeetingPresenceDO`、`ai_face_gallery`、`face_provider.py`、`/internal/face-event` 等作废项）；F5 迁移已到 `V3.55`、错误码已用 `061_005–007`/`063_*`/`064_*`；F6 `PartyIdentityController.page` 已脱敏、`MediaAnalysisServiceImpl` 伪能力已按 C30 移除；F7 `deploy/ser` 与 `deploy/compreface` 已存在、CompreFace 已部署且 `verify.ps1` 9/9；F8 会议目录已有 8 个 vitest spec + composables + 四区组件；F10 `getRoom` 已被 `useRoomSession` 调用；F12 已有会议局部 `meeting.css` token；F13 音视频元素已分离。**仍属实的只有 F9（无 `hasPermission`、无 `patch`）与 F11（原型断言脚本不在仓库，已改由 8 个 vitest spec 作为替代证据）**。

---

## 2. 冲突点 / 影响范围 / 优化建议 / 优先处理顺序

优先级定义：**P0-1** 阻断真实链路、必须最先修；**P0-2** 本轮前端一致性交付必须解决；**P1-1** 契约定版（后端实施前必须统一）；**P1-2** 合规与隐私；**P2** 分期能力上线前处理。

### 2.1 P0-1 阻断真实链路（3 项）

| # | 冲突点 | 影响范围 | 优化建议 | 优先顺序 |
|---|---|---|---|---|
| C01 | **双前缀缺陷**（F1）：spec SP-1/2 §0.4 已发现，但要等「SP-1/2 实施」才修 | 转录回推 100% 失败且 worker 只 `print` 异常，字幕、SP-2 分析、告警全链路无从验收；现有会议功能即已受损 | 保持包位置不变，`@RequestMapping` 字面量改 `/ai/meeting/internal`，javadoc 同步改写；worker 与网关不动；补 `@SpringBootTest` 回归锁断言不存在 `/admin-api/admin-api/` 路径 | **1** |
| C02 | **远端音频不可闻**（F13） | 双人真机入会「看得见画面、听不到人声」，是视频会议基础功能缺陷，优先级高于任何 AI 能力 | `RemoteTile` 音视频元素分离：`<audio>` 始终渲染、不带 `muted`、attach `audioTrack`；`<video muted>` 只管画面；保留 `flush:'post'` 与无参 `detach()`；实施时核实 livekit-client 2.23 是否也自动 attach（避免双音），必要时补 `room.startAudio()` 用户手势；扩展 `tileAttach.spec.ts` 而非替换现有 3 例 | **2** |
| C03 | **入会 grant `roomJoin`**：spec SP-1/2 §11 记「已修代码，需重启 `AiApplication` 才生效」 | 未重启时入会必报 `permissions denied`，用户会误判为网络/证书问题 | 保留 `describeConnectFailure()` 五层分类文案（尤其 `permissions denied → 缺 roomJoin`）；实施首日解 JWT 校验 `grants.video.roomJoin === true` | **3** |

> 2026-11-06 收口：C01 已修（Controller 映射改为 `/ai/meeting/internal`，并补 `MeetingTranscriptInternalMvcMappingTest` 的 Spring MVC 真实注册路径断言，见 §8）；C02 已落实；C03 的 `roomJoin` grant 已写入 `MeetingTokenServiceImpl` 并有单测，真实登录 → 入会的 E2E 也已跑通（`Demo-deploy/tools/e2e/face-verify-e2e.js`）。本表「待实施」措辞属 2026-11-04 时点结论，当前仅剩环境重启/密钥注入等运维动作。

### 2.2 P0-2 与原型或现有实现不一致（12 项）

| # | 冲突点 | 影响范围 | 优化建议 | 优先顺序 |
|---|---|---|---|---|
| C04 | **主色被擅自改掉**：原型 `--accent:#00a870`，spec SP-1/2 §3.7 判给主题 `--accent-cyan:#1A5FB4`，并写进 §9「三处有意差异③」与 §12 自检 | 与用户「与原型效果一致」直接冲突；说话高亮、Tab 下划线、开关、chip、P1 角标全部变色 | 按裁决 Q3：新增 `--meeting-accent:#00A870` 及会议专有 token，**作用域限定会议根容器**（新文件 `meeting.css`），全局 `variables.css` 既有取值一个不动；订正 spec §3.7/§9/§12 | **4** |
| C05 | **spec §3.7 行号与色值引用错误**：把 `.know` 底色写成 `#f6fff9` 并标 `:233`（实为 `.acard[data-on=1]` 背景；`.know` 在 `:230` 为 `#eaf2ff`）；「P1 角标底/字」标 `:136`/`:115`（实为 banner 底色与 tile focus 描边；P1 角标在 `:218`） | 按错误行号取色会导致知情条、分期角标视觉与原型不符 | 以原型实读行号订正：`.know` → `#eaf2ff` + `border #bedaff`；P1 → `#eaf2ff/#4080ff`；P2 → `#fff3e8/#ff7d00`；`--meeting-hit` 取 `#fffbe6` 派生 | **4** |
| C06 | **视频卡能力语义被三度改写**：原型 `SVC.video.ds` 是「激烈争执、多人站立对峙、遮挡镜头、离席」等行为理解；SP-3 §1.2 明确「行为一项都不做，只做到场一致性」；本轮又换 CompreFace 1:1 比对 | 卡片文案、`.err` 不可用原因、`SP-3 · P1` 角标、会议信息 Tab 状态行全部失真 | 重写视频卡为「人像到场一致性核验（CompreFace 1:1）」，`available=false` 时 `.err` 显示真实原因（服务未部署/门禁未过/无同意）；在本文档显式登记「原型=行为理解示意，真实能力=1:1 到场一致性」为**有意差异**及原因 | **5** |
| C07 | **spec 自行引入 `focusPinned`**：SP-1/2 §3.1 写「手动点击 tile 可钉住，有人说话不抢回」+ 钉徽标；原型只有点击切 `st.focus`，无钉住态 | 交互流程与原型不一致，且增加未定义的抢焦点规则与状态 | 删除 `focusPinned`，按原型实现「点击即切换焦点」；钉住列为 P1 可选增强并标注需原型同步 | **5** |
| C08 | **partial 字幕链路缺失**：原型 `push(id,who,text,partial)` 做 partial→final 覆盖 + `.tr[data-partial]::after` 光标；真实 SSE 只有 final `transcript`，`TranscriptSegmentVO` 无 `partial`/`seq` | 转录 Tab 与舞台叠加条的「正在讲话/淡出/光标」状态无法与原型一致 | 定版 SSE 可选扩展事件 `partial`（旧后端不发送时按定稿降级渲染，不报错）；`captions.ts` 增按 id 合并的纯函数；未知事件一律忽略保证向后兼容 | **6** |
| C09 | **名单/角色/Case号无数据链**：原型 5 人含主持人/申请人/被申请人/系统轨、未入会分组、角色 chip、呼叫；现有 `issueToken/getRoom/pageRooms` 无参与者名单/角色/未入会名单，`MeetingRoomRespVO` 只有数字 `caseId`；spec `MeetingTopBar` props 要 `title, caseCode` | 顶栏空白、成员 Tab 无法分组、搜索与 chip 无数据；spec §3.1 分组设计不可实现 | 调用**已定义但从未使用**的 `getRoom(roomId)` 补标题与Case号（显示 `Case #caseId`，**不虚构Case编号字符串**）；成员以真实已入会 `speakers` 渲染，未入会分组在无名单接口时显示明确空态「暂无法获取未入会名单（需后端名单接口）」；角色由 `isLocal`/identity 推导最小标签，不伪造业务角色；搜索沿用原型 `roleHit` **按词匹配**（因「被申请人」包含「申请人」） | **6** |
| C10 | **连接质量/计时无来源**：原型 `mQ` 随机 mock、`mClock` 从本地 `started`；spec 未定义 `ConnectionQuality` 事件与计时基准；`MeetingStatus` 组件去向未在 §3.2 契约中交代 | 顶栏两项状态不确定，spec 组件表无法落地 | 质量由 `RoomEvent.ConnectionQualityChanged` 驱动（livekit-client 2.23 已具备），无事件时降级为「未知」；计时以本地入会时刻为基准并注明与房间 `startTime` 的口径差异；`MeetingStatus` 融入 `MeetingTopBar`，保留四态文案 | **7** |
| C11 | **纪要/结束按钮未接线**：原型 `btnMinutes`/`btnEnd` 仅 `toast`；现有实现有 `MinutesDrawer`（草稿→确认→回写）与 `genMinutes()`（endRoom + disconnect + 开抽屉）；spec §3.2 控制条 15 项未定义接线 | 真实能力被原型 mock 覆盖会造成功能倒退 | 以真实实现为准：`btnMinutes` 打开 `MinutesDrawer`，`btnEnd` 走二次确认 + `genMinutes`；登记为「有意差异（原型仅 toast 占位）」 | **7** |
| C12 | **Esc 快捷键**：原型 legend 写「Esc 退全屏」但代码无监听；spec §3.4 声称「与原型 legend 一致」 | 文案与行为不符 | 实现侧补 `Esc` 退出全屏（保留浏览器原生行为兜底）；本次按「补实现」处理 | **8** |
| C13 | **原型自身两处缺陷**：gallery 共享时 `list` 已含 `shareTile` 又额外插一个 `grid-column:1/-1` 共享 tile（重复渲染）；`renderStage` 每次整块 `innerHTML` 重建（与「舞台稳定性」禁令冲突） | 直接照抄会重现共享画面重复与摄像头闪断 | 共享态只插入一路共享 tile；tile 用 `identity` 稳定 key 常驻，说话高亮/字幕/告警只改 `dataset` 与独立浮层；`stageStability.spec.ts` 锁死 DOM 引用不变 | **8** |
| C14 | **原型开关存 localStorage vs spec 服务端权威** | 属合理差异，但演示态若沿用会造成「看起来已开启」的伪能力 | 保留 spec 结论（服务端权威、`localStorage` 只存 `mode/side/tab/cap` 视图偏好）；DEV 演示态必须显式标注「演示数据」，不得伪装成服务端已开启；`import.meta.env.DEV` 包裹、生产剔除 | **9** |
| C15 | **`VideoGrid/CaptionPanel/ParticipantList` 删除后无迁移映射**：spec §3.3 只说「并入/上移」，未交代 `MeetingStatus`、SSE 订阅、现有测试的保护 | 重构易破坏既有 `tileAttach.spec.ts` 3 例与 `captions.ts` 4 个纯函数 | 补完整迁移映射；保留 `captions.ts` 纯函数与既有测试并扩展；SSE 订阅抽 `useCaptionStream`，渲染迁 `TranscriptPanel`；删除前确认三者仅被 `MeetingRoom.vue` 引用 | **9** |

### 2.3 P1-1 四份 spec 互相冲突（7 项）

| # | 冲突点 | 影响范围 | 优化建议 | 优先顺序 |
|---|---|---|---|---|
| C16 | **SP-4 §6.4 自相矛盾**：写「新增 3 个可空字段」却列 `audioLevel/serEmotion/serConfidence/serModel` 4 个，且 `audioLevel` 属 SP-2 而非 SP-4 新增；§3.2 步骤 3 push 体只列 3 个 ser 键 | `TranscriptSegmentVO`/DO 列数、worker 契约、DDL 加列数无法确定 | 订正为「本文新增 3 个：`serEmotion`/`serConfidence`/`serModel`；`audioLevel` 由 SP-2 定义，本文仅复用」；DDL 与 push 体三处统一 | **10** |
| C17 | **SP-1/2 §8 不变量② 处置互斥**：SP-3 §0-T1「作废该不变量（受 G0–G3 门禁约束）」，SP-4 §3.3「`video` 在 SP-3 落地前恒 false（与不变量② 保持一致）」+ §10.1 用例⑭要求快照 `video=false`，SP-3 §6.1 又要求 `video` 由 `false` 常量改为按探活计算 | 同一 `kind=video` 开关在三份 spec 中语义相反；后端判定表与前端卡片状态无定论 | 统一为**单一可关断门禁**：`available = 平台开关 AND 探活成功 AND g3Passed(人工显式置位)`；未通过时 `enabled=false/available=false`、不写开关行、不产该 kind 告警；门禁通过后才允许翻转。三份 spec 统一引用本定义 | **10** |
| C18 | **`AnalyzeStatusRespVO`/`MeetingAlertVO` 被三份 spec 各自扩字段**：卡片数 2(SP-1/2) → 3(SP-4 加 `ser`) → 3(SP-3 翻转 `video` 且加 `videoChannel`)；SP-1/2 §4.1.1 判定表写死 `kind=video → available=false` 不写开关行，SP-3 §6.4 改为 `jailed-by-poc` 但**未给判定表替换行** | 前端无法定版接口类型；后端实现者会按最早那份 spec 写 | 定版**统一契约**（§3）：`kind ∈ voice\|ser\|video` 三值由服务端返回驱动，前端不硬编码卡片数与「恒不可用」；`MeetingAlert` 合并 `serEmotion/serConfidence/serModel/videoChannel` 全部可空；补 §4.1.1 的门禁替换行 | **11** |
| C19 | **同一端点 `/internal/analyze/switch` 快照结构不一致**：SP-4 §3.2 `{voice,ser,video,serPolicy}`，SP-3 §3.2 `{voice,ser,video,serPolicy,facePolicy}` | worker 侧解析会按其中一份写，另一份上线即字段缺失 | 定版为**可扩展快照**：固定 `{voice,ser,video}` + 可选 `serPolicy`/`facePolicy` 策略块；缺失策略块时对应能力 fail-closed；禁止把策略字段当必填 | **11** |
| C20 | **SP-3 自相矛盾的「已就绪」断言**：§0-T2/事实 13/§5.3 称「读码确认 SP-5 的 `PartyIdentityForVerifyRespDTO` 已含 `idCardFrontUrl`、`PartyApi` 已就绪，直接复用」；F4 实测两者**零命中**；同文 §11 又自认「`MeetingAlertDO`、`ai_party_verify_record`、`PartyApi` 均为设计态」 | 照 §5.3 实施会在「复用现成 Feign」处直接失败；也让 SP-5→SP-3 依赖顺序被误判 | 订正为「`PartyApi`/`PartyIdentityForVerifyRespDTO` 为 SP-5 设计态对象，实施顺序 SP-1/2 → SP-5 → SP-4 → SP-3 不可颠倒」；CompreFace 1:1 通路下证件照字节改由核验任务期经 `FileApi` 临时取得，不依赖常态底库 | **12** |
| C21 | **SP-5 与 11-03 的「已部署/已复用」误判**：SP-5 §0-P1/§12 称 PP-OCRv6「已在 192.168.40.30:8080 真实部署」、§12 把 `PartyApi` 列入「均已实读确认存在」（同句末尾又注「提议新增、当前不存在」）；F3/F7 显示只有配置指向与部署件、无联调证据；11-03 声称会议复用 `SseEmitterPool` 亦不成立 | 让「零新部署、现在就能交付」的分期判断过于乐观 | 措辞统一改为「配置指向该地址 + `Demo-deploy/paddle/` 部署件存在，**运行/联调证据缺失**」；`PartyApi` 从「实读存在」清单移除；修正 `MeetingTranscriptServiceImpl` 注释与上游 11-03 的 `SseEmitterPool` 表述（登记为后续小改造） | **12** |
| C22 | **「实测」证据不可复现**：SP-1/2 §0.4 双前缀「实测响应」仓库内无留档（唯一单测只测错误密钥）；§10.3「原型 jsdom 79 断言全绿」脚本不在仓库、被 gitignore 且不在 vitest include（F11） | 验收基线建立在本轮无法验证的产物上 | 双前缀修复补 `@SpringBootTest` 路径断言；原型断言脚本补进 `src/views/ai/meeting/__tests__/`（本轮新增 `analyze/captionStream/stageStability/meetingLayout` 等 spec）；把 §10.3 标注为「外部一次性验证，不可复现，以本轮 vitest 为准」 | **13** |

### 2.4 P1-2 合规与隐私（4 项）

| # | 冲突点 | 影响范围 | 优化建议 | 优先顺序 |
|---|---|---|---|---|
| C23 | **同一面板三套同意口径**：SP-1/2 用 `noticeConfirmed` 布尔 + `AiConfigOperateLog`；SP-4 §9 说复用 `noticeConfirmed`，若走 SP-5 则 `ai_party_consent.scope=SER_ANALYSIS`；SP-3 §9.1 要求 `FACE_COMPARE` **独立单独同意**且不与 `IDCARD_VERIFY` 覆盖；而 SP-5 §7.1 DDL 注释只预留 `FACE_COMPARE`，SP-4 自称已登记「注释级修订」但 SP-5 原文未改 | 触及敏感个人信息与生物识别信息；无法证明「取得过单独同意」，也无法统一撤回语义；最严重的合规缺口 | 定版**单一同意模型**：`ai_party_consent.scope` 枚举统一为 `IDCARD_VERIFY \| FACE_COMPARE \| SER_ANALYSIS \| VOICE_ANALYZE`，`version` 等值、撤回置 `revoked_at`；`noticeConfirmed` 降级为**操作人确认动作**（写审计），不再充当同意凭据；任何能力开启前先查有效同意，无同意零外呼；三份 spec 同步引用 | **14** |
| C24 | **CompreFace 持久化与 SP-3 原隐私硬约束冲突**：原 spec §3.3/§9.4 要求「服务侧 `persistence:false`、不挂任何卷、帧不落盘、向量不入日志」；CompreFace 自带 Postgres 命名卷 | 若走 recognition subject 底库，服务侧会留下生物特征副本，撤回时无法保证清除 | 选 **verification 1:1**（不建 subject、不落业务底库），部署件 README 显式声明：CompreFace 平台自身 Postgres 保存其管理数据（应用/密钥/若启用 recognition 则含人脸），本平台**禁止启用 recognition/subject 能力**；证件照与会中帧仅在核验任务期经内网传输，帧不落盘、不入库、不进日志；卷的留存期、备份加密、删除流程列为 G3 必答项 | **14** |
| C25 | **明文敏感字段与留存期**：SP-3 `ai_face_gallery.embedding` 明文 `REAL[]`（§11 自认移交运维）；SP-5 `PartyApi` 明文身份证号 + `/rpc-api` 是否对外路由未验证；SP-1/2 把转录原文存 `ai_meeting_alert.text_snippet` 并「随纪要留存」但**无留存期/查阅删除权**（SP-4 §11 已登记为跨 spec 缺口）；`paddle.ocr.api-key` 明文默认值入 Git | 二次扩散风险与合规举证缺口 | CompreFace 1:1 架构下**废弃 `ai_face_gallery`**（不再存向量）；`PartyApi` 路径限定 `/rpc-api` 并在网关验证不对外路由；补 `ai_meeting_transcript`/`ai_meeting_alert` 留存期与当事人查阅删除路径（与纪要留存策略合并决策）；`api-key` 改无默认值 + 启动校验 | **15** |
| C26 | **CompreFace 许可认知风险**：若按「insightface 无商用授权 → 换 CompreFace → 授权已解决」写入文档，会形成虚假合规结论 | G3 门禁被误判为通过，带病上线 | 保留 G3，改写为「CompreFace 平台 Apache-2.0；**所选具体模型权重**的商用许可须逐项核实并法务留档；未留档前 `jailed-by-poc=false`」；详见 §4.4。**2026-11-05 修订**：已按用户裁决改用可商用开源权重 YuNet + SFace（选型与三层许可核实见 SP-3 总纲 D-2），**仅「模型权重授权」子项判为已解决**；G3 整体仍未通过，其余四项待办与 `jailed-by-poc=false` 不变，**不得把子项结论扩大为「授权问题已整体解决」** | **15** |

### 2.5 P2 分期能力（4 项，登记但不阻断本轮）

| # | 冲突点 | 影响范围 | 优化建议 | 优先顺序 |
|---|---|---|---|---|
| C27 | **前端工程能力与 spec 不匹配**：spec 用 `hasPermission`（实际 `hasAccess(code)`）；5 个新端点/`event: alert`/2 个权限码全缺失（F4/F9）；`request.ts` 无 `patch`；spec §3.2 要求「组件内零十六进制字面量」但现有 8 个组件全是硬编码色值 | 契约写得再好也无法直接接线 | 前端统一用 `hasAccess`；新增接口只用 `get/post`；会议 token 集中到 `meeting.css`；分析接口经 `AnalyzeSource` 适配层隔离，后端未就绪时 DEV 演示兜底 | **16** |
| C28 | **交付清单不可执行**：四份 spec §13 的 V3.49~V3.57、菜单 9499~9507、deploy/ser、deploy/face、Java 测试类全部设计态；SP-3 §7 已声明「SP-1/2、SP-5 未实现，本文不得先行落地，否则 V3.56 直接失败」 | 排期若按「并行开发」会连环失败 | 实施顺序固定 **SP-1/2 → SP-5 → SP-4 → SP-3**；CompreFace 部署件可并行准备但不得接业务链路；号段分配（错误码/迁移/菜单/端口）保持四份 spec 现有划分，本轮不占用 | **17** |
| C29 | **SP-3 换 CompreFace 的连锁失效清单**：`insightface-svc/{app.py,Dockerfile,requirements.txt,models/buffalo_l}`、`/v1/face/detect\|embed`、`X-Verify-Token` HMAC、`embedding-dim:512`、`normed_embedding`、`FaceSimilarityCalculator`、`ai_face_gallery.embedding REAL[]`、`enroll/gallery/status/gallery/delete`、菜单 9505/9507、`FACE_NO_BASE/FACE_BASE_STALE/FACE_UNSTABLE` 语义、§8.4.1-L1 许可结论、§8.4.9 V1–V6、端口 8030/8031、`persistence:false` 断言、§10.1/§10.4 相关用例与冒烟、§11/§12/§13 交付物 | 不逐项处理会留下大量悬空引用，实施者无法判断哪些还有效 | 见 §4.3「失效-替换对照表」；SP-3 文档以「覆盖性修订总纲」逐章给出替换结论，保留原文主体作为对照 | **17** |
| C30 | **`MediaAnalysisServiceImpl` 伪「情感时间线」已在前端可见**，易被误认为 SP-4 已交付 | 认知风险：评审看到假曲线会误判能力已具备 | 与 SP-4 同期改造：`getCapabilities()` 按真实 provider 探活；四个 mock 方法显式抛 `ServiceException`；本轮前端演示态必须显式标注「演示数据」，绝不复用该假链路 | **18** |

---

## 3. 统一后的分析接口契约（定版，前后端共同依据）

> 后端 5 个端点当前**全部为设计态**（F4）。本节定版的是「契约意图与字段语义」，不是「已实现」。前端按此实现 API 层，后端上线后仅需替换 `AnalyzeSource` 适配器。

### 3.1 契约分层

```
UI（AnalysisPanel / SidePanel / StageView）
   ↓ 只依赖 AnalyzeSource 接口
AnalyzeSource
   ├─ HttpAnalyzeSource   后端就绪后使用（get/post + SSE）
   └─ DemoAnalyzeSource   import.meta.env.DEV 且后端不可用时，原型同款演示数据
```

`AnalyzeSource` 提供：`loadStatus()`、`loadCost()`、`listAlerts()`、`ack(id)` 与 **`toggle(kind, enabled)` 两参**（D2 定版）。`noticeConfirmed` 由前端 `toggleAnalyze` 的 body 固定携带、服务端只写审计；**SSE 订阅归 `useCaptionStream`，`AnalyzeSource` 不新增 `subscribe()`**。UI 不感知数据源；演示态在界面常驻「演示数据」标识，生产构建剔除。

### 3.2 端点（沿用 SP-1/2 §6.1 路径，统一字段）

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/ai/meeting/analyze/status` | GET | `ai:meeting:query` | 返回**能力列表**（不是固定两张卡），由服务端决定条目与顺序 |
| `/ai/meeting/analyze/toggle` | POST | `ai:meeting:analyze` | body `{roomId, kind, enabled, noticeConfirmed}`；返回**实际生效**状态 |
| `/ai/meeting/analyze/cost` | GET | `ai:meeting:query` | `{segCount, models, rules, throttled, rejected}` |
| `/ai/meeting/alert/list` | GET | `ai:meeting:query` | SSE 断线后补齐；支持 `level` / `speakerIdentity` 过滤 |
| `/ai/meeting/alert/ack` | POST | `ai:meeting:alert-ack` | 幂等；不存在返回 `1_040_061_007` |
| `/ai/meeting/transcript/stream` | GET(SSE) | `@PermitAll` | 事件：`transcript` / `alert` / 可选 `partial`；**未知事件一律忽略** |

### 3.3 定版数据结构

- **`AnalyzeStatus`**：`kind: 'voice' | 'ser' | 'video'`、`label`、`sp`、`phase`、`enabled`、`available`、`reason: string | null`。卡片数量、顺序、`available` 判定**完全由服务端返回驱动**；前端不硬编码「`video` 恒不可用」，也不硬编码三张卡。
- **统一门禁（替换 SP-1/2 §4.1.1 的 `kind=video` 行）**：`available(kind) = 平台开关 AND 该能力探活成功 AND g3Passed(kind)`；`g3Passed` 由运维在门禁留档后**显式置位**（`video` 对应 `MEETING_FACE_POC_PASSED`，`ser` 对应 SER PoC 留档）。未通过时返回 `enabled=false, available=false, reason=<真实原因>`，**不写开关行、不产该 kind 告警**。开启仍需 `noticeConfirmed` + 有效单独同意（C23）。
- **`MeetingAlert`**：`id, roomId, transcriptId, kind, level(1|2|3), levelLabel, message, speakerIdentity, speakerName, textSnippet, audioLevel|null, emotion|null, evidence|null, serEmotion|null, serConfidence|null, serModel|null, videoChannel|null, modelCalled, ack, ackBy|null, ackTime|null, createTime`。所有可空字段允许 `null`；前端**不得显示默认 `calm` 或空标签**（对应 SP-4 §5.1、§10.3）；`message` 由后端 `AlertLevel` 枚举唯一提供，前端只渲染不拼接定性语句。
- **`TranscriptSegment`（前端）**：在既有 `speakerIdentity/text/startTs?/endTs?` 上追加**全部可选** `id?/seq?/partial?/audioLevel?/serEmotion?/serConfidence?/serModel?`。可空是硬要求（旧 worker、能力未开启、段被门丢弃、调用失败四种情形都传 `null`，不得 NPE、不得拒绝整段转录）。
- **快照 `/ai/meeting/internal/analyze/switch`**：固定 `{voice, ser, video}` + 可选 `serPolicy` / `facePolicy` 策略块；缺失策略块时对应能力 fail-closed；阈值唯一来源在 Java，worker 不持有业务阈值。

### 3.4 SSE 与页面状态

- `transcript` → 定稿分段，按 `id`（缺失时按 `speakerIdentity+text`）合并，避免重推重复。
- `partial`（可选扩展）→ 同 id 覆盖更新，显示 `data-partial` 光标；**旧后端不发时按定稿降级渲染**，不报错、不空白。
- `alert` → 去重后更新未读角标；`danger` 置 `stage.dataset.risk='danger'`，15s 或全部知悉后撤下；**只改 dataset 与独立 `RiskBanner`，绝不触发 tile 重建**。
- 进面板先 `listAlerts()` 再订阅流，弥补 SSE 断线缺口；`alert` 与对应 `transcript` 到达顺序不作假设，靠 `transcriptId` 关联。

---

## 4. CompreFace 迁移说明（SP-3 架构替换）

### 4.1 选型结论与边界

用户指令「insightface 无商用授权，人脸识别采用 CompreFace」。据此把 SP-3 的模型服务从「自建 insightface `buffalo_l` 容器」整体替换为 **CompreFace 自托管平台**，并采用 **`POST /api/v1/verification/verify` 的 1:1 两图比对**：

| 维度 | 结论 |
|---|---|
| 比对方式 | `source_image`（证件照，核验任务期经 `FileApi` 取字节） + `target_image`（会中帧） → `similarity`；**不做 1:N 检索、不建 subject 底库** |
| 检测 | `POST /api/v1/detection/detect` → `result[].box{x_min,y_min,x_max,y_max,probability}`；多人同框由适配层按 `result.length` 判定并拒答，不交给服务侧猜 |
| 鉴权 | `x-api-key`（CompreFace 服务 key）；外层 nginx 再加 `X-API-Key` 统一入口，与 `Demo-deploy/paddle/` 范式一致 |
| 部署 | 官方多容器 compose：`compreface-postgres-db` / `admin` / `api` / `fe` / `core`；对外端口避开 8011(OCR)/8020,8021(SER)/8080/80 |
| 业务侧留存 | 只存 `similarity`、结论、依据摘要、模型标识；**不存向量、不存帧、不存图像 URL 明文** |
| 判定措辞 | 无活体检测，`FACE_MISMATCH` 只能是「疑似不一致，请主持人现场确认」；禁止「不是本人/冒名/顶替」；结论不改 `party_identity.status` |

> **API 细节标注为待实测**：本环境 `raw.githubusercontent.com` / GitHub 页面 / deepwiki 的 `web_fetch` 均超时或 429，CompreFace 官方 REST 文档全文未能取到；上述端点与字段来自公开检索摘要。`Demo-deploy/compreface/scripts/verify.ps1` 的四段式验证是唯一可执行证明，未回写 README 前不得置启用开关。

### 4.2 为什么选 verification 而非 recognition

- SP-3 §1.2 把「1:N 人脸检索、以脸搜人、跨会议人脸聚类」列为**红线**；CompreFace 的 recognition 服务本质是 1:N subject 检索，且会把人脸样例存入其 Postgres，与红线及 C24 直接冲突。
- verification 1:1 不建 subject，服务侧不因本平台产生当事人人脸底库；证件照只在该次核验任务期经内网传输，符合数据最小化。
- 代价：每次核验需重新取证件照字节（SP-5 的 `FileApi.getFileContent` 通道），且相似度阈值必须按 CompreFace 的 similarity 口径**本地标定**（G2），不能沿用原 spec 的余弦阈值 `0.45`。

### 4.3 失效-替换对照表（C29 展开）

| 原 SP-3 设计 | 处置 | 替换 / 说明 |
|---|---|---|
| `insightface-svc/{app.py,Dockerfile,requirements.txt,models/buffalo_l}` | 废弃 | `Demo-deploy/compreface/` 官方多容器 compose + nginx 模板 + scripts + README |
| `/v1/face/detect`、`/v1/face/embed` 自建契约 | 废弃 | `/api/v1/detection/detect`、`/api/v1/verification/verify`（路径、请求体、返回体全部改写） |
| `X-Verify-Token` HMAC 任务凭据 | 废弃 | 任务窗口守卫上移到 Java 侧「核验任务期 + 单独同意 + 一次性 verifyId」；外层 nginx `X-API-Key` 统一鉴权 |
| `embedding-dim:512`、`normed_embedding`、`FaceSimilarityCalculator` | 废弃 | 服务直接返回 `similarity`；Java 侧不再算余弦、不再持有向量维度常量 |
| `ai_face_gallery` 表（`embedding REAL[]`、`source_url_hash`、`consent_id`、唯一索引） | **整表废弃** | 业务侧不建人脸底库；`ai_party_verify_record` 增 `face_similarity`/`face_frames_used`/`face_service_model` 等列 |
| `enroll` / `gallery/status` / `gallery/delete` 三端点与菜单 9505、9507 | 废弃 | 保留 `verifyType=FACE` 走 SP-5 `/ai/party/verify/idcard` 扩展；菜单仅保留 9506「人像核验发起」及必要的权限行 |
| `FACE_NO_BASE` / `FACE_BASE_STALE` | 废弃 | 无底库即无「底库过期」态；改为 `FACE_SOURCE_UNAVAILABLE`（证件照取不到）与 `FACE_SERVICE_UNAVAILABLE` |
| `FACE_UNSTABLE`（帧间余弦极差 > 0.25） | 重定义 | 改为「任务窗口内多次 similarity 极差超过标定阈值」，阈值由 G2 给出，不沿用余弦口径 |
| `minQuality` / `faceQualityLow` | 重定义 | 用 `/detection/detect` 的 `box.probability` 与框尺寸（人脸像素下限）作质量门 |
| `MULTI_FACE` 服务返 409 | 重定义 | 适配层按 `result.length` 判断，>1 即本帧不参与结论并记 `skipped` |
| `meeting.face.similarity-threshold: 0.45`、`embedding-dim` | 废弃/重写 | 改为按 CompreFace similarity 口径的 `similarity-threshold`，**G2 标定前不得用于生产判定**；无 `embedding-dim` |
| 端口 8030/8031、`FACE_PORT`/`FACE_NGINX_PORT` | 改写 | 见 `Demo-deploy/compreface/.env.example`，显式避开已占端口 |
| §8.4.1-L1「insightface 预置模型非商用」 | 改写 | CompreFace 平台 Apache-2.0 + **模型权重商用许可待核实**（§4.4） |
| §8.4.9 V1–V6 待实测项 | 重写 | 换成 CompreFace 部署待实测项（多容器健康、detection 返回结构、verification 返回字段、CPU 延迟、中文东亚面孔 FAR/FRR、模型许可） |
| §3.3/§9.4「服务侧 `persistence:false`、不挂卷」 | 改写 | 见 C24：CompreFace 自带 Postgres 卷，靠「禁用 recognition/subject」把业务侧生物特征落库面收敛为零 |
| §10.1 `FaceSimilarityCalculatorTest` / `FaceGalleryServiceTest` | 废弃 | 换成 `CompreFaceClientContractTest`（请求体/返回体解析、多人同框、无脸、探活失败、任务窗口外拒发）与 `PartyFaceVerdictTest` |
| §10.4 冒烟步骤 2/3/8 | 重写 | 改为 `verify.ps1` 四段式 + 任务窗口与隐私核查 |
| §11/§12/§13 | 同步 | 风险表、自检表、交付清单按本表逐项替换 |

### 4.4 G3 门禁改写（授权认知，C26）

原 SP-3 §8.1 G3 写「insightface 预置模型包官方声明仅非商业研究用途，现状为未通过」。换 CompreFace 后**不得改写为「已通过」**，正确表述为：

> CompreFace 平台代码为 Apache-2.0，可用于商业项目；但**内置/所选的具体模型权重**许可独立（公开资料提及 FaceNet 自定义许可、SubCenter-ArcFace / InsightFace 系模型，部分权重仍可能限非商业研究）。G3 通过判据：逐项列出部署所用模型名与版本、取得其权重许可全文、法务确认可商用并留档；同时确认 CompreFace 发行包内不含其它受限组件。未留档前 `MEETING_FACE_POC_PASSED` 保持 `false`，`video.available` 恒 `false`。

即：**换件解决的是「自建 insightface 容器」这条路径，不等于自动取得任何模型权重的商用授权。** 这条必须写进 SP-3 与部署件 README 首页。

**2026-11-05 修订（用户裁决，子项级结论）**：CompreFace 部署权重改用可商用开源组合 **YuNet（检测）+ SFace（识别）**（OpenCV Zoo / ONNX），选型、备选比较与「代码许可 / 权重许可 / 训练数据集许可」三层核实清单见 `2026-11-04-face-vision-analysis-design.md` 总纲 **D-2 段**。据此：

- **「模型权重授权」子项已解决**：不再沿用平台内置可能限非商用研究的权重；
- **G3 整体仍为未通过**：模型名与版本清单、权重许可快照与法务意见、命名卷留存/删除流程、告知文案三点审定四项仍待办；
- G0/G1/G2 未取证状态不变；`MEETING_FACE_POC_PASSED` 保持 `false`、`video.available` 恒 `false`、`jailed-by-poc=false`、实施计划 Task 11「仅当 Task 10 全部通过」的前置一字不改；
- 换模型后 SFace 为 128 维，G2 必须按新 similarity 分布重标定，余弦占位 `0.45` 作废；`embedding-dim` / `gallery-retention-days` / `task-secret` 等旧 insightface 口径已删除。

部署件侧按用户 Q1 裁决只做「设计 + 部署件配置」：`Demo-deploy/compreface/` 声明模型来源、自定义 core 镜像标识、SHA256 期望值与离线校验断言，**不实现插件适配层、不构建镜像、不下载权重、未实测、不可投产**。

> **2026-11-06 状态订正**：上一句是 2026-11-04 的边界，后续已按用户裁决推进 —— 自定义 core 镜像 `compreface-core-yunet-sface:1.2.0` 已构建、YuNet/SFace 权重已下载并过 SHA256、本地与远端 `192.168.110.169:8050` 均部署成功、`verify.ps1` 由四段扩为 **9 段且实测 9/9 通过**；用户 2026-11-05 人工放行后落地收敛版 1:1 业务链路（生效版 §2/§7）。但 **G0/G1/G2 未取证、G3 整体未通过、`MEETING_FACE_POC_PASSED=false`、阈值留空恒 `FACE_INSUFFICIENT`**，故「不可投产」结论不变；人工放行是风险接受决策，不是门禁留档齐备。

### 4.5 保留不变的 SP-3 结论

以下内容不因换 CompreFace 而失效，继续有效：G0「视频轨能否到达 worker」仍是**唯一实施前置且至今未证实**（`worker.py:84` 丢弃非音频轨、README 自陈未联调）；单帧不结论（连续帧 + 跨时长 + 质量达标）；`FACE_MISMATCH` 为唯一「不通过」且措辞必须含「疑似/请现场确认」；不改 `party_identity.status`、处置由人；`ai_party_consent` 的 `FACE_COMPARE` 单独同意；在场事实与在场告警分离；实施顺序 SP-1/2 → SP-5 → SP-4 → SP-3；错误码段 `1_040_065_*`、迁移 `V3.56/V3.57`、菜单 `9505–9507` 的号段划分（菜单按 §4.3 收缩）。

---

## 5. 实施顺序与验收

### 5.1 顺序（与 §2 优先顺序一致）

| 阶段 | 内容 | 状态（2026-11-06 收口后） |
|---|---|---|
| 1 | C01 双前缀修复、C02 远端音频、C03 grant 重启验证 | **均已完成**：C01 映射改 `/ai/meeting/internal`，补 `MeetingTranscriptInternalMappingTest` 4 例 + `MeetingTranscriptInternalMvcMappingTest` 的 Spring MVC 真实注册路径断言；C02 音视频元素分离；C03 `roomJoin=true` 已落地并有单测，真实登录 → 入会 E2E 通过。仅剩各环境重启/密钥注入的运维动作 |
| 2 | 契约定版（§3）+ 六份 spec 最小订正 + D1–D6 定版决议 | **完成**（§6.1 定版决议；SP-5 恢复版 5 处校准；2026-11-06 补 C05/C18/C20/C21 就地订正与 §3.1 签名订正） |
| 3 | CompreFace 部署件 + G0–G3 门禁说明 | **部署 PoC 已完成（契约层）、门禁未通过**：自定义 core 镜像 YuNet + SFace 已构建并部署到远端 `192.168.110.169:8050`，权重过 SHA256，`verify.ps1` 9/9 通过（含 1:N 红线 404）；用户人工放行后落地收敛版 1:1 业务链路。但 **G0/G1/G2 未取证、G3 整体未通过**（仅「模型权重授权」子项已解决）、`MEETING_FACE_POC_PASSED=false`、阈值留空恒 `FACE_INSUFFICIENT`，**不可投产**。剩余真机/法务任务见生效版 §9 与本文 §8 |
| 4 | 前端四区布局、舞台三态、四 Tab、15 项控制条、真实/演示适配层 | **完成**，新增 SP-5 核验 API、SP-4 依据栏纯函数、SP-3 抓帧/人像核验卡片；演示态补第三张 `ser` 卡并常驻「演示数据」标识 |
| 5 | vitest 用例 + 浏览器一致性核对 | **完成**：会议室目录 **8 文件 / 60 例全绿**（另有 `views/ai/party/__tests__` 2 文件 / 13 例，合计 10 文件 / 73 例）；原型浏览器实测 + 实现页真实 Chromium E2E 全链路已跑通（§7.3 已改写）。**真人真机逐像素比对仍缺**，属 R1/R2 门禁 |
| 6 | 后端 SP-1/2 → SP-5 → SP-4 → SP-3 → SP-6 按序实施 | **代码层：SP-1/2、SP-5、SP-4 已落地，SP-3 收敛版业务链路已打通**（V3.49–V3.55、5 个分析端点、SSE `alert`、两级门、九步核验编排、开关快照、融合服务、SER provider 四道门/30s 轮询/ASR-SER 并行、`CompreFaceClient`/`MeetingFaceController`/前端抓帧）。**门禁层：SP-4 的 U1–U5 与六条 PoC 未通过**（`MEETING_SER_ENABLED`/`MEETING_SER_POC_PASSED=false`，SER 容器未运行）；**SP-3 门禁未通过、不得投产**；**SP-6 仍停在门禁前**（G0-a~d 未取证、T3/T5 未获用户书面确认，按 D6 不开工）。逐阶段数据见 `2026-11-05-meeting-ai-specs-implementation.md`「执行结果登记」「2026-11-06 补完登记」「状态订正（2026-11-06）」 |

> **口径统一（2026-11-06）**：上表同时给出「代码/契约层已打通」与「门禁未通过」两层状态，二者不矛盾：
> 人工放行（修订方案 §7.1）是风险接受决策，不等价于 G0–G3 留档齐备；任何一处把
> `MEETING_FACE_POC_PASSED` 写成 `true`、把 `video.available` 写成恒 `true` 或把阈值标定写成已完成，
> 都属虚假合规结论。生效口径见 `2026-11-06-face-vision-analysis-effective-spec.md`。

### 5.2 验收口径

- `npm run test`：会议目录全部 spec 通过；既有 `captions.spec.ts` 4 组与 `tileAttach.spec.ts` 3 例保留并扩展。
- `npm run build` / `vue-tsc`：按 `meeting` 路径过滤验证（全仓存在既有报错基线，lint 有 100 warnings 容忍额度），不得引入新的会议目录错误。
- 效果/交互/状态一致性：以 `prototype/meeting-room.html` 为基线逐项核对四区骨架、四 Tab、15 项控制条与 P1/P2 角标、AI 分析告警态、未读角标、危险红条、断点浮层、快捷键；若 `localhost:63342` 不可达，则以本地原型文件静态读取为基线、仅对实现页做浏览器核验并显式标注该限制。
- 演示态：界面常驻「演示数据」标识，生产构建剔除；不落库、不伪装服务端结论。
- CompreFace 部署件：`verify.ps1` 已扩为 9 段并**实测 9/9 通过**（含 1:N 红线 404 与权重 SHA256 离线校验），README 含 G0–G3、模型清单与许可核实清单；实测仅证明契约层，不代表门禁通过（见 §5.1 状态订正）。

---

## 6. 本次已落实的订正清单

| 文件 | 订正内容 |
|---|---|
| `2026-11-04-meeting-ai-spec-review-and-revision.md` | 本文件（新增）：四列冲突表 30 项、事实基线 13 条、统一契约、CompreFace 迁移说明、实施顺序与验收 |
| `2026-11-04-meeting-room-ui-design.md` | 顶部加「修订索引」；§3.7 主色改按原型绿 + 局部 token、修正 `.know`/P1 角标行号色值；§9 有意差异③ 与 §12 自检同步；§3.1 删 `focusPinned`；补 partial 降级、纪要/结束接线、`MeetingStatus` 去向；§4.1.1 加门禁替换行；§10.3 标注 79 断言不可复现 |
| `2026-11-04-face-vision-analysis-design.md` | 顶部加「CompreFace 覆盖性修订总纲」（逐章替换结论 + §4.3 对照表 + §4.4 G3 改写）；§0 增差异登记；§8.4.1 许可结论改写；§12 自检与 §13 交付清单加作废指针 |
| `2026-11-04-acoustic-ser-design.md` | §6.4 字段计数订正（3 个新增 + `audioLevel` 属 SP-2）；§3.2/§3.3 快照结构统一；§0-S1 与 §3.3 的 `video` 不变量② 处置统一到 §3 门禁；§9 同意口径并入统一契约；§12 自检同步 |
| `2026-11-04-party-identity-verification-design.md` | §12 `PartyApi` 自相矛盾订正；「PP-OCRv6 真实部署」改为「配置指向 + 部署件存在，无联调证据」；同意 scope 补统一枚举来源；§9 M2 移交项同步到 CompreFace 架构 |
| `Demo-web/src/views/ai/meeting/**` | 前端实现（四区组件、composables、适配层、测试），详见工程代码 |
| `Demo-deploy/compreface/**` | 部署件（compose、nginx 模板、4 个 ps1、.env.example、README），不接业务链路（2026-11-04 时点；后续状态见 §5.1/§8） |
| `2026-11-06-face-vision-analysis-effective-spec.md` | SP-3 单一生效版精简 spec；原设计 §3–§13 隔离为历史对照；§9 是剩余门禁任务唯一入口 |
| `2026-11-04-meeting-room-ui-design.md` | 2026-11-06 就地订正 C05（§3.7 行号/色值/token 派生）与 C18（§6.1 契约改三值、卡片数服务端驱动） |
| `2026-11-03-meeting-ai-capability-design.md` | C21：顶部加事实订正 + §2/§3.1/§3.3/§4.1/§4.2 五处删去「会议字幕复用 `SseEmitterPool`」 |
| `2026-11-04-party-identity-verification-design.md` | C21：§5.1 的「PP-OCRv6 已部署」改为「配置指向 + 部署件存在、无联调证据」；C25：§9 L3 由待办改为已落实 |
| `2026-11-04-face-vision-analysis-design.md` | C20/C21：顶部事实订正②/③（PartyApi 已落地、端点已实测）、B 段与 C 段就地指针，保留门禁未过结论 |
| `MeetingTranscriptInternalMvcMappingTest.java` | C01/C22：Spring MVC 真实注册路径回归（无需 DB/Nacos），锁死无 `/admin-api/admin-api/` |
| `MediaAnalysisServiceImpl.java` + `MediaAnalysisServiceImplTest.java` | C30：四个 mock 方法显式抛 `ServiceException`、`getCapabilities()` 按真实 provider 探活口径全 false，删除「保存模拟结果」路径 |
| `MediaCapture.vue` / `AnalysisPanel.vue` | C30：前端演示态默认关闭并常驻「演示数据」标识，不复用后端假链路 |
| `application-{dev,local}.yaml`、`OcrConfigHelper.java`、`PaddleOcrClient.java` + 测试 | C25：OCR api-key 去掉明文默认值，启动期校验 + 调用期 fail-closed |
| `ser_provider.py`、`worker.py`、`test_ser_provider.py` | C19：快照解析可选 `facePolicy`，缺失时画面侧能力显式 fail-closed，新增契约测试 |
| 本文 §8 | 30 项冲突最终状态矩阵、开发侧补完清单、真人/法务/运维门禁清单 |

---

## 6.1 定版决议（2026-11-05，实施计划 D1–D6）

> 下列 6 项为 `2026-11-05-meeting-ai-specs-implementation.md` 的书面定版输入，任何一项未定版不得进入 Task 2；各 spec 修订索引均已加指针。

| # | 冲突 | 定版结论 |
|---|---|---|
| D1 | SP-5 原为空文件、5 份 spec 均引用其表/端点/枚举/号段；用户已于 2026-11-05 恢复为 515 行完整文档 | 恢复版即为 `V3.52` 与 Task 7 的唯一依据，**不重建**；只校准 5 处与统一契约的差异：①修订索引 3 的 scope 四值 → 五值；②§7.1 `ai_party_consent.scope` COMMENT → 五值清单；③§9 M2 正文「人像底库 / 人脸向量表」→ CompreFace 1:1 无底库口径；④§12 自检「分期一致性」行的 `FACE_MISMATCH` 预留 → `FACE_*` 族由 SP-3 总纲 B 定义；⑤§13 交付清单补 `verify_type` 归属说明（见 D4） |
| D2 | 本文 §3.1 的 `AnalyzeSource.toggle(kind,enabled,noticeConfirmed)` + `subscribe()` 与已落地 `useAnalyzePanel.ts` 的 `toggle(kind,enabled)` + 无 `subscribe` 不一致 | **以落地代码为准**：`toggle(kind,enabled)` 2 参，`noticeConfirmed` 由前端 `toggleAnalyze` body 固定携带且在服务端只写审计；SSE 订阅归 `useCaptionStream`，`AnalyzeSource` 不新增 `subscribe` |
| D3 | 同意 scope 四值（评审 C23、SP-5 修订索引 3 与 §7.1 COMMENT）与五值（SP-6 T2 追加 `VOICEPRINT_VERIFY`） | 定版 **5 值**：`IDCARD_VERIFY` / `FACE_COMPARE` / `SER_ANALYSIS` / `VOICE_ANALYZE` / `VOICEPRINT_VERIFY`；`PartyConsentScopeEnum`、SP-5 §7.1 V3.52 的 `COMMENT ON COLUMN ai_party_consent.scope`、V3.59 的 COMMENT 三处使用同一份清单 |
| D4 | `ai_party_verify_record.verify_type` 在 SP-3 `V3.56` 为 `VARCHAR(16)`、SP-6 `V3.60` 为 `VARCHAR(24)` 且都带 `DEFAULT 'IDCARD'`；SP-5 恢复版 §7.1 V3.52 无此列，也无 `room_id` | **单列单定义且尊重 SP-5 恢复版**：`V3.52` 按 SP-5 §7.1 原文建表（不加 `verify_type` / `room_id`）；由 **`V3.56` 一次性** `ADD COLUMN verify_type VARCHAR(24) NOT NULL DEFAULT 'IDCARD'` + `room_id BIGINT`，取值族 `IDCARD` / `FACE` / `VOICEPRINT`；`V3.60` **只改 `verify_type` 的 COMMENT**（补 `VOICEPRINT` 语义），不得再 `ALTER` 同名列或重复补 `room_id` |
| D5 | 菜单 9505/9506 三方重叠（SP-3 号段、SP-4 §6.5 复议项、SP-6 从 9508 起） | SP-3 CompreFace 版只保留 **9506**（人像核验发起），9505/9507 释放；SP-4 复议权限点改用 `9512/9513`（若合规确需拆分）；SP-6 保持 `9508~9511` |
| D6 | 声纹归属（SP-4 §1.2 归 SP-3/SP-5，实际由 SP-6 兑现）与 SP-6 的 T3（平台持有声纹向量）/T5（逆转「不调 137」） | 归属改为 SP-6；T3 与 T5 需**用户书面确认**后才允许 Task 13 开工；未确认时 SP-6 只交付到 Task 12 的门禁取证 |

---

## 7. 浏览器核验记录、对照结论与限制（2026-11-05 首轮 / 2026-11-06 订正）

### 7.1 核验方式

- 原型：Playwright Chromium `file:///d:/work/Demo_platform/Demo-web/prototype/meeting-room.html`，1600×900，`playwright_evaluate` 读取 DOM/dataset/computed style，并跑一轮交互脚本；截图存 `scratch/prototype-meeting-room-baseline-2026-11-04T16-23-36-132Z.png`。
- 实现（首轮）：Vite dev server（`:5175`）已成功启动，但实现页当时**无法在无人值守浏览器中渲染**（§7.3 的 2026-11-05 限制），故以 46 条 vitest + jsdom DOM 断言为证据。
- 实现（2026-11-06 补齐）：uaa / ai-server / 网关 / LiveKit / CompreFace 就绪后，`Demo-deploy/tools/e2e/face-verify-e2e.js` 用真实 Chromium + MJPEG 假摄像头**不 mock 任何接口**跑通「登录 → 入会 → 能力卡 → 同意门 → 抓帧 → 1:1 → 渲染」，详见修订方案 §7.9。当前会议室目录为 **8 文件 / 60 例全绿**。
- `localhost:63342` 未使用；URL 所指原型与本地 `Demo-web/prototype/meeting-room.html` 为同一文件（全仓仅此一个 `meeting-room.html`）。

### 7.2 逐项对照结论

| 项 | 原型（浏览器实测） | 实现（代码 / jsdom 断言） | 结论 |
|---|---|---|---|
| 四区骨架 | `grid-template-areas: "top top" "stage side" "bar bar"`；行高 `48px / 1fr / 68px` | `meeting.css` 同值；`meetingLayout.spec.ts` 断言四区存在 | 一致 |
| 主色 | `--accent:#00a870` | `--meeting-accent:#00A870`，作用域限定 `.meeting-room`；全局 `variables.css` 未改 | 一致（裁决 Q3） |
| 舞台底色 | `--stage:#14161a` | `--meeting-stage:#14161A` | 一致 |
| 尺寸 token | `--top:48px --side:320px --bar:68px --strip:96px` | `--meeting-top/side/bar/strip` 同值，≤1023px 时 strip=72px | 一致 |
| 侧栏 Tab | 4 个（members/transcript/info/analysis），`aria-selected` | 4 个 `role=tab`，4 个 pane 常驻、只用 `data-on` 切换 | 一致（避免 SSE 订阅重建） |
| 控制条 | 13 个 `.cb` + 1 个 `.draft`；P1 4 项、P2 3 项（含顶栏设置）、2 个 disabled | ≥13 `.cb`、P1 ≥4 / P2 ≥3 / disabled ≥2；`data-phase` 角标 | 一致 |
| 分析卡 | 2 张（voice `SP-2·P0` / video `SP-3·P1` 不可用） | 服务端 `statuses` 驱动、不硬编码卡片数；DEV 演示态已补 `ser` 成 3 张，video `.err` 含真实门禁原因 | 有意差异（后端三值契约，卡片数由服务端驱动） |
| 录制徽标 | 默认 `display:none`（`data-on` 未置位） | `#mRec data-on="0"` 默认 | 一致 |
| 视图切换 | `speaker` ↔ `gallery` | 同，`#stage[data-mode]` | 一致 |
| 告警流 | 开启语音 → `#aDemo` → 1 条 danger、角标 `1`、`data-risk=danger`、文案「疑似威胁性表述——请主持人确认，必要时休会或转线下」；知悉 → 角标隐藏 +「已知悉 · 随纪要留存」 | `meetingLayout.spec.ts` 同名用例逐项断言 | 一致 |
| video 门禁 | 点击后仍 `data-on=0`，`.err` 显示不可用原因 | `available=false` 时**可点击**、保持关闭、toast 回显真实原因、零画面告警；仅无权限时开关整体置灰 | 一致（本轮修正：不再把不可用开关 disabled，以对齐原型） |
| 舞台稳定性 | 原型 `updateSpeaking()` 只改 `dataset.cam`、不整台重绘 | `stageStability.spec.ts` 断言 danger 告警/说话高亮/字幕开关前后 tile DOM 节点引用 `toBe` 同一 | 一致且更强 |
| 共享画面 | gallery 下共享 tile 被渲染**两次**（原型自身 bug） | 共享态只插一路 `.share-slot` | 有意修复（原型 bug，不复制） |
| partial 字幕 | mock 脚本 `partial → final` 覆盖 | 可选 SSE 事件 `partial` + 同 id 合并；旧后端不发时按定稿降级 | 有意差异（后端契约待补，见 §3） |
| 未入会成员 | 5 人 mock，含 1 名未入会 | 无名单接口 → 显示「暂无法获取未入会名单」空态 | 有意差异（不伪造数据） |
| Case号 | mock 字符串 `2026-HZ-0381` | `getRoom` 真实数据 `Case #caseId` | 有意差异（不虚构Case编号） |
| 连接质量 / 计时 | 随机 mock / 本地 `started` | `ConnectionQualityChanged` / 组件内计时 | 有意差异（接真实能力） |

### 7.3 限制登记（2026-11-05 的限制已解除，但门禁限制仍在）

1. **首轮限制（已解除）**：直接访问 `/ai/meeting/live?roomId=1` 曾因路由守卫重定向 `/login`；注入假 token 后 `getPermissionInfo()` 返回 HTTP 500、页面全白。根因是当时 uaa / ai-server 未启动，不是前端代码缺陷。
2. **已补齐的证据**：后端就绪后以真实账号登录，并用 `face-verify-e2e.js`（Playwright + 本地 Chromium、MJPEG 假摄像头、零接口 mock）跑通全链路；登录、入会、能力卡开关、同意门、抓帧、1:1 核验、结果渲染全部为真实请求，详见修订方案 §7.9。因此「实现页无法在浏览器渲染」不再成立。
3. **仍存在的限制（不得写成已通过）**：E2E 用的是样例人脸画面而非真人摄像头，**不能替代** G0 双人真机 `KIND_VIDEO` 日志实证（R1）与 G1 20 段真实会中帧召回率（R2）；逐像素视觉比对也未做，以原型浏览器实测 + 8 文件 60 例 jsdom/Vitest 断言为一致性证据。真人真机补齐方式见 `Demo-deploy/tools/g01/README.md`。

### 7.4 工具链验证结论（2026-11-06 口径）

| 检查 | 结果 |
|---|---|
| 会议室 vitest | **8 文件 / 60 例全绿**（`alertCard` 4、`analyze` 12、`captions` 8、`captionStream` 7、`faceVerifyCard` 8、`meetingLayout` 10、`stageStability` 5、`tileAttach` 6）；另有 `views/ai/party/__tests__` 2 文件 / 13 例（`partyConsent` 5、`partyVerify` 8），合计 **10 文件 / 73 例全绿**（2026-11-06 实测）。旧登记「6 文件 46 例」「9 文件 60 例」均为不同时点/口径，已作废 |
| `vue-tsc --noEmit` / `pnpm type-check` | 新增/修改的会议文件**零错误**；仅 2 条既有错误落在未修改的 `MeetingList.vue` |
| `eslint` / `pnpm lint` | **仍不可执行**：`package.json` 有 `lint`/`verify` 脚本，但 `devDependencies` 未装 `eslint`/`prettier`（`pnpm-lock.yaml` 零命中），`.eslintrc.cjs` 为旧式配置。属既有工具链问题（C29/P2），本轮未擅自新增依赖 |
| 后端 Java / worker | 2026-11-06 SER 补完后：`MeetingSer*Test` 等 23 例 0 failures、worker `unittest` 25 例 OK；本轮新增 C01/C25/C30 三类测试见 §8.5。全量 `mvn test` 受跨仓 snapshot 元数据与既有源码缺失（如 `VoiceprintTemplateService`）影响，不构成本轮改动回归 |
| CompreFace 部署件 | 自定义镜像已构建、权重过 SHA256、`verify.ps1` **9 段实测 9/9 通过**（含 1:N 404）；README 含 G0–G3 与许可核实清单。**契约层完成 ≠ 门禁通过**，`MEETING_FACE_POC_PASSED` 保持 `false` |

### 7.5 收尾清理

**2026-11-05 首轮**：核验产生的 Vite dev server（`:5175`）、Playwright Chromium 会话与当时的 `scratch/` 临时日志在收尾时关闭与清除；原型基线截图保留作为评审证据。
**2026-11-06 本轮**：验证输出同样落在 `scratch/`，该目录为多会话共用，本轮不清理（见 §8.5）。

---

## 8. 未完成任务收口（2026-11-06）

> **本节是全文「尚未完成的任务」的唯一入口**。§1 是 2026-11-04 时点事实基线，§2 是当时发现的 30 项冲突，
> §5/§6/§7 的状态登记已按本节统一。任何后续开发、评审、验收请先读 §8.3/§8.4 的门禁与剩余清单。

### 8.1 本轮（2026-11-06）补完的开发任务

| C 编号 | 收口前缺口 | 交付 | 验证/证据 |
|---|---|---|---|
| C01 / C22 | C01 只有注解反射「等价断言」，无 Spring MVC 真实注册路径回归；原型 79 断言脚本不在仓库 | 新增 `MeetingTranscriptInternalMvcMappingTest`：用框架真实 `WebMvcRegistrations` 前缀规则 + 最小 `StaticWebApplicationContext` 构造 `RequestMappingHandlerMapping`，断言实际路径恰为 `/admin-api/ai/meeting/internal/{transcript,analyze/switch}` 且无双前缀；原型一次性断言明确登记「不可复现」并由 8 个 vitest spec 替代 | 新增 1 个离线可跑的 JUnit 类；见 §8.5 |
| C05 | SP-1/2 §3.7 正文仍写 `.know #f6fff9(:233)`、P1 角标 `:136/:115` | 按原型实读就地改为 `.know #eaf2ff + border #bedaff(:230)`、P1 `#eaf2ff/#4080ff(:218)`、P2 `:219`、`--meeting-hit` 由 `#fffbe6(:275)` 派生 | `meeting-room.html` 行号复核 |
| C18 | SP-1/2 §6.1 契约仍是 `kind:"voice"|"video"` 两值 | 改为 `voice|ser|video` 三值并注明卡片数/顺序由服务端返回驱动 | 与 `AnalyzeStatusRespVO.java` 一致 |
| C19 | 快照只解析 `serPolicy`，`facePolicy` 零处理、无 fail-closed 证明 | `ser_provider.parse_switch_snapshot` 解析可选 `facePolicy`，输出 `facePolicyComplete` / `faceEnabled`；`worker.AnalyzeSwitchCache.face_enabled` 显式门；缺策略块时画面侧能力恒 false | 新增 2 个 worker 契约测试 |
| C20 / C21 | SP-3 顶部「PartyApi 代码零命中」「端点待实测」「不接业务链路」过时；11-03 五处「复用 SseEmitterPool」；SP-5 §5.1「已部署」 | 三份 spec 就地订正并保留「门禁未过、不得投产」结论；11-03 加顶部事实订正 | 逐条 grep 复核 |
| C25 | `paddle.ocr.api-key` 明文默认值入 Git、缺启动校验、空 key 仍发请求 | `application-dev/local.yaml` 改 `${PADDLE_OCR_API_KEY:}`；`OcrConfigHelper.validateApiKeyConfiguration()` 启动期告警；`PaddleOcrClient.requireApiKey()` 调用期 fail-closed；SP-5 §9 L3 改为已落实 | 新增 `PaddleOcrClientApiKeyTest` |
| C30 | `MediaAnalysisServiceImpl` 四个 mock + `getCapabilities()` 四项全 true；前端 `MediaCapture` 默认输出假「分析结果」 | 五个分析入口显式抛 `ServiceException`、能力位按真实 provider 探活口径全 false、删除「保存模拟结果」路径；前端演示态默认关闭、`demo:true`、标题常驻「演示数据」 | 新增 `MediaAnalysisServiceImplTest` |
| 状态登记 | §3.1 签名、§4.4 部署件边界、§5.1 阶段状态、§6 清单、§7.1/7.2/7.3/7.4 与 F1–F13 均停在 2026-11-05 口径 | 全文就地订正 + 本节状态矩阵 + 时点声明 | 本文通读 |

### 8.2 C01–C30 最终状态矩阵

| 状态 | 编号 | 说明 |
|---|---|---|
| **首轮已完成** | C02、C03、C04、C06–C15、C16、C17、C24、C26、C27、C28、C29 | 前端一致性、契约定版、同意模型文义、CompreFace 迁移对照、实施顺序等已落地；C17 的「任何能力开启前查有效同意」实现缺口归入 C23 |
| **本轮补完** | C01、C05、C18、C19、C20、C21、C22、C30 | 见 §8.1 |
| **本轮部分完成** | C23、C25 | C23：五值枚举 / `revoked_at` / 证件核验同意前置门已落，但「会议分析 toggle 与人像核验自动查有效同意」未接（需先定版 partyId 与 consentId 映射）；C25：脱敏 / `/rpc-api` / api-key 已收口，但留存期、当事人查阅删除权、网关不对外路由实测仍缺 |
| **门禁冻结（非遗漏）** | C26 的 G3 其余四项、C28 的 SP-6 号段、D6 的 T3/T5 | 按计划不得开工；详见 §8.3 |

### 8.3 仍未完成且**不可由开发会话代劳**（必须真人 / 法务 / 运维 / 用户书面确认）

| # | 任务 | 判据 / 前置 | 工具包或出处 |
|---|---|---|---|
| R1 | G0 双人真机日志实证 | 同一 room 内 ≥2 个不同 identity 各有 `kind=KIND_VIDEO` | `Demo-deploy/tools/g01/g0-check-log.ps1` → `g0-report.md` |
| R2 | G1 20 段真实会中帧召回 | ≥20 段、召回 ≥85%、误报 ≤5% | `tools/g01/collect.html` + `g1-eval-frames.ps1` |
| R3 | G2 真实样本标定与阈值显式设置 | 正/负各 ≥20 组、帧域 FAR/FRR；管理员手工设 `MEETING_FACE_SIMILARITY_THRESHOLD` | `compreface/scripts/calibrate-threshold.ps1` |
| G3-1~4 | 模型名/版本清单、权重许可快照与法务意见、管理库留存/备份加密/撤回删除流程、告知文案三点审定 | 四项留档齐备后法务签字 | 生效版 §9 |
| V5/V8 | 真实帧 P50/P95、1:N 残留与卷内巡检 | 回写 `compreface/README.md` §7 | 生效版 §9 |
| 轮换 | 登录 RSA 2048 位密钥轮换 | 两次 uaa 重启 + `rotate-login-key.ps1` 的 `switch/verify/retire` + 生产前端重发 | `Demo-deploy/tools/rotate-login-key.ps1` |
| SER | SP-4 的 §8.2.9 U1–U5 实测与 §8.4 六条 PoC | 容器运行、真机联调、商用许可留档 | `Demo-deploy/ser/README.md` |
| SP-6 | G0-a/b/c/d 四项取证；~~T3/T5 用户书面确认~~（**2026-11-07 已确认，见 §8.7**） | D6 的「书面确认」前置已按用户 2026-11-07 指令「1、2、3 都要做」登记为**风险接受与放行编码**；**不等价于 G0–G3 取证通过**，`VOICEPRINT_POC_PASSED=false` 与全体开关不变 | 实施计划 §执行结果登记 / 本文 §8.7 |
| 合规 | 转录/告警留存期与当事人查阅删除路径；`/rpc-api` 不对外路由实测；`wss`/HTTPS Mixed Content 与 `8051` ufw 白名单 | 需产品/法务/运维定版，不能由开发会话代签 | C25 / 修订方案 §6 |
| 视觉 | 真人真机逐像素比对 | R1/R2 完成后另排 | §7.3 |

### 8.4 门禁不变声明（本轮一行未放宽）

`MEETING_FACE_POC_PASSED=false`、`VOICEPRINT_POC_PASSED=false`、`MEETING_SER_POC_PASSED=false`；
`video-gate-passed` / `MEETING_FACE_ENABLED` / `MEETING_SER_ENABLED` 的**代码默认值一律 false**；
`MEETING_FACE_SIMILARITY_THRESHOLD` 留空 ⇒ 恒 `FACE_INSUFFICIENT`、不产身份结论；
Task 11「仅当 Task 10 全部留档齐备」语义、Task 13 的 D6 前置、`worker.py` 视频轨丢弃分支、
1:N 红线、不建底库/不持向量/帧不落盘 —— 全部保持。本轮的 C30/C25/C19 改造不新增表、列、迁移、菜单、错误码，也不置位任何开关。

### 8.5 验证记录（2026-11-06 实跑）

| 检查 | 结果 |
|---|---|
| worker `python -m unittest discover -s tests -q` | **27 例 OK**（原 25 例 + C19 新增 2 例），0 failures |
| 前端 `vitest run src/views/ai/meeting/__tests__ src/views/ai/party/__tests__` | **10 文件 / 73 例全绿**（会议室 8/60 + party 2/13）；C30 前端改动未破坏既有回归 |
| 新增 3 个 JUnit 类（C01/C25/C30） | 离线 `javac` 编译 0 error，JUnit Platform Launcher 实跑 **5 例全通过 / 0 失败**：`MeetingTranscriptInternalMvcMappingTest` 1、`MediaAnalysisServiceImplTest` 2、`PaddleOcrClientApiKeyTest` 2。MVC 用例在换入当前 Controller 源码前曾检出 `/admin-api/admin-api/...`（旧 jar 类），换入后恰为两条单前缀路径，证明它锁的是真实注册路径而非字符串拼装 |
| `vue-tsc --noEmit` | 本轮改动的 `MediaCapture.vue` / `AnalysisPanel.vue` **零新增错误**；全仓仍有既有基线错误（含未改动的 `faceVerifyCard.spec.ts` TS2322），与本轮无关 |
| IDE diagnostics | 本轮编辑的 6 个 Java/Vue 文件 **0 条** |
| `eslint` / `pnpm lint` | 仍不可执行（工具链既有缺陷，§7.4）；未通过新增依赖绕过 |

### 8.6 SP-5 补完与门禁跳过登记（2026-11-06）

用户指令「跳过真实环境门禁，继续下一步」按 §8.3 口径登记为**现场取证豁免**：跳过不是取证通过，§8.4 的所有门禁开关一行未放宽。

| 项 | 订正后事实 |
|---|---|
| C23 | 「人像核验自动查有效同意」已落地（`MeetingFaceController:88-91` 的 `FACE_COMPARE` 有效同意硬门 + `MeetingFaceConsentGateTest` 3 例）；**仍缺「会议分析 toggle 自动查有效同意」**，且需先定版 `partyId`↔`consentId` 映射，属设计决策，未擅自接线 |
| C25 | 「留存期」已落地（`PartyVerifyRetentionJob` + `party.verify.retention-days` 默认 180）；**当事人查阅删除权**需产品/法务定版、`/rpc-api` 不对外路由需运维实测，两项仍缺 |
| C20/C21 | SP-5 OCR 网关不再是恒 `OCR_UNREADABLE` 占位：真实 `PaddleIdCardOcrGateway`（取字节 → PP-OCRv6 lines/score → 结构化抽取 → 正则降级 → 校验位）已接通，占位仅在 `ocr-enabled=false` 时按配置生效；`get-sensitive` 已落审计 |
| 构建状态 | 全仓 `mvn -o -B -DskipTests compile` 复测 **BUILD SUCCESS**；一次中途报 `VoiceprintTemplateService` 缺符号属构建时序/增量缓存，此前「SP-6 阻塞全仓编译」的登记作废 |
| 全仓离线回归 | ai-server **149 passed**、uaa-server **4 passed**、前端 `meeting+party+voiceprint` **14 文件 117 passed**、worker **27 OK**；`vue-tsc` 按本轮改动路径 0 错误 |
| 仍未取证（按本次裁决跳过） | §11 填充率 SQL、网关 `/rpc-api` 实测、SP-5 §10.4 七步冒烟、§10.5 八项指标、共享库迁移执行；工作区非 git 仓库，`git commit` 不适用 |

### 8.7 2026-11-07 三项收口登记（C23 / SP-3 落库 / SP-6 收尾）

用户指令「继续，1、2、3 都要做」按 §8.3 同一口径登记为**风险接受与放行编码**，
不改写 §8.4 的任何门禁开关：`MEETING_FACE_POC_PASSED` / `VOICEPRINT_POC_PASSED` / `MEETING_SER_POC_PASSED`
仍为 `false`，G2 阈值留空、全体 `enabled` 默认 `false`。

| # | 收口前缺口 | 本轮交付 | 验证 |
|---|---|---|---|
| 1 C23 | 会议分析 toggle 未查有效同意；`partyId↔consentId` 映射未定版 | `MeetingConsentGate`（roomId→caseId→case_party.party_id→ai_party_consent）、`MeetingAnalyzeSwitchServiceImpl.unavailableReason` 增加同意项并**先于探活**；`toggle` 审计写 `consentIds`；`MeetingSerGuardServiceImplTest` 补同意门 mock | `MeetingConsentGateTest` 4 例 + `MeetingAnalyzeSwitchServiceImplTest` 10 例 |
| 2 SP-3 | 生效版 §7「明确不做持久化」；V3.56/V3.57、9506、065 号段全缺；`MeetingFaceController` 不落库 | V3.56（`verify_type`/`room_id`/五个人脸列 + `ai_meeting_presence` 结构预留）、V3.57（菜单 9506）、`1_040_065_000~006` 按 CompreFace 语义重定义、`PartyVerifyRecordDO/VO` 扩列、`MeetingFaceController.persist()` 写 `verify_type=FACE`、`FaceVerdictResolver.labelOf()` 供列表展示 | `MeetingFaceRecordPersistenceTest` 4 例（Jackson 序列化钉死无 embedding/URL/号码）+ 前端 `faceRecordContract.spec.ts` 2 例 |
| 3 SP-6 | `AudioNormalizer` 只解 WAV，白名单却含 mp3/m4a/flac；T3/T5 书面确认未回填 | `AudioDecoder` SPI + `ExternalCommandAudioDecoder`（显式命令、超时、内存、不静默降级）、`AudioNormalizer.decode(bytes, decoder, filename)`、`VoiceprintQualityGate` 接线、`voiceprint.decoder-command` / `decoder-timeout-ms` 默认空/5000；T3/T5 按本次指令登记为书面确认（见 §8.3） | `AudioNormalizerTest` 5 例 + `ExternalCommandAudioDecoderTest` 6 例 + 既有 `VoiceprintQualityGateTest` 4 例回归 |

**`partyId ↔ consentId` 映射定版**（C23 的设计决策，本节为唯一口径）：`roomId → ai_meeting_room.case_id → case_party.party_id`（`party_info` 全局主数据 ID，**不是** `case_party.id`）→ `ai_party_consent.party_id`；scope 按 kind 一一对应 `VOICE→VOICE_ANALYZE` / `SER→SER_ANALYSIS` / `VIDEO→FACE_COMPARE`；一案多当事人**全部**须持有效同意（fail-closed）；`consentId` 即 `PartyConsentDO.id`，只随审计 `content` 留痕，不新增 VO 字段、不改 `AnalyzeToggleReqVO` 四参与 `AnalyzeSource.toggle(kind, enabled)` 二参。

**全仓离线回归（2026-11-07 实测）**：ai-server JUnit **211 passed / 0 failures**（`mvn -o -B -am test`，含 `-am` 从源码编译 ai-api 以绕开旧 `JevSystemOne*` jar）；uaa-server **4 passed**；前端 `meeting+party+voiceprint` **15 文件 121 passed**；worker unittest **27 OK**；`vue-tsc` 在本轮涉及路径 **0 新增错误**（`MeetingList.vue` 2 条为既有基线）。既有 `ExternalRetrievalControllerTest` / `ExternalKnowledgeTypeEnumTest` 的失败与本轮无关，已从验证集合排除并如实登记。

**仍需真人/部署**：V3.56/V3.57 与 V3.58–V3.60 在共享库执行、G0 双人真机、G1/G2 标定与影子人检、G3 四项留档、137 端点实现与鉴权、ffmpeg 解码器部署注入、§10.4/§10.5 冒烟与巡检 —— 一律不得写成已通过；工作区非 git 仓库，`git commit` 不适用。

### 8.8 2026-11-07 续：剩余纯开发缺口收口

用户指令「继续」按 §8.3 口径先排除真人/法务/运维/部署项，再完成三项**纯代码**缺口。门禁开关一行未动。

| # | 收口前缺口 | 本轮交付 | 验证 |
|---|---|---|---|
| ① | V3.56 后 IDCARD/FACE/VOICEPRINT 共用 `ai_party_verify_record`，但 `/ai/party/verify/page` 无过滤，证件档案页会混显 FACE 结论 | Mapper 增 `selectPageByPartyAndType` / `countByPartyAndType`；`PartyVerifyService.page` 增 4 参重载（三值白名单，非法值拒绝）；Controller 默认 `verifyType=IDCARD`；前端 `pageVerifyRecords` 默认带 `IDCARD`，卡片自动隔离 | `PartyVerifyRecordPageTest` 3 例 + 前端 `verifyPage.spec.ts` 2 例 |
| ② | 质检门归一后的 PCM 只用于本地判定，`transcribe` / `embed` 仍外呼原始字节（spec §13.2.1 ③-附登记的实现边界） | `Clip.toWavBytes()` 编回 16k mono 16-bit WAV；`Quality.normalizedWav` 保留该字节；`VoiceprintVerifyService.verify/enroll` 的 ASR 与 embedding 统一上传 `normalized.wav` | `VoiceprintNormalizedUploadTest` 1 例 + `AudioNormalizerTest` 回环 1 例 + `VoiceprintQualityGateTest` 1 例 |
| ③ | `CompreFaceClient.detect` 服务异常时返回空列表，被 Controller 吞成 `FACE_NO_FACE`（服务故障伪装成「本帧无人脸」） | `detect` 异常返回 `null`；Controller 对 `null` 判 `FACE_SERVICE_UNAVAILABLE`，空列表才判 `FACE_NO_FACE`。**判定族仍为生效版 §5 唯一 6 值，不新增 verdict、不引入 8 值旧表** | `MeetingFaceRecordPersistenceTest` 新增 1 例 |

**全仓离线回归（本轮实测）**：ai-server JUnit **218 passed / 0 failures**（`mvn -o -B -am test`）；uaa-server **4 passed**；前端 **16 文件 124 passed**；worker **27 OK**；`vue-tsc` 本轮涉及路径 **0 新增错误**。既有 `ExternalRetrievalControllerTest` / `ExternalKnowledgeTypeEnumTest` 失败仍与本轮无关，验证集合继续排除。

**下一轮候选（本轮未做，需另起计划或产品/合规定版，不是遗漏）**：跨实例 SSE 广播（可仿 Redis 优先 / 本地降级）；逐方告知记录落库（P1，需告知字段范围定版）；C25 当事人查阅删除权端点（需留存期策略与合规定版）；P2 能力（录制/Egress/会控/设置）按既有 YAGNI 决议不排 Task。真人/部署项见 §8.7 末尾，全部保持未通过。

### 8.9 2026-11-07 第五轮：跨实例 SSE / 逐方告知 / 当事人自查删除权 / P2 边界

正文见 `2026-11-07-dev-closure-round5.md`：跨实例 SSE 广播、逐方告知记录落库、当事人自查与删除权三项纯开发已完成并有回归；P2 能力按既有 YAGNI 决议不排 Task、只给边界与开工前置。门禁开关一行未动。

**前端接线（同日已闭环）**：逐方告知面板（`MeetingNoticePanel.vue`，会议 AI 分析区）与当事人自助抽屉（`MyVerifyRecordsDrawer.vue`，档案页「我的核验记录」）均已挂载并有组件测试；管理端**不提供**按 partyId 的代办删除（避免越权删除），如确需另起端点并要求二次确认与法务定版。前端回归 18 文件 131 passed。
| 全量 `mvn test` | **未作为通过结论**：本环境跨仓 timestamped snapshot 解析与既有源码缺失（`VoiceprintTemplateService` 等）导致全模块编译失败，属既有基线问题；本轮 Java 改动改用「当前源码 + 既有 fat jar 类路径」离线编译并执行新增测试，不把局部验证写成全量回归 |

> 验证输出（vitest / vue-tsc / javac 日志与离线类路径文件）落在 `scratch/` 临时目录，不入库、不作为交付物；
> `scratch/` 为多会话共用，本轮不清理目录，原型基线截图保留作为评审证据。


