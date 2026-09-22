"""Mem0 长期记忆服务配置（本地私有化部署模式）"""
from pydantic import BaseModel, Field


class Mem0Settings(BaseModel):
    """Mem0 配置字段 - 支持本地私有化部署
    
    环境变量命名规范：MEM0_<PARAM_NAME>
    """
    
    # ========== 连接配置 ==========
    MEM0_RAG_URL: str = Field(
        default="",
        description="Mem0 RAG API 地址（本地私有化部署）"
    )
    
    MEM0_API_KEY: str = Field(
        default="",
        description="Mem0 API Key（用于认证）"
    )
    
    MEM0_MCP_HOST: str = Field(
        default="localhost",
        description="MCP 服务主机地址"
    )
    
    MEM0_MCP_PORT: int = Field(
        default=8080,
        description="MCP 服务端口"
    )
    
    # ========== 功能开关 ==========
    MEM0_ENABLED: bool = Field(
        default=False,
        description="是否启用 Mem0 长期记忆服务"
    )
    
    MEM0_USE_CLOUD_API: bool = Field(
        default=False,
        description="是否使用 Mem0 云端 API（本地私有化部署时设为 False）"
    )
    
    # ========== 存储与检索 ==========
    MEM0_MAX_ENTRIES: int = Field(
        default=10000,
        description="每个用户的最大记忆条目数"
    )
    
    MEM0_RETENTION_DAYS: int = Field(
        default=90,
        description="记忆保留天数（过期自动清理）"
    )
    
    MEM0_EMBEDDING_MODEL: str = Field(
        default="all-MiniLM-L6-v2",
        description="向量化模型名称"
    )
    
    MEM0_VECTOR_DIMENSION: int = Field(
        default=384,
        description="向量维度"
    )
    
    # ========== 性能与缓存 ==========
    MEM0_CACHE_TTL: int = Field(
        default=3600,
        description="记忆缓存 TTL（秒）"
    )
    
    MEM0_SEARCH_LIMIT: int = Field(
        default=10,
        description="默认检索返回的最大结果数"
    )
    
    MEM0_RETRIEVE_TOP_K: int = Field(
        default=5,
        description="语义搜索 Top-K 参数"
    )
    
    # ========== 压缩与优化（如果存在该接口）==========
    MEM0_ENABLE_COMPRESSION: bool = Field(
        default=False,
        description="是否启用记忆压缩（减少 Token 占用）"
    )
    
    MEM0_COMPLETION_TOKEN_LIMIT: int = Field(
        default=10000,
        description="记忆压缩后的 Token 上限"
    )
    
    # ========== 用户标识字段 ==========
    MEM0_USER_ID_FIELD: str = Field(
        default="user_id",
        description="用户 ID 字段名（用于区分不同用户的记忆）"
    )
    
    @property
    def mcp_endpoint(self) -> str:
        """构建 MCP 服务完整端点 URL"""
        return f"http://{self.MEM0_MCP_HOST}:{self.MEM0_MCP_PORT}"
    
    @property
    def is_local_deployment(self) -> bool:
        """判断是否为本地私有化部署模式"""
        return not self.MEM0_USE_CLOUD_API and bool(self.MEM0_RAG_URL)
