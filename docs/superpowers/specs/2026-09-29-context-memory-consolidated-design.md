# 上下文记忆与长期记忆 — 统一架构设计（最新版）

> **版本**：v3.0（合并定稿）
> **日期**：2026-09-29
> **状态**：Consolidated（现行权威文档）
> **作者**：AI Assistant Architecture Team
> **定位**：本文**取代**下列 4 份旧文档，作为会话上下文记忆 / 长期记忆的唯一权威说明：
> - `2026-09-22-multi-mode-session-context-architecture-design.md`（三层架构原文）
> - `2026-09-22-mediation-context-transformation-design.md`（调解场景改造）
> - `2026-09-24-cross-mode-context-completion-design.md`（跨模式补全）
> - `2026-09-24-mode-context-memory-matrix.md`（9 模式矩阵，**矩阵数值已过时，见 §6**）
>
> 旧文档保留作历史决策留痕，但**一切以本文 + 当前代码为准**。

---

## 1. 范围与术语

### 1.1 两套互不相干的「记忆」

工程里存在两套都叫「记忆」的东西，**必须先区分**，否则极易误改：

| | **A. 应用内会话记忆**（本文主体） | **B. AI Agent 自身长期记忆** |
|---|---|---|
| 服务对象 | 终端用户（会话/模式切换时"继承上文"） | CodeBuddy Agent（跨会话记住项目事实） |
| 存储 | 本工程 Postgres（`ai_context_storage` 等） | 外部自托管 mem0 服务 |
| 代码 | `app/services/context_manager.py` 等 | 无代码，仅 MCP 调用 |
| 配置 | `app/config.py` | `~/.codebuddy/mcp.json` + `.codebuddy/mem0.config.json` |
| 详见 | 全文 | §11 |

### 1.2 分层术语（应用内）

| 层 | 名称 | 载体 | 作用域 |
|---|---|---|---|
| **L1** | 共享层 | `AiChatSession.context_data`（JSON） | 会话级全局配置 |
| **L1′** | 消息流 | `ai_chat_messages` 表 | 会话内原始问答（模式无关） |
| **L2** | 隔离层 | `ai_context_storage` 表 | 模式级短期记忆（`source_mode` 分区） |
| **L3** | 同步层 | `Mem0Service` → mem0 | 用户级长期记忆 |

> 命名约定：L2 的"隔离"指**写入**按模式隔离；是否**可被别的模式读取**由 `is_cross_mode_accessible` 单独控制。

---

## 2. 整体架构

```
┌─────────────── 前端 ───────────────┐
│ ChatInput「继承上文」开关           │  ← 仅 scheduled 隐藏
│ AssistantPanel → context           │
│            .enable_cross_mode_injection
└──────────────┬─────────────────────┘
               │ AgentRequest
┌──────────────▼────── AI Gateway ──────────────┐
│ mode_handlers/*.py                            │
│   ├ maybe_cross_mode_user_input()   ← 受控门控  │
│   ├ build_cross_mode_user_input()   ← 无条件    │
│   └ persist_l2_context()            ← L2 写入   │
└──────────────┬────────────────────────────────┘
               │
┌──────────────▼────── ContextManager（三层合成）──┐
│ L1  AiChatSession.context_data                  │
│ L1′ ai_chat_messages（_load_session_history）    │
│ L2  ai_context_storage（+策略过滤）              │
│ L3  Mem0Service（长期记忆）                      │
│    → build_cross_mode_injection() → prompt 前缀  │
│    → build_full_context() → 全量上下文（可截断）  │
└──────────────┬──────────────────────────────────┘
               │
┌──────────────▼────── 策略层 context_policies.py ─┐
│ PRIORITY_MAP / DEFAULT_ACCESS_MAP / TTL / 保护名单│
└──────────────────────────────────────────────────┘

调解分支（并列实现，非继承）：
MediationContextManager —— 主键为 case_number（非 session_id）
```

**关键设计约束**：
1. **读取失败一律静默降级**：`persist_l2_context` / `build_cross_mode_user_input` 内部捕获所有异常，返回原 `user_input`，**绝不阻断 SSE 主流程**。
2. **`persist_l2_context` 自持 `SessionLocal`**（不复用请求的 Session），避免长事务与连接占用。
3. **L3 检索必须走 `Mem0Service.search_with_filters`**，禁止直连 `_client.search`（协程泄漏）。

---

## 3. 数据模型

### 3.1 `ai_context_storage`（L2 隔离层）
`backend/app/models/ai_context_storage.py`

| 字段 | 说明 |
|---|---|
| `tenant_id` / `case_number` | 分区键 |
| `session_id` | 关联会话（字符串） |
| `mode` | 旧版写入分区 |
| `source_mode` | **跨模式共享标签**（`general/mediation/simulation/debug/sqlbot/research/dify_chatflow/skill/scheduled`） |
| `context_key` / `context_data` | 唯一标识 + JSON 内容 |
| `priority` | 1(高)/2(中)/3(低)；`_prune_low_priority` 删除 `priority >= 3` |
| `is_cross_mode_accessible` | **是否允许被其它模式读取**（默认 `False`） |
| `context_tags` | 数组，一条可归属多模式（GIN 索引） |
| `expires_at` | TTL 过期时间 |
| `origin_session_id` | 原始写入会话（支持派生会话） |
| `vector_embedding` | 预留 pgvector |

索引：`idx_mode_tenant` / `idx_session_key` / `idx_expires_at` / `idx_source_mode_expiry`（部分索引，仅未过期）。

### 3.2 其它表
- `ai_chat_session.context_data`（L1 共享层；含 `mode_policy`、`case_number`、`phase`、`context_snapshot`）
- `ai_chat_messages`（L1′ 消息流）
- `ai_context_compaction_log`（压缩审计日志）
- 迁移：`alembic/versions/048*`（跨模式字段）、`049_add_ai_chat_session_context_fields.py`

---

## 4. 策略层 `app/core/context_policies.py`

| 常量 | 值 / 语义 |
|---|---|
| `PRIORITY_MAP` | debug 1 / sqlbot 2 / general 3 / dify_chatflow 3 / skill 3 / scheduled 3 / research 4 / simulation 5 / **mediation 6**（数值越大越重要，压缩优先保留） |
| `DEFAULT_ACCESS_MAP` | mediation→{general,mediation,research}；simulation→{general,simulation,research}；general→{general,mediation,simulation,research}；research→同 general；sqlbot→{general,sqlbot}；debug→{debug}。<br>**skill/agent/team/thinking/deep_research 无条目 → 回落为仅自身** |
| `DEFAULT_PROTECTED_MODES` | `["mediation","simulation"]`（压缩不删） |
| `DEFAULT_TTL_HOURS` | debug 24 / sqlbot 48 / general 168 / research 336 / simulation 168 / **mediation 720** / dify_chatflow 168 / skill 168 / scheduled 720 |
| `CHAT_HISTORY_LIMIT` | 20 |
| `MEM0_RETRIEVE_TOP_K` | 5 |
| `resolve_mode_policy(ctx)` | 读 `context_data["mode_policy"]`；默认 `share_debug=False`、`share_sqlbot=False` |
| `allowed_source_modes(mode, policy, extra_tags)` | `DEFAULT_ACCESS_MAP × share_*` 交集 + extra_tags + 必含自身 |
| `auto_cross_mode_accessible(mode, priority)` | `PRIORITY_MAP[mode] >= 4 or priority <= 1` |

> ⚠️ **重要差异**：`allowed_source_modes`（白名单）**只作用于** `get_context_with_mode_filter()` 与 `build_full_context()`；
> **不作用于注入路径** `build_cross_mode_injection()` —— 后者只看 `is_cross_mode_accessible=True` + 未过期 + `exclude_source_modes`。
> 这是最容易误解的一点：**写入时打标 `is_cross_mode_accessible` 才决定能否被继承**，白名单管的是统计/检索接口。

---

## 5. 核心实现

### 5.1 `ContextManager`（`app/services/context_manager.py`）
构造：`ContextManager(db, session_id, user_id, mode, tenant_id=1)`；内部持有 `Mem0Service`。

| 层 | 方法 | 说明 |
|---|---|---|
| L1 | `get_shared_context()` | 读 `AiChatSession.context_data` |
| L2 | `get_isolated_context(key, limit=10, priority_filter=5)` | 强匹配 `mode == self.mode` |
| L2 | `store_isolated_context(key, data, priority=5, tags, cross_mode_accessible, ttl_hours, origin_session_id)` | 自动注入 `source_mode` / `is_cross_mode_accessible=auto_cross_mode_accessible()` / `expires_at` |
| L2 | `get_context_with_mode_filter(key, limit=20, allow_cross_mode=False, include_tags, priority_filter)` | **走白名单**；要求 `is_cross_mode_accessible IS TRUE OR source_mode == self.mode` |
| L3 | `sync_to_long_term(content, metadata, cross_mode_accessible=True)` | 写 Mem0 |
| L3 | `retrieve_from_long_term(query, top_k=5, allowed_source_modes, excluded_source_modes)` | 必须走 `search_with_filters` |
| 合成 | `build_full_context(max_tokens=16000, allow_cross_mode=True, max_history=None)` | 返回 `{session_id, mode, shared, history, skill_results, {mode}_current, other_modes, case_info, long_term_memory}` |
| 合成 | **`build_cross_mode_injection(active_mode, current_user_input, max_history=20, max_l2=8, include_l1=True, exclude_source_modes=None) -> str`** | **"继承上文"的唯一底层实现**（见 §5.2） |
| 生命周期 | `compact_context(strategy="summarize_recent", user_id, protected_modes)` | 见 §8 |
| 私有 | `_load_session_history` / `_extract_case_info` / `_calculate_tokens`(tiktoken cl100k，降级 `len*0.25`) / `_truncate_if_needed` | 截断顺序：`long_term_memory → other_modes → skill_results → {mode}_current → history`，附 `_truncation_meta` |

### 5.2 `build_cross_mode_injection` 行为（权威定义）
1. 首行固定：`【上下文记忆】以下是同一会话中此前其它模式的对话内容，供你理解背景（仅供参考，不必重复回答）：`
2. **L1′**：`ai_chat_messages` 按 `session_id` 取最近 `max_history` 条（模式无关）；若末条 user 消息与本次提问相同则剔除（对齐 `chat/stream` 先落库行为）；输出 `- 用户：…` / `- 助手：…`，每条截断 1500 字符。
3. **L2**：`ai_context_storage` 过滤 `tenant_id + session_id + is_cross_mode_accessible IS TRUE + 未过期 + source_mode ∉ exclude_source_modes`，按 `created_at DESC` 取 `max_l2` 条；取 `answer|result|user_input|message`，输出 `- [来自{src}模式]：{内容[:1500]}`。
4. 无内容返回 `""`（仅剩引导语即视为空）。

### 5.3 Gateway 包装器（`mode_handlers/_common.py`）

| 函数 | 语义 |
|---|---|
| `persist_l2_context(*, session_id, source_mode, context_key, context_data, priority=3, ttl_hours=None, is_cross_mode_accessible=False, context_tags=None, case_number="default", tenant_id=1) -> bool` | L2 写入统一入口；`ttl_hours` 缺省取 `default_ttl_hours(source_mode)`；失败 `logger.warning` + 返回 `False` |
| `build_cross_mode_user_input(*, session_id, user_id, active_mode, current_user_input, tenant_id=1, max_history=20, max_l2=8, include_l1=True, exclude_source_modes=None) -> str` | **无条件**注入；拼装 `f"{ctx_text}\n\n【当前用户问题】\n{current_user_input}"` |
| `maybe_cross_mode_user_input(*, context, session_id, user_id, active_mode, current_user_input, **kwargs) -> str` | **受控**：`context.enable_cross_mode_injection` 为假则原样返回 |

### 5.4 `MediationContextManager`（`app/services/mediation_context_manager.py`）
**并列实现，非继承**（`class MediationContextManager`），差异：
- 主键从 `session_id` 换成 **`case_number`**；构造 `(db, case_number, user_id, mode="mediation", session_id=None, tenant_id=1)`，非法 mode 降级 `general`
- `MEDIATION_MODES = {mediation, simulation, hitr, debug}`；Key 约定 `dialogue_history` / `snapshot_` / `agent_`
- 方法：`get_dialogue_history(limit=20)`、`store_dialogue_history(...)`（**`is_cross_mode_accessible=False`，调解对话默认不跨模式**）、`store_agent_state(agent_id, state, priority=8)`（`source_mode="simulation"`）、`get_agent_state`、`sync_case_experience(text, extra_metadata)`、`retrieve_case_experience(query, top_k=MEM0_RETRIEVE_TOP_K)`（同 case → 同 phase 优先）、`get_current_phase()`、`build_full_mediation_context(max_dialogue=20)`

---

## 6. 各模式 × 记忆能力矩阵（**最新，取代 09-24 矩阵**）

### 6.1 写入侧（谁能被别人继承）

| 模式 | Handler | `source_mode` | `is_cross_mode_accessible` | TTL(h) | priority | context_tags |
|---|---|---|---|---|---|---|
| 通用对话/纠纷调解 | `dify_chatflow.py` | `dify_chatflow` | **True** | 168 | 3 | `[dify_chatflow, session_type]` |
| 数据分析 | `data.py` | `sqlbot` | False | 48 | 2 | `[sqlbot, datasource_{id}]` |
| 技能 | `skill.py` | `skill` | **True** | 168 | 2 | `[skill, pkg_id]` |
| 深度思考 | `thinking.py` | `thinking` | False | 720 | 1 | `[thinking]` |
| 深度研究 | `deep_research.py` | `deep_research` | False | 720 | 2 | `[deep_research]` |
| 智能体 | `agent.py` | `agent` | False | 720 | 2 | `[agent, thinking]` / `[agent, tool_call]` |
| 智能体团队 | `team.py` | `team` | False | 720 | 2（思考）/ 1（发言） | `[team, thinking]` / `[team, speech]` |
| 云端调度 | `scheduled.py` | `scheduled` | False | 720 | 4 | `[scheduled, target_mode]` |
| 调解 HITL | `MediationContextManager` / `HITLContextSnapshotter` | `mediation` / `hitr` / `simulation` | False（对话与 Agent 状态） | 720 | 5~8 | — |

> ⚠️ **TTL 实际值 vs 策略默认值不一致**：多数 handler **硬编码** `ttl_hours=720`（agent / deep_research / thinking / team / scheduled），
> 与 `DEFAULT_TTL_HOURS`（research 336、general 168 等）不符；仅 `dify_chatflow`(168)、`skill`(168)、`data`(48) 与策略值接近。
> 即 **策略层的 TTL 表对多数模式实际未生效**，属已知技术债（见 §14 #7）。

> 结论：**只有 `skill` 与 `dify_chatflow` 的产物默认可被其它模式继承**；其余模式写入 `is_cross_mode_accessible=False`（可被本模式检索，不参与跨模式注入）。

### 6.2 读取侧（"继承上文"支持情况）

| 模式 | UI 开关 | 后端门控 | 默认值 | 注入参数 |
|---|---|---|---|---|
| 通用对话 / 纠纷调解 | 显示 | **无条件**（`build_cross_mode_user_input`） | 始终继承 | `include_l1=False`、`exclude_source_modes=["dify_chatflow"]`（避免与 Dify 自有 `conversation_id` 历史重复） |
| 数据分析 | 显示 | **双开关**：请求 `enable_cross_mode_injection` **或** 全局 `SQLBOT_CROSS_MODE_INJECTION_ENABLED` | **关**（保证 NL2SQL 准确率） | 前缀注入到 `_sqlbot.query_stream(...)` |
| 技能 / 智能体 / 团队 / 深度思考 / 深度研究 | 显示 | `maybe_cross_mode_user_input`（`enable_cross_mode_injection`） | 关 | 默认参数 |
| 云端调度 | **隐藏**（`v-if="sessionType !== 'scheduled'"`） | 不注入 | — | 提交即返回 |
| 调解 HITL | 不适用 | 不注入 | — | 走 `MediationContextManager` 自有链路 |

**已知不一致（待收敛）**：通用/纠纷（Dify）前端也显示"继承上文"开关并下发 `enable_cross_mode_injection`，但后端 `dify_chatflow.py` **无条件注入、忽略该开关** —— 即该模式下开关实际无效（UI 上表现为"关了也继承"）。属有意设计（Dify 必须继承技能记忆），但 UI 语义需后续对齐。

---

## 7. 「继承上文」端到端链路

1. **前端**：`ChatInput.vue`（除 `scheduled` 外显示，class `inherit-context-toggle`）→ `update:inheritContext`
2. **持久化**：`AssistantPanel.vue` — `assistant.inheritContext`（localStorage），`watch` 落盘
3. **请求组装**：`AssistantPanel.vue` — `scheduled` 只下发 `target_mode/priority/timeout_seconds/max_retries`；其余下发 `context.enable_cross_mode_injection = inheritContext.value`（`deep_research` 额外加 `knowledge_bases/max_sub_questions/max_concurrency`）
4. **网关**：handler 调 `maybe_cross_mode_user_input`（或 `data.py` 自有的双开关逻辑）
5. **合成**：`ContextManager.build_cross_mode_injection` → `【上下文记忆】…【当前用户问题】…`
6. **注入**：作为 `user_input` 传入下游引擎（SQLBot / 编排器 / Dify）

---

## 8. 生命周期管理

- **TTL 清理**：`app/tasks/context_ttl_cleanup.py` → `AiContextStorageCleanupService`（批量删除，避免大事务）
- **压缩** `compact_context(strategy)`：`<5000` tokens 跳过；返回 `{before_tokens, after_tokens, compression_ratio, summary, snapshot_data, deleted_count, protected_modes}`
  - `summarize_recent` → `_summarize_recent_conversations`
  - `prune_low_priority` → `_prune_low_priority`（删 `priority >= 3`）
  - `archive_old` → `_archive_to_mem0`（归档后删本地，元数据含 `context_key/context_id/case_number/created_at`）
  - 三者均 `~source_mode.in_(protected_modes)` 排除受保护模式
- **截断**：`_truncate_if_needed` 按固定优先级削减，写 `_truncation_meta`
- **审计**：`_log_compaction` → `ai_context_compaction_log`

---

## 9. 长期记忆：Mem0

### 9.1 `Mem0Service`（`app/services/mem0_service.py`，兼容 AgentScope `MemoryBase`）
后端选择顺序：**自托管 REST > 云端 SDK > 本地内存**

| 实现 | 触发条件 | 行为 |
|---|---|---|
| `SelfHostedMem0Impl` | `Mem0Config.host` 非空 | 纯标准库 `urllib`；`POST {host}/memories`、`POST {host}/memories/search`；鉴权 `X-API-Key` + `Authorization: Bearer` 兜底；超时 10s；失败降级 |
| 云端 `MemoryClient` | `mem0` SDK 已装 且 `api_key` 非空 | 官方云 API |
| `LocalMem0Impl` | 以上皆否 | 进程内 list，**重启即失**（仅开发兜底） |

API：`record` / `retrieve` / `add_memory`（别名）/ `search_memories`（别名）/ `search_with_filters(query, user_id, limit, allowed_modes, excluded_modes)`（云端走服务端 `filters`，本地/降级走后置过滤）。

### 9.2 配置（`app/config.py`）
```python
MEM0_API_KEY: str = ""   # 自托管管理员密钥 m0sk_... / 云端 key
MEM0_HOST: str = ""      # 非空 → 直连自托管 REST（不依赖 mem0 SDK）
```
`Mem0Config`：另有 `max_entries=10000`、`embedding_model="all-MiniLM-L6-v2"`、`vector_dimension=384`。

### 9.3 接口与前端
- `POST /ai/context/memory/record`（`sync_to_long_term`）、`POST /ai/context/memory/retrieve`（支持 `filters.mode` / `date_range` 后置过滤）
- `POST /api/v1/ai-sessions/{id}/manual-note`（调解员手动笔记 → Mem0）、`POST /api/v1/ai-sessions/{id}/memory-aids`（记忆辅助检索）
- 前端：`api/aiContext.ts`（`recordLongTermMemory` / `retrieveLongTermMemory`，`cross_mode_accessible` 默认 `true`）、`api/mediationMemory.ts`（`useRecordManualNote` / `useFetchMemoryAids` / `useMediatorMemories`）

---

## 10. 并发保护：PG 咨询锁（2026-09-29 补齐）

**背景**：`app/db/advisory_lock.py` 曾整体缺失（git 历史从未存在），导致 6 处 import 失败、`routers/key_matters.py` 无法启动。已按调用方签名重建。

```python
class AdvisoryLockBusyError(Exception)          # 锁被占用 → 判定为瞬时并发冲突

def acquire_advisory_xact_lock(db, key: int, *, lock_name: str, owner_id: int) -> None:
    # SELECT pg_try_advisory_xact_lock(:key)；非阻塞，占用即抛 AdvisoryLockBusyError
    # 锁随事务 COMMIT/ROLLBACK 自动释放
```

| 调用方 | `lock_name` | `owner_id` | key |
|---|---|---|---|
| `entity_candidate_service._acquire_candidate_lock` | `entity_candidate` | `event_id` | `int(fingerprint[:15], 16)` |
| `key_matter_identity_service._acquire_identity_lock` | `key_matter_identity` | `event_id` | `int(sha256(强锚点线索)[:15], 16)` |
| `key_matter_warning_service._acquire_warning_lock` | `key_matter_warning` | `matter_id` | `matter_id` |

捕获/识别：`tasks/key_matter_failure.py`（映射为 `advisory_lock_busy` 错误码，提示"并发处理同一聚合对象，等待下一轮重试"）、两个 `key_matter_*_pipeline.py`（`except AdvisoryLockBusyError: raise`）。

> 注：ContextManager / MediationContextManager / `persist_l2_context` **不使用咨询锁**，它们走"自持 `SessionLocal` + 静默降级"。**两条并发机制平行、不交叉。**

---

## 11. 附：AI Agent 侧 mem0（与应用内记忆无关）

| 项 | 位置 |
|---|---|
| MCP 服务注册 | `~/.codebuddy/mcp.json`（streamable-http，约定名 `mem0`） |
| 工程级配置 | `.codebuddy/mem0.config.json`（**git-ignored，含 api_key 严禁提交**）：`mcp_server=mem0-tianque`、`api_url=http://192.168.110.169:8080/mcp`、`api_key=m0sk_***`（脱敏）、`admin_user_id`、`project_id=risk_control`、`git_remote` |
| 加载/保存规则 | 根 `CODEBUDDY.md` §1–§2（会话开始 `get_memories` 拉池；持久事实 `add_memory`） |
| 自动化脚本 | `mem0-transcript-poster.mjs` / `mem0-ide-session-poster.mjs` —— 位于 `ai-dev-sop` 仓库，**不在本仓** |

---

## 12. 接口清单

### 12.1 后端（注意前缀差异）
`routers/ai/context.py`：**无 `/api/v1` 前缀**（`main.py` 注册时未加）→ `/ai/context/...`

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/ai/context/session/{id}/stats` | `build_full_context` + token 估算 + 按 `source_mode` 分组 breakdown + Mem0 计数 |
| POST | `/ai/context/compact` | 策略映射 `summarize_recent / prune_low_priority / archive_old`（未知策略 400） |
| GET | `/ai/context/session/{id}/entries` | `get_context_with_mode_filter` |
| POST | `/ai/context/memory/record` | 写长期记忆 |
| POST | `/ai/context/memory/retrieve` | 检索长期记忆 |
| POST | `/ai/context/short-term` | 写 L2 |
| GET | `/ai/context/short-term` | 读 L2（前端 `getShortTermMemory`） |

辅助 `_resolve_mode_for_session`：`preferred_mode → agent_mode → session_type 映射(dispute→mediation, data→sqlbot) → 最近 source_mode 众数 → fallback`。

`routers/mediation/mediation_context.py`：**带 `/api/v1`** → `/api/v1/mediation/...`

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/case/{case_number}/context/stats` | 按案件聚合（simulation→agent_states、hitr→snapshot_count），token 估算 `条目数*256` |
| POST | `/context/compact` | 找 anchor session（`context_data.case_number`）；无锚点走 `cleanup_expired_records`；有锚点走 `compact_context(protected_modes=["mediation","hitr"])` 并写回 `context_snapshot` |
| GET | `/case/{case_number}/context/dialogue` | 调解对话历史 |
| POST/GET | `/case/{case_number}/context/agent-state[/{agent_id}]` | 仿真 Agent 状态（写后 `bump_context_version`） |
| GET | `/case/{case_number}/context/hitl-snapshots` | HITL 快照列表 |
| GET/POST | `/hitl-snapshots[/{hitl_request_id}]` | 读/建 HITL 快照（`case_number` 必填） |

### 12.2 前端
- `frontend/src/api/aiContext.ts`：`getContextStats` / `compactContext` / `getContextEntries` / `storeShortTermMemory` / `getShortTermMemory` / `recordLongTermMemory` / `retrieveLongTermMemory`
- `frontend/src/api/mediationMemory.ts`：`useFetchMediatorContext` / `useFetchMediatorPreferences` / `useRecordManualNote` / `useFetchMemoryAids` / `useMediatorMemories`
- 消费方：`ContextStatsDrawer.vue`、`ContextStatsCard.vue`、`SQLBotStatsDrawer.vue`、`MemoryAidsDrawer.vue`、`api/sqlbotStats.ts`

---

## 13. 测试覆盖

| 文件 | 覆盖 |
|---|---|
| `tests/integration/test_cross_mode_access_control.py` | 白名单/拒绝矩阵（general↔mediation 放行、thinking→skill 拒绝、debug→general 拒绝、同模式绕过 accessible 检查、long_term 按 source_mode 过滤） |
| `tests/integration/test_cross_mode_context_completion.py` | 各模式 L2 落库（dify/sqlbot/skill/scheduled）+ 新模式纳入跨模式过滤 + breakdown 可见 |
| `tests/integration/test_l2_lifecycle.py` | TTL 清理、默认 TTL（mediation 720 / general 168）、`persist_l2_context` 失败静默降级 |
| `tests/integration/test_phase4_gap_closure.py` | debug 快照、token 截断（`_truncation_meta`）、压缩策略映射（含未知策略报错） |
| `tests/integration/test_phase5_remaining_gaps.py` | 缺失 `user_id` 修复、`bump_context_version`、Agent 状态持久化 |
| `tests/unit/models/test_ai_context_storage.py` | ORM 模型（TTL / 过期 / `to_dict` / 优先级 / mode 取值） |
| `tests/unit|integration/.../test_debug_context_isolator*.py` | EventDebugPanel 隔离器（快照创建/读取/过期/清理） |
| `tests/mediation/test_case_context_store.py` | `CaseContextStore` L1 内存层 |

---

## 14. 已知差距与后续

| # | 缺口 | 建议 |
|---|---|---|
| 1 | Dify（通用/纠纷）模式下"继承上文"开关无效（后端无条件注入） | UI 隐藏该模式开关，或后端改为尊重开关 |
| 2 | 写入侧仅 `skill` / `dify_chatflow` 可跨模式继承，其余模式产物互不可见 | 按业务需要逐个放开 `is_cross_mode_accessible`（注意 SQLBot 准确率风险） |
| 3 | `DEFAULT_ACCESS_MAP` 缺 `skill/agent/team/thinking/deep_research` 条目 → 这些模式在统计接口中只能读自身 | 补齐白名单条目 |
| 4 | SQLBot 注入为纯 prompt 前缀，长上下文仍可能拉低准确率 | 可对注入内容做结构化摘要而非原文拼接 |
| 5 | `vector_embedding` 字段预留但未启用，L2 检索仍为结构化过滤 + 时间排序 | 接入 pgvector 做语义检索 |
| 6 | Mem0 本地回退（`LocalMem0Impl`）重启即失，生产环境须配置 `MEM0_HOST` | 生产强制校验 `MEM0_HOST` 非空 |
| 7 | handler 硬编码 `ttl_hours`（多为 720）使 `DEFAULT_TTL_HOURS` 对多数模式形同虚设 | 移除硬编码，统一走 `default_ttl_hours(source_mode)`；确需差异则在策略表调整 |
| 8 | 仅 `data.py` 在写 L2 后额外 `sync_to_long_term`，其余模式无长期记忆沉淀 | 评估是否对 `skill` / 调解结论等开通 Mem0 同步 |

---

## 15. 关联文档（历史留痕）

- `docs/sessions/multi-mode-context-unification-design.md`（统一上下文 v2.0）
- `docs/sessions/context-unification-quick-reference.md`（速查）
- `docs/sessions/phase1-context-architecture-completed.md` / `phase2-lifecycle-management-completed.md` / `phase3-hitl-memory-enhancement-completed.md`
- `docs/session_mode_context_pipeline.md`
- 本目录下的 4 份 09-22 / 09-24 旧 spec（**已被本文取代**）

---

**文档结束**
