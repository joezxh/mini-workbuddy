"""统一登记装配测试（spec 步骤二：SUPERAGENT 类型 + build_agent_toolkit）。

不依赖真实 MCP Server / 数据库：
- ai_mcp_client / ai_tool_definition 查询经 fake db（query 链 mock）；
- MCPClient.connect 全部 monkeypatch 失败（不 spawn 子进程）；
- AgentFactory 分支 mock 模型构建与 superagent toolkit。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.ai.superagent.tools import (
    LocalTool, MCPToolkitFactory, build_agent_toolkit,
)
from app.ai.superagent.tools.toolkit import (
    _normalize_inline_mcp, _resolve_mcp_server_entries,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- Fake DB

class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDb:
    """query(Model) → 按 ORM 类名分流到预置行。"""

    def __init__(self, mcp_rows=None, tool_rows=None):
        self._mcp = mcp_rows or []
        self._tools = tool_rows or []

    def query(self, model):
        name = model.__name__
        if name == "AiMcpClient":
            return _FakeQuery(self._mcp)
        if name == "AiToolDefinition":
            return _FakeQuery(self._tools)
        return _FakeQuery([])


def _mcp_row(id=5, name="win-mcp", tools_config=None):
    return SimpleNamespace(id=id, name=name, client_type="stdio",
                           tools_config=tools_config or {})


@pytest.fixture(autouse=True)
def _no_spawn(monkeypatch):
    """所有 MCP connect 直接失败（不 spawn 真实子进程）。"""

    async def _fail_connect(self):
        raise RuntimeError("MCP server not installed")

    monkeypatch.setattr(
        "app.ai.superagent.tools.mcp_adapter.MCPClient.connect", _fail_connect)


# ---------------------------------------------------------------- mcp 三态解析

def test_inline_dict_entry_normalized():
    entry = _normalize_inline_mcp({
        "name": "svc", "command": r"D:\x\my-server.cmd", "args": ["--p", "1"],
        "env": {"K": "V"}, "transport": "stdio",
    })
    assert entry == {"name": "svc", "command": r"D:\x\my-server.cmd",
                     "args": ["--p", "1"], "env": {"K": "V"}}


def test_inline_windows_mcp_gets_serve_subcommand():
    """windows-mcp 入口缺 serve 子命令时自动补齐（WINDOWS_MCP_ARGS 定制）。"""
    entry = _normalize_inline_mcp({"command": "windows-mcp"})
    assert entry is not None and entry["args"] == ["serve"]
    # 已显式带 serve 不重复补
    entry2 = _normalize_inline_mcp({"cmd": "C:\\v\\windows-mcp.exe", "args": ["serve", "--p"]})
    assert entry2["args"] == ["serve", "--p"]


def test_inline_dict_without_command_skipped():
    assert _normalize_inline_mcp({"name": "no-cmd"}) is None


def test_builtin_str_entry():
    entries = _resolve_mcp_server_entries(["playwright", "windows-mcp", "kira-mcp"], None)
    assert set(entries) == {"playwright", "windows-mcp", "kira-mcp"}
    assert entries["playwright"]["command"] == "npx"
    assert entries["windows-mcp"]["args"] == ["serve"]


def test_db_id_entry_from_tools_config():
    """int / 数字 str → ai_mcp_client.id，配置取自 tools_config JSON。"""
    db = _FakeDb(mcp_rows=[_mcp_row(
        id=9, name="kira", tools_config={"command": "kira-mcp", "args": [], "env": {}})])
    entries = _resolve_mcp_server_entries([9], db)
    assert set(entries) == {"kira"}
    entries2 = _resolve_mcp_server_entries(["9"], db)
    assert set(entries2) == {"kira"}


def test_db_name_entry_and_mcpServers_shape():
    """str name → ai_mcp_client.name；兼容 mcpServers 嵌套形状。"""
    db = _FakeDb(mcp_rows=[_mcp_row(tools_config={
        "mcpServers": {"win": {"command": "windows-mcp", "args": [], "env": {"A": "1"}}},
    })])
    entries = _resolve_mcp_server_entries(["win-mcp"], db)
    assert set(entries) == {"win-mcp"}
    assert entries["win-mcp"]["command"] == "windows-mcp"
    assert entries["win-mcp"]["args"] == ["serve"]  # 自动补 serve
    assert entries["win-mcp"]["env"] == {"A": "1"}


def test_db_entry_without_command_skipped():
    db = _FakeDb(mcp_rows=[_mcp_row(tools_config={"client_type": "http"})])
    assert _resolve_mcp_server_entries(["win-mcp"], db) == {}


def test_unknown_str_without_db_skipped():
    """db=None 时未知 key 不查表，直接跳过（ticket 旧契约）。"""
    assert _resolve_mcp_server_entries(["unknown-mcp"], None) == {}


# ---------------------------------------------------------------- build_agent_toolkit

def test_build_agent_toolkit_mcp_and_local(monkeypatch):
    """登记 mcp_servers（三态混排）+ kb/skills → Toolkit 装配。"""
    db = _FakeDb(mcp_rows=[_mcp_row(
        id=3, name="custom-svc", tools_config={"command": "svc.exe", "args": ["-m"]})])
    kwargs = {
        "agent_code": "ag-1",
        "mcp_servers": ["playwright", 3, {"name": "inl", "command": "inl.exe"}],
        "knowledge_bases": ["col-a"],
        "skills": ["weekly-report"],
    }
    tk = _run(build_agent_toolkit(kwargs, db=db, workspace_id=1, tenant_id=7))
    assert set(tk.clients) == {"playwright", "custom-svc", "inl"}
    assert tk.tools == {}  # connect 全失败 → 无 MCP 工具
    # 本地工具：kb_search（kb 登记）+ ontology + sandbox + skill
    assert "kb_search" in tk.extra_tools
    assert "skill_weekly-report" in tk.extra_tools
    assert tk.extra_tools["skill_weekly-report"].description == "执行已登记技能 weekly-report"
    descs = {d["name"] for d in tk.tool_descriptions()}
    assert {"kb_search", "ontology_search", "python_exec", "skill_weekly-report"} <= descs


def test_build_agent_toolkit_custom_tool_bridged(monkeypatch):
    """tool_key（custom 型）→ ToolManager 解析后桥接为 LocalTool。"""
    db = _FakeDb()

    class _FakeChunk:
        def __init__(self):
            self.content = [SimpleNamespace(text='{"ok": 1}')]

    async def _fake_tool_call(self, **kwargs):
        return _FakeChunk()

    fake_tool = SimpleNamespace(
        name="my_tool", description="自定义工具", input_schema={"type": "object"},
        call=_fake_tool_call.__get__(SimpleNamespace()),
    )
    monkeypatch.setattr("app.ai.tool_manager.manager._resolve_tool",
                        lambda db_, key: fake_tool if key == "my_tool" else None)

    tk = _run(build_agent_toolkit({"tools": ["my_tool"]}, db=db))
    assert "my_tool" in tk.extra_tools
    bridge = tk.extra_tools["my_tool"]
    assert bridge.description == "自定义工具"
    assert bridge.input_schema == {"type": "object"}
    out = _run(bridge.call({"q": "x"}))
    assert out == {"ok": 1}  # ToolChunk → 文本 → JSON 还原


def test_build_agent_toolkit_mcp_tool_no_duplicate(monkeypatch):
    """tool_type=mcp 的条目映射到 mcp_servers 对应实例，不重复实例化。"""
    db = _FakeDb(
        mcp_rows=[_mcp_row(id=7, name="desktop", tools_config={"command": "win-cmd.exe"})],
        tool_rows=[SimpleNamespace(
            tool_key="desktop_click", tool_type="mcp",
            config_value={"mcp_server": 7, "tools": ["click"]}),
        ],
    )

    connected = {}

    async def _connect(self):
        connected[self.server_cmd] = connected.get(self.server_cmd, 0) + 1
        from app.ai.superagent.tools.mcp_adapter import MCPTool
        return [MCPTool(name="click", description="click", input_schema={}),
                MCPTool(name="type_text", description="type", input_schema={})]

    monkeypatch.setattr(
        "app.ai.superagent.tools.mcp_adapter.MCPClient.connect", _connect)

    kwargs = {
        "mcp_servers": [7],           # 登记 server（id）
        "tools": ["desktop_click"],   # mcp 型 tool，config_value 引用同一 server id
    }
    tk = _run(build_agent_toolkit(kwargs, db=db))
    # 同一 server 只实例化/连接一次
    assert connected == {"win-cmd.exe": 1}
    assert set(tk.clients) == {"desktop"}
    # 白名单过滤：仅暴露 config_value.tools 指定的工具
    assert set(tk.tools) == {"desktop:click"}


def test_build_agent_toolkit_mcp_tool_alone_instantiates_server(monkeypatch):
    """mcp 型 tool 引用的 server 未在 mcp_servers 中 → 归一并实例化（builtin 引用）。"""

    async def _connect(self):
        from app.ai.superagent.tools.mcp_adapter import MCPTool
        return [MCPTool(name="navigate", description="n", input_schema={})]

    monkeypatch.setattr(
        "app.ai.superagent.tools.mcp_adapter.MCPClient.connect", _connect)

    db = _FakeDb(tool_rows=[SimpleNamespace(
        tool_key="browser_go", tool_type="mcp",
        config_value={"server": "playwright"}),
    ])
    tk = _run(build_agent_toolkit({"tools": ["browser_go"]}, db=db))
    assert "playwright" in tk.clients
    assert "playwright:navigate" in tk.tools


def test_build_agent_toolkit_no_registration_yields_sandbox_only():
    """空登记 → 仍有进程内 Sandbox 组合（与 ticket 同款本地工具基底）。"""
    tk = _run(build_agent_toolkit({"agent_code": "empty"}, db=None))
    assert tk.clients == {}
    assert set(tk.extra_tools) == {"python_exec"}


# ---------------------------------------------------------------- build_ticket_toolkit 兼容映射

@pytest.mark.asyncio
async def test_build_ticket_toolkit_db_mcp_ids(monkeypatch):
    """ticket mcp_ids 引用 ai_mcp_client（id/name）→ 统一装配路径实例化。"""
    db = _FakeDb(mcp_rows=[_mcp_row(
        id=11, name="repo-svc", tools_config={"command": "repo.exe", "args": ["serve"]})])
    ticket = {"id": "T-1", "workspace_id": 2, "tenant_id": 5,
              "config": {"mcp_ids": [11, "repo-svc"]}}
    tk = await MCPToolkitFactory.build_ticket_toolkit(ticket, db=db)
    assert set(tk.clients) == {"repo-svc"}  # 同名去重：id 与 name 指向同一条记录


@pytest.mark.asyncio
async def test_build_ticket_toolkit_builtin_still_works(monkeypatch):
    """内置 key 行为不变（回归：默认 playwright + kb_ids 本地工具）。"""
    ticket = {"id": "T-2", "workspace_id": 1,
              "config": {"mcp_ids": ["playwright", "windows-mcp"], "kb_ids": ["col-a"]},
              "tenant_id": 7}
    tk = await MCPToolkitFactory.build_ticket_toolkit(ticket)
    assert set(tk.clients) == {"playwright", "windows-mcp"}
    assert set(tk.extra_tools) == {"kb_search", "ontology_search", "python_exec"}


# ---------------------------------------------------------------- AgentFactory 分支

class _FakeSaToolkit:
    """superagent Toolkit 替身 —— 桥接断言用。"""

    def __init__(self):
        self.tools = {
            "playwright:navigate": SimpleNamespace(
                description="导航", input_schema={"type": "object"}),
        }
        self.extra_tools = {
            "kb_search": LocalTool(name="kb_search", description="检索",
                                   input_schema={"type": "object"},
                                   handler=lambda a: {"hits": []}),
        }
        self.calls = []

    async def call(self, ref, arguments):
        self.calls.append((ref, arguments))
        return {"ref": ref}

    async def close_all(self):
        pass


@pytest.fixture()
def _fake_model(monkeypatch):
    from agentscope.credential import OpenAICredential
    from agentscope.model import OpenAIChatModel

    def _build(cfg):
        return OpenAIChatModel(
            credential=OpenAICredential(api_key="sk-test"),
            model=(cfg or {}).get("model") or "test-model",
        )

    monkeypatch.setattr("app.ai.strategy.factory_ext.build_model", _build)


def test_create_superagent_agent_bridges_registered_tools(_fake_model, monkeypatch):
    """SUPERAGENT 分支：登记能力 → agentscope Agent（工具桥接 + ALLOW 权限）。"""
    from app.ai.agent_factory import AgentFactory

    fake_tk = _FakeSaToolkit()
    monkeypatch.setattr(
        "app.ai.superagent.tools.toolkit.build_agent_toolkit_sync",
        lambda kwargs, db=None, workspace_id=0, tenant_id=None: fake_tk)

    agent = AgentFactory(db=None).create_agent("superagent", {
        "agent_code": "ag-9", "name": "超级代理",
        "model_config": {"provider": "openai", "model": "gpt-x"},
        "mcp_servers": ["playwright"], "tools": [], "skills": [],
        "system_prompt": "领域提示词",
    })
    # 返回物与其它分支同型（agentscope Agent）
    assert type(agent).__name__ == "Agent"
    assert agent.name == "超级代理"
    assert agent._system_prompt == "领域提示词"

    # 注册工具：MCP ref + 本地工具，全部 ALLOW
    t_mcp = _run(agent.toolkit.get_tool("playwright:navigate"))
    t_local = _run(agent.toolkit.get_tool("kb_search"))
    assert t_mcp is not None and t_local is not None
    from agentscope.permission import PermissionBehavior
    assert t_mcp._permission.behavior == PermissionBehavior.ALLOW

    # MCP 工具真实转发：模型调用 → toolkit.call('server:tool', arguments)
    chunk = _run(t_mcp.call(query="x"))
    assert fake_tk.calls == [("playwright:navigate", {"query": "x"})]
    assert chunk is not None


def test_create_superagent_agent_react_config(_fake_model, monkeypatch):
    """react_config.max_iters → ReActConfig 透传。"""
    from app.ai.agent_factory import AgentFactory

    monkeypatch.setattr(
        "app.ai.superagent.tools.toolkit.build_agent_toolkit_sync",
        lambda kwargs, db=None, workspace_id=0, tenant_id=None: _FakeSaToolkit())

    agent = AgentFactory(db=None).create_agent("superagent", {
        "agent_code": "ag-10", "react_config": {"max_iters": 7},
    })
    assert agent.react_config.max_iters == 7
