"""文件存储枚举：存储类型（对齐 Java FileStorageEnum）与业务 code。

FTP/SFTP/OSS 为预留扩展位，本期不实现客户端，枚举保留以便配置表兼容与后续扩展。
"""
from enum import IntEnum


class FileStorageEnum(IntEnum):
    DB = 1
    LOCAL = 10
    FTP = 11       # 预留
    SFTP = 12      # 预留
    S3 = 20
    OSS = 30       # 预留（本期通过 S3 兼容端点覆盖阿里云 OSS）

    @classmethod
    def supported(cls) -> tuple["FileStorageEnum", ...]:
        return (cls.DB, cls.LOCAL, cls.S3)

    @classmethod
    def is_supported(cls, storage: int) -> bool:
        try:
            return cls(int(storage)) in cls.supported()
        except (ValueError, TypeError):
            return False


# 业务 code：调用方按 code 选择存储配置，未指定时使用 master。
MASTER_CODE = "master"
BUSINESS_CODES = {
    "master": "默认主存储",
    "ai-image": "AI 图片",
    "kms": "知识库",
    "ability": "能力中心",
    "ai-examine": "AI 审查",
    "ai-legal-document": "法律文书",
    "ocr": "OCR",
    "tenant-kms": "租户知识库",
    "other": "其它",
}
