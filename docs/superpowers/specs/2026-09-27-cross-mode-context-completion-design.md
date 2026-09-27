# MinWorkBuddy 9 种会话模式 × 跨模式上下文记忆设计方案

> **版本**: v1.0
> **日期**: 2026-09-27
> **状态**: ✅ Approved (brainstorming 已确认 6 个澄清问题 + 7 节设计)
> **作者**: Cursor Architecture Team
> **驱动需求**: MinWorkBuddy 9 种会话模式均参与跨模式上下文记忆(用户偏好 + 案件/工作空间上下文双维度)
> **参考资料**: risk_control 工程 `docs/superpowers/specs/2026-09-24-cross-mode-context-completion-design.md` 与对应实施计划 + 完成报告
> **设计模式**: brainstorming skill

---

## 1. 背景与目标

### 1.1 现状

MinWorkBuddy 现有 `AIChatContextStorage` 表(由 `2026-09-21` 三层架构设计引入)、`ContextManager`(纯内存三层合成)、`Mem0Service`(Mem0 + LocalMem0 兜底)、`compaction_audit_service`、`auto_compaction_scheduler`,前端已有 `ContextStatsDisplay` / `CompactButton` / `ManualOverrideModal` / `useContextStats` / `useContextCompaction`。**但**:

- **没有 `persist_l2_context()` 统一入口**(`grep` 验证 0 命中);
- **没有 `source_mode / context_tags / is_cross_mode_accessible / case_number` 这套 L2 元数据**;
- **没有 `PRIORITY_MAP` 跨模式策略常量**;
- 9 种会话模式(`general / react / thinking / deep_research / skill / agent / team / scheduled / shared`)在 SSE 收尾处均**未落 L2 + 同步 Mem0**,跨会话/跨模式上下文复用能力缺失;
- `AssistantPanel.vue` 的 `StatsCard` 展示的是通用 token 统计,**未与 9 种模式对应**;`CompactButton/ManualOverrideModal` 未挂载。

### 1.2 需求确认(6 项澄清)

| # | 澄清问题 | 回答 |
|---|----------|------|
| 1 | 「9 种会话模式」定义 | b. 对齐 MinWorkBuddy 现有 UI 8 种 + scheduled |
| 2 | 第 9 种模式 | a. scheduled 是第 9 种,**只记输入不写 Mem0** |
| 3 | 跨模式共享粒度 | a. **默认 `is_cross_mode_accessible=False`**,按需开启 |
| 4 | 前端改动范围 | **c-rich**:统计页 + 9 张模式卡片 + 历史抽屉全量方案 |
| 5 | 长期记忆后端 | **a-mem0-only**:统一 Mem0Service + LocalMem0 兜底 |
| 6 | 实施范围 | **方案 B**:CrossModeContextRecorder + 策略注册表 + 统一钩子 |

### 1.3 目标

实现 **9 种会话模式 × 跨模式上下文记忆**:

| 模式 | source_mode | priority | TTL(h) | 写 Mem0 | is_cross_mode_accessible |
|------|-------------|----------|--------|---------|---------------------------|
| 通用对话 | `general` | 3 | 168 | ✅ | false |
| ReAct 计划 | `react` | 3 | 168 | ✅ | false |
| 深度思考 | `thinking` | 4 | 168 | ✅ | false |
| 深度研究 | `deep_research` | 4 | 336 | ✅ | **true** |
| 技能执行 | `skill` | 2 | 168 | ✅ | false |
| 智能体 | `agent` | 2 | 720 | ✅ | **true** |
| 智能体团队 | `team` | 2 | 168 | ✅ | **true** |
| 云端调度 | `scheduled` | 4 | 720 | ❌ | false |
| 共享层 | `shared` | 5 | 168 | ❌ | false |

- **用户偏好维度(Mem0)**:8 种交互模式自动写长期记忆,新会话开始时按 session_type 自动注入;
- **案件/工作空间维度(L2)**:9 种模式都落 L2,按 `source_mode` + `case_number` 跨会话检索;
- **跨模式共享**:默认隔离,`deep_research / agent / team` 三种模式结果显式标记可被其他模式读取。

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       MinWorkBuddy 多模式会话上下文架构 v2                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  AssistantPanel (frontend)                                                   │
│        │                                                                     │
│        │  SSE done/finalize                                                  │
│        ▼                                                                     │
│  SSEBridge.finalize_session(session_type, payload)  ◄── 统一收尾点             │
│        │                                                                     │
│        │  按 session_type → strategy_id                                     │
│        ▼                                                                     │
│  CrossModeContextRecorder.record_finalize(strategy_id, payload)              │
│        │                                                                     │
│        │1) persist_l2_context(source_mode, ttl, priority, tags, …) │
│        │  2) sync_to_long_term(summary)   ── if Mem0Enabled                  │
│        │ 3) write_audit(...)                                                │
│        ▼                                                                     │
│  AIChatContextStorage (L2)  +  Mem0Service (Long-term)                      │
│        │                                                                     │
│        │  read: get_context_with_mode_filter(allow_cross_mode, tags, …)    │
│        ▼                                                                     │
│  CrossModeStatsPage (frontend) — 数据驱动 9 张模式卡                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 `AIChatContextStorage` 扩展字段

```sql
-- backend/app/db/migrations/versions/2026_09_27_add_cross_mode_context_fields.py
ALTER TABLE ai_context_storage
    ADD COLUMN IF NOT EXISTS source_mode           VARCHAR(32) NOT NULL DEFAULT 'shared',
    ADD COLUMN IF NOT EXISTS context_tags          JSONB       NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS is_cross_mode_accessible BOOLEAN  NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS case_number           VARCHAR(64)  NULL;

CREATE INDEX IF NOT EXISTS ix_ai_context_storage_source_mode
    ON ai_context_storage (tenant_id, session_id, source_mode);

CREATE INDEX IF NOT EXISTS ix_ai_context_storage_cross_mode
    ON ai_context_storage (tenant_id, source_mode, is_cross_mode_accessible)
    WHERE is_cross_mode_accessible = TRUE;

-- 数据回填:已有数据 source_mode 默认取 mode 字段
UPDATE ai_context_storage SET source_mode = mode WHERE source_mode = 'shared';
```

| 字段 | 类型 | 含义 | 默认 |
|------|------|------|------|
| `source_mode` | VARCHAR(32) | 业务来源模式,与 `session_type` 同值集合 | `'shared'` |
| `context_tags` | JSONB | 上下文标签列表 | `'[]'` |
| `is_cross_mode_accessible` | BOOL | 是否允许跨模式检索 | `False` |
| `case_number` | VARCHAR(64) | 案件/工作空间标识 | `NULL` |
| `expires_at` | TIMESTAMP | 已存在;按 TTL 写入 | `NULL` |

`mode` 字段保留(`general/skill/...`),与 `source_mode` 同步写入但语义略不同。**不破坏** 现有 `compaction_audit_service` 与 `auto_compaction_scheduler`。

### 3.2 新增 `ai_session_finalize_log` 表(审计 + 调试)

```sql
CREATE TABLE IF NOT EXISTS ai_session_finalize_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL,
    session_id      BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    session_type    VARCHAR(32) NOT NULL,
    source_mode     VARCHAR(32) NOT NULL,
    l2_record_id    BIGINT       NULL,
    mem0_synced     BOOLEAN      NOT NULL DEFAULT FALSE,
    mem0_memory_id  VARCHAR(64)  NULL,
    finalized_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    error_message   TEXT         NULL
);
CREATE INDEX ix_ai_session_finalize_log_session
    ON ai_session_finalize_log (tenant_id, session_id, finalized_at DESC);
```

---

## 4. 后端模块

### 4.1 `backend/app/core/context_policies.py`(新建,~80 行)

```python
"""9 种会话模式的跨模式上下文策略常量。与 risk_control 对齐。"""
from __future__ import annotations
from typing import Dict, List

PRIORITY_MAP: Dict[str, int] = {
    "general":       3,
    "react":         3,
    "thinking":      4,
    "deep_research": 4,
    "skill":         2,
    "agent":         2,
    "team":          2,
    "scheduled":     4,
    "shared":        5,
}

DEFAULT_TTL_HOURS: Dict[str, int] = {
    "general":       168,
    "react":         168,
    "thinking":      168,
    "deep_research": 336,
    "skill":         168,
    "agent":         720,
    "team":          168,
    "scheduled":     720,
    "shared":        168,
}

DEFAULT_PROTECTED_MODES: List[str] = ["agent", "team", "deep_research"]

MEM0_ENABLED_MODES: set[str] = {
    "general", "react", "thinking", "deep_research", "skill", "agent", "team",
}
```

### 4.2 `backend/app/ai/context_manager.py` 扩展 3 方法(~120 行新增)

在现有 `ContextManager` 上**追加**,**不动**现有 InMemory 三层合成:

```python
class ContextManager:
    # ... 现有 InMemory 实现保留 ...

    def persist_l2_context(
        self, session_id: int, source_mode: str, context_key: str,
        context_data: Dict[str, Any], priority: int = 5,
        ttl_hours: Optional[int] = None,
        is_cross_mode_accessible: bool = False,
        context_tags: Optional[List[str]] = None,
        case_number: Optional[str] = None,
        tenant_id: int = 1, user_id: int = 0,
    ) -> Optional[int]:
        """统一 L2 落库入口。失败静默,返回 record_id 或 None。"""

    def sync_to_long_term(
        self, session_id: int, user_id: int, summary: str,
        metadata: Optional[Dict[str, Any]] = None,
        source_mode: Optional[str] = None,
    ) -> Optional[str]:
        """同步到 Mem0。失败静默,返回 memory_id 或 None。"""

    def get_context_with_mode_filter(
        self, session_id: int, user_id: int,
        allow_cross_mode: bool = False,
        include_tags: Optional[List[str]] = None,
        source_mode: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """跨模式检索。allow_cross_mode=True 才读取 is_cross_mode_accessible=True 记录。"""
```

3 个方法签名与 risk_control 完全一致,便于迁移参考工程的集成测试。

### 4.3 `backend/app/ai/services/cross_mode_recorder.py`(新建,~180 行)

**9 模式"零侵入接入"的关键**。策略表 + 收尾触发器。

```python
@dataclass(frozen=True)
class FinalizeStrategy:
    session_type: str
    source_mode: str
    priority: int
    ttl_hours: int
    write_mem0: bool
    extract_payload: Callable[[Dict[str, Any]], Dict[str, Any]]
    extract_summary: Callable[[Dict[str, Any]], str]
    context_tags: Callable[[Dict[str, Any]], List[str]] = lambda p: []
    is_cross_mode_accessible: bool = False

STRATEGY_TABLE: Dict[str, FinalizeStrategy] = {
    "general":       FinalizeStrategy(...),
    "react":         FinalizeStrategy(...),
    "thinking":      FinalizeStrategy(...),
    "deep_research": FinalizeStrategy(..., is_cross_mode_accessible=True),
    "skill":         FinalizeStrategy(...),
    "agent":         FinalizeStrategy(..., is_cross_mode_accessible=True),
    "team":          FinalizeStrategy(..., is_cross_mode_accessible=True),
    "scheduled":     FinalizeStrategy(..., write_mem0=False),
    "shared":        FinalizeStrategy(..., write_mem0=False),
}


class CrossModeContextRecorder:
    def has_strategy(cls, session_type: str) -> bool: ...
    def record_finalize(
        self, session_id: int, user_id: int, tenant_id: int,
        session_type: str, payload: Dict[str, Any],
        case_number: Optional[str] = None,
    ) -> Optional[int]:
        """主入口:按 session_type 选择策略,执行 L2 + Mem0 + 审计。"""
```

---

## 5. 集成点

### 5.1 SSEBridge 集成(统一收尾点)

修改 `backend/app/ai/sse_bridge.py:finalize_session()`:

```python
def finalize_session(self, session_id: int, payload: Dict[str, Any]) -> None:
    """会话结束收尾:写 L2 + 同步 Mem0(策略驱动)"""
    session_type = payload.get("session_type", "shared")
    user_id      = payload.get("user_id", 0)
    tenant_id    = payload.get("tenant_id", 1)
    case_number  = payload.get("case_number")

    # 现有 SSE 清理逻辑保留
    self._do_existing_cleanup(session_id, payload)

    # 新增:跨模式上下文记录(策略驱动 + Feature flag)
    if not settings.ENABLE_CROSS_MODE_RECORDER:
        return
    if not CrossModeContextRecorder.has_strategy(session_type):
        return
    recorder = CrossModeContextRecorder(self.db)
    recorder.record_finalize(
        session_id=session_id, user_id=user_id, tenant_id=tenant_id,
        session_type=session_type, payload=payload, case_number=case_number,
    )
```

### 5.2 Handler 适配(零侵入)

现有 handler 在调用 SSEBridge `finalize_session()` 时需在 payload 中传 `session_type + user_id + tenant_id`;**新字段**(如 `answer / thinking_steps / sql / result / execution_id` 等)**缺失时由 `extract_payload` 的 `p.get()` 兜底**,老 handler 不会崩。

| session_type | 现有调用方 | payload 必备字段 |
|--------------|------------|------------------|
| `general` | `routers/ai/ai_chat.py` | user_input, answer, tool_calls |
| `react` | `routers/ai/react.py` | + plan_steps |
| `thinking` | thinking agent | + thinking_steps, final_answer |
| `deep_research` | `ResearchOrchestrator.run()` | + sub_questions, sources, final_report |
| `skill` | `SkillExecutionService.execute()` | + skill_name, skill_display_name, execution_id, result |
| `agent` | `ai_agent.py` | + agent_name, tool_calls_count, execution_id |
| `team` | `TeamManager.run_team()` | + team_name, member_count, speech_count |
| `scheduled` | Celery 提交任务 | + task_id, task_no, target_mode, priority |
| `shared` | 兜底 | data |

### 5.3 `routers/ai/ai_context.py` 扩展 3 路由

```python
POST /api/v1/ai/context/entries         # 跨模式条目检索
POST /api/v1/ai/context/breakdown       # 按 source_mode 聚合
GET  /api/v1/ai/context/strategies      # 列出 9 种策略(给前端驱动卡片)
```

---

## 6. 前端模块(全量方案 c-rich)

### 6.1 新增/扩展文件

| 文件 | 类型 | 职责 |
|------|------|------|
| `frontend/src/api/aiContext.ts` | 扩展 | + `getContextEntries / getCrossModeBreakdown / listFinalizeStrategies` |
| `frontend/src/hooks/useCrossModeStats.ts` | 新建 | 9 模式策略 + breakdown + 按模式 entries |
| `frontend/src/components/context/ModeContextCard.vue` | 新建 | 数据驱动单模式卡 |
| `frontend/src/components/context/ContextHistoryList.vue` | 新建 | 通用历史列表 |
| `frontend/src/views/context/CrossModeStatsPage.vue` | 新建 | 统计页 + 9 张模式卡 + 历史抽屉 |
| `frontend/src/views/assistant/components/AssistantPanel.vue` | 扩展 | 挂载"跨模式上下文"按钮 |

### 6.2 `ModeContextCard.vue` 数据驱动

接收 props:`{ strategy: FinalizeStrategy, bucket?: ContextBreakdownBucket }`;emit `view-history / enable-cross`。**9 张卡复用同一组件,只换 props**。

### 6.3 `useCrossModeStats` Hook

封装 `loadStrategies / loadBreakdown / loadEntriesByMode`,跨页面复用。

### 6.4 `AssistantPanel.vue` 集成

在 `chat-main-header` "我的异步任务" 按钮旁新增 "跨模式上下文" 按钮,点击弹出 `CrossModeStatsPage`(`a-modal` 内嵌,避免改路由)。

### 6.5 复用现有组件

`useContextStats / useContextCompaction / ContextStatsDisplay / CompactButton / ManualOverrideModal` 全部复用,**不重写**。

---

## 7. 错误处理与降级

| 失败点 | 行为 | 是否阻断 SSE |
|--------|------|--------------|
| `persist_l2_context` 失败 | `logger.warning`,`record_finalize` 返回 None | 否 |
| `sync_to_long_term` 失败(Mem0 不可达) | `logger.warning`,`mem0_id=None` | 否 |
| 审计日志写失败 | `logger.warning`,不抛 | 否 |
| `get_context_with_mode_filter` 失败 | 路由层返回 `[]` + HTTP 200 | 否 |
| `STRATEGY_TABLE` 缺失 session_type | `has_strategy()` 返回 False,recorder 跳过 | 否 |
| handler 未传新字段 | `extract_payload` 用 `p.get()` 兜底 | 否 |
| 迁移脚本失败 | alembic 升级失败 → 部署阻断 | 是 |
| `context_tags` 非 JSON 类型 | 序列化前类型检查 → 兜底 `[]` | 否 |

**核心契约**:recorder 内部所有异常**全部 try/except + logger.warning**,绝不向上抛。SSE 主流程**绝不依赖** L2/Mem0 的可用性。

---

## 8. 测试策略

### 8.1 单元测试(5 文件)

```
backend/tests/unit/
├── test_context_policies.py                  # 策略常量完整性
├── test_persist_l2_context.py                # 写库 + 失败静默
├── test_sync_to_long_term.py                 # Mem0 调用 + 失败降级
├── test_get_context_with_mode_filter.py      # 4 个过滤组合
└── test_cross_mode_recorder.py               # STRATEGY_TABLE 9模式 + record_finalize
```

### 8.2 集成测试(2 文件)

```
backend/tests/integration/
├── test_cross_mode_end_to_end.py             # SSE → finalize → L2 → Mem0 → 检索
└── test_cross_mode_frontend_api.py           # /entries /breakdown /strategies
```

### 8.3 关键测试用例

- `test_all_nine_modes_have_strategy`:9 种 session_type 全部 in `STRATEGY_TABLE`
- `test_scheduled_does_not_write_mem0`:`scheduled.write_mem0 is False`
- `test_deep_research_is_cross_mode_accessible`:`deep_research.is_cross_mode_accessible is True`
- `test_persist_l2_writes_to_ai_context_storage`:落库字段正确
- `test_persist_l2_silent_on_failure`:异常被吞,不抛
- `test_get_context_with_mode_filter_cross_mode`:`allow_cross_mode=True` 才能读到 `is_cross_mode_accessible=True` 记录

### 8.4 性能预算

| 操作 | 预算 |
|------|------|
| `record_finalize` 调用 | < 200ms |
| `get_context_with_mode_filter` 50 条 | < 100ms |
| `get_cross_mode_breakdown` GROUP BY | < 50ms |
| 9 模式卡渲染 | < 100ms |

---

## 9. 实施顺序(10 步,~24h)

| Step | 任务 | 工时 | 验收 | Commit 前缀 |
|------|------|------|------|-------------|
| 1 | 迁移:扩展 `ai_context_storage` 4字段 + 新建 `ai_session_finalize_log` | 1h | `alembic upgrade head` 成功 | `feat(db): add cross-mode context fields + finalize log` |
| 2 | `core/context_policies.py` 策略常量 | 0.5h | import 通过 | `feat(policies): cross-mode strategy constants` |
| 3 | `ContextManager` 扩展 3 方法 | 3h | 3 个单测 PASS | `feat(context-mgr): cross-mode persist + sync + filter` |
| 4 | `services/cross_mode_recorder.py` + STRATEGY_TABLE | 2h | 9 模式 has_strategy 全 True | `feat(recorder): strategy-driven cross-mode recorder` |
| 5 | `sse_bridge.py:finalize_session` 接入 recorder | 1h | finalize 后 L2 落库 | `feat(sse-bridge): invoke recorder on finalize` |
| 6 | `routers/ai/ai_context.py` 新增 3 路由 | 1h | curl 三路由 200 | `feat(context-api): entries + breakdown + strategies` |
| 7 | Feature flag `ENABLE_CROSS_MODE_RECORDER` | 0.5h | False 时跳过 recorder | `feat(flag): enable_cross_mode_recorder toggle` |
| 8 | 前端 5 文件:api + hook + 2 组件 + 统计页 | 10h | 9 卡数据驱动渲染 + 抽屉可开 | `feat(frontend): cross-mode stats page + 9 mode cards` |
| 9 | `AssistantPanel.vue` 挂载按钮 | 1h | 点击按钮弹出统计页 | `feat(panel): cross-mode stats launcher` |
| 10 | 测试:5 单元 + 2 集成 + 性能 | 4h | 全 PASS,p95 < 300ms | `test(cross-mode): unit + integration + perf` |
| **总计** | | **24h** | | |

**额外**:评审 + 微调 2h,完成报告 1h → **总约 27h**。

### 9.1 PR 拆分建议

- **PR-1**(Step 1-5):后端基础设施 + 9 模式接入,~7h
- **PR-2**(Step 6-7):API + Feature flag,~1.5h
- **PR-3**(Step 8-10):前端 + 测试,~15h

---

## 10. 回滚方案

| 层级 | 回滚操作 |
|------|----------|
| Feature flag | `ENABLE_CROSS_MODE_RECORDER=false` → SSEBridge.finalize_session 跳过 recorder |
| 数据库迁移 | Alembic `downgrade()` 已写;**字段添加无破坏性** |
| 前端 | 删除 `views/context/CrossModeStatsPage.vue` 即可,API 路由不依赖前端 |
| 后端 | 删除 `services/cross_mode_recorder.py` + 回滚 `sse_bridge.py` 改动 |

---

## 11. 与 risk_control 一致性

| 项 | risk_control | MinWorkBuddy | 一致性 |
|----|--------------|--------------|--------|
| `source_mode` 枚举 | 9 种 | 9 种 | ✅ 名称与语义一致 |
| `persist_l2_context / sync_to_long_term / get_context_with_mode_filter` | 已实现 | 计划新增 | ✅ 签名一致 |
| `context_policies.py:PRIORITY_MAP` | 已实现 | 计划新增 | ✅ 4 共有模式(general/sqlbot/skill/scheduled)值一致;其余按业务设 |
| 默认 `is_cross_mode_accessible=False` | true | true | ✅ |
| `scheduled` 不写 Mem0 | true | true | ✅ |
| 失败静默降级 | true | true | ✅ |

**借鉴价值**:risk_control 集成测试思路、SQLBotStatsCard 设计稿可直接参考。

---

## 12. 附录

### A. 关键代码定位

| 主题 | 路径 |
|------|------|
| 策略常量 | `backend/app/core/context_policies.py` |
| L2 统一入口 | `backend/app/ai/context_manager.py:persist_l2_context` |
| Mem0 统一入口 | `backend/app/ai/context_manager.py:sync_to_long_term` |
| 跨模式检索 | `backend/app/ai/context_manager.py:get_context_with_mode_filter` |
| 9 模式策略表 | `backend/app/ai/services/cross_mode_recorder.py:STRATEGY_TABLE` |
| SSE 收尾钩子 | `backend/app/ai/sse_bridge.py:finalize_session` |
| 跨模式 API | `backend/app/routers/ai/ai_context.py:/entries /breakdown /strategies` |
| 前端统计页 | `frontend/src/views/context/CrossModeStatsPage.vue` |
| 前端模式卡 | `frontend/src/components/context/ModeContextCard.vue` |
| 前端 Hook | `frontend/src/hooks/useCrossModeStats.ts` |

### B. 关联文档

- MinWorkBuddy 三层架构设计:`docs/superpowers/specs/2026-09-21-multi-mode-session-context-architecture-design.md`
- MinWorkBuddy Phase 1-3 实施总结:`Phase1_Phase2_Phase3_Complete_Summary.md`
- 参考设计:`docs/superpowers/specs/2026-09-24-cross-mode-context-completion-design.md`(risk_control)
- 参考实施计划:`docs/superpowers/plans/2026-09-24-cross-mode-context-completion.md`
- 参考完成报告:`docs/sessions/cross-mode-context-completion-completed.md`

### C. 修订历史

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v0.1 | 2026-09-27 | 初始草案 |
| v1.0 | 2026-09-27 | 完整版定稿(brainstorming 6 项澄清 + 7 节设计确认通过) |

---

**文档结束**
**下一步**:invoke `writing-plans` skill 生成详细实施计划