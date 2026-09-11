"""Task 9：本体 Agent 工具测试。

会话注入：ToolBase.call 内部自建会话（生产走 SessionLocal），测试通过
`session_factory` 构造参数注入 conftest 的 schema-per-test 会话工厂。
用户上下文：`bind_tool_user(ToolUserContext(...))` 旁路通道。
"""
from __future__ import annotations

import asyncio
import json

from agentscope.tool import ToolBase
from sqlalchemy.orm import sessionmaker

from app.ai.tool_manager.tool_context import ToolUserContext, bind_tool_user
from app.ai.tools.ontology_tools import (
    OntologyAnswerCqTool,
    OntologyQueryTool,
    OntologySuggestTool,
)
from app.models.sys.sys_user import SysUser
from app.services.ontology.modeling_service import (
    MetaTableRef,
    ModelingService,
)

from .conftest import TENANT_A, TENANT_B, engine_for, open_session

TOOL_USER_ID = 101


def _setup(db_target: str):
    """建表 + 工具用户 + 会话工厂（每个测试独立 schema）。"""
    eng = engine_for(db_target, create_tables=True)
    factory = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    sess = factory()
    sess.add(SysUser(
        user_id=TOOL_USER_ID,
        username="tool-user",
        password_hash="x",
        real_name="工具用户",
        status="active",
        is_admin=False,
        tenant_id=TENANT_A,
    ))
    sess.commit()
    sess.close()
    return eng, factory


def _payload(chunk) -> dict:
    block = chunk.content[0]
    text = block["text"] if isinstance(block, dict) else block.text
    return json.loads(text)


def _run(tool: ToolBase, **kwargs) -> dict:
    ctx = ToolUserContext(user_id=TOOL_USER_ID, username="tool-user")
    with bind_tool_user(ctx):
        return _payload(asyncio.run(tool.call(**kwargs)))


# ── 1. ontology_query ─────────────────────────────────────────────────────────

def test_query_stats_and_properties(db_target: str) -> None:
    eng, factory = _setup(db_target)
    try:
        sess = factory()
        ModelingService(sess, TENANT_A).add_object_type("customer", "客户")
        sess.commit()

        tool = OntologyQueryTool(session_factory=factory)
        stats = _run(tool, action="stats")
        assert stats["class_count"] == 0        # OWL 层无类
        assert stats["cq_coverage"] == 0.0

        props = _run(tool, action="properties", object_type_code="customer")
        assert props == []                       # 尚无属性

        _run(tool, action="consistency")         # 不抛错即接口可用
    finally:
        sess.close()
        eng.dispose()


def test_query_requires_tenant(db_target: str) -> None:
    """无租户用户 → tenant_required（IM-07 语义在 Tool 侧一致）。"""
    eng, factory = _setup(db_target)
    sess = factory()
    try:
        # 构造一个无租户的用户（tenant_id=None）
        sess.add(SysUser(
            user_id=999, username="no-tenant", password_hash="x",
            real_name="无租户用户", status="active", is_admin=False, tenant_id=None,
        ))
        sess.commit()
        tool = OntologyQueryTool(session_factory=factory)
        ctx = ToolUserContext(user_id=999, username="no-tenant")
        with bind_tool_user(ctx):
            payload = _payload(asyncio.run(tool.call(action="stats")))
        assert payload["error"] == "tenant_required"
    finally:
        sess.close()
        eng.dispose()


# ── 2. ontology_answer_cq ─────────────────────────────────────────────────────

def test_answer_cq_reports_coverage_and_uncovered(db_target: str) -> None:
    eng, factory = _setup(db_target)
    sess = factory()
    try:
        svc = ModelingService(sess, TENANT_A)
        svc.add_object_type("customer", "客户")
        svc.add_cq("列出所有客户", linked_object_codes=["customer"])
        svc.add_cq("客户签了哪些合同")
        sess.commit()

        tool = OntologyAnswerCqTool(session_factory=factory)
        payload = _run(tool)
        assert payload["cq_coverage"] == 0.5
        assert payload["covered"] == 1
        assert payload["uncovered"] == ["客户签了哪些合同"]

        filtered = _run(tool, question="合同")
        assert filtered["total"] == 1 and filtered["uncovered"] == ["客户签了哪些合同"]
    finally:
        sess.close()
        eng.dispose()


# ── 3. ontology_suggest（写操作）──────────────────────────────────────────────

def test_suggest_generates_candidates(db_target: str) -> None:
    eng, factory = _setup(db_target)
    sess = factory()
    try:
        tool = OntologySuggestTool(session_factory=factory)
        payload = _run(tool, tables=[
            {"source_id": "s1", "database": "dw", "table_name": "t_customer",
             "comment": "客户表"},
        ], columns=[
            {"source_id": "s1", "database": "dw", "table_name": "t_customer",
             "column_name": "cust_name", "confidence": 0.9},
        ], column_pairs=[])

        assert payload["created"]["object_type"] == 1
        assert payload["created"]["property"] == 1

        # 幂等：重复提交不重复生成
        again = _run(tool, tables=[
            {"source_id": "s1", "database": "dw", "table_name": "t_customer"},
        ], columns=[], column_pairs=[])
        assert again["created"].get("object_type", 0) == 0
    finally:
        sess.close()
        eng.dispose()


def test_suggest_validates_input(db_target: str) -> None:
    """悬空引用（引用不存在的对象类型）返回错误而不是 500/脏数据。"""
    eng, factory = _setup(db_target)
    sess = factory()
    try:
        tool = OntologySuggestTool(session_factory=factory)
        payload = _run(tool, columns=[
            {"source_id": "s1", "database": "dw", "table_name": "t_ghost",
             "column_name": "x"},
        ], column_pairs=[], tables=[])
        # t_ghost 不在 tables 里 → 列被跳过（不是错误），可追溯
        assert payload["created"].get("property", 0) == 0

        # 表名空白 → 输入校验错误
        bad = _run(tool, tables=[
            {"source_id": "s1", "database": "dw", "table_name": "   "},
        ], columns=[], column_pairs=[])
        assert "error" in bad
    finally:
        sess.close()
        eng.dispose()


def test_suggest_is_tenant_scoped(db_target: str) -> None:
    """同一批元数据由租户 B 的用户提交，不影响租户 A 的本体。"""
    eng, factory = _setup(db_target)
    sess = factory()
    try:
        # 先给 B 的用户造行
        sess.add(SysUser(
            user_id=102, username="tool-user-b", password_hash="x",
            real_name="B租户用户", status="active", is_admin=False, tenant_id=TENANT_B,
        ))
        sess.commit()

        ModelingService(sess, TENANT_A).add_object_type("t_customer", "客户A")
        sess.commit()

        tool = OntologySuggestTool(session_factory=factory)
        ctx = ToolUserContext(user_id=102, username="tool-user-b")
        with bind_tool_user(ctx):
            payload = _payload(asyncio.run(tool.call(tables=[
                {"source_id": "s1", "database": "dw", "table_name": "t_customer"},
            ], columns=[], column_pairs=[])))
        # B 从零生成自己的候选；A 的数据不受影响
        assert payload["created"]["object_type"] == 1
        a_rows = ModelingService(sess, TENANT_A).list_object_types()
        assert [r.name for r in a_rows] == ["客户A"]
    finally:
        sess.close()
        eng.dispose()


def test_tools_are_toolbase_subclasses() -> None:
    """三个工具必须是 ToolBase 子类（ToolManager.register 的入参要求）。"""
    for cls in (OntologyQueryTool, OntologyAnswerCqTool, OntologySuggestTool):
        assert issubclass(cls, ToolBase)
        assert cls.name and cls.description and cls.input_schema
