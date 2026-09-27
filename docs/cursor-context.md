# 9 种会话模式 × 跨模式上下文记忆 — 索引文档

> **本文档定位:** 索引入口。完整设计在 spec,完整实施步骤在 plan,完整提交链在 git log。
> 任何修改请优先查阅本文档 → spec → plan → commit,而不是直接猜测。

---

## 1. 任务一句话描述

为 MinWorkBuddy 实现 **9 种会话模式** (`general / react / thinking / deep_research / skill / agent / team / scheduled / shared`) 的 **L2 短期记忆 + 本地私有化 Mem0 永久记忆** 双层基础设施,达成 **跨模式 + 跨会话** 的上下文复用能力。

| 维度 | 内容 |
|------|------|
| 项目 | MinWorkBuddy |
| 模式数 | 9 (general/react/thinking/deep_research/skill/agent/team/scheduled/shared) |
| 记忆层 | L2 短期 (`AIChatContextStorage` JSONB) + Mem0 永久 (本地私有化部署) |
| 跨模式可读 | 默认 False;`deep_research / agent / team` 三模式 True |
| 集成点 | `sse_bridge.py:finalize_session`(SSE 会话收尾点零侵入接入) |
| 入口页 | `CrossModeStatsPage.vue`(`AssistantPanel.vue` 挂载入口按钮) |
| 子代理 PR | 3 个 (后端基建 / API / 前端) |
| 总 commit | 18 (实施) + 3 (设计/计划) = 21 commits |

---

## 2. 三份根文档

| 类型 | 路径 | 角色 | 状态 |
|------|------|------|------|
| 设计方案 v1.0 | [`docs/superpowers/specs/2026-09-27-cross-mode-context-completion-design.md`](./superpowers/specs/2026-09-27-cross-mode-context-completion-design.md) | 背景、目标、架构图、数据模型、模块划分、错误降级、测试策略、实施顺序 | ✅ 已 commit (`04d7232`) |
| 设计方案 v1.1 | 同上 | 追加 **Mem0 本地私有化永久记忆约束** | ✅ 已 commit (`7e89c52`) |
| 实施计划 | [`docs/superpowers/plans/2026-09-27-cross-mode-context-completion.md`](./superpowers/plans/2026-09-27-cross-mode-context-completion.md) | 18 个 Task 步骤 + 每个 Task 的代码片段 + Acceptance + TDD 测试代码 | ✅ 已 commit (`292225a`) |

---

## 3. 18 个 Task 与 commit 对照表

### PR-1:后端基础设施(Task 1-7)→ 7 commits

| Task | 标题 | commit | 主要变更 |
|------|------|--------|---------|
| 1 | DB 迁移:4 字段 + `ai_session_finalize_log` 表 | `0f10e3f` | Alembic 迁移 + 2 个 ORM 模型 |
| 2 | `context_policies.py` 9 模式策略常量 | `47a9508` | `PRIORITY_MAP / DEFAULT_TTL_HOURS / DEFAULT_PROTECTED_MODES / MEM0_ENABLED_MODES` |
| 3-5 | `ContextManager` 三方法扩展 | `1643f6f` | `persist_l2_context / sync_to_long_term / get_context_with_mode_filter` |
| 5/7 | `CrossModeHealthService` 周报指标 | `ac59ada` | finalize 健康度审计 |
| 7 | `AutoCompactionScheduler` 周报接入 | `20f26ab` | weekly_report 含 finalize 健康度 |
| 7 | `ENABLE_CROSS_MODE_RECORDER` 功能开关 | `e4e66d7` | settings + CrossModeRecorder 守护 |
| 7 | `lifespan` 启动/关闭接入 | `1933efe` | AutoCompactionScheduler 启停 |

### PR-2:API 端点(Task 8)→ 1 commit

| Task | 标题 | commit | 主要变更 |
|------|------|--------|---------|
| 8 | `ai_context.py` 3 路由 | `552cafc` | `POST /entries`、`POST /breakdown`、`GET /strategies` |

### PR-3:前端(Task 9-18)→ 10 commits

> 注:plan 中编号为 Task 9-18,提交消息与实际 Task 内容按 plan 内部编号 9-18 标记,但实际实施顺序与 plan 的 Task 9-18 表对应关系略有调整(均落在 10 个 PR-3 commit 内)。

| plan Task | 标题 | commit | 主要变更 |
|-----------|------|--------|---------|
| 9 | Pinia contexts store | `25209eb` | `stores/contexts.ts`(9 模式状态管理) |
| 10 | API 客户端层扩展 | `7289499` | `aiContext.ts` 3 端点 + 4 类型补全 |
| 11 | `useCrossModeStats` composable | `5a9f174` | 9 模式统计钩子 |
| 12 | `useContextCompaction` composable | `fc84d76` | 跨模式压缩钩子 |
| 13 | `ModeContextCard.vue` | `fb8c3f7` | 数据驱动单模式卡(9 模式共用) |
| 14 | `ContextHistoryList.vue` | `a0e5d56` | 通用历史条目列表 |
| 15 | `CompactButton` + `ContextStatsDisplay` | `88dda85` | Element Plus → Ant Design Vue 升级 |
| 16 | `ManualOverrideModal` | `97118da` | 9 模式手动策略覆写 |
| 17 | `CrossModeStatsPage.vue` | `e88cf41` | 9 模式统计页 + 历史抽屉 |
| 18 | `AssistantPanel.vue` 集成 | `5020802` | 挂载"跨模式上下文"按钮 + 弹窗 |

完整提交链:

```text
04d7232 docs(spec): v1.0 设计方案
7e89c52 docs(spec): v1.1 - 追加 Mem0 本地私有化永久记忆约束
292225a docs(plan): 实施计划(18 Task)
───────────────── PR-1 后端基础设施 ─────────────────
0f10e3f Task 1: DB migration + 2 ORM
47a9508 Task 2: 9-mode policies
1643f6f Task 3-6: recorder / sync / persist
ac59ada Task 5/7: health service weekly
20f26ab Task 7: scheduler weekly hookup
e4e66d7 feature flag + recorder 守护
1933efe Task 7: lifespan 接入
───────────────── PR-2 API 端点 ─────────────────
552cafc Task 8: entries + breakdown + strategies
───────────────── PR-3 前端 ─────────────────
25209eb Task  9 contexts store
7289499 Task 10 API + types
5a9f174 Task 11 useCrossModeStats
fc84d76 Task 12 useContextCompaction
fb8c3f7 Task 13 ModeContextCard
a0e5d56 Task 14 ContextHistoryList
88dda85 Task 15 CompactButton + ContextStatsDisplay
97118da Task 16 ManualOverrideModal
e88cf41 Task 17 CrossModeStatsPage
5020802 Task 18 AssistantPanel 集成
```

---

## 4. 核心约束(实施前必读)

摘自 `plans/2026-09-27-cross-mode-context-completion.md:Global Constraints`,**所有 PR 均需遵守**:

1. **Mem0 部署形态** — 本地私有化、**永久记忆**(`LocalMem0APIImpl` HTTP 主路径,`LocalMem0Impl` InMemory 仅 fallback;fallback 时 `logger.warning`)
2. **Mem0 摘要截断** — `extract_summary` 默认 **2000 字符**(本地无 token 成本约束,比 risk_control 1000 字符更长,保证完整语义)
3. **失败静默降级** — `persist_l2_context` 失败 `logger.warning`;`sync_to_long_term` 失败 `logger.error`(永久记忆健康度告警);审计日志失败 `logger.warning`;**全部 try/except 不阻断 SSE 主流程**
4. **`is_cross_mode_accessible` 默认 False**;仅 `deep_research / agent / team` 显式 True
5. **`scheduled` 不写 Mem0** — `write_mem0=False`(只记输入不写永久记忆,沿用风险控制语义)
6. **Decimal 精度** — 金额用 `Decimal`,禁止 `float`
7. **TypeScript 严格模式** — 前端接口必须显式声明,禁止隐式 `any`
8. **Commit 粒度** — 每个 Task 立即 commit,Conventional Commits
9. **不引入新依赖** — 仅复用 loguru / sqlalchemy / pydantic / alembic / apscheduler / vue / ant-design-vue
10. **Feature flag** — `settings.ENABLE_CROSS_MODE_RECORDER`(默认 True),False 时 `sse_bridge.finalize_session` 跳过 recorder

---

## 5. 关键架构要点

### 后端分层

```text
SSE 主流程 (sse_bridge.finalize_session)
  ├─ Feature flag 守护 (ENABLE_CROSS_MODE_RECORDER)
  └─ CrossModeContextRecorder.record_finalize()
        ├─ strategy = STRATEGY_TABLE[session_mode]   ← 9 模式策略注册表
        ├─ ContextManager.persist_l2_context()       ← L2 短期 (DB)
        ├─ ContextManager.sync_to_long_term()        ← Mem0 永久 (本地)
        └─ CompactionAuditService.record()           ← ai_session_finalize_log
              └─ CrossModeHealthService (weekly_report)
                    └─ AutoCompactionScheduler.weekly_report()
```

### 前端数据流(数据驱动)

```text
GET /api/v1/ai/context/strategies
  ↓
stores/contexts.ts (Pinia)
  ↓
useCrossModeStats / useContextCompaction (composables)
  ↓
CrossModeStatsPage.vue
  ↓ v-for="strategy in (strategies.value || DEFAULT_STRATEGIES)"
ModeContextCard.vue  (单一组件,9 次复用)
  ├─ ContextHistoryList.vue  (抽屉)
  ├─ CompactButton.vue + ContextStatsDisplay.vue
  └─ ManualOverrideModal.vue
```

### 9 模式策略表(`STRATEGY_TABLE`)

```python
{
    "general":      {priority: 1, ttl: 24,  protected: False, mem0: True,  cross_mode_accessible: False},
    "react":        {priority: 2, ttl: 24,  protected: False, mem0: True,  cross_mode_accessible: False},
    "thinking":     {priority: 3, ttl: 24,  protected: True,  mem0: True,  cross_mode_accessible: False},
    "deep_research":{priority: 4, ttl: 72,  protected: True,  mem0: True,  cross_mode_accessible: True},
    "skill":        {priority: 5, ttl: 48,  protected: False, mem0: True,  cross_mode_accessible: False},
    "agent":        {priority: 6, ttl: 168, protected: True,  mem0: True,  cross_mode_accessible: True},
    "team":         {priority: 7, ttl: 168, protected: True,  mem0: True,  cross_mode_accessible: True},
    "scheduled":    {priority: 8, ttl: 24,  protected: False, mem0: False, cross_mode_accessible: False},
    "shared":       {priority: 9, ttl: 168, protected: True,  mem0: True,  cross_mode_accessible: True},
}
```

> 完整字段定义见 [`backend/app/core/context_policies.py`](../../backend/app/core/context_policies.py)。

---

## 6. 数据模型

### `ai_context_storage` 新增 4 字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `is_cross_mode_accessible` | BOOL | False | 是否可被其它模式读取 |
| `cross_mode_source` | VARCHAR(64) | NULL | 产生该条目的源模式(`general/react/...`) |
| `cross_mode_tags` | JSONB | `[]` | 跨模式标签,用于精准过滤 |
| `priority_score` | INT | NULL | 跨模式检索时排序权重 |

### 新表 `ai_session_finalize_log`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | |
| `session_id` | VARCHAR(128) | SSE 会话 ID |
| `tenant_id` | VARCHAR(64) | 多租户隔离 |
| `user_id` | VARCHAR(64) | |
| `session_mode` | VARCHAR(32) | 9 模式之一 |
| `l2_persisted` | BOOL | 是否成功写入 L2 |
| `mem0_synced` | BOOL | 是否成功写入 Mem0 |
| `error_message` | TEXT NULL | 失败原因(降级不阻断) |
| `created_at` | TIMESTAMPTZ | |

完整迁移文件: [`backend/app/db/migrations/versions/2026_09_27_add_cross_mode_context_fields.py`](../../backend/app/db/migrations/versions/2026_09_27_add_cross_mode_context_fields.py)

---

## 7. API 端点(PR-2)

| Method | Path | 用途 | Feature flag 关闭 |
|--------|------|------|------------------|
| POST | `/api/v1/ai/context/entries` | 跨模式条目检索(`source_mode` + `include_tags` + `allow_cross_mode` 过滤) | 503 |
| POST | `/api/v1/ai/context/breakdown` | 按 `source_mode` 聚合统计(9 模式分布) | 503 |
| GET | `/api/v1/ai/context/strategies` | 返回 9 模式策略清单(`STRATEGY_TABLE` 数据驱动) | **200**(前端需 fallback) |

实现位于 [`backend/app/routers/ai/ai_context.py`](../../backend/app/routers/ai/ai_context.py) (commit `552cafc`)。

---

## 8. 测试统计

| 阶段 | 数量 | 类型 | 状态 |
|------|------|------|------|
| PR-1 | 28/28 ✅ | backend pytest | `test_context_policies`、`test_cross_mode_recorder`、`test_cross_mode_recorder_flag`、`test_lifespan_integration`、`test_compaction_audit_service`、`test_auto_compaction_scheduler_weekly`、`test_2026_09_27_cross_mode_fields` |
| PR-2 | 12/12 ✅ | backend pytest | `test_ai_context_endpoints` |
| PR-3 | 78/78 ✅ | frontend Vitest | `contexts.spec`、`aiContext.spec`、`useCrossModeStats`/`useContextCompaction`/`useContextStats` specs、5 个 Vue 组件 specs、`AssistantPanel` 集成 |
| **合计** | **118/118** | | |

> **预先存在的非 vitest 套件**: `audioDsp.spec.ts`(Node native test)与本次无关。

---

## 9. 三个子代理执行记录

| PR | Subagent ID | 输出路径 | 关键产出 |
|----|-------------|---------|---------|
| PR-1 | [`93ec44a2-b720-4d10-88e7-482c2423bf1a`](../../agent-transcripts/b892e74c-2681-4903-8aad-bbb37c56850d/subagents/93ec44a2-b720-4d10-88e7-482c2423bf1a.jsonl) | 7 commits / +2193 行 / 28 测试 |
| PR-2 | [`fc37d543-4737-4c98-bb98-544a8af48e74`](../../agent-transcripts/b892e74c-2681-4903-8aad-bbb37c56850d/subagents/fc37d543-4737-4c98-bb98-544a8af48e74.jsonl) | 1 commit / +623 行 / 12 测试 |
| PR-3 | [`e89e1c09-ff2c-4398-ad3f-1edc96653a22`](../../agent-transcripts/b892e74c-2681-4903-8aad-bbb37c56850d/subagents/e89e1c09-ff2c-4398-ad3f-1edc96653a22.jsonl) | 10 commits / +2494 行 / 78 测试 |

---

## 10. 工作树残留(非本次范围)

PR-3 完成后,`git status` 仍显示以下未跟踪/未提交项,均属于会话开始前已存在的状态:

```text
 M frontend/src/api/aiSession.ts              (用户先前会话改动)
?? Phase1_Phase2_Phase3_Complete_Summary.md (用户先前会话总结)
?? docs/superpowers/plans/2026-09-21-multi-mode-context-management.md (用户先前会话旧 plan)
?? temp_phase1_phase2_implementation_summary.md (用户先前会话临时文件)
```

PR-2 子代理发现 **9 个后端测试因 `ai_context.py` 工作树已有未提交改动失败**:

- `tests/integration/test_api_context.py`(4)
- `tests/unit/test_context_manager.py`(5)

原因:这些改动替换了 `dummy_get_current_user` 为真实鉴权(影响 `/stats` `/retrieve` `/compaction` 三个旧端点),与本次 3 个 PR 的端点不重叠。**属于用户先前会话遗留技术债,未纳入本次实施范围。**

---

## 11. 常见问题速查

**Q: 如何关闭跨模式上下文(临时)?**
设置 `settings.ENABLE_CROSS_MODE_RECORDER = False`,`sse_bridge.finalize_session` 跳过 recorder。`/strategies` 端点仍 200,前端用 `DEFAULT_STRATEGIES` fallback。

**Q: `scheduled` 模式为什么不上 Mem0?**
风险控制语义:定时任务触发的会话只记输入,不污染永久记忆。

**Q: `deep_research / agent / team` 三个模式的特殊之处?**
- `deep_research`:深度研究需要长期上下文,跨模式可读、7 天 TTL
- `agent`:Agent 自主执行,需调用其它模式产出,跨模式可读、7 天 TTL
- `team`:多 Agent 协作,跨模式可读、7 天 TTL

**Q: 数据驱动 UI 是什么意思?**
`CrossModeStatsPage.vue` 用 `v-for` 遍历 `strategies.value || DEFAULT_STRATEGIES`,由 `ModeContextCard.vue` 单一组件渲染任意 9 模式;**禁止硬编码 9 个独立卡片组件**(plan 明确约束)。

**Q: 如何验证 Mem0 健康度?**
- 实时:`logger.error` 触发 `sync_to_long_term` 失败告警
- 周报:`AutoCompactionScheduler.weekly_report` 统计 `ai_session_finalize_log` 中 `mem0_synced=False` 比例
- 前端:9 模式卡中 `mem0` 字段为 False 的(`scheduled`)显示永久记忆为 N/A

---

## 12. 文档导航

```text
docs/
├── cursor-context.md                                     ← 本文档(索引入口)
└── superpowers/
    ├── specs/
    │   └── 2026-09-27-cross-mode-context-completion-design.md   (设计方案 v1.1)
    └── plans/
        └── 2026-09-27-cross-mode-context-completion.md           (实施计划,18 Task)
```

阅读顺序建议:**本文档 → design v1.1 → plan → 相关 commit diff → 测试代码**。
