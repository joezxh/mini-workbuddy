"""API Key 加解密测试"""
import pytest
from app.services.workflow.crypto import encrypt_api_key, decrypt_api_key


def test_encrypt_decrypt_roundtrip():
    """加密后解密应还原"""
    original = "sk-test-1234567890abcdef"
    encrypted = encrypt_api_key(original)
    assert encrypted != original
    assert decrypt_api_key(encrypted) == original


def test_encrypt_produces_different_output():
    """同一明文两次加密结果不同（Fernet 含时间戳）"""
    original = "sk-test-key"
    e1 = encrypt_api_key(original)
    e2 = encrypt_api_key(original)
    # Fernet token 含时间戳，但解密后相同
    assert decrypt_api_key(e1) == decrypt_api_key(e2) == original


def test_decrypt_invalid_raises():
    """无效密文应抛异常"""
    with pytest.raises(Exception):
        decrypt_api_key("not-a-valid-fernet-token")
