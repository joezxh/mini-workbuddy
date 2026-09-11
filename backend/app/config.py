import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from urllib.parse import quote_plus
from pathlib import Path


# 项目根目录（backend/ 上一级），避免 settings.BASE_DIR 未定义崩溃。
# 支持通过环境变量 APP_BASE_DIR 显式覆盖，以适配 Docker 容器：
# WORKDIR=/app 且 COPY app ./app 时，__file__ 三级上溯会算成 / 而非 /app，
# 导致所有 _BASE_DIR/"backend"/... 路径与挂载卷（/app/data/...）对不上。
_BASE_DIR = Path(os.environ.get("APP_BASE_DIR", Path(__file__).resolve().parent.parent.parent))


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    APP_NAME: str = "MiniWorkBuddy"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 启动建表开关：True 时使用 Base.metadata.create_all（开发/小环境）；
    # 生产环境请置 False 并改用 `alembic upgrade head`，避免与迁移脚本漂移。
    AUTO_CREATE_TABLES: bool = True

    # 项目路径
    BASE_DIR: Path = _BASE_DIR
    UPLOAD_DIR: Path = _BASE_DIR / "backend" / "uploads" / "ai_files"
    FILE_STORAGE_DIR: Path = _BASE_DIR / "backend" / "uploads" / "infra_files"

    # AgentScope Workspace 根目录
    # 留空时自动检测运行环境:
    #   - Docker 容器内: /data/workspaces
    #   - Windows PC: %APPDATA%/minworkbuddy/workspace
    #   - macOS/Linux PC: ~/.minworkbuddy/workspace
    WORKSPACE_BASE_DIR: str = ""

    # 技能（skill）文件根目录
    # 多实例部署时，运维可将此路径映射到共享存储（如 NFS 挂载、或 MinIO 通过
    # 挂载工具映射到本地目录）；留空则默认使用 backend/data/skills。
    # 支持绝对路径或相对路径（相对项目根目录 _BASE_DIR）。
    SKILLS_BASE_DIR: str = ""

    # 技能仓库（Skill Hub）本地克隆缓存目录
    # 第三方/官方 git 仓库首次访问时 clone 到此目录，之后从缓存读取 skills/ 与 category_index.json。
    # 留空则默认 <项目根>/data/hub_cache。支持绝对路径或相对 _BASE_DIR 的相对路径。
    # 建议填相对路径 data/hub_cache：可跨机器/容器移植，避免写死盘符。
    HUB_CACHE_DIR: str = ""

    # 官方技能仓库（Skill Hub）Git 地址（默认展示，不可删除）
    OFFICIAL_HUB_URL: str = "http://gitlab.hztianque.com/tianQAI/tianque-skills.git"
    OFFICIAL_HUB_BRANCH: str = "main"
    # 官方仓库只读访问账号密码（私有 GitLab 需鉴权时使用）
    # 仅用于 git clone 时以 https://user:pass@host/... 方式注入，不显示在仓库地址中
    OFFICIAL_HUB_USERNAME: str = ""
    OFFICIAL_HUB_PASSWORD: str = ""

    # SkillHub 云市场（source_type=skillhub 的官方仓库）
    # API Key 通过请求头 X-API-Key 注入；留空时走公共接口（部分技能可能无法下载）
    SKILLHUB_API_KEY: str = ""
    SKILLHUB_BASE_URL: str = "https://api.skillhub.cn"

    # 数据库配置
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "minworkbuddy"
    DATABASE_ECHO: bool = True  # 开发环境输出SQL语句
    
    # 数据库连接池配置
    DB_POOL_SIZE: int = 30           # 常驻连接数
    DB_MAX_OVERFLOW: int = 20        # 最大溢出连接数
    DB_POOL_TIMEOUT: int = 30        # 获取连接超时（秒）
    DB_POOL_RECYCLE: int = 1800      # 连接回收时间（30分钟）

    # asyncio 全局线程池大小（影响 asyncio.to_thread 并发上限）
    # 公式：migration_concurrency × 3（all类型Phase1）+ 缓冲 5
    # 例：concurrency=5 → 5×3+5=20，取整留余量设25
    # 若未配置，Python默认值为 min(32, cpu_count+4)
    THREAD_POOL_MAX_WORKERS: int = 25
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接 URL（密码进行 URL 编码）"""
        password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        """构建 Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            password = quote_plus(self.REDIS_PASSWORD)
            return f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-this-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小时
        
    # CORS 配置（字符串，逗号分隔）
    CORS_ORIGINS: str = "*"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """将 CORS_ORIGINS 字符串转换为列表"""
        # 如果配置为 "*"，返回 ["*"] 允许所有源
        if self.CORS_ORIGINS == "*":
            return ["*"]
        if self.CORS_ORIGINS.startswith('['):
            # 如果是 JSON 数组格式，解析它
            import json
            try:
                return json.loads(self.CORS_ORIGINS)
            except:
                pass
        # 否则按逗号分隔
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]

    @property
    def resolved_workspace_base_dir(self) -> str:
        """解析 AgentScope Workspace 根目录。

        优先级:
        1. 环境变量 WORKSPACE_BASE_DIR 显式配置
        2. Docker 容器内自动检测 → /data/workspaces
        3. Windows PC → %APPDATA%/miniworkbuddy/workspace
        4. macOS/Linux PC → ~/.miniworkbuddy/workspace
        """
        if self.WORKSPACE_BASE_DIR:
            return self.WORKSPACE_BASE_DIR

        import os
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
        """解析技能（skill）文件根目录。

        多实例部署时，运维可将 SKILLS_BASE_DIR 映射到共享存储
        （NFS 挂载、或 MinIO/对象存储通过挂载工具映射到本地目录）。

        优先级:
        1. 环境变量 SKILLS_BASE_DIR 显式配置（绝对路径或相对 _BASE_DIR 的相对路径）
        2. 默认 backend/data/skills
        """
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
        # 默认指向项目根目录下的 data/hub_cache（与 data/workspace 同级），
        # 不再使用旧的 backend/data/hub_cache。
        return _BASE_DIR / "data" / "hub_cache"

    # Dify 配置（保留用于知识增强等场景，主 AI 引擎已切换到 AgentScope）
    DIFY_API_URL: str = ""
    DIFY_API_KEY: str = ""
    DIFY_WORKFLOW_HTTP_TIMEOUT_SECONDS: float = 1800.0
    
    # GPUStack Embedding 配置（OpenAI 兼容模式）
    GPUSTACK_API_URL: str = "http://192.168.40.30/v1"
    GPUSTACK_API_KEY: str = "gpustack_ee60e8a2e89f94f2_f7106a2810b92acda3a3a338991caf28"
    GPUSTACK_EMBEDDING_MODEL: str = "Qwen3-Embedding-4B"
    GPUSTACK_EMBEDDING_DIMENSION: int = 768  # Qwen3-Embedding-4B 向量维度

    # NVIDIA NIM Embedding 配置（OpenAI 兼容模式，EMBEDDING_PROVIDER=nvidia 时生效）
    NVIDIA_API_URL: str = "http://localhost:8080/v1"
    NVIDIA_API_KEY: str = ""
    NVIDIA_EMBEDDING_MODEL: str = "Qwen3-Embedding-4B"
    NVIDIA_EMBEDDING_DIMENSION: int = 768
    NVIDIA_CHAT_MODEL: str = "qwen3-32b"

    # RAG Service 上传文件的本地 blob 存储根目录（P1 Task 1）
    # 留空则默认 <项目根>/data/kb_blobs
    KB_BLOB_DIR: str = ""
    # GPUStack 对话/Chat 模型（用于知识增强 LLM 辅助标注建议）
    GPUSTACK_CHAT_MODEL: str = "qwen3-32b"   # 对话模型名称（Agent 流程默认使用）

    # 阿里百炼配置
    ALIBABA_API_KEY: str = ""
    ALIBABA_API_URL: str = ""
    # 百炼 Embedding 配置（当 EMBEDDING_PROVIDER=dashscope 时生效）
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"     # 百炼向量模型名称
    DASHSCOPE_EMBEDDING_DIMENSION: int = 1024                # 向量维度（text-embedding-v3 最大 1024）
    # 原生 DashScope HTTP 接口基础地址（固定值，一般不需修改）
    DASHSCOPE_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"

    # Embedding 提供商选择：gpustack | dashscope
    EMBEDDING_PROVIDER: str = "gpustack"

    # 统一向量维度配置（根据 EMBEDDING_PROVIDER 自动选择）
    @property
    def EMBEDDING_DIMENSION(self) -> int:
        """根据 EMBEDDING_PROVIDER 自动返回对应的向量维度"""
        provider = self.EMBEDDING_PROVIDER.lower().strip()
        if provider == "dashscope":
            return self.DASHSCOPE_EMBEDDING_DIMENSION
        if provider == "nvidia":
            return self.NVIDIA_EMBEDDING_DIMENSION
        return self.GPUSTACK_EMBEDDING_DIMENSION

    # Magic API 配置
    MAGIC_API_URL: str = ""

    # DataOps 数据源凭据加密密钥（Fernet，32 字节 url-safe base64）。
    # 独立密钥，不得复用 SECRET_KEY（默认值硬编码且密钥混用）。
    # 未配置时加密/解密显式报错，拒绝降级为明文存储。
    # 生成方式：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    DATAOPS_ENCRYPTION_KEY: str = ""

    # 文件上传配置
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB

    # 审计日志配置
    AUDIT_LOG_ENABLED: bool = False              # 审计日志总开关（不影响权限检查）
    AUDIT_LOG_BATCH_SIZE: int = 20              # 异步批量写入：每批条数
    AUDIT_LOG_FLUSH_INTERVAL: float = 10.0       # 异步批量写入：最大等待秒数
    AUDIT_LOG_SKIP_METHODS: str = "GET"          # 跳过审计日志的 HTTP 方法（逗号分隔）
    AUDIT_LOG_MASK_FIELDS: str = "password,oldPassword,newPassword,token,secret,apiKey,accessKey,accessToken,refreshToken,secretKey"  # 敏感字段脱敏列表（逗号分隔）

    # 日志配置
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE: str = "./logs/app.log"
    
    # 搜索服务配置 - 博查
    BOCHA_ENABLED: bool = True
    BOCHA_API_BASE_URL: str = "https://api.bocha.com"
    BOCHA_API_KEY: str = ""
    BOCHA_API_SECRET: str = ""
    BOCHA_TIMEOUT: int = 30
    BOCHA_MAX_RESULTS: int = 50
    BOCHA_DAILY_QUOTA: int = 1000
    
    # 搜索服务配置 - 数眼智能
    SHUYAN_ENABLED: bool = True
    SHUYAN_API_BASE_URL: str = "https://api.shuyanai.com/v1"
    SHUYAN_API_KEY: str = ""
    SHUYAN_TIMEOUT: int = 30
    SHUYAN_MAX_RESULTS: int = 50
    SHUYAN_DAILY_QUOTA: int = 500
    SHUYAN_PRIORITY: int = 1
    
    # 搜索服务配置 - 安思派
    ANSPIRE_ENABLED: bool = True
    ANSPIRE_API_BASE_URL: str = "https://api.anspire.com/v1"
    ANSPIRE_API_KEY: str = ""
    ANSPIRE_TIMEOUT: int = 30
    ANSPIRE_MAX_RESULTS: int = 50
    ANSPIRE_DAILY_QUOTA: int = 500
    ANSPIRE_PRIORITY: int = 2
    
    # 搜索服务配置 - Firecrawl
    FIRECRAWL_ENABLED: bool = True
    FIRECRAWL_API_BASE_URL: str = "http://localhost:3002"
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_TIMEOUT: int = 60
    FIRECRAWL_MAX_RESULTS: int = 100
    FIRECRAWL_DAILY_QUOTA: int = 10000
    FIRECRAWL_PRIORITY: int = 99
    
    # 搜索服务通用配置
    SEARCH_AUTO_FALLBACK: bool = True
    SEARCH_RETRY_TIMES: int = 3
    SEARCH_CACHE_ENABLED: bool = True
    SEARCH_CACHE_TTL: int = 3600

    # 异步任务队列提供商（celery | arq）
    TASK_QUEUE_PROVIDER: str = "celery"

    # Celery配置（TASK_QUEUE_PROVIDER=celery时生效）
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ARQ配置（TASK_QUEUE_PROVIDER=arq时生效）
    ARQ_REDIS_HOST: str = "localhost"
    ARQ_REDIS_PORT: int = 6379
    ARQ_REDIS_DB: int = 0
    ARQ_MAX_JOBS: int = 10
    ARQ_JOB_TIMEOUT: int = 180
    ARQ_MAX_TRIES: int = 3
    ENABLE_ARQ: bool = False

    # ------------------------------------------------------------------
    # SCHEDULED 模式（agent_async_task）调度参数配置
    # 注意：agent_async_task 走进程内 APScheduler（app.state.scheduler_service），
    # 与 TASK_QUEUE_PROVIDER 控制的事件处理流水线（celery/arq）互不影响。
    # ------------------------------------------------------------------
    ASYNC_TASK_MAX_CONCURRENCY: int = 3          # 全局并发上限（Semaphore）
    ASYNC_TASK_BACKOFF_BASE: float = 30.0        # 重试指数退避基数（秒）
    ASYNC_TASK_BACKOFF_CAP: float = 600.0        # 退避上限（秒）
    ASYNC_TASK_ALERT_FAILURE_RATE: float = 0.3   # 失败率告警阈值
    ASYNC_TASK_FAILURE_ALERT_ENABLED: bool = False
    ASYNC_TASK_FAILURE_ALERT_WEBHOOK: str = ""   # 钉钉/飞书/Slack webhook
    ASYNC_TASK_SCHEDULER_PRIMARY_ONLY: bool = False  # 多 worker 时仅主进程注册 job

    # OpenTelemetry 可观测性配置
    OTEL_ENABLED: bool = True                          # 是否启用链路追踪
    OTEL_SERVICE_NAME: str = "minworkbuddy"     # 服务名称
    OTEL_EXPORTER: str = "console"                    # 导出器类型: console | jaeger | otlp
    OTEL_JAEGER_AGENT_HOST: str = "localhost"         # Jaeger Agent 地址
    OTEL_JAEGER_AGENT_PORT: int = 6831               # Jaeger Agent 端口
    OTEL_OTLP_ENDPOINT: str = "http://localhost:4317" # OTLP gRPC 端点
    OTEL_SAMPLE_RATE: float = 1.0                     # 采样率 0.0-1.0

    # 批量处理配置
    BATCH_SIZE: int = 20
    BATCH_MAX_CONCURRENT: int = 3
    
    # 查询优化配置
    QUERY_BATCH_SIZE: int = 500          # 批量查询分页大小
    QUERY_CACHE_ENABLED: bool = True      # 查询结果缓存
    QUERY_CACHE_TTL: int = 300           # 查询缓存5分钟

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

