# 当事人证件核验（SP-5：身份证 OCR 一致性核验 + 单独同意留痕）设计

> **修订索引（2026-11-04，以 `2026-11-04-meeting-ai-spec-review-and-revision.md` 为准）**
> 1. **§12「类名与列名」自相矛盾订正**：原文把 `PartyApi` 列入「均已实读文件确认存在」清单（同句末尾又注「提议新增、当前不存在」）。实际情况：`Demo-module-uaa-api` 现暴露 11 个 `*Api`，**无 `PartyApi`**；`PartyIdentityForVerifyRespDTO` 同样零命中。两者都是**本文提议新增的设计态对象**，实施时从零添加，不得写成「复用现成 Feign」。
> 2. **「PP-OCRv6 已真实部署」措辞订正**：§0-P1、§2 事实 8/9、§12 涉及运行状态的判断，统一改为「`application-dev.yaml` 配置指向 `192.168.40.30:8080/ocr/v6/ocr`，`Demo-deploy/paddle/` 部署件存在；**仓库内无运行/联调证据**，`livekit-worker/README.md` 亦自陈未联调」。`PaddleOcrClient`/`OcrEngine*` 抽象及其测试真实存在，这部分不变。
> 3. **同意 scope 统一枚举来源**（对应 §7.1 DDL 注释、§9 M2）：`ai_party_consent.scope` 定版为 **5 值** `IDCARD_VERIFY | FACE_COMPARE | SER_ANALYSIS | VOICE_ANALYZE | VOICEPRINT_VERIFY`（2026-11-05 定版 D3，纳入 SP-6 声纹核验），六份 spec 共用同一张表、同一 `version` 等值语义、同一 `revoked_at` 撤回机制；`noticeConfirmed` 降级为操作人确认动作（写审计），不再充当单独同意凭据。
> 4. **§9 M2 移交项同步到 CompreFace 架构**：人像 1:1 比对已由用户裁决改用 CompreFace `POST /api/v1/verification/verify`（**不做 1:N、不建 subject 底库、平台不持有向量**），见 SP-3 顶部「覆盖性修订总纲」与评审方案 §4。因此本文 §1.2、§9 M2 中「人脸向量表 / 人像底库 / `FACE_MISMATCH` 预留」的描述改为：`ai_party_verify_record.verdict` 仍预留并扩充 `FACE_*` 族；证件照 `idCardFrontUrl` 只在**核验任务期**经 `FileApi.getFileContent` 临时取字节送比对，不再用于建立向量底库；`ai_face_gallery` 整表废弃。
> 5. **§0-P1 拆分结论保留**：SP-5 = 证件 OCR **文本**一致性核验（P1、零新模型），人像 1:1 移交 SP-3；`verdict` 十行判定表、MATCHED 唯一通过态、不改 `party_identity.status`、处置走 `/audit`、不存原图不存明文号码、日志负向测试 —— 全部继续有效。
> 6. **§3.3 `PartyApi` 路径基准保留**：一律 `/rpc-api/uaa/party`，不采用 `AiCapabilityApi` 的 `/admin-api` 第二风格；上线前须在网关验证 `/rpc-api` 不对外路由（评审方案 C25）。
> 7. **工程能力订正**：§13 交付清单中前端权限判断用 `accessStore.hasAccess(code)`（工程无 `hasPermission`）；新增端点只用 `get/post`（`request.ts` 无 `patch`，删除叫 `del`）。
> 8. **号段与实施顺序保留**：错误码 `1_040_063_*`、迁移 `V3.52–V3.54`、菜单 `9501–9504` 不变；实施顺序固定 **SP-1/2 → SP-5 → SP-4 → SP-3**，本文不得在 SP-1/2 未落地时单独上线。
> 9. **2026-11-05 校准（定版 D1–D6）**：scope 五值纳入 `VOICEPRINT_VERIFY`（D3）、§9 M2 正文改 CompreFace 1:1 无底库口径、§12「分期一致性」改 `FACE_*` 族；`verify_type` / `room_id` 归 **V3.56** 一次性建立（D4），不在 SP-5 交付；实施以 `2026-11-05-meeting-ai-specs-implementation.md` 的 D1–D6 为准。

- 日期：2026-11-04
- 状态：**代码层已实施并收口（2026-11-06）；§10.4/§10.5 的现场取证按用户裁决跳过，属「未取证」，不得写成验收通过，POC/投产开关一律不变**
- 上游文档：`2026-11-04-meeting-room-ui-design.md`（SP-1/SP-2，本文落实其 §1.2 划给 SP-5 的非目标）、`2026-11-03-meeting-ai-capability-design.md`
- 落地范围：`Demo-ai`（核验编排 + 新 Feign 提供方）、`Demo-basic/Demo-module-uaa`（底库读取 API）、`Demo-web`（当事人档案页核验入口）
- 本文所有类名、列名、接口路径、错误码段、迁移号、菜单 ID 均以**实读代码 + 全仓扫描**为准，出处逐条标在 §2

### 实施状态（2026-11-06）

| 项 | 状态 |
|---|---|
| §13 交付清单（V3.52–V3.54、5 个端点、`PartyApi` 与脱敏、五个错误码、线程池、页面入口、前端 API） | 已落地 |
| 真实 OCR 链路（此前只有 `UnconfiguredIdCardOcrGateway` 占位，恒判 `OCR_UNREADABLE`） | 已补齐：`PaddleIdCardOcrGateway` 取图字节 → PP-OCRv6 逐行 `lines/score` → `Demo_IDCARD_EXTRACT` 结构化抽取 → 正则降级 → GB 11643 校验位；`party.verify.ocr-enabled=false` 可显式回到诚实降级态 |
| 配置消费与合规（`party.verify.*` 此前写在 YAML 无人读取；同意版本等值、180 天留存） | 已补齐：`PartyVerifyProperties` + `PartyVerifyRetentionJob` + `consent-version` |
| uaa `get-sensitive` 审计（此前只有 `log.info`） | 已补齐：`PartyIdentitySensitiveAuditService` 落 `OperateLogApi`，日志不含明文 |
| 前端档案页明文收窄 + 核验卡片/同意采集入口 | 已补齐：`PartyVerifyCard.vue` 挂到 `views/uaa/partyIdentity/index.vue`，明文仅经单独授权端点按次取回 |
| 测试 | 单模块：ai-server 38 + uaa-server 4、前端 13 全绿；**收口全仓回归（2026-11-06）**：ai-server `-Dtest='Meeting*Test,RiskLexiconTest,Party*Test,IdCard*Test,Paddle*Test,Voiceprint*Test,VoiceGatewayEmbedding*Test,FaceContractTest'` → **149 passed / 0 failures**、uaa-server → **4 passed**、前端 `meeting+party+voiceprint` → **14 文件 117 passed**、worker unittest → **27 OK**；`mvn -o -B -DskipTests compile` → BUILD SUCCESS；本次改动文件 `vue-tsc` 0 错误；日志负向 `PartyVerifyLogHygieneTest` 已覆盖全链路 |
| 编排缺陷（实施中发现并修复） | 未认证/企业当事人此前仍会外呼 OCR 网关，违反 §3.2「前置门零外呼」；已在 `PartyVerifyServiceImpl.run` 短路 |
| 共享表扩展（2026-11-07） | `V3.56` 给 `ai_party_verify_record` 补 `verify_type VARCHAR(24) NOT NULL DEFAULT 'IDCARD'` / `room_id` 与人脸标量列，三能力共用一表；`PartyVerifyServiceImpl.start()` 显式写 `IDCARD`，`toVO` 对 FACE 用 `FaceVerdictResolver.labelOf()` 提供中性文案。V3.52 建表形态不变，脱敏与不改 `party_identity.status` 的红线不变 |
| 核验历史隔离（2026-11-07 续） | `GET /ai/party/verify/page` 新增 `verifyType`（默认 `IDCARD`，仅 `IDCARD/FACE/VOICEPRINT` 合法），Mapper 两条按类型过滤 SQL；证件档案页不再混显 FACE 结论。`PartyVerifyRecordPageTest` 3 例 + 前端 `verifyPage.spec.ts` 2 例回归。依赖 V3.56 先在共享库执行（缺列会报错，属预期防呆） |
| 当事人查阅与删除权（2026-11-07，C25 收口） | `GET /ai/party/verify/mine`、`POST /ai/party/verify/erase`（uaa 按登录账号反查当事人，含租户隔离）；**留存期策略定版**：记录留存 180 天到期逻辑删除、当事人主动删除立即生效、同意表只置 `revoked_at` 保留留痕；未绑定身份抛 `1_040_063_005` 不回退全部当事人；管理端不提供按 partyId 代办删除。详见 `2026-11-07-dev-closure-round5.md` §3 |
| **真实环境门禁（2026-11-06 用户裁决跳过）** | §11 填充率统计 SQL；网关验证 `/rpc-api` 不对外路由；§10.4 七步冒烟（需 40.30 OCR 可达）；§10.5 八项指标（≥50 张样本、队列满压测、P95 ≤15s）。**全部未取证、不得视为通过**；不置位任何 POC/投产开关，`party.verify.ocr-enabled` 需内网 OCR 可达后才可启用。工作区非 git 仓库，`git commit` 不适用 |
| 全仓构建（2026-11-06 复测订正） | `mvn -o -B -s settings.xml -pl Demo-ai-module/Demo-module-ai-server -DskipTests compile` → **BUILD SUCCESS**。补完过程中一次编译曾报 SP-6 `VoiceprintTemplateService` 找不到符号（3 处），系构建时序/增量缓存问题，该类源码与 `.class` 均在仓内且非空壳；此前登记的「全仓构建被 SP-6 阻塞」结论作废 |

---

## 0. 与上游设计的差异登记（评审先读这里）

| # | 上游原文 | 本文的决定 | 差异性质 | 理由 |
|---|---|---|---|---|
| P1 | SP-1/SP-2 §1.2 把「身份证人像 1:1 核验」整体列为 **SP-5 / P2** | **拆开重定义**：SP-5 = 证件 OCR 文本一致性核验（姓名 + 公民身份号码），**P1 且零新模型、零 GPU，现在就能交付**；人像 1:1 比对**移出 SP-5，并入 SP-3**（它的前置与人脸引擎完全同源） | 范围收缩 + 分期提前 | 实测 `party_identity` 底库字段齐全（`id_card_front_url`/`real_name`/`identity_no`）；`application-dev.yaml` 配置指向 `192.168.40.30:8080/ocr/v6/ocr` 且 `Demo-deploy/paddle/` 部署件存在（**【2026-11-04 订正】原写「已真实部署」，仓库内无运行/联调证据，`livekit-worker/README.md` 亦自陈未联调**）；Java 侧 `PaddleOcrClient` 与 OCR 引擎抽象（`OcrEngine`/`OcrEngineFactory`/`PaddleOcrEngine`/`VisionModelOcrEngine`）已落地带测试。把人像比对与文本核验捆在一起，会让一项今天能交付的能力被另一项没有的能力阻塞 |
| P2 | 上游未涉及同意留痕 | **新增 `ai_party_consent` 表**，把「处理敏感个人信息的单独同意」做成核验的前置硬门 | 新增必做项 | 全仓 `*.sql` grep `consent\|agree\|authoriz\|privacy` **无任何个人信息授权留痕表**（命中的全是「Demo协议书」业务文书与字典项）。公民身份号码 + 人脸 + 身份证件照片均属《个人信息保护法》第 28 条敏感个人信息，处理须单独同意并可举证；没有留痕表就无法证明取得过同意，这是合规缺口而不是优化项 |
| P3 | 上游 §1.2 表述为「跨服务 + 敏感个人信息」，未给通路 | 明确通路：**uaa 侧新增 `PartyApi` Feign**（现状 `Demo-module-uaa-api` 暴露 11 个 `*Api`，**没有 PartyApi**，见 §2 事实 5），身份证图片字节走 `FileApi.getFileContent(path, code)` | 补全实现路径 | 底库在 uaa 服务，ai 服务无现成取数通道；「跨服务」这句抽象描述会掩盖「API 要从零加」的真实工作量 |

### 0.1 本文顺带发现的一个现存安全缺陷（属必修，不是新设计）

`PartyIdentityController.java:33-42` 的分页接口**直接返回 DO 实体**：

```java
@GetMapping("/page")
@PreAuthorize("@ss.hasPermission('system:party-identity:query')")
public CommonResult<PageResult<PartyIdentityDO>> page(...)
```

`PartyIdentityDO` 含 `identityNo`（完整公民身份号码）、`realName`、`idCardFrontUrl`、`idCardBackUrl`，因此**凡持有 `system:party-identity:query` 权限的前端页面都能在列表里拿到明文身份证号与证件照 URL**。而该权限是「查询」粒度，不等于「可查看明文敏感字段」。

SP-5 上线前必须一并修（§8.3）：新增 `PartyIdentityRespVO`，列表默认脱敏（`identity_no` 输出 `3301**********1234` 形态），明文与证件照 URL 只在**单条详情 + 更高权限点 + 记审计**三个条件同时满足时返回。本缺陷与 SP-5 同源同表，分开修会重复改动，故并入本文交付。

---

## 1. 目标与范围

### 1.1 本期目标（P1）

1. **证件 OCR 一致性核验**：对已认证当事人（`status = 1`）的身份证正面照做 OCR，抽取「姓名 / 公民身份号码」，与 `party_identity` 底库记录逐项比对，产出**可解释、非定性**的核验结论（`verdict`），落核验记录表并可追溯。
2. **单独同意留痕**：新增 `ai_party_consent`，未取得有效同意则**拒绝发起核验**（前置硬门，不是提示）。
3. **公民身份号码校验位本地校验**：按 GB 11643—1999 加权 mod 11 算法本地校验 OCR 抽出的号码，拦截 OCR 误读，零模型成本。
4. **打通 uaa 底库读取通道**：新增 `PartyApi` Feign，服务端间传递，明文只在内网服务间流动。
5. 修复 §0.1 的明文暴露缺陷。
6. 核验结论进入Demo员/管理员可见的档案视图，**不自动改变认证状态**。

### 1.2 非目标（逐条给归属，不留悬空）

| 项 | 归属 | 本文如何交代 |
|---|---|---|
| 人像 1:1 比对（证件照 vs 会中/现场人脸）、人脸底库与向量检索 | SP-3 | §9 显式登记为移交项；本文的核验结论枚举预留 `FACE_MISMATCH` 取值位但**本期不产出**，DO 注释与迁移 COMMENT 均标明「SP-3 前恒不出现」 |
| 活体检测（防照片攻击） | SP-3 | 不设计、不提及可用性 |
| OCR 识别营业执照 / 统一社会信用代码一致性（`auth_type = 2` 企业） | P2 | 本文只实现自然人路径；企业当事人直接返回 `SKIPPED_ENTERPRISE`，不假装支持 |
| 公安部/权威源实名三要素核验（需外部付费接口，现无凭证） | 不做（无接口凭证，非本期也非后续计划） | 全文不引入任何外部实名接口；`verdict` 明确声明「仅系统内自洽性校验，不代表真实身份」 |
| 银行卡、手机号实名 | 不做 | 不在本文 |
| 认证状态自动驳回 / 自动失效 | 不做 | 处置始终由人：核验不通过只产生待办提示，`status` 变更仍走既有 `PartyIdentityController` 的 `/audit`（`system:party-identity:audit`） |

---

## 2. 读码核实的事实基线（本设计的唯一依据）

| # | 主题 | 事实 | 出处 |
|---|---|---|---|
| 1 | 底库实体 | `PartyIdentityDO` 存在，`@TableName(value = "party_identity", autoResultMap = true)` + `@KeySequence("party_identity_seq")`，**继承 `TenantBaseDO`**（故有 `tenant_id`/`creator`/`create_time`/`updater`/`update_time`/`deleted`）；字段 `id:Long`、`accountId:Long`、`authType:Integer`、`identityNo:String`、`realName:String`、`creditCode:String`、`idCardFrontUrl:String`、`idCardBackUrl:String`、`status:Integer`、`rejectReason:String` | `Demo-module-uaa/Demo-module-uaa-server/src/main/java/com/tianque/uaa/dal/dataobject/party/PartyIdentityDO.java:16-71` |
| 2 | 底库 DDL | PG 脚本：`id BIGINT NOT NULL DEFAULT nextval('party_identity_seq'::regclass)`；`CREATE INDEX idx_party_identity_account ON party_identity (account_id)`；**`CREATE UNIQUE INDEX uk_party_identity_no_auth ON party_identity (tenant_id, identity_no) WHERE status = 1 AND deleted = false`**（即「1 身份 = 1 账号」只在已认证态约束）；列注释与 DO 一致 | `Demo-docs/sql/party_account_postgres.sql:9,44-45,63-69` |
| 3 | 枚举 | `PartyIdentityTypeEnum` 1自然人 / 2企业；`PartyIdentityStatusEnum` 0待认证 1已认证 2已驳回 3已失效 | `Demo-module-uaa/.../enums/party/PartyIdentityTypeEnum.java`、`PartyIdentityStatusEnum.java`，并与 DO `:35-38`、`:61-64` 注释一致 |
| 4 | 既有服务与控制器 | `PartyIdentityController` 类级 `@RequestMapping("/uaa/party-identity")`，`GET /page`（`system:party-identity:query`）、`POST /audit`（`system:party-identity:audit`）；`PartyIdentityService`/`Impl`、`PartyAccountService`/`Impl`、`PartyAccountController`、`PartyAuthService` 均在 | `PartyIdentityController.java:26-47`、`service/party/` 与 `service/auth/party/` 目录列举 |
| 5 | **跨服务通道缺失** | `Demo-module-uaa-api` 仅暴露 11 个 Feign：`DeptApi`、`PostApi`、`LoginLogApi`、`MediatorApi`、`OrgApi`、`OrganizationApi`、`PermissionApi`、`RoleApi`、`SocialClientApi`、`SocialUserApi`、`AdminUserApi` —— **无任何 Party 相关 Api** → ai 服务取 `party_identity` 必须新增 `PartyApi` | `Demo-module-uaa-api` 目录列举；`UserProfileQueryToolFunction.java:7,26,36` 证明 ai 侧已有消费 uaa Feign 的先例（走 `AdminUserApi` + `TenantUtils.execute`） |
| 6 | 图片取字节 | `FileApi`（system 服务）已提供 `byte[] getFileContent(String path, String code)`（`GET PREFIX + "/content"`）与 `presignGetUrl(url, expirationSeconds, code)`、`getSignUrl(path, code)`；`PREFIX = ApiConstants.PREFIX + "/file"` | `Demo-module-system-api/.../api/file/FileApi.java:28-30,96-118,138-146` |
| 7 | OCR 客户端已落地 | `PaddleOcrClient.recognizeImage(MultipartFile, prompt)`：`service-type=remote` 时 hutool `HttpRequest.post(apiUrl).timeout(readTimeout).form("image", bytes, fileName)` + 头 `X-API-Key`；`parseOcrResponse` 适配 `data:[{text}]`；`service-type=local` 分支**显式抛「本地模型识别功能尚未实现」**（不是假数据） | `Demo-module-ai-server/.../core/client/PaddleOcrClient.java:41-53,58-90,95-107,112-158` |
| 8 | OCR 配置实值 | dev 与 local 均为 `paddle.ocr.service-type: remote`、`api-url: http://192.168.40.30:8080/ocr/v6/ocr`、`api-key: ${PADDLE_OCR_API_KEY:…}`、`connect-timeout: 30000`、`read-timeout: 120000`、`enable-cache: false`、`cache-expire-seconds: 3600`；注释指明契约见 `Demo-docs/ocr-image/PaddleOCR部署指南.md` | `Demo-module-ai-server/src/main/resources/application-dev.yaml:166-177`、`application-local.yaml:155-161` |
| 9 | OCR 服务真实形态 | 容器 `pp-ocrv6` 为 **CPU 推理、零显存**，只绑 `127.0.0.1:8011`，`OCR_ENABLE_MKLDNN` 必须 `false`（paddle 3.3.0 CPU + oneDNN(PIR) 与 `PP-OCRv6_medium_det` 不兼容会抛 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute`），`OCR_CPU_THREADS=10`；Nginx 是唯一对外入口且强制 `X-API-Key` | `Demo-deploy/paddle/docker-compose.yml:11-30,32-53`、`README.md:80-89` |
| 10 | OCR 接口契约 | `POST /ocr`（multipart `image`）与别名 `POST /api/ocr`；`GET /health` 返回 `{"status":"ok","gpu_available":false,"model":"PP-OCRv6_medium","ready":true}`；响应含 `data:[{text}]`（按行拼接全文）+ `lines:[{text,score,box}]` + `count`；服务端把字节流转 **RGB numpy** 再 `predict`，结果取 `result[i].json["res"]` 的 `rec_texts/rec_scores/rec_boxes` | `Demo-deploy/paddle/pp-ocrv6/app.py:5-7,79,102-105,130-132,136-153`、`README.md:45-63,91-98` |
| 11 | OCR 引擎抽象可复用 | `OcrEngine` 接口 + `OcrEngineFactory` + `PaddleOcrEngine` + `VisionModelOcrEngine` 均已实现并**各有测试类**；`OcrModeEnum` 三值 `traditional/vision/hybrid`；`VisionModelOcrEngine.recognize()` 真调 `aiLLMCallService.callModelForStructuredJsonWithMedia(bytes, contentType, promptCode, variables)`，逐图循环、单图失败仅 `log.warn` 不中断 | `service/capability/ocr/` 目录、`VisionModelOcrEngine.java:26-57,59-62`、`AiLLMCallService.java:99`、`AiLLMCallServiceImpl.java:800`，测试 `VisionModelOcrEngineTest.java`、`OcrEngineFactoryTest.java`、`PaddleOcrEngineTest.java`、`AiLLMCallServiceImplWithMediaTest.java` |
| 12 | Feign 前缀两种风格并存 | `AiApiConstants.NAME = "ai-server"`、`PREFIX = RpcConstants.RPC_API_PREFIX + "/ai"`，`RPC_API_PREFIX = "/rpc-api"`；**但** `AiCapabilityApi` 用的是硬编码 `String PREFIX = "/admin-api/ai/capability"`，并在 javadoc 说明「与 ai-server 既有 admin 控制器风格一致，且对齐网关 `Path=/admin-api/ai/**` 不剥离前缀，Feign 直连与 admin 前端均按完整前缀可达」 | `Demo-module-ai-api/.../api/enums/AiApiConstants.java`、`Demo-framework/.../RpcConstants.java`、`AiCapabilityApi.java:15-32` |
| 13 | 算力现状（决定本文边界） | GPU 仅存在于个人笔记本（`.env:14` 注释「本机 RTX 5070 Ti 为 0」，并备有 `paddleocr-genai-vllm-server:...sm120-offline` 镜像）；`PaddleOCR-VL` 文档解析因「vllm/torch 与 CUDA 12.8 冲突、native 后端多线程卡死」**已从 compose 撤下**，当前 `docker-compose.yml` 只有 `pp-ocrv6`(CPU) + nginx；生产实际被 Java 调用的是 `192.168.40.30` 上的 CPU 服务 | `Demo-deploy/paddle/.env:13-15,26-29`、`README.md:6-8`、`docker-compose.yml:10-30` |
| 14 | 敏感字段直出问题 | 分页接口签名 `CommonResult<PageResult<PartyIdentityDO>>`，DO 含 `identityNo`/`realName`/`idCardFrontUrl`/`idCardBackUrl` → 列表即明文 | `PartyIdentityController.java:33-42` |
| 15 | 同意留痕表不存在 | 全仓 `*.sql` grep `consent\|agree\|authoriz\|privacy\|告知` 命中的均为「Demo协议书」业务文书、字典项与 skill slug，**无个人信息授权表** | 扫描结果（本文 §0 P2） |
| 16 | 错误码段位 | `1_040_0xx` 子段已用 `000–004,006,008–016,024–026,061,062`；`1_040_061_000–004` 为会议（SP-1/2 追加 005–007），`1_040_062_000–006` 为语音；**`1_040_063_*` 全空闲** | `Demo-module-ai-server/.../util/ErrorCodeConstants.java` 全表扫描 |
| 17 | 迁移号 | `Demo-ai/docs/sql` 现存最新 `V3.48__meeting_minutes_prompt.sql`；SP-1/SP-2 已预定 `V3.49–V3.51`；仓库存在带字母后缀的补丁惯例（`V3.38a__fix_menu_id_conflict.sql`、`V3.39a__fix_project_dataset_menu_role_grant.sql`）→ 本文取 **V3.52–V3.54** | `docs/sql` 目录列举 |
| 18 | 菜单 ID | `9490–9494` 会议（V3.46）、`9495–9498` 语音演示（V3.47）、`9499–9500` 已被 SP-1/2 预定；`docs/uaa_menu.sql:724-773` 出现的 `9510/9511/9520/9530/9550/9551` 是 **`sort` 列取值而非 `id`**（列序为 `id,name,permission,type,sort,parent_id,path,…`）→ 本文取 **`9501–9504`** 不与任何 ID 冲突 | `V3.46__meeting_menu.sql:4,13`、`V3.47__voice_demo_menu.sql:14`、`docs/uaa_menu.sql:724-732,772-773` |
| 19 | 表风格范式 | ai 侧 PG 迁移统一 `BIGSERIAL` + 审计列 + `tenant_id` + 部分唯一索引 `WHERE deleted = FALSE`（V3.45、V3.49 同构） | `docs/sql/V3.45__meeting_tables.sql`、SP-1/2 §7.1 |

---

## 3. 架构与数据通路

### 3.1 编排位置的选择

核验编排放 **ai-server**，不放 uaa：

1. OCR 客户端与 OCR 引擎抽象都在 ai-server（事实 7、11），放 uaa 会让认证服务反向依赖 AI 服务。
2. uaa 是账号/认证服务，引入模型调用会污染其可用性边界（登录链路不能被 OCR 拖慢）。
3. 方向：`ai-server → uaa(取底库) → system(取图片字节) → 40.30(OCR)`，全部为 ai-server 主动出向调用，uaa 与 system 不感知 AI 存在。

### 3.2 端到端数据流

```
0 前置门（缺任一即拒绝发起，不做「先跑了再说」）
   ├ 当事人 `status = 1`（已认证）？           否 → NOT_VERIFIED
   ├ `auth_type = 1`（自然人）？               否 → SKIPPED_ENTERPRISE
   ├ `id_card_front_url` 非空？               否 → IMAGE_UNAVAILABLE
   └ 存在有效单独同意（`ai_party_consent`）？  否 → 抛 1_040_063_000，零外呼
1 PartyApi.getIdentityForVerify(partyId)  → Feign → uaa-server
   （返回内部 DTO，含明文 identity_no/real_name 与图片 URL；仅服务端间可达，不暴露给前端）
   └ uaa 不可达 / 记录不存在 → 1_040_063_001
2 FileApi.getFileContent(path = id_card_front_url, code = <仓库编码>) → byte[]
   └ 抛异常或空字节 → IMAGE_UNAVAILABLE（记录 fail_stage='file'）
3 OCR 取文本（默认 traditional，见 §5.1）
   POST {paddle.ocr.api-url}  multipart image + X-API-Key，读超时 120s
   → lines:[{text, score, box}]
   └ HTTP 非 2xx / 超时 / lines 空 → OCR_UNREADABLE（记录 fail_stage='ocr'）
4 大模型结构化抽取（仅对 lines 文本，不再传图）
   callModelForStructuredJson(textOf(lines), "Demo_IDCARD_EXTRACT", vars, IDCARD_JSON_SCHEMA)
   → { name, idNo, birthDate, address, sex, nation, overallQuality }
   └ 模型异常/非法 JSON → 1_040_063_002，但**仍保留第 3 步的 lines**，改走 §5.3 正则降级抽取
5 本地零成本校验（不依赖模型）
   ├ 公民身份号码 18 位 + GB 11643 校验位（§5.4）
   ├ 出生日期与号码第 7–14 位一致性
   └ 号码前 6 位与地址首位省份行政区划自洽（仅记 warn，不作不通过依据）
6 与底库逐项比对 → 计算 verdict（§4 判定表，自上而下短路）
7 落 ai_party_verify_record（脱敏列 + 结论 + 依据 + 耗时 + 是否调用模型）
8 写审计 AiConfigOperateLogService.record("PARTY_IDCARD_VERIFY", …, result)
9 返回给前端的是脱敏结论，**永不回传完整证件号与图片字节**
```

**成本与时序约束**：单次核验串行链路为 `取库(RPC) → 取图(Feign) → OCR(最坏 120s) → 大模型(1.5–4s)`，**最坏情况远大于同步可接受范围**。因此核验**必须异步**：接口立即返回 `verifyId`（`PENDING`），前端轮询 `GET /ai/party/verify/get`；编排线程复用 SP-1/2 §6.6 已确立的专用线程池范式，本文新建 `partyVerifyExecutor`（core 1 / max 2 / queue 50 / `AbortPolicy`，理由同「不得拖累调用线程 + 队列满宁可拒绝不可阻塞」）。

### 3.3 新增 Feign：PartyApi（uaa 侧提供）

置于 `Demo-module-uaa-api/.../api/party/PartyApi.java`，对齐 uaa 既有 Api 风格：

```java
@FeignClient(name = ApiConstants.NAME)   // uaa 服务名
public interface PartyApi {
    String PREFIX = ApiConstants.PREFIX + "/party";

    /** 供 ai-server 证件核验取底库；返回明文敏感字段，故路径在 /rpc-api 下，不经网关暴露 */
    @GetMapping(PREFIX + "/identity-for-verify")
    CommonResult<PartyIdentityForVerifyRespDTO> getIdentityForVerify(@RequestParam("id") Long id);
}
```

`PartyIdentityForVerifyRespDTO { partyId:Long, accountId:Long, authType:Integer, identityNo:String, realName:String, creditCode:String, idCardFrontUrl:String, status:Integer, tenantId:Long }`。

三点必须写死在实现里：

1. **路径基准 `/rpc-api/uaa/party`**（`RpcConstants.RPC_API_PREFIX = "/rpc-api"`），**不得**采用 `AiCapabilityApi` 那种硬编码 `/admin-api/...` 的第二风格；新增 RpcApi 一律 `/rpc-api` 前缀，理由见 §9 遗留项 L2。
2. `@PermitAll` + 依赖内网 `/rpc-api` 不对外路由，与框架既有 RpcApi 一致；**并在方法上加 `@PreAuthorize` 的反向保护说明注释**，防止有人后续把它挂到 admin 控制器路径。
3. 查询必须带租户上下文（`TenantUtils.execute`，范式见事实 5 的 `UserProfileQueryToolFunction:35`），否则跨租户取号即越权。

---

## 4. 核验判定规则（`PartyVerifyVerdict` 枚举，自上而下短路，无自由裁量）

| 序 | 条件 | `verdict` | 中文文案（前端只渲染，不拼接） | 是否计入「不通过」 |
|---|---|---|---|---|
| 1 | 当事人不存在或 `status != 1` | `NOT_VERIFIED` | 底库无已认证记录，无法核验 | 否（未知，不判负） |
| 2 | `auth_type = 2`（企业） | `SKIPPED_ENTERPRISE` | 企业类型当事人不适用身份证核验 | 否 |
| 3 | 无有效单独同意 | 不落记录 | 抛 `1_040_063_000`，零外呼 | 否（拒绝发起） |
| 4 | 图片取不到（URL 空 / FileApi 失败 / 0 字节） | `IMAGE_UNAVAILABLE` | 证件照片不可获取，核验未完成 | 否（未完成 ≠ 不通过） |
| 5 | OCR 失败或无可用行 | `OCR_UNREADABLE` | 证件照片无法识别，建议重新上传清晰照片 | 否 |
| 6 | 抽不到号码，或号码校验位不通过且降级正则也失败 | `ID_NO_UNREADABLE` | 证件号码无法可靠识别 | 否 |
| 7 | 号码校验位不通过但可读出（OCR 读清了却与国标不符） | `ID_NO_INVALID_CHECKSUM` | 识别出的号码不符合校验规则，可能是照片遮挡或误读 | 否 |
| 8 | 号码与底库 `identity_no` 不一致（忽略末位 X 大小写、忽略空格） | `ID_NO_MISMATCH` | **识别号码与系统登记号码不一致** | **是** |
| 9 | 号码一致、姓名不一致（忽略全半角括号与空格差异） | `NAME_MISMATCH` | 识别姓名与系统登记姓名不一致 | **是** |
| 10 | 号码与姓名均一致 | `MATCHED` | 证件信息与系统登记一致 | 否（通过） |

**四条硬不变量**（写进单测钉死）：

- ① `MATCHED` 是唯一「通过」态；`ID_NO_MISMATCH`/`NAME_MISMATCH` 是仅有的两个「不通过」态；其余一律 **unknown/unreadable**，不得在任何文案里表述为「非本人」「假冒」「欺诈」。
- ② 号码不一致（序 8）优先于姓名不一致（序 9）：号码是主键级锚点（事实 2 的唯一索引即以 `identity_no` 为锚），姓名同音异字极常见。
- ③ 本文所有结论均为「**系统内自洽性校验**」，即「照片上的字 vs 库里存的字」是否一致；**不代表**「照片上的人是不是本人」、**不代表**「该号码真实存在且属于此人」。文案与 `verdict` 注释都必须体现这条边界（对齐 SP-1/2「不落定性结论」原则，且在法律场景更严格）。
- ④ 核验**永不修改** `party_identity.status`；状态变更仍只能走 uaa 的 `/audit`。

---

## 5. OCR 与要素抽取契约

### 5.1 模式选择（复用既有 `OcrModeEnum`，不新造枚举）

| 模式 | 通路 | 本文用法 |
|---|---|---|
| `traditional` | `PaddleOcrEngine` → PP-OCRv6（CPU；**配置指向 `192.168.40.30:8080` + `Demo-deploy/paddle/` 部署件存在，运行/联调证据缺失**） | **默认**。逐行文本 + 逐行 `score`，可作号码可信度门槛；18 位数字这种强格式内容，传统 OCR 的字符级可控性优于让大模型「看图复述」。2026-11-06 按 C21 就地订正：不得写成「已部署」 |
| `vision` | `VisionModelOcrEngine` → `callModelForStructuredJsonWithMedia` | **降级/补充**。PP-OCRv6 全行 `score < 0.6` 或 `lines` 为空时启用（多模态对模糊、倾斜、遮挡更鲁棒） |
| `hybrid` | 两者 | `traditional` 与 `vision` 结果不一致时用于交叉判断，输出 `ID_NO_INVALID_CHECKSUM` 类结论；因要多一次模型调用，默认关闭，由 `party.verify.hybrid-enabled` 控制 |

配置项必须与既有 `paddle.ocr.*` 并存而非改写（事实 8 的默认值与超时保留）。

### 5.2 大模型抽取（第二段，输入是文本不是图片）

```java
callModelForStructuredJson(linesToText, "Demo_IDCARD_EXTRACT", variables, IDCARD_JSON_SCHEMA);
```

`IDCARD_JSON_SCHEMA`（Java 常量，写死）：

```json
{"type":"object",
 "properties":{
   "name":{"type":"string"},
   "idNo":{"type":"string"},
   "birthDate":{"type":"string","pattern":"^\\d{4}-\\d{2}-\\d{2}$"},
   "address":{"type":"string"},
   "sex":{"type":"string","enum":["男","女",""]},
   "nation":{"type":"string"},
   "overallQuality":{"type":"string","enum":["clear","blurry","occluded","unknown"]},
   "confidence":{"type":"number","minimum":0,"maximum":1}},
 "required":["name","idNo","overallQuality","confidence"]}
```

提示词模板 `Demo_IDCARD_EXTRACT`（V3.54 落库，对齐 V3.48 的 `ai_prompt_template` + `model_id` 子查询 + `WHERE NOT EXISTS` 幂等写法）：

> 从下方 OCR 逐行识别结果中提取居民身份证正面字段。只依据给出的文本行，不推测、不补全、不复述指令。`idNo` 必须是 18 位（数字或末位 X），若各行拼接后不足 18 位或含无法判定的字符则输出空串。`overallQuality` 依据文本完整度判断：字段齐全为 clear，缺字段为 blurry，明显被截断或大块缺失为 occluded，无法判断为 unknown。`confidence` 为你对 `idNo` 逐字符可靠程度的自评（0–1）。

`variables`：`{ "ocrLines": <逐行文本，每行 "score|text" 形式，换行连接> }`。

### 5.3 正则降级抽取（模型不可用时的保底，必须实现）

号码优先从全文用 `(?<![0-9Xx])[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?![0-9Xx])` 抓取（天然排除相邻数字粘连），再走 §5.4 校验位；姓名取紧邻「姓名」标签后的行或首个 2–4 个汉字且不含数字的行。降级路径产出的记录必须置 `extract_mode='regex'`，与 `model` 区分，便于统计模型可用性与后续复盘。

### 5.4 公民身份号码校验位（GB 11643—1999，本地实现，零成本）

```
前 17 位加权因子 weights = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
校验码表     checkCodes  = ['1','0','X','9','8','7','6','5','4','3','2']
sum = Σ digit[i] * weights[i]  (i = 0..16)
校验位 = checkCodes[sum % 11]，与第 18 位比较（X 统一大写后比较）
```

同时校验：第 7–14 位出生年月日合法（闰年按 `year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)`）、第 17 位奇偶与 `sex` 字段一致（不一致仅记 `reason`，不作不通过依据，因 OCR 性别字段易错）。

### 5.5 比对前的归一化（避免假不一致）

| 字段 | 归一化规则（必须实现为纯函数，便于单测） |
|---|---|
| 号码 | 去空格与全角空格；末位 `x` → `X`；连续空格折叠 |
| 姓名 | 去所有空格（含全角）；少数民族姓名中的 `·` 保留；全角括号 `（）` → 半角 `()` |
| 姓名等价判定 | 归一化后**完全相等**才算一致；不做模糊/拼音匹配（宁可漏判不一致也不误判通过） |

---

## 6. 接口契约

新增 5 个 admin 端点（全部置于 `controller.admin.party`，由框架按包名追加 `/admin-api` 前缀，mapping 字面量**不含前缀**——遵循 SP-1/2 §6.5 已查明的双前缀教训）：

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/ai/party/verify/idcard` | POST | `ai:party-verify:idcard` | 发起核验；body `IdCardVerifyReqVO{ partyId:Long@NotNull, consentId:Long }`；立即返回 `verifyId` + `status=PENDING` |
| `/ai/party/verify/get` | GET | `ai:party-verify:query` | `?verifyId=` 轮询取结果（含 verdict 与脱敏依据） |
| `/ai/party/verify/page` | GET | `ai:party-verify:query` | 按当事人分页查历史核验记录（只出脱敏列） |
| `/ai/party/consent/grant` | POST | `ai:party-consent:grant` | 记录单独同意；body `ConsentGrantReqVO{ partyId, scope:"IDCARD_VERIFY", version, source }` |
| `/ai/party/consent/status` | GET | `ai:party-verify:query` | `?partyId=` 返回当前有效同意状态（无则前端呈现同意采集入口） |

`PartyVerifyRecordVO { id, partyId, authType, verdict, verdictLabel, matchedName(Boolean|null), matchedIdNo(Boolean|null), ocrNameMasked(String|null), ocrIdNoMasked(String|null), ocrConfidence(BigDecimal|null), extractMode('model'|'regex'|'hybrid'), modelCalled(Boolean), failStage('file'|'ocr'|'model'|null), elapsedMs(Integer), operatorId, operatorName, consentId, createTime }`。

**明确不出现在任何 VO 的字段**：完整 `identity_no`、完整 OCR 号码、`id_card_front_url`、图片字节。

`PartyConsentVO { partyId, scope, version, granted(Boolean), grantedAt, grantedBy, source, revokedAt }`。

### 6.2 错误码（`1_040_063_*`，事实 16 确认该段空闲）

```
1_040_063_000  处理当事人证件信息前须取得单独同意: {}
1_040_063_001  当事人身份底库读取失败: {}
1_040_063_002  证件要素抽取失败: {}
1_040_063_003  核验任务不存在: {}
1_040_063_004  证件核验服务繁忙，请稍后重试（线程池队列已满被拒绝）
```

---

## 7. 数据表与迁移（PG 方言，对齐事实 19 的 V3.45 风格）

| 文件 | 内容 |
|---|---|
| `V3.52__party_verify_tables.sql` | `ai_party_verify_record` + `ai_party_consent` 两张新表 |
| `V3.53__party_verify_menu.sql` | 菜单 ID 段 9501–9504 + 超管授权 |
| `V3.54__party_idcard_extract_prompt.sql` | 提示词模板 `Demo_IDCARD_EXTRACT`（对齐 V3.48 幂等写法） |

### 7.1 V3.52 DDL

```sql
BEGIN;

-- 单独同意留痕（合规举证依据）
CREATE TABLE IF NOT EXISTS ai_party_consent (
  id            BIGSERIAL    NOT NULL,
  party_id      BIGINT       NOT NULL,
  scope         VARCHAR(48)  NOT NULL,                 -- 五值见定版决议 D3
  version       VARCHAR(16)  NOT NULL,                 -- 告知文本版本号，文案改了必须升版
  granted       BOOLEAN      NOT NULL DEFAULT TRUE,
  source        VARCHAR(32)  NOT NULL DEFAULT 'ADMIN',  -- ADMIN / PARTY_APP / SMS_LINK
  granted_by    BIGINT,                                 -- 操作人；当事人本人自授时存其 accountId
  granted_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at    TIMESTAMP,                              -- 撤回时间（不删行，留痕要求）
  remark        VARCHAR(256),
  creator       VARCHAR(64)  DEFAULT '',
  create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater       VARCHAR(64)  DEFAULT '',
  update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id     BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_party_consent IS '当事人个人信息处理单独同意留痕（撤回只置 revoked_at，不物理删除）';
COMMENT ON COLUMN ai_party_consent.scope IS 'IDCARD_VERIFY / FACE_COMPARE / SER_ANALYSIS / VOICE_ANALYZE / VOICEPRINT_VERIFY（统一五值，见定版决议 D3）';
COMMENT ON COLUMN ai_party_consent.version IS '告知文案版本，版本变更须重新取得同意';
-- 同一当事人同一范围至多一条「未撤回且未删除」的有效同意
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_party_consent_active
  ON ai_party_consent (tenant_id, party_id, scope) WHERE revoked_at IS NULL AND deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_ai_party_consent_party ON ai_party_consent (party_id);

-- 核验记录
CREATE TABLE IF NOT EXISTS ai_party_verify_record (
  id                BIGSERIAL    NOT NULL,
  party_id          BIGINT       NOT NULL,
  account_id        BIGINT,                             -- 冗余，便于与账号维度审计串联
  auth_type         SMALLINT     NOT NULL,              -- 1自然人 2企业
  verdict           VARCHAR(32)  NOT NULL DEFAULT 'PENDING',
  matched_name      BOOLEAN,                            -- 三值：true/false/未完成
  matched_id_no     BOOLEAN,
  ocr_name_masked   VARCHAR(64),                        -- 脱敏后姓名，如「张*/」
  ocr_id_no_masked  VARCHAR(24),                        -- 脱敏后号码，如「3301**********1234」
  ocr_confidence    NUMERIC(4,3),                       -- 模型自评 0–1
  extract_mode      VARCHAR(16),                        -- model / regex / hybrid
  model_called      BOOLEAN      NOT NULL DEFAULT FALSE,
  ocr_lines_count   INT,                                -- PP-OCRv6 返回行数，便于排查
  avg_line_score    NUMERIC(4,3),                       -- 逐行 score 均值
  fail_stage        VARCHAR(16),                        -- file / ocr / model
  reason            VARCHAR(512),                       -- 人可读依据（不含明文证件号）
  status            VARCHAR(16)  NOT NULL DEFAULT 'PENDING', -- PENDING/SUCCESS/FAILED/REJECTED
  consent_id        BIGINT,                             -- 援引的同意记录
  operator_id       BIGINT,
  operator_name     VARCHAR(64),
  elapsed_ms        INT,
  creator           VARCHAR(64)  DEFAULT '',
  create_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater           VARCHAR(64)  DEFAULT '',
  update_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id         BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_party_verify_record IS '当事人证件 OCR 一致性核验记录；仅存脱敏结果，不存原图与完整号码';
COMMENT ON COLUMN ai_party_verify_record.verdict IS 'PartyVerifyVerdict 枚举；系统内自洽性校验结论，不代表真实身份';
COMMENT ON COLUMN ai_party_verify_record.ocr_id_no_masked IS '识别号码脱敏形态，明文号码一律不落库';
CREATE INDEX IF NOT EXISTS idx_ai_party_verify_party ON ai_party_verify_record (party_id, create_time);
CREATE INDEX IF NOT EXISTS idx_ai_party_verify_status ON ai_party_verify_record (status);

COMMIT;
-- 回滚：DROP TABLE IF EXISTS ai_party_verify_record, ai_party_consent;
```

**两条设计取舍必须记录**：

1. **不存原图、不存完整号码**：`id_card_front_url` 已在 `party_identity` 里，核验记录只需能指回底库记录；再存一份等于**多复制一份敏感个人信息**，与「最小必要」原则相悖。`ocr_id_no_masked` 足够支撑人工复核。
2. **`status` 与 `verdict` 分列**：`status` 是任务生命周期（PENDING/SUCCESS/FAILED/REJECTED），`verdict` 是业务结论；混淆两者会导致「OCR 挂了」被统计成「核验不通过」。§4 的序 4–7 全部是 `status='SUCCESS'` 而 verdict 为 unknown 态。

---

## 8. 合规与安全

### 8.1 单独同意前置门

- 未取得 `scope='IDCARD_VERIFY'` 且未撤回、且 `version` 与当前告知文本版本一致的同意记录 → **拒绝发起**（`1_040_063_000`），且在**任何外呼之前**判定（不先取图再问同意）。
- 告知文本必须包含：处理目的（核验登记信息一致性）、处理方式（OCR + 大模型抽取）、处理范围（姓名、公民身份号码、证件照片）、**不构成身份真实性认证**、留存期限、撤回方式。
- 版本升级后旧同意自动失效（用 `version` 等值判定，不做「默示沿用」）。
- 撤回：置 `revoked_at`，不删行；撤回后新发起被拒，历史记录保留（否则无法举证「曾经取得过、何时撤回」）。

### 8.2 数据最小化与留存

| 数据 | 处理 |
|---|---|
| 身份证图片字节 | 仅内存传递，**不写磁盘、不落对象存储、不进日志**；OCR 响应图片相关字段一律不持久化 |
| 明文公民身份号码 | 不新增落库；核验记录只存脱敏形态；日志禁止打印（实现时 `log` 语句只允许 `partyId`/`verdict`，加断言测试） |
| OCR 逐行原文 | 只存 `ocr_lines_count` 与 `avg_line_score` 两个统计量，原文不落库（原文即明文来源） |
| 留存期 | `party.verify.retention-days`（默认 180）；到期由既有清理任务置 `deleted = TRUE`（逻辑删除，符合既有 `deleted` 语义） |

### 8.3 修复 §0.1 的明文暴露（本期必做）

- `PartyIdentityController.page` 返回类型改为 `CommonResult<PageResult<PartyIdentityRespVO>>`，新增 `PartyIdentityConvert`：列表态强制脱敏 `identityNo`、**不输出** `idCardFrontUrl`/`idCardBackUrl`。
- 新增单条详情 `GET /uaa/party-identity/get-sensitive?id=`，权限 `system:party-identity:sensitive-query`（菜单 9504），返回明文并**每次写审计**。
- 前端既有当事人档案页改为消费脱敏字段（`Demo-web` 对应视图，字段名不变，值形态变化）。
- 迁移同步给新权限点建行，避免上线即 403。

### 8.4 权限点与菜单（V3.53，ID 段 9501–9504）

| ID | 名称 | permission | type | parent |
|---|---|---|---|---|
| 9501 | 证件核验 | `ai:party-verify:query` | 2 | 会议/当事人档案挂载点由前端路由决定，parent 取既有当事人档案菜单 ID |
| 9502 | 发起证件核验 | `ai:party-verify:idcard` | 3 | 9501 |
| 9503 | 采集单独同意 | `ai:party-consent:grant` | 3 | 9501 |
| 9504 | 查看证件明文 | `system:party-identity:sensitive-query` | 3 | 9501 |

沿用 V3.46 的防呆段占用检查（`SELECT count(*) … BETWEEN 9501 AND 9504 > 0 → RAISE EXCEPTION`）与 `ON CONFLICT` 幂等，超管授权 `role_id=1, tenant_id=1, id = 100000 + menu_id`。

---

## 9. 对既有设计的修订登记与移交项

| # | 目标文档 | 修订内容 |
|---|---|---|
| M1 | SP-1/SP-2 §1.2 | 「身份证人像 1:1 核验」整条描述改为：证件 OCR 文本一致性核验 = **SP-5 本期**；人像 1:1 比对 = **移交 SP-3**。避免后续读者以为 SP-5 会产出人脸相关结论 |
| M2 | SP-3（CompreFace 版） | 接收移交项：`party_identity.id_card_front_url` 只在**核验任务期**经 `FileApi.getFileContent` 临时取字节，与会中帧一起送 CompreFace `POST /api/v1/verification/verify` 做 **1:1 两图比对**；**不建 subject 底库、不建人脸向量表、平台不持有向量**（`ai_face_gallery` 整表废弃）。`ai_party_verify_record.verdict` 的 `FACE_*` 族由 SP-3 总纲 B 定义；人脸核验复用本表 `ai_party_consent` 的 `FACE_COMPARE` 取值，不得另建一套同意模型 |
| M3 | SP-3/SP-4/SP-5 共同 | `getCapabilities()` 谎报问题（上游 §0 D3）修复后，三者的可用性判定应统一改由该方法提供，而不是各自硬编码 `available=false` |
| L1 | 遗留 | PP-OCRv6 `read-timeout: 120000`（事实 8）意味着一次核验最坏占用核验线程 2 分钟；线程池 max 2 时并发 2 张模糊证件即可占满。故队列 50 + `AbortPolicy` + `1_040_063_004` 是必要保护，不是可选优化 |
| L2 | 遗留 | `AiCapabilityApi` 用 `/admin-api/ai/capability`（事实 12）与框架 `/rpc-api` 惯例并存，属既有不一致。本文新增的 `PartyApi` 一律 `/rpc-api/uaa/party`，不扩大第二种风格的面积；`AiCapabilityApi` 的归一化另开小改造，不塞进本文 |
| L3 | 遗留 → **C25 已收口（2026-11-06）** | 原写「`paddle.ocr.api-key` 默认值硬编码在 `application-dev.yaml:174`，建议改为无默认值 + 启动校验，不在本文范围」。现已落实：`application-dev.yaml` / `application-local.yaml` 改为 `${PADDLE_OCR_API_KEY:}`（无明文默认值）；`OcrConfigHelper.validateApiKeyConfiguration()` 启动期告警；`PaddleOcrClient.requireApiKey()` 调用期 fail-closed；`PaddleOcrClientApiKeyTest` 回归。本地/部署需显式注入该环境变量，详见评审方案 §8 |

---

## 10. 测试与验收

### 10.1 后端单测（JUnit5 + Mockito，测试类镜像被测类包结构）

| 测试类 | 必录用例 |
|---|---|
| `PartyVerifyVerdictResolverTest` | §4 十行判定表逐行一条参数化用例（10 例）；重点钉死：序 8 优先于序 9（号码与姓名同时不一致 → `ID_NO_MISMATCH`）；`status='SUCCESS'` 但 verdict 为 unknown 态时不得计入不通过 |
| `IdCardChecksumTest` | 合法号码通过；末位 `x` 大写等价；篡改任一位必失败；17 位/19 位/含非法字符 → false；出生日期段 `19990230` 非法；第 17 位奇偶与 `sex` 不一致仅记 reason 不判负 |
| `IdCardNormalizeTest` | 全角空格、内部空格、全半角括号、`·` 保留；归一化后同名为 true；**模糊/拼音不算一致**（如「张三」vs「张山」→ false） |
| `PartyVerifyOrchestrationTest` | ①无有效同意 → 抛 `1_040_063_000` 且 `verify(fileApi, never())`、`verify(ocr, never())`（**前置门在任何外呼之前**）；②`status != 1` → `NOT_VERIFIED` 零外呼；③`auth_type=2` → `SKIPPED_ENTERPRISE` 零外呼；④取图失败 → `IMAGE_UNAVAILABLE`、`fail_stage='file'`；⑤OCR 空 → `OCR_UNREADABLE`；⑥模型异常 → 走 regex 且 `extract_mode='regex'`；⑦全链路成功 → 落库 + 审计 `record(...,"success")` 被调 |
| `PartyConsentServiceImplTest` | 有效同意判定（`granted=TRUE AND revoked_at IS NULL AND version=当前`）；撤回后新发起被拒；版本升级后旧同意失效；同 `(tenant,party,scope)` 二次授予不违反 `uk_ai_party_consent_active`（走幂等更新或明确拒绝，实现取其一并在测试钉死） |
| `PartyApiImplTest` | 跨租户取数被 `TenantUtils` 上下文隔离（A 租户 id 在 B 租户上下文查不到）；返回 DTO 含 URL 与明文号码（供服务端），且不复用给前端 VO |
| `PartyIdentityRespVOTest`（§8.3 回归锁） | 分页返回体中 `identityNo` 为脱敏形态、`idCardFrontUrl` 为 null；断言序列化 JSON **不含** 18 位号码正则匹配（防止将来有人把 DO 直接换回去） |

### 10.2 日志与泄漏的负向测试（本文特有，不可省）

- `PartyVerifyLogHygieneTest`：以 appender 捕获核验链路全部日志行，断言无任何行匹配 `\d{17}[\dXx]`，且不含图片 base64/字节流特征。理由：证件号一旦进 ELK 就等于二次扩散，这是唯一能在 CI 阶段拦住它的机制。

### 10.3 前端 vitest

| 文件 | 用例 |
|---|---|
| `partyVerify.spec.ts` | `verdict → 展示态` 映射覆盖全部 10 个取值；unknown 类不得渲染成红色不通过；PENDING 轮询到终态停止；VO 无明文号码时页面不出现「请输入身份证号」类补全入口 |
| `partyConsent.spec.ts` | 无有效同意时「发起核验」按钮 disabled 且 title 指向同意采集；version 变更后重新要求同意 |

### 10.4 端到端冒烟（内网，需 40.30 OCR 可达）

```powershell
# 1) 未采集同意直接发起 → 期望 {"code":1040063000,...}，且 OCR 服务侧无访问日志（零外呼验证）
# 2) 采集同意后对真实 partyId 发起 → 立即返回 verifyId + status=PENDING
# 3) 轮询 GET /ai/party/verify/get → 终态 verdict ∈ §4 十值之一，elapsedMs 有值
# 4) 查库 ai_party_verify_record → ocr_id_no_masked 为脱敏形态、无明文；model_called 与实际调用一致
# 5) 换一张护照图片（URL 指向非身份证）→ verdict=OCR_UNREADABLE 或 ID_NO_UNREADABLE，不得抛未捕获异常
# 6) 把底库 identity_no 人为改一位再核验 → verdict=ID_NO_MISMATCH，party_identity.status 不变
# 7) 当事人档案页列表 → 身份证号为脱敏、无证件照 URL（§8.3 修复验证）
```

### 10.5 验收指标

| 指标 | 阈值 | 口径 |
|---|---|---|
| 同意前置门 | 无同意时 OCR/模型/文件服务外呼次数 = 0 | §10.1 用例① + §10.4 步骤 1 |
| 号码识别准确率（真实清晰证件样本 ≥ 50 张） | 校验位通过的号码占比 ≥ 90% | 冒烟样本集统计 `ID_NO_INVALID_CHECKSUM` + `ID_NO_UNREADABLE` 比例 |
| 一致当事人误判为不通过 | = 0 | 对底库来源即该证件的样本，verdict 必为 `MATCHED` |
| 明文零落库零入日志 | 0 条 | `PartyVerifyLogHygieneTest` + 对 `reason`/`remark` 列的正则抽检 |
| 定性措辞 | 出现次数 = 0 | 对全部 `verdictLabel` 与前端文案 grep「非本人/假冒/欺诈/认定」 |
| 状态不变量 | 核验前后 `party_identity.status` 恒等 | §10.4 步骤 6 + 单测断言 |
| 线程池保护 | 队列满返回 `1_040_063_004`，不阻塞 HTTP 线程 | 压测并发 60 发起 |
| 单次核验 P95 时延 | ≤ 15s（CPU OCR，不含排队） | `elapsed_ms` 分布 |

---

## 11. 风险与遗留

| 项 | 状态 | 处置 |
|---|---|---|
| PP-OCRv6 是 CPU 单实例（`OCR_CPU_THREADS=10`，`docker-compose.yml` 无 replicas） | 核验为异步 + 小线程池，不会拖垮在线链路，但吞吐受限 | 上线前用 §10.4 步骤 3 实测单张耗时；若 P95 超 15s 则先加副本再加功能 |
| GPU 生产可用性未定（事实 13：GPU 在个人笔记本，且 VL 因 CUDA 12.8 已撤） | 本文**不依赖 GPU**：默认 `traditional`（CPU OCR），`vision` 仅在降级时用多模态大模型（走既有 `callModelForStructuredJsonWithMedia`，由模型负载均衡选路）。若后续确认可用 GPU，`hybrid-enabled` 开关即可开启交叉判断，无需改设计 | 触发条件写明：新增内网 GPU 且 vllm/torch 与 CUDA 版本兼容验证通过 |
| 大模型抽取 18 位号码的可靠性未实测 | 已用「传统 OCR 先行 + 校验位本地硬校验 + 正则降级」三层兜底，模型只负责字段定位不负责识读 | 首次上线后统计 `extract_mode` 分布与 `ID_NO_INVALID_CHECKSUM` 比例，再决定是否保留 vision 默认降级 |
| `party_identity` 的 `id_card_front_url` 实际填充率未知（可能是 NULL 居多） | 若填充率低，本能力上线即大面积 `IMAGE_UNAVAILABLE`，观感等同「坏了」 | **实施第一步先跑一次填充率统计 SQL**（`count(*) filter (where id_card_front_url is not null)` 占比），据结果决定是否先做「补录引导」再开核验入口 |
| `FileApi.getFileContent(path, code)` 的 `code`（仓库编码）取值需按当事人照片实际存储仓确定 | 本文未替读者猜 `code` 常量 | 实现时从既有上传链路反查实际写入的 `configCode`，写成配置项 `party.verify.file-code`，取不到则报 `IMAGE_UNAVAILABLE` 而非 NPE |
| 无面向前端的当事人「自助同意」入口 | 本文只做 `source='ADMIN'` 代录 + 预留 `PARTY_APP`/`SMS_LINK` 取值 | 自助签署属 P2，另立文档 |
| uaa 权限串前缀为 `system:` 而服务是 uaa（事实 4：`system:party-identity:query`） | 属既有命名不一致，本文新增点沿用同前缀以免权限体系分裂 | 统一为 `uaa:` 需全量改菜单与前端，另开清理任务 |

---

## 12. Spec 自检（写完后逐条核对）

| 检查项 | 结论 |
|---|---|
| 占位符 | 无 `TODO`/`TBD`/`FIXME`/`待定`/`待补充`/`xxx`；每张表每格均有内容；无空代码块或空标题 |
| 类名与列名 | 【2026-11-04 订正：原句把 `PartyApi` 列入「均已实读确认存在」，与同句末尾注释自相矛盾】`PartyIdentityDO`/`PartyIdentityController`/`FileApi`/`PaddleOcrClient`/`OcrEngine*`/`AiLLMCallService` 均已实读文件确认存在；**`PartyApi` 与 `PartyIdentityForVerifyRespDTO` 全仓零命中，是本文提议新增的设计态对象**，须从零添加，不得写成「复用现成 Feign」；`id_card_front_url`（DB）与 `idCardFrontUrl`（Java）双形态分别标注，不混写。§7 两张表同为设计态 |
| 仓库归属 | uaa 模块物理位于 **Demo-basic** 仓（非独立 uaa 仓）；本文所有出处均按「仓名 + 模块路径」完整书写，避免再次因搜索范围不全误判存在性（详见上游文档 §12 同条教训记录） |
| 数据通路 | 「跨服务」落到具体 API：`PartyApi`（新增，`/rpc-api/uaa/party`）+ `FileApi.getFileContent`（既有）+ `PaddleOcrClient`（既有），每跳标失败出口（§3.2） |
| 底库唯一性依据 | 引 `uk_party_identity_no_auth … WHERE status = 1 AND deleted = false` 实际索引定义，未凭 DO 注释推断 |
| 算力边界 | 不假设 GPU 可用（事实 13），默认路径 CPU-only；GPU 分支以「触发条件 + 开关」形式写明，非模糊表述 |
| 错误码 | `1_040_063_000–004`，经全表扫描确认该子段空闲（已用段列于事实 16），不与 `061`/`062` 冲突 |
| 迁移号 | V3.52–V3.54，紧接 SP-1/2 已预定的 V3.51；带字母后缀惯例（V3.38a/V3.39a）已确认不干扰整数号递增 |
| 菜单 ID | 9501–9504；并显式澄清 `uaa_menu.sql` 中 `9510/9520/9530/9550` 属 `sort` 列取值而非 `id`，排除误读 |
| 分期一致性 | SP-5 = 本文（P1）；人像 1:1 比对移交 SP-3（CompreFace）并在 M2 登记，`FACE_*` 族由 SP-3 总纲 B 定义（不再是单条 `FACE_MISMATCH` 预留）；企业证件、活体、外部实名、自动驳回均在 §1.2 显式列为非目标且给出界面表现，无「后面再说」项 |
| 合规边界 | 同意前置门（零外呼）、不存原图、不存明文号码、日志负向测试、留存期、撤回留痕——六项均为可实现可断言的规则，不是原则性口号 |
| 定性风险 | §4 不变量①③ + §10.5「定性措辞 = 0」形成文案闭环；核验结论严格限定为「系统内自洽性校验」，不冒充身份真实性认证 |
| 与上游一致 | 异步线程池范式、错误码风格、迁移风格（`BIGSERIAL`+审计列+`tenant_id`+部分唯一索引）、Feign 前缀推导、`AlertLevel` 式的「后端文案唯一来源」原则，均与 SP-1/SP-2 文档对齐；对上游 §1.2 的两处修订已在 §9 M1/M2 登记，不会互相打脸 |

---

## 13. 交付清单（实施完成后逐项存在）

- `Demo-basic/Demo-module-uaa`：`Demo-module-uaa-api/.../api/party/PartyApi.java` + `dto/PartyIdentityForVerifyRespDTO.java`；`-server` 侧 `api/party/PartyApiImpl.java`、`PartyIdentityController`（脱敏改造 + `get-sensitive` 端点）、`vo/PartyIdentityRespVO.java`、`convert` 脱敏逻辑、§10.1 对应测试类
- `Demo-ai/Demo-module-ai-server`：`controller/admin/party/PartyVerifyController.java` + `controller/admin/party/PartyConsentController.java` + `vo/`（`IdCardVerifyReqVO`、`PartyVerifyRecordVO`、`ConsentGrantReqVO`、`PartyConsentVO`）、`service/party/PartyVerifyService` + `impl`、`service/party/PartyConsentService` + `impl`、`service/party/support/IdCardChecksum`、`support/IdCardNormalizer`、`support/IdCardRegexExtractor`、`service/party/enums/PartyVerifyVerdict` + `PartyConsentScopeEnum` + `VerifyFailStage`、`dal/dataobject/party/PartyVerifyRecordDO` + `PartyConsentDO`、`dal/mysql/party/PartyVerifyRecordMapper` + `PartyConsentMapper`、`config/PartyVerifyConfiguration.java`（`partyVerifyExecutor`）、`util/ErrorCodeConstants` 追加 5 码、`application.yaml` 追加 `party.verify.*`、§10.1/§10.2 全部测试类
- `Demo-ai/docs/sql`：`V3.52__party_verify_tables.sql`、`V3.53__party_verify_menu.sql`、`V3.54__party_idcard_extract_prompt.sql`
- `Demo-web`：当事人档案页核验卡片与同意采集入口、`api/party/verify.ts`、`__tests__/partyVerify.spec.ts` + `partyConsent.spec.ts`
- `Demo-docs`：本文档；并按 §9 M1 对 `2026-11-04-meeting-room-ui-design.md` §1.2 做一次修订提交
- **号段归属说明（D4）**：`ai_party_verify_record.verify_type VARCHAR(24) NOT NULL DEFAULT 'IDCARD'` 与 `room_id BIGINT` 由 **V3.56（SP-3 阶段）一次性建立**；V3.52 按本文 §7.1 原文不建这两列，V3.60 只改 `verify_type` 的 COMMENT。两列**不在 SP-5 交付清单内**。
