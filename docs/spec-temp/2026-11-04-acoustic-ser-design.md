# 会中声学情感识别（SP-4：Speech Emotion Recognition）设计

> **修订索引（2026-11-04，以 `2026-11-04-meeting-ai-spec-review-and-revision.md` 为准）**
> 1. **§6.4 字段计数订正（原文自相矛盾）**：原文写「`TranscriptSegmentVO` 新增 3 个可空字段」却列出 `audioLevel`、`serEmotion`、`serConfidence`、`serModel` 四个。正确表述：**本文新增 3 个** —— `serEmotion`(String)、`serConfidence`(BigDecimal)、`serModel`(String)；`audioLevel`(Short) **由 SP-1/SP-2 §5.1 定义，本文仅复用**，不计入本文新增。§3.2 步骤 3 的 push 体、§6.4、§7 DDL 三处统一按此口径（DDL 只加 `ser_*` 三列）。
> 2. **§3.2/§3.3 快照结构统一**：`/ai/meeting/internal/analyze/switch` 定版为固定 `{voice, ser, video}` + **可选** `serPolicy` / `facePolicy` 策略块；worker 解析不得把策略块当必填，缺失时对应能力 fail-closed。与 SP-3 §3.2 的 `facePolicy` 扩展兼容，不再视为两份不同契约。
> 3. **`video` 不变量② 处置统一**：§0-S1 扩 `kind` 合法集为 `voice|ser|video` 保留；但 §3.3「`video` 在 SP-3 落地前恒 false（与 SP-1/2 §8 不变量② 保持一致）」与 §10.1 用例⑭「快照含 `video=false`」改为引用**统一门禁**：`available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)`，未通过时 `video=false` 且 reason 给真实原因；门禁通过后允许翻转。SP-1/2、SP-3、本文三处一致，不再出现「作废 / 沿用」两种说法。
> 4. **§9 同意口径并入统一契约**：`SER_ANALYSIS` 作为 `ai_party_consent.scope` 的一个枚举值，与 `IDCARD_VERIFY`/`FACE_COMPARE`/`VOICE_ANALYZE` 共用同一张表、同一 `version` 等值语义与同一 `revoked_at` 撤回机制；`noticeConfirmed` 降级为操作人确认动作（写审计），不再充当单独同意凭据。关闭后的残余采集窗口（30s 轮询）仍须写进告知文案。
> 5. **§6.1 `AnalyzeStatusRespVO` 定版**：返回**能力列表**，条目数量与顺序由服务端驱动；前端不得硬编码「两张卡 / 三张卡 / `video` 恒不可用」。`MeetingAlertVO` 的 ser 三字段与 SP-3 的 `videoChannel` 合并进统一 `MeetingAlert`（所有扩展字段可空，`null` 时前端不得显示默认 `calm` 或空标签）。
> 6. **§3.2 步骤 4 的「第二次守卫」继续有效**（服务端开关为 false 时 ser 三列写 null、零告警），这是纵深防御的正确设计，不因契约统一而放宽。
> 7. **§12 自检同步**：原文「对上游的修订是否显式」五条应补第 6 条（统一门禁与统一同意口径）；「号段冲突」结论保留（错误码 `1_040_064_*`、迁移 `V3.55`、端口 8020/8021 与其它 spec 不冲突）。
> 8. **工程能力订正**：前端权限判断是 `accessStore.hasAccess(code)` 而非 `hasPermission`；新增端点只用 `get/post`（`request.ts` 无 `patch`，删除叫 `del`）；§10.3 的前端用例需落在 `src/views/ai/meeting/__tests__/` 才会被 vitest 收集。
> 9. **不受影响的保留结论**：§5.2「声学侧永不单独构成 `danger`」、§5.3「只补写不升级」、§5.5「失败不产告警不重试」、§8.2 emotion2vec 选型与 A/B 双分支、§9 用途限制与落盘禁令 —— 用户本轮裁决只涉及人脸识别，SER 设计不变。
> 10. **实施定版指针（2026-11-05）**：本文实施以 `2026-11-05-meeting-ai-specs-implementation.md` 的 D1–D6 为准（D3 同意 scope 五值、D5 复议权限点改 9512/9513、D6 声纹归属改 SP-6）；`AnalyzeStatusRespVO` 条目数量由服务端返回驱动，不硬编码卡片数。
> 11. **实施完成登记（2026-11-06）**：§13 交付清单的代码、契约、部署件与测试已补齐：`Demo-deploy/ser/` 的 `emotion2vec/{app.py,Dockerfile,requirements.txt,wheels}`、可构建 compose 与 `/ser` 前缀 nginx 模板；worker 的 `SerResult`/`HttpSerProvider`/段长门/并发门/断路器/30s 快照轮询/ASR 与 SER 并行；Java 的 `MeetingSerProperties`、`MeetingSerAvailabilityService`（真实探活）、`fillSerEvidenceIfAbsent`、§5.1 四条文案与对齐 §6.3 的错误码段；五个测试类与前端用例、七步冒烟脚本。验证：离线 `mvn -o -nsu` 编译通过、Java 23 例 / worker 25 例 / 前端 60 例全绿。**未解除的仍是门禁类**：§8.2.9 U1–U5 五项实测、§8.4 六条 PoC、模型商用许可留档、真机联调，`MEETING_SER_ENABLED` / `MEETING_SER_POC_PASSED` / `MEETING_G3_SER` 保持 `false`、`SER_PROVIDER=none`。实测值与取证状态归 `Demo-deploy/ser/README.md`；代码可运行不等于已上线。

- 日期：2026-11-04
- 状态：代码层已交付（2026-11-06）；PoC 门禁未通过，仍待用户复核
- 上游文档：`2026-11-04-meeting-room-ui-design.md`（SP-1/SP-2，本文修订其 §5 开关集、§7.1 唯一索引、§11 一条遗留）、`2026-11-03-meeting-ai-capability-design.md`、`2026-11-04-party-identity-verification-design.md`（SP-5，本文复用其同意表）
- 落地范围：`Demo-ai/deploy/livekit-worker`（Python 侧 SER provider）、`Demo-module-ai-server`（开关权威、告警融合、探活）、`Demo-web`（第三张开关卡与告警依据栏）、`Demo-deploy`（新模型服务容器，形态见 §8）
- 本文所有类名、行号、端点、错误码段、迁移号、菜单 ID 均以**实读代码 + 全仓扫描**为准，出处逐条列在 §2
- 算力前提（用户未裁定，按 C 方案执行）：**本文不假设任何 GPU 可用**，同时给出 A（新增内网 GPU）与 B（仅复用现有 CPU）两条分支及明确切换阈值，见 §8

---

## 0. 与已交付设计的差异登记（评审先读这里）

| # | 上游原文 | 本文的决定 | 差异性质 | 理由 |
|---|---|---|---|---|
| S1 | SP-1/SP-2 §6.1 规定开关 `kind` 合法集为 `voice` 或 `video`，其余抛 `1_040_061_005` | 合法集扩为 `voice`、`video`、`ser` 三值，`ser` 为第三张卡片 | 修订已交付设计 | SP-2 的 `voice` 输入是**转录文本 + 音量标量**（其 §5.2、§5.3），而声学情感的输入是**原始 PCM 波形**，二者信号源、失败模式、成本结构完全不同。合并进同一个 `voice` 开关会让「关掉大模型调用」与「关掉音频外呼」不可分别控制，成本门与告知门都会失真 |
| S2 | SP-1/SP-2 §7.1 建了 `uk_ai_meeting_alert_transcript ON ai_meeting_alert (transcript_id)` 单列唯一 | 该索引必须替换为 `(transcript_id, kind)` 的部分唯一索引，`V3.55` 内 DROP 后重建 | **破坏性修订**（不改则 SP-4 直接失效） | 同一条转录分段可以同时产生「文本语义告警」与「声学情感告警」两行。保留单列唯一时，先到的一行会永久占位，后到的声学告警被唯一冲突吞掉——而文本侧分析通常先完成，结果就是 SP-4 上线后**几乎永远不出声学告警**，且表现为「静默无数据」而非报错，最难发现。本文 §5.4 给出避免双重刷屏的替代手段（补写而非新建），所以放宽唯一性不会带来刷屏 |
| S3 | SP-1/SP-2 §5 全章不依赖 137 语音网关；其 §11 把「SP-4 立项时必须先解决 137 并发容量」列为遗留 | 本文同样不调 137；该遗留以「SER 走独立服务 + 分支 B 只覆盖一级门命中段 + 阈值自动降级」解决，并在 §8 明确容量口径 | 回应既有遗留，且不引入 137 依赖 | SER 与 ASR 是两种推理，混用同一网关会让转录链路（字幕）被情感分析拖死；`VoiceGatewayProperties` 里也没有任何 emotion 配置项（事实 10） |
| S4 | 上游把 SP-4 记为「P1，137 无 emotion 端点，需新模型服务」，未定服务形态、未定模型、未定算力 | 本文定契约与门禁，不下结论于具体模型精度：模型标识符只作为「服务侧自报」字段（`ser_model`），**平台侧不绑定任何模型名**；算力按 A 或 B 双分支加切换阈值（§8） | 补全实现路径 | 全仓无任何声学情感实现痕迹（事实 12），任何「已有 emotion 服务」的表述都无依据；把模型选型写进设计会导致实施时被一个未验证的名字锁死 |
| S5 | SP-1/SP-2 §11 已指出 `MediaAnalysisServiceImpl` 是伪能力，并声明「未改造前任何 spec 不得引用它作为已具备证据」 | 本文严格遵守：不复用该类、不引用其 `emotion` 或 `sentiment` 输出，并在 §11 提出与 SP-4 同步的改造建议（把它也标为未实现） | 划界 | 该类的情感与语音结论全是硬编码字符串（事实 13），若 SP-4 复用它，界面上会出现「声学情感：calm」的**假数据**，比没有数据伤害大得多 |

### 0.1 本文顺带坐实的一个现存缺陷（与 SP-4 同源，必须一并交代）

`Demo-module-ai-server` 的 `service.disputehall.impl.MediaAnalysisServiceImpl` 对外宣称具备情感、语音转写、图像与视频分析能力，实际全部是硬编码返回值，且 `getCapabilities()` 把四项开关一律报 `true`：

```java
// L104-121：TODO 未实现，直接返回固定结果
result.setDominantEmotion("calm");
result.setConfidence(new BigDecimal("0.85"));
scores.put("calm", new BigDecimal("0.45"));   // 另有 angry/anxious/happy/sad 四个固定值
// L205-210：analyzeEmotionInternal 整个方法体只有一句
result.setData(Map.of("emotion", "calm", "confidence", 0.88));
// L234-239：能力自述谎报
capabilities.setSentimentEnabled(true);  setAsrEnabled(true);  setVisionEnabled(true);  setVideoEnabled(true);
```

更关键的是 `analyzeEmotionTimeline`（L123-150）会把这条假路径的结果组装成「情感时间线」返回前端——**界面上已经存在一条看起来像 SP-4 产出、实为常量的曲线**。SP-4 上线时不得复用该视图，也不得把两者并排展示，否则评审会误认为声学情感已交付。

---

## 1. 目标与范围

### 1.1 本期目标（P1）

1. worker 在 `END_OF_SPEECH` 处**复用已经持有的那段 PCM**（事实 1），并行调用一个可插拔的 SER 服务，产出五类标签之一加置信度，随同转录分段回推 Java；不二次缓冲、不落盘、不转存。
2. SER 客户端与 `asr_provider.py` **严格同构**：抽象基类 + 纯函数复用 + `get_ser_provider()` 在未实现时显式 `raise`，绝不静默降级成假标签。
3. 开关权威仍在 Java：worker 不持有业务阈值，改为从新增内部端点拉取「开关与策略快照」（§6.1），30s 刷新，取不到即视为关闭（fail-closed）。
4. 标签集与 SP-2 的 `EMOTION_JSON_SCHEMA` **同源五值**（`calm`、`anxious`、`agitated`、`anger`、`threat`），使告警文案、等级枚举、前端徽标三处零新增分叉。
5. 融合规则：声学证据**永不单独构成 `danger`**，且与文本告警之间只补写不升级（§5.3），避免两个异步任务时序不定导致等级跳动。
6. 隐私最小化：PCM 仅在 worker 进程内存中存活，不进数据库、不进文件、不进日志；平台只持久化标签与置信度。
7. 给出 A 与 B 两条算力分支及**可自动判定的降级阈值**（§8），并以 PoC 门禁阻止「凭感觉上线」。

### 1.2 非目标（逐条给归属，不留悬空）

| 项 | 归属 | 本文如何交代 |
|---|---|---|
| 声纹识别、说话人身份确认、跨会议声纹聚类 | SP-3 与 SP-5 | 本文**不做**身份推断：会中说话人身份来自 LiveKit 的 `participant.identity`（事实 3），与音频内容无关，因此 SER 输出天然匿名于身份；§9 明确禁止把 ser 标签用于身份认定 |
| 视频轨帧采样、人脸检测与比对 | SP-3 | `worker.py:84` 显式丢弃非音频轨，本文**不改这一行**；`video` 是否可用按修订索引 #3 的统一门禁 `available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)` 判定，未通过时 `video=false` 且 reason 给真实原因 |
| 重叠语音分离（两人同时说话的拆分） | 不做 | 明确写入限制：现有 `silero` VAD 是单流逐轨（事实 1 的 `transcribe_track` 按轨独立），本文不引入分离，SER 在混叠段直接放弃出结果（§4.3） |
| 模型训练、微调、方言适配 | 不做 | 只定服务契约；`ser_model` 由服务侧自报并入库，平台不做选型承诺 |
| 跨会议情绪画像、个人情绪档案 | P2，且默认不做 | 不建任何按自然人聚合的表或视图；§9 列为红线 |
| 实时频谱、音高、语速等副语言学特征展示 | 不做 | 展示层只留「音量 dBFS（SP-2）＋声学情感」两项，不扩成仪表盘 |
| 情感标签的多语言与跨文化校准 | 不做 | 服务侧问题，平台只透传置信度并受 §5.3 阈值约束 |

---

## 2. 读码核实的事实基线（本设计的唯一依据）

| # | 事实 | 出处 |
|---|---|---|
| 1 | `worker.py` 共 105 行；`transcribe_track()` 在 `END_OF_SPEECH` 分支把 `ev.frame.data` 累积进 `pcm` 后整段送 ASR，此时该段完整 PCM 已在内存 | `Demo-ai/deploy/livekit-worker/worker.py:53-80`（关键 L65-70） |
| 2 | ASR 调用方式：`await asyncio.to_thread(provider.transcribe, bytes(pcm), SAMPLE_RATE)`，即同步 HTTP 已在线程池中 offload，SER 可复用同一手法并行 | `worker.py:70` |
| 3 | 回推契约：`POST {JAVA_BASE}/admin-api/ai/meeting/internal/transcript?roomSid=...`，头 `X-Internal-Token`，body 为分段数组，`timeout=10`；说话人身份取 `participant.identity` | `worker.py:32-50`、`worker.py:87` |
| 4 | Java 侧承接：`MeetingTranscriptInternalController.java:42` 用 `@RequestHeader("X-Internal-Token")`；`MeetingTranscriptServiceImpl.java:43` 注入 `${meeting.internal-transcript-token}` | 两处实读 |
| 5 | `worker.py:84` `if track.kind != rtc.TrackKind.KIND_AUDIO: return` —— 视频轨被显式丢弃，这是 SP-3 的接入点，SP-4 不涉及 | `worker.py:83-87` |
| 6 | `SAMPLE_RATE = 16000`，int16 单声道 | `worker.py:34`、`worker.py:55` |
| 7 | provider 抽象范式：基类 `AsrProvider.transcribe(pcm16_bytes, sample_rate, language)`、纯函数 `_to_wav()`、`QwenAsrProvider` 打 `POST {base}/v1/audio/transcriptions`、`get_provider()` 对未知名字 `raise ValueError` 不降级 | `deploy/livekit-worker/asr_provider.py`（全文 66 行） |
| 8 | 依赖锁定：`livekit-agents[silero]~=0.12`、`livekit-plugins-silero~=0.7`、`requests`；Dockerfile 162B，无 GPU 基础镜像 | `deploy/livekit-worker/requirements.txt`、`Dockerfile` |
| 9 | `TranscriptSegmentVO` 现仅 4 个字段：`speakerIdentity`、`text`、`startTs`、`endTs`，**无** `audioLevel`（SP-2 尚未落地） | `controller/admin/meeting/vo/TranscriptSegmentVO.java:9-18` |
| 10 | `ai_meeting_transcript` 现存列：`id`、`room_id`、`speaker_identity`、`text`、`start_ts`、`end_ts`、`seq` ＋ `TenantBaseDO` 审计与租户列 | `dal/dataobject/meeting/MeetingTranscriptDO.java:16-28` |
| 11 | 137 语音网关配置类**无任何 emotion 字段**，仅 `baseUrl`、`realtimeWsUrl`、`apiKey`、`asrModel`、`ttsModel`、`defaultVoice`、`connectTimeout=5000`、`readTimeout=30000`；`application.yaml:362-366` 同构 | `config/VoiceGatewayProperties.java:14-30` |
| 12 | Java 侧真实外呼件 `VoiceGatewayClient`（117 行）：ASR `POST {base}/v1/audio/transcriptions`、TTS `POST {base}/v1/audio/speech`、探活 `GET {base}/v1/pool`，源码注释明确「137 无 /health」；非 2xx 抛 `IllegalStateException`；`apiKey` 为空则不加 `Authorization` | `service/voice/client/VoiceGatewayClient.java:28-101` |
| 13 | **全仓无声学情感任何痕迹**：对 `Demo-*` 各仓的 `*.java`、`*.py`、`*.yaml`、`*.md`、`*.ps1` 搜 `emotion2vec`、`audio/emotion`、`acoustic`、`SER`，命中全部落在 IDE 技能文档（`.claude`、`.codebuddy`、`.cursor`）与前端 store 命名的误匹配，无一处平台实现 | 跨仓 grep 结论 |
| 14 | `MediaAnalysisServiceImpl` 伪能力精确行号：情感 TODO 与固定值 `L96-121`；语音转写模拟 `L155-169`（`"这是模拟的语音转文字结果..."`、`setConfidence(0.92)`）；图像模拟 `L181-196`；场景模拟 `L198-203`；`emotion` 常量 `L205-210`；`getCapabilities()` 四项全 `true` `L234-250`；provider 配置键 `ai.media.provider`、`ai.sentiment.provider`、`ai.asr.provider`、`ai.vision.provider`（默认 `cloud`）`L30-39` | 实读全文 286 行 |
| 15 | SP-1/SP-2 已定但未实现的设计（本文须对齐而非另造）：词表 danger 7 词与 warn 6 词、一级门音量阈值 `-18 dBFS`、同一发言人 `8s` 节流、每房间每分钟 `6` 次模型上限、`EMOTION_JSON_SCHEMA` 五值、`AlertLevel` 三级文案、Redis 三键、`meetingAnalyzeExecutor` 线程池 `2/4/200` | `2026-11-04-meeting-room-ui-design.md` §5.2-§5.5、§6.6、§8 |
| 16 | SP-1/SP-2 的 `ai_meeting_alert` 唯一索引为单列 `transcript_id`；`MeetingAlertVO` 含 `audioLevel`、`emotion`、`evidence`、`modelCalled` | 同上 §7.1 L493、§6.1 L378-383 |
| 17 | 错误码段位实况：代码已用 `1_040_060_*`、`1_040_061_000-004`、`1_040_062_000-006`；已交付设计已预定 `1_040_061_005-007`（SP-1/2）与 `1_040_063_*`（SP-5）→ **`1_040_064_*` 归本文** | `util/ErrorCodeConstants.java`（`VOICE_GATEWAY_UNAVAILABLE = 1_040_062_000` 在 L255）＋ 三份 spec 交叉扫描 |
| 18 | 迁移号实况：`Demo-ai/docs/sql` 真实最新为 `V3.48__meeting_minutes_prompt.sql`（另有 `V3.38a`、`V3.39a` 字母后缀补丁惯例）；`V3.49-3.51` 归 SP-1/2，`V3.52-3.54` 归 SP-5 → **`V3.55` 归本文**，`V3.56` 及以后归 SP-3；全仓无 `V3.49+` 文件 | `docs/sql` 目录列举 ＋ 全仓 `*.sql` 文件名扫描 |
| 19 | 菜单 ID 实况：`9490-9494` 会议、`9495-9498` 语音演示、`9499-9500` SP-1/2、`9501-9504` SP-5；`9505-9519` 作为 `uaa_menu.id` 全仓 SQL 无占用（`docs/uaa_menu.sql:724-773` 的 `9510` 等是 `sort` 列取值）→ 本文**不新增菜单**，见 §6.5 | 全仓 SQL 扫描 |
| 20 | GPU 证据自相矛盾，无法由仓库判定：`Demo-deploy/paddle/.env` 写「本机 RTX 5070 Ti 为 0」并备好 `sm120` 离线镜像；同目录 `README.md` L6-8 称 VL 因 vllm/torch 与 CUDA 12.8 冲突已撤下；`docker-compose.yml` 当前只剩 CPU 版 `pp-ocrv6`（`127.0.0.1:8011`，`OCR_ENABLE_MKLDNN=false`）；Java 实际调用 `http://192.168.40.30:8080/ocr/v6/ocr`（`application-dev.yaml:172-175`） | 四处实读 |
| 21 | 可复制的内网模型服务部署范式（本文 §8 直接沿用其结构）：`docker-compose.yml` ＋ `nginx/default.conf.template`（对外唯一入口，`X-API-Key` 鉴权）＋ 应用 `app.py` ＋ `Dockerfile` ＋ `requirements.txt` ＋ 离线 `wheels/` ＋ `scripts/{deploy,status,stop,verify}.ps1` ＋ `.env.example`；服务自带 `GET /health` 且返回 `gpu_available` | `Demo-deploy/paddle/` 目录树（15 个文件） |
| 22 | SP-5 已建 `ai_party_consent`，`scope` 列注释预留了 `FACE_COMPARE(SP-3)` → 本文追加 `SER_ANALYSIS`，不新建同意表 | `2026-11-04-party-identity-verification-design.md` §7.1 L289 |

---

## 3. 架构与数据通路

### 3.1 SER 推理发生在哪：三形态对比与选定

| 形态 | 做法 | 判定 | 理由 |
|---|---|---|---|
| ① worker 直连 SER 服务 | worker 复用内存中的 PCM，与 ASR 并行调 SER，把标签随分段一起回推 Java | **选定** | PCM 只在产生它的进程内存里存活（§9 隐私硬要求）；与事实 7 的 provider 范式同构；Java 不需要接收音频；线程模型已有 `to_thread` 先例（事实 2）；延迟与 ASR 重叠而非串联 |
| ② worker 把 PCM 回推 Java，Java 转调 SER | 新增大体积上传端点 | 否 | 音频要过 Java 与网关（ multipart 上限、临时文件、双份密钥面），直接违反最小化；转录链路的 `timeout=10`（事实 3）撑不住音频体积 |
| ③ Java 侧另起 LiveKit 订阅取音频 | 服务端二次拉流 | 否 | 需第二套 egress 与解码，且要重做 VAD 分段才能与 `transcript_id` 对齐，工程量大于收益 |

形态 ① 的**唯一代价**是「开关关闭即零成本」这条 SP-1/SP-2 不变量必须跨语言保证。解法见 §3.2：worker 不自己判断业务开关，而是向 Java 拉权威快照，且 Java 落库前做第二次守卫（纵深防御，任一层失效都不会产生数据）。

### 3.2 端到端链路（含每步失败出口）

```
0 worker 启动：get_ser_provider() 读 SER_PROVIDER。为 none 或未实现 → 抛 ValueError，
  worker 进程直接起不来（同 asr_provider 范式；宁可不启动，也不要用假标签骗人）

1 worker 进房后，AnalyzeSwitchCache 每 30s 拉一次：
  GET {JAVA}/admin-api/ai/meeting/internal/analyze/switch?roomSid=...   （头 X-Internal-Token）
  → { voice:bool, ser:bool, video:false, serPolicy:{minSegSec,maxSegSec,maxConcurrency,
       minConfidence,failThreshold,cooldownSec} }
    - 401/404/超时/JSON 非法 → 缓存置为 ser=false（fail-closed），并 print 一次状态码
    - 首次拉取失败时 ser=false：宁可整场不分析，也不在门控未知时外呼

2 VAD END_OF_SPEECH → pcm 成型（现状不变）
    - RMS 算 dBFS（SP-2 §5.1 已设计，本文不改）
    - ASR 线程任务照旧
    - ser 任务：仅当 缓存 ser=true 且 段长 ∈ [minSegSec, maxSegSec] 且 信号量未满 才发起
        - 不满足 → ser_emotion=null, ser_confidence=null（不发起、不记为失败）
        - 信号量 SER_MAX_CONCURRENCY 满 → 直接放弃本段，计数 serSkipped++
        - 调用异常或非法标签 → serEmotion 置 null，failure 计数 +1，
          连续 failThreshold 次 → 断路器 OPEN，冷却 cooldownSec 内不再发起

3 push(room_sid, [{speakerIdentity, text, startTs, endTs, audioLevel,
                   serEmotion, serConfidence, serModel}])
    - HTTP 失败：打印状态码 ＋ 响应体前 200 字符（SP-2 §6.4 已要求），字幕链路仍不阻断其他轨

4 Java MeetingTranscriptInternalController.ingest(...)
    - 密钥不符 → 1_040_061_002（既有）
    - 落 ai_meeting_transcript（含 ser_emotion、ser_confidence、ser_model 三列）
    - **第二次守卫**：ser 开关为 false 或 meeting.ser.enabled=false → 三列写 null 后落库，
        并 log.warn 一条「收到未授权开启期间的声学结果」；绝不建告警行
        （设计意图：worker 被绕过、配置漂移、旧 worker 残留，都不允许变成假告警）

5 文本告警任务（SP-2 §8 步骤 4，本文不动其内部）
6 声学融合：MeetingSerAlertService.fuse(seg, textAlertRow) → 见 §5.3
7 SSE 事件 alert（复用 SP-2 的 pushAlertToRoom，不新开事件名）
8 前端第三张卡片状态来自 GET /ai/meeting/analyze/status 的 kind=ser 行
```

### 3.3 新增 Java 内部端点（worker 专用）

`MeetingTranscriptInternalController` 同类内新增一个方法即可，**不新建 Controller**（新建易在包名与映射上重演 SP-1/2 §6.5 的双前缀缺陷）：

```java
@GetMapping("/analyze/switch")
public CommonResult<AnalyzeSwitchSnapshotRespVO> switchSnapshot(
        @RequestParam("roomSid") String roomSid,
        @RequestHeader("X-Internal-Token") String secret) { ... }
```

类在 `controller.admin.meeting` 包，框架按包名匹配 `**.controller.admin.**` 后追加 `/admin-api`，因此映射字面量只写 `/ai/meeting/internal` ＋ `/analyze/switch`，实际注册路径 `/admin-api/ai/meeting/internal/analyze/switch`。`video` 按修订索引 #3 的统一门禁求值：`available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)`；门禁未通过时下发 `video=false` 且 reason 给真实原因，门禁通过后允许翻转（与 SP-1/2 §8、SP-3 三处一致，不再有「恒 false / 沿用 / 作废」两种说法）。

快照内容取 SP-2 已设计的 Redis 开关缓存（键 `ai:meeting:analyze:switch:{roomId}:{kind}`，TTL 60s），`serPolicy` 直接来自 `meeting.ser.*` 配置绑定 → worker 侧零业务阈值，配置唯一来源是 Java。

---

## 4. SER Provider 契约（Python 侧）

### 4.1 抽象与文件布局

新增 `deploy/livekit-worker/ser_provider.py`，与 `asr_provider.py` 严格同构；**`_to_wav` 从 `asr_provider` 导入复用，不复制第二份**（两份实现必然漂移，这是唯一允许跨模块引用的一处）：

```python
SER_EMOTIONS = ("calm", "anxious", "agitated", "anger", "threat")   # 与 SP-2 EMOTION_JSON_SCHEMA 同源

@dataclass(frozen=True)
class SerResult:
    emotion: str          # 必属 SER_EMOTIONS
    confidence: float     # [0,1]
    model: str            # 服务侧自报，入库用，平台不解释
    latency_ms: int

class SerProvider:
    def predict(self, pcm16_bytes: bytes, sample_rate: int) -> SerResult:
        raise NotImplementedError

def get_ser_provider() -> SerProvider:
    name = os.environ.get("SER_PROVIDER", "none").lower()
    if name in ("emotion2vec",):          # 内网自建容器（§8 分支 A 或 B）
        return HttpSerProvider()
    raise ValueError(f"未实现的 SER_PROVIDER={name!r}；未配置则不启用声学情感分析")
```

`SER_PROVIDER` 默认 `none`，含义是**默认不启用**。这与 SP-1/2 的「默认关闭」不变量①对齐：不配服务时 worker 里没有任何 SER 外呼代码路径会被执行。

### 4.2 HTTP 契约（对服务侧的要求，非对既有服务的描述）

`HttpSerProvider` 打：

```
POST {SER_GATEWAY_BASE_URL}/v1/audio/emotion
Content-Type: multipart/form-data
  file: seg.wav        # 16k 单声道 int16 PCM 经 _to_wav 包装，audio/wav
  sample_rate: 16000
  language: zh
Headers: X-API-Key: *** 已配置时（与 Demo-deploy/paddle 的 nginx 范式一致，事实 21）
→ 200 {"emotion":"anger","confidence":0.83,"model":"<服务自报>","latencyMs":412}
→ 非 2xx 或 emotion 不在 SER_EMOTIONS 或 confidence 越界 → 抛 RuntimeError（由调用方计入断路）
GET  {SER_GATEWAY_BASE_URL}/health → {"status":"ok","gpu_available":<bool>,"model":"..."}
```

契约刻意与 `paddle/pp-ocrv6/app.py` 同形（`/health` 带 `gpu_available`、`X-API-Key`、JSON 数值字段），好处是 `Demo-deploy` 的 nginx 模板、`scripts/*.ps1` 与运维认知可直接复用，不新造第二种服务风格。

### 4.3 段长门、并发门与断路器

| 门 | 判定 | 触发动作 |
|---|---|---|
| 开关门 | 快照 `ser=false` | 不发起，`serEmotion=null`，不计失败 |
| 段长门 | `len(pcm) / (sample_rate * 2)` 秒，须 ∈ `[minSegSec, maxSegSec]`（默认 `1.0`–`30.0`，由快照下发） | 不发起，不计失败；短于 1s 的段在Demo现场多为语气词，标签无意义 |
| 并发门 | `asyncio.Semaphore(maxConcurrency)`（默认 `2`，取自快照）非阻塞获取失败 | 放弃本段并 `serSkipped++`；**绝不等位**，等位会拖慢字幕 push |
| 断路器 | 连续失败 `failThreshold`（默认 `3`）次 → OPEN，冷却 `cooldownSec`（默认 `60`）；期间成功一次即半开恢复 | OPEN 期间不发起；恢复后自动闭合 |
| 混叠语音 | 本期无分离能力（§1.2） | 不做识别，直接放弃出结果，不猜 |

`worker.py` 的挂载改动控制在两处：`transcribe_track` 内 `pcm` 成型后并行起 ser 任务，以及 `push` 体加三个键。`worker.py:84` 的视频轨丢弃、`SAMPLE_RATE`、VAD 用法、逐轨 `create_task` 一律不动。

---

## 5. 判定与融合规则

### 5.1 标签到等级的映射（写死 Java 常量，非模型可改）

| `ser_emotion` | 声学侧等级 `serLevel` | 是否可单独产告警 | 前端 `message`（取自 `AlertLevel` 枚举新增项） |
|---|---|---|---|
| `calm` | 无 | 否 | 不落告警，仅回写 transcript 列 |
| `anxious` | `info` | 是（`minConfidence` 达标时） | 语调疑似急促紧绷——留意是否需要放缓节奏，请主持人确认 |
| `agitated` | `info` | 是 | 语调疑似激动——留意冲突升级，请主持人确认 |
| `anger` | `warn` | 是 | 语调疑似愤怒——请主持人确认现场情况 |
| `threat` | `warn`（**封顶，不得为 danger**） | 是 | 语调疑似带有攻击性——仅作提示，请主持人现场确认 |

`confidence < minConfidence`（默认 `0.60`）→ 整条丢弃，不落列不建告警。声学标签的类内方差远大于文本判定，低置信声学值一旦上屏就会被读成「系统在指控某人愤怒」，所以丢弃优先于展示。

### 5.2 为什么声学侧不允许 `danger`

`threat` 由声学给出时只到 `warn`：情感识别对语速、音高、文化表达习惯高度敏感，且模型对「大声说话」与「威胁」并无稳定区分能力（本文不假设任何模型具备）。`danger` 在 SP-1/2 的语义是「出现对他人的威胁或伤害暗示」，暗示只能由**文本**承载。这条约束必须有可执行的测试（§10.1 用例④、§10.5 指标①），它比任何文案措辞都更硬。

### 5.3 与文本告警的合成（避免竞态与刷屏）

| 情形 | 条件 | 动作 |
|---|---|---|
| A | 同一 `transcript_id` 已有文本告警行（`kind='voice'`） | **只补写不新建**：`UPDATE ai_meeting_alert SET ser_emotion=?, ser_confidence=?, ser_model=?, evidence=evidence‖'；声学：'‖ser_emotion‖'('‖conf‖')' WHERE id=? AND ser_emotion IS NULL`，`level` 与 `message` **一律不变** |
| B | 无文本告警行，且 §5.1 允许单独产警 | 新建 `kind='ser'` 行，`level=serLevel`，`text_snippet` 取该段转录文本（转录恒存在，因为 ser 与 ASR 同源同段） |
| C | 两侧都不满足 | 只回写 transcript 三列 |

A 情形不做等级合并的理由是时序不可靠：文本与声学是两个独立异步任务，谁先落地不定。若允许「后到者升级」，SSE 已推送的 `level` 与库内值会分叉，前端角标与红条会跳动，且重推时会出现「先降级后升级」的荒谬序列。补写只增加依据、不改变结论，是可幂等、可回放的操作。

`uk_ai_meeting_alert_transcript` 放宽后（§S2）刷屏风险由 A 规则挡住：一条转录最多一行文本告警 ＋ 一行声学告警，且声学告警在文本告警存在时根本不产生。

### 5.4 幂等

- A 情形的 `WHERE ser_emotion IS NULL` 保证 worker 重推不覆盖首次值，也不产生第二条补写。
- B 情形靠 §7 的 `(transcript_id, kind)` 部分唯一索引挡重，冲突时 `INSERT ... ON CONFLICT DO NOTHING` 语义（Mapper 层捕获 `DuplicateKeyException` 并忽略，不抛给调用方），与 SP-1/2 §5.6 的处置风格一致。

### 5.5 失败语义

模型异常、超时、非法 JSON、非法标签、置信度越界 → `log.warn("[meeting-ser] roomId={} transcriptId={} 声学分析失败: {}", ...)`，**不产告警、不重试、不影响文本链路与字幕链路**。与 SP-1/2 §5.5 同一条原则：缺的是提示，错的是伤害。

---

## 6. 接口契约

### 6.1 新增与变更端点

| 端点 | 方法 | 权限 | 变更 |
|---|---|---|---|
| `/ai/meeting/internal/analyze/switch` | GET | 内部密钥 `X-Internal-Token`（非 `@PreAuthorize`） | **新增**，worker 专用，返回 §3.2 步骤 1 的快照 |
| `/ai/meeting/analyze/toggle` | POST | `ai:meeting:analyze`（复用菜单 9499） | `kind` 合法集加 `ser`；其余语义不变 |
| `/ai/meeting/analyze/status` | GET | `ai:meeting:query` | 返回列表多一行 `kind=ser` |
| `/ai/meeting/alert/list` | GET | `ai:meeting:query` | VO 加三个 ser 字段 |
| `/ai/meeting/alert/ack` | POST | `ai:meeting:alert-ack` | 无变更（声学告警与文本告警走同一知悉动作与审计） |

SP-4 不新增权限点：能切 `voice` 的账号即可切 `ser`，因为两者同属「会中风险分析」这一项授权决策；新增权限点会让授权矩阵出现「可开文本但不可开声学」这种现实中没人维护的组合（§6.5 记为可复议项）。

`ser` 卡片的 `available` 判定（与 `video` 的「恒不可用」形成对照，`ser` 是**可真可假**）：

| 条件 | `enabled` | `available` | `reason` | 是否写开关行 |
|---|---|---|---|---|
| `meeting.ser.enabled=false` | `false` | `false` | 「声学情感分析已在服务端停用」 | 否 |
| `meeting.ser.enabled=true` 且 `/health` 探活失败（TTL 内） | `false` | `false` | 「不可用：SER 服务未部署或不可达（`{base-url}`）」 | 否（避免「已开启」假象，沿用 SP-1/2 的 `video` 处置） |
| 探活成功、`enabled=true`、`noticeConfirmed!=true` | `false` | `true` | 「开启前须确认已向各方告知（含情绪推断）」，抛 `1_040_061_006` | 否 |
| 探活成功、`enabled=true`、`noticeConfirmed=true` | `true` | `true` | `null` | upsert ＋ 审计 |

### 6.2 VO 扩展（字段名即属性名）

```
AnalyzeStatusRespVO          kind ∈ "voice" | "video" | "ser"；ser 行 sp="SP-4", phase="P1"
MeetingAlertVO 新增三字段：
  serEmotion:String|null     calm/anxious/agitated/anger/threat
  serConfidence:BigDecimal|null   scale=2
  serModel:String|null       服务自报标识，仅供追溯，前端不展示原文
TranscriptRespVO（离线复核用）新增同上三字段
```

**明确不出现在任何 VO**：音频字节、音频 URL、任何可回放的路径（§9）。

### 6.3 错误码（`1_040_064_*`，事实 17 确认该段空闲）

```
1_040_064_000  声学情感服务不可用: {}
1_040_064_001  声学情感返回值非法: {}
1_040_064_002  声学分析音频段不合规: {}
1_040_064_003  转录内部开关查询密钥无效
1_040_064_004  声学情感分析未开启，结果已丢弃
```

`1_040_064_003` 与既有 `1_040_061_002`（转录回推密钥无效）刻意分开：两个内部端点的失效原因不同，混用会让排障时误判是 worker 还是 Java 的配置漂移。

### 6.4 worker 与 Java 的双侧契约变更

【2026-11-04 订正：原句写「新增 3 个」却列出 4 个，且把 SP-2 的 `audioLevel` 误算为本文新增】`TranscriptSegmentVO` **本文新增 3 个可空字段**：`serEmotion`（`String`）、`serConfidence`（`BigDecimal`）、`serModel`（`String`）；`audioLevel`（`Short`）由 **SP-1/SP-2 §5.1** 定义，本文仅复用、不计入本文新增，V3.55 也只加 `ser_*` 三列。全部**可空**是硬要求：旧 worker、SER 未开启、段被门丢弃、调用失败四种情形都传 `null`，Java 不得 NPE、不得因此拒绝整段转录。

### 6.5 配置项（`Demo-module-ai-server/src/main/resources/application.yaml`）

```yaml
meeting:
  analyze:            # SP-1/SP-2 既有块，本文不动
    ...
  ser:
    enabled: ${MEETING_SER_ENABLED:false}      # 默认关，与 §4.1「SER_PROVIDER 默认 none」双处对齐
    base-url: ${MEETING_SER_BASE_URL:}         # 配到 nginx 前缀为止，例 http://192.168.40.30:8020/ser（带 X-API-Key；§4.2 的两段路径直接拼在这后面）
    api-key: ${MEETING_SER_API_KEY:}
    min-confidence: 0.60                       # Java 落库前二次校验（§5.1）
    health-cache-ttl-seconds: 30               # available 判定用的探活缓存
    policy:                                    # 下发给 worker，唯一来源在此（§3.2 步骤 1）
      min-seg-sec: 1.0
      max-seg-sec: 30.0
      max-concurrency: 2
      fail-threshold: 3
      cooldown-seconds: 60
    switch-poll-interval-seconds: 30           # 仅用于快照里回显，worker 读它
```

worker 侧环境变量（`Demo-deploy` 的 compose 注入，事实 21 范式）：`SER_PROVIDER`、`SER_GATEWAY_BASE_URL`、`SER_API_KEY`、`JAVA_CALLBACK_BASE`、`MEETING_INTERNAL_TOKEN`。**阈值不在 worker 配**，避免与 Java 漂移。

`SP-4` 不新增菜单行（事实 19 的空闲段 `9505+` 保留给 SP-3），权限复用 `ai:meeting:analyze`（9499）与 `ai:meeting:alert-ack`（9500）。复议条件：若合规部门要求「开文本」与开「声学」分别审批，再启用 9505 与 9506。

---

## 7. 数据表与迁移（PG 方言，对齐事实 15 的 V3.45 风格）

| 文件 | 内容 |
|---|---|
| `V3.55__meeting_ser_columns.sql` | 两张表加列 ＋ 替换告警唯一索引 |

**执行前置**：`V3.49`（SP-1/2）必须已落地——`ai_meeting_alert` 表与其单列唯一索引 `uk_ai_meeting_alert_transcript` 都在那里创建，本迁移要 DROP 的正是它；`ai_meeting_transcript.audio_level` 也在 V3.49。若 SP-2 未实施，V3.55 会因对象不存在而失败（属期望行为，SP-4 不允许绕过 SP-2 单独上线）。

```sql
BEGIN;

-- 1) 转录分段携带声学结论（与 audio_level 同一处置范式：可空、worker 未开启即为 NULL）
ALTER TABLE ai_meeting_transcript ADD COLUMN IF NOT EXISTS ser_emotion    VARCHAR(16);
ALTER TABLE ai_meeting_transcript ADD COLUMN IF NOT EXISTS ser_confidence  NUMERIC(4,3);
ALTER TABLE ai_meeting_transcript ADD COLUMN IF NOT EXISTS ser_model       VARCHAR(64);
COMMENT ON COLUMN ai_meeting_transcript.ser_emotion
  IS '声学情感标签 calm/anxious/agitated/anger/threat；NULL 表示未开启或被门丢弃，不代表 calm';
COMMENT ON COLUMN ai_meeting_transcript.ser_confidence IS '声学置信度 [0,1]，低于 meeting.ser.min-confidence 时整条丢弃不写入';
COMMENT ON COLUMN ai_meeting_transcript.ser_model IS 'SER 服务自报模型标识，仅作追溯，不作展示';

-- 2) 告警行携带声学依据
ALTER TABLE ai_meeting_alert ADD COLUMN IF NOT EXISTS ser_emotion    VARCHAR(16);
ALTER TABLE ai_meeting_alert ADD COLUMN IF NOT EXISTS ser_confidence NUMERIC(4,3);
ALTER TABLE ai_meeting_alert ADD COLUMN IF NOT EXISTS ser_model      VARCHAR(64);

-- 3) 唯一索引替换（本文对 SP-1/2 §7.1 的破坏性修订，见 §0-S2）
DROP INDEX IF EXISTS uk_ai_meeting_alert_transcript;
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_meeting_alert_transcript_kind
  ON ai_meeting_alert (transcript_id, kind) WHERE deleted = FALSE;

-- 4) kind 注释扩容（SP-1/2 原文只写 voice/video）
COMMENT ON COLUMN ai_meeting_alert.kind IS 'voice 文本语义 / ser 声学情感（SP-4）/ video 视频行为（SP-3 前不产行）';
COMMENT ON COLUMN ai_meeting_alert.ser_confidence IS '仅当本行 kind=ser 或为文本告警补写时有值；声学证据永不单独构成 level=3';

COMMIT;
-- 回滚：
--   ALTER TABLE ai_meeting_alert ADD CONSTRAINT ... 不适用，索引回滚用：
--   DROP INDEX IF EXISTS uk_ai_meeting_alert_transcript_kind;
--   CREATE UNIQUE INDEX uk_ai_meeting_alert_transcript ON ai_meeting_alert (transcript_id);
--   注意：回滚前须 DELETE 掉 kind='ser' 的行，否则单列唯一索引重建会失败。
--   ALTER TABLE ai_meeting_alert   DROP COLUMN IF EXISTS ser_emotion, DROP COLUMN IF EXISTS ser_confidence, DROP COLUMN IF EXISTS ser_model;
--   ALTER TABLE ai_meeting_transcript DROP COLUMN IF EXISTS ser_emotion, DROP COLUMN IF EXISTS ser_confidence, DROP COLUMN IF EXISTS ser_model;
```

回滚注释里「须先删 `kind='ser'` 行」是有意保留的坑位说明：这是本迁移唯一不可无损逆转的点，值得写在文件里而不是只写在本文。

Java 侧 `MeetingTranscriptDO` 与 `MeetingAlertDO`（SP-1/2 新建）各加三个属性，类型 `String`、`BigDecimal`、`String`；`MeetingAlertMapper` 加 `MeetingAlertDO selectByTranscriptAndKind(Long transcriptId, String kind)` 与 `int fillSerEvidenceIfAbsent(Long id, String emotion, BigDecimal conf, String model, String evidence)`（A 情形用，`WHERE ser_emotion IS NULL`）。

---

## 8. 算力形态与容量（C 方案：双分支 ＋ 可判定切换阈值）

事实 20 已说明 GPU 可用性证据互相矛盾，本文因此不以任何一种为假设，改为两条都成立、由阈值切换的设计。

### 8.1 容量口径（先算账，再谈选型）

一场 30 分钟、4 人会议（与 SP-1/2 §5.4 同一口径）：转录分段 180–300 段，累计语音时长上界 30 分钟（同一时刻多人同时说话时总和更大）。

| 分支 | 覆盖范围 | 待推理段数 | 说明 |
|---|---|---|---|
| A 全量 | 所有合规段（长度 ∈ 门内） | 150–280 段，约 25–28 分钟音频 | 需要专用推理资源，`gpu_available=true` 才有意义 |
| B 门控（默认） | 仅 SP-2 一级门命中的段（词表命中或 `audioLevel ≥ -18 dBFS`） | 45–105 段，约 8–12 分钟音频 | 复用 SP-2 已有的一级门结果做筛选，量降到 A 的 25–35%，CPU 可行；代价是「平静但语调异常」的段会被漏掉——必须在 §10.5 指标里把这个漏检口径写出来，不许掩盖 |

分支 B 是本文**推荐起点**：它与 SP-2 的零成本门共享同一判据，不额外引入「什么段该分析」的第二套策略，也让「关掉声学分析能省多少」这个问题有可验证答案。

### 8.2 部署形态（emotion2vec 内网容器，逐文件）

模型选型已确定（用户 2026-11-04 指令）：**`iic/emotion2vec_plus_large`**（达摩院 ModelScope，~300M 参数，官方支持 9 类，输入 16k Hz）。

这不推翻 S4：S4 禁止的是**平台侧（Java 与 worker）硬编码模型名**。模型名只出现在 `Demo-deploy/ser/` 的 `.env`、Dockerfile 与镜像内，Java 只存 `ser_model` 自报字符串，worker 只看 `SER_PROVIDER` 环境变量——换一个 SER 模型不需要改平台代码。许可与商用条款仍归 §8.4 门禁，本文不为任何模型作保（emotion2vec_plus_large 的权重许可需实施时留档，见 §8.4）。

目录与端口（严格照事实 21 的 `Demo-deploy/paddle/` 结构；与 OCR 的 `8011` 不冲）：

```
Demo-deploy/ser/
  docker-compose.yml
  .env.example          .env（deploy.ps1 首次自动生成）
  emotion2vec/          app.py  Dockerfile  requirements.txt  wheels/
  nginx/default.conf.template
  scripts/              deploy.ps1  status.ps1  verify.ps1  stop.ps1
  README.md
```

| 服务 | 监听 | 默认端口 | 说明 |
|---|---|---|---|
| emotion2vec | 容器 8000，宿主 `127.0.0.1:${SER_PORT}` | `8021` | 只绑回环，禁止绕过 nginx 直连（照抄 paddle `docker-compose.yml:20` 的取向） |
| ser-nginx | 容器 80，宿主 `0.0.0.0:${SER_NGINX_PORT}` | `8020` | 唯一对外入口，`X-API-Key` 鉴权；Java 与 worker 都只访问它 |

#### 8.2.1 `docker-compose.yml`

```yaml
# emotion2vec_plus_large SER 一体化部署：推理容器（CPU 或 GPU）＋ Nginx 反代鉴权
#
# 端口约定（与 paddle 同一取向：推理容器只监听 127.0.0.1，避免绕过 Nginx）：
#   emotion2vec  127.0.0.1:${SER_PORT}         -> 容器 8000
#   ser-nginx    0.0.0.0:${SER_NGINX_PORT}     -> 容器 80   （唯一对外入口）
#
# 对外路径（均需 X-API-Key）：/ser/v1/audio/emotion , /ser/health
#   即调用方把 base-url 配到 `http://<host>:8020/ser`，与 §4.2 的 `{SER_GATEWAY_BASE_URL}/v1/audio/emotion`
#   和 `{SER_GATEWAY_BASE_URL}/health` 两行逐字对得上；nginx 剥掉 `/ser` 前缀后转容器同名路径
# 免鉴权探针：/ser-nginx-health

services:
  emotion2vec:
    build:
      context: ./emotion2vec
      dockerfile: Dockerfile
    image: ${SER_IMAGE:-emotion2vec:1.0}
    container_name: emotion2vec
    restart: unless-stopped
    ports:
      - "127.0.0.1:${SER_PORT:-8021}:8000"
    environment:
      SER_MODEL_ID: ${SER_MODEL_ID:-iic/emotion2vec_plus_large}
      SER_DEVICE: ${SER_DEVICE:-cpu}          # cpu 或 cuda:0，分支 A 才改 cuda
      SER_MAX_INFLIGHT: ${SER_MAX_INFLIGHT:-2}
      SER_TORCH_THREADS: ${SER_TORCH_THREADS:-8}
    # 严禁挂载任何音频卷（§9 落盘禁令在部署层的体现）；不挂 volume 即无持久写路径
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://127.0.0.1:8000/health || exit 1"]
      interval: 30s
      timeout: 5s
      start_period: 120s    # 300M 模型加载比 OCR 慢，给足窗口免误判 unhealthy
      retries: 3
    deploy:
      resources:
        limits:
          memory: ${SER_MEM_LIMIT:-6g}

  ser-nginx:
    image: ${NGINX_IMAGE:-docker.m.daocloud.io/library/nginx:1.27-alpine}
    container_name: ser-nginx
    restart: unless-stopped
    depends_on:
      - emotion2vec
    ports:
      - "${SER_NGINX_PORT:-8020}:80"
    environment:
      API_KEY: ${API_KEY:?请先在 .env 中设置 API_KEY}
      SER_UPSTREAM: http://emotion2vec:8000
    volumes:
      - ./nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro
    healthcheck:
      # 同 paddle 的坑：alpine 下 localhost 优先解析 ::1，必须写 127.0.0.1
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ser-nginx-health >/dev/null || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
```

#### 8.2.2 `emotion2vec/Dockerfile`

离线策略直接复用 paddle 的两招（事实 21）： wheels 优先＋回退在线，以及**权重在构建期预热烘焙进镜像**，运行期不再联网。

```dockerfile
# emotion2vec_plus_large SER 推理镜像 —— 默认 CPU，可切 GPU（分支 A）
# 构建上下文：Demo-deploy/ser/emotion2vec
#
# 离线能力：
#   * torch/torchaudio 大体积轮子放 wheels/ 则离线安装；目录为空时回退清华源
#   * 模型权重在构建期预热下载并烘焙进镜像 /root/.cache/modelscope
#     => 运行期不联网，且不得挂载覆盖该目录的卷（照抄 paddle Dockerfile:45 的预热手法）

FROM docker.m.daocloud.io/library/python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    USE_TF=0 USE_FLAX=0 HF_HUB_OFFLINE=1 \
    PYTHONUNBUFFERED=1

RUN sed -i 's#deb.debian.org#mirrors.tuna.tsinghua.edu.cn#g' \
        /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsox-dev libgl1 libglib2.0-0 \
        curl ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# 1) 优先离线 wheels（含 torch/torchaudio），缺失则在线装 CPU 版
COPY wheels /wheels
RUN if ls /wheels/*.whl >/dev/null 2>&1; then \
        echo "[build] install from offline wheels" \
        && pip install --no-cache-dir /wheels/*.whl; \
    else \
        echo "[build] install torch CPU online" \
        && pip install --no-cache-dir \
             torch==2.3.1 torchaudio==2.3.1 \
             --index-url https://download.pytorch.org/whl/cpu; \
    fi

# 2) 服务栈与推理库
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 3) 构建期预热权重（顺便把“加载失败”提前到构建期暴露，而不是上线当天）
#    disable_update=True：禁掉 funasr 的版本检查联网请求（内网必失败）
RUN python -c "from funasr import AutoModel; \\\nAutoModel(model='iic/emotion2vec_plus_large', device='cpu', disable_update=True)"

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 8.2.3 `emotion2vec/requirements.txt`

版本写死，与 paddle 同一做法（其 `requirements.txt` 头注即要求这一点）：

```
# SER 服务依赖（版本写死保证可复现；torch/torchaudio 由 Dockerfile 处理，此处不重复声明）
funasr==1.2.7
modelscope==1.23.0
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.20
numpy==1.26.4
soundfile==0.2.1
```

> `fastapi`、`uvicorn`、`python-multipart`、`numpy` 四个版本与 `paddle/pp-ocrv6/requirements.txt` 逐字一致，目的是让两套镜像共用同一个 pip 缓存层与同一组已验证可装版本；换版须同时评估 OCR 侧。`funasr` 与 `modelscope` 上写的版本号是**本文的设计假定值**（仓内无这两个包的任何版本记录，因此本文不假装知道当前最新稳版）：实施时以 `pip index versions funasr` 当场取到的最新稳定版为准，并把**实际所用版本号**写进 `Demo-deploy/ser/README.md` 的版本清单（与 paddle README 第七章同格式）；§8.2.9-U1 的实测结论直接取决于此，未固定版本就无法复现。

#### 8.2.4 标签映射：官方 9 类 → 平台 5 类（本文与 SP-2 同源的五值）

官方模型卡（`iic/emotion2vec_plus_large`）列出的 9 类为：`angry`、`disgusted`、`fearful`、`happy`、`neutral`、`other`、`sad`、`surprised`、`unknown`，输出为 9 维 softmax（九维得分之和为 1）。映射到§4.1 的 `SER_EMOTIONS`：

| emotion2vec 输出 | 平台标签 | 理据 |
|---|---|---|
| `neutral`、`happy` | `calm` | 业务上两者都是「无需介入」，分开只会多出一种无意义告警等级 |
| `fearful`、`sad` | `anxious` | 同为低控制感／需安抚类，SP-2 文案「情绪波动，建议放缓节奏」适用 |
| `surprised`、`disgusted` | `agitated` | 高唤醒／排斥倾向，归入「激动」而非单独新增等级 |
| `angry` | `anger` | 一一对应 |
| `other`、`unknown` | **不输出，计为失败** | 官方设计上这两类就是「模型主动拒分类」的安全护栏；平台把它们当 `calm` 就是把「测不出」误记为「无情绪」，属于假数据（违反 §5.5） |
| — | `threat` | **本 provider 永不产生**。`threat` 是语义判断（要挟、威胁措辞），属于 SP-2 文本模型的能力域；声学信号里没有对应的分类。五值保留 `threat` 只为 provider 可替换性，§10.1 用例④仍要测「即便收到 `threat` 也不得定 danger」 |

#### 8.2.5 `emotion2vec/app.py`

与 `paddle/pp-ocrv6/app.py` 严格同构：惰性加载＋双重检查锁、同步推理走 `asyncio.to_thread`、`/health` 报 `gpu_available`、失败一律 `HTTPException` 不返回默认值。

```python
"""emotion2vec_plus_large SER 服务（§4.2 契约的实现件）。

端点
----
GET  /health  -> {"status":"ok","gpu_available":<bool>,"model":"<自报>",
                  "ready":<bool>,"persistence":false,"labels_supported":[...]}
POST /v1/audio/emotion (multipart: file=<wav 16k 单声道 int16>, sample_rate, language)
             -> {"emotion":"anger","confidence":0.68,"model":"...","latencyMs":412,
                 "rawLabel":"angry","scores":{...}}
             -> 非 2xx：400 音频非法 / 409 拒分类(other 或 unknown) / 429 并发满 / 500 推理失败

三个刻意的设计
--------------
1. 不落盘：入参字节直接解码为 ndarray。若本版本 funasr 的 generate 不接受数组而必须
   给路径，只允许写 /dev/shm（内存盘）且 finally 删除，绝禁写持久卷（§9）。
2. 不静默降级：`other`/`unknown` 与任何未知标签一律 409 拒答，而不是回 `calm`。
   worker 侧收到非 2xx 即计一次 failure，连续达阈触发断路（§4.3）。
3. 单并发门：SER_MAX_INFLIGHT 满时 429，而不是排队——转录链路宁可丢一段情感，
   不可把字幕拖慢（§3.1 形态①的延迟重叠假设）。
"""
import asyncio, os, re, threading, time
from io import BytesIO

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI(title="emotion2vec SER Service", version="1.0.0")

MODEL_ID = os.environ.get("SER_MODEL_ID", "iic/emotion2vec_plus_large")
DEVICE = os.environ.get("SER_DEVICE", "cpu")
MAX_INFLIGHT = int(os.environ.get("SER_MAX_INFLIGHT", "2"))
THREADS = int(os.environ.get("SER_TORCH_THREADS", "8"))

# 官方 9 类 -> 平台 5 类（§8.2.4，与 SER_EMOTIONS 同源）
LABEL_MAP = {
    "neutral": "calm", "happy": "calm",
    "fearful": "anxious", "sad": "anxious",
    "surprised": "agitated", "disgusted": "agitated",
    "angry": "anger",
}
REJECT = {"other", "unknown"}      # 模型主动拒分类，不得当成 calm

_lock, _sem = threading.Lock(), threading.Semaphore(MAX_INFLIGHT)
_model, _labels = None, None


def get_model():
    global _model, _labels
    if _model is None:
        with _lock:
            if _model is None:
                import torch
                torch.set_num_threads(THREADS)
                from funasr import AutoModel
                _model = AutoModel(model=MODEL_ID, device=DEVICE, disable_update=True)
                # 启动时仍模型自报的标签表，不自己写死拼写变体
                _labels = getattr(getattr(_model, "model", None), "labels", None)
    return _model


def _norm(label: str) -> str:
    """容错取字母标签：去掉官方可能带的 `<|angry|>` 包裹与 `0: angry` 序号前缀。"""
    s = re.sub(r"[<|>]", "", str(label)).strip().lower()
    return s.split(":", 1)[-1].strip() if ":" in s else s


def _decode(data: bytes, rate: int) -> np.ndarray:
    """wav 字节 -> float32 单声道数组（不写磁盘）。"""
    if not data:
        raise HTTPException(status_code=400, detail="empty audio")
    try:
        import soundfile as sf
        arr, sr = sf.read(BytesIO(data), dtype="float32", always_2d=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid audio: {exc}")
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    if int(sr) != int(rate):
        raise HTTPException(status_code=400,
                            detail=f"sample_rate mismatch: got {sr}, want {rate}")
    return arr


def _run(data: bytes, rate: int) -> dict:
    if not _sem.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="ser busy, retry later")
    try:
        model = get_model()
        audio = _decode(data, rate)
        t0 = time.monotonic()
        # 首选传数组；若本版本要求路径，见文件头说明 1 的 /dev/shm 方案
        res = model.generate(input=audio, fs=rate, sampling_rate=rate,
                             granularity="utterance", extract_embedding=False)
        first = (res[0] if isinstance(res, list) and res else res) or {}
        scores = first.get("scores") or first.get("emotion_scores") or []
        labels = first.get("labels") or _labels or []
        if not scores or len(scores) != len(labels):
            raise HTTPException(status_code=502,
                                detail=f"unexpected result shape: keys={list(first)[:8]}")
        idx = int(np.argmax(np.asarray(scores, dtype=np.float32)))
        raw = _norm(labels[idx])
        conf = round(float(scores[idx]), 4)
        if raw in REJECT:
            # 409 而不是 200：让 worker 计失败，不写标签（§5.5 失败语义）
            raise HTTPException(status_code=409,
                                detail=f"model refused classification: {raw}")
        emotion = LABEL_MAP.get(raw)
        if emotion is None:
            # 标签表与映射不一致 => 暴露而不是猜一个（与 asr_provider 的 raise 取向同源）
            raise HTTPException(status_code=502,
                                detail=f"unmapped label: {raw!r}")
        return {"emotion": emotion, "confidence": conf, "model": MODEL_ID,
                "rawLabel": raw, "latencyMs": int((time.monotonic() - t0) * 1000),
                "scores": {_norm(k): round(float(v), 4) for k, v in zip(labels, scores)}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ser failed: {exc}")
    finally:
        _sem.release()


@app.get("/health")
def health():
    import torch
    return {"status": "ok",
            "gpu_available": bool(torch.cuda.is_available()),
            "device": DEVICE, "model": MODEL_ID,
            "ready": _model is not None,
            "persistence": False,               # 服务侧不得具备任何持久化（§9）
            "labels_supported": sorted(LABEL_MAP) + sorted(REJECT)}


@app.post("/v1/audio/emotion")
async def emotion(file: UploadFile = File(...),
                  sample_rate: int = Form(16000),
                  language: str = Form("zh")):
    return await asyncio.to_thread(_run, await file.read(), sample_rate)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

`@app.post("/v1/audio/emotion")` 的路径字面量与 `@app.get("/health")` 一起，就是 §4.2 契约里 `{SER_GATEWAY_BASE_URL}` 后面的那两段，容器内不改名、不加版本层；对外的 `/ser` 前缀只由 nginx 的 `location /ser/` 负责剥与不剥（§8.2.6），worker 与 Java 只管把 base-url 配到 `http://<host>:8020/ser`。这样做而不是把容器路径简化成 `/emotion`：§4.2 是先于本节定下的对外契约，改服务内部路径的成本低于改双侧客户端与既有冒烟脚本。

#### 8.2.6 `nginx/default.conf.template`

```nginx
# SER Nginx 反代 + API Key 鉴权（照抄 paddle/nginx/default.conf.template 结构）
# 官方镜像启动时对本文件 envsubst，仅 ${VAR} 形式被替换，$host 等 nginx 变量原样保留。

server {
    listen 80;
    server_name _;
    default_type application/json;

    client_max_body_size 8m;          # 音频段比图片小，上限故意收紧
    proxy_connect_timeout 10s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_buffering off;

    location = /ser-nginx-health {
        return 200 '{"status":"ok","service":"ser-nginx"}';
    }

    # 外部 /ser/v1/audio/emotion -> 容器 /v1/audio/emotion；/ser/health -> /health
    # （前缀剥掉后路径不变，因此容器内路由与 §4.2 契约逐字相同）
    location /ser/ {
        if ($http_x_api_key != "${API_KEY}") {
            return 401 '{"error":"unauthorized","message":"missing or invalid X-API-Key"}';
        }
        proxy_pass ${SER_UPSTREAM}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        return 404 '{"error":"not found","routes":["/ser/v1/audio/emotion","/ser/health"]}';
    }
}
```

#### 8.2.7 `.env.example`

```bash
# ===== 复制为 .env 后再启动：Copy-Item .env.example .env =====

# ---------- 对外鉴权 ----------
API_KEY=change-me-please-use-a-long-random-string

# ---------- 端口（推理容器只绑 127.0.0.1） ----------
SER_NGINX_PORT=8020
SER_PORT=8021

# ---------- 模型与算力 ----------
SER_MODEL_ID=iic/emotion2vec_plus_large
# cpu = 分支 B（默认）。改 cuda:0 即分支 A，但必须先按 §8.4 量过延迟，
# 且注意 Demo-deploy/paddle/.env:14 与 paddle/README.md 第八章记录的
# CUDA 12.8 与 torch cu130 冲突、vllm 与 paddlepaddle-gpu 争 cudnn 的教训。
SER_DEVICE=cpu
SER_MAX_INFLIGHT=2
SER_TORCH_THREADS=8
SER_MEM_LIMIT=6g

# ---------- 镜像 ----------
SER_IMAGE=emotion2vec:1.0
NGINX_IMAGE=docker.m.daocloud.io/library/nginx:1.27-alpine
```

#### 8.2.8 `scripts/` 四个 ps1

四个脚本逐个照 `paddle/scripts/` 的真实写法实现，但不把它已踩过的坑一并抄过来（下列三条在 paddle 源码注释里是明文记着的）：

| 脚本 | 与 OCR 版的差异 | 必顶的原样保留项 |
|---|---|---|
| `deploy.ps1` | 服务名换 `emotion2vec ser-nginx`；等健康超时从 `600` 抬到 `900`（300M 模型） | `$ErrorActionPreference='Continue'` 加显式 `$LASTEXITCODE` 检查（docker 往 stderr 打 WARNING，Stop 模式会误断）；首次自动生成 `.env` 与随机 40 位 `API_KEY`；`Wait-Healthy` 用 `docker inspect --format '{{.State.Health.Status}}'` |
| `status.ps1` | 探活 URL 改 `127.0.0.1:$SER_PORT/health` 与 `127.0.0.1:$SER_NGINX_PORT/ser-nginx-health` | 末尾保留 `docker stats --no-stream`，分支 B 下这是看 SER 是否挤占 OCR 的 `OCR_CPU_THREADS=10` 的唯一手段（§8.4 资源条） |
| `verify.ps1` | 三段式：nginx 存活 → 无 key 应 401 → 用真 wav 打 `/ser/v1/audio/emotion` 断言 `emotion ∈` 五值；再追加两例负向：传全静音期望 409 或 502，**绝不能是 200 `calm`** | Windows PowerShell 5.1 不支持 `Invoke-RestMethod -Form`，必须用 `curl.exe -F`（paddle `verify.ps1` 注释已记此限） |
| `stop.ps1` | 同构 | 保留 `-Volumes` 开关与「模型缓存在镜像内，无需重下」的提醒 |

#### 8.2.9 本文尚未实测项（禁止当作已知）

与 paddle 不同，`ser/` 是一套**还不存在**的部署，所以本文不写「故障排查（已踩过的坑）」那一章——那是实测产物。以下五条必须在 G1 当场实测并把结果写回 `Demo-deploy/ser/README.md`，未回写前 SP-4 不得上线：

| # | 待实测项 | 为何不能先猜 |
|---|---|---|
| U1 | `funasr.AutoModel.generate` 能否直接收 ndarray，参数名是 `fs` 还是 `sampling_rate` | 决定 §9 不落盘能否不借助 /dev/shm；属库版本行为，README 必须记实际可用签名 |
| U2 | 返回体 `labels` 的字面量形态：裸字母（`angry`）、官方 tokens 那种「尖括号＋竖线包裹」形式、还是带序号前缀（`0: angry`） | `_norm()` 已容错这三种形态，但实际形态要留档，否则映射表无法审计（本性格式不在此文里原文引用，因它含会撑坏表格列数的竖线字符，以实测后回写 README 为准） |
| U3 | 3s 音频在分支 B（CPU、`SER_TORCH_THREADS=8`）上的 P50/P95 延迟 | §8.3 的 `1500 ms` 阈值是设计值，不是实测值 |
| U4 | 权重烘焙后的镜像体积与首次 `ready` 耗时（`start_period: 120s` 是否够） | healthcheck 给太短会反复重启，给太长会掩盖真故障 |
| U5 | 中文Demo方言、多人交叠下的标签有效性与人检一致率 | §8.4 门禁的第 3 行本就是为此而设，这里只记它的实测数据归口 |




### 8.3 自动降级阈值（可判定，非「视情况」）

| 触发条件（任一） | 动作 |
|---|---|
| SER P95 延迟连续 5 分钟 > `1500 ms` | 由 A 切 B（只处理一级门命中段）；`log.warn` 一条并在 `cost` 接口计数里可见 |
| 断路器 5 分钟内 OPEN ≥ 2 次 | 切 B 且 `maxConcurrency` 降为 `1` |
| 切 B 后仍满足上述任一 | Java 侧把 `ser` 卡片置 `available=false`、`reason` 写「SER 服务过载，已自动停用」，并停止向 worker 下发 `ser=true`（真正断流，不是仅提示） |
| 恢复条件：`/health` 连续 3 次成功且 P95 < `1000 ms` 持续 10 分钟 | 逐级回升 B → A；回升不自动到 A 之外 |

阈值全部落在 `meeting.ser.*` 与快照下发字段，调整不发版即可验证；**降级只减覆盖率，绝不产生假数据**，这是与 §5.5 一致的取向。

### 8.4 上线前置门禁（PoC，未过不得上线）

| 门禁 | 判据 |
|---|---|
| 延迟 | 用 3 段真实会议录音（10s、30s、60s）各跑 20 次，P95 ≤ 1500 ms |
| 资源 | 记录峰值显存或 CPU 线程占用；分支 B 在 2 并发下不得使宿主机 OCR 容器（同为 CPU，事实 20）的 `OCR_CPU_THREADS=10` 出现饥饿 |
| 标签有效性（人检） | 影子模式跑 2 场真实Demo会，声学标签与人工听记一致率 ≥ 70% 才可开启告警推送；不足则该能力停留在「只落库不展示」 |
| 无静默降级 | 关掉 SER 服务，确认前端 `available=false` 且告警流不出现任何 `kind='ser'` 新行（而不是出现 `calm`） |
| 拒分类行为 | 对一段 3s 全静音音频，服务必须回 409 或 502，**不得回 200 `calm`**（§8.2.4 映射表的后半段是这条的可执行版本） |
| 标签表一致性 | `verify.ps1` 拉 `/health` 的 `labels_supported`，与 §8.2.4 表格逐项比对；多、少、改名均判失败 |

模型许可：选型已定为 emotion2vec_plus_large（§8.2），但**许可与商用条款仍需实施时留档**——ModelScope 模型页需核实其权重许可证（代码仓库与应用文档声明可能不一致），若为仅研究用途，须按 §11 的同一逻辑改买商用授权或换模型。`ser_model` 仍是服务自报字符串，平台不解释。

---

## 9. 合规与安全

| 主题 | 决定 | 依据 |
|---|---|---|
| 音频落盘 | **禁止**。PCM 只在 worker 内存，请求发出即弃；容器不挂任何音频卷；worker 日志禁打音频、base64、`pcm` 长度以外的内容 | 事实 1 的 PCM 生命周期就是最短可行窗口；一旦落盘就要面对留存期与调取风险，而业务并不需要回放 |
| 持久化内容 | 只存标签、置信度、模型标识（§7）；不存时长、不存频谱、不存中间特征 | 数据最小化 |
| 告知与同意 | 复用 SP-1/2 的 `noticeConfirmed` 开关门，但确认文案必须新增「对语音语调做情绪倾向分析」一项；若走 SP-5 的留痕路径，则 `ai_party_consent.scope` 取 `SER_ANALYSIS`（事实 22，SP-5 §7.1 注释需增此枚举值，已登记为对 SP-5 的**注释级**修订） | 声音可用于生物识别，情绪推断触及心理健康相关信息，按最敏感的一项定标准而非争论归类 |
| 定性禁令 | UI 文案与后端枚举都不得出现「愤怒」「具有攻击性」等断言式表述，一律「疑似…请主持人确认」；告警卡必须显示「声学推断，非情绪定性」 | §5.2；SP-1/2 不变量③ |
| 用途限制 | ser 结果不得写入Demo协议书、不得作为责任或诚信的依据、不得用于按自然人聚合画像 | §1.2 |
| 留存期 | ser 三列生命周期随所在表：`ai_meeting_alert` 随纪要留存（长期，含审计需要）；`ai_meeting_transcript` 按既有转录清理策略（SP-1/2 未定清理期，本文不擅自改他表留存，只声明自身列随表清理，并在 §11 记为待与 SP-1/2 合并决策） | 避免本文替 SP-1/2 做未授权的留存决策 |
| 撤回 | 关开关即刻停止采集（快照 `ser=false` → worker 30s 内生效，最长 30s 的残余采集须写进告知文案，不得隐瞒） | 30s 是 §3.2 步骤 1 的轮询周期，不是可忽略误差 |
| 密钥 | `X-API-Key` 与 `MEETING_INTERNAL_TOKEN` 一律走环境变量占位符，禁止写进 YAML 明文（现存 `paddle.ocr.api-key` 硬编码是反面例，见 §11） | 与 `VoiceGatewayProperties` L9 注释的既有约定一致 |

---

## 10. 测试与验收

### 10.1 后端单测（JUnit5 ＋ Mockito，测试类镜像被测类包结构）

| 测试类 | 必录用例 |
|---|---|
| `MeetingSerGuardServiceImplTest` | ①`meeting.ser.enabled=false` → `status` 返回 `available=false` 且 `reason` 非空，`toggle` 不写开关行；②探活失败 → 同上；③探活成功且 `noticeConfirmed` 缺失 → 抛 `1_040_061_006` |
| `MeetingSerFusionServiceTest` | ④**声学永不单独 danger**：输入 `emotion=threat, confidence=0.99` 且无文本告警 → 落行 `kind='ser', level=2`（断言 `level != 3`）；⑤A 情形：已有文本告警 → 只补写三列，`level` 与 `message` 恒等，且 `verify(alertMapper, never()).insert(any(MeetingAlertDO.class))`；⑥`confidence < minConfidence` → 零写入零告警；⑦`ser_emotion='calm'` 且无文本告警 → 仅回写 transcript，无告警行；⑧补写二次幂等：第二次 `fillSerEvidenceIfAbsent` 影响行数 0 |
| `MeetingSerIngestGuardTest` | ⑨worker 传来 ser 值但服务端开关为关 → transcript 三列写 null 落库，`log.warn` 被调用，零告警行（§3.2 步骤 4 的纵深防御） |
| `MeetingAlertMapperSerIndexTest` | ⑩同 `transcript_id` ＋ 不同 `kind` 两行可共存；⑪同 `(transcript_id, kind)` 二次插入被唯一索引挡掉且不抛给调用方 |
| `MeetingSerSwitchSnapshotTest` | ⑫`@SpringBootTest` 断言注册路径为 `/admin-api/ai/meeting/internal/analyze/switch` 且不存在 `admin-api/admin-api` 前缀（承接 SP-1/2 §6.5 的双前缀回归锁）；⑬密钥不符 → `1_040_064_003`；⑭快照含 `serPolicy` 五个字段且 `video=false` |

### 10.2 worker 侧（pytest，只测纯函数，不依赖 LiveKit 房间）

| 用例 | 断言 |
|---|---|
| 段长门 | 0.5s、1.0s、30.0s、30.1s 四例的发起或不发起正确 |
| 标签解析 | `SerResult.from_response` 对未知 `emotion`、`confidence` 越界、缺字段三种畸形响应均 `raise` |
| 断路器 | 连续 3 次失败进入 OPEN，冷却期内发起次数 0，恢复后再次可用 |
| 开关快照 fail-closed | 快照 HTTP 500、超时、非法 JSON、`ser` 键缺失四种情形均判定 `ser=false` 且零外呼 |
| `SER_PROVIDER` 未配置 | `get_ser_provider()` 抛 `ValueError`（不允许默默返回 `None` 后带病运行） |
| `_to_wav` 复用 | 断言 `ser_provider` 未定义第二个同名函数（`import asr_provider; assert ser_provider._to_wav is asr_provider._to_wav`） |

### 10.3 前端 vitest

| 文件 | 用例 |
|---|---|
| `analyze.spec.ts`（扩展现有，不新建第二套） | `applySwitch` 对第三张卡同样以服务端返回为准；`ser.available=false` 时开关 `disabled` 且显示 `reason`；三卡独立，切 `ser` 不改 `on.voice` |
| `alertCard.spec.ts` | 有 `serEmotion` 时依据栏出现「声学情感」且同时显示「非情绪定性」；`serEmotion=null` 时该行不渲染（不得显示空标签或默认 `calm`） |

### 10.4 端到端冒烟（内网，需 SER 服务可达）

```powershell
# 1) 探活：GET {base}/ser/health → {"status":"ok","gpu_available":...,"model":"..."}
# 2) 单发：用 Demo-deploy/paddle/samples 之外的任意 16k 单声道 wav 打 /ser/v1/audio/emotion
#    → 期望 200 且 emotion ∈ 五值；再打一个畸形请求 → 期望非 200，worker 侧计入断路
# 3) 关开关（meeting.ser.enabled=false）灌一段含「逼我」的分段
#    → transcript 的 ser 三列为 NULL，ai_meeting_alert 仅 1 行 kind='voice'（证明零成本与守卫生效）
# 4) 开开关重灌同一段 → 2 行：kind='voice' 1 行 ＋ kind='ser' 1 行，或 voice 行被补写 ser 列
#    （依 §5.3 情形判定，两种都算通过；断言 level 未被声学改动）
# 5) 停掉 SER 容器 → 60s 内 status 的 ser.available=false，且告警流无新增 ser 行
# 6) 双前缀回归：/admin-api/admin-api/ai/meeting/internal/analyze/switch 必须 404 或 401
# 7) 隐私负向：跑完一场后在 worker 容器内 find / -newermt -mmin -5 -size +100k
#    → 不得发现任何 wav、pcm、mp3 文件（§9 落盘禁令的可执行版本）
```

### 10.5 验收指标

| 指标 | 阈值 | 口径 |
|---|---|---|
| 声学单独定 danger 次数 | 0 | 全量 `kind='ser'` 行 `level` 分布，用例④ ＋ 上线后 SQL 巡检 |
| SER 停用期间的假数据 | 0（不得出现默认 `calm`） | `ser_emotion IS NOT NULL` 且开关关闭时段交叉核查 |
| 端到端时延 | 段入库到 `alert` 事件 P95 ≤ 5s（与 SP-2 同口径，声学不额外突破） | 服务端日志时间差 |
| 一级门覆盖率（分支 B） | 被分析段数 ÷ 总段数 ∈ `[20%, 45%]` | `ser` 分析计数与 `segCount`，用于暴露漏检而非掩盖 |
| 零成本 | `ser` 未开启时 SER 服务侧访问日志 0 条 | 服务侧日志 ＋ 用例⑨⑬ |
| 音频落地 | 容器内音频文件数 0 | §10.4 步骤 7 |
| 告知残余窗口 | UI 与文案均写明「关闭后最长 30s 仍在采集」 | 文案与 `notice` 组件断言 |

---

## 11. 风险与遗留

| 项 | 状态 | 处置 |
|---|---|---|
| SER 模型在中文Demo场景、方言、多人交叉语境下的准确率无任何本地证据 | 高不确定 | §8.4 PoC 门禁 ＋ 影子模式先行；未过人检一致率则只落库不上屏 |
| 情绪标签的个体与文化差异可能系统性偏置（如把方言的高抑扬读成 `anger`） | 未评估 | §9 用途限制禁止用于对人的负面认定；§8.4 人检环节专门看这类误标 |
| SP-1/SP-2 尚未实现（`MeetingAnalyzeService`、`RiskLexicon`、`MeetingAlertDO`、`ai_meeting_alert` 均为设计态，代码 grep 零命中） | 事实 | **本文以 V3.49 已落地为硬前置**（§7），SP-2 未落地时 SP-4 不可单独上线；两份 spec 的实施顺序不可颠倒 |
| 一级门音量 `-18 dBFS` 与声学信号同源（都是这段 PCM 的能量） | 有意保留 | 声学侧不再用音量做门（避免同一信号被两次计入决策），音量只属于 SP-2 的文本门；此处边界写在 §5.3 情形表里 |
| worker 单实例本期串行 2–4 轨（`worker.py` 模块注释 L15），加 SER 并发会加剧 | 中 | `maxConcurrency` 默认 `2` ＋ 非阻塞等位（§4.3）；多副本评估属 M20 范畴，本文不扩范围 |
| `MediaAnalysisServiceImpl` 的伪「情感时间线」已在前端可见，易被误认为 SP-4 已交付 | 高（认知风险） | 建议与 SP-4 同期改造：`getCapabilities()` 改为按真实 provider 探活；四个 mock 方法显式抛 `ServiceException`，与 SP-5 里 `recognizeByLocalModel` 的诚实未实现写法一致（该写法已核实为真实存在） |
| 30s 开关轮询窗口＝关闭后的残余采集 | 设计取舍 | 已在 §9 要求写进告知文案；若合规不接受，改为 SSE 反向推送，代价是 worker 需常驻第二通道，届时另立设计 |
| 密钥硬编码反面例：`application-dev.yaml` 里 `paddle.ocr.api-key` 有明文默认值 | 现存问题，不属本文 | SP-4 的 `meeting.ser.api-key` 严禁照抄该写法；建议单开一次配置卫生清理 |
| 转录与告警的留存期未定（SP-1/2 未决策） | 跨 spec 缺口 | §9 已声明本文不擅自替他表决策，登记为需与 SP-1/2 合并决策的项 |

---

## 12. Spec 自检（写完后逐条核对）

| 检查项 | 结论 |
|---|---|
| 占位符 | 无 `TODO`、`TBD`、`FIXME`、`待定`、`待补充`、`xxx`（§2 事实 14 里的 `TODO` 是在**引述被测代码的现状缺陷**，不是本文遗留）；每张表每格均有内容；§8.2.9 的 U1–U5 不是占位，而是带验收人与回写目标的待实测清单（未回写即不得上线） |
| 内部一致性 | `kind='ser'` 全文 8 处、`kind=ser`（无引号的配置与注释写法）3 处，拼写完全一致（Node 实测）；五值标签集在 §1.1、§4.1、§5.1（按行枚举）、§6.2、§7 列注释、§8.2.4 右列六处同源，§10.2 的 worker 用例只断言「未知标签即 raise」而不重列五值（避免第七处拷贝）；错误码只用 `1_040_064_*`（§6.3 四条 ＋ §6.1 引用既有 `1_040_061_006` 一处，已标明是复用）；迁移号只用 `V3.55`；菜单不新增且给出复议条件；服务路径在 §4.2、§8.2.1、§8.2.5、§8.2.6、§8.2.8、§10.4 六处逐字对得上（容器 `/v1/audio/emotion` ＋ `/health`，对外加 nginx 前缀 `/ser`） |
| 号段冲突 | 事实 17、18、19 逐条对三份已交付 spec 交叉核查：`064`、`V3.55`、菜单不占用，与 SP-1/2（`061_005-007`、`V3.49-3.51`、`9499-9500`）和 SP-5（`063_*`、`V3.52-3.54`、`9501-9504`）不重叠；与 SP-3 的 `065_*`、`V3.56-3.57`、`9505-9507` 也不重叠；deploy 端口本文取 `8020/8021`，OCR 取 `8011`、SP-3 取 `8030/8031`，三者互不冲突 |
| 对上游的修订是否显式 | **六条**：S1–S5 在 §0，其中 S2 标注为破坏性修订并给出重建索引与回滚注意事项；**第 6 条为统一门禁与统一同意口径** —— §3.3 的 `video` 由「恒 false」改为 `available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)`（修订索引 #3），§9 的 `SER_ANALYSIS` 并入 `ai_party_consent.scope` 五值、共用 `version` 等值语义与 `revoked_at` 撤回机制，`noticeConfirmed` 降级为操作人确认动作（修订索引 #4）；§0 另登记对 SP-5 同意表 `scope` 注释的追加 |
| 未验证即写入的内容 | 本文不声明已有 SER 服务在跑（事实 13：全仓零痕迹）。§8.2 按用户指令点名 `iic/emotion2vec_plus_large`，但写的全是**设计值与官方口径**：官方 9 类标签、~300M、16k 输入、softmax 得分、`other/unknown` 为主动拒分类，均取自官方模型卡与 funasr 用法文档；而本仓的部署件尚不存在，因此 §8.2.9 列 U1–U5 五项**禁止当作已知**的待实测项，并要求未回写 README 前不得置启用开关；许可与商用条款仍未核实，挂在 §8.4 与 §11。同理，本文不写「故障排查（已踩过的坑）」那一章 |
| 行内代码跨行 | 已检查，无反引号跨行；§11 表格里提及的类名与配置键均为单行内联代码 |
| 表格内裸竖线 | 已检查：单元格内表达并列一律用「＋」或文字「或」；全文**未出现任何裸竖线或未转义竖线**——§8.2.9-U2 本要引用官方那种「尖括号＋竖线包裹」的标签字面量，为了不撑坏本表列数而改用文字描述而不直引；Node 校验器实测全文 `BAD_ROWS=0`、`EMPTY_CELL=0`（本行上一稿曾自破一次：为了举例而写了一个反引号包裹的竖线，恰好把本表列数撑成 3，当场被抽到） |
| ASCII 图示对齐 | §3.2、§8.2（目录树）、§10.4 为纯文本缩进流程与命令，行首统一用 ASCII 减号加空格作层级前缀，**不使用制表符边框字符**（此类字符属歧义宽度，中文环境按全角渲染会散架）；首稿曾使用树形连接符 24 个，本轮插入 §8.2 后重新实测，全文 `BOXDRAW=0` |
| 编码与换行 | UTF-8 无 BOM、LF、无制表符、无替换字符 |
| 硬约束遵循 | 未修改任何生产代码；未 git commit；接口路径与字段名全部来自 §2 实读出处；色值不涉及（本文无 UI 样式变更，仅新增文案与字段） |

---

## 13. 交付清单（实施完成后逐项存在）

- `Demo-ai/deploy/livekit-worker/`：`ser_provider.py`（`SER_EMOTIONS`、`SerResult`、`SerProvider`、`HttpSerProvider`、`get_ser_provider`、断路与段长门）；`worker.py` 两处挂载改动（ser 任务并行 ＋ push 三键）；`requirements.txt` 不新增依赖（`requests` 已有）；`Dockerfile` 不变（CPU 基础镜像）
- `Demo-module-ai-server`：`MeetingTranscriptInternalController` 增 `switchSnapshot`；`service/meeting/MeetingSerAvailabilityService`（探活与缓存）；`MeetingSerFusionService`（§5.3 三情形）；`TranscriptSegmentVO`、`MeetingAlertVO`、`MeetingTranscriptDO`、`MeetingAlertDO` 加字段；`MeetingAlertMapper` 加两个方法；`config/MeetingSerProperties`；`ErrorCodeConstants` 加 `1_040_064_000-004`；`AnalyzeLevelEnum` 或 `AlertLevel` 加 §5.1 四条文案
- `Demo-ai/docs/sql`：`V3.55__meeting_ser_columns.sql`
- `Demo-web`：`AnalysisPanel.vue` 第三张卡（`SP-4 · P1`）、`analyze.ts` 三卡状态、告警卡依据栏 ser 字段与「非情绪定性」标注
- `Demo-deploy/ser/`：`docker-compose.yml`、`emotion2vec/{app.py,Dockerfile,requirements.txt,wheels/}`、`nginx/default.conf.template`、`scripts/{deploy,status,verify,stop}.ps1`、`.env.example`、`README.md`（含 §8.2.9 五项实测回写，未回写不得置 `MEETING_SER_ENABLED=true`）
- 测试：Java 5 个测试类（§10.1）、worker pytest（§10.2）、前端 vitest 扩展（§10.3）、冒烟脚本（§10.4）
- 文档：SP-1/SP-2 spec 的 §5、§7.1、§8、§11 四处按本文 §0 做修订登记（本文单向声明，不代改其原文，实施时同步更新；2026-11-06 已同步）

### 13.1 实施状态（2026-11-06，逐项对照上表）

| 清单项 | 状态 | 证据 |
|---|---|---|
| worker `ser_provider.py` 与 `worker.py` 两处挂载 | 已交付 | `SER_EMOTIONS`/`SerResult`/`HttpSerProvider`/`get_ser_provider`、段长门、非阻塞并发门、断路器、快照 fail-closed、30s 轮询、ASR 与 SER 用 `asyncio.gather` 并行；`_to_wav` 仍从 `asr_provider` import 复用；`requirements.txt` 与 `Dockerfile` 未变 |
| Java 服务、VO/DO、Mapper、错误码、`AlertLevel` | 已交付 | `MeetingSerProperties`、`MeetingSerAvailabilityService`（真实 `/health` 探活＋TTL）、`fillSerEvidenceIfAbsent`（`WHERE ser_emotion IS NULL`）、§5.1 四条文案、`1_040_064_000–004` 对齐 §6.3（保留旧符号别名）、`switchSnapshot` 下发完整五字段策略 |
| `V3.55__meeting_ser_columns.sql` | 已交付 | 三列 × 2 表、`(transcript_id, kind)` 部分唯一索引、回滚顺序说明；已在共享库执行并 COMMIT（见修订方案 §7.5） |
| 前端第三卡与告警依据栏 | 已交付 | 卡片由服务端 `statuses` 驱动不硬编码；`serEmotion=null` 不渲染；「非情绪定性」与「关闭后最长 30s」文案齐备 |
| `Demo-deploy/ser/**` | 已交付（**未运行**） | compose 带 `build:`、emotion2vec 四件套、`/ser` 前缀 nginx、4 个 ps1 ＋ `e2e-smoke.ps1`、README 取证表；镜像未构建、容器未起 |
| 测试 | 已交付 | Java 5 个测试类 23 例、worker 25 例、前端 60 例全绿；`mvn -o -nsu` 编译通过 |
| SP-1/SP-2 spec 四处修订登记 | 已交付 | 见该文档 2026-11-06 修订索引条目与四处正文注记 |
| §8.2.9 U1–U5 实测、§8.4 六条 PoC 门禁、许可留档、真机联调 | **未完成（门禁）** | `Demo-deploy/ser/README.md` 全部保持「待测」；`MEETING_SER_ENABLED` / `MEETING_SER_POC_PASSED` / `MEETING_G3_SER` 恒 `false`、`SER_PROVIDER=none`。这四项须真人真机与外部服务，不得由开发会话代填 |

> 判读口径：**代码层完成 ≠ 能力上线**。本设计的上线条件仍是 §8.4 六条门禁全过、U1–U5 回写、模型商用许可留档并由人工显式置位；在此之前 `ser` 卡片 `available=false`，worker 零外呼，Java 第二次守卫把入站 `ser_*` 写 `NULL`。
