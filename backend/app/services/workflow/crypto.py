"""API Key 加解密工具 — 使用 Fernet 对称加密"""
import base64
import hashlib
from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    """从 SECRET_KEY 派生 Fernet 密钥（32 url-safe base64 字节）"""
    secret = getattr(settings, "SECRET_KEY", "default-secret-key")
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_api_key(plain_key: str) -> str:
    """加密 API Key"""
    f = _get_fernet()
    return f.encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key"""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()
