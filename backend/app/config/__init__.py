"""应用配置包 — 将单体 Settings 拆分为按领域分组的 mixin。

所有消费方无需改动：``from app.config import settings`` 仍然有效。
每个子模块定义一个 BaseModel mixin，最终通过多重继承组合为 Settings(BaseSettings)。

子模块清单:
  _env          共享基础常量（_BASE_DIR）
  _app          核心应用配置（路径、JWT、CORS、日志、第三方服务等）
  _database     数据库连接 & 连接池
  _redis        Redis 连接
  _search       搜索服务（博查 / 数眼 / 安思派 / Firecrawl）
  _voice        调解语音 RTC
  _embedding    Embedding 多供应商（GPUStack / NVIDIA / DashScope）
  _otel         OpenTelemetry 可观测性
  _audit        审计日志
  _async_task   异步任务调度参数
  _mem0         Mem0 长期记忆服务（本地私有化部署）
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from ._env import _BASE_DIR
from ._app import AppSettings
from ._database import DatabaseSettings
from ._redis import RedisSettings
from ._search import SearchSettings
from ._voice import VoiceSettings
from ._embedding import EmbeddingSettings
from ._otel import OTelSettings
from ._audit import AuditSettings
from ._async_task import AsyncTaskSettings
from ._mem0 import Mem0Settings
from ._cross_mode_recorder import CrossModeRecorderSettings


class Settings(
    AppSettings,
    DatabaseSettings,
    RedisSettings,
    SearchSettings,
    VoiceSettings,
    EmbeddingSettings,
    OTelSettings,
    AuditSettings,
    AsyncTaskSettings,
    Mem0Settings,
    CrossModeRecorderSettings,
    BaseSettings,
):
    """应用配置 — 组合所有领域 mixin。

    字段访问方式与原单体 Settings 完全一致：
        settings.DB_HOST
        settings.DATABASE_URL      # @property
        settings.EMBEDDING_DIMENSION  # @property
        settings.cors_origins_list    # @property
    """

    model_config = SettingsConfigDict(
        # 同时按相对 CWD 与按 _BASE_DIR 绝对路径查找 .env，
        # 无论从项目根目录、backend 目录还是其它目录启动都能命中配置，避免静默丢失。
        env_file=[
            ".env",
            "backend/.env",
            str(_BASE_DIR / ".env"),
            str(_BASE_DIR / "backend" / ".env"),
        ],
        case_sensitive=True,
        extra="ignore",  # 忽略未定义的字段
    )


settings = Settings()
