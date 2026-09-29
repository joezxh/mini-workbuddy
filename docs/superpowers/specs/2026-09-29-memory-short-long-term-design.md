# 短期记忆 + 长期记忆（ReMe/Mem0 可切换）— 架构设计

> **版本**：v1.0
> **日期**：2026-09-29
> **状态**：Partially Implemented（P0 + P1 主体已完成；P1 读取侧 recall 接线待收尾；P2 延后）
> **落地工程**：MinWorkBuddy（`backend/app`）
> **参照**：`docs/superpowers/specs/2026-09-29-context-memory-consolidated-design.md`（同日合并稿）

---

## 0. 与同日合并稿的关系

合并稿 `2026-09-29-context-memory-consolidated-design.md` 描述的是**上下文记忆 / 跨模式继承**，本文在其之上补齐**短期记忆（L1 工作记忆 + L2 会话记忆）与长期记忆后端可切换**。

两点必须先声明，避免误读：

1. 合并稿中若干路径与**当前代码不符**（`app/config.py`、`app/mode_handlers/_common.py`、`Mem0Service.search_with_filters` 均不存在）。**本文一切以当前代码为准**（证据见 §2），建议合并稿后续标注"路径已过时"。
2. 分工：合并稿继续拥有「模式 × 跨模式继承矩阵、接口清单、前端消费」；**本文拥有 L1/L2/L3 的分层、数据结构、存储检索与 L3 provider 抽象**。二者冲突时以本文为准。

---

## 1. 范围与术语

### 1.1 两套「记忆」必须区分

| | **A. 应用内记忆**（本文主体） | **B. Agent 自身记忆** |
|---|---|---|
| 服务对象 | 终端用户（会话连贯、跨会话继承） | CodeBuddy Agent（跨 IDE 会话记项目事实） |
| 存储 | 本工程 Postgres + Redis + 记忆后端 | 外部自托管 mem0 服务 |
| 配置 | `backend/app/config/` | `~/.codebuddy/mcp.json`、`.codebuddy/mem0.config.json` |
| 本文 | 全文 | **不涉及** |

### 1.2 分层

| 层 | 名称 | 载体 | 是否持久化 |
|---|---|---|---|
| **L0** | 消息流 | `ai_chat_message` | ✅ 永久（唯一权威事实源） |
| **L1** | 工作记忆 | 内存投影 + **Redis 快照** | ⚠️ 缓存（TTL 30min，可重建） |
| **L2** | 会话记忆 | `ai_context_storage` | ✅ TTL（按模式 48h~720h） |
| **L3** | 长期记忆 | ReMe / Mem0 / none | ✅ 永久 |

**单一事实源**：L0 是唯一权威对话流水；L2/L3 都是派生视图；**L1 是运行时投影，Redis 快照只是缓存，永不作为唯一数据源**。

---

## 2. 现状盘点与差距

### 2.1 已有资产（真实代码）

| 层 | 载体 | 位置 |
|---|---|---|
| L0 | `ai_chat_message` | `backend/app/models/ai/ai_chat.py:50` |
| L1′ | **进程内 dict** `_shared_context` / `_isolated_contexts` | `backend/app/ai/context_manager.py:111-114` |
| L2 | `ai_context_storage` | `backend/app/models/ai/ai_chat_context_storage.py:24` |
| L2 读写 | `persist_l2_context` / `get_context_with_mode_filter` | `backend/app/ai/context_manager.py:655 / 770` |
| L3 | Mem0（**同步** httpx） | `backend/app/ai/services/mem0_service.py:69 / 340` |
| 策略 | 常量表 + 10 条 `STRATEGY_TABLE` | `backend/app/core/context_policies.py`、`backend/app/ai/services/cross_mode_recorder.py:47` |
| 预算 | 模型窗口常量 | `backend/app/constants/llm_tokens.py` |
| 压缩/审计 | 调度器 + 审计表 | `backend/app/services/auto_compaction_scheduler.py`、`models/ai/ai_session_finalize_log.py` |
| Redis | `RedisSettings.REDIS_URL`；`redis.from_url` 降级范式 | `backend/app/config/_redis.py:14`、`backend/app/services/kb/kb_cache.py:24` |
| 接线点 | 读取侧 brief / 写入侧 finalize | `backend/app/routers/ai/ai_agent.py:174-180 / 209-245` |

### 2.2 必须解决的差距

| # | 差距 | 影响 | 修复 |
|---|---|---|---|
| G1 | L1′ 是进程内 dict，生产 `gunicorn -w 4` 多 worker 不共享、重启即失 | 「工作记忆」跨请求不成立 | L1 改为可重建投影 + Redis 快照（§5.2） |
| G2 | 预算口径分裂：`TokenBudget` 用 `len(split())+50`（`context_manager.py:72`），与模型窗口无关 | 超窗口 / 浪费窗口 | 统一走 `constants/llm_tokens.py`（§6.3） |
| G3 | `Mem0Service` 同步 httpx 阻塞事件循环；`record()` 返回 bool 却被伪造成 `f"mem_{u}_{s}"`（`context_manager.py:762`） | 审计字段 `mem0_memory_id` 不可信 | Provider 改 async + 返回真实 id（§7.4） |
| G4 | L3 硬编码 Mem0（`sync_to_long_term` 直接 import） | 无法切换后端 | `LongTermMemoryProvider` 抽象（§5.4） |
| G5 | 四套"长期记忆"并存：Mem0Service / `memory_service.LongTermMemoryService`(InMemory) / `UserMemoryManager`+Graphiti / `middleware/graphiti_memory.py` | 事实源分裂 | 收敛：L3 只有一个 provider 抽象；Graphiti 另案不动（§9.8） |
| G6 | L2 无语义检索（`embedding_vector` 是 `Text` 且从未写入）；pgvector 已在 `kb_segment` 启用 | 只能结构化过滤 | P2 可选，本期不做（§14） |
| G7 | 唯一键 `(tenant,session,mode,context_key)` + `context_key` 含毫秒时间戳 → 每次 finalize 新增一行，无幂等 | L2 单调膨胀 | 新增 `memory_kind` / `run_id`，按 kind 组织（§5.3） |
| G8 | 读取侧 `build_cross_mode_brief` 是固定 200 字符截断的裸文本拼接，无预算模型、无来源可追溯 | 注入不可控 | L1 统一装配与裁剪（§5.1） |

---

## 3. 目标架构

```
写入链路 (capture)
  SSE finalize (routers/ai/ai_agent.py:238)
      └─► MemoryPolicy(模式策略, memory/policies.py)
            ├─► L2 SessionMemoryStore  → ai_context_storage (TTL)  → INCR Redis gen
            └─► L3 provider.capture()  → ReMe / Mem0 (异步后台)     → INCR Redis gen
            └─► ai_session_finalize_log (审计, 真实 memory_id)

读取链路 (recall)  每请求
  Redis GET gen + GET snapshot  ──命中──► WorkingMemory(items) ──┐
       └─未命中──► L0 最近 N 条                                  ├─► 预算分配 + 固定裁剪序
                  L2 (tenant+session+kind+未过期+tags)           │   (safe_input_budget)
                  L3 provider.recall(top_k, 后置过滤)  ──────────┘
                       └─► 回写 Redis 快照 (≤64KiB, TTL 1800s)
                       └─► to_messages() / to_brief() → AgentScope Agent
```

**三条硬原则**

1. **可重建**：L1 永远能从 L0+L2+L3 重算；Redis 只是省算力的缓存，宕机即降级为全量重建。
2. **失败静默 + 可观测**：沿用现有 `logger.warning` 静默降级 + `ai_session_finalize_log`；任何记忆异常**绝不阻断 SSE**。
3. **收敛而非新增**：不引入第五套长期记忆（G5）。

---

## 4. 模块职责

新建包 `backend/app/ai/memory/`：

| 文件 | 职责 | 状态 |
|---|---|---|
| `memory/types.py` | L1/L2/L3 统一数据结构（dataclass） | 新建 |
| `memory/budget.py` | 预算分配与裁剪；**唯一入口**委托 `constants/llm_tokens.py`，不引入第二套估算器 | 新建（修 G2） |
| `memory/working.py` | L1 `WorkingMemoryBuilder`：装配 + 裁剪 + `to_messages()` / `to_brief()` | 新建 |
| `memory/working_cache.py` | L1 Redis 快照：GET/SET、`gen` 失效、体积上限、降级 | 新建（修 G1） |
| `memory/session_store.py` | L2 `SessionMemoryStore`：v1 schema 读写、TTL、跨模式可见性、tags、v0 兼容 | 新建（吸收 `ContextManager` 的 L2 部分） |
| `memory/policies.py` | 模式 × 记忆策略**单一事实源**（合并 `core/context_policies.py` + `STRATEGY_TABLE`） | 新建（消除双策略源） |
| `memory/ltm/base.py` | L3 `LongTermMemoryProvider` Protocol（**async**）+ `MemoryScope/Draft/Record/Query` | 新建（修 G4） |
| `memory/ltm/reme_provider.py` | ReMe HTTP Job API 实现（**默认 provider**） | 新建 |
| `memory/ltm/mem0_provider.py` | Mem0 实现（异步 httpx，返回真实 memory_id） | 新建（修 G3） |
| `memory/ltm/null_provider.py` | noop 兜底，显式标记"非持久" | 新建 |
| `memory/ltm/factory.py` | 按配置选 provider + 注册表（可扩展第三后端） | 新建 |
| `memory/facade.py` | `MemoryService`：`recall()` / `capture()`，上层唯一入口 | 新建 |

改造：

| 文件 | 改动 |
|---|---|
| `ai/context_manager.py` | 改为**薄壳**：`persist_l2_context` / `sync_to_long_term` / `get_context_with_mode_filter` / `compact_context` 委托给 store/facade，**旧签名全部保留** |
| `ai/services/cross_mode_recorder.py` | `STRATEGY_TABLE` 迁至 `memory/policies.py`，本模块 **re-export 保持兼容**；L3 写入改异步 |
| `config/_memory.py` | 新增 `MemorySettings`（`MEMORY_*` + `REME_*`） |
| `config/__init__.py` | `Settings` 继承链加入 `MemorySettings` |
| `config/_mem0.py` | **原样保留**（向后兼容），Mem0 退为 opt-in |
| `models/ai/ai_chat_context_storage.py` | +3 列 + 1 索引 |
| `models/ai/ai_session_finalize_log.py` | +1 列 `ltm_provider` |

---

## 5. 数据结构

### 5.1 L1 工作记忆

```python
WORKING_KINDS = ("system", "turn", "fact", "artifact", "ltm", "tool")

@dataclass(frozen=True)
class WorkingItem:
    kind: str          # system|turn|fact|artifact|ltm|tool
    role: str          # system|user|assistant|tool
    content: str
    tokens: int
    priority: int      # 1 最重要（与 PRIORITY_MAP 同向：越小越重要）
    src: str           # l0:{msg_id} | l2:{id} | l3:{provider}:{id}
    pinned: bool = False
    ts: str | None = None

@dataclass
class WorkingMemory:
    model: str
    window: int
    budget: int
    items: list[WorkingItem]      # 已裁剪，可直投 prompt
    dropped: list[WorkingItem]    # 被裁掉（审计，不入 prompt）
    from_cache: bool = False

    def to_messages(self) -> list[dict[str, str]]: ...    # 给 AgentScope
    def to_brief(self, max_chars: int = 4000) -> str: ...  # 给 sys_prompt 前缀

    @property
    def meta(self) -> dict: ...   # {window, budget, used, dropped_by_kind, from_cache}
```

**裁剪序（固定）**：`tool → artifact → ltm → fact → turn`；`system` 与 `pinned` **永不裁**。
同类内：先删 `priority` 大者，再删 `ts` 早者。

### 5.2 L1 Redis 快照（缓存层）

| 项 | 设计 |
|---|---|
| Key | `mwb:wm:v1:{tenant_id}:{session_id}:{mode}` |
| 版本键 | `mwb:wm:gen:{tenant_id}:{session_id}`（INCR） |
| Value | `{"v":1,"gen":7,"model":"qwen3-32b","window":32768,"budget":24000,"built_at":"...","items":[...]}` |
| **存"已装配未裁剪"的 items** | 裁剪结果依赖本次 input/output token，缓存成品会导致预算错配 |
| TTL | 1800s（`MEMORY_WORKING_SNAPSHOT_TTL`） |
| 体积上限 | 64 KiB；超出**不写**（不淘汰、不报错） |
| 失效 | 任何 L2 写入 / L3 capture 完成后 `INCR gen`；读侧 `gen` 不一致即重建 |
| 降级 | Redis 不可用 → 直接全量重建，`logger.debug` 采样，**绝不失败请求** |
| 客户端 | 同步 `redis.from_url(settings.REDIS_URL)`，复用 `services/kb/kb_cache.py:24` 的降级工厂范式 |

### 5.3 L2 会话记忆（`ai_context_storage`）

新增列（迁移 `2026_09_29_0001_memory_kind_fields.py`）：

```python
memory_kind    = Column(String(24), nullable=False, server_default="artifact")  # turn|fact|artifact|note
token_estimate = Column(Integer,   nullable=False, server_default="0")
run_id         = Column(String(64), nullable=True)    # 溯源 execution_id / AgentRun
Index("ix_ai_ctx_kind_session", "tenant_id", "session_id", "memory_kind", "expires_at")
```

`context_data` **schema v1**：

```json
{
  "schema_version": 1,
  "kind": "artifact",
  "summary": "供 L1 直接注入的短摘要 (≤2000)",
  "payload": { "...": "模式原始产物，按需全量读取" },
  "actor":   { "tenant_id": 1, "user_id": 1, "session_id": 1, "run_id": "..." },
  "token_estimate": 512,
  "source":  { "session_type": "agent", "source_mode": "agent" }
}
```

> **v0 兼容**：`schema_version` 缺失时整块当 `payload`，`summary` 沿用 `cross_mode_recorder._ANSWER_KEYS` 抽取。

`ai_session_finalize_log` 新增 `ltm_provider String(16)`；`mem0_memory_id` 改为存 **`{provider}:{原生 id}`**。

### 5.4 L3 长期记忆（provider 无关）

```python
@dataclass
class MemoryScope:
    tenant_id: int
    user_id: int
    session_id: int | None = None
    case_number: str | None = None
    source_modes: list[str] | None = None
    exclude_source_modes: list[str] | None = None
    tags: list[str] | None = None

@dataclass
class MemoryDraft:                      # 写入
    content: str
    kind: str = "fact"                  # fact|summary|note
    scope: MemoryScope = None
    slug: str | None = None             # ReMe 幂等路径用
    metadata: dict = field(default_factory=dict)

@dataclass
class MemoryRecord:                     # 读取
    id: str
    content: str
    score: float | None = None
    created_at: str | None = None
    metadata: dict = field(default_factory=dict)
    provider: str = ""

@dataclass
class MemoryQuery:
    text: str
    scope: MemoryScope
    top_k: int = 5
    max_chars: int = 4000

class LongTermMemoryProvider(Protocol):  # 全部 async
    name: str
    async def capture(self, drafts: Sequence[MemoryDraft]) -> list[str]: ...
    async def recall(self, query: MemoryQuery) -> list[MemoryRecord]: ...
    async def delete(self, ids: Sequence[str], scope: MemoryScope) -> int: ...
    async def health(self) -> dict: ...   # {ok, detail, latency_ms}
```

---

## 6. 存储与检索策略

### 6.1 分层策略表

| 层 | 存储 | 写入时机 | 检索 | 生命周期 |
|---|---|---|---|---|
| L0 | Postgres `ai_chat_message` | 每轮（已有） | 按 session 取最近 N（默认 20） | 永久 |
| L1 | Redis 快照 | 每次 recall 重建后回写 | `GET key` + `GET gen` | TTL 30min / gen 失效 |
| L2 | Postgres `ai_context_storage` | SSE finalize（策略驱动） | `tenant + session + memory_kind + 未过期 (+is_cross_mode_accessible) + tags`，按 `last_accessed DESC` | `DEFAULT_TTL_HOURS`（48h~720h），`auto_compaction_scheduler` 清理 |
| L3 | ReMe workspace / Mem0 服务 | 同 finalize，异步后台 | provider 语义检索 + **统一后置过滤**（tenant/user/source_mode/tags）+ `max_chars` 截断 | 永久 |

### 6.2 检索顺序

1. Redis 快照（`gen` 校验）
2. 未命中 → L0 最近 N 条 → L2 会话内 + 跨模式可见 → L3 `recall(top_k)`
3. 统一进 `WorkingMemoryBuilder` 预算裁剪
4. 回写快照

### 6.3 预算

- 唯一来源：`constants/llm_tokens.py` —— `resolve_context_window(model)` → `safe_input_budget(window, max_output)`（受 `SAFETY_MARGIN_TOKENS=1024`、`MIN_INPUT_BUDGET_TOKENS=4096` 约束）。
- **废弃** `context_manager.TokenBudget` 的 `len(split())+50` 估算。
- 分配比例 `MEMORY_BUDGET_RATIO`（可配，默认）：`system/pinned` 先占 → `turn 0.45` → `fact 0.15` → `artifact 0.15` → `ltm 0.15` → `tool 0.05`。
- 字符→token 估算集中在 `memory/budget.py` 单点，后续换 tiktoken 只改一处。

---

## 7. ReMe / Mem0 接入与配置切换

### 7.1 已确认决策

| 决策 | 结论 |
|---|---|
| 默认 provider | **`MEMORY_LTM_PROVIDER=reme`**（Mem0 退为 opt-in） |
| ReMe 多租户 | **共享 workspace + 路径前缀** `t{tenant_id}/u{user_id}/`，召回后按前缀**后置过滤**（单容器） |
| L2 策略源 | `STRATEGY_TABLE` 迁至 `memory/policies.py`，原模块 re-export 兼容 |
| L1 | 增加 Redis 快照缓存层 |

### 7.2 能力对照（事实，非推测）

| | **ReMe**（默认） | **Mem0**（opt-in） |
|---|---|---|
| 形态 | Markdown 文件 workspace（`daily/` → `digest/`）+ BM25 + 可选向量 + wikilink | 实体/事实抽取 + 向量库 |
| 服务 | `reme start`，默认 `127.0.0.1:2333`，Job 暴露为 `POST /<job-name>`，响应 `{success, answer, metadata}` | 自托管 REST（本工程 `docker/mem0`）或云端 SDK |
| 写入 | `POST /write {path,name,description,content}`（直写，**不需要 LLM**）；`POST /auto_memory {session_id,messages,date}`（需 LLM，每 session 一张 daily 卡） | `POST {MEM0_RAG_URL}/memories {user_id,message,metadata}`（服务端 LLM 抽取） |
| 检索 | `POST /search {query,limit,min_score,start_date,end_date}` → `metadata.results[]`（含 `path:start_line-end_line`、score、outlinks/inlinks） | `POST {MEM0_RAG_URL}/search` |
| 多租户 | ⚠️ `workspace_dir` 是**服务级配置，不支持按请求传入** → 采用路径前缀约定 | metadata 原生 `user_id` / `tenant_id` 过滤 |
| Python | 3.11+（本工程 `python:3.11-slim` ✅） | 无 SDK 也可（本工程自研 HTTP 客户端） |
| 鉴权 | **服务层无鉴权**；必须 `service.jobs=[search,read,write,traverse]` 白名单 + 仅内网 | `X-API-Key` / `Authorization: Bearer` |

### 7.3 ReMe 映射规则

**capture**

| `MemoryDraft.kind` | 目标 Job | path（幂等，重复写=更新） |
|---|---|---|
| `summary`（模式产物摘要） | `/write` | `digest/t{tenant}/u{user}/{yyyy-mm}/{yyyy-mm-dd}-{session_id}.md` |
| `fact` / `note` | `/write` | `digest/t{tenant}/u{user}/{yyyy-mm}/{slug}.md`（`slug` 取自 `draft.slug`，缺省用 `sha1(content)[:10]`） |

> `auto_memory`（LLM 提炼 + session 级卡片 upsert）列为 **P2**，由 `REME_AUTO_MEMORY_ENABLED` 控制；默认关闭，以保证默认 provider 不强依赖 LLM。

**recall**

1. `POST /search`，`limit = REME_SEARCH_LIMIT`（默认 20，**过召回**以抵消后置过滤损耗）
2. 取 `metadata.results[]`（缺失时降级解析 `answer`）
3. 按 `path.startswith(f"digest/t{tenant}/u{user}/")` 过滤
4. 按 score 排序取 `top_k`，累计 `max_chars` 截断
5. `MemoryRecord.id = f"reme:{path}#{start_line}-{end_line}"`

### 7.4 Mem0 映射规则

- `capture` → `POST {MEM0_RAG_URL}/memories`，metadata 写入 `tenant_id/user_id/source_mode/session_type/case_number/run_id/tags`。
- `recall` → `POST {MEM0_RAG_URL}/search`（路径可用 `MEM0_SEARCH_PATH` 覆盖）。
- **必须返回服务端真实 memory id**，禁止再伪造 `f"mem_{u}_{s}"`（修 G3）。
- 客户端改为 `httpx.AsyncClient`，超时 `MEMORY_LTM_TIMEOUT_MS`。

### 7.5 切换机制

```python
# memory/ltm/factory.py
_REGISTRY = {"reme": ReMeProvider, "mem0": Mem0Provider, "none": NullProvider}

def get_provider() -> LongTermMemoryProvider:
    # 读 settings.MEMORY_LTM_PROVIDER；provider 对象缓存 60s + reload() 手动刷新
```

- provider **无状态**，作用域全部由 `MemoryScope` 传参 → 全局单例天然多租户安全。
- 业务代码只依赖 `LongTermMemoryProvider` Protocol，切换后端零改动。
- 新增第三后端：实现 Protocol + 注册一行。
- **不做**自动回退到另一个后端（避免双写与事实源分裂）；后端不可用时 `MEMORY_LTM_FAIL_OPEN=true` → recall 返回空、capture 记 warning，主流程不受影响。

---

## 8. 配置清单（新增 `config/_memory.py`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `MEMORY_LTM_PROVIDER` | `reme` | `reme` / `mem0` / `none` |
| `MEMORY_LTM_ENABLED` | `true` | 总开关 |
| `MEMORY_LTM_TOP_K` | `5` | 单次召回条数 |
| `MEMORY_LTM_MAX_CHARS` | `4000` | 召回内容字符预算 |
| `MEMORY_LTM_TIMEOUT_MS` | `3000` | 单次调用超时 |
| `MEMORY_LTM_FAIL_OPEN` | `true` | 后端不可用时静默降级 |
| `MEMORY_WORKING_SNAPSHOT_ENABLED` | `true` | L1 Redis 快照 |
| `MEMORY_WORKING_SNAPSHOT_TTL` | `1800` | 快照 TTL（秒） |
| `MEMORY_WORKING_SNAPSHOT_MAX_BYTES` | `65536` | 超过则不写 |
| `MEMORY_HISTORY_LIMIT` | `20` | L0 最近消息条数 |
| `MEMORY_BUDGET_RATIO` | `{"turn":0.45,"fact":0.15,"artifact":0.15,"ltm":0.15,"tool":0.05}` | L1 预算分配 |
| `REME_BASE_URL` | `http://127.0.0.1:2333` | ReMe 服务地址 |
| `REME_MODE` | `http` | `http`（P0）；`embedded`（P2） |
| `REME_TIMEOUT_MS` | `5000` | |
| `REME_SEARCH_LIMIT` | `20` | 过召回上限 |
| `REME_MIN_SCORE` | `0.0` | |
| `REME_TENANT_ISOLATION` | `path` | `path`（共享 workspace + 前缀） |
| `REME_AUTO_MEMORY_ENABLED` | `false` | P2：LLM 提炼 |
| `REME_AUTO_DREAM_ENABLED` | `false` | P2：daily → digest 沉淀 |
| `REME_WORKSPACE_ROOT` | `/data/reme` | P2 embedded 模式用 |

> `MEM0_*`（`config/_mem0.py`）**全部保留**，Mem0 opt-in 时继续生效。
>
> **开关优先级（消歧）**：`MEMORY_LTM_ENABLED=false` 为总开关，关闭时任何 provider 都不读写；
> provider=`mem0` 时还需 `MEM0_ENABLED=true`（沿用既有语义），两者为**与**关系；
> provider=`reme` 时 `MEM0_ENABLED` 被忽略。

部署：ReMe 容器加入 `docker-compose.dev.yml`（独立 profile），启动参数
`reme start service.host=0.0.0.0 service.jobs=[search,read,write,traverse]`，**仅内网暴露**；workspace 目录挂卷持久化。

---

## 9. 与现有代码的集成点

| # | 位置 | 改动 |
|---|---|---|
| 1 | `routers/ai/ai_agent.py:174-180` | 读取侧：`build_cross_mode_brief` → `MemoryService.recall(...).to_brief()`（带预算与来源可追溯，修 G8） |
| 2 | `routers/ai/ai_agent.py:209-245` | 写入侧：`finalize_chat_stream` **签名不变**，内部 L3 改异步 provider + 真实 id（修 G3） |
| 3 | `ai/services/cross_mode_recorder.py:47` | `STRATEGY_TABLE` 迁至 `memory/policies.py`，本模块 re-export；`FinalizeStrategy.write_mem0` 更名 `write_ltm`（保留 `write_mem0` 属性别名一个版本） |
| 4 | `ai/context_manager.py` | 薄壳化；`persist_l2_context` / `sync_to_long_term` / `get_context_with_mode_filter` / `compact_context` 委托，**旧签名保留** |
| 5 | `routers/ai/ai_context.py:227/277/378` | 因 #4 保持签名，**无需改动** |
| 6 | `services/auto_compaction_scheduler.py:238` | 同上无需改动；清理任务后续扩展 `memory_kind` 维度（P2） |
| 7 | `config/_mem0.py` + `config/__init__.py` | `_mem0.py` 原样；`Settings` 继承链加 `MemorySettings` |
| 8 | `models/ai/ai_chat_context_storage.py`、`models/ai/ai_session_finalize_log.py` | +3 列 / +1 列 + 新索引 + 新迁移 |
| 9 | `ai/memory/reme_middleware.py` | `UserMemoryManager`(Graphiti) **不动**（非 L3）；文件内 ReMe TODO 注释改为指向新 provider |
| 10 | `ai/services/memory_service.py` | `LongTermMemoryService`(InMemory) 标记 deprecated，保留给旧调用方 |
| 11 | `docker-compose.dev.yml`、`.env.example` | ReMe 服务（可选 profile）+ 新增配置项 |
| 12 | 前端 `api/aiContext.ts`、`stores/contexts.ts` | P2：provider 健康 / 记忆统计接口 |

---

## 10. 关键流程

### A. 请求进入（recall）

1. `MemoryService.recall(session, mode, user_input, model)`
2. Redis `GET gen` + `GET snapshot`（2 次 GET）→ 命中且 `gen` 一致 → `from_cache=True`
3. 未命中 → 装配：L0 最近 N 条 → L2（`tenant+session+memory_kind+未过期(+跨模式可见)+tags`）→ L3 `provider.recall(top_k)` + 后置过滤
4. `WorkingMemoryBuilder` 按 `safe_input_budget` 分配 + 固定裁剪序裁剪
5. 回写快照（≤64 KiB，TTL 1800s）
6. 输出 `to_messages()` / `to_brief()` 注入 AgentScope
7. **全程异常 → 降级为"仅 L0 最近 N 条"，绝不失败请求**

### B. SSE 收尾（capture）

1. `StreamAnswerCollector.answer` → `finalize_chat_stream`（`ai_agent.py:238`）
2. 查 `memory/policies.py` 策略 → `extract_payload` / `extract_summary`
3. `SessionMemoryStore.put()` 落 L2（v1 schema，`memory_kind` / `token_estimate` / `run_id`）→ `INCR gen`
4. 策略 `write_ltm` 为真 → 提交异步任务 `provider.capture(draft)`（**不阻塞 SSE**）→ 完成后再 `INCR gen`
5. `_write_audit` 写 `ai_session_finalize_log`：真实 `{provider}:{id}` + `ltm_provider`
6. 任一步失败 → `logger.warning`，SSE 不受影响

### C. 生命周期与运维

- **TTL**：`auto_compaction_scheduler` 现有清理任务（P2 扩展 `memory_kind`）
- **快照**：TTL 自然过期 + 写操作 `INCR gen`；不主动删除
- **健康**：`provider.health()` 供运维接口（P2）；失败计数进审计日志
- **备份**：ReMe workspace 目录挂卷，直接文件级备份（Memory as File 的固有优势）

---

## 11. 可配置性 / 可扩展性 / 可落地性

| 维度 | 落地方式 |
|---|---|
| 可配置 | L3 后端、top_k、超时、预算比例、快照 TTL/上限、L0 条数全部环境变量化；分模式策略集中在 `memory/policies.py` |
| 可扩展 | `LongTermMemoryProvider` Protocol + 注册表：新增后端 = 实现接口 + 注册一行；`MemoryScope` 承载作用域，provider 无状态 |
| 可落地 | P0 全部为**存量文件内改造 + 新增独立包**，不改既有 API 契约（`finalize_chat_stream` / `ContextManager` 签名保持）；`ENABLE_CROSS_MODE_RECORDER` 现有开关继续守护灰度 |

---

## 12. 测试与验收

| 主张 | 证据 | 负向用例 |
|---|---|---|
| Redis 不可用时 L1 仍正确 | unit：mock redis 抛异常 → 全量重建且 items 正确 | 快照 `gen` 不一致时必须重建（不可返回旧内容） |
| L1 裁剪守预算 | unit：构造超预算输入 → `sum(tokens) <= budget`，`system/pinned` 不被裁 | 裁剪序违反（先裁 tool）时断言失败 |
| L2 v1/v0 兼容 | unit：v0 记录可被 v1 读取路径解析，`summary` 按 `_ANSWER_KEYS` 抽取 | 缺 `schema_version` 不报错 |
| provider 切换不改业务 | unit：factory 返回 reme/mem0/none 三态，`facade` 行为一致 | 未注册 provider 名 → 启动期显式失败（不静默用 none） |
| ReMe 租户隔离 | 集成（fake HTTP）：A 租户召回结果不含 B 租户 path | 路径前缀不匹配的 chunk 必须被过滤 |
| Mem0 返回真实 id | 集成（fake HTTP）：`mem0_memory_id` 等于服务端返回值 | 伪造 `mem_{u}_{s}` 时断言失败 |
| 后端不可用不阻断 SSE | 集成：provider 抛异常 → SSE 正常结束，`ai_session_finalize_log` 记录 `ltm_synced=false` | `FAIL_OPEN=false` 时按配置显式失败 |
| 既有测试不退化 | `cd backend && pytest tests/unit tests/integration` | — |

---

## 13. 落地顺序

- **P0**：`types.py` / `budget.py` / `policies.py` / `ltm/{base,factory,reme_provider,mem0_provider,null_provider}.py` / `config/_memory.py`；`ContextManager` 薄壳化（修 G2/G3/G4/G5）
- **P1**：`session_store.py` / `working.py` / `working_cache.py` + 迁移 + `ai_agent.py` 双侧接线 + ReMe 容器（修 G1/G7/G8）
- **P2**：`auto_memory` / `auto_dream`、embedded 模式、L2 pgvector 语义检索、前端健康与统计接口

---

## 14. 已知后果、风险与「不做的事」

**后果**

1. 默认 ReMe 且 `auto_memory` 关闭时，L3 **不做 LLM 事实抽取**——写入即 Markdown 直写，检索为 BM25（+可选向量）。换来"默认 provider 不强依赖 LLM"，代价是记忆粒度粗于 Mem0。
2. 已写入 Mem0 的存量记忆**不会自动迁移**到 ReMe；切换即视为新后端（迁移脚本属 P2，本期不做）。
3. L2 `context_key` 仍含毫秒时间戳（保留兼容），幂等性由 `memory_kind + run_id` 承担，唯一键不变。

**风险**

| 风险 | 缓解 |
|---|---|
| ReMe BM25 中文分词质量未知 | 启用 embedding（`file_store.default.embedding_store=default` + `reindex scope=embedding`）；验收需实测中文召回 |
| ReMe 服务无鉴权 | 仅内网 + `service.jobs` 白名单 + 反向代理 |
| `workspace_dir` 不支持按请求传入 | 路径前缀约定（已确认方案）；若未来要求物理隔离，改 `REME_TENANT_ISOLATION=workspace` 起多实例 |
| L1 快照陈旧 | `gen` 失效 + TTL 30min + 快照仅缓存 |
| 同步 Redis 客户端在 async 链路 | 仅 GET/SET/INCR（亚毫秒）；若实测成为瓶颈再换 `redis.asyncio` |

**明确不做**

- L2 向量检索、ReMe embedded 模式、`auto_memory` / `auto_dream`（均 P2）
- 跨后端记忆迁移工具
- Graphiti（`UserMemoryManager` / `graphiti_memory.py`）并入 L3 —— 另案
- 自动回退到另一个 L3 后端
- L1 快照跨会话共享（key 含 `session_id`）

---

## 15. 关联文档

- `docs/superpowers/specs/2026-09-29-context-memory-consolidated-design.md`（上下文/跨模式继承；路径部分已过时，见 §0）
- `backend/app/core/context_policies.py`、`backend/app/ai/services/cross_mode_recorder.py`（策略源）
- `backend/app/constants/llm_tokens.py`（预算常量）
- ReMe 官方文档：`https://reme.agentscope.io/zh/services`、`/zh/memory_search`、`/zh/auto_memory`

---

---

## 16. 实现进展（2026-09-29 落地，分支 `feat/memory-short-long-term`）

> 本节记录截至 2026-09-29 的实际落地情况，与 §4 / §9 / §13 对照。提交哈希来自本分支 git 历史。

### 16.1 已完成（P0 + P1 主体）

**新建包 `app/ai/memory/`（§4 全部模块）**

| 模块 | 对应设计 | 提交 |
|---|---|---|
| `types.py` | L1/L3 统一数据结构、`WORKING_KINDS`、裁剪序 | `008c7fe` |
| `budget.py` | 统一 token 估算 + 比例分配（修 G2） | `48e3812` |
| `policies.py` | `STRATEGY_TABLE` 单一事实源（消除双策略源） | `cc7db86` |
| `working.py` | L1 装配器：比例预算 + 固定裁剪序 + system/pinned 豁免 | `3e56223` |
| `working_cache.py` | L1 Redis 快照：gen 失效 + 体积上限 + 宕机静默降级 | `1a31f81` |
| `session_store.py` | L2 v1 schema 写入 + v0 兼容解析 + 跨模式过滤 | `9d5d0c7` |
| `ltm/base.py` + `null_provider.py` | `LongTermMemoryProvider` Protocol（async）+ 兜底 | `5b38350` |
| `ltm/reme_provider.py` | ReMe HTTP Job API（**默认 L3 后端**） | `146b962` |
| `ltm/mem0_provider.py` | Mem0 异步 + 真实 memory id + 租户后置过滤（修 G3） | `7b66e7a` |
| `ltm/factory.py` | 注册表 + 60s 缓存 + 未注册 fail-closed（修 G4/G5） | `3527dd2` |
| `facade.py` | `MemoryService.recall/capture`，上层唯一入口 | `2f2e65a` |

**改造（§4 改造项）**

- `ai/context_manager.py` 薄壳化（`persist_l2_context` / `sync_to_long_term` / `get_context_with_mode_filter` / `compact_context` 委托 store/facade，旧签名保留）— `b57baad`
- `ai/services/cross_mode_recorder.py`：`STRATEGY_TABLE` 迁至 `memory/policies.py` 并 re-export；`write_mem0` 更名 `write_ltm`（保留别名）— `cc7db86`
- `config/_memory.py` 新增 `MemorySettings`（`MEMORY_*` + `REME_*`）并注册进 `Settings`；`config/_mem0.py` 原样保留 — `102e962`
- `models/ai/ai_chat_context_storage.py` +3 列（`memory_kind` / `token_estimate` / `run_id`）+ 新索引；`models/ai/ai_session_finalize_log.py` +1 列 `ltm_provider` — `46adb0c`（迁移 `2026_09_29_0001`）
- `ai/memory/reme_middleware.py`（`UserMemoryManager` / Graphiti）不动；`ai/services/memory_service.py` `LongTermMemoryService` 标记 deprecated — 符合 G5
- 部署：`docker-compose.dev.yml` 新增 `reme` 服务（独立 profile，仅内网）+ `.env.example` 新增 `MEMORY_LTM_*` / `REME_*` — `146b962`

**写入侧接线（§9 #2/#8、§6.1）**

- `routers/ai/ai_agent.py` `/chat/stream`：`finalize_chat_stream` 异步化为 `afinalize_chat_stream`，内部 await L3 `provider.capture` + 写真实 `{provider}:{id}` 审计（修 G3）— `617c6ce` / `c7cc94b`
- `routers/agent/agent_team.py` `/chat` 与 `/run`：按 `conversation_id` 复用/新建 `AiChatSession`（`AiChatSession.conversation_id` 列 + 迁移 `2026_09_29_0002`；`AiChatService.get_or_create_team_session`），再 `await afinalize_chat_stream` 写 L2+L3（真实 id）；`conversation_id` 缺失则 fail-open 跳过

**测试**：`test_cross_mode_afinalize.py`、`test_cross_mode_recorder.py`、`test_context_manager_delegation.py`、`test_team_cross_mode_memory.py`、`test_memory_facade.py`（含 L1 快照缓存隔离修复）

### 16.2 未完成的本设计功能

1. **读取侧 recall 未接线（P1 §9 #1，最高优先级缺口）**
   设计要求的读取入口 `build_cross_mode_brief → MemoryService.recall(...).to_brief()` 尚未落地：`routers/ai/ai_agent.py:170` 仍调用 **legacy** `build_cross_mode_brief`（内部走 `ContextManager.get_context_with_mode_filter`，仅 L2 legacy 读取）。
   结果：`MemoryService.recall`（L0+L2+L3 装配 + Redis 快照缓存 + 预算裁剪 + `to_brief` / `to_messages`）虽已实现，但在请求入口**未激活**——当前读取路径不享受 L1 Redis 缓存、跨模式 L3 召回与预算裁剪。
   处置：将 `ai_agent.py` 读取侧改为 `MemoryService.recall(...).to_brief()`（或 `to_messages()` 注入 AgentScope），并保留 legacy 行为作为降级；需回归既有跨模式注入用例（`tests/integration/test_cross_mode_*`）。

2. **P2 明确延后（设计 §13/§14 已标注"本期不做"）**
   - ReMe `auto_memory`（LLM 事实抽取，`REME_AUTO_MEMORY_ENABLED` 默认 false）
   - ReMe `auto_dream`（daily → digest 沉淀）
   - ReMe `embedded` 模式（`REME_MODE=embedded`）
   - L2 pgvector 语义检索（G6）
   - 前端 provider 健康 / 记忆统计接口（§9.8 / §12.2：`api/aiContext.ts` 尚未新增）

3. **设计明确不做（符合 G5）**：Graphiti / `UserMemoryManager` 并入 L3 —— 另案，未做。

### 16.3 关联文档 `2026-09-29-context-memory-consolidated-design.md` §14 缺口处置

| 缺口 | 状态 |
|---|---|
| #8 仅 `data.py` 写 L2 后 `sync_to_long_term`，其余模式无长期记忆沉淀 | ✅ 已缓解：新 `finalize_chat_stream`（ai_agent.py 统一入口）使经 `/chat/stream` 的所有模式（skill/agent/team/thinking/deep_research/research）写入侧均走 L3 provider |
| L3 硬编码 Mem0（§9.1） | ✅ 已解决：L3 抽象 + factory/providers，可切换 reme/mem0/none |
| #1 Dify"继承上文"开关无效 | ⚠️ 仍属 legacy 行为，与本设计读取路径无关 |
| #2 写入侧仅 skill/dify 可跨模式继承 | ⚠️ legacy `is_cross_mode_accessible` 标记仍在；新系统跨模式可见性由 `memory/policies.py` 决定，但 legacy L2 条目仍带旧标记，需逐步统一 |
| #3 `DEFAULT_ACCESS_MAP` 缺 skill/agent/team/thinking/deep_research 条目 | ⚠️ 属 legacy 白名单；新 `policies.py` 是 L3 capture 策略，非同一套，未合并 |
| #5 `vector_embedding` 未启用 | ⏸ 属 P2（见 16.2 #2） |
| #6 Mem0 本地回退重启即失 | ⚠️ 仍存（生产须配置 `MEM0_HOST`）；新 `none` provider 可作显式关闭 |
| #7 handler 硬编码 `ttl_hours` | ⚠️ 新 finalize 写入路径已采用策略 TTL；legacy handlers 是否仍硬编码需逐个核对 |
| #4 SQLBot 注入为纯 prompt 前缀 | ⚠️ 仍存（与 L3 抽象无关，属注入策略优化） |

---

**文档结束**
