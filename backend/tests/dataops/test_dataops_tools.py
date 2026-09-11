"""P2 Task 14 测试：DataOps Agent 工具定义契约。

验证五个工具的定义能正确 seed（class_name 指向真实类、字段一致），以及工具类
的 AgentScope 协议类属性（name / input_schema / is_read_only）正确。
真实 DB 链路由各服务自身的集成测试覆盖。
"""
from __future__ import annotations

from app.ai.tools.dataops_tools import (
    DATAOPS_TOOL_KEYS, DataopsBindTool, DataopsInferRelationsTool, DataopsQueryTool,
    DataopsScanTool, DataopsWriteRequestTool, build_dataops_tool_definitions,
)


def test_tool_definitions_count_and_enabled():
    defs = build_dataops_tool_definitions()
    assert len(defs) == len(DATAOPS_TOOL_KEYS) == 5
    keys = {d.tool_key for d in defs}
    assert keys == set(DATAOPS_TOOL_KEYS)
    for d in defs:
        assert d.status == "enabled"
        assert d.is_system is True
        assert d.category == "数据治理"
        # class_name 必须能解析到真实类
        module_name, _, cls_name = d.class_name.rpartition(".")
        mod = __import__(module_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        assert cls is not None


def test_tool_class_attributes():
    specs = [
        (DataopsScanTool, "dataops_scan", False),
        (DataopsQueryTool, "dataops_query", True),
        (DataopsWriteRequestTool, "dataops_write_request", False),
        (DataopsBindTool, "dataops_bind", False),
        (DataopsInferRelationsTool, "dataops_infer_relations", False),
    ]
    for cls, name, read_only in specs:
        inst = cls(session_factory=lambda: None)
        assert inst.name == name
        assert inst.is_read_only is read_only
        assert "type" in inst.input_schema and inst.input_schema["type"] == "object"
