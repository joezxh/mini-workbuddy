"""DataOps 数据源凭据加密（P2 Task 1）。

Fernet 对称加密，密钥来自 ``settings.DATAOPS_ENCRYPTION_KEY``（独立密钥，
不复用 ``SECRET_KEY``：其默认值是硬编码弱密钥，且密钥混用会放大泄露面）。

显式失败原则：密钥未配置时**拒绝降级为明文存储**，直接抛 ``RuntimeError``。
"""
from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    key = (settings.DATAOPS_ENCRYPTION_KEY or "").strip()
    if not key:
        raise RuntimeError(
            "DATAOPS_ENCRYPTION_KEY 未配置，拒绝降级为明文存储。"
            '生成方式：python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt_secret(raw: str) -> str:
    """加密明文（密码/API Key），返回可落库的 token。"""
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_secret(token: str) -> str:
    """解密落库 token；token 被篡改或密钥轮换不匹配时抛 InvalidToken。"""
    return _fernet().decrypt(token.encode()).decode()


def generate_key() -> str:
    """生成新密钥（运维工具函数，与 settings 配置解耦）。"""
    return Fernet.generate_key().decode()
