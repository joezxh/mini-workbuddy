"""审计日志配置"""
from pydantic import BaseModel


class AuditSettings(BaseModel):
    """审计日志配置字段"""
    AUDIT_LOG_ENABLED: bool = False
    AUDIT_LOG_BATCH_SIZE: int = 20
    AUDIT_LOG_FLUSH_INTERVAL: float = 10.0
    AUDIT_LOG_SKIP_METHODS: str = "GET"
    AUDIT_LOG_MASK_FIELDS: str = "password,oldPassword,newPassword,token,secret,apiKey,accessKey,accessToken,refreshToken,secretKey"
