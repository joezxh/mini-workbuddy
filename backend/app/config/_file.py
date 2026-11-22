"""文件存储配置：客户端缓存、上传大小、压缩包解压限额与临时目录。"""
from pydantic import BaseModel


class FileStorageSettings(BaseModel):
    FILE_CLIENT_CACHE_TTL_SECONDS: int = 10

    # 压缩包解压任务（对齐 Java ArchiveExtractProperties）
    FILE_ARCHIVE_MAX_ENTRIES: int = 100
    FILE_ARCHIVE_MAX_ENTRY_SIZE: int = 50 * 1024 * 1024
    FILE_ARCHIVE_MAX_TOTAL_SIZE: int = 200 * 1024 * 1024
    FILE_ARCHIVE_MAX_RATIO: int = 200
    FILE_ARCHIVE_TASK_TTL_MINUTES: int = 30
    FILE_ARCHIVE_TASK_TIMEOUT_MINUTES: int = 5
    FILE_ARCHIVE_TASK_TEMP_DIR: str = ""
