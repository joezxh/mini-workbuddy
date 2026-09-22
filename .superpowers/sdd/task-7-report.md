# Task 7 Report: SkillEventHandler 重写（语法修复 + 分级 + 三级关联 + 计量）

**Status:** DONE_WITH_CONCERNS（功能全部完成、122 测试通过；因安装版 agentscope 与 brief 存在 4 处 API 差异，做了有依据的适配，需审查者确认——依据即下方 Step 0 原始输出）

**Commits:**
- `01772c2` feat(agent): SkillEventHandler 重写——分级落库/三级关联/token 计量，修复 lambda-yield 语法错误
- `2f3dc42` docs(agent): 修正 execution.py 模块 docstring 中已失效的 EventStreamHandler 描述

**测试：** `tests/unit/test_skill_event_handler.py` 6 passed；全量 `tests/unit` 122 passed（基线 116 + 新增 6），1 个既有 warning（SQLAlchemy declarative_base）。

---

## Step 0 字段检查（原始输出，verbatim）

命令（brief 提供）：

```
cd backend && python -c "
from agentscope.event import TextBlockDeltaEvent, ToolCallEndEvent, ModelCallEndEvent, ReplyEndEvent, ToolResultEndEvent
for cls in (TextBlockDeltaEvent, ToolCallEndEvent, ModelCallEndEvent, ReplyEndEvent, ToolResultEndEvent):
    print(cls.__name__, getattr(cls, 'model_fields', None) or cls.__annotations__)
"
```

输出：

```
TextBlockDeltaEvent {'id': ..., 'created_at': ..., 'metadata': ..., 'type': ..., 'reply_id': FieldInfo(annotation=str, required=True), 'block_id': FieldInfo(annotation=str, required=True), 'delta': FieldInfo(annotation=str, required=True)}
ToolCallEndEvent {'id': ..., 'created_at': ..., 'metadata': ..., 'type': ..., 'reply_id': FieldInfo(annotation=str, required=True), 'tool_call_id': FieldInfo(annotation=str, required=True)}
ModelCallEndEvent {'id': ..., 'created_at': ..., 'metadata': ..., 'type': ..., 'reply_id': FieldInfo(annotation=str, required=True), 'input_tokens': FieldInfo(annotation=int, required=True), 'output_tokens': FieldInfo(annotation=int, required=True), 'cache_input_tokens': ..., 'cache_creation_input_tokens': ..., 'finished_reason': ...}
ReplyEndEvent {'id': ..., 'created_at': ..., 'metadata': ..., 'type': ..., 'session_id': FieldInfo(annotation=str, required=True), 'reply_id': FieldInfo(annotation=str, required=True), 'finished_reason': FieldInfo(annotation=ReplyFinishedReason, required=False, default=<ReplyFinishedReason.COMPLETED: 'completed'>), 'error': FieldInfo(annotation=Union[ErrorInfo, NoneType], required=False, default=None)}
ToolResultEndEvent {'id': ..., 'created_at': ..., 'metadata': ..., 'type': ..., 'reply_id': FieldInfo(annotation=str, required=True), 'tool_call_id': FieldInfo(annotation=str, required=True), 'state': FieldInfo(annotation=ToolResultState, required=True)}
```

补充检查（其余 brief 涉及的类）：

```
ReplyStartEvent      → session_id, reply_id, name, role（全必填）
TextBlockEndEvent    → reply_id, block_id, text(optional)
ThinkingBlockDeltaEvent → reply_id, block_id, delta
ThinkingBlockEndEvent   → reply_id, block_id
ToolCallStartEvent   → reply_id, tool_call_id, tool_call_name   ← 与 brief 一致
ToolResultTextDeltaEvent → reply_id, tool_call_id, delta
ExceedMaxItersEvent  → reply_id, name
ToolResultEndEvent state="success" → use_enum_values 存为 str 'success' ✓
```

**关键差异发现：**

1. **`ErrorEvent` 不存在**：`from agentscope.event import ErrorEvent` → ImportError。全模块事件类清单（安装版）：
   `AgentEvent, CustomEvent, DataBlockDeltaEvent, DataBlockEndEvent, DataBlockStartEvent, ExceedMaxItersEvent, ExternalExecutionResultEvent, HintBlockEvent, ModelCallEndEvent, ModelCallStartEvent, ReplyEndEvent, ReplyStartEvent, RequireExternalExecutionEvent, RequireUserConfirmEvent, TextBlockDeltaEvent, TextBlockEndEvent, TextBlockStartEvent, ThinkingBlockDeltaEvent, ThinkingBlockEndEvent, ThinkingBlockStartEvent, ToolCallDeltaEvent, ToolCallEndEvent, ToolCallStartEvent, ToolResultDataDeltaEvent, ToolResultEndEvent, ToolResultStartEvent, ToolResultTextDeltaEvent, UserConfirmResultEvent, UserInterruptEvent`
   错误经 **`ReplyEndEvent.error`（`ErrorInfo`，字段 `type: ErrorType` + `message: str`）** 传递（Step 0 输出可直接验证）。
2. **`EventStreamHandler` 也不存在于 `agentscope.event`**（现有代码 `from agentscope.event import EventStreamHandler` 本身就是坏的 ImportError——此前被语法错误掩盖，从未 import 成功过）。全 agentscope 包内 grep 无此类定义。
3. **`ToolCallEndEvent` 无 `tool_args` 字段**（仅 reply_id/tool_call_id；工具参数经 ToolCallDeltaEvent 流式传输）。
4. **`ModelCallEndEvent` 无 `model_name` 字段**。
5. **`EventBus`（Task 5 产出）无 `execution_id`/`trace_id` 属性** —— brief `_publish_db` 里的 `self.bus.execution_id` 会 AttributeError。

## 逐条适配说明（含依据）

| # | brief 原文 | 适配 | 依据 |
|---|-----------|------|------|
| 1 | handler 继承 `EventStreamHandler` | 改为普通类，删除该 import | Step 0：类不存在于安装版 |
| 2 | `elif isinstance(event, ErrorEvent):` 分支 + import | 删除该分支；错误处理并入 `ReplyEndEvent` 分支：`event.error is not None` 时发布 error 信封（DB/STREAM/UI 级）+ SSE error 事件 | Step 0：`ReplyEndEvent.error: ErrorInfo \| None` 字段确凿存在；ErrorEvent 不存在则 import 即崩 |
| 3 | 测试 `ToolCallEndEvent(..., tool_args={"cmd":"ls"})` | 测试移除 `tool_args` kwarg；handler 保留 `getattr(event, "tool_args", {}) or {}` 防御式读取（取值为 `{}`） | Step 0：字段不存在（pydantic 默认 extra=ignore，传入也会被丢弃） |
| 4 | 测试 `ModelCallEndEvent(..., model_name="qwen-max")` | 测试移除 `model_name` kwarg；handler 保留 `getattr(event, "model_name", "")`（取值为 `""`） | Step 0：字段不存在 |
| 5 | `_publish_db` 读 `self.bus.execution_id / self.bus.trace_id` | `__init__` 新增可选参 `execution_id`/`trace_id`：显式传入 → `getattr(bus, ..., None)` → 兜底 `str(uuid.uuid4())`（仅 execution_id；EventEnvelope.execution_id 必填） | Task 5 的 `EventBus` 无这两个属性（bus.py 已读，仅有 `publish()`）；FakeBus 也没有 |
| 6 | brief handler 的 ThinkingBlockEnd 只落 `{"block_id": ...}` | 改为累计 thinking delta 后落 `{"thinking": 全文}` | **brief 自身测试** `test_thinking_delta_summary` 断言 `content == {"thinking": "思考中"}` —— 测试是验收标准，handler 代码段与其矛盾，以测试为准 |
| 7 | brief 注释称未知事件"SSE error 兜底"，代码只 `logger.debug` | 依 brief 的**代码**实现（仅 debug 日志）。原因：真实流含大量未处理 Start 事件（ThinkingBlockStart/TextBlockStart/ToolResultStart/ModelCallStart 等），若逐个发 SSE error 会污染前端 | brief 测试 `test_error_event` 的断言 `... or bus.published == []` 两种实现都通过；旧版行为即"忽略未知事件" |
| 8 | dispatch note 4：旧 `from app.schemas.agent.agent import ExecutionEventType` 变为未用、应删除 | 已删除旧路径导入；改为 `from app.schemas.agent.event_types import ..., ExecutionEventType` 一并导入 —— **因 execute() 仍在用 `ExecutionEventType.AGENT_START/ERROR`（Task 8 才重写）**，note 4 的"未用"判断不成立，此为兼容两者要求的最小解 | execute() 代码（本任务未重写） |

其余实现严格按 brief + dispatch notes：
- `__init__` 初始化 `self._final_text_parts`；`TextBlockDeltaEvent` 分支同时 append `text_parts` 与 `_final_text_parts`（note 3）✓
- `execute()` 内第二处 `lambda evt: yield evt` 语法错误按 note 2 的最小修复：`SkillEventHandler(skill_name=skill_name, bus=EventBus(), out_q=asyncio.Queue())`，周边 agent/user_msg/reply_stream 行保持原样，未引入 Task 8 语义 ✓
- `_run_agent_native` 死代码整体删除（brief (d)）✓
- 存根区（record_execution_* pass）替换为 `app.ai.skills.execution_records` 真实导入（brief (a)）✓
- `from app.ai.services.execution_event_service import ExecutionEventService` 保留（note 5）✓
- 模块结尾**可正常 import**（pytest 收集 + 6 测试全过为证）✓

## 分级/关联/计量自检（对照 self-review 清单）

- **delta→仅 SSE**：Text/Thinking/ToolResult(Text/Data) delta 分支均不调用 `_publish_db`；SSE 类型保持旧值（text/thinking/tool_result）✓
- **块级/调用级汇总→DB**：`text_done`（`{"text": 拼接全文}`，levels=[DB]）、`thinking_done`（`{"thinking": 拼接}`，[DB]）、`tool_call`/`tool_result`（[DB,STREAM,UI]，ui_hint=timeline）、`reply_start`/`reply_end`（[DB]）、`model_call`（[LOG]，levels==[0]）✓
- **三级关联**：`reply_id`（信封级，ReplyStart 设置）、`block_id`（text_done/thinking_done kwargs）、`tool_call_id`（tool_call/tool_result kwargs）✓
- **token 计量**：`usage` 累计 input/output_tokens，`iterations` 计数；`reply_end` metadata 携带 `{input_tokens, output_tokens, iterations}`；`done` SSE 用 `_final_text_parts` 全文 ✓
- **TDD 流程**：Step 1 写测试 → Step 2 确认 RED（collection error: `SyntaxError: invalid syntax` at line 332）→ Step 3 实现 → Step 4 GREEN ✓

## Concerns（需审查者知悉）

1. **ErrorEvent 分支的替代实现**：适配 #2 是行为决策（错误随 ReplyEnd 一起处理：先发 error 信封/SSE，再发 reply_end + done）。若 spec 对错误时序另有要求（如 error 时不应发 done SSE），需在 Task 8 调整。
2. **适配 #5 execution_id 兜底 uuid**：execute() 走 `EventBus()`（无 execution_id）时，handler 信封的 execution_id 是随机 uuid，与 `agent_execution` 主记录的 execution_id **不一致**。Task 8 重写 execute() 时应显式传 `execution_id=execution_id, trace_id=trace_id`（新签名已支持）。
3. **model_call 的 model_name 恒为 `""`、tool_call 的 input 恒为 `{}`**：安装版事件不携带这两字段。若 spec 要求落库含模型名/工具入参，需在 Task 8 或 P1 从 ModelCallStart/ToolCallDelta 累积。
4. 工作区存在大量**本任务之外**的未提交改动（其他 plan 的 frontend/hub 等文件）——本任务仅提交了 brief 列出的两个文件。

## 验证命令与结果

```
python -c "import ast; ast.parse(open('app/ai/skills/execution.py', encoding='utf-8').read()); print('syntax ok')"
→ syntax ok

python -m pytest tests/unit/test_skill_event_handler.py -v
→ 6 passed, 1 warning

python -m pytest tests/unit -q
→ 122 passed, 1 warning（基线 116，无回归）
```
