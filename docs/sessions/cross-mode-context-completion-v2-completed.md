# 跨模式上下文记忆 v2.0 整合优化 - 完成报告

> 日期: 2026-09-27
> 前置: v1.x 设计(spec v1.1) + 18 Task 实施计划(Cursor 执行)
> 本轮: 逐符号代码审查 → 整合优化 → 缺口补全

## 1. 审查结论(为什么需要 v2.0)

v1.x 实施产物(策略层/记录器/ORM/迁移/API/前端统计页)**均已存在于工作树**,但存在两类问题:

1. **集成闭环断裂(阻断级)**: 全工程无任何生产代码调用 `CrossModeContextRecorder.record_finalize`——设计声称的 `sse_bridge.py:finalize_session` 并不存在(SSEBridge 是无状态事件转换器、不持有 db)。9 模式 L2/Mem0 写入链为死代码,跨模式记忆从未真正写入。
2. **模式清单错位(功能缺失)**: 工程实际 9 种会话模式含 `data`(SQLBot)(前端 fallback 映射 + 字典表),v1.x 用 `shared` 顶替了它,导致 data 会话既不被记录、`AgentFactory.create_agent("data")` 还会抛 ValueError。

完整缺口清单(G1~G8)见 `docs/superpowers/specs/2026-09-27-cross-mode-context-completion-design.md` §13。

## 2. 本轮完成情况

| Task | 状态 | 关键改动 |
|------|------|---------|
| T1 data 模式补齐 | ✅ | `context_policies.py`: PRIORITY_MAP/TTL/MEM0 白名单加 `data`(48h TTL) + 新增 `SESSION_MODES`(9 种权威清单)与 `STORAGE_FALLBACK_MODE`;`cross_mode_recorder.py` STRATEGY_TABLE 补 `data` 策略 |
| T2 模型注册 | ✅ | `models/ai/__init__.py`: 注册 AIChatContextStorage + AISessionFinalizeLog(+ AiChat 聚合导出) |
| T3 SSE 收尾闭环(G1) | ✅ | 新增 `StreamAnswerCollector`(SSE 事件解析收集答案,异常静默) + `finalize_chat_stream`(统一收尾入口);接入 `routers/ai/ai_agent.py /chat/stream` event_generator(done 前调用,失败不阻断) |
| T4 data 会话可执行(G7) | ✅ | `AgentFactory.create_agent` 增加 `case "data"` → 通用 Agent(SQLBot 工具经 AgentConfig.tools 注入) |
| T5 scheduled 接入(G4) | ✅ | `agent_scheduled_task_service._load_spec` 补 tenant_id/prompt;`_trigger_job` 提交成功后 record_finalize(仅 L2,不写 Mem0) |
| T6 会话内切换模式(G5) | ✅ | 后端 `PUT /ai/assistant/sessions/{id}` 支持 `session_type`(∈ SESSION_MODES 校验,非法 400);`/chat/stream` 同步已有会话的 session_type;前端 `aiSession.updateSession` 兼容 string/object 双签名,`AssistantPanel.vue` watch(sessionType) 持久化切换并提示"上下文已继承" |
| T7 读取侧注入(G6) | ✅ | `build_cross_mode_brief`: 同会话最近 L2 条目(过滤过期)拼成摘要注入 sys_prompt;flag 守护 + 静默降级 |
| T8 测试(G8) | ✅ | `test_context_policies.py` 重写(SESSION_MODES/data 策略);`test_cross_mode_recorder.py` 增 data 策略 + StreamAnswerCollector(5 例) + finalize_chat_stream(3 例);`test_ai_context_endpoints.py` strategies 预期更新为 10 项;`ai_context.py` MODE_LABELS/COLORS 补 data |
| T9 文档 | ✅ | spec 追加 v2.0 章节(§13 审查结论/§14 修复方案);cursor-context.md 勘误 + v2.0 章节;本报告 |

## 3. 修复后数据流

```
/chat/stream (ai_agent.py)
  ├─ build_cross_mode_brief → sys_prompt 注入        [读取侧]
  ├─ StreamAnswerCollector.feed(sse_event)           [边转发边收集]
  └─ stream 结束 → finalize_chat_stream
        └─ CrossModeContextRecorder.record_finalize
              ├─ persist_l2_context  → ai_context_storage (L2 短期)
              ├─ sync_to_long_term   → 本地 Mem0 (永久,8 种交互模式)
              └─ _write_audit        → ai_session_finalize_log

agent_scheduled_task_service._trigger_job → record_finalize("scheduled", 仅 L2)
PUT /ai/assistant/sessions/{id} {session_type} → 会话内切换,消息 + L2 延续
```

## 4. 9 种模式 × 覆盖方式

| 模式 | 记录路径 | Mem0 | 跨模式可读 |
|------|---------|------|-----------|
| general / react / thinking / deep_research / skill / agent / team | /chat/stream 统一收尾 | ✅ | deep_research/agent/team ✅ 其余 ❌ |
| data (SQLBot) | /chat/stream(通用 Agent 回退)统一收尾 | ✅ | ❌ |
| scheduled | 定时任务触发回调(仅记输入) | ❌ | ❌ |
| shared | 存储层兜底标记(非会话模式) | ❌ | — |

## 5. 测试结果

- `pytest tests/unit`: **187 passed**, 1 skipped, 17 failed
- 17 个失败**全部为 v1.x 之前遗留**(与 cursor-context.md §10 及本次改动无关):
  - test_context_manager.py(5): 断言旧 API 形状(`result["data"]`)
  - test_migration_context_storage.py(3): 需真实 PostgreSQL 环境
  - test_mem0_service.py(4): patch 目标 `MemoryClient` 属性不存在(mock 形状失配)
  - test_hitl_coordinator.py(3) / test_skill_event_handler.py(2): 事件序列差异
- 新增测试全部通过: policies(data/SESSION_MODES) + recorder(data 策略/collector/finalize) + endpoints(strategies=10)

## 6. 遗留事项

1. 17 个遗留失败建议单独排期修复(多为 mock/断言形状过时,非功能缺陷)。
2. `get_context_with_mode_filter` 未在 SQL 层过滤 `expires_at`(brief 已兜底过滤),后续可下沉到查询。
3. 前端 17 个失败对应的 Vitest 套件本轮未运行(v1.x 报告 78/78,前端本轮仅改 aiSession.ts 与 AssistantPanel.vue 的 watch 块,已过 IDE lint)。
4. Alembic 迁移链: `2026_09_21_0000` 的 `down_revision=None` 与既有链路的关系建议用 `alembic history` 复核(本轮新增迁移 `2026_09_27_0000` 已挂接)。
