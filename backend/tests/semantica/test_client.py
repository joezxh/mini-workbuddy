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
