"""SemanticaClient 失败路径与能力探测测试（monkeypatch 假 import，不连真实后端）。"""
import importlib

import pytest

import app.services.semantica.client as client_mod
from app.services.semantica.client import SemanticaClient, SemanticaUnavailable


def test_is_available_true_when_installed():
    assert SemanticaClient.is_available() is True


def test_unavailable_when_semantica_missing(monkeypatch):
    """模拟 semantica 未安装时，探测返回 False 且调用抛 SemanticaUnavailable。"""
    orig = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name.startswith("semantica"):
            raise ImportError(f"no such module: {name}")
        return orig(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    importlib.reload(client_mod)
    try:
        assert client_mod.SemanticaClient.is_available() is False
        # 注意：reload 后 client_mod 内的 SemanticaUnavailable 是新类对象，
        # 必须用 reload 后的引用匹配，否则 pytest.raises 按旧类对象判定失败
        with pytest.raises(client_mod.SemanticaUnavailable):
            client_mod._import("semantica.kg")
    finally:
        importlib.reload(client_mod)  # 恢复真实 import_module


def test_extract_entities_uses_semantic_extract(monkeypatch):
    """map semantica.semantic_extract.named_entity_recognizer 调用真实（已安装）API。"""
    # semantica 已安装，仅验证 client 调用链路不抛 ImportError
    client = SemanticaClient()
    # 不实际抽取（需模型），只确认 extract_entities 方法存在且可调用签名
    assert callable(client.extract_entities)


# ── dict 入参归一（关系抽取回归）──────────────────────────────────────────
def test_to_entities_converts_dicts_to_entity_objects():
    """抽取器要的是带 ``.text`` 的 Entity，不是 dict。"""
    from semantica.semantic_extract.types import Entity

    out = client_mod._to_entities([
        {"text": "实体A", "label": "ORG"},
        {"name": "实体B"},          # 只有 name（本项目常见形态）
        "实体C",                     # 裸字符串
        Entity("实体D", "LOC", 0, 3),  # 已是对象则原样透传
    ])
    assert [e.text for e in out] == ["实体A", "实体B", "实体C", "实体D"]
    assert out[0].label == "ORG"
    assert out[2].label == ""


def test_to_entities_passes_through_non_list_and_objects():
    assert client_mod._to_entities(None) is None
    assert client_mod._to_entities([]) == []
    from semantica.semantic_extract.types import Entity

    ent = Entity("A", "ORG", 0, 1)
    assert client_mod._to_entities([ent]) == [ent]


class _RecordingTripletExtractor:
    """记录传进来的 entities，用于断言类型已归一。"""

    last_entities = None

    def extract_triplets(self, text, entities=None, relations=None, **kwargs):
        type(self).last_entities = entities
        return []


def test_extract_triplets_receives_entities_not_dicts(monkeypatch):
    """回归：dict 直传会让抽取器内部 ``entity.text`` 抛 AttributeError，
    表现为「抽取成功但 relations 恒为 0」。"""
    import sys
    import types

    _RecordingTripletExtractor.last_entities = None
    fake = types.ModuleType("semantica.semantic_extract.triplet_extractor")
    fake.TripletExtractor = _RecordingTripletExtractor
    monkeypatch.setitem(sys.modules, "semantica.semantic_extract.triplet_extractor", fake)

    SemanticaClient().extract_triplets("文本", entities=[{"text": "实体A", "label": "ORG"}])

    got = _RecordingTripletExtractor.last_entities
    assert got and got[0].text == "实体A"


def test_extract_relations_receives_entities_not_dicts(monkeypatch):
    import sys
    import types

    captured = {}

    class _FakeRelationExtractor:
        def extract(self, text, entities, **kwargs):
            captured["entities"] = entities
            return []

    fake = types.ModuleType("semantica.semantic_extract.relation_extractor")
    fake.RelationExtractor = _FakeRelationExtractor
    monkeypatch.setitem(sys.modules, "semantica.semantic_extract.relation_extractor", fake)

    SemanticaClient().extract_relations("文本", [{"text": "实体A"}])

    assert captured["entities"][0].text == "实体A"
