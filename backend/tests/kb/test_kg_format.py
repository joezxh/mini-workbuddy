"""图谱知识库（type=4）二级形态矩阵与强制约束（TDD - Red）。

覆盖：
- type=4 唯一合法形态为 ``graph``；
- type=4 强制 index_mode=high_quality、multimodal_enabled=False；
- 其它类型不受 normalize_graph_kb 影响（零回归）。
"""
import pytest
from fastapi import HTTPException


def test_type4_only_accepts_graph_format():
    from app.services.kb.kb_format import validate_kb_format

    assert validate_kb_format(4, "graph") == "graph"


@pytest.mark.parametrize("bad", ["document", "table", "qa", "connector", "proxy"])
def test_type4_rejects_other_formats(bad):
    from app.services.kb.kb_format import validate_kb_format

    with pytest.raises(HTTPException) as exc:
        validate_kb_format(4, bad)
    assert exc.value.status_code == 422


def test_type4_auto_fills_graph_format():
    """type=4 形态唯一：缺省自动补齐为 graph，客户端无需记忆 magic 字符串。"""
    from app.services.kb.kb_format import validate_kb_format

    assert validate_kb_format(4, None) == "graph"
    assert validate_kb_format(4, "graph") == "graph"


def test_normalize_graph_kb_forces_constraints():
    from app.services.kb.kb_format import normalize_graph_kb

    data = {
        "kb_format": "document",
        "index_mode": "economy",
        "multimodal_enabled": True,
    }
    normalize_graph_kb(4, data)
    assert data == {
        "kb_format": "graph",
        "index_mode": "high_quality",
        "multimodal_enabled": False,
    }


def test_normalize_graph_kb_ignores_other_types():
    from app.services.kb.kb_format import normalize_graph_kb

    data = {"kb_format": "qa", "index_mode": "economy", "multimodal_enabled": True}
    normalize_graph_kb(2, data)
    assert data == {"kb_format": "qa", "index_mode": "economy", "multimodal_enabled": True}

    normalize_graph_kb(3, data)
    assert data["kb_format"] == "qa"


def test_graph_kb_type_enum_exists():
    from app.models.wiki.wiki_knowledge import KnowledgeType

    assert KnowledgeType.GRAPH_KB == 4
    assert KnowledgeType.GRAPH_KB.name == "GRAPH_KB"


def test_external_type_must_be_null_for_type4():
    """type≠3 走 validate_external_type 的既有拒绝分支，无需额外规则。"""
    from app.services.kb.kb_format import validate_external_type

    assert validate_external_type(4, "graph", None) is None
    with pytest.raises(HTTPException):
        validate_external_type(4, "graph", "feishu")
