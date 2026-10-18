"""Semantica 语义组件配置（本体 / 语义抽取 / 图谱构建 / 向量混合检索）。

semantica 以进程内 ``import semantica.*`` 方式接入，持久层使用 PostgreSQL
(pgvector 向量) + Neo4j（图存储）。Neo4j 与 Graphiti 长期记忆共用同一实例，
通过 ``GRAPHITI_GROUP_ID`` 做命名空间 / label 前缀隔离。

环境变量命名规范：``SEMANTICA_<PARAM>`` 与 ``NEO4J_<PARAM>`` / ``GRAPHITI_GROUP_ID``。
敏感字段（DB / Neo4j 密码）仅在运行期由 ``.env`` 提供，这里只放占位默认值。
"""
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, model_validator


class SemanticaSettings(BaseModel):
    """Semantica 配置字段。"""

    # ========== PostgreSQL（关系 + 向量存储后端） ==========
    SEMANTICA_DB_HOST: str = Field(default="localhost")
    SEMANTICA_DB_PORT: int = Field(default=5432)
    SEMANTICA_DB_USER: str = Field(default="ai-user")
    SEMANTICA_DB_PASSWORD: str = Field(
        default="", description="真实值由 .env 提供，勿提交明文"
    )
    SEMANTICA_DB_NAME: str = Field(default="miniworkbuddy")

    # ========== 向量存储 ==========
    SEMANTICA_VECTOR_BACKEND: str = Field(default="pgvector")
    SEMANTICA_VECTOR_DIM: int = Field(
        default=768, description="必须等于 GPUSTACK_EMBEDDING_DIMENSION，否则 pgvector 维度不匹配"
    )

    # ========== Neo4j（图存储后端，与 Graphiti 记忆共用实例） ==========
    NEO4J_ENABLED: bool = Field(default=True)
    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(
        default="neo4j", description="真实值由 .env 提供；与 Graphiti 默认保持一致"
    )
    GRAPHITI_GROUP_ID: str = Field(
        default="minworkbuddy",
        description="图分组 id：Graphiti 与 Semantica 共用此前缀做实例内隔离",
    )

    @property
    def db_url(self) -> str:
        """构建 semantica 专用的 PostgreSQL 连接 URL（密码做 URL 编码）。"""
        pw = quote_plus(self.SEMANTICA_DB_PASSWORD)
        return (
            f"postgresql://{self.SEMANTICA_DB_USER}:{pw}@"
            f"{self.SEMANTICA_DB_HOST}:{self.SEMANTICA_DB_PORT}/{self.SEMANTICA_DB_NAME}"
        )

    @property
    def namespace_prefix(self) -> str:
        """租户隔离命名空间前缀（如 ``minworkbuddy``），所有集合 / label 以此为根。"""
        return self.GRAPHITI_GROUP_ID

    @model_validator(mode="after")
    def _check_dimension(self) -> "SemanticaSettings":
        """向量维度必须与工程 embedding 维度一致，否则 pgvector 物理列维度冲突。"""
        dim = getattr(self, "GPUSTACK_EMBEDDING_DIMENSION", None)
        if dim is not None and self.SEMANTICA_VECTOR_DIM != dim:
            raise ValueError(
                f"SEMANTICA_VECTOR_DIM({self.SEMANTICA_VECTOR_DIM}) 必须等于 "
                f"GPUSTACK_EMBEDDING_DIMENSION({dim})，否则 pgvector 维度不匹配"
            )
        return self
