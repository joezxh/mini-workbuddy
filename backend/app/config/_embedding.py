"""Embedding 配置（多供应商）"""
from pydantic import BaseModel


class EmbeddingSettings(BaseModel):
    """Embedding 配置字段"""
    # GPUStack Embedding 配置（OpenAI 兼容模式）
    GPUSTACK_API_URL: str = "http://192.168.40.30/v1"
    GPUSTACK_API_KEY: str = "gpustack_ee60e8a2e89f94f2_f7106a2810b92acda3a3a338991caf28"
    GPUSTACK_EMBEDDING_MODEL: str = "Qwen3-Embedding-4B"
    GPUSTACK_EMBEDDING_DIMENSION: int = 768  # Qwen3-Embedding-4B 向量维度
    GPUSTACK_CHAT_MODEL: str = "qwen3-32b"

    # NVIDIA NIM Embedding 配置（OpenAI 兼容模式，EMBEDDING_PROVIDER=nvidia 时生效）
    NVIDIA_API_URL: str = "http://localhost:8080/v1"
    NVIDIA_API_KEY: str = ""
    NVIDIA_EMBEDDING_MODEL: str = "Qwen3-Embedding-4B"
    NVIDIA_EMBEDDING_DIMENSION: int = 768
    NVIDIA_CHAT_MODEL: str = "qwen3-32b"

    # 阿里百炼 / DashScope Embedding 配置（EMBEDDING_PROVIDER=dashscope 时生效）
    ALIBABA_API_KEY: str = ""
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"
    DASHSCOPE_EMBEDDING_DIMENSION: int = 1024
    DASHSCOPE_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"

    # Embedding 提供商选择：gpustack | dashscope | nvidia
    EMBEDDING_PROVIDER: str = "gpustack"

    @property
    def EMBEDDING_DIMENSION(self) -> int:
        """根据 EMBEDDING_PROVIDER 自动返回对应的向量维度"""
        provider = self.EMBEDDING_PROVIDER.lower().strip()
        if provider == "dashscope":
            return self.DASHSCOPE_EMBEDDING_DIMENSION
        if provider == "nvidia":
            return self.NVIDIA_EMBEDDING_DIMENSION
        return self.GPUSTACK_EMBEDDING_DIMENSION
