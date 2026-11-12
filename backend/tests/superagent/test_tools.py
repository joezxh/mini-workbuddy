"""SuperAgent Tools 单元测试（规格 2.4/2.5）。

不依赖真实 MCP Server / 数据库：
- Knowledge / Ontology / Sandbox build() 在 service 缺失或 tenant 不可解析时降级返回 []；
- Toolkit.build_ticket_toolkit 组合 MCP（connect 失败被捕获）+ 本地 extra_tools。
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from app.ai.superagent.tools import (
    KnowledgeTools, LocalTool, MCPClient, MCPToolkitFactory, OntologyTools,
    SandboxTools, Toolkit,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- Knowledge

class _FakeRetrievalSvc:
    """替代 KbRetrievalService —— 不触碰 DB / Embedding。"""

    def __init__(self, store, embed_fn):
        pass

    @classmethod
    def from_session(cls, db, tenant_id, embedding_code=None):
        assert tenant_id == 7
        return cls(None, None)

    def hybrid_search_by_text(self, collection, query_text, top_k=5, **kw):
        return [
            SimpleNamespace(document_id="d1", chunk_index=0, content="命中片段",
                            score=0.9, metadata=None),
        ]


def test_knowledge_degrades_without_collections():
    assert KnowledgeTools.build(1, None) == []
    assert KnowledgeTools.build(1, ["", "  "]) == []


def test_knowledge_degrades_when_service_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.services.kb.retrieval_service", None)
    assert KnowledgeTools.build(1, ["col-a"], tenant_id=1) == []


def test_knowledge_degrades_without_tenant():
    # db=None → tenant 不可解析 → 降级
    assert KnowledgeTools.build(1, ["col-a"], db=None, tenant_id=None) == []


def test_knowledge_build_and_search(monkeypatch):
    tools = KnowledgeTools.build(1, ["col-a", "col-b"], db=object(), tenant_id=7)
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "kb_search"
    monkeypatch.setattr(
        "app.services.kb.retrieval_service.KbRetrievalService", _FakeRetrievalSvc)
    out = _run(tool.call({"query": "报销制度", "top_k": 3}))
    assert out["count"] == 2  # 2 个集合 × 各 1 条命中
    assert out["collections"][0]["collection"] == "col-a"
    assert out["collections"][0]["items"][0]["document_id"] == "d1"
    assert out["collections"][1]["collection"] == "col-b"


def test_knowledge_search_error_folded(monkeypatch):
    tools = KnowledgeTools.build(1, ["col-a"], db=object(), tenant_id=7)
    monkeypatch.setattr(
        "app.services.kb.retrieval_service.KbRetrievalService", _FakeRetrievalSvc)
    out = _run(tools[0].call({"query": ""}))
    assert "error" in out


# ---------------------------------------------------------------- Ontology

class _FakeOntologySvc:
    def __init__(self, db, tenant_id):
        assert tenant_id == 7

    def search(self, *, kw=None, kind="table", size=20, **_):
        return {"total": 1, "page": 1, "size": size,
                "items": [{"code": "t_user", "kw": kw, "kind": kind}]}


def test_ontology_degrades_without_tenant():
    assert OntologyTools.build(1, db=None, tenant_id=None) == []


def test_ontology_degrades_when_service_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.services.ontology.ontology_asset_service", None)
    assert OntologyTools.build(1, tenant_id=1) == []


def test_ontology_build_and_search(monkeypatch):
    tools = OntologyTools.build(1, db=object(), tenant_id=7)
    assert len(tools) == 1 and tools[0].name == "ontology_search"
    monkeypatch.setattr(
        "app.services.ontology.ontology_asset_service.OntologyAssetService",
        _FakeOntologySvc)
    out = _run(tools[0].call({"kw": "用户", "size": 5}))
    assert out["total"] == 1
    assert out["items"][0]["code"] == "t_user"
    assert out["items"][0]["kw"] == "用户"


# ---------------------------------------------------------------- Sandbox

def test_sandbox_build_and_exec():
    tools = SandboxTools.build(1)
    assert len(tools) == 1 and tools[0].name == "python_exec"
    out = _run(tools[0].call({
        "expr": {"op": "add", "a": {"op": "num", "v": "1.5"}, "b": {"op": "num", "v": "2"}},
    }))
    assert out == {"result": "3.5000"}  # Decimal 量化 4 位


def test_sandbox_prop_and_param():
    tool = SandboxTools.build(1)[0]
    out = _run(tool.call({
        "expr": {"op": "gt",
                 "a": {"op": "prop", "entity": "acct", "key": "balance"},
                 "b": {"op": "param", "key": "threshold"}},
        "props": {"acct.balance": "100"},
        "params": {"threshold": "99"},
    }))
    assert out == {"result": "True"}  # ast_eval 返回 Python bool


def test_sandbox_missing_ref_returns_error():
    tool = SandboxTools.build(1)[0]
    out = _run(tool.call({
        "expr": {"op": "prop", "entity": "acct", "key": "nope"},
        "props": {},
    }))
    assert out["error"].startswith("MISSING_PROP")


def test_sandbox_degrades_when_service_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.services.sandbox.ast_eval", None)
    assert SandboxTools.build(1) == []


# ---------------------------------------------------------------- Toolkit 组装

def test_local_tool_routing_and_errors():
    async def _ah(args):
        return {"async": args["x"]}

    tk = Toolkit(workspace_id=1, extra_tools={
        "sync_tool": LocalTool(name="sync_tool", description="", handler=lambda a: {"ok": True}),
        "async_tool": LocalTool(name="async_tool", description="", handler=_ah),
    })
    assert _run(tk.call("sync_tool", {})) == {"ok": True}
    assert _run(tk.call("async_tool", {"x": 1})) == {"async": 1}
    with pytest.raises(KeyError):
        _run(tk.call("nope", {}))
    with pytest.raises(KeyError):
        _run(tk.call("mcp:not_connected", {}))
    names = [d["name"] for d in tk.tool_descriptions()]
    assert names == ["sync_tool", "async_tool"]


@pytest.mark.asyncio
async def test_build_ticket_toolkit_combines(monkeypatch):
    """MCP connect 失败被捕获，本地工具照常组合。"""

    async def _fail_connect(self):
        raise RuntimeError("MCP server not installed")

    monkeypatch.setattr(
        "app.ai.superagent.tools.mcp_adapter.MCPClient.connect", _fail_connect)

    ticket = {
        "id": "T-0001",
        "workspace_id": 1,
        "config": {"mcp_ids": ["playwright", "windows-mcp"], "kb_ids": ["col-a"]},
        "tenant_id": 7,
    }
    tk = await MCPToolkitFactory.build_ticket_toolkit(ticket)
    assert set(tk.clients) == {"playwright", "windows-mcp"}
    assert tk.tools == {}  # connect 全失败 → 无 MCP 工具
    assert set(tk.extra_tools) == {"kb_search", "ontology_search", "python_exec"}


@pytest.mark.asyncio
async def test_build_ticket_toolkit_orm_style_ticket(monkeypatch):
    """ORM 对象形态的 ticket（getattr 读取）+ 默认 mcp_ids。"""

    async def _fail_connect(self):
        raise RuntimeError("MCP server not installed")

    monkeypatch.setattr(
        "app.ai.superagent.tools.mcp_adapter.MCPClient.connect", _fail_connect)

    ticket = SimpleNamespace(
        workspace_id=3, config={"kb_ids": ["kb1"]}, tenant_id=9, id="T-0002")
    tk = await MCPToolkitFactory.build_ticket_toolkit(ticket)
    assert "playwright" in tk.clients  # 默认启 Playwright
    assert set(tk.extra_tools) == {"kb_search", "ontology_search", "python_exec"}


# ---------------------------------------------------------------- 安全边界（Task 5.1）

def test_toolkit_unknown_mcp_server_keyerror():
    """Toolkit.call 对未注册的 MCP server 抛 KeyError —— 不静默降级（Task 2.3 安全边界）。"""
    tk = Toolkit(workspace_id=1, clients={"playwright": MCPClient("npx", ["-y", "x"])})
    with pytest.raises(KeyError, match="No MCP server"):
        _run(tk.call("nosuch_server:tool", {}))


def test_build_records_domain_whitelist(monkeypatch):
    """MCPToolkitFactory.build(domain_whitelist=...) —— 白名单被记录（Task 2.3）。"""
    recorded: list[str] = []

    class _CapLogger:
        def info(self, msg, *a, **k):
            recorded.append(str(msg))

        def error(self, msg, *a, **k):
            recorded.append(str(msg))

    monkeypatch.setattr("app.ai.superagent.tools.toolkit.logger", _CapLogger())
    # mcp_ids 不含已知 server → 不 spawn 子进程；domain_whitelist 仍被记录
    tk = _run(MCPToolkitFactory.build(
        1, mcp_ids=["unknown-mcp"], domain_whitelist=["example.com"]))
    assert any("example.com" in m for m in recorded)
    assert tk.clients == {}
