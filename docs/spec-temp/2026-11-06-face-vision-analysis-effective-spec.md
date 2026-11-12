# SP-3 会中人像 1:1 到场一致性核验 —— 单一生效版 Spec

> 日期：2026-11-06（当日二轮更新）　状态：**生效（设计口径）· 用户已声明真人门禁通过 · 配置默认值未改、投产仍需运维置位**
>
> 本文件是 `2026-11-04-face-vision-analysis-design.md`（下称「原设计」）经两次裁决后的**唯一生效口径**。
> 原设计 §3–§13 的 2026-11-04 insightface 原文已由本轮加「整章作废」banner 隔离为历史设计对照，
> **不得实施、不得引用为契约、不得作为验收依据**（修订方案 C02 / §6 P0-2）。
>
> 上位依据：原设计顶部总纲 A–E 与 D-2 段、`2026-11-04-meeting-ai-spec-review-and-revision.md` §3 统一契约、
> `2026-11-05-meeting-ai-specs-implementation.md` D1–D6 与 Task 10/11、
> `2026-11-05-ai-meeting-consolidated-revision.md` §4（契约定版）/ §7（人工放行与实装记录）。
> 部署件：`Demo-deploy/compreface/README.md`、`guide.md`、`scripts/verify.ps1`（9/9 实测）。
>
> **一句话状态**：CompreFace 1:1 契约层部署 PoC 已完成、Task 11 经用户 2026-11-05 人工确认放行后落地了
> **收敛版业务链路**，端到端已打通；但 **G0/G1/G2 未取证、G3 整体未通过**，
> `MEETING_FACE_POC_PASSED=false`、阈值留空、系统恒返回「核验未完成」，**不产任何身份结论**。
> 人工放行是风险接受与放行决策，**不等价于门禁留档齐备**（修订方案 §7.1）。
>
> **2026-11-06 用户放行登记**：用户明确指令「不考虑门禁，当前真人测试的门禁都通过」，据此本轮不再以门禁为由阻塞编码，
> 已执行 C1–C3 上线硬缺口开发（自动同意校验、服务端窗口、证件照后端取字节，见 §2/§7/§8）。
> 如实记录：工作区内仍无 G0/G1/G2 报告文件与 G3 四项留档；代码默认值、`MEETING_FACE_POC_PASSED`、
> `MEETING_FACE_SIMILARITY_THRESHOLD` **一个字未改**，阈值留空时系统仍恒返回「核验未完成」。
> 门禁置位与投产仍属运维动作，本文件不代劳、不伪称已通过。

---

## 0. 本文件收口了什么

| 项 | 收口前 | 收口后 |
|---|---|---|
| 生效口径 | 原设计 1100+ 行正文中大部分是已作废的 insightface 原文，仅靠顶部一张 B 段替换表约束 | 原设计 §3–§13 加统一整章作废 banner ＋ §4.3/§6.1/§7/§10 就地指针；本文件为唯一生效版 |
| 架构 | 三份文档分别写 worker 取帧、CompreFace 1:1、浏览器抓帧，互相冲突 | §2 定版为**浏览器焦点视频轨抓帧 → ai-server → CompreFace**，不接 worker 视频轨 |
| 判定族 | 旧 8 值 / 18 值 / 6 值并存 | §5 定版为实装的 **6 值**，唯一不通过 `FACE_MISMATCH` |
| 状态登记 | 计划与评审方案仍写「镜像未构建、服务未部署、Task 11 不开工」 | §8/§9 与实测对齐，并在计划/评审方案加状态订正（C03 / §6 P0-3） |
| 剩余任务 | 散落在 §7.10、README §2/§7、原设计 §8.1 | §9 单一清单，区分「开发可完成」与「必须真人/法务/运维」 |

**本文件不改动任何生产代码、不置位任何开关、不新增迁移、不解除任何门禁。**

---

## 1. 目标、非目标与红线

### 1.1 目标（收敛版）

1. 会中对**特定当事人**做 1:1 人像一致性核验：证件照与会中帧一起送 CompreFace `verification/verify`，取服务端 `similarity`。
2. 只在主持人**显式发起**、勾选「已取得单独同意」、且服务端能力卡 `video.available && enabled` 为真时才抓帧。
3. 保守判定：单帧不结论，须连续 `3` 帧且跨时长 `≥ 15s`；阈值未标定（G2）时**只回传相似度，不产结论**。
4. 结论一律「疑似/请现场确认」，**永不修改 `party_identity.status`**、不写 `ai_meeting_alert`、处置由人。

### 1.2 非目标与红线（逐条可执行检查）

| 项 | 约束 | 实装落点 |
|---|---|---|
| 1:N 检索、以脸搜人、跨会议人脸聚类 | 禁止；nginx 路径白名单只放行 detection/verification，1:N 路径 404 | `compreface/nginx/default.conf.template`、`verify.ps1` 第 5 段断言 |
| 建 subject 底库、持有/落库向量 | 禁止；平台只存内存中的图片字节与 similarity | `CompreFaceClient` 无缓存/无 Mapper；`FaceVerifyRespVO` 无 `embedding*` 字段 |
| 帧落盘、入库、进日志 | 禁止；帧只存在于本次请求内存 | `useFaceVerification.grabFrame()`、`MeetingFaceController` 仅记录 verdict 类别 |
| 活体检测 | **不做且必须告知**；一张证件照即可骗过链路 | `FaceVerifyCard.vue` 隐私声明；结论措辞硬约束 |
| 自动身份定性 / 自动改状态 | 禁止；`FACE_MISMATCH` 是唯一不通过，措辞固定 | `FaceVerdictResolver.resolve()`、`FaceVerifyCard` 唯一红色分支 |
| 服务不可用时误判为「不匹配」 | 禁止；一律 `FACE_SERVICE_UNAVAILABLE` + 核验未完成 | `MeetingFaceController.unavailable()` |

---

## 2. 生效架构与数据通路

```
浏览器（会议室焦点视频轨）
  └─ useFaceVerification.grabFrame()：离屏 video + canvas，长边 640、JPEG q0.72、1 帧/3s
       └─ POST /admin-api/ai/meeting/face/verify  (multipart targetImage + partyId + roomId)
            └─ MeetingFaceController
                 ├─ Step 0 硬门：PartyConsentService.findValid(partyId, FACE_COMPARE)
                 │     无同意 → 抛 1_040_063_000，先于任何外呼（含探活/身份底库/文件/模型）
                 ├─ 证件照：PartyApi.getIdentityForVerify → idCardFrontUrl
                 │           → FileApi.getFileContent(path, fileCode)（仅本次请求内存）
                 ├─ 开关 / 探活 / 取字节失败 → FACE_SERVICE_UNAVAILABLE
                 ├─ CompreFaceClient.detect(targetImage) → result[].box.probability
                 │     多脸 → FACE_MULTI_FACE（拒答，不猜身份）；无脸 → FACE_NO_FACE
                 ├─ CompreFaceClient.verify(idCardBytes, targetImage)
                 │     → result[0].face_matches[0].similarity
                 ├─ FaceVerifyWindowService.observe(roomId, partyId, sim, threshold, now, ttl)
                 │     服务端累计连续低分帧与跨时（Redis 优先 / 本地退化，带 TTL）
                 └─ FaceVerdictResolver.resolve() → 6 值判定 → FaceVerifyRespVO（回显服务端窗口）
```

前端**不再上传**证件照文件，也**不再上传** `lowFrameCount` / `spanSeconds`；卡片勾选同意只是 UI 提示，
服务端 `FACE_COMPARE` 硬门才是唯一凭据，窗口值只由服务端回显供展示（2026-11-06 补齐）。

**实测拓扑（2026-11-05）**：CompreFace 业务网关 `http://192.168.110.169:8050`（外层 `X-API-Key`）、
控制台 `8051`、共享 PostgreSQL `192.168.100.80:5432/compreface`（管理数据，无当事人人脸底库）、
ai-server 本机 `:8086` / 网关 `:8080`、LiveKit `ws://192.168.110.169:7880`。

**关键形态裁决**：采用**浏览器抓帧**，不依赖 worker 视频轨。原设计 §3.1 的形态 ①（worker `VideoStream` 取帧）
因 G0 未证实而**不实施**；`worker.py` 的 `[track-observe]` 观测日志保留但**不改判断分支**，
其真机实证仍是 G0 门禁的独立待办（R1）。这不是「绕开 G0 即门禁通过」：见 §3 与 §9。

**模型与相似度口径**：自定义镜像 `compreface-core-yunet-sface:1.2.0`，YuNet（检测）＋ SFace（128 维识别），
权重 SHA256 见 `compreface/guide.md` §1.3。`similarity` 由 CompreFace 服务端按欧氏距离换算，
**与论文余弦口径不同**；原设计的余弦占位 `0.45` 已作废，G2 必须按帧域本地重标定。

---

## 3. 门禁公式与 fail-closed 开关

**统一公式（修订方案 §4.1，覆盖原设计 §6.4 的旧公式）**：

```
available(kind) = meeting.analyze.enabled
                  AND platformEnabled(kind)
                  AND probeOk(kind)
                  AND g3Passed(kind)
                  AND noticeConfirmed          # 操作人确认动作（写审计），非同意凭据
                  AND validConsent(scope)      # FACE_COMPARE 单独同意
未通过 → enabled=false, available=false, reason=真实原因, 不写开关行, 不产该 kind 告警
```

**video 的两个门禁层必须分开理解**：

> **2026-11-07 置位（用户「继续」指令）**：已用 `Demo-deploy/compreface/scripts/enable-face-poc.ps1 -Action enable`
> 把本地两个 `.env` 置为 `POC_PASSED=true` / `G3_VIDEO=true` / `FACE_ENABLED=true`、阈值 `0.55`
> （**联调值**，来源为现有样例标定报告的帧域建议值，样本量不足；真人 G2 报告到手后须替换）。
> 置位留档 `evidence/poc-enablement-record.md`，`deploy.ps1` 已改为「true 时校验置位留档」。
> **下表仍是代码默认值**，须由部署环境显式注入；`enable-face-poc.ps1 -Action rollback` 可一键回到 fail-closed。

| 层 | 变量 | 代码默认值 | 语义 |
|---|---|---|---|
| 部署件门禁 | `MEETING_FACE_POC_PASSED`（`compreface/.env`） | `false` | 置 true 后 `deploy.ps1` 要求存在 `evidence/poc-enablement-record.md` |
| 后端能力门禁 | `MEETING_G3_VIDEO`（`video-gate-passed`） | 代码默认 `false` | `/analyze/status` 的 `video.available` 才可能为 true |
| 后端外呼门禁 | `MEETING_FACE_ENABLED` | 代码默认 `false` | 不置位则 `CompreFaceClient` 全部请求短路，`face/health` 返回 false |
| 结论门禁 | `MEETING_FACE_SIMILARITY_THRESHOLD` | **留空** | 空 ⇒ `calibratedThreshold()` 返回 null ⇒ 恒 `FACE_INSUFFICIENT`，**不产身份结论** |

2026-11-05 用户人工放行后，部署环境显式注入 `MEETING_G3_VIDEO=true`、`MEETING_FACE_ENABLED=true`，
实测 `face/health=true`、`video.available=true`。**代码默认值一个字未改**；这是放行决策，
不是门禁通过，也不解除 `MEETING_FACE_POC_PASSED=false`。阈值仍留空，是最后一道「零模型结论」保险。

---

## 4. 接口契约（实装为准）

### 4.1 ai-server（框架自动前置 `/admin-api`，映射字面量不含该前缀）

| 端点 | 方法 | 权限 | 契约 |
|---|---|---|---|
| `/ai/meeting/face/verify` | POST | `ai:meeting:analyze` | multipart `targetImage`（会中帧）＋ `partyId` ＋ `roomId`（默认 0）→ `FaceVerifyRespVO`；证件照由服务端按 `partyId` 取字节，窗口由服务端累计 |
| `/ai/meeting/face/health` | GET | `ai:meeting:query` | `CommonResult<Boolean>`；只证网关存活，不证模型就绪 |
| `/ai/meeting/analyze/status` | GET | 既有 | 三值 `voice\|ser\|video`，`available/reason` 服务端驱动，前端不得本地判定 |
| `/ai/party/consent/status` | GET | `ai:party-verify:query` | 支持可选 `scope`；SP-3 传 `FACE_COMPARE`，不传则保持 SP-5 的 `IDCARD_VERIFY` 兼容 |

`FaceVerifyRespVO` 字段：`verdict`、`similarity`、`threshold`、`faceCount`、`message`、`reason`、
`lowFrameCount`、`spanSeconds`（后两项为服务端窗口回显）。
**响应体与日志均不含** `embedding*`、图片字节、证件照 URL 全串、CompreFace 服务 key。
`verify` 的 Step 0 是 `FACE_COMPARE` 同意硬门：无有效同意抛 `1_040_063_000`（复用 SP-5 号段），零外呼。

### 4.2 CompreFace（外层网关，业务侧只持 `X-API-Key`）

```
GET  /face-nginx-health                          → {"status":"ok"}（免鉴权）
POST /face/api/v1/detection/detect?limit=5       → result[].box{x_min,y_min,x_max,y_max,probability}
POST /face/api/v1/verification/verify            → result[0].face_matches[0].similarity
POST /face/api/v1/recognition/recognize          → 404（1:N 红线，客户端从不调用）
```

实测参考点（非阈值）：同人原图 `0.91883`、同人帧域 `0.66306`、异人 `0.0777`；
多脸样例检出 5 张脸 → `FACE_MULTI_FACE`。**原图域系统性高于帧域**，阈值必须取帧域（§9-R3）。

### 4.3 前端

`src/api/ai/face.ts` 的 `verifyFace(targetImage, partyId, roomId)` / `getFaceHealth()`；
`FaceVerifyCard.vue` 仅当 `video.available && enabled` 才渲染，须勾选同意 ＋ 填写**当事人 ID**
（可由会议链接 `?partyId=` 预填）才能开始，**无文件上传控件**；
`useFaceVerification.ts` 只抓帧并展示服务端回显的 `lowFrameCount` / `spanSeconds`，不自行累计窗口。
卡片一律不显示示例人脸数据；`MeetingRoom.vue` 把 `roomId` 传入 composable 作为窗口键。

---

## 5. 判定族（唯一 6 值，覆盖原设计 §4.3 的 8/18 值旧表）

| verdict | 触发 | 文案 | 不通过 |
|---|---|---|---|
| `FACE_INSUFFICIENT` | 阈值未标定（G2）／窗口不足（连续帧 < 3 或跨时 < 15s） | 核验未完成：阈值未标定 / 样本窗口不足 | 否 |
| `FACE_NO_FACE` | 本帧未检出人脸 | 本帧未检出人脸，核验未完成 | 否 |
| `FACE_MULTI_FACE` | 目标帧检出 >1 张脸 | 画面中有多人，无法进行 1:1 核验，请现场确认 | 否 |
| `FACE_SERVICE_UNAVAILABLE` | 开关关 / 探活失败 / 图像读取失败 / 服务无有效结果 | 核验未完成：<真实原因> | 否 |
| `FACE_MATCHED` | 阈值已标定、窗口满足、`similarity ≥ threshold` | 一致性核验未见异常（非身份认定） | 否 |
| `FACE_MISMATCH` | 阈值已标定、窗口满足、`similarity < threshold` | **疑似不一致，请现场确认** | **是（唯一）** |

短路顺序：`阈值未标定` → `服务无有效结果` → `窗口不足` → `MISMATCH/MATCHED`；
多脸与无脸在 Controller 层先于比对短路。`FaceVerdictResolver` 为无 IO 纯函数，
**不得**出现「不是本人 / 冒名 / 顶替」等定性措辞，不得自动改任何业务状态。

---

## 6. 配置（`application.yaml` 的 `meeting.face.*`，默认全 fail-closed）

```yaml
meeting:
  face:
    enabled: ${MEETING_FACE_ENABLED:false}
    base-url: ${COMPREFACE_BASE_URL:http://192.168.110.169:8050}
    api-key: ${COMPREFACE_API_KEY:}
    similarity-threshold: ${MEETING_FACE_SIMILARITY_THRESHOLD:}   # 留空 = G2 未标定 = 不判定
    timeout-ms: ${MEETING_FACE_TIMEOUT_MS:5000}
    min-frames: ${MEETING_FACE_MIN_FRAMES:3}
    min-span-seconds: ${MEETING_FACE_MIN_SPAN_SECONDS:15}
  analyze:
    video-gate-passed: ${MEETING_G3_VIDEO:false}
```

`CompreFaceProperties.calibratedThreshold()` 对空值、非法值、越界值一律返回 `null`（fail-closed）。
任何环境变量注入都不得写入代码默认值；部署期注入见修订方案 §7.4。

---

## 7. 数据持久化边界（2026-11-07 用户裁决后：核验历史落库）

> **口径变更**：本节 2026-11-06 原文为「收敛版明确不做」。用户 2026-11-07 指令「1、2、3 都要做」
> 明确解除该裁决，按实施计划 Task 11 / D4 / D5 落地持久化与号段。以下为**现行口径**。

**已落（代码与迁移已交付，未在共享库执行）**：

| 交付 | 位置 |
|---|---|
| `V3.56__face_presence.sql` | `ai_meeting_presence` 结构预留；`ai_party_verify_record` 一次性补 `verify_type VARCHAR(24) NOT NULL DEFAULT 'IDCARD'`、`room_id` 与五个人脸标量列；`verify_type` 注释一次写全三值（`V3.60` 只改注释，不再 ALTER） |
| `V3.57__face_menu.sql` | 菜单 `9506` / `ai:meeting:face-verify`（D5：9505/9507 仍释放） |
| `1_040_065_000~006` | 按 CompreFace 1:1 语义**重定义**；原 insightface 时代「人像底库 / 特征向量 / 密钥回推」语义作废 |
| 落库链路 | `MeetingFaceController.persist()` 写 `verify_type=FACE` 的核验历史；`PartyVerifyServiceImpl.start()` 显式写 `IDCARD`；`PartyVerifyRecordVO` 增加 `verifyType` 与三个人脸标量 |

**红线不放宽**：仍不建 `ai_face_gallery`、不写 `ai_meeting_presence` 行、不做 1:N、不落人脸向量/帧/证件照 URL、不改 `party_identity.status`、不写 `ai_meeting_alert`、不产 SSE 新事件名；落库只存 similarity、结论、依据摘要、服务标识与窗口计数（`MeetingFaceRecordPersistenceTest` 用序列化断言钉死）。

| 明确未接 | 原因 | 归属 |
|---|---|---|
| worker 视频轨（`worker.py:84` 分支） | 浏览器抓帧不依赖它；如需恢复该形态须独立评审 | R1 后独立评审 |

**2026-11-06 已补齐的三项上线硬缺口**（不再属于未做清单，仍未新增任何表/列/迁移/菜单/新错误码）：

1. **自动 `FACE_COMPARE` 同意校验**：`MeetingFaceController.verify()` Step 0 调
   `PartyConsentService.findValid(partyId, FACE_COMPARE)`；无同意抛 `1_040_063_000` 且零外呼
   （`MeetingFaceConsentGateTest` 钉死）。`PartyConsentService.status(partyId, scope)` 与
   `GET /ai/party/consent/status?scope=` 支持按 scope 查询，默认仍 `IDCARD_VERIFY`。
2. **服务端窗口复核**：新增 `FaceVerifyWindowService`，键 `meeting:face:window:{roomId}:{partyId}`，
   Redis 优先 / 进程内退化、TTL 随 `min-span-seconds` 推导；高分帧与阈值未标定清零。
   前端 `lowFrameCount` / `spanSeconds` 入参**彻底删除**，响应回显服务端值。
3. **证件照后端取字节**：`PartyApi.getIdentityForVerify(partyId)` → `idCardFrontUrl` →
   `FileApi.getFileContent(path, PartyVerifyProperties.getFileCode())`；`fileCode` 默认 `idcard`；
   取不到或 0 字节短路 `FACE_SERVICE_UNAVAILABLE`，URL 不进日志/响应。前端删除 `<input type=file>`。

`partyId` 目前由主持人填写或会议链接 `?partyId=` 预填；接入当事人列表/焦点参与方映射属后续产品决策，
不改变「服务端取字节」这一安全边界。

---

## 8. 测试与验收基线（已实测，不重跑不伪造）

| 验证 | 结果 |
|---|---|
| `mvn -o -pl :Demo-module-ai-server -am -DskipTests compile` | 通过 |
| `FaceContractTest`（阈值门 + 判定状态机 9 例） | 9 passed / 0 failures |
| `FaceVerifyWindowServiceTest`（连续帧/跨时/清零/过期，2026-11-06 新增） | 6 passed / 0 failures |
| `MeetingFaceConsentGateTest`（同意零外呼、服务端窗口、证件照短路，2026-11-06 新增） | 3 passed / 0 failures |
| 会议室 vitest（2026-11-06） | 11 文件 / **85 例全绿**，其中 `faceVerifyCard.spec.ts` 10 例（含「无文件上传控件」「服务端累计窗口」） |
| `vue-tsc --noEmit` | 按本次改动文件过滤 **0 错误**（全仓既有基线不在本轮范围） |
| `CompreFaceClientRemoteContractTest` 真实外呼远端 8050 | 3/3 通过；默认跳过，需 `-Dface.remote.test=true` |
| `face-verify-e2e.js`（Playwright CI 回归，不 mock 接口） | 已改为 `E2E_PARTY_ID` 驱动：填当事人 ID → 服务端取证件照 → 1:1；MJPEG 假摄像头只替代摄像头画面，真人取证走 `tools/g01/` |
| `/face/verify` 端到端 | 同人 `0.91883`、异人 `0.0777`，均 `FACE_INSUFFICIENT`；多脸 `FACE_MULTI_FACE` |
| `verify.ps1` 部署契约 | 9/9（含 1:N 红线 404、权重 SHA256 离线校验） |

**红线断言（回归必查）**：`threshold=null` 时任何输入都不得出现 `FACE_MATCHED` / `FACE_MISMATCH`；
服务不可用不得返回 `MISMATCH`；`FACE_MISMATCH` 唯一红色且措辞固定；响应体不含 `embedding` 字段；
日志不含 base64 长串与证件照 URL。

---

## 9. 门禁状态与剩余任务（本清单是「尚未完成」的唯一入口）

> **状态口径（2026-11-06）**：用户已明确声明「真人测试的门禁都通过」并指令不考虑门禁，
> 本轮据此完成了 §7 的三项开发硬缺口。下表记录的是**工作区内留档材料的状态**，用于运维置位与审计，
> 不是对用户放行结论的否定；G0/G1/G2 报告文件与 G3 四项留档在本工作区仍不存在，
> 且 `MEETING_FACE_POC_PASSED`、阈值、代码默认值一个字未改。

| 门禁 | 留档状态（工作区材料） | 置位前置 |
|---|---|---|
| G0 帧可达 | **未证实** | R1 |
| G1 真实帧召回/误报 | 契约层已验证，**召回口径未通过** | R2 |
| G2 阈值标定 | **未通过**（阈值留空，恒 `FACE_INSUFFICIENT`） | R3 |
| G3 许可与合规 | **未通过**（仅「模型权重授权」子项已解决） | 四项留档，见下 |
| 部署件开关 | 本地 `.env` 已于 2026-11-07 置 `true`（留档 `evidence/poc-enablement-record.md`） | 用户放行；真人/法务留档仍待补，可一键 rollback |

### 9.1 必须真人真机 / 法务 / 运维完成（开发会话不得代劳、不得伪造）

| # | 任务 | 判据 | 工具包 |
|---|---|---|---|
| R1 | G0 双人真机日志实证 | 同一 room 内 ≥2 个不同 `identity` 各有 `kind=KIND_VIDEO` | `Demo-deploy/tools/g01/g0-check-log.ps1` → `g0-report.md` |
| R2 | G1 20 段真实会中帧 | ≥20 段、召回 ≥85%、误报 ≤5%，覆盖侧脸/低光/遮挡/多人/无人 | `tools/g01/collect.html` + `g1-eval-frames.ps1` → `g1-report.md` |
| R3 | G2 真实样本标定 | 正/负配对各 ≥20 组、帧域 FAR/FRR 达标；由管理员**显式**设阈值 | `tools/g01/collect.html` + `compreface/scripts/calibrate-threshold.ps1` |
| G3-1 | 模型名与版本清单 | 逐项列出 YuNet / SFace 权重文件名、版本、SHA256 | 素材已在 `guide.md` §1.3，须评审留档 |
| G3-2 | 权重许可快照 + 三层核实 + 法务意见 + 组件扫描 | 代码/权重/训练数据集三层出处齐全，法务签字 | 待法务 |
| G3-3 | 管理库留存期 / 备份加密 / 撤回删除流程 | 运维工单号，回填原设计 §11 | 待运维 |
| G3-4 | 告知文案三点审定 | 「不保存图像 / 无活体检测 / 不改实名状态」逐条审定记录 | 待合规 |
| V5/V8 | 真实帧 P50/P95、1:N 残留与卷内巡检 | 回写 `compreface/README.md` §7 | 待实测 |
| 轮换 | 登录 RSA 2048 位密钥轮换 | 两次 uaa 重启 + `rotate-login-key.ps1` 的 `switch/verify/retire` + 生产前端重发 | `Demo-deploy/tools/rotate-login-key.ps1` |

### 9.2 上线前合规/工程硬缺口（2026-11-06 复核口径）

**1–3 已由开发会话补齐**（`MeetingFaceController` 顶部注释与实现为准，先前「本轮未做」的登记已过时）：

1. ✅ **自动同意校验**：`MeetingFaceController:88-91` 在 `FACE_COMPARE` 有效同意缺失时抛 `PARTY_CONSENT_REQUIRED`，先于探活/底库/文件/模型任何外呼；`MeetingFaceConsentGateTest` 3 例回归。
2. ✅ **服务端窗口复核**：`FaceVerifyWindowService.observe(roomId, partyId, similarity, threshold, now, ttl)` 按房间+当事人累计 `lowFrameCount`/`spanSeconds`（`MeetingFaceController:135-146`），客户端不再传这两个参数。
3. ✅ **证件照服务端取字节**：`MeetingFaceController:156-170` 经 `PartyApi.getIdentityForVerify` + `FileApi.getFileContent` 临时取字节，前端只传 `partyId` 与会中帧；URL 不进日志/响应。

**4–5 仍需真人/部署环境**：用户 2026-11-06 声明真人测试门禁已通过、2026-11-07 指令继续；
本地 `.env` 已按放行置位（§3/§9），**代码默认值仍未改**；真人 G0/G1/G2 报告与 G3 法务/运维签字仍不在工作区。

4. **真人浏览器联调**：`face-verify-e2e.js` 已支持 `E2E_PARTY_ID` 与 `E2E_REAL_CAMERA=1`
   （真人摄像头模式，去掉 Chromium 假设备参数）；CI 回归仍用 MJPEG 假摄像头，真人取证走 `tools/g01/`。
5. **实时部署契约**：`wss` / HTTPS Mixed Content 边界、远端控制台 `8051` 的 ufw 网段白名单、Demo 密钥轮换。
6. **V5/V8 与 G3 留档**：`verify.ps1 -CheckLatency -CheckResidual` 可自动产出
   `evidence/v5-latency.md` / `evidence/v8-residual.md`；`evidence/g3/` 四份文件已建
   （模型清单坐实，许可快照/法务意见/运维工单/文案审定待签字）。
7. **阈值替换**：当前 `0.55` 来自样本不足的样例报告，仅供联调；真人 G2 报告到手后按
   `enable-face-poc.ps1 -Action rollback` → `-Action enable -Threshold <真人值>` 替换。

**8. 核验历史落库（2026-11-07 已补，见 §7）**：`V3.56`/`V3.57`、菜单 9506、065 号段与 `MeetingFaceController.persist()` 已交付；`MeetingFaceRecordPersistenceTest` 4 例 + 前端 `faceRecordContract.spec.ts` 2 例回归。迁移仍须在共享库执行，G0–G3 门禁状态不变。

**9. 判定边界修正（2026-11-07 续）**：`CompreFaceClient.detect` 服务异常时由「返回空列表」改为返回 `null`，Controller 对 `null` 判 `FACE_SERVICE_UNAVAILABLE`、空列表才判 `FACE_NO_FACE`，不再把服务故障伪装成「本帧无人脸」。判定族**仍为 §5 唯一 6 值**，不引入旧 8 值表。同批给 `/ai/party/verify/page` 加 `verifyType` 过滤（默认 `IDCARD`），证件档案页不混显 FACE 记录；回归：ai-server 218 passed、前端 16 文件 124 passed。

> 置位已完成但**留档未齐备**：正式投产前须补齐真人报告、G3 四项签字并复核阈值来源；
> 任何时候可用 `enable-face-poc.ps1 -Action rollback` 一键回到 fail-closed。

---

## 10. 文件索引

| 层 | 路径 |
|---|---|
| 后端 | `Demo-ai/.../controller/admin/meeting/MeetingFaceController.java`、`vo/FaceVerifyRespVO.java`、`service/meeting/support/{CompreFaceClient,FaceVerdictResolver,FaceVerifyWindowService}.java`、`config/CompreFaceProperties.java`、`service/party/{PartyConsentService,impl/PartyConsentServiceImpl}.java`、`controller/admin/party/PartyConsentController.java`；测试 `FaceContractTest.java`、`FaceVerifyWindowServiceTest.java`、`MeetingFaceConsentGateTest.java`、`CompreFaceClientRemoteContractTest.java` |
| 前端 | `Demo-web/src/api/ai/face.ts`、`api/party/verify.ts`、`views/ai/meeting/{MeetingRoom.vue,components/FaceVerifyCard.vue,composables/useFaceVerification.ts,__tests__/faceVerifyCard.spec.ts}` |
| 部署件 | `Demo-deploy/compreface/{README.md,guide.md,docker-compose.yml,.env.example}`、`nginx/default.conf.template`、`scripts/{deploy,build-core,verify,status,stop,calibrate-threshold,enable-face-poc}.ps1`（`verify.ps1` 支持 `-CheckLatency/-CheckResidual`）、`build/core-build/`、`models/`、`evidence/{poc-enablement-record.md,g3/}` |
| 取证工具 | `Demo-deploy/tools/g01/{README.md,collect.html,g0-check-log.ps1,g1-eval-frames.ps1}`、`tools/e2e/face-verify-e2e.js`（`E2E_PARTY_ID` / `E2E_REAL_CAMERA=1`） |
| 设计/计划 | 原设计（历史对照）、本文件（生效）、`2026-11-04-meeting-ai-spec-review-and-revision.md`、`2026-11-05-ai-meeting-consolidated-revision.md`、`2026-11-05-meeting-ai-specs-implementation.md` |

---

## 11. 作废对照速查（旧 → 生效）

| 原设计旧口径 | 生效口径 |
|---|---|
| insightface `buffalo_l` 自建容器、512 维、`normed_embedding` | CompreFace 1.2.0 自定义镜像 + YuNet/SFace（128 维，服务侧内存） |
| `ai_face_gallery.embedding REAL[]` + Java 余弦 | 无底库、无向量；相似度由 CompreFace 返回 |
| `/v1/face/embed` + `X-Verify-Token` HMAC | 无 embed 端点；1:1 `verification/verify` 两图直传 |
| `enroll` / `gallery/status` / `gallery/delete`、菜单 9505/9507 | 全部删除；菜单口径仅 9506（本收敛版也未落菜单） |
| 判定表 11–18（8 值）、余弦 `0.45`、极差 `0.25` | §5 的 6 值；阈值 G2 帧域标定前为空 |
| worker `VideoStream` 取帧 + `/internal/face-event` | 浏览器焦点轨抓帧 + `/ai/meeting/face/verify` |
| 端口 `8030/8031`、`persistence:false`、V1–V6 | `8050/8051`；管理库存在且删除流程属 G3 必答；V1–V9 见 README §7 |
| `V3.56`/`V3.57`、`1_040_065_*`、28 条旧用例 | 收敛版不新增迁移/错误码；测试基线见 §8 |
