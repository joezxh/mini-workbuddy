# 多智能体组织模式范例（AgentScope 2.0.12）实施计划

> **迁移注记（2026-11-20，本计划已交付后的收编迁移）**：本文引用的
> `backend/examples/org_patterns/` 与 `backend/tests/org_patterns/` 已删除，正式收编落点：
> 实现 → `backend/app/ai/team/org_patterns/`（_common.py → scaffolding.py；
> 01~08 → listing_launch / market_expansion / inquiry_pipeline / support_handoff /
> multiplatform_ops / ad_review_debate / budget_parallel / supply_chain_federation）；
> 测试 → `backend/tests/ai/team/org_patterns/`；CLI → `backend/scripts/run_org_pattern.py`；
> README → `docs/design/org-pattern-teams-zh.md`。下文为历史执行快照，路径不再逐处改写。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 8 个可离线运行的多智能体组织模式范例（跨境电商/外贸/营销投流场景），并以 API 幂等种子挂到现有 agentTeam 专家组「跨境电商」分类下。

**Architecture:** 方案 A 双轨制：`backend/examples/org_patterns/` 独立脚本（共享 `_common.py`，全 mock 离线）权威演示模式语义；`scripts/seed_org_pattern_teams.py` 走 HTTP API 注册 8 个 `xborder-*` 团队。零主链路改动，仅修 orchestrator 的 `TEAM_COMPLETE` 事件漂移。

**Tech Stack:** Python 3.11 / agentscope==2.0.12 / pytest / FastAPI 既有 API（种子脚本仅 HTTP 调用）

**Spec:** `docs/design/org-pattern-examples-zh.md`（已定稿，含事实核实与 8 模式设计；执行者两个文件都要读）

## Global Constraints

- agentscope==2.0.12（Task 1 升级后所有任务以此为准）；Python 3.11（`backend/.venv`）。
- 文档与注释用中文；范例脚本**不 import `app.*`**（独立可运行）；种子脚本只走 HTTP API。
- 不新增事件枚举：只允许 `app/schemas/agent/event_types.py` 既有 canonical 值；范例内以 trace 表达同语义。
- 不做 DB 迁移、不引消息中间件、不改前端、不改 orchestrator 编排逻辑（D6 删除漂移记录除外）。
- 团队 `team_code` 前缀 `xborder-`；category「跨境电商」；mode ∈ {sequential, parallel, msghub, supervisor, dag}。
- 所有范例 `--mock` 离线非交互跑通；无 API key 且未 `--mock` 时抛清晰中文 RuntimeError（不 hang）。
- Agent name 用 ASCII（spike S3 兜底决策）；中文角色名入 system_prompt/role_desc。
- 测试不依赖网络/DB/真实模型；pytest 从 `backend/` 目录运行。
- 每个驱动循环有硬上限：max_iters / max_hops=3 / max_rounds / 发言预算=16 / asyncio.wait_for。

## Review Focus

1. **脚本耗尽**：FakeChatModel 脚本队列被超出预期的轮次耗尽 → 必须抛含 agent 名的清晰错误，测试钉在 Task 4。
2. **无 key 裸跑**：未设任何环境变量且未加 `--mock` → 清晰中文报错而非 hang/traceback 淹没，测试钉在 Task 4。
3. **越权/泄漏**：层级总监直派 Worker、交接泄漏全量对话 → trace 断言钉在 Task 12 / Task 7。
4. **伪并发**：并行范例实际串行 → 时间戳断言钉在 Task 9。
5. **种子半成品**：缺成员 agent 时创建半个团队、重跑重复创建 → dry-run/幂等测试钉在 Task 8。

---

### Task 1: 升级 agentscope 2.0.12 + 回归

**Files:**
- Modify: `backend/requirements.txt:110`（仅过期注释）

**Interfaces:**
- Produces: venv 内 agentscope==2.0.12，后续所有任务的运行环境。

- [ ] **Step 1: 升级并验证版本**

Run: `D:\projects\MinWorkBuddy\backend\.venv\Scripts\pip3.exe install agentscope==2.0.12`
Run: `D:\projects\MinWorkBuddy\backend\.venv\Scripts\python.exe -c "import agentscope; from agentscope._version import __version__; print(__version__)"`
Expected: `2.0.12`

- [ ] **Step 2: 回归既有测试（语音/纠正/团队事件/SOP）**

Run（cwd=backend）: `.venv\Scripts\python.exe -m pytest tests/duplex tests/voice_demo tests/agent tests/ai -q`
Expected: 与升级前基线一致（先跑一遍升级前基线再对比；既有失败不属本任务，记录即可）。
若出现 thinking 相关 400：按 spec §1.1 检查框架层与业务层是否重复发送 enable_thinking，去重而非删业务方言。

- [ ] **Step 3: 修正 requirements.txt L110 过期注释**

`agentscope==2.0.12  # 固定 2.0.11：原生 Agent Team API + 流式修复` → `agentscope==2.0.12  # 原生 Team/SOP API + pipeline 失败清理修复（#3581）`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: 对齐 agentscope 2.0.12 并修正过期注释"
```

### Task 2: 修正 TEAM_COMPLETE 事件漂移（D6）

**Files:**
- Modify: `backend/app/ai/team/orchestrator.py`（删除 `_record_execution_done` 方法及 submit 中的调用）
- Test: `backend/tests/agent/test_team_orchestrator_events.py`

**Interfaces:**
- Consumes: `AgentScopeOrchestrator(db, team, run, event_svc=...)`；`app.ai.msg_utils.text_msg/text_of`。
- Produces: `team_done` 唯一来源为端点层 `RunCollector.emit_team_done`；orchestrator 不再写任何完成事件。

- [ ] **Step 1: 写失败测试**

```python
# tests/agent/test_team_orchestrator_events.py
"""submit 成功后 orchestrator 不写完成事件（team_done 由 RunCollector 负责）。"""
import asyncio
from types import SimpleNamespace
from app.ai.team.orchestrator import AgentScopeOrchestrator
from app.ai.msg_utils import text_msg

class Recorder:
    def __init__(self): self.events = []
    def record(self, **kw): self.events.append(kw)

def test_submit_emits_no_completion_event(monkeypatch):
    rec = Recorder()
    orch = AgentScopeOrchestrator(
        db=None, team=SimpleNamespace(team_code="t", id=1),
        run=SimpleNamespace(run_id="r1"), event_svc=rec)
    async def fake_create(): return True
    monkeypatch.setattr(orch, "create_team", fake_create)
    orch._leader = SimpleNamespace(
        reply=lambda msg: asyncio.sleep(0, result=text_msg("leader", "assistant", "结论")))
    result = asyncio.run(orch.submit("任务"))
    assert result == "结论"
    assert all(e.get("event_type") not in ("TEAM_COMPLETE", "team_done") for e in rec.events)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/agent/test_team_orchestrator_events.py -v`
Expected: FAIL（当前写入 `TEAM_COMPLETE`）

- [ ] **Step 3: 删除 `_record_execution_done` 方法及 submit 中 `self._record_execution_done(final_text)` 调用**

- [ ] **Step 4: 运行确认通过 + 团队相关回归**

Run: `pytest tests/agent/test_team_orchestrator_events.py tests/agent -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/team/orchestrator.py backend/tests/agent/test_team_orchestrator_events.py
git commit -m "fix: 移除 orchestrator 非 canonical TEAM_COMPLETE 事件，team_done 归口 RunCollector"
```

### Task 3: Spike 验证 S1/S2/S3（D7）

**Files:**
- Modify: `docs/design/org-pattern-examples-zh.md`（附录 A 回填）

**Interfaces:**
- Produces: 附录 A 三项结论——S1 模型基类名与 `__call__` 签名/响应类型；S2 `SOPEngine` 运行入口与返回类型；S3 中文 name 是否被 formatter 改写。Task 4/6 直接消费。

- [ ] **Step 1: S1 模型基类探测**

Run: `.venv\Scripts\python.exe -c "import agentscope.model as m, inspect; print([x for x in dir(m) if 'Model' in x or 'Response' in x]); from agentscope.model import ChatModelBase; print(inspect.signature(ChatModelBase.__call__))"`（若类名不存在，按 dir 输出改取实际基类）
记录：基类全名、`__call__` 参数与返回类型、构造所需最小参数。

- [ ] **Step 2: S2 SOPEngine 入口探测**

Run: `.venv\Scripts\python.exe -c "from agentscope.sop import SOPEngine; import inspect; print([x for x in dir(SOPEngine) if not x.startswith('_')]); print(inspect.signature(SOPEngine.run))"`（按实际公开方法调整）
记录：运行入口方法名、签名、返回类型。

- [ ] **Step 3: S3 中文 name formatter 探测**

构造 `Agent(name="测试专家", ...)`（mock 模型）走 OpenAI formatter，检查输出 messages 的 name 字段是否保留中文/被改写/报错；记录结论。无论结论如何，范例 name 一律 ASCII（Global Constraints 已定）。

- [ ] **Step 4: 回填附录 A 并 Commit**

```bash
git add docs/design/org-pattern-examples-zh.md
git commit -m "docs: 回填 org-pattern spike 结论（FakeModel 基类/SOPEngine 入口/中文 name）"
```

### Task 4: 共享脚手架 _common.py

**Files:**
- Create: `backend/examples/org_patterns/_common.py`
- Test: `backend/tests/org_patterns/conftest.py`、`backend/tests/org_patterns/test_common.py`

**Interfaces:**
- Consumes: Task 3 附录 A 的 S1 基类/签名。
- Produces（后续所有范例任务依赖，签名固定）:
  - `FakeChatModel(script: list)`：S1 基类子类；每次调用按序弹出脚本项（str → 纯文本回复；dict → 按 S1 响应类型构造，支持 tool_calls）；耗尽抛 `RuntimeError(f"FakeChatModel 脚本耗尽: {self.name}")`。
  - `make_model(script: list | None = None, name: str = "fake") -> ChatModelBase`：script 非 None → FakeChatModel；否则 OPENAI_BASE_URL+OPENAI_API_KEY → OpenAIChatModel，其次 DASHSCOPE_API_KEY → DashScopeChatModel；皆无 → `RuntimeError("未配置模型环境变量：请设置 OPENAI_BASE_URL/OPENAI_API_KEY 或 DASHSCOPE_API_KEY，或加 --mock 离线运行")`。
  - `make_agent(name: str, system_prompt: str, tools: list | None = None, max_iters: int = 8, model=None) -> Agent`：PermissionMode.BYPASS；model 缺省 make_model()。
  - `render_stream(stream) -> Msg`：ConsoleRenderer 渲染并返回最终消息。
  - `Trace`：`record(kind: str, **kw)` 追加 `{"kind": kind, **kw}`；`items: list[dict]`；`kinds(kind) -> list[dict]` 过滤。
  - mock 工具：**均为普通 Python 函数**（确定性 str/JSON 返回，便于直接单测），范例内自行用 `FunctionTool` 包装：`mock_market_scan(category)`、`mock_fx_rate(pair)`（USD/JPY=155.0）、`mock_compliance_check(product, market)`、`mock_cost_table(product)`、`mock_channel_roi(channel, budget)`（async，内部 `asyncio.sleep(1)`，返回含 `started_at`/`finished_at` 时间戳）、`mock_platform_stock(platform)`、`mock_platform_price(platform)`、`erp_gateway(fields: list[str])`、`logistics_gateway(fields)`、`ads_gateway(fields)`（白名单外字段返回 `{"error": "字段越界", "denied": [...]}`；白名单：erp=[capacity, lead_time]，logistics=[quote, transit_time]，ads=[budget_spent]）。
  - `run_cli(main_coro_fn)`：argparse `--mock`，`asyncio.run(main_coro_fn(mock=args.mock))`。
  - `load_example(filename: str)`（放 conftest）：importlib.util.spec_from_file_location 加载数字开头模块。

- [ ] **Step 1: 写失败测试**

```python
# tests/trade/test_common.py
import pytest
from _common import FakeChatModel, make_model, Trace, mock_fx_rate, erp_gateway  # conftest 注入 examples 路径

def test_fake_model_script_order():
    m = FakeChatModel(["第一答", "第二答"], name="t")
    # 按 S1 签名调用两次，断言文本依次为 第一答/第二答

def test_fake_model_exhausted_raises():
    m = FakeChatModel([], name="t")
    with pytest.raises(RuntimeError, match="脚本耗尽"): ...  # 调用一次

def test_make_model_no_env_raises(monkeypatch):
    for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "DASHSCOPE_API_KEY"): monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="--mock"): make_model()

def test_trace_filter():
    t = Trace(); t.record("dispatch", member="a"); t.record("done")
    assert t.kinds("dispatch") == [{"kind": "dispatch", "member": "a"}]

def test_gateway_whitelist():
    assert "denied" in erp_gateway(["cost_price"])  # mock 工具是普通函数，直接调用
```

conftest.py：`sys.path.insert(0, str(Path(__file__).parents[2] / "examples" / "org_patterns"))`。

- [ ] **Step 2: 运行确认失败** — `pytest tests/org_patterns/test_common.py -v` → FAIL（模块不存在）
- [ ] **Step 3: 实现 _common.py**（按 Interfaces 签名；FakeChatModel 响应构造按附录 A S1）
- [ ] **Step 4: 运行确认通过** — `pytest tests/org_patterns/test_common.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: org-pattern 范例共享脚手架（FakeModel/mock 工具/Trace/CLI）"`

### Task 5: 范例 01 Supervisor-Worker（打样 1）

**Files:**
- Create: `backend/examples/org_patterns/01_supervisor_worker.py`
- Test: `backend/tests/org_patterns/test_01_supervisor.py`

**Interfaces:**
- Consumes: Task 4 全部脚手架。
- Produces: `async def run_demo(mock: bool) -> dict`，返回 `{"final": str, "trace": Trace}`；`if __name__ == "__main__": run_cli(run_demo)`。trace 含 `dispatch(member=...)`×4、`member_done(member=...)`、`final`。后续范例同此契约。

- [ ] **Step 1: 写失败测试**

```python
def test_supervisor_mock_semantics():
    mod = load_example("01_supervisor_worker.py")
    out = asyncio.run(mod.run_demo(mock=True))
    dispatched = {t["member"] for t in out["trace"].kinds("dispatch")}
    assert dispatched == {"product_picker", "listing_writer", "compliance_checker", "pricing_analyst"}
    assert "GO" in out["final"] or "NO-GO" in out["final"]
```

mock 脚本：leader 首轮对 4 成员各发一个 TeamAssign 工具调用（按 S1 响应类型构造），次轮输出含 "GO" 的汇总；各 worker 单条文本回复。

- [ ] **Step 2: 运行确认失败** — `pytest tests/org_patterns/test_01_supervisor.py -v`
- [ ] **Step 3: 实现**：`TeamPipeline(leader=make_agent("listing_director", LEADER_PROMPT, max_iters=12, model=...), members=[TeamMember(agent=..., description=...)×4])`；dispatch trace 通过包装成员 reply 或监听 pipe 事件记录（取简单者：成员 Agent 外包一层记录 reply 调用的薄代理）。角色/prompt/示例输入按 spec §3.1。
- [ ] **Step 4: 运行确认通过 + 离线 CLI 冒烟**

Run: `pytest tests/org_patterns/test_01_supervisor.py -v` → PASS
Run: `.venv\Scripts\python.exe examples\org_patterns\01_supervisor_worker.py --mock` → 正常结束打印汇总

- [ ] **Step 5: Commit** — `git commit -m "feat: 范例01 Supervisor-Worker 跨境新品上架统筹"`

### Task 6: 范例 03 流水线（打样 2）

**Files:**
- Create: `backend/examples/org_patterns/03_pipeline_inquiry.py`
- Test: `backend/tests/org_patterns/test_03_pipeline.py`

**Interfaces:**
- Consumes: Task 4 脚手架 + 附录 A S2（SOPEngine 入口）。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `step_start(subject=...)`/`step_done(subject=...)` 严格顺序、`step_retry(subject=..., attempt=n)`。

- [ ] **Step 1: 写失败测试**

```python
def test_pipeline_order_and_retry():
    out = asyncio.run(load_example("03_pipeline_inquiry.py").run_demo(mock=True))
    order = [t["subject"] for t in out["trace"].kinds("step_done")]
    assert order == ["解析询盘", "报价", "合同条款", "跟单催单"]

def test_pipeline_verifier_retry_capped():
    out = asyncio.run(load_example("03_pipeline_inquiry.py").run_demo(mock=True, inject_bad_rate=True))
    retries = [t for t in out["trace"].kinds("step_retry") if t["subject"] == "报价"]
    assert 1 <= len(retries) <= 3
```

`run_demo(mock: bool, inject_bad_rate: bool = False)`：注入时 mock_fx_rate 首次返回错误汇率，verifier 脚本判 fail 触发重试。

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：`SOP(steps=[SOPStep(subject, description, executor, verifier=..., max_attempts=3)×4])` + S2 入口运行；trace 经 executor 薄代理记录。角色按 spec §3.3。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**（同 Task 5 Step 4 格式）
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例03 流水线 外贸询盘SOP（原生 agentscope.sop）"`

### Task 7: 范例 04 交接式（打样 3）

**Files:**
- Create: `backend/examples/org_patterns/04_handoff_support.py`
- Test: `backend/tests/org_patterns/test_04_handoff.py`

**Interfaces:**
- Consumes: Task 4 脚手架；`agentscope.event.RequireExternalExecutionEvent/UserInterruptEvent`、`ToolBase(is_external_tool=True)`。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `handoff(from=..., to=..., summary=...)`、`expert_first_msg(expert=..., content=...)`。

- [ ] **Step 1: 写失败测试**

```python
def test_handoff_summary_only_and_hops():
    out = asyncio.run(load_example("04_handoff_support.py").run_demo(mock=True))
    hops = out["trace"].kinds("handoff")
    assert [h["to"] for h in hops] == ["logistics_en", "returns_zh"]
    for fm in out["trace"].kinds("expert_first_msg"):
        assert fm["content"].startswith("<handover>")
        assert "西语客户完整对话" not in fm["content"]  # 前专家全量对话标记串不得出现
    assert len(hops) <= 3
```

mock 脚本：presale_es 发 transfer_to 工具调用（summary 含订单号），logistics_en 同理，returns_zh 直接终答；全量对话中埋标记串验证不泄漏。

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：TransferTo(ToolBase) 外部工具 + 驱动循环（spec §3.4 拓扑；范式见 agent-architecture-patterns-zh.md §9）：消费 reply_stream 至 RequireExternalExecutionEvent → UserInterruptEvent 关闭挂起 → 切专家 → `<handover>摘要</handover>` 作首条消息；max_hops=3 硬上限。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例04 交接式 跨语种客服专家交接（外部工具+驱动循环）"`

### Task 8: 种子脚本 seed_org_pattern_teams.py

**Files:**
- Create: `backend/scripts/seed_org_pattern_teams.py`
- Test: `backend/tests/org_patterns/test_seed_org_teams.py`

**Interfaces:**
- Consumes: 既有 API（`POST /api/v1/agent-config`、`GET/POST /api/v1/ai-team`），payload 范式照 `seed_domain_content.py`。
- Produces: 模块级 `AGENTS: list[dict]`、`TEAMS: list[dict]`（8 团队，字段 team_code/name/description/category/mode/members/roles/edges/sample_input）；`build_payloads() -> (agent_payloads, team_payloads)` 纯函数；`main()` argparse `--dry-run --base-url --username --password`。

- [ ] **Step 1: 写失败测试（纯数据断言，不触网）**

```python
def test_seed_data_contract():
    # scripts 非包：测试内用 importlib.util.spec_from_file_location 从
    # backend/scripts/seed_org_pattern_teams.py 加载（与 conftest.load_example 同法，路径换 scripts）
    mod = load_script("seed_org_pattern_teams.py")
    codes = [t["team_code"] for t in mod.TEAMS]
    assert len(codes) == 8 and len(set(codes)) == 8
    assert all(c.startswith("xborder-") for c in codes)
    assert all(t["category"] == "跨境电商" for t in mod.TEAMS)
    assert all(t["mode"] in {"sequential","parallel","msghub","supervisor","dag"} for t in mod.TEAMS)
    agent_codes = {a["agent_code"] for a in mod.AGENTS}
    for t in mod.TEAMS:
        assert set(t["members"]) <= agent_codes          # 无悬空成员
        assert set(t["roles"]) == set(t["members"])
    for a in mod.AGENTS:
        assert a["strategy"]["execution_mode"] == "llm"  # builder 决策：无技能纯 LLM Agent

def test_edges_reference_known_nodes():
    # 每条 edge 的端点 ∈ members ∪ {__START__, __END__}；supervisor/msghub 动态模式 edges 可为 []
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：8 团队数据按 spec §3 各节挂载段（mode 映射见 spec §2 总表）；agent payload `strategy={"execution_mode":"llm","system_prompt":...}`、`tools={"tools":[],"skills":[]}`；创建流程仿 seed_domain_content（按 code 查重跳过、缺成员跳过整团队、sequential/parallel/dag 生成 edges，supervisor/msghub edges=[]）；`--dry-run` 只打印。
- [ ] **Step 4: 运行确认通过 + dry-run 冒烟**

Run: `pytest tests/org_patterns/test_seed_org_teams.py -v` → PASS
Run: `.venv\Scripts\python.exe scripts\seed_org_pattern_teams.py --dry-run` → 打印 8 团队预览，不触网

- [ ] **Step 5: Commit** — `git commit -m "feat: 跨境电商 xborder-* 8 团队幂等种子脚本"`

### Task 9: 范例 07 并行聚合

**Files:**
- Create: `backend/examples/org_patterns/07_parallel_budget.py`
- Test: `backend/tests/org_patterns/test_07_parallel.py`

**Interfaces:**
- Consumes: Task 4 `mock_channel_roi`（含时间戳、sleep 1s）。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `worker_start(channel=..., at=float)`×3、`worker_done`、`worker_failed(channel=...)`（注入时）。

- [ ] **Step 1: 写失败测试**

```python
def test_real_concurrency_by_timestamps():
    out = asyncio.run(load_example("07_parallel_budget.py").run_demo(mock=True))
    starts = sorted(t["at"] for t in out["trace"].kinds("worker_start"))
    assert starts[-1] - starts[0] < 0.2          # 三路几乎同时启动
    # 总耗时由测试外部计时：asyncio.run 全程 < 1.5s（sleep 1s×3 串行会 ≥3s）

def test_single_failure_continues():
    out = asyncio.run(load_example("07_parallel_budget.py").run_demo(mock=True, fail_channel="roi_meta"))
    assert out["trace"].kinds("worker_failed")
    assert "roi_meta" in out["final"] or "占位" in out["final"]  # 聚合含失败说明
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：`asyncio.gather(*[asyncio.wait_for(w.reply(task), 60) ...])`，异常捕获→占位结果；聚合 Agent 汇总；trace 打时间戳（time.monotonic）。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例07 并行聚合 多渠道预算测算（时间戳证并发）"`

### Task 10: 范例 06 辩论/群聊

**Files:**
- Create: `backend/examples/org_patterns/06_debate_adreview.py`
- Test: `backend/tests/org_patterns/test_06_debate.py`

**Interfaces:**
- Consumes: Task 4 脚手架；`Agent.reply(structured_schema=Verdict)`（Verdict 为 pydantic 模型：verdict/reason/final_plan）。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `round(n=...)`、`speech(role=..., sees=[...])`、`verdict(verdict=...)`。

- [ ] **Step 1: 写失败测试**

```python
def test_debate_converges_within_3_rounds():
    out = asyncio.run(load_example("06_debate_adreview.py").run_demo(mock=True))
    rounds = out["trace"].kinds("round")
    assert 1 <= len(rounds) <= 3
    assert out["trace"].kinds("verdict")[-1]["verdict"] == "final"
    assert out["final"]  # 终审方案非空

def test_both_sides_see_opponent():
    out = asyncio.run(load_example("06_debate_adreview.py").run_demo(mock=True))
    for s in out["trace"].kinds("speech"):
        if s["role"] == "con_creative": assert "pro_creative" in s["sees"]
```

mock 脚本：judge 第 1 轮 continue、第 2 轮 final（验证提前收敛）；另测 judge 恒 continue 时代码兜底第 3 轮强制 final。

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：轮次循环（正方→反方→裁判结构化裁决），max_rounds=3 代码兜底强制终局；辩论记录全员可见。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例06 辩论群聊 广告策略评审（结构化裁决收敛）"`

### Task 11: 范例 05 对等网状

**Files:**
- Create: `backend/examples/org_patterns/05_mesh_multiplatform.py`
- Test: `backend/tests/org_patterns/test_05_mesh.py`

**Interfaces:**
- Consumes: Task 4 脚手架 + mock_platform_stock/price。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `broadcast(msg_id=..., visible_to=[4 平台])`、`speech(platform=..., round=n)`。

- [ ] **Step 1: 写失败测试**

```python
def test_mesh_broadcast_visibility_and_budget():
    out = asyncio.run(load_example("05_mesh_multiplatform.py").run_demo(mock=True))
    for b in out["trace"].kinds("broadcast"):
        assert set(b["visible_to"]) == {"amazon_ops","shopee_ops","tiktok_ops","indie_ops"}
    assert len(out["trace"].kinds("speech")) <= 16     # 发言预算
    rounds = {s["round"] for s in out["trace"].kinds("speech")}
    assert max(rounds) <= 4
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：共享消息板 list + 轮转发言循环；每轮把增量喂给当前平台 Agent；连续一轮无新实质消息或 max_rounds=4 终止；无中心汇总者（final 为消息板终态摘要，由代码拼接而非某 Agent 裁决）。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例05 对等网状 多平台运营互通（自建广播循环）"`

### Task 12: 范例 02 层级式

**Files:**
- Create: `backend/examples/org_patterns/02_hierarchy_expansion.py`
- Test: `backend/tests/org_patterns/test_02_hierarchy.py`

**Interfaces:**
- Consumes: Task 4 脚手架；Task 5 的 TeamPipeline 用法；外部工具事件范式（同 Task 7）。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `assign_team(team=..., task=...)`（仅 director 层）、`team_done(team=...)`、`worker_call(leader=..., worker=...)`（仅 leader 层）。

- [ ] **Step 1: 写失败测试**

```python
def test_no_skip_level():
    out = asyncio.run(load_example("02_hierarchy_expansion.py").run_demo(mock=True))
    director_tasks = [t["task"] for t in out["trace"].kinds("assign_team")]
    worker_names = {"sea_researcher","sea_writer","eu_researcher"}
    assert all(not any(w in t for w in worker_names) for t in director_tasks)  # 总监不直派 Worker
    assert {t["team"] for t in out["trace"].kinds("assign_team")} == {"sea_team","eu_team"}

def test_subteam_timeout_does_not_abort_director():
    out = asyncio.run(load_example("02_hierarchy_expansion.py").run_demo(mock=True, timeout_team="eu_team"))
    assert out["final"]  # 总监仍产出（含 eu 失败说明）
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：director + assign_team 外部工具；两个子 TeamPipeline；`asyncio.gather` 跑子团队 + 每队 `asyncio.wait_for`；结果经 `ExternalExecutionResultEvent` 回填 director；每层独立 max_iters（6/8/6）。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例02 层级式 海外市场拓展（薄编排层+子TeamPipeline）"`

### Task 13: 范例 08 联邦式

**Files:**
- Create: `backend/examples/org_patterns/08_federated_supplychain.py`
- Test: `backend/tests/org_patterns/test_08_federated.py`

**Interfaces:**
- Consumes: Task 4 三个白名单网关工具。
- Produces: `run_demo(mock) -> {"final", "trace"}`；trace 含 `gateway_call(domain=..., fields=...)`、`gateway_denied(domain=..., denied=[...])`。

- [ ] **Step 1: 写失败测试**

```python
def test_cross_boundary_denied():
    out = asyncio.run(load_example("08_federated_supplychain.py").run_demo(mock=True, probe_boundary=True))
    denied = out["trace"].kinds("gateway_denied")
    assert any(d["domain"] == "logistics" and "cost_price" in d["denied"] for d in denied)

def test_coordinator_context_whitelist_only():
    out = asyncio.run(load_example("08_federated_supplychain.py").run_demo(mock=True))
    for c in out["trace"].kinds("gateway_call"):
        allowed = {"erp": {"capacity","lead_time"}, "logistics": {"quote","transit_time"}, "ads": {"budget_spent"}}
        assert set(c["fields"]) <= allowed[c["domain"]]
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：brand_coordinator（Supervisor 式派活给 3 域 Agent）；各域 Agent 只挂本域网关工具；probe_boundary 注入一次越界请求验证拒绝；协调者上下文仅白名单结果。
- [ ] **Step 4: 运行确认通过 + CLI 冒烟**
- [ ] **Step 5: Commit** — `git commit -m "feat: 范例08 联邦式 跨组织供应链协同（白名单网关边界）"`

### Task 14: README + 全量离线验证 + 收尾

**Files:**
- Create: `backend/examples/org_patterns/README.md`
- Modify: `docs/design/org-pattern-examples-zh.md`（如有实施偏差回填）

**Interfaces:**
- Consumes: 全部前序任务产物。

- [ ] **Step 1: README**：8 模式索引表（模式/脚本/场景/原生程度）、环境变量说明（OPENAI_BASE_URL/OPENAI_API_KEY/DASHSCOPE_API_KEY）、`--mock` 用法、种子脚本用法（含 --dry-run）、与 UI 统一编排的关系说明（方案 A 权衡）。
- [ ] **Step 2: 全量离线验证**

Run: `pytest tests/org_patterns tests/agent/test_team_orchestrator_events.py -q` → 全 PASS
Run: 8 个脚本逐一 `--mock` 冒烟（PowerShell 循环）→ 全部正常退出
Run: `pytest tests/duplex tests/voice_demo tests/agent tests/ai -q` → 与 Task 1 基线一致

- [ ] **Step 3: 自检 Global Constraints 与 Review Focus 逐条对照**（无新枚举/无 app.* import/无迁移/硬上限齐全）
- [ ] **Step 4: Commit** — `git commit -m "docs: org-pattern 范例 README 与全量离线验证收尾"`

---

## 依赖关系

Task 1 → 2 → 3 → 4 → {5, 6, 7}（打样，可并行）→ 8；{9, 10, 11}（可并行）→ 12 → 13 → 14。
Task 8 只依赖 Task 4 之前的设计数据（spec §3），实际可在 Task 4 后任意时点插入。

## 假设与已做的 builder 决策

- 种子 agent 用 `execution_mode="llm"`、不绑技能（spec D4 全 mock；已核实 schema 默认值即 llm）。
- 测试经 importlib 加载数字开头脚本；`run_demo(mock, **注入开关)` 为统一契约。
- supervisor/msghub 动态模式种子 edges=[]（现有 orchestrator 运行时不读边，静态边仅 sequential/parallel/dag 需要）。
- 真实模型路径（非 --mock）只做冒烟不做语义断言（模型输出不确定）；语义验收全部走 mock。
- 无通用实现者子代理可用时由本会话顺序执行，独立审查在收尾统一进行（已在交接说明中注明）。