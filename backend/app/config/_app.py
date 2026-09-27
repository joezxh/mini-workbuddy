"""核心应用配置（路径、JWT、CORS、日志、第三方服务等）"""
import os
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

from ._env import _BASE_DIR


class AppSettings(BaseModel):
    """核心应用配置字段"""

    # ── 应用信息 ──────────────────────────────────────────────
    APP_NAME: str = "MiniWorkBuddy"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 启动建表开关：True 时使用 Base.metadata.create_all（开发/小环境）；
    # 生产环境请置 False 并改用 `alembic upgrade head`，避免与迁移脚本漂移。
    AUTO_CREATE_TABLES: bool = True

    # ── 项目路径 ──────────────────────────────────────────────
    BASE_DIR: Path = _BASE_DIR
    UPLOAD_DIR: Path = _BASE_DIR / "backend" / "uploads" / "ai_files"
    FILE_STORAGE_DIR: Path = _BASE_DIR / "backend" / "uploads" / "infra_files"

    # asyncio 全局线程池大小（影响 asyncio.to_thread 并发上限）
    THREAD_POOL_MAX_WORKERS: int = 25

    # ── 工作空间 & 技能 ──────────────────────────────────────
    # AgentScope Workspace 根目录
    # 留空时自动检测运行环境:
    #   - Docker 容器内: /data/workspaces
    #   - Windows PC: %APPDATA%/minworkbuddy/workspace
    #   - macOS/Linux PC: ~/.minworkbuddy/workspace
    WORKSPACE_BASE_DIR: str = ""

    # 技能（skill）文件根目录
    SKILLS_BASE_DIR: str = ""

    # 技能仓库（Skill Hub）本地克隆缓存目录
    HUB_CACHE_DIR: str = ""

    # 官方技能仓库 Git 地址
    OFFICIAL_HUB_URL: str = "http://gitlab.hztianque.com/tianQAI/tianque-skills.git"
    OFFICIAL_HUB_BRANCH: str = "main"
    OFFICIAL_HUB_USERNAME: str = ""
    OFFICIAL_HUB_PASSWORD: str = ""

    # SkillHub 云市场
    SKILLHUB_API_KEY: str = ""
    SKILLHUB_BASE_URL: str = "https://api.skillhub.cn"

    # ── JWT ───────────────────────────────────────────────────
    SECRET_KEY: str = "your-secret-key-change-this-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小时

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        """将 CORS_ORIGINS 字符串转换为列表"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        if self.CORS_ORIGINS.startswith('['):
            import json
            try:
                return json.loads(self.CORS_ORIGINS)
            except Exception:
                pass
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]

    # ── 路径解析属性 ──────────────────────────────────────────
    @property
    def resolved_workspace_base_dir(self) -> str:
        """解析 AgentScope Workspace 根目录。

        优先级:
        1. 环境变量 WORKSPACE_BASE_DIR 显式配置
        2. Docker 容器内自动检测 → /data/workspaces
        3. Windows PC → %APPDATA%/minworkbuddy/workspace
        4. macOS/Linux PC → ~/.minworkbuddy/workspace
        """
        if self.WORKSPACE_BASE_DIR:
            return self.WORKSPACE_BASE_DIR

        # Docker 容器检测
        if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER"):
            return "/data/workspaces"

        # PC 桌面端: 使用用户本地目录
        if os.name == "nt":  # Windows
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            return os.path.join(appdata, "minworkbuddy", "workspace")
        else:  # macOS / Linux
            return os.path.expanduser("~/.minworkbuddy/workspace")

    @property
    def resolved_skills_base_dir(self) -> Path:
        """解析技能（skill）文件根目录。"""
        raw = self.SKILLS_BASE_DIR.strip() if self.SKILLS_BASE_DIR else ""
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = _BASE_DIR / p
            return p
        return _BASE_DIR / "backend" / "data" / "skills"

    @property
    def hub_cache_path(self) -> Path:
        """技能仓库克隆缓存根目录。"""
        raw = self.HUB_CACHE_DIR.strip() if self.HUB_CACHE_DIR else ""
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = _BASE_DIR / p
            return p
        return _BASE_DIR / "data" / "hub_cache"

    # ── 第三方服务 ────────────────────────────────────────────
    # Dify（保留用于知识增强等场景，主 AI 引擎已切换到 AgentScope）
    DIFY_API_URL: str = ""
    DIFY_API_KEY: str = ""
    DIFY_WORKFLOW_HTTP_TIMEOUT_SECONDS: float = 1800.0

    # Magic API
    MAGIC_API_URL: str = ""

    # KB 子应用服务间调用凭证（spec 知识库统一化 T6）：空=禁用该通道（fail-closed）
    KB_SERVICE_TOKEN: str = ""

    # DataOps 数据源凭据加密密钥（Fernet，32 字节 url-safe base64）
    DATAOPS_ENCRYPTION_KEY: str = ""

    # RAG Service 上传文件的本地 blob 存储根目录
    KB_BLOB_DIR: str = ""

    # SQLBot 私有化部署（NL2SQL 数据源代理）
    SQLBOT_API_URL: str = ""
    SQLBOT_ACCESS_KEY: str = ""
    SQLBOT_SECRET_KEY: str = ""
    SQLBOT_DATASOURCE_ID: Optional[int] = None
    SQLBOT_TIMEOUT: int = 30

    # ── 文件上传 ──────────────────────────────────────────────
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB

    # ── 日志 ──────────────────────────────────────────────────
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE: str = "./logs/app.log"

    # ── 任务队列 ──────────────────────────────────────────────
    # 异步任务队列提供商（celery | arq）
    TASK_QUEUE_PROVIDER: str = "celery"

    # Celery 配置（TASK_QUEUE_PROVIDER=celery 时生效）
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ARQ 配置（TASK_QUEUE_PROVIDER=arq 时生效）
    ARQ_REDIS_HOST: str = "localhost"
    ARQ_REDIS_PORT: int = 6379
    ARQ_REDIS_DB: int = 0
    ARQ_MAX_JOBS: int = 10
    ARQ_JOB_TIMEOUT: int = 180
    ARQ_MAX_TRIES: int = 3
    ENABLE_ARQ: bool = False

    # ── 批量处理 & 查询优化 ───────────────────────────────────
    BATCH_SIZE: int = 20
    BATCH_MAX_CONCURRENT: int = 3
    QUERY_BATCH_SIZE: int = 500
    QUERY_CACHE_ENABLED: bool = True
    QUERY_CACHE_TTL: int = 300
