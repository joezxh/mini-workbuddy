"""Fernet 凭据加密测试（P2 Task 1）。"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.ai.dataops.crypto import decrypt_secret, encrypt_secret, generate_key
from app.config import settings


@pytest.fixture
def key(monkeypatch) -> str:
    k = generate_key()
    monkeypatch.setattr(settings, "DATAOPS_ENCRYPTION_KEY", k)
    return k


def test_roundtrip(key):
    token = encrypt_secret("p@ssw0rd")
    assert token != "p@ssw0rd"
    assert "p@ssw0rd" not in token
    assert decrypt_secret(token) == "p@ssw0rd"


def test_token_unique_per_call(key):
    """Fernet 带随机 nonce：同一明文两次加密产生不同 token（防彩虹对比）。"""
    assert encrypt_secret("same") != encrypt_secret("same")


def test_missing_key_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "DATAOPS_ENCRYPTION_KEY", "")
    with pytest.raises(RuntimeError):
        encrypt_secret("x")


def test_tampered_token_rejected(key):
    token = encrypt_secret("secret")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(Exception):
        decrypt_secret(tampered)


def test_wrong_key_rejected(monkeypatch, key):
    token = encrypt_secret("secret")
    monkeypatch.setattr(settings, "DATAOPS_ENCRYPTION_KEY", generate_key())
    with pytest.raises(Exception):
        decrypt_secret(token)
