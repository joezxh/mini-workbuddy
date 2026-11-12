# 视频会议 + 语音能力 Demo（P0）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 mediation_platform 落地本期 P0 的两条并行演示线——① 基于 LiveKit 的视频会议 Demo（后端 token/房间 + Python 转录 worker + SSE 字幕 + 会后纪要草稿→确认回写案件）；② 直连 137 的语音能力演示（ASR 转写 + TTS 合成，单菜单双 Tab，含客户端 Silero VAD 分段）。

**Architecture:** 媒体面浏览器直连 livekit-server（7880/7881/7882），控制面（token、房间、字幕、纪要）经 Java REST/SSE 并纳入登录态与菜单权限；转录面由独立 Python `livekit-agents` worker 以"参会者"进房逐轨转写，经带共享密钥的内部 REST 回推 Java 落库并 SSE 下推。语音演示线与会议线**完全解耦**（不依赖 LiveKit/worker/token），由 `VoiceGatewayClient`（Hutool HTTP）经 Java 代理直连 137:8765 的 `/v1/audio/transcriptions`、`/v1/audio/speech`，前端不直连内网 137。

**Tech Stack:** Java 21 + Spring Boot 3.5 + MyBatis-Plus + PostgreSQL（运行时数据源）+ Redis + Hutool（HTTP/JWT）；Python `livekit-agents`；前端 Vite + Vue 3.5 + ant-design-vue 4.2.6 + `livekit-client` + `@ricky0123/vad-web`；vitest + vue-tsc + JUnit5 + Mockito。

**设计基线：** `mediation-docs/superpowers/specs/2026-11-03-meeting-ai-capability-design.md`（M1–M20 已锁定）。本计划严格对齐该 spec 的 §3（会议架构）、§5（错误码/配置/表）、§12（语音 Demo）、§13（菜单/权限/前端落点）。

---

## 关键事实与全局约定（执行前必读）

以下事实已在计划阶段核实到代码，实施时**不得臆造、须遵循**：

1. **模块与包根**：后端落 `mediation-ai/mediation-ai-module/mediation-module-ai-server`，基础包 `com.tianque.module.ai`。会议线新增子包 `com.tianque.module.ai.meeting.*`，语音线新增 `com.tianque.module.ai.voicedemo.*`（M8：**不新建 Maven 模块**）。
2. **Controller 路径前缀**：AI server 经网关 `ai-admin-api`（`Path=/admin-api/ai/**`，除 v3/api-docs 外不 StripPrefix）。既有 `controller.admin.disputehall.MediaAnalysisController` 用**字面全路径** `@RequestMapping("/admin-api/ai/media-analysis")`，本计划会议/语音 controller 一律**对齐该字面量约定**（`/admin-api/ai/meeting`、`/admin-api/ai/voice-demo`），前端 `BASE` 同样带 `/admin-api/ai/...`。**每个 Track 的首个 controller Task 第一步必须先 `Read` `MediaAnalysisController.java` 确认装配方式后再落 `@RequestMapping`**（若核实为依赖框架自动前缀，则去掉字面 `/admin-api` 前缀，两种约定二选一、全模块统一）。
3. **错误码**：`com.tianque.module.ai.util.ErrorCodeConstants`（`1-040-xxx-xxx` 段，末段当前到 `1_040_016_xxx`）。会议段用 **`1_040_061_xxx`**、语音段用 **`1_040_062_xxx`**（两段经全仓检索确认**未被占用**，与 spec §5.1 一致）。用 `new ErrorCode(code, "msg")`，占位符 `{}`。
4. **异常与返回**：统一 `CommonResult<T>`（`import static com.tianque.framework.common.pojo.CommonResult.success;`）；业务异常 `throw exception(ERROR_CODE)`（`com.tianque.framework.common.exception.ServiceException`）。SSE 端点返回 `SseEmitter`（非 CommonResult），并设 `X-Accel-Buffering: no`。
5. **HS256 自签 token（M4）**：复用 Hutool JWT（`cn.hutool.jwt.JWT` / `JWTUtil`，`hutool-all` 5.8.41 已在 `mediation-common` 传递依赖内，无需新增库）。本地 LiveKit keys 见 `scratch/livekit.yaml` = `devkey: secret`；生产须换 ≥32 位（§9-7），值走 `application.yaml` 占位符 `${LIVEKIT_API_KEY}/${LIVEKIT_API_SECRET}`，**不硬编码**（M17）。
6. **137 语音服务（§2.1 实测）**：ASR `POST /v1/audio/transcriptions` 仅返 `{"text","language"}`（无服务端分段/时间戳）；TTS `POST /v1/audio/speech` JSON→**24kHz mono WAV**（`response_format`/`speed` 解析但忽略/未生效）；合法音色 9 个（`Vivian/Serena/Uncle_Fu/Dylan/Eric/Ryan/Aiden/Ono_Anna/Sohee`）+ 自定义；单实例串行（`/v1/pool size:1`）；**无鉴权**（`api_key=not-needed`），`api-key` 配置为占位。base-url 走 `${VOICE_GATEWAY_BASE_URL}`（= `http://192.168.1.137:8765`），内网地址属敏感信息不硬编码。
7. **客户端 VAD（M18）**：时间戳分段由前端 `@ricky0123/vad-web`（WASM/ONNX）在录音模式切段逐段送转写；会议链路由 worker 用 `silero-vad` 逐轨切段。
8. **前端 SSE**：GET 字幕流复用 `stores/superagentFeed.ts` 的**裸 fetch + `buildAuthHeaders()`**（`Authorization: Bearer`、`tenant-id`）范式，而非 `EventSource`（后者无法带鉴权头）。TTS blob 下载/播放用 `@/utils/request` 的 `download`（`responseType:'blob'`）或直接 `post` 取 blob。
9. **回写安全边界（M7）**：`MeetingMinutesService` 只产 `status=DRAFT` 草稿、**绝不写业务表**；仅主持人 `confirm` 后经 `SuperagentCheckpointManager`（`AWAITING_CONFIRM(2)→DONE(3)`）状态机 + `CaseContextApi.addMediationRecord(AddMediationRecordRequest)` 回写并落 `AgentOperationLogDO`（`chatId/sessionId/toolName/args/riskLevel/success`）。
10. **PG 方言**：建表用 `BIGSERIAL`/`JSONB`/`TIMESTAMP`/`COMMENT ON`/独立 `CREATE INDEX`（名加表名前缀）；公共列 `creator/create_time/updater/update_time/deleted/tenant_id`（DO 继承 `TenantBaseDO`）。菜单表是 **`uaa_menu`**（非 system_menu），列集含 `path/icon/component/component_name/status/visible/keep_alive/always_show`；超管授权 `uaa_role_menu.id = 100000 + menu_id`。迁移脚本落 `mediation-ai/docs/sql/V3.xx__*.sql`，**当前最大号 V3.44 → 本计划起用 V3.45**。每条线脚本首段用 Step-0 防呆 `DO $$ ... RAISE EXCEPTION`（沿用 V3.40 范式）。
11. **菜单 ID（§13.2）**：会议线 9490–9494、语音线 9495–9498；9484–9489 留缓冲，避让既有 9460–9472/9480–9483。
12. **测试**：后端 JUnit5 + Mockito（`@MockitoSettings(strictness = Strictness.LENIENT)`，`@InjectMocks` 单构造函数注入）。纯逻辑（token grants、纪要 DRAFT 不变式、分段拼接、错误码映射）走单测；HTTP/DB/WebRTC 走冒烟验证。前端 vitest 测纯函数（参数拼装、VAD 段→请求映射、voice api）。检查命令：后端 `mvn -pl mediation-ai/mediation-ai-module/mediation-module-ai-server test`；前端 `pnpm type-check && pnpm lint`（在 `mediation-web`）。
13. **提交**：遵循 mediation_platform git 规范（见 `git-commit.md`），Conventional Commits + `zhangxuhui` 分支、**不擅自 push**。频繁小提交，每个 Task 末尾提交一次。

**本地依赖前置（§7/§8）**：`mwb-livekit` 容器（`scratch/livekit.yaml`，7880/7881/7882）、`redis`（6379，`--requirepass password123`）已在跑且 Redis 已接入；137:8765 从开发机可达（§9 Q12 定案）。worker 与 livekit-server 须能经**同一 Redis** 组网。

---

## 文件结构（File Structure，先锁定分解）

### 后端 · 语音线（`com.tianque.module.ai.voicedemo`，新增）
```
voicedemo/
├── controller/admin/voicedemo/VoiceDemoController.java     # /ai/voice-demo/asr/transcribe, /tts/synthesize, /health
│   └── vo/{AsrTranscribeRespVO, TtsSynthReqVO}.java
├── service/voicedemo/{VoiceDemoService, impl/VoiceDemoServiceImpl}.java
├── client/VoiceGatewayClient.java                          # Hutool HTTP：STT multipart / TTS JSON / 存活探测
└── config/VoiceGatewayProperties.java                      # @ConfigurationProperties("voice.gateway")
```
改：`util/ErrorCodeConstants.java`（+`1_040_062_xxx` 段）、`resources/application.yaml`（+`voice.gateway.*`）。

### 前端 · 语音线（`mediation-web/src`，新增）
```
api/ai/voiceDemo.ts                                         # asrTranscribe(multipart)/ttsSynthesize(blob)/health
views/ai/voice-demo/
├── VoiceDemo.vue                                           # a-tabs 双 Tab（按权限过滤）
└── components/{AsrPanel.vue, TtsPanel.vue, VadRecorder.vue}
```
加依赖：`@ricky0123/vad-web`。测：`api/ai/__tests__/voiceDemo.spec.ts`、`views/ai/voice-demo/__tests__/*.spec.ts`（纯函数）。

### 后端 · 会议线（`com.tianque.module.ai.meeting`，新增）
```
meeting/
├── controller/admin/meeting/{MeetingController, MeetingMinutesController}.java
│   └── vo/{MeetingRoomCreateReqVO, MeetingTokenReqVO, MeetingTokenRespVO, MeetingRoomRespVO,
│            TranscriptSegmentVO, MinutesDraftRespVO, MinutesConfirmReqVO}.java
├── controller/internal/MeetingTranscriptInternalController.java   # worker 回推，@PermitAll+共享密钥
├── service/meeting/{MeetingTokenService, MeetingRoomService, MeetingTranscriptService, MeetingMinutesService}.java
│   └── impl/*.java
├── dal/dataobject/meeting/{MeetingRoomDO, MeetingParticipantDO, MeetingTranscriptDO, MeetingMinutesDO}.java
├── dal/mysql/meeting/{MeetingRoomMapper, MeetingParticipantMapper, MeetingTranscriptMapper, MeetingMinutesMapper}.java
└── enums/{MeetingStatus, ParticipantRole, MinutesStatus}.java
```
改：`util/ErrorCodeConstants.java`（+`1_040_061_xxx` 段）、`resources/application.yaml`（+`livekit.*`/`meeting.*`）。
新增 SQL：`docs/sql/V3.45__meeting_tables.sql`、`V3.46__meeting_menu.sql`、`V3.47__voice_demo_menu.sql`、`V3.48__meeting_minutes_prompt.sql`。

### worker（Python，新增 `deploy/livekit-worker/`）
```
deploy/livekit-worker/
├── worker.py            # livekit-agents entrypoint：进房订阅各音轨→silero-vad 切段→AsrProvider→回推 Java
├── asr_provider.py      # AsrProvider 抽象 + QwenAsrProvider(137) + DashScopeAsrProvider(外网备选)
├── requirements.txt     # livekit-agents, livekit-plugins-silero, requests, dashscope(可选)
├── Dockerfile
└── README.md            # 启动/组网/环境变量
```

### 前端 · 会议线（`mediation-web/src`，新增）
```
api/ai/meeting.ts                       # createRoom/token/room get·page/end/transcript-stream/minutes draft·confirm
views/ai/meeting/
├── MeetingList.vue                     # 列表 + 快速建房(绑 caseId)
├── MeetingRoom.vue                     # 会中主界面（livekit-client Room）
└── components/{VideoGrid, LocalTile, RemoteTile, ControlBar, ParticipantList,
               CaptionPanel, MeetingStatus, MinutesDrawer}.vue
```
加依赖：`livekit-client`。

---

## Track V：语音能力演示（voicedemo，直连 137，可先行冒烟，与会议线并行）

> 对应 spec §12、§4 G/H、§13。零 LiveKit 依赖。错误码 `1_040_062_xxx`，权限 `ai:voice-demo:{query,asr,tts}`，菜单 9495–9498。

### Task V1: 错误码 + VoiceGatewayProperties 配置

**Files:**
- Modify: `mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/util/ErrorCodeConstants.java`
- Create: `.../com/tianque/module/ai/voicedemo/config/VoiceGatewayProperties.java`
- Modify: `.../src/main/resources/application.yaml`

- [ ] **Step 1: 追加语音演示错误码段**

在 `ErrorCodeConstants` 接口末尾（`CAPABILITY_FILE_RECOGNIZE_FAILED` 之后、`}` 之前）追加：

```java
    // ========== 137 语音演示（voicedemo）1-040-062-000 ==========
    ErrorCode VOICE_GATEWAY_UNAVAILABLE = new ErrorCode(1_040_062_000, "语音服务不可用（137 不可达）: {}");
    ErrorCode VOICE_ASR_TRANSCRIBE_FAILED = new ErrorCode(1_040_062_001, "ASR 转写失败: {}");
    ErrorCode VOICE_ASR_AUDIO_EMPTY = new ErrorCode(1_040_062_002, "ASR 缺少音频");
    ErrorCode VOICE_TTS_SYNTH_FAILED = new ErrorCode(1_040_062_003, "TTS 合成失败: {}");
    ErrorCode VOICE_TTS_TEXT_EMPTY = new ErrorCode(1_040_062_004, "TTS 文本为空");
```

- [ ] **Step 2: 新建配置属性类（全占位符，对齐 spec §5.3）**

`voicedemo/config/VoiceGatewayProperties.java`：

```java
package com.tianque.module.ai.voicedemo.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * @author zhangxuhui
 * @description 137 语音网关配置（ASR/TTS 演示直连；base-url/api-key 属敏感信息，全部走占位符，不硬编码 M17）
 */
@Data
@Component
@ConfigurationProperties(prefix = "voice.gateway")
public class VoiceGatewayProperties {
    /** REST 基址，例 http://192.168.1.137:8765 */
    private String baseUrl;
    /** S2S 实时（P1 对照预留，本期不用） */
    private String realtimeWsUrl;
    /** 现部署 not-needed，占位以备加鉴权 */
    private String apiKey;
    /** ASR 模型，默认 qwen3-asr */
    private String asrModel = "qwen3-asr";
    /** TTS 模型，默认 qwen3-tts */
    private String ttsModel = "qwen3-tts";
    /** 默认音色 */
    private String defaultVoice = "Aiden";
    /** 连接超时(ms) */
    private int connectTimeout = 5000;
    /** 读取超时(ms)，长音频上限防护 */
    private int readTimeout = 30000;
}
```

- [ ] **Step 3: application.yaml 增加 `voice.gateway` 段**

在 `--- #################### 调解 AI 平台配置 ####################` 文档块内（`mediation:` 段之前或同块末尾）追加：

```yaml
# 137 语音服务（ASR/TTS 演示直连；内网地址属敏感信息，值走配置中心/环境变量，不硬编码）
voice:
  gateway:
    base-url: ${VOICE_GATEWAY_BASE_URL:http://192.168.1.137:8765}
    realtime-ws-url: ${VOICE_REALTIME_WS_URL:ws://192.168.1.137:8765/v1/realtime}
    api-key: ${VOICE_GATEWAY_API_KEY:not-needed}
    asr-model: ${VOICE_ASR_MODEL:qwen3-asr}
    tts-model: ${VOICE_TTS_MODEL:qwen3-tts}
    default-voice: ${VOICE_TTS_VOICE:Aiden}
    connect-timeout: 5000
    read-timeout: 30000
```

- [ ] **Step 4: 编译验证**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server compile`
Expected: BUILD SUCCESS（新错误码/配置类通过编译）

- [ ] **Step 5: Commit**

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/util/ErrorCodeConstants.java \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/voicedemo/config/VoiceGatewayProperties.java \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/resources/application.yaml
git commit -m "feat(ai-voicedemo): 新增 137 语音演示错误码段与网关配置属性"
```

---

### Task V2: VoiceGatewayClient（Hutool HTTP 直连 137）+ 单测

**Files:**
- Create: `.../voicedemo/client/VoiceGatewayClient.java`
- Test: `.../src/test/java/com/tianque/module/ai/voicedemo/client/VoiceGatewayClientTest.java`

> 风格对齐 `core/client/PaddleOcrClient`（Hutool `HttpRequest`/`HttpResponse`，超时/错误码转换/日志统一在 client）。本 Task 测**纯解析函数** `parseAsrText(String)` 与 `buildTtsPayload(...)`（不触网）。

- [ ] **Step 1: 写失败测试（ASR 响应解析 + TTS 请求体拼装）**

`VoiceGatewayClientTest.java`：

```java
package com.tianque.module.ai.voicedemo.client;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class VoiceGatewayClientTest {

    @Test
    void parseAsrText_returnsTextField() {
        // 137 REST 实测仅返回 {"text","language"}
        assertEquals("hello world", VoiceGatewayClient.parseAsrText("{\"text\":\"hello world\",\"language\":\"English\"}"));
    }

    @Test
    void parseAsrText_blankBody_returnsEmpty() {
        assertEquals("", VoiceGatewayClient.parseAsrText(""));
        assertEquals("", VoiceGatewayClient.parseAsrText(null));
    }

    @Test
    void parseAsrText_invalidJson_throws() {
        assertThrows(IllegalArgumentException.class, () -> VoiceGatewayClient.parseAsrText("not-json"));
    }

    @Test
    void buildTtsPayload_mapsFields() {
        Map<String, Object> p = VoiceGatewayClient.buildTtsPayload("你好", "Vivian", 1.0, "wav", "qwen3-tts");
        assertEquals("你好", p.get("input"));
        assertEquals("Vivian", p.get("voice"));
        assertEquals("qwen3-tts", p.get("model"));
    }
}
```

- [ ] **Step 2: 运行确认失败**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=VoiceGatewayClientTest test`
Expected: 编译失败（`VoiceGatewayClient` 不存在）

- [ ] **Step 3: 实现 VoiceGatewayClient**

`voicedemo/client/VoiceGatewayClient.java`：

```java
package com.tianque.module.ai.voicedemo.client;

import cn.hutool.http.ContentType;
import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONUtil;
import com.tianque.module.ai.voicedemo.config.VoiceGatewayProperties;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * @author zhangxuhui
 * @description 137 语音网关薄封装（Hutool HTTP）：ASR multipart 转发、TTS JSON→音频字节、存活探测。
 *              超时/错误码转换/日志统一在此层（对齐 PaddleOcrClient 风格）。
 */
@Component
@Slf4j
public class VoiceGatewayClient {

    @Resource
    private VoiceGatewayProperties props;

    /** ASR：上传式 multipart 转写，返回 137 原始 JSON 文本串（仅 text/language） */
    public String transcribe(byte[] audioBytes, String filename, String language) {
        String url = props.getBaseUrl() + "/v1/audio/transcriptions";
        HttpRequest req = HttpRequest.post(url)
                .timeout(props.getReadTimeout())
                .setConnectionTimeout(props.getConnectTimeout())
                .form("file", audioBytes, filename)
                .form("model", props.getAsrModel());
        if (language != null && !language.isBlank() && !"auto".equalsIgnoreCase(language)) {
            req.form("language", language);
        }
        if (hasApiKey()) {
            req.header("Authorization", "Bearer " + props.getApiKey());
        }
        log.info("[transcribe] 调用 137 ASR, url={}, file={}, size={}", url, filename, audioBytes.length);
        try (HttpResponse resp = req.execute()) {
            if (!resp.isOk()) {
                throw new IllegalStateException("ASR HTTP " + resp.getStatus() + ": " + resp.body());
            }
            return resp.body();
        }
    }

    /** TTS：JSON→音频字节（137 恒输出 24kHz mono WAV） */
    public byte[] synthesize(String input, String voice, Double speed, String responseFormat) {
        String url = props.getBaseUrl() + "/v1/audio/speech";
        Map<String, Object> payload = buildTtsPayload(input,
                (voice == null || voice.isBlank()) ? props.getDefaultVoice() : voice,
                speed, responseFormat, props.getTtsModel());
        HttpRequest req = HttpRequest.post(url)
                .timeout(props.getReadTimeout())
                .setConnectionTimeout(props.getConnectTimeout())
                .body(JSONUtil.toJsonStr(payload), ContentType.JSON.getValue());
        if (hasApiKey()) {
            req.header("Authorization", "Bearer " + props.getApiKey());
        }
        log.info("[synthesize] 调用 137 TTS, url={}, voice={}, inputLen={}", url, payload.get("voice"), input.length());
        try (HttpResponse resp = req.execute()) {
            if (!resp.isOk()) {
                throw new IllegalStateException("TTS HTTP " + resp.getStatus() + ": " + resp.body());
            }
            return resp.bodyBytes();
        }
    }

    /** 存活探测：137 无 /health，用 /v1/pool */
    public boolean alive() {
        try {
            HttpResponse resp = HttpRequest.get(props.getBaseUrl() + "/v1/pool")
                    .timeout(props.getConnectTimeout()).execute();
            return resp.isOk();
        } catch (Exception e) {
            log.warn("[alive] 137 存活探测失败: {}", e.getMessage());
            return false;
        }
    }

    private boolean hasApiKey() {
        return props.getApiKey() != null && !props.getApiKey().isBlank()
                && !"not-needed".equalsIgnoreCase(props.getApiKey());
    }

    /** 纯函数：解析 137 ASR JSON，取 text 字段（无则空串）。供单测覆盖。 */
    public static String parseAsrText(String json) {
        if (json == null || json.isBlank()) {
            return "";
        }
        if (!JSONUtil.isTypeJSONObject(json)) {
            throw new IllegalArgumentException("非法 ASR 响应 JSON: " + json);
        }
        return JSONUtil.parseObj(json).getStr("text", "");
    }

    /** 纯函数：拼装 TTS 请求体。供单测覆盖。 */
    public static Map<String, Object> buildTtsPayload(String input, String voice, Double speed,
                                                       String responseFormat, String model) {
        Map<String, Object> p = new HashMap<>();
        p.put("input", input);
        p.put("model", model);
        if (voice != null && !voice.isBlank()) {
            p.put("voice", voice);
        }
        if (speed != null) {
            p.put("speed", speed);   // 137 实测未生效，入参占位透传
        }
        if (responseFormat != null && !responseFormat.isBlank()) {
            p.put("response_format", responseFormat); // 实测解析但恒输出 WAV
        }
        return p;
    }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=VoiceGatewayClientTest test`
Expected: BUILD SUCCESS（4 用例全绿）

- [ ] **Step 5: Commit**

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/voicedemo/client/VoiceGatewayClient.java \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/test/java/com/tianque/module/ai/voicedemo/client/VoiceGatewayClientTest.java
git commit -m "feat(ai-voicedemo): VoiceGatewayClient 直连 137（ASR multipart/TTS JSON/存活探测）+ 纯函数单测"
```

---

### Task V3: VoiceDemoService + Controller（ASR/TTS 接口，错误码降级）

**Files:**
- Create: `.../voicedemo/controller/admin/voicedemo/vo/{AsrTranscribeRespVO, TtsSynthReqVO}.java`
- Create: `.../voicedemo/service/voicedemo/{VoiceDemoService, impl/VoiceDemoServiceImpl}.java`
- Create: `.../voicedemo/controller/admin/voicedemo/VoiceDemoController.java`
- Test: `.../src/test/java/com/tianque/module/ai/voicedemo/service/VoiceDemoServiceImplTest.java`

> **先决步骤**：`Read` `controller/admin/disputehall/MediaAnalysisController.java` 确认 `@RequestMapping` 是否带字面 `/admin-api/ai` 前缀，本 controller 与之保持一致（本计划按全局约定用字面 `/admin-api/ai/voice-demo`）。

- [ ] **Step 1: 写失败测试（空音频→VOICE_ASR_AUDIO_EMPTY；空文本→VOICE_TTS_TEXT_EMPTY；不可达→VOICE_GATEWAY_UNAVAILABLE）**

`VoiceDemoServiceImplTest.java`：

```java
package com.tianque.module.ai.voicedemo.service;

import com.tianque.framework.common.exception.ServiceException;
import com.tianque.module.ai.voicedemo.client.VoiceGatewayClient;
import com.tianque.module.ai.controller.admin.voice.vo.TtsSynthReqVO;
import com.tianque.module.ai.service.voice.impl.VoiceDemoServiceImpl;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.web.multipart.MultipartFile;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.when;

@MockitoSettings(strictness = Strictness.LENIENT)
class VoiceDemoServiceImplTest {

    @Mock
    VoiceGatewayClient client;
    @Mock
    MultipartFile file;
    @InjectMocks
    VoiceDemoServiceImpl service;

    @Test
    void transcribe_emptyFile_throwsAudioEmpty() {
        when(file.isEmpty()).thenReturn(true);
        assertThrows(ServiceException.class, () -> service.transcribe(file, "auto"));
    }

    @Test
    void transcribe_clientUnavailable_throwsGatewayUnavailable() throws Exception {
        when(file.isEmpty()).thenReturn(false);
        when(file.getBytes()).thenReturn(new byte[]{1});
        when(file.getOriginalFilename()).thenReturn("a.wav");
        when(client.transcribe(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any()))
                .thenThrow(new IllegalStateException("connect refused"));
        assertThrows(ServiceException.class, () -> service.transcribe(file, "auto"));
    }

    @Test
    void synthesize_emptyText_throwsTextEmpty() {
        TtsSynthReqVO req = new TtsSynthReqVO();
        req.setInput("   ");
        assertThrows(ServiceException.class, () -> service.synthesize(req));
    }
}
```

- [ ] **Step 2: 运行确认失败**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=VoiceDemoServiceImplTest test`
Expected: 编译失败（Service/VO 不存在）

- [ ] **Step 3: VO 与 Service**

`vo/AsrTranscribeRespVO.java`：

```java
package com.tianque.module.ai.controller.admin.voice.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "管理后台 - 137 ASR 转写响应")
public class AsrTranscribeRespVO {
    @Schema(description = "转写文本")
    private String text;
    @Schema(description = "耗时(ms)")
    private Long costMs;
}
```

`vo/TtsSynthReqVO.java`：

```java
package com.tianque.module.ai.controller.admin.voice.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
@Schema(description = "管理后台 - 137 TTS 合成请求")
public class TtsSynthReqVO {
    @NotBlank(message = "文本不能为空")
    @Schema(description = "待合成文本")
    private String input;
    @Schema(description = "音色，默认 Aiden；合法：Vivian/Serena/Uncle_Fu/Dylan/Eric/Ryan/Aiden/Ono_Anna/Sohee 或自定义")
    private String voice;
    @Schema(description = "语速倍率（137 实测未生效，占位）")
    private Double speed;
    @Schema(description = "格式（137 恒输出 WAV，占位）")
    private String responseFormat;
}
```

`service/voicedemo/VoiceDemoService.java`：

```java
package com.tianque.module.ai.voicedemo.service;

import com.tianque.module.ai.controller.admin.voice.vo.AsrTranscribeRespVO;
import com.tianque.module.ai.controller.admin.voice.vo.TtsSynthReqVO;
import org.springframework.web.multipart.MultipartFile;

public interface VoiceDemoService {
    AsrTranscribeRespVO transcribe(MultipartFile file, String language);

    byte[] synthesize(TtsSynthReqVO req);

    boolean alive();
}
```

`service/voicedemo/impl/VoiceDemoServiceImpl.java`：

```java
package com.tianque.module.ai.service.voice.impl;

import com.tianque.module.ai.voicedemo.client.VoiceGatewayClient;
import com.tianque.module.ai.controller.admin.voice.vo.AsrTranscribeRespVO;
import com.tianque.module.ai.controller.admin.voice.vo.TtsSynthReqVO;
import com.tianque.module.ai.voicedemo.service.VoiceDemoService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.UncheckedIOException;

import static com.tianque.framework.common.exception.util.ServiceExceptionUtil.exception;
import static com.tianque.module.ai.util.ErrorCodeConstants.*;

@Service
@Validated
@Slf4j
public class VoiceDemoServiceImpl implements VoiceDemoService {

    @Resource
    private VoiceGatewayClient client;

    @Override
    public AsrTranscribeRespVO transcribe(org.springframework.web.multipart.MultipartFile file, String language) {
        if (file == null || file.isEmpty()) {
            throw exception(VOICE_ASR_AUDIO_EMPTY);
        }
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        long start = System.currentTimeMillis();
        String raw;
        try {
            raw = client.transcribe(bytes, file.getOriginalFilename(), language);
        } catch (IllegalStateException e) {
            // 连接失败/HTTP 非 2xx → 网关不可用或转写失败，统一按不可用降级
            log.error("[transcribe] 137 ASR 调用失败", e);
            throw exception(VOICE_GATEWAY_UNAVAILABLE, e.getMessage());
        }
        AsrTranscribeRespVO vo = new AsrTranscribeRespVO();
        vo.setText(VoiceGatewayClient.parseAsrText(raw));
        vo.setCostMs(System.currentTimeMillis() - start);
        return vo;
    }

    @Override
    public byte[] synthesize(TtsSynthReqVO req) {
        if (req.getInput() == null || req.getInput().isBlank()) {
            throw exception(VOICE_TTS_TEXT_EMPTY);
        }
        try {
            return client.synthesize(req.getInput(), req.getVoice(), req.getSpeed(), req.getResponseFormat());
        } catch (IllegalStateException e) {
            log.error("[synthesize] 137 TTS 调用失败", e);
            throw exception(VOICE_GATEWAY_UNAVAILABLE, e.getMessage());
        }
    }

    @Override
    public boolean alive() {
        return client.alive();
    }
}
```

> 补 `import org.springframework.validation.annotation.Validated;`。若 `ServiceExceptionUtil.exception(ErrorCode, Object...)` 签名不含变参重载，则降级项消息用 `exception(VOICE_GATEWAY_UNAVAILABLE)`（不带 `{}`）并在日志保留原因。

- [ ] **Step 4: Controller**

`controller/admin/voicedemo/VoiceDemoController.java`：

```java
package com.tianque.module.ai.voicedemo.controller.admin.voicedemo;

import com.tianque.framework.common.pojo.CommonResult;
import com.tianque.module.ai.controller.admin.voice.vo.AsrTranscribeRespVO;
import com.tianque.module.ai.controller.admin.voice.vo.TtsSynthReqVO;
import com.tianque.module.ai.voicedemo.service.VoiceDemoService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import static com.tianque.framework.common.pojo.CommonResult.success;

@Tag(name = "管理后台 - 语音能力演示（137 ASR/TTS）")
@RestController
@RequestMapping("/admin-api/ai/voice-demo")   // 对齐 MediaAnalysisController 字面量约定
@Validated
@Slf4j
public class VoiceDemoController {

    @Resource
    private VoiceDemoService voiceDemoService;

    @PostMapping("/asr/transcribe")
    @Operation(summary = "ASR 转写（multipart 上传）")
    @PreAuthorize("@ss.hasPermission('ai:voice-demo:asr')")
    public CommonResult<AsrTranscribeRespVO> transcribe(@RequestPart("file") MultipartFile file,
                                                        @RequestParam(value = "language", required = false) String language) {
        return success(voiceDemoService.transcribe(file, language));
    }

    @PostMapping("/tts/synthesize")
    @Operation(summary = "TTS 合成（返回音频字节，前端 blob 播放/下载）")
    @PreAuthorize("@ss.hasPermission('ai:voice-demo:tts')")
    public void synthesize(@RequestBody @Valid TtsSynthReqVO req, HttpServletResponse response) {
        byte[] audio = voiceDemoService.synthesize(req);
        response.setContentType("audio/wav");
        response.setHeader("Content-Disposition", "inline; filename=tts.wav");
        try {
            response.getOutputStream().write(audio);
            response.getOutputStream().flush();
        } catch (java.io.IOException e) {
            log.error("[synthesize] 写出音频失败", e);
        }
    }

    @GetMapping("/health")
    @Operation(summary = "137 语音服务存活探测")
    @PreAuthorize("@ss.hasPermission('ai:voice-demo:query')")
    public CommonResult<Boolean> health() {
        return success(voiceDemoService.alive());
    }
}
```

> TTS 直接写 `HttpServletResponse` 输出流返回二进制（spec §12.2「本期直返 blob，不落盘」）；异常路径由 `synthesize(req)` 内 `throw exception(...)` 抛出，经全局异常处理器转 `CommonResult` JSON，前端拦截 `content-type=json` 视为错误（见 V6）。

- [ ] **Step 5: 运行确认通过 + 编译**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=VoiceDemoServiceImplTest test`
Expected: BUILD SUCCESS（3 用例全绿）

- [ ] **Step 6: Commit**

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/voicedemo \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/test/java/com/tianque/module/ai/voicedemo
git commit -m "feat(ai-voicedemo): VoiceDemo 服务与 Controller（ASR/TTS/health，错误码降级）"
```

---

### Task V4: 语音演示菜单 + 授权 SQL（uaa_menu 9495–9498）

**Files:**
- Create: `mediation-ai/docs/sql/V3.47__voice_demo_menu.sql`

- [ ] **Step 1: 编写脚本（Step-0 防呆 + 单菜单双 Tab + 两按钮 + 超管/全角色授权，对齐 V3.40 范式）**

```sql
-- ============================================================
-- V3.47: 「语音能力演示」目录 + ASR/TTS 演示菜单 + 按钮权限 + 授权
-- 对应设计: mediation-docs/superpowers/specs/2026-11-03-meeting-ai-capability-design.md §13.2
-- 数据库: PostgreSQL（对齐 V3.39/V3.40 风格）；菜单 ID 段 9495–9498（9484–9489 留缓冲避让）
-- 决策 M16：单菜单双 Tab（页面权限 ai:voice-demo:query，按钮 ai:voice-demo:asr / :tts）
-- ============================================================
BEGIN;

-- Step 0: 防呆 —— 9495–9498 必须全空闲，否则中止回滚
DO $$
DECLARE cnt int;
BEGIN
  SELECT count(*) INTO cnt FROM uaa_menu WHERE id BETWEEN 9495 AND 9498;
  IF cnt > 0 THEN
    RAISE EXCEPTION '菜单 id 9495-9498 段已被占用 % 行，请整段顺延后再执行', cnt;
  END IF;
END $$;

-- Step 1: 目录（type=1）9495
INSERT INTO uaa_menu (id, name, permission, type, sort, parent_id, path, icon, component,
                      component_name, status, visible, keep_alive, always_show,
                      creator, create_time, updater, update_time, deleted)
VALUES (9495, '语音能力演示', '', 1, 90, 0, '/ai/voice-demo', 'SoundOutlined', '',
        NULL, 0, true, true, true, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sort = EXCLUDED.sort, updater = 'system', update_time = CURRENT_TIMESTAMP;

-- Step 2: 页面菜单（type=2）9496，父 9495，挂双 Tab 页组件
INSERT INTO uaa_menu (id, name, permission, type, sort, parent_id, path, icon, component,
                      component_name, status, visible, keep_alive, always_show,
                      creator, create_time, updater, update_time, deleted)
VALUES (9496, 'ASR/TTS 演示', 'ai:voice-demo:query', 2, 1, 9495, 'demo', 'AudioMutedOutlined', 'ai/voice-demo/VoiceDemo',
        'AiVoiceDemo', 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, permission = EXCLUDED.permission,
  path = EXCLUDED.path, component = EXCLUDED.component, updater = 'system', update_time = CURRENT_TIMESTAMP;

-- Step 3: 按钮（type=3）9497 ASR / 9498 TTS，父 9496
INSERT INTO uaa_menu (id, name, permission, type, sort, parent_id, path, icon, component,
                      component_name, status, visible, keep_alive, always_show,
                      creator, create_time, updater, update_time, deleted)
VALUES
 (9497, '语音转写(ASR)', 'ai:voice-demo:asr', 3, 1, 9496, '', '', '', NULL, 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false),
 (9498, '语音合成(TTS)', 'ai:voice-demo:tts', 3, 2, 9496, '', '', '', NULL, 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, permission = EXCLUDED.permission, updater = 'system', update_time = CURRENT_TIMESTAMP;

-- Step 4: 超管授权（role_id=1, tenant_id=1），id = 100000 + menu_id
INSERT INTO uaa_role_menu (id, tenant_id, role_id, menu_id, creator, create_time, updater, update_time, deleted)
SELECT 100000 + m.id, 1, 1, m.id, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false
FROM generate_series(9495, 9498) m(id)
WHERE NOT EXISTS (SELECT 1 FROM uaa_role_menu rm WHERE rm.role_id = 1 AND rm.menu_id = m.id);

COMMIT;

-- 回滚（按需）：
-- DELETE FROM uaa_role_menu WHERE menu_id BETWEEN 9495 AND 9498;
-- DELETE FROM uaa_menu WHERE id BETWEEN 9495 AND 9498;

-- 验证：预期 4 行菜单 + 4 行超管授权
SELECT id, parent_id, name, permission, type FROM uaa_menu WHERE id BETWEEN 9495 AND 9498 ORDER BY id;
SELECT COUNT(*) FROM uaa_role_menu WHERE menu_id BETWEEN 9495 AND 9498 AND role_id = 1;
```

> 若本地演示需全员可见，追加 V3.40 Step-4 同款「400000+ 段 `ROW_NUMBER` 全角色授权」；本计划按超管授权即可满足开发登录态验证。`component` 路径 `ai/voice-demo/VoiceDemo` 须与 V6 建的前端文件 `src/views/ai/voice-demo/VoiceDemo.vue` 对应（route-helper 用 `import.meta.glob('../views/**')` 解析）。

- [ ] **Step 2: 临时 PG 容器验证幂等（可选，若本地有 PG）**

Run: `docker exec -i <pg> psql -U postgres -d mediation_db -f V3.47__voice_demo_menu.sql`（执行两遍）
Expected: 两遍均成功、无重复键报错（防呆段对已存在 id 因 `count>0` 会中止——**第二遍预期触发 RAISE EXCEPTION 中止，证明防呆生效**；如需可重跑用 `ON CONFLICT DO UPDATE` 分支则先注释 Step 0）

- [ ] **Step 3: Commit**

```bash
git add mediation-ai/docs/sql/V3.47__voice_demo_menu.sql
git commit -m "feat(ai-voicedemo): 语音能力演示菜单与授权 SQL（uaa_menu 9495-9498）"
```

---

### Task V5: 前端依赖 + voiceDemo API 封装 + 单测

**Files:**
- Modify: `mediation-web/package.json`（+ `@ricky0123/vad-web`）
- Create: `mediation-web/src/api/ai/voiceDemo.ts`
- Test: `mediation-web/src/api/ai/__tests__/voiceDemo.spec.ts`

- [ ] **Step 1: 安装依赖**

Run（在 `mediation-web`）: `pnpm add @ricky0123/vad-web`
Expected: 写入 package.json dependencies，lock 更新

- [ ] **Step 2: 写失败测试（TTS 错误响应判定 + ASR 参数拼装纯函数）**

`voiceDemo.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import { buildAsrForm, isAudioBlob, VOICE_DEMO_BASE } from '../voiceDemo'

describe('voiceDemo api', () => {
  it('base 带 admin-api 前缀', () => {
    expect(VOICE_DEMO_BASE).toBe('/admin-api/ai/voice-demo')
  })
  it('buildAsrForm 组装 multipart', () => {
    const fd = buildAsrForm(new File(['x'], 'a.wav', { type: 'audio/wav' }), 'zh')
    expect(fd.get('file')).toBeInstanceOf(File)
    expect(fd.get('language')).toBe('zh')
  })
  it('buildAsrForm 省略空 language', () => {
    const fd = buildAsrForm(new File(['x'], 'a.wav'), '')
    expect(fd.get('language')).toBeNull()
  })
  it('isAudioBlob 依据 content-type 判定', () => {
    expect(isAudioBlob({ headers: { 'content-type': 'audio/wav' } })).toBe(true)
    expect(isAudioBlob({ headers: { 'content-type': 'application/json' } })).toBe(false)
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `pnpm vitest run src/api/ai/__tests__/voiceDemo.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 4: 实现 api**

`src/api/ai/voiceDemo.ts`：

```ts
import { get, post } from '@/utils/request'

export const VOICE_DEMO_BASE = '/admin-api/ai/voice-demo'

export interface AsrTranscribeResp {
  text: string
  costMs?: number
}

/** 纯函数：组装 ASR multipart（file + 可选 language） */
export function buildAsrForm(file: File, language?: string): FormData {
  const fd = new FormData()
  fd.append('file', file)
  if (language && language !== 'auto') fd.append('language', language)
  return fd
}

/** 纯函数：判定响应是否为音频二进制（否则视为 CommonResult JSON 错误） */
export function isAudioBlob(res: { headers?: Record<string, string> }): boolean {
  const ct = (res.headers?.['content-type'] || res.headers?.['Content-Type'] || '').toLowerCase()
  return ct.startsWith('audio/')
}

/** ASR 转写：multipart，后端返回 CommonResult<AsrTranscribeResp> */
export function asrTranscribe(file: File, language?: string) {
  return post<AsrTranscribeResp>(`${VOICE_DEMO_BASE}/asr/transcribe`, buildAsrForm(file, language), {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

/** TTS 合成：JSON 请求，返回原始 blob 响应（含 headers 供 isAudioBlob 判定） */
export function ttsSynthesize(payload: { input: string; voice?: string; speed?: number; responseFormat?: string }) {
  return post<Blob>(`${VOICE_DEMO_BASE}/tts/synthesize`, payload, {
    responseType: 'blob',
    timeout: 60000,
  })
}

export function voiceHealth() {
  return get<boolean>(`${VOICE_DEMO_BASE}/health`)
}
```

> 若 `@/utils/request` 的 `post` 默认拦截会把 blob 解成 `data`（见 request.ts 第 97-101 行对 blob/arraybuffer/stream 已跳过 JSON 解析），则 `ttsSynthesize` 返回 blob；错误时后端返回 `application/json`，`isAudioBlob` 返回 false，UI 层再 `await blob.text()` 解析 `msg`。实现时按 `request.ts` 实际返回类型微调（`post` 是否透传 headers——若不透传，改为直接用 `service` 实例或 `fetch`）。

- [ ] **Step 5: 运行确认通过**

Run: `pnpm vitest run src/api/ai/__tests__/voiceDemo.spec.ts`
Expected: PASS（4 用例）

- [ ] **Step 6: Commit**

```bash
git add mediation-web/package.json mediation-web/pnpm-lock.yaml mediation-web/src/api/ai/voiceDemo.ts mediation-web/src/api/ai/__tests__/voiceDemo.spec.ts
git commit -m "feat(web-voicedemo): voiceDemo API 封装与 vad-web 依赖"
```

---

### Task V6: 前端页面（VoiceDemo 双 Tab + AsrPanel/VadRecorder + TtsPanel）

**Files:**
- Create: `mediation-web/src/views/ai/voice-demo/VoiceDemo.vue`
- Create: `mediation-web/src/views/ai/voice-demo/components/AsrPanel.vue`
- Create: `mediation-web/src/views/ai/voice-demo/components/VadRecorder.vue`
- Create: `mediation-web/src/views/ai/voice-demo/components/TtsPanel.vue`
- Test: `mediation-web/src/views/ai/voice-demo/__tests__/segments.spec.ts`（VAD 段→展示行拼接纯函数）

- [ ] **Step 1: 写失败测试（分段拼接纯函数）**

先建一个可测的纯函数文件 `mediation-web/src/views/ai/voice-demo/segments.ts`：

```ts
export interface TranscriptSegment { start: number; end: number; text: string }

/** 纯函数：把逐段结果按客户端 start ms 升序整理，过滤空文本 */
export function normalizeSegments(segs: TranscriptSegment[]): TranscriptSegment[] {
  return segs.filter((s) => s.text && s.text.trim()).sort((a, b) => a.start - b.start)
}

/** 纯函数：合并全文（空格分隔） */
export function mergeText(segs: TranscriptSegment[]): string {
  return normalizeSegments(segs).map((s) => s.text.trim()).join(' ')
}
```

`__tests__/segments.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import { normalizeSegments, mergeText } from '../segments'

describe('vad segments', () => {
  const raw = [
    { start: 200, end: 900, text: 'B' },
    { start: 0, end: 150, text: 'A' },
    { start: 1000, end: 1200, text: '  ' },
  ]
  it('normalizeSegments 升序且去空', () => {
    const n = normalizeSegments(raw)
    expect(n.map((s) => s.text)).toEqual(['A', 'B'])
  })
  it('mergeText 空格拼接', () => {
    expect(mergeText(raw)).toBe('A B')
  })
})
```

Run: `pnpm vitest run src/views/ai/voice-demo/__tests__/segments.spec.ts`
Expected: FAIL（segments.ts 未建）→ 建 `segments.ts`（Step 1 代码）→ 再跑 PASS

- [ ] **Step 2: VoiceDemo.vue（双 Tab，按权限过滤 Tab 渲染）**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import AsrPanel from './components/AsrPanel.vue'
import TtsPanel from './components/TtsPanel.vue'
import { useAccessStore } from '@/stores/access'

const active = ref('asr')
const accessStore = useAccessStore()
// 依按钮权限分别控制 Tab（M16）；无独立权限函数时用 hasPermi 工具，见 directives/permission.ts
const canAsr = accessStore.hasPermission('ai:voice-demo:asr')
const canTts = accessStore.hasPermission('ai:voice-demo:tts')
</script>

<template>
  <div class="voice-demo">
    <a-page-header title="语音能力演示" sub-title="直连 137：ASR 转写 / TTS 合成（与视频会议完全解耦）" />
    <a-tabs v-model:activeKey="active" type="card">
      <a-tab-pane v-if="canAsr" key="asr" tab="语音转写 (ASR)">
        <AsrPanel />
      </a-tab-pane>
      <a-tab-pane v-if="canTts" key="tts" tab="语音合成 (TTS)">
        <TtsPanel />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>
```

> `useAccessStore().hasPermission` 若不存在，改用项目既有权限判定（`Read` `stores/access.ts` 与 `utils/permission.ts`，用 `hasPermission(['ai:voice-demo:asr'])` 之类的既有函数）。

- [ ] **Step 3: AsrPanel.vue（上传/录音双模式）**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { asrTranscribe, type AsrTranscribeResp } from '@/api/ai/voiceDemo'
import VadRecorder from './VadRecorder.vue'
import { mergeText, type TranscriptSegment } from '../segments'

const mode = ref<'upload' | 'record'>('upload')
const file = ref<File | null>(null)
const language = ref('auto')
const loading = ref(false)
const result = ref<AsrTranscribeResp | null>(null)
const segments = ref<TranscriptSegment[]>([])

function onFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0] || null
  file.value = f
}

async function runUpload() {
  if (!file.value) { message.warning('请选择音频文件'); return }
  loading.value = true
  try {
    result.value = await asrTranscribe(file.value, language.value)
  } catch (err: any) {
    message.error(err?.msg || err?.message || '转写失败（137 不可达？）')
  } finally { loading.value = false }
}

// 录音模式：VadRecorder 每切出一段即回调 onSegment（携带 blob + start/end ms），逐段送转
async function onSegment(seg: { blob: Blob; start: number; end: number }) {
  const f = new File([seg.blob], `vad_${seg.start}_${seg.end}.wav`, { type: 'audio/wav' })
  try {
    const r = await asrTranscribe(f, language.value)
    if (r?.text) segments.value.push({ start: seg.start, end: seg.end, text: r.text })
  } catch { /* 单段失败不阻断其余段 */ }
}
</script>

<template>
  <div class="asr-panel">
    <a-radio-group v-model:value="mode">
      <a-radio-button value="upload">上传音频</a-radio-button>
      <a-radio-button value="record">录音（VAD 分段）</a-radio-button>
    </a-radio-group>

    <div style="margin: 12px 0">
      语言：
      <a-select v-model:value="language" style="width: 120px">
        <a-select-option value="auto">Auto</a-select-option>
        <a-select-option value="zh">中文</a-select-option>
        <a-select-option value="en">English</a-select-option>
      </a-select>
    </div>

    <template v-if="mode === 'upload'">
      <input type="file" accept="audio/*" @change="onFileChange" />
      <a-button type="primary" :loading="loading" @click="runUpload" style="margin-left: 8px">转写</a-button>
    </template>
    <template v-else>
      <VadRecorder @segment="onSegment" />
      <div v-if="segments.length" style="margin-top: 12px">
        <h4>分段结果</h4>
        <a-table :dataSource="segments" :columns="[
          { title: '起(ms)', dataIndex: 'start' },
          { title: '止(ms)', dataIndex: 'end' },
          { title: '文本', dataIndex: 'text' }]" rowKey="start" size="small" :pagination="false" />
        <p>合并：<b>{{ mergeText(segments) }}</b></p>
      </div>
    </template>

    <div v-if="result && mode === 'upload'" style="margin-top: 12px">
      <a-alert type="success" :message="`转写（${result.costMs ?? '-'}ms）`" :description="result.text" />
    </div>
  </div>
</template>
```

- [ ] **Step 4: VadRecorder.vue（Silero VAD 切段，emit segment）**

```vue
<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { MicVAD } from '@ricky0123/vad-web'
import { message } from 'ant-design-vue'

const emit = defineEmits<{ (e: 'segment', seg: { blob: Blob; start: number; end: number }): void }>()
const running = ref(false)
let vad: MicVAD | null = null
let segStart = 0

async function start() {
  message.info('需要麦克风权限，首次加载模型体积较大')
  vad = await MicVAD.new({
    // minSilence 与 137 服务端 VAD(700ms) 对齐（§12.4，M18）
    positiveSpeechThreshold: 0.5,
    negativeSpeechThreshold: 0.35,
    minSpeechMs: 250,
    redemptionMs: 700,
    startOnLoad: true,
    onSpeechStart: () => { segStart = Date.now() },
    onSpeechEnd: (audio: Float32Array) => {
      const end = Date.now()
      emit('segment', { blob: float32ToWavBlob(audio, 16000), start: segStart, end })
    },
  })
  running.value = true
}
function stop() { vad?.stop(); running.value = false }

// Float32 PCM → 16-bit WAV Blob（137 transcriptions 用 soundfile 解码，接受 WAV）
function float32ToWavBlob(audio: Float32Array, sampleRate: number): Blob {
  const buf = new ArrayBuffer(44 + audio.length * 2)
  const dv = new DataView(buf)
  const ws = (o: number, s: string) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)) }
  ws(0, 'RIFF'); dv.setUint32(4, 36 + audio.length * 2, true); ws(8, 'WAVE'); ws(12, 'fmt ')
  dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true)
  dv.setUint32(24, sampleRate, true); dv.setUint32(28, sampleRate * 2, true)
  dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); ws(36, 'data'); dv.setUint32(40, audio.length * 2, true)
  let o = 44
  for (let i = 0; i < audio.length; i++, o += 2) {
    const s = Math.max(-1, Math.min(1, audio[i]))
    dv.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

onBeforeUnmount(() => vad?.destroy?.())
</script>

<template>
  <a-space>
    <a-button v-if="!running" type="primary" @click="start">开始录音</a-button>
    <a-button v-else danger @click="stop">停止</a-button>
    <span v-if="running">正在监听，说停后自动送转写…</span>
  </a-space>
</template>
```

> `@ricky0123/vad-web` 的 `MicVAD.new` 选项名以安装版本 README 为准（`redemptionMs`/`minSpeechMs` 在 2.x；若装到旧版字段名不同，实现时按 node_modules 内 `.d.ts` 校正）。模型资源默认走 CDN，离线场景需 `publicPath` 指向本地 `@ricky0123/vad-web/dist/*.onnx`。

- [ ] **Step 5: TtsPanel.vue（文本 + 9 音色按语种分组 + 播放/下载）**

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ttsSynthesize, isAudioBlob } from '@/api/ai/voiceDemo'

const form = reactive({ input: '', voice: 'Aiden', speed: 1.0, responseFormat: 'wav' })
const loading = ref(false)
const audioUrl = ref('')
// §9 Q10 定案：内置 9 音色按语种分组 + 自定义
const voices = [
  { group: '中文', items: ['Vivian', 'Serena', 'Uncle_Fu', 'Dylan', 'Eric'] },
  { group: '英语', items: ['Ryan', 'Aiden'] },
  { group: '日语', items: ['Ono_Anna'] },
  { group: '韩语', items: ['Sohee'] },
]

async function run() {
  if (!form.input.trim()) { message.warning('文本不能为空'); return }
  loading.value = true
  try {
    const res: any = await ttsSynthesize({ input: form.input, voice: form.voice, speed: form.speed, responseFormat: form.responseFormat })
    // res 为 blob；若后端报错返回 json，则解析 msg
    if (res instanceof Blob) {
      if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
      audioUrl.value = URL.createObjectURL(res)
    } else {
      message.error(res?.msg || '合成失败')
    }
  } catch (err: any) {
    message.error(err?.msg || err?.message || '合成失败（137 不可达/非法音色？）')
  } finally { loading.value = false }
}
</script>

<template>
  <div class="tts-panel">
    <a-textarea v-model:value="form.input" :rows="3" placeholder="输入待合成文本" />
    <a-space style="margin-top: 12px" wrap>
      <span>音色：
        <a-select v-model:value="form.voice" style="width: 160px">
          <a-optgroup v-for="g in voices" :key="g.group" :label="g.group">
            <a-select-option v-for="v in g.items" :key="v" :value="v">{{ v }}</a-select-option>
          </a-optgroup>
        </a-select>
      </span>
      <span>语速（137 实测未生效）：<a-input-number v-model:value="form.speed" :min="0.5" :max="2" :step="0.1" /></span>
      <span>格式（137 恒输出 WAV）：
        <a-select v-model:value="form.responseFormat" style="width: 100px">
          <a-select-option value="wav">wav</a-select-option>
          <a-select-option value="mp3">mp3</a-select-option>
          <a-select-option value="pcm">pcm</a-select-option>
        </a-select>
      </span>
      <a-button type="primary" :loading="loading" @click="run">合成并播放</a-button>
    </a-space>
    <div v-if="audioUrl" style="margin-top: 12px">
      <audio :src="audioUrl" controls />
      <a :href="audioUrl" download="tts.wav" style="margin-left: 12px">下载</a>
    </div>
  </div>
</template>
```

- [ ] **Step 6: 类型检查 + 测试 + Lint**

Run: `pnpm vitest run src/views/ai/voice-demo/__tests__/segments.spec.ts && pnpm type-check && pnpm lint`
Expected: 测试 PASS；type-check 无 error；lint 无 error（warning 可接受）

- [ ] **Step 7: Commit**

```bash
git add mediation-web/src/views/ai/voice-demo
git commit -m "feat(web-voicedemo): 语音演示页（双 Tab + ASR 上传/VAD 录音分段 + TTS 9 音色播放）"
```

---

### Task V7: 语音线端到端冒烟（spec §7 步骤 7–9）

**Files:** 无（验证）

- [ ] **Step 1: curl 直连 137（127 本机或开发机）**

Run: `curl -s -X POST http://192.168.1.137:8765/v1/audio/transcriptions -F "file=@sample.wav" -F "model=qwen3-asr"`
Expected: JSON 含非空 `"text"`
Run: `curl -s -X POST http://192.168.1.137:8765/v1/audio/speech -H "Content-Type: application/json" -d '{"input":"你好","voice":"Aiden","model":"qwen3-tts"}' -o out.wav`
Expected: `out.wav` 可播放（24kHz mono）；存活探测 `curl -s http://192.168.1.137:8765/v1/pool` 返 `size:1`

- [ ] **Step 2: 起 ai-server（local profile），经 Java 代理**

登录态拿 token 后：
Run: `curl -s -H "Authorization: Bearer $TOKEN" -H "tenant-id: 1" -X POST $HOST/admin-api/ai/voice-demo/asr/transcribe -F "file=@sample.wav"`
Expected: `CommonResult` data.text 非空
Run: `curl -s -H "Authorization: Bearer $TOKEN" -H "tenant-id: 1" -X POST $HOST/admin-api/ai/voice-demo/tts/synthesize -H "Content-Type: application/json" -d '{"input":"测试合成","voice":"Vivian"}' -o s.wav`
Expected: `s.wav` 可播放

- [ ] **Step 3: 页面验收（独立性）**

停掉 `mwb-livekit` 容器与 worker，打开「语音能力演示」：上传得文本、录音分段得带起止毫秒的行、合成得可播放音频。
Expected: 三者在无 LiveKit/worker 情况下全部可用（M12 独立性验收）。

- [ ] **Step 4: 记录结果并在 spec §7 勾选**

将实测耗时/文本回写 spec §7 步骤 7–9 备注（若与预期不符，登记为实施期缺口，不臆造）。

---

## Track M：视频会议 Demo（meeting，LiveKit + worker + 纪要回写）

> 对应 spec §3、§5、§4 B/C、§13。错误码 `1_040_061_xxx`，权限 `ai:meeting:{create,join,query,update}`，菜单 9490–9494。与 Track V 并行、互不引用。

### Task M1: 会议相关数据表 DDL（PG 方言，V3.45）

**Files:**
- Create: `mediation-ai/docs/sql/V3.45__meeting_tables.sql`

- [ ] **Step 1: 编写四表 DDL（BIGSERIAL/JSONB/COMMENT ON/独立索引，公共列齐全）**

```sql
-- ============================================================
-- V3.45: 视频会议 Demo 四表（对齐 spec §5.2；PG 方言，对齐既有迁移风格）
-- 会议/参与者/转录/纪要。租户隔离列 tenant_id（DO 继承 TenantBaseDO）。
-- ============================================================
BEGIN;

CREATE TABLE IF NOT EXISTS ai_meeting_room (
  id            BIGSERIAL    NOT NULL,
  room_sid      VARCHAR(128) NOT NULL,               -- LiveKit 房间名/ID
  case_id       BIGINT,                              -- 绑定案件（§9-2 单案件）
  title         VARCHAR(255) NOT NULL,
  host_user_id  BIGINT       NOT NULL,
  status        SMALLINT     NOT NULL DEFAULT 0,     -- 0进行中 1已结束
  start_time    TIMESTAMP,
  end_time      TIMESTAMP,
  creator       VARCHAR(64)  DEFAULT '',
  create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater       VARCHAR(64)  DEFAULT '',
  update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id     BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_meeting_room IS '视频会议房间';
COMMENT ON COLUMN ai_meeting_room.status IS '0进行中 1已结束';
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_meeting_room_room_sid ON ai_meeting_room (room_sid) WHERE deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_ai_meeting_room_case ON ai_meeting_room (case_id);

CREATE TABLE IF NOT EXISTS ai_meeting_participant (
  id            BIGSERIAL    NOT NULL,
  room_id       BIGINT       NOT NULL,
  identity      VARCHAR(128) NOT NULL,               -- LiveKit participant identity
  display_name  VARCHAR(128),
  role          SMALLINT     NOT NULL DEFAULT 1,     -- 0主持人 1参会人 2转录worker
  join_time     TIMESTAMP,
  leave_time    TIMESTAMP,
  creator       VARCHAR(64)  DEFAULT '',
  create_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater       VARCHAR(64)  DEFAULT '',
  update_time   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id     BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE ai_meeting_participant IS '会议参与者';
CREATE INDEX IF NOT EXISTS idx_ai_meeting_participant_room ON ai_meeting_participant (room_id);

CREATE TABLE IF NOT EXISTS ai_meeting_transcript (
  id                BIGSERIAL    NOT NULL,
  room_id           BIGINT       NOT NULL,
  speaker_identity  VARCHAR(128),                    -- 按 participant 分轨（§9-1）
  text              TEXT         NOT NULL,
  start_ts          BIGINT,                          -- 客户端/worker VAD 起始(ms)
  end_ts            BIGINT,
  seq               INT          NOT NULL DEFAULT 0, -- 房间内递增序号
  creator           VARCHAR(64)  DEFAULT '',
  create_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater           VARCHAR(64)  DEFAULT '',
  update_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id         BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE ai_meeting_transcript IS '会议实时转录分段';
CREATE INDEX IF NOT EXISTS idx_ai_meeting_transcript_room_seq ON ai_meeting_transcript (room_id, seq);

CREATE TABLE IF NOT EXISTS ai_meeting_minutes (
  id           BIGSERIAL    NOT NULL,
  room_id      BIGINT       NOT NULL,
  content      JSONB,                                -- 结构化纪要草稿
  elements     JSONB,                                -- 纠纷要素抽取结果
  status       VARCHAR(16)  NOT NULL DEFAULT 'DRAFT',-- DRAFT/CONFIRMED（M7）
  checkpoint_id BIGINT,                               -- 关联确认点（confirm 后）
  reviewer     BIGINT,                                -- 确认人
  confirm_time TIMESTAMP,
  creator      VARCHAR(64)  DEFAULT '',
  create_time  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater      VARCHAR(64)  DEFAULT '',
  update_time  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id    BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_meeting_minutes IS '会议纪要（草稿→确认）';
COMMENT ON COLUMN ai_meeting_minutes.status IS 'DRAFT 草稿(不写业务表) / CONFIRMED 已确认回写';
CREATE INDEX IF NOT EXISTS idx_ai_meeting_minutes_room ON ai_meeting_minutes (room_id);

COMMIT;
-- 回滚：DROP TABLE IF EXISTS ai_meeting_minutes, ai_meeting_transcript, ai_meeting_participant, ai_meeting_room;
```

- [ ] **Step 2: 临时 PG 容器验证幂等**

Run: `docker exec -i <pg> psql -U postgres -d mediation_db -f V3.45__meeting_tables.sql`（执行两遍）
Expected: 两遍均成功（`CREATE TABLE IF NOT EXISTS`/`CREATE INDEX IF NOT EXISTS` 保证幂等），四表存在

- [ ] **Step 3: Commit**

```bash
git add mediation-ai/docs/sql/V3.45__meeting_tables.sql
git commit -m "feat(ai-meeting): 视频会议四表 DDL（PG 方言）"
```

---

### Task M2: 会议枚举 + 错误码 + livekit/meeting 配置

**Files:**
- Create: `.../meeting/enums/{MeetingStatus, ParticipantRole, MinutesStatus}.java`
- Modify: `.../util/ErrorCodeConstants.java`
- Modify: `.../resources/application.yaml`

- [ ] **Step 1: 枚举**

`enums/MeetingStatus.java`：

```java
package com.tianque.module.ai.meeting.enums;

import lombok.AllArgsConstructor;
import lombok.Getter;

/** 会议状态：0进行中 1已结束 */
@Getter
@AllArgsConstructor
public enum MeetingStatus {
    ONGOING(0), ENDED(1);
    private final int code;
}
```

`enums/ParticipantRole.java`：

```java
package com.tianque.module.ai.meeting.enums;

import lombok.AllArgsConstructor;
import lombok.Getter;

/** 参与者角色：0主持人 1参会人 2转录worker */
@Getter
@AllArgsConstructor
public enum ParticipantRole {
    HOST(0), MEMBER(1), WORKER(2);
    private final int code;
}
```

`enums/MinutesStatus.java`：

```java
package com.tianque.module.ai.meeting.enums;

/** 纪要状态（M7）：DRAFT 不写业务表，CONFIRMED 才回写 */
public enum MinutesStatus {
    DRAFT, CONFIRMED;
}
```

- [ ] **Step 2: 追加会议错误码段（`ErrorCodeConstants` 语音段之后）**

```java
    // ========== 视频会议（meeting）1-040-061-000 ==========
    ErrorCode MEETING_ROOM_NOT_EXISTS = new ErrorCode(1_040_061_000, "会议房间不存在: {}");
    ErrorCode MEETING_TOKEN_SIGN_FAILED = new ErrorCode(1_040_061_001, "入会令牌签发失败");
    ErrorCode MEETING_INTERNAL_TOKEN_INVALID = new ErrorCode(1_040_061_002, "转录内部回推密钥无效");
    ErrorCode MEETING_MINUTES_DRAFT_NOT_EXISTS = new ErrorCode(1_040_061_003, "纪要草稿不存在或未生成");
    ErrorCode MEETING_MINUTES_CONFIRM_ILLEGAL = new ErrorCode(1_040_061_004, "纪要确认状态非法（非 AWAITING_CONFIRM）");
```

- [ ] **Step 3: application.yaml 增加 livekit/meeting 段（调解 AI 平台配置块内）**

```yaml
livekit:
  server-url: ${LIVEKIT_SERVER_URL:ws://localhost:7880}    # 浏览器侧信令/媒体
  api-url: ${LIVEKIT_API_URL:http://localhost:7880}        # Java 侧房间管理
  api-key: ${LIVEKIT_API_KEY:devkey}                       # 须与 livekit.yaml keys 一致；生产换≥32位
  api-secret: ${LIVEKIT_API_SECRET:secret}
  token-ttl: 3600
meeting:
  internal-transcript-token: ${MEETING_INTERNAL_TOKEN:change-me-internal-token}
  minutes-prompt-code: MEDIATION_MEETING_MINUTES
```

- [ ] **Step 4: 编译验证**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server compile`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting/enums \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/util/ErrorCodeConstants.java \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/resources/application.yaml
git commit -m "feat(ai-meeting): 会议枚举、错误码段与 livekit/meeting 配置"
```

---

### Task M3: MeetingTokenService（HS256 自签 LiveKit access token）+ 单测

**Files:**
- Create: `.../meeting/service/meeting/{MeetingTokenService, impl/MeetingTokenServiceImpl}.java`
- Test: `.../src/test/java/com/tianque/module/ai/meeting/service/MeetingTokenServiceTest.java`

> LiveKit access token = JWT(HS256)，claims：`iss`(api-key)、`sub`(identity)、`exp`、`nbf`、`jti`、`video`:{`room`,`participantIdentity`,`canPublish`,`canSubscribe`,`canAdminCompute`}。用 Hutool `cn.hutool.jwt.JWT` + `HMACSHA256`。**测纯函数：签发的 token 能被同密钥验签且 grants 正确。**

- [ ] **Step 1: 写失败测试**

```java
package com.tianque.module.ai.meeting.service;

import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import com.tianque.module.ai.service.meeting.impl.MeetingTokenServiceImpl;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class MeetingTokenServiceTest {

    private final MeetingTokenServiceImpl svc = new MeetingTokenServiceImpl("devkey", "secret", "");

    @Test
    void signToken_verifiableAndCarriesGrants() {
        String token = svc.signToken("room-1", "alice", "Alice");
        assertNotNull(token);
        // 同密钥验签
        JWT jwt = JWTUtil.parseToken(token);
        assertTrue(jwt.setKey("secret".getBytes()).validate());
        assertEquals("devkey", jwt.getPayload("iss"));
        assertEquals("alice", jwt.getPayload("sub"));
        Map<?, ?> video = (Map<?, ?>) jwt.getPayload("video");
        assertEquals("room-1", video.get("room"));
        assertEquals(Boolean.TRUE, video.get("canPublish"));
        assertEquals(Boolean.TRUE, video.get("canSubscribe"));
    }
}
```

- [ ] **Step 2: 运行确认失败**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=MeetingTokenServiceTest test`
Expected: 编译失败（svc 不存在）

- [ ] **Step 3: 实现（用 @Value 注入密钥；测试用直接构造）**

`service/meeting/MeetingTokenService.java`：

```java
package com.tianque.module.ai.meeting.service;

public interface MeetingTokenService {
    /** 签发 LiveKit access token（HS256 自签 M4） */
    String signToken(String roomSid, String identity, String displayName);
}
```

`service/meeting/impl/MeetingTokenServiceImpl.java`：

```java
package com.tianque.module.ai.service.meeting.impl;

import cn.hutool.jwt.JWT;
import com.tianque.module.ai.meeting.service.MeetingTokenService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import static com.tianque.framework.common.exception.util.ServiceExceptionUtil.exception;
import static com.tianque.module.ai.util.ErrorCodeConstants.MEETING_TOKEN_SIGN_FAILED;

@Service
public class MeetingTokenServiceImpl implements MeetingTokenService {

    private final String apiKey;
    private final String apiSecret;
    private final String serverUrl;
    private final int tokenTtl;

    // 生产构造：@Value 注入；测试用三参构造直接 new
    public MeetingTokenServiceImpl(@Value("${livekit.api-key}") String apiKey,
                                   @Value("${livekit.api-secret}") String apiSecret,
                                   @Value("${livekit.server-url:}") String serverUrl,
                                   @Value("${livekit.token-ttl:3600}") int tokenTtl) {
        this.apiKey = apiKey;
        this.apiSecret = apiSecret;
        this.serverUrl = serverUrl;
        this.tokenTtl = tokenTtl;
    }

    /** 测试友好构造（默认 ttl 3600） */
    public MeetingTokenServiceImpl(String apiKey, String apiSecret, String serverUrl) {
        this(apiKey, apiSecret, serverUrl, 3600);
    }

    @Override
    public String signToken(String roomSid, String identity, String displayName) {
        try {
            long now = System.currentTimeMillis();
            Map<String, Object> video = new HashMap<>();
            video.put("room", roomSid);
            video.put("participantIdentity", identity);
            video.put("canPublish", true);
            video.put("canSubscribe", true);
            video.put("canAdminCompute", false);
            if (displayName != null && !displayName.isBlank()) {
                video.put("participantName", displayName);
            }
            return JWT.create()
                    .setPayload("iss", apiKey)
                    .setPayload("sub", identity)
                    .setPayload("jti", UUID.randomUUID().toString())
                    .setPayload("nbf", new Date(now - 5000))
                    .setPayload("exp", new Date(now + tokenTtl * 1000L))
                    .setPayload("video", video)
                    .setKey(apiSecret.getBytes())
                    .setAlgorithm("HmacSHA256")
                    .sign();
        } catch (Exception e) {
            throw exception(MEETING_TOKEN_SIGN_FAILED);
        }
    }
}
```

> Hutool `JWT` 的 HS256 算法名以安装版为准（`setAlgorithm("HmacSHA256")`；若无该方法则 `JWTUtil.create(...)` 默认即 HS256）。LiveKit token 的 `video` grants 字段名以 LiveKit 官方 access-token 规范为准（`room`/`participantIdentity`/`canPublish`/`canSubscribe`），实现时对照 `livekit-client` 校验。

- [ ] **Step 4: 运行确认通过**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=MeetingTokenServiceTest test`
Expected: PASS（验签 + grants 断言）

- [ ] **Step 5: Commit**

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting/service/meeting \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/test/java/com/tianque/module/ai/meeting/service/MeetingTokenServiceTest.java
git commit -m "feat(ai-meeting): MeetingTokenService HS256 自签 LiveKit token + 验签单测"
```

---

### Task M4: DAL（DO + Mapper）

**Files:**
- Create: `.../meeting/dal/dataobject/meeting/{MeetingRoomDO, MeetingParticipantDO, MeetingTranscriptDO, MeetingMinutesDO}.java`
- Create: `.../meeting/dal/mysql/meeting/{MeetingRoomMapper, MeetingParticipantMapper, MeetingTranscriptMapper, MeetingMinutesMapper}.java`

- [ ] **Step 1: DO（继承 TenantBaseDO，@TableName/@TableId，JSONB 用 JacksonTypeHandler）**

以 `MeetingRoomDO` 为例（其余同构，字段对齐 V3.45 列）：

```java
package com.tianque.module.ai.meeting.dal.dataobject.meeting;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.tianque.framework.tenant.core.db.TenantBaseDO;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDateTime;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("ai_meeting_room")
public class MeetingRoomDO extends TenantBaseDO {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String roomSid;
    private Long caseId;
    private String title;
    private Long hostUserId;
    private Integer status;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
}
```

`MeetingMinutesDO` 的 JSONB 字段：

```java
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> content;
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> elements;
```

import：`com.baomidou.mybatisplus.annotation.TableField;` `com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;`（对齐 `AgentOperationLogDO`）。`@TableName(value = "ai_meeting_minutes", autoResultMap = true)`。participant/transcript DO 字段照 V3.45。

- [ ] **Step 2: Mapper（BaseMapperX）**

```java
package com.tianque.module.ai.meeting.dal.mysql.meeting;

import com.tianque.framework.mybatis.core.mapper.BaseMapperX;
import com.tianque.module.ai.meeting.dal.dataobject.meeting.MeetingRoomDO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface MeetingRoomMapper extends BaseMapperX<MeetingRoomDO> {
}
```

> `BaseMapperX` 全限定名以既有 mapper 为准（`Read` `SuperagentCheckpointMapper` 确认 import）。`MeetingTranscriptMapper` 加 `selectMaxSeq(Long roomId)`（默认方法或 XML）供 worker 回推续号；`MeetingMinutesMapper` 加 `selectByRoomId(Long roomId)`。

- [ ] **Step 3: 编译**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server compile`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting/dal
git commit -m "feat(ai-meeting): 会议四表 DO 与 Mapper"
```

---

### Task M5: MeetingRoomService + MeetingController（create/token/get/page/end）

**Files:**
- Create: VOs `.../meeting/controller/admin/meeting/vo/{MeetingRoomCreateReqVO, MeetingTokenReqVO, MeetingTokenRespVO, MeetingRoomRespVO}.java`
- Create: `.../meeting/service/meeting/{MeetingRoomService, impl/MeetingRoomServiceImpl}.java`
- Create: `.../meeting/controller/admin/meeting/MeetingController.java`

- [ ] **Step 1: VO**

```java
// MeetingRoomCreateReqVO
@Data
public class MeetingRoomCreateReqVO {
    @NotNull(message = "案件ID不能为空") private Long caseId;
    @NotBlank(message = "标题不能为空") private String title;
}
// MeetingTokenReqVO
@Data
public class MeetingTokenReqVO {
    @NotNull private Long roomId;
    @NotBlank private String identity;
    private String displayName;
}
// MeetingTokenRespVO
@Data
public class MeetingTokenRespVO {
    private String token; private String serverUrl; private String roomSid; private String identity;
}
// MeetingRoomRespVO
@Data
public class MeetingRoomRespVO {
    private Long id; private String roomSid; private Long caseId; private String title;
    private Integer status; private LocalDateTime startTime; private LocalDateTime endTime;
}
```

- [ ] **Step 2: Service（建房落库 + 签发 token + 结束置态并异步触发纪要）**

`MeetingRoomService` 接口：`Long createRoom(MeetingRoomCreateReqVO)`、`MeetingTokenRespVO issueToken(MeetingTokenReqVO)`、`MeetingRoomDO getRoom(Long)`、`void endRoom(Long roomId)`、`List<MeetingRoomDO> getRoomPage(...)`（分页可复用框架 `PageParam`）。

`MeetingRoomServiceImpl` 关键实现（`createRoom`/`issueToken`/`endRoom`）：

```java
@Service
@Validated
@Slf4j
public class MeetingRoomServiceImpl implements MeetingRoomService {

    @Resource private MeetingRoomMapper roomMapper;
    @Resource private MeetingTokenService tokenService;
    @Resource private MeetingMinutesService minutesService; // M7 依赖（Task M6 提供）

    @Value("${livekit.server-url}") private String serverUrl;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long createRoom(MeetingRoomCreateReqVO req) {
        MeetingRoomDO room = new MeetingRoomDO();
        room.setCaseId(req.getCaseId());
        room.setTitle(req.getTitle());
        room.setHostUserId(SecurityFrameworkUtils.getLoginUserId());
        room.setStatus(MeetingStatus.ONGOING.getCode());
        room.setStartTime(java.time.LocalDateTime.now());
        // room_sid 用可控唯一串（Demo：case + 时间戳；生产可换 UUID/雪花）
        room.setRoomSid("meet-" + req.getCaseId() + "-" + System.currentTimeMillis());
        roomMapper.insert(room);
        return room.getId();
    }

    @Override
    public MeetingTokenRespVO issueToken(MeetingTokenReqVO req) {
        MeetingRoomDO room = roomMapper.selectById(req.getRoomId());
        if (room == null) {
            throw exception(MEETING_ROOM_NOT_EXISTS, req.getRoomId());
        }
        MeetingTokenRespVO vo = new MeetingTokenRespVO();
        vo.setIdentity(req.getIdentity());
        vo.setRoomSid(room.getRoomSid());
        vo.setServerUrl(serverUrl);
        vo.setToken(tokenService.signToken(room.getRoomSid(), req.getIdentity(), req.getDisplayName()));
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void endRoom(Long roomId) {
        MeetingRoomDO room = roomMapper.selectById(roomId);
        if (room == null) {
            throw exception(MEETING_ROOM_NOT_EXISTS, roomId);
        }
        room.setStatus(MeetingStatus.ENDED.getCode());
        room.setEndTime(java.time.LocalDateTime.now());
        roomMapper.updateById(room);
        // 异步触发纪要草稿（仅产 DRAFT，绝不写业务表 —— M7）
        minutesService.generateDraftAsync(roomId);
    }
    // getRoom/getRoomPage 略（标准 selectById / selectPage）
}
```

import：`SecurityFrameworkUtils`（`com.tianque.framework.security.core.util`）、`exception`（`ServiceExceptionUtil`）、错误码静态导入、`MeetingStatus`。

- [ ] **Step 3: Controller**

```java
@Tag(name = "管理后台 - 视频会议")
@RestController
@RequestMapping("/admin-api/ai/meeting")   // 对齐 MediaAnalysisController 字面量约定
@Validated
@Slf4j
public class MeetingController {

    @Resource private MeetingRoomService roomService;

    @PostMapping("/room/create")
    @Operation(summary = "创建会议（绑定案件）")
    @PreAuthorize("@ss.hasPermission('ai:meeting:create')")
    public CommonResult<Long> createRoom(@RequestBody @Valid MeetingRoomCreateReqVO req) {
        return success(roomService.createRoom(req));
    }

    @PostMapping("/token")
    @Operation(summary = "签发入会 token")
    @PreAuthorize("@ss.hasPermission('ai:meeting:join')")
    public CommonResult<MeetingTokenRespVO> token(@RequestBody @Valid MeetingTokenReqVO req) {
        return success(roomService.issueToken(req));
    }

    @GetMapping("/room/get")
    @Operation(summary = "会议详情")
    @Parameter(name = "id", description = "会议ID", required = true)
    @PreAuthorize("@ss.hasPermission('ai:meeting:query')")
    public CommonResult<MeetingRoomRespVO> get(@RequestParam("id") Long id) {
        return success(MeetingConvert.toResp(roomService.getRoom(id)));
    }

    @PostMapping("/room/end")
    @Operation(summary = "结束会议并触发纪要草稿")
    @Parameter(name = "id", description = "会议ID", required = true)
    @PreAuthorize("@ss.hasPermission('ai:meeting:update')")
    public CommonResult<Boolean> end(@RequestParam("id") Long id) {
        roomService.endRoom(id);
        return success(true);
    }
}
```

> `MeetingConvert` 用 MapStruct 或手写静态 `toResp(DO)`（本期可手写一个 `BeanUtil.copyProperties` 静态方法，避免过度设计）。`/room/page` 端点同 `get` 风格返回分页。

- [ ] **Step 4: 编译 + 提交**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server compile` → BUILD SUCCESS

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting/controller/admin/meeting \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting/service/meeting/MeetingRoomService.java \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting/service/meeting/impl/MeetingRoomServiceImpl.java
git commit -m "feat(ai-meeting): 房间服务与 MeetingController（建房/token/结束）"
```

---

### Task M6: 转录回推内部端点 + MeetingTranscriptService（落库 + SSE）+ 单测

**Files:**
- Create: VO `.../meeting/controller/admin/meeting/vo/TranscriptSegmentVO.java`
- Create: `.../meeting/controller/internal/MeetingTranscriptInternalController.java`
- Create: `.../meeting/service/meeting/{MeetingTranscriptService, impl/MeetingTranscriptServiceImpl}.java`
- Test: `.../src/test/java/com/tianque/module/ai/meeting/service/MeetingTranscriptInternalTest.java`

> worker→Java 走带共享密钥的内部 REST（M6）：`POST /admin-api/ai/meeting/internal/transcript`，头 `X-Internal-Token` 校验 `meeting.internal-transcript-token`，`@PermitAll`（不出公网）。落 `ai_meeting_transcript` 后经 SSE 下推（`SseEmitterPool`，按 roomId 分组）。字幕流端点 `GET /transcript/stream` 复用 `SseEmitter`。

- [ ] **Step 1: 写失败测试（密钥非法→MEETING_INTERNAL_TOKEN_INVALID）**

```java
package com.tianque.module.ai.meeting.service;

import com.tianque.framework.common.exception.ServiceException;
import com.tianque.module.ai.service.meeting.impl.MeetingTranscriptServiceImpl;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import com.tianque.module.ai.meeting.dal.mysql.meeting.MeetingTranscriptMapper;

import static org.junit.jupiter.api.Assertions.*;

@MockitoSettings(strictness = Strictness.LENIENT)
class MeetingTranscriptInternalTest {

    @Mock
    MeetingTranscriptMapper transcriptMapper;
    @InjectMocks
    MeetingTranscriptServiceImpl service;

    @Test
    void ingest_wrongSecret_throws() {
        assertThrows(ServiceException.class,
                () -> service.ingest("room-1", "wrong-secret", java.util.List.of()));
    }
}
```

- [ ] **Step 2: 运行确认失败**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=MeetingTranscriptInternalTest test`
Expected: 编译失败

- [ ] **Step 3: VO + Service（含密钥校验、seq 续号、SSE 广播）**

`TranscriptSegmentVO`：`{ String speakerIdentity; String text; Long startTs; Long endTs; }`

`MeetingTranscriptServiceImpl`（`@Value("${meeting.internal-transcript-token}")` 注入期望密钥；构造注入 mapper，测试可 `@InjectMocks`）：

```java
@Service
@Slf4j
public class MeetingTranscriptServiceImpl implements MeetingTranscriptService {

    @Resource private MeetingTranscriptMapper transcriptMapper;
    @Resource private MeetingRoomMapper roomMapper;
    @Value("${meeting.internal-transcript-token}") private String internalToken;

    /** 房间 SSE 连接：roomId -> emitter（复用 SseEmitterPool.getEmitter） */
    @Override
    public void ingest(String roomSid, String secret, java.util.List<TranscriptSegmentVO> segments) {
        if (secret == null || !secret.equals(internalToken)) {
            throw exception(MEETING_INTERNAL_TOKEN_INVALID);
        }
        MeetingRoomDO room = roomMapper.selectOne(MeetingRoomDO::getRoomSid, roomSid);
        if (room == null) {
            throw exception(MEETING_ROOM_NOT_EXISTS, roomSid);
        }
        int seq = nextSeq(room.getId());
        for (TranscriptSegmentVO seg : segments) {
            MeetingTranscriptDO row = new MeetingTranscriptDO();
            row.setRoomId(room.getId());
            row.setSpeakerIdentity(seg.getSpeakerIdentity());
            row.setText(seg.getText());
            row.setStartTs(seg.getStartTs());
            row.setEndTs(seg.getEndTs());
            row.setSeq(seq++);
            transcriptMapper.insert(row);
            pushToRoom(room.getId(), row);   // SSE 下推
        }
    }

    private int nextSeq(Long roomId) {
        Integer max = transcriptMapper.selectMaxSeq(roomId);
        return max == null ? 0 : max + 1;
    }

    private void pushToRoom(Long roomId, MeetingTranscriptDO row) {
        try {
            SseEmitter emitter = SseEmitterPool.getEmitter("meeting-" + roomId);
            emitter.send(SseEmitter.event().name("transcript").data(row));
        } catch (Exception e) {
            log.warn("[pushToRoom] SSE 推送失败 roomId={}: {}", roomId, e.getMessage());
        }
    }

    @Override
    public SseEmitter subscribe(Long roomId) {
        return SseEmitterPool.getEmitter("meeting-" + roomId);
    }

    @Override
    public java.util.List<MeetingTranscriptDO> listByRoom(Long roomId) {
        return transcriptMapper.selectList(MeetingTranscriptDO::getRoomId, roomId);
    }
}
```

- [ ] **Step 4: 内部 Controller + 字幕流端点**

```java
// MeetingTranscriptInternalController（controller/internal）
@RestController
@RequestMapping("/admin-api/ai/meeting/internal")
@PermitAll   // 类级免登录（M6，不出公网）；密钥在 service 校验
public class MeetingTranscriptInternalController {
    @Resource private MeetingTranscriptService transcriptService;

    @PostMapping("/transcript")
    @Operation(summary = "worker 回推转录分段")
    public CommonResult<Boolean> ingest(@RequestParam("roomSid") String roomSid,
                                        @RequestHeader("X-Internal-Token") String secret,
                                        @RequestBody java.util.List<TranscriptSegmentVO> segments) {
        transcriptService.ingest(roomSid, secret, segments);
        return success(true);
    }
}

// MeetingController 追加字幕流端点（Task M5 类内）
@GetMapping(value = "/transcript/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
@Operation(summary = "会中实时字幕 SSE")
@PreAuthorize("@ss.hasPermission('ai:meeting:query')")
public SseEmitter transcriptStream(@RequestParam("roomId") Long roomId, HttpServletResponse response) {
    response.setHeader("X-Accel-Buffering", "no");
    return transcriptService.subscribe(roomId);
}
```

> `@PermitAll`（`jakarta.annotation.security.PermitAll`）由框架 `TianqueWebSecurityConfigurerAdapter.getPermitAllUrlsFromAnnotations()` 收集放行。若 `internal` 包不在 `controller.admin` 下、路径前缀装配与 M2 约定不同，实现时对照确认（internal 端点同样经 `/admin-api/ai/**` 网关转发）。

- [ ] **Step 5: 运行确认通过 + 提交**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=MeetingTranscriptInternalTest test` → PASS

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/test/java/com/tianque/module/ai/meeting/service/MeetingTranscriptInternalTest.java
git commit -m "feat(ai-meeting): worker 转录回推内部端点 + SSE 字幕下推（共享密钥校验）"
```

---

### Task M7: MeetingMinutesService（LLM 草稿 + 确认回写）+ 单测（DRAFT 不变式）

**Files:**
- Create: VOs `.../meeting/controller/admin/meeting/vo/{MinutesDraftRespVO, MinutesConfirmReqVO}.java`
- Create: `.../meeting/service/meeting/{MeetingMinutesService, impl/MeetingMinutesServiceImpl}.java`, `.../meeting/controller/admin/meeting/MeetingMinutesController.java`
- Test: `.../src/test/java/com/tianque/module/ai/meeting/service/MeetingMinutesDraftInvariantTest.java`

> 数据流（§3.4）：① `generateDraftAsync(roomId)` 读转录全文→`AiLLMCallService.callModelForStructuredJson(text, promptCode=MEDIATION_MEETING_MINUTES, vars, schema)`→存 `ai_meeting_minutes(status=DRAFT)`，**不动业务表**；② `getDraft(roomId)` 返回草稿；③ `confirm(roomId, edited)` → `SuperagentCheckpointManager.pause` 生 `AWAITING_CONFIRM` → `accept` → `CaseContextApi.addMediationRecord` + `AgentOperationLog` 留痕。

- [ ] **Step 1: 写失败测试（草稿生成后 status=DRAFT，且未 confirm 前绝不触业务写）**

```java
package com.tianque.module.ai.meeting.service;

import com.tianque.module.ai.meeting.dal.dataobject.meeting.MeetingMinutesDO;
import com.tianque.module.ai.meeting.dal.mysql.meeting.MeetingMinutesMapper;
import com.tianque.module.ai.meeting.dal.mysql.meeting.MeetingTranscriptMapper;
import com.tianque.module.ai.meeting.enums.MinutesStatus;
import com.tianque.module.ai.service.meeting.impl.MeetingMinutesServiceImpl;
import com.tianque.module.ai.service.chat.AiLLMCallService;
import com.tianque.module.ai.service.chat.dto.ChatModelResponse;
import com.tianque.module.medcase.api.CaseContextApi;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@MockitoSettings(strictness = Strictness.LENIENT)
class MeetingMinutesDraftInvariantTest {

    @Mock
    MeetingMinutesMapper minutesMapper;
    @Mock
    MeetingTranscriptMapper transcriptMapper;
    @Mock
    AiLLMCallService llmCallService;
    @Mock
    CaseContextApi caseContextApi;
    @InjectMocks
    MeetingMinutesServiceImpl service;

    @Test
    void generateDraft_persistsDraftAndNeverWritesCase() {
        when(transcriptMapper.selectList(any())).thenReturn(List.of());
        ChatModelResponse resp = ChatModelResponse.builder()
                .finalResponse("{\"summary\":\"双方就赔偿达成一致\"}").code(200).build();
        when(llmCallService.callModelForStructuredJson(any(), any(), any(), any())).thenReturn(resp);

        service.generateDraft(1L);

        ArgumentCaptor<MeetingMinutesDO> cap = ArgumentCaptor.forClass(MeetingMinutesDO.class);
        verify(minutesMapper).insert(cap.capture());
        assertEquals(MinutesStatus.DRAFT.name(), cap.getValue().getStatus());
        // M7 硬边界：未确认前绝不回写案件
        verify(caseContextApi, never()).addMediationRecord(any());
    }

    @Test
    void getDraft_missing_throws() {
        when(minutesMapper.selectByRoomId(99L)).thenReturn(null);
        assertThrows(RuntimeException.class, () -> service.getDraft(99L));
    }
}
```

- [ ] **Step 2: 运行确认失败**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=MeetingMinutesDraftInvariantTest test`
Expected: 编译失败

- [ ] **Step 3: VO**

```java
// MinutesDraftRespVO
@Data
public class MinutesDraftRespVO {
    private Long roomId; private String status;
    private Map<String, Object> content; private Map<String, Object> elements;
}
// MinutesConfirmReqVO
@Data
public class MinutesConfirmReqVO {
    @NotNull private Long roomId;
    private Map<String, Object> editedContent; // 主持人可编辑后回传
}
```

- [ ] **Step 4: Service**

`MeetingMinutesService` 接口：`void generateDraftAsync(Long)`、`void generateDraft(Long)`、`MinutesDraftRespVO getDraft(Long)`、`void confirm(MinutesConfirmReqVO)`。

`MeetingMinutesServiceImpl`（构造/字段注入供 `@InjectMocks`；`CaseContextApi` 为 Feign，`SuperagentCheckpointManager`/`AgentOperationLog` 写入器在 confirm 中使用）：

```java
@Service
@Validated
@Slf4j
public class MeetingMinutesServiceImpl implements MeetingMinutesService {

    @Resource private MeetingMinutesMapper minutesMapper;
    @Resource private MeetingTranscriptMapper transcriptMapper;
    @Resource private MeetingRoomMapper roomMapper;
    @Resource private AiLLMCallService aiLLMCallService;
    @Resource private CaseContextApi caseContextApi;
    @Resource private SuperagentCheckpointManager checkpointManager;
    @Resource private AgentOperationLogMapper operationLogMapper;
    @Value("${meeting.minutes-prompt-code:MEDIATION_MEETING_MINUTES}") private String promptCode;

    @Async
    @Override
    public void generateDraftAsync(Long roomId) { generateDraft(roomId); }

    @Override
    public void generateDraft(Long roomId) {
        String transcript = renderTranscript(roomId);
        ChatModelResponse r = aiLLMCallService.callModelForStructuredJson(
                transcript, promptCode, Map.of(), null);
        Map<String, Object> content = parseJson(r.getFinalResponse());
        MeetingMinutesDO minutes = new MeetingMinutesDO();
        minutes.setRoomId(roomId);
        minutes.setContent(content);
        minutes.setStatus(MinutesStatus.DRAFT.name());  // 关键：仅 DRAFT，不触业务字段
        minutesMapper.insert(minutes);
    }

    @Override
    public MinutesDraftRespVO getDraft(Long roomId) {
        MeetingMinutesDO m = minutesMapper.selectByRoomId(roomId);
        if (m == null) throw exception(MEETING_MINUTES_DRAFT_NOT_EXISTS);
        MinutesDraftRespVO vo = new MinutesDraftRespVO();
        vo.setRoomId(roomId); vo.setStatus(m.getStatus());
        vo.setContent(m.getContent()); vo.setElements(m.getElements());
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void confirm(MinutesConfirmReqVO req) {
        MeetingRoomDO room = roomMapper.selectById(req.getRoomId());
        MeetingMinutesDO m = minutesMapper.selectByRoomId(req.getRoomId());
        if (room == null || m == null) throw exception(MEETING_MINUTES_DRAFT_NOT_EXISTS);
        Long userId = SecurityFrameworkUtils.getLoginUserId();
        Map<String, Object> finalContent = req.getEditedContent() != null ? req.getEditedContent() : m.getContent();
        // 1) 经确认点状态机（AWAITING_CONFIRM → DONE）
        Long cpId = checkpointManager.pause("meeting-" + req.getRoomId(), "meeting",
                "writeback_meeting_minutes", finalContent, 3);
        var cp = checkpointManager.accept(cpId, userId);
        if (cp.getStatus() != SuperagentCheckpointStatus.DONE.getCode()) {
            throw exception(MEETING_MINUTES_CONFIRM_ILLEGAL);
        }
        // 2) 回写调解记录
        String recordContent = String.valueOf(finalContent.getOrDefault("summary", ""));
        caseContextApi.addMediationRecord(new AddMediationRecordRequest(
                room.getCaseId(), recordContent, null, userId, null));
        // 3) 审计留痕
        AgentOperationLogDO logRow = new AgentOperationLogDO();
        logRow.setChatId("meeting-" + req.getRoomId());
        logRow.setSessionId("meeting");
        logRow.setToolName("writeback_meeting_minutes");
        logRow.setArgs(finalContent);
        logRow.setRiskLevel(3);
        logRow.setSuccess(true);
        operationLogMapper.insert(logRow);
        // 4) 置纪要 CONFIRMED
        m.setStatus(MinutesStatus.CONFIRMED.name());
        m.setCheckpointId(cpId);
        m.setReviewer(userId);
        m.setConfirmTime(java.time.LocalDateTime.now());
        minutesMapper.updateById(m);
    }

    private String renderTranscript(Long roomId) {
        List<MeetingTranscriptDO> segs = transcriptMapper.selectList(MeetingTranscriptDO::getRoomId, roomId);
        StringBuilder sb = new StringBuilder();
        for (MeetingTranscriptDO s : segs) {
            sb.append(s.getSpeakerIdentity() == null ? "" : s.getSpeakerIdentity())
              .append(": ").append(s.getText()).append("\n");
        }
        return sb.toString();
    }

    private Map<String, Object> parseJson(String raw) {
        if (raw == null || raw.isBlank()) return Map.of();
        return JSONUtil.parseObj(raw).toBean(Map.class);
    }
}
```

> `SuperagentCheckpointStatus`/`AgentOperationLogMapper`/`AddMediationRecordRequest` 均已存在（§2 复用）。`AgentOperationLogMapper` 名以实际为准（`Read` superagent.chat.dal.mysql）。`@Async` 需 ai-server 已启用 `@EnableAsync`（若无，改用 `FeedStreamService` 同款的同步生成或 `CompletableFuture.runAsync`）。

- [ ] **Step 5: MeetingMinutesController**

```java
@Tag(name = "管理后台 - 会议纪要")
@RestController
@RequestMapping("/admin-api/ai/meeting/minutes")
@Validated
@Slf4j
public class MeetingMinutesController {
    @Resource private MeetingMinutesService minutesService;

    @GetMapping("/draft")
    @Operation(summary = "获取纪要草稿")
    @PreAuthorize("@ss.hasPermission('ai:meeting:query')")
    public CommonResult<MinutesDraftRespVO> draft(@RequestParam("roomId") Long roomId) {
        return success(minutesService.getDraft(roomId));
    }

    @PostMapping("/confirm")
    @Operation(summary = "确认并回写案件调解记录")
    @PreAuthorize("@ss.hasPermission('ai:meeting:update')")
    public CommonResult<Boolean> confirm(@RequestBody @Valid MinutesConfirmReqVO req) {
        minutesService.confirm(req);
        return success(true);
    }
}
```

- [ ] **Step 6: 运行确认通过 + 提交**

Run: `mvn -q -pl mediation-ai/mediation-ai-module/mediation-module-ai-server -Dtest=MeetingMinutesDraftInvariantTest test` → PASS（2 用例）

```bash
git add mediation-ai/mediation-ai-module/mediation-module-ai-server/src/main/java/com/tianque/module/ai/meeting \
        mediation-ai/mediation-ai-module/mediation-module-ai-server/src/test/java/com/tianque/module/ai/meeting/service/MeetingMinutesDraftInvariantTest.java
git commit -m "feat(ai-meeting): 纪要草稿/确认回写服务（DRAFT 不写库不变式）+ 单测"
```

---

### Task M8: 纪要提示词模板种子 SQL（MEDIATION_MEETING_MINUTES，V3.48）

**Files:**
- Create: `mediation-ai/docs/sql/V3.48__meeting_minutes_prompt.sql`

- [ ] **Step 1: 编写 seed（对齐 ROUND_STRATEGY 范式：model_id 子查询 + WHERE NOT EXISTS）**

```sql
-- V3.48: 会议纪要生成提示词模板 MEDIATION_MEETING_MINUTES
-- 模型必须与模板同租户（tenant_id=1）且取对话模型（type=1）
INSERT INTO ai_prompt_template (code, title, prompt_template, model_id, status, public_status, sort, tenant_id, creator, updater, create_time, update_time)
SELECT 'MEDIATION_MEETING_MINUTES', '调解-会议纪要生成',
'你是调解会议纪要助手。根据以下逐说话人的会议转录，输出结构化纪要 JSON（字段：summary 概要、points 要点数组、agreements 已达成事项数组、followups 待办数组）。仅基于转录事实，不虚构。\n\n转录：\n{user_query}',
(SELECT id FROM ai_model WHERE deleted = false AND status = 0 AND tenant_id = 1 AND type = 1 ORDER BY id LIMIT 1),
0, true, 0, 1, 'seed', 'seed', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_prompt_template WHERE code = 'MEDIATION_MEETING_MINUTES');

INSERT INTO ai_prompt_template_key (tenant_id, key_name, extractor, template_id, remark, status, model_id, public_status, label, sort, creator, updater, deleted)
SELECT 1, 'user_query', 'user_query', (SELECT id FROM ai_prompt_template WHERE code = 'MEDIATION_MEETING_MINUTES'),
       '会议转录全文', 0, NULL, true, '会议转录全文', 1, 'seed', 'seed', false
WHERE NOT EXISTS (SELECT 1 FROM ai_prompt_template_key k JOIN ai_prompt_template t ON t.id = k.template_id
  WHERE t.code = 'MEDIATION_MEETING_MINUTES' AND k.key_name = 'user_query');
-- 回滚：DELETE FROM ai_prompt_template WHERE code='MEDIATION_MEETING_MINUTES';
```

- [ ] **Step 2: 临时 PG 验证幂等（两遍）**

Run: 执行两遍 `V3.48__meeting_minutes_prompt.sql`
Expected: 模板与 key 各 1 行，第二遍 `WHERE NOT EXISTS` 不重复插入

- [ ] **Step 3: Commit**

```bash
git add mediation-ai/docs/sql/V3.48__meeting_minutes_prompt.sql
git commit -m "feat(ai-meeting): 会议纪要提示词模板种子 MEDIATION_MEETING_MINUTES"
```

---

### Task M9: 会议菜单 + 授权 SQL（uaa_menu 9490–9494，V3.46）

**Files:**
- Create: `mediation-ai/docs/sql/V3.46__meeting_menu.sql`

- [ ] **Step 1: 编写脚本（Step-0 防呆 + 一级目录/页面/三按钮 + 超管授权，同 V3.47 结构）**

```sql
-- V3.46: 视频会议菜单与权限（uaa_menu 9490-9494，§13.2；PG）
BEGIN;
DO $$ DECLARE cnt int;
BEGIN
  SELECT count(*) INTO cnt FROM uaa_menu WHERE id BETWEEN 9490 AND 9494;
  IF cnt > 0 THEN RAISE EXCEPTION '菜单 id 9490-9494 段已被占用 % 行，请整段顺延', cnt; END IF;
END $$;

INSERT INTO uaa_menu (id, name, permission, type, sort, parent_id, path, icon, component, component_name, status, visible, keep_alive, always_show, creator, create_time, updater, update_time, deleted)
VALUES
 (9490, '视频会议', '', 1, 89, 0, '/ai/meeting', 'VideoCameraOutlined', '', NULL, 0, true, true, true, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false),
 (9491, '会议演示', 'ai:meeting:query', 2, 1, 9490, 'room', 'VideoCameraOutlined', 'ai/meeting/MeetingList', 'AiMeetingList', 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false),
 (9492, '创建会议', 'ai:meeting:create', 3, 1, 9491, '', '', '', NULL, 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false),
 (9493, '加入会议', 'ai:meeting:join', 3, 2, 9491, '', '', '', NULL, 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false),
 (9494, '结束/纪要确认', 'ai:meeting:update', 3, 3, 9491, '', '', '', NULL, 0, true, true, false, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, permission = EXCLUDED.permission, parent_id = EXCLUDED.parent_id, component = EXCLUDED.component, updater = 'system', update_time = CURRENT_TIMESTAMP;

INSERT INTO uaa_role_menu (id, tenant_id, role_id, menu_id, creator, create_time, updater, update_time, deleted)
SELECT 100000 + m.id, 1, 1, m.id, 'system', CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, false
FROM generate_series(9490, 9494) m(id)
WHERE NOT EXISTS (SELECT 1 FROM uaa_role_menu rm WHERE rm.role_id = 1 AND rm.menu_id = m.id);
COMMIT;
-- 回滚：DELETE FROM uaa_role_menu WHERE menu_id BETWEEN 9490 AND 9494; DELETE FROM uaa_menu WHERE id BETWEEN 9490 AND 9494;
```

> `component` `ai/meeting/MeetingList` 对应前端 `src/views/ai/meeting/MeetingList.vue`（route-helper `import.meta.glob` 解析）。MeetingRoom 页由 MeetingList 内部跳转（静态路由或带 `hidden` meta），本菜单仅注册列表入口。

- [ ] **Step 2: 临时 PG 验证幂等（防呆段）**

Run: 执行第一遍 → 4 菜单+1 目录，5 行授权；第二遍 RAISE EXCEPTION 中止
Expected: 防呆生效

- [ ] **Step 3: Commit**

```bash
git add mediation-ai/docs/sql/V3.46__meeting_menu.sql
git commit -m "feat(ai-meeting): 视频会议菜单与授权 SQL（uaa_menu 9490-9494）"
```

---

### Task M10: Python livekit-agents 转录 worker

**Files:**
- Create: `deploy/livekit-worker/{worker.py, asr_provider.py, requirements.txt, Dockerfile, README.md}`

> M2/M5：worker 以参会者进房，逐轨 `silero-vad` 切段→`AsrProvider`（默认 137 `qwen3-asr`，M3/M19）→`POST {java}/admin-api/ai/meeting/internal/transcript` + `X-Internal-Token`。单实例串行（M20），本期 2–4 轨。

- [ ] **Step 1: requirements.txt**

```
livekit-agents~=0.12
livekit-plugins-silero~=0.7
requests
# 外网备选：dashscope（仅当 ASR_PROVIDER=dashscope 时按需装）
```

- [ ] **Step 2: asr_provider.py（可插拔）**

```python
import os, io, wave, requests

class AsrProvider:
    def transcribe(self, pcm16_bytes: bytes, sample_rate: int, language: str = "auto") -> str:
        raise NotImplementedError

def _to_wav(pcm16_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sample_rate)
        w.writeframes(pcm16_bytes)
    return buf.getvalue()

class QwenAsrProvider(AsrProvider):
    """137 内网 qwen3-asr：POST /v1/audio/transcriptions（仅返 {text,language}）"""
    def __init__(self):
        self.base = os.environ["VOICE_GATEWAY_BASE_URL"].rstrip("/")
        self.model = os.environ.get("VOICE_ASR_MODEL", "qwen3-asr")
    def transcribe(self, pcm16_bytes, sample_rate, language="auto"):
        wav = _to_wav(pcm16_bytes, sample_rate)
        data = {"model": self.model}
        if language and language != "auto":
            data["language"] = language
        r = requests.post(f"{self.base}/v1/audio/transcriptions",
                          files={"file": ("seg.wav", wav, "audio/wav")}, data=data, timeout=30)
        r.raise_for_status()
        return r.json().get("text", "")

def get_provider() -> AsrProvider:
    # 默认 137（M19）；外网备选 dashscope 未实现时回退报错，不臆造
    return QwenAsrProvider()
```

- [ ] **Step 3: worker.py（进房订阅各音轨→VAD 切段→回推 Java）**

```python
import os, time, requests
from livekit.agents import Agent, AgentSession, WorkerOptions, cli, JobContext
from livekit.agents.vad import SilenceActivationDetector
import livekit.plugins

JAVA_BASE = os.environ["JAVA_CALLBACK_BASE"].rstrip("/")
INTERNAL_TOKEN = os.environ["MEETING_INTERNAL_TOKEN"]
from asr_provider import get_provider
provider = get_provider()

class Transcriber(Agent):
    def __init__(self):
        super().__init__(instructions="你是转录器，不做对话。")

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    room_sid = ctx.room.name
    session = AgentSession(vad=livekit.plugins.silero.VAD.load(),
                           stt=None)  # 不走内置 STT，自控分段→137
    await session.start(room=ctx.room, agent=Transcriber())

    def push(segs):
        requests.post(f"{JAVA_BASE}/admin-api/ai/meeting/internal/transcript",
                      params={"roomSid": room_sid},
                      headers={"X-Internal-Token": INTERNAL_TOKEN},
                      json=segs, timeout=10)

    # 逐轨音频由 worker 回调推送分段（具体订阅 API 以 livekit-agents 版本为准）：
    # 伪代码：对每个 track 的 vad 语音段 → provider.transcribe(pcm, sr) → push
    # 实现时按 worker.py 真实事件接上（speech_started/stopped 记录 start/end ms）
    print(f"[worker] connected room={room_sid}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

> ⚠ **worker 为集成件、非 TDD 单测**（依赖真实 LiveKit 房间）。上方 `entrypoint` 内的逐轨 VAD→ASR→push 需实现期按安装的 `livekit-agents` 版本真实 API 补齐（本计划标注为骨架，不臆造具体事件回调）；`push` 回推体与 M6 `TranscriptSegmentVO`（`speakerIdentity/text/startTs/endTs`）字段对齐。验收靠 M12 端到端冒烟。

- [ ] **Step 4: Dockerfile + README**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "worker.py", "start"]
```

README 记录：环境变量（`LIVEKIT_URL`/`LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`/`VOICE_GATEWAY_BASE_URL`/`VOICE_ASR_MODEL`/`JAVA_CALLBACK_BASE`/`MEETING_INTERNAL_TOKEN`）、与 livekit-server/redis 同一网络组网（§8）、启动命令。

- [ ] **Step 5: Commit**

```bash
git add deploy/livekit-worker
git commit -m "feat(ai-meeting): Python livekit-agents 转录 worker（137 AsrProvider）"
```

---

### Task M11: 前端会议 api + 页面（livekit-client）

**Files:**
- Modify: `mediation-web/package.json`（+ `livekit-client`）
- Create: `mediation-web/src/api/ai/meeting.ts`
- Create: `views/ai/meeting/{MeetingList.vue, MeetingRoom.vue}` + `components/{VideoGrid, LocalTile, RemoteTile, ControlBar, ParticipantList, CaptionPanel, MeetingStatus, MinutesDrawer}.vue`

- [ ] **Step 1: 安装依赖**

Run（在 `mediation-web`）: `pnpm add livekit-client`

- [ ] **Step 2: api/ai/meeting.ts**

```ts
import { get, post } from '@/utils/request'
const BASE = '/admin-api/ai/meeting'

export interface MeetingTokenResp { token: string; serverUrl: string; roomSid: string; identity: string }
export interface MeetingRoom { id: number; roomSid: string; caseId?: number; title: string; status: number }
export interface MinutesDraft { roomId: number; status: string; content: Record<string, any>; elements?: Record<string, any> }

export const createRoom = (caseId: number, title: string) =>
  post<number>(`${BASE}/room/create`, { caseId, title })
export const issueToken = (roomId: number, identity: string, displayName: string) =>
  post<MeetingTokenResp>(`${BASE}/token`, { roomId, identity, displayName })
export const getRoom = (id: number) => get<MeetingRoom>(`${BASE}/room/get`, { params: { id } })
export const endRoom = (id: number) => post<boolean>(`${BASE}/room/end`, undefined, { params: { id } })
export const getMinutesDraft = (roomId: number) =>
  get<MinutesDraft>(`${BASE}/minutes/draft`, { params: { roomId } })
export const confirmMinutes = (roomId: number, editedContent?: Record<string, any>) =>
  post<boolean>(`${BASE}/minutes/confirm`, { roomId, editedContent })

/** 字幕流 SSE 地址（GET，由组件用裸 fetch + 鉴权头订阅，同 superagentFeed）*/
export const TRANSCRIPT_STREAM_URL = `${BASE}/transcript/stream`
```

- [ ] **Step 3: MeetingList.vue（列表 + 快速建房入会）**

`<script setup lang="ts">`：加载 `getRoom` 分页（或直接建房）→ 输入 caseId+标题点「建房」`createRoom` → 拿 roomId → 跳 `MeetingRoom`（query: roomId, identity=当前用户）。参照 `views/ai/capability/CapabilityDemo.vue` 风格（`a-page-header` + `a-card`）。

- [ ] **Step 4: MeetingRoom.vue（livekit-client 核心）**

```vue
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Room, RoomEvent, Track } from 'livekit-client'
import { issueToken, endRoom } from '@/api/ai/meeting'
import VideoGrid from './components/VideoGrid.vue'
import ControlBar from './components/ControlBar.vue'
import ParticipantList from './components/ParticipantList.vue'
import CaptionPanel from './components/CaptionPanel.vue'
import MeetingStatus from './components/MeetingStatus.vue'
import MinutesDrawer from './components/MinutesDrawer.vue'

const route = useRoute()
const room = new Room()
const connState = ref('connecting')
const speakers = ref<any[]>([])
const captions = ref<any[]>([])
const drawerOpen = ref(false)

onMounted(async () => {
  const roomId = Number(route.query.roomId)
  const identity = String(route.query.identity || 'web-' + Math.random().toString(36).slice(2, 8))
  const tk = await issueToken(roomId, identity, identity)
  room.on(RoomEvent.ConnectedStateChange, (s) => { connState.value = s })
  room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
    if (track.kind === Track.Kind.Video || track.kind === Track.Kind.Audio) {
      speakers.value.push({ identity: participant.identity, track, sid: track.sid })
    }
  })
  await room.connect(tk.serverUrl, tk.token)
  await room.localParticipant.setMicrophoneEnabled(true)
  await room.localParticipant.setCameraEnabled(true)
})

async function leave() { await room.disconnect() }
async function genMinutes() { await endRoom(Number(route.query.roomId)); drawerOpen.value = true }

onBeforeUnmount(() => room.disconnect())
defineExpose({ captions, room })
</script>

<template>
  <div class="meeting-room">
    <MeetingStatus :state="connState" />
    <VideoGrid :speakers="speakers" />
    <ControlBar :room="room" @leave="leave" @end="genMinutes" />
    <ParticipantList :room="room" />
    <CaptionPanel :captions="captions" :room-id="Number(route.query.roomId)" />
    <MinutesDrawer v-model:open="drawerOpen" :room-id="Number(route.query.roomId)" />
  </div>
</template>
```

- [ ] **Step 5: CaptionPanel.vue（SSE 字幕，复用 superagentFeed fetch 范式）**

参照 `stores/superagentFeed.ts` 的 `buildAuthHeaders()` + fetch ReadableStream 解析 `event: transcript`，将 `data`（含 speakerIdentity/text/startTs/endTs）append 到 captions。卸载时 `abort()`。

- [ ] **Step 6: ControlBar / VideoGrid / Local·RemoteTile / ParticipantList / MeetingStatus / MinutesDrawer**

- VideoGrid：自适应网格，`RemoteTile` 将 `track.mediaStreamTrack` attach 到 `<video>`；`LocalTile` 同理。
- ControlBar：静音/取消 `localParticipant.setMicrophoneEnabled(bool)`、开关摄像头、离开、结束生成纪要。
- MinutesDrawer：`onMounted`/打开时 `getMinutesDraft(roomId)` 展示草稿（段落↔转录时间戳锚点可回溯）→ 可编辑 → 「确认」`confirmMinutes(roomId, edited)` → 成功提示。

- [ ] **Step 7: 类型检查 + Lint**

Run: `pnpm type-check && pnpm lint`
Expected: 无 error

- [ ] **Step 8: Commit**

```bash
git add mediation-web/package.json mediation-web/pnpm-lock.yaml mediation-web/src/api/ai/meeting.ts mediation-web/src/views/ai/meeting
git commit -m "feat(web-meeting): 会议 api + 房间页（livekit-client + SSE 字幕 + 纪要抽屉）"
```

---

### Task M12: 会议线端到端冒烟（spec §7 步骤 1–6）

**Files:** 无（验证）

- [ ] **Step 1: 前置容器健康**

Run: `docker ps`；`redis-cli -h 127.0.0.1 -p 6379 -a password123 keys 'livekit*'`
Expected: `mwb-livekit`(7880/7881/7882)、`redis` 健康；Redis 出现 `livekit_version`/`nodes`

- [ ] **Step 2: 起 worker 容器**

Run: `cd deploy/livekit-worker && docker build -t meet-worker . && docker run --rm --network host -e LIVEKIT_URL=ws://localhost:7880 -e LIVEKIT_API_KEY=devkey -e LIVEKIT_API_SECRET=secret -e VOICE_GATEWAY_BASE_URL=http://192.168.1.137:8765 -e JAVA_CALLBACK_BASE=http://localhost:8086 -e MEETING_INTERNAL_TOKEN=change-me-internal-token meet-worker`
Expected: 日志 `[worker] connected room=...`；回推 `/internal/transcript` 返回 200

- [ ] **Step 3: 后端签 token**

登录态 `POST /admin-api/ai/meeting/room/create` → 得 roomId；`POST /admin-api/ai/meeting/token` → JWT（校验 `video.room`/`sub`）

- [ ] **Step 4: 双浏览器入会**

两个浏览器/无痕窗口打开房间页：互见画面、`CaptionPanel` 字幕随发言滚动（双真人发言 3s 内）

- [ ] **Step 5: 结束→纪要→确认→回写**

点「离开/结束」→ `MinutesDrawer` 轮询得 DRAFT 草稿 → 「确认」→ 目标 `caseId` 新增一条调解记录 + `ai_agent_operation_log` 留痕（toolName=writeback_meeting_minutes, riskLevel=3）

- [ ] **Step 6: 验证 M7 硬边界**

确认前查 `case_mediation_record` 行数零变化；确认后 +1。任一不符→登记缺陷不提交。

---

## Self-Review（计划自审）

**1. Spec 覆盖**：会议线 §3（token/房间/worker/SSE/纪要回写）→ M1–M12；语音线 §12（G/H）、§12.4 VAD → V1–V7；错误码 §5.1、配置 §5.3、表 §5.2、菜单 §13.2 → M1/M2/V4/M9。迭代 1+/实时对照(P1)未入本计划（符合范围）。**待确认覆盖度**：§9 仍开放项 Q16（补丁常驻）属部署约束，不入 P0 代码。若发现遗漏，补 Task 后回写本节。

**2. 占位符扫描**：worker.py 逐轨 VAD→ASR→push 事件回调已显式标为「实现期按 livekit-agents 真实 API 补齐」的骨架（不臆造跨版本 API），属**已知集成风险**而非 placeholder；其余 Java/SQL/前端均给出可落地代码。MeetingConvert 标注「可手写 BeanUtil」。

**3. 类型一致性**：错误码常量名（`MEETING_*`/`VOICE_*`）在 M2/V1 定义、M3–M7/V3 引用一致；`TranscriptSegmentVO`（M6）与 worker `push` 体（M10）字段一致；`MinutesStatus`（M2）与 V3.45 `status` 列一致；api `BASE`（`/admin-api/ai/meeting`·`/admin-api/ai/voice-demo`）与 controller `@RequestMapping`、菜单 `component` 路径与 views 文件路径一致；checkpoint 状态机 `AWAITING_CONFIRM(2)→DONE(3)` 与 superagent 既有枚举一致。

**4. 两约定冲突提示**：`@RequestMapping` 前缀存在字面量（DisputeHall/capability）与自动前缀（superagent）两套——计划统一按**字面量** `/admin-api/ai/...`，并在 M5/V3 首步强制 `Read MediaAnalysisController` 校准。若实为自动前缀，全局去除 `/admin-api` 字面段（前后端同步）。

---

## Execution Handoff

Plan complete and saved to `mediation-docs/superpowers/plans/2026-11-04-meeting-voice-demo-p0.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks, fast iteration.
2. **Inline Execution** — batch execute tasks in this session with checkpoints for review.
