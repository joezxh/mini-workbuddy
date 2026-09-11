"""Embedding 配置映射测试（P1 Task 7）。

验证 provider → 协议/地址/模型/维度的映射，api_key 脱敏，未知 provider 显式失败，
以及 /embedding_models 端点可达。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.kb.embedding_config import (
    PROTOCOL_DASHSCOPE,
    PROTOCOL_OPENAI,
    describe_embedding_config,
    resolve_embedding_config,
)


def test_gpustack_maps_to_openai_protocol(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gpustack")
    monkeypatch.setattr(settings, "GPUSTACK_API_URL", "http://192.168.40.30/v1")
    monkeypatch.setattr(settings, "GPUSTACK_EMBEDDING_MODEL", "Qwen3-Embedding-4B")
    monkeypatch.setattr(settings, "GPUSTACK_EMBEDDING_DIMENSION", 768)

    cfg = resolve_embedding_config()
    assert cfg.provider == "gpustack"
    assert cfg.protocol == PROTOCOL_OPENAI
    assert cfg.base_url == "http://192.168.40.30/v1"
    assert cfg.model == "Qwen3-Embedding-4B"
    assert cfg.dimension == 768


def test_dashscope_maps_to_native_protocol(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "dashscope")
    monkeypatch.setattr(settings, "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3")
    monkeypatch.setattr(settings, "DASHSCOPE_EMBEDDING_DIMENSION", 1024)

    cfg = resolve_embedding_config()
    assert cfg.provider == "dashscope"
    assert cfg.protocol == PROTOCOL_DASHSCOPE
    assert cfg.model == "text-embedding-v3"
    assert cfg.dimension == 1024


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "no-such")
    with pytest.raises(ValueError):
        resolve_embedding_config()


def test_nvidia_maps_to_openai_protocol(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "nvidia")
    monkeypatch.setattr(settings, "NVIDIA_API_URL", "http://localhost:8080/v1")
    monkeypatch.setattr(settings, "NVIDIA_EMBEDDING_MODEL", "Qwen3-Embedding-4B")
    monkeypatch.setattr(settings, "NVIDIA_EMBEDDING_DIMENSION", 768)

    cfg = resolve_embedding_config()
    assert cfg.provider == "nvidia"
    assert cfg.protocol == PROTOCOL_OPENAI
    assert cfg.base_url == "http://localhost:8080/v1"
    assert cfg.dimension == 768


def test_describe_masks_api_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gpustack")
    monkeypatch.setattr(settings, "GPUSTACK_API_KEY", "gpustack_abcdef123456")
    cfg = resolve_embedding_config()
    d = describe_embedding_config(cfg)
    assert d["api_key_masked"] == "***3456"
    assert d["api_key_configured"] is True
    # 明文绝不外泄
    assert "gpustack_abcdef123456" not in str(d)


def test_embedding_models_endpoint():
    from app.services.kb.kb_app import kb_app

    with TestClient(kb_app) as client:
        r = client.get("/embedding_models")
        assert r.status_code == 200
        body = r.json()
        assert body["current"]["provider"] in ("gpustack", "nvidia", "dashscope")
        assert set(body["supported"]) == {"gpustack", "nvidia", "dashscope"}
