# SDD Progress: agentscope-voice-s2s (plan: docs/superpowers/plans/2026-09-20-agentscope-voice-s2s.md)

# Branch: feature/agentscope-voice-s2s  Base: 4bc1b57 (main)  Started: 2026-09-22
# 注意：工作区有其它会话遗留的未提交改动（backend/app/ai/**、skills、frontend assistant/i18n 等），
# 各任务提交必须用 pathspec 限定范围，禁止 git add -A；Task 6 收编 requirements*.txt 时先 git diff 确认。
# 规格与计划已在 2026-09-21 复核修订（agentscope 2.0.8 无 OpenAIRealtimeModel 等）。
# 历史台账：agent-event-p0 计划 Task 1-6 已全部完成并合并至 main（f5be34d..0288054）。

---

Task 1: complete (commit a7dd0d7, 5/5 tests pass; 修复：子代理误卷入 staged 的 multi-mode spec，soft reset 后 pathspec 重提交)
Task 2: complete (commit 4eb2c87, 9/9 tests; 修复 send_text 检查顺序+None 保护、_drain 收尾)
Task 3: complete (commit f4ce9de, 11/11; ProviderKey 收敛、registry 切 AgentScope 内核)
Task 4: complete (commit 14f9a1e, 15/15; interrupt/confirm/ping 修复/barge-in 代际/_platform_matches)
Task 5: complete (commit 1f7f415, 3/3; Toolkit 构建 ToolResultState←agentscope.message SUCCESS)
Task 6: complete (commit 3c9bbf1, 删 1915 行/25 文件; requirements 删 torch系+sentence-transformers+onnxruntime;
  重写 test_voice_registry_select 为新语义; 全量回归 357 passed，15 存量失败（hitl/mem0/migration/skill_event，非语音）
  + 3 ontology collection error（conftest 缺 build_client_routers，存量）)
Task 7: complete (commit 3b58125)
Task 8: complete (commit ada03c8; vitest 2.1.9 dev 依赖引入——此前前端无测试基础设施)
Task 9: complete (commit cb66de3)
Task 10: complete (commit 3912c5b)
Task 11: complete (commit 3c562cf; 修复 frontend/.gitignore 缺失——lint 从未真正可跑，验证改用 vue-tsc+vitest)
Task 12: complete (commit 9785077)
Task 13: complete (commit 121e248)
Final review: NEEDS_FIXES → 修复 commit 20eb844（C-1 音频单通道/C-2 MCP 注入打通/C-3 Toolkit 契约/I-1 帧名归一化/I-2 reader 泄漏/I-3 pump 生命周期/M-1~M-4）；
  回归：后端 29 passed，前端 vitest 9 passed，vue-tsc 0 errors。
分支遗留（不阻塞）：M-5 docstring 陈旧片段、M-6 playback.ended 前端未消费/助手轮次未 append_turn、
  全仓 34 个既有 tsc 错误（llm-wiki/kms/assistant 等其它会话文件）、
  存量测试失败 15（hitl/mem0/migration/skill_event）+ ontology collection 3（conftest 缺 build_client_routers）。
