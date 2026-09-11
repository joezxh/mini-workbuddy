"""Embedding 配置映射（P1 Task 7）：MWB provider → 检索管线所需的连接配置。

纯配置映射，**不写自定义 EmbeddingModel**（已核实本地 agentscope 2.0.7.post1 的
``agentscope.model`` 只有 Chat 模型、无 embedding 类）。MWB 侧向量生成统一走
``app.ai.embedding_client``（协议由本模块映射决定）：

- ``gpustack``  → OpenAI 兼容协议（``/embeddings`` 端点），指向本地 GPUStack
- ``nvidia``    → OpenAI 兼容协议，指向 NVIDIA NIM（``NVIDIA_*`` 配置）
- ``dashscope`` → DashScope 原生协议（非 OpenAI 兼容），指向阿里百炼

映射规则上线即冻结；新增 provider 需同步扩展 ``app.ai.embedding_client`` 后端。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings

# 协议标识：openai = OpenAI 兼容 /v1/embeddings；dashscope = 百炼原生 HTTP
PROTOCOL_OPENAI = "openai"
PROTOCOL_DASHSCOPE = "dashscope"

# 支持的 provider 列表（供 /embedding_models 端点与前端下拉使用）
SUPPORTED_PROVIDERS = ("gpustack", "nvidia", "dashscope")


@dataclass(frozen=True)
class EmbeddingConfig:
    """单个 provider 的 embedding 连接配置。"""

    provider: str      # gpustack | dashscope
    protocol: str      # openai | dashscope
    base_url: str
    api_key: str
    model: str
    dimension: int


def resolve_embedding_config(provider: str | None = None) -> EmbeddingConfig:
    """按 provider 名解析 embedding 配置；不传则用 ``settings.EMBEDDING_PROVIDER``。

    :raises ValueError: provider 不受支持时（显式失败，不静默降级）
    """
    name = (provider or settings.EMBEDDING_PROVIDER or "gpustack").lower().strip()

    if name == "dashscope":
        return EmbeddingConfig(
            provider="dashscope",
            protocol=PROTOCOL_DASHSCOPE,
            base_url=settings.DASHSCOPE_API_URL,
            api_key=settings.ALIBABA_API_KEY,
            model=settings.DASHSCOPE_EMBEDDING_MODEL,
            dimension=settings.DASHSCOPE_EMBEDDING_DIMENSION,
        )

    if name == "nvidia":
        return EmbeddingConfig(
            provider="nvidia",
            protocol=PROTOCOL_OPENAI,
            base_url=settings.NVIDIA_API_URL,
            api_key=settings.NVIDIA_API_KEY,
            model=settings.NVIDIA_EMBEDDING_MODEL,
            dimension=settings.NVIDIA_EMBEDDING_DIMENSION,
        )

    if name == "gpustack":
        return EmbeddingConfig(
            provider="gpustack",
            protocol=PROTOCOL_OPENAI,
            base_url=settings.GPUSTACK_API_URL,
            api_key=settings.GPUSTACK_API_KEY,
            model=settings.GPUSTACK_EMBEDDING_MODEL,
            dimension=settings.GPUSTACK_EMBEDDING_DIMENSION,
        )

    raise ValueError(
        f"不支持的 EMBEDDING_PROVIDER={name!r}，可选：{', '.join(SUPPORTED_PROVIDERS)}"
    )


def describe_embedding_config(cfg: EmbeddingConfig) -> dict:
    """把配置转为可对外展示的 dict（api_key 脱敏，绝不外泄明文）。"""
    key = cfg.api_key or ""
    masked = f"***{key[-4:]}" if len(key) >= 4 else ("***" if key else "")
    return {
        "provider": cfg.provider,
        "protocol": cfg.protocol,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "dimension": cfg.dimension,
        "api_key_masked": masked,
        "api_key_configured": bool(key),
    }
