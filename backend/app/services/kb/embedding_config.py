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

import time as _time
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select

from app.config import settings

# 协议标识：openai = OpenAI 兼容 /v1/embeddings；dashscope = 百炼原生 HTTP
PROTOCOL_OPENAI = "openai"
PROTOCOL_DASHSCOPE = "dashscope"

# 支持的 provider 列表（供 /embedding_models 端点与前端下拉使用）
SUPPORTED_PROVIDERS = ("gpustack", "nvidia", "dashscope")

# 模型管理（数据字典 model_type）中「向量化模型」的类型编码
EMBEDDING_MODEL_TYPE = 5

# 平台名命中这些关键词即按百炼原生协议（非 OpenAI 兼容）处理
_DASHSCOPE_HINTS = ("dashscope", "百炼", "通义", "aliyun")


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


def _is_dashscope_platform(platform: Optional[str]) -> bool:
    text = (platform or "").lower()
    return any(hint in text for hint in _DASHSCOPE_HINTS)


def normalize_openai_base_url(url: str) -> str:
    """OpenAI 兼容地址规范化为以 /v1 结尾（与 embedding_client DB 模式行为一致）。

    OpenAI SDK 直接拼接 ``{base_url}/embeddings``，若库中存的是裸主机地址
    （如 http://192.168.40.30）会打到错误路径，服务端返回无 data 的响应体。
    """
    u = (url or "").strip().rstrip("/")
    if u and not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


# 连通性探测结果缓存：key = base_url|model → (时间戳, 是否可达)
_probe_cache: dict[str, tuple[float, bool]] = {}
_PROBE_TTL = 60        # 探测结果有效期（秒）
_PROBE_TIMEOUT = 5.0   # 单次探测超时（秒）


def probe_embedding_config(cfg: EmbeddingConfig) -> bool:
    """对嵌入端点做轻量连通性探测（不产生真实推理费用）。

    - 仅 OpenAI 兼容协议探测：POST {base}/embeddings 发送最小输入（不带 dimensions）；
    - dashscope 原生协议视为可达（密钥/网络问题在调用时暴露）；
    - 结果按 base_url+model 缓存 60s，避免每次向量化都重复探测。
    """
    if cfg.protocol != PROTOCOL_OPENAI:
        return True
    base = normalize_openai_base_url(cfg.base_url)
    if not base:
        return False
    cache_key = f"{base}|{cfg.model}"
    now = _time.time()
    cached = _probe_cache.get(cache_key)
    if cached and (now - cached[0]) < _PROBE_TTL:
        return cached[1]
    ok = False
    detail = ""
    try:
        with httpx.Client(timeout=_PROBE_TIMEOUT) as client:
            resp = client.post(
                f"{base}/embeddings",
                json={"model": cfg.model, "input": ["ping"]},
                headers={
                    "Authorization": f"Bearer {cfg.api_key or 'not-required'}",
                    "Content-Type": "application/json",
                },
            )
            ok = resp.status_code == 200
            if not ok:
                detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:  # noqa: BLE001 - 探测异常一律视为不可达
        detail = str(exc)
    _probe_cache[cache_key] = (now, ok)
    if not ok:
        logger.warning(
            f"[Embedding] 连通性探测失败（{cfg.provider} -> {base}/embeddings）: {detail}"
        )
    return ok


def resolve_default_embedding_from_db(session) -> Optional[EmbeddingConfig]:
    """模型管理中配置的默认「向量化模型」（type=5 + is_default + status=1）。

    返回 ``None`` 表示未配置 / 配置不完整，由调用方回落环境变量配置。
    api_key 与 url 取自关联的 ``ai_api_key``，维度取模型行 ``dimensions``。
    """
    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    row = session.execute(
        select(AiChatModel)
        .where(
            AiChatModel.type == EMBEDDING_MODEL_TYPE,
            AiChatModel.is_default.is_(True),
            AiChatModel.status == 1,
        )
        .order_by(AiChatModel.sort.desc(), AiChatModel.id.asc())
    ).scalars().first()
    if row is None:
        return None
    if not row.dimensions:
        logger.warning(
            f"[Embedding] 模型管理默认向量化模型 {row.code or row.id} 未配置维度，忽略并回落环境变量"
        )
        return None
    key = session.get(AiApiKey, row.key_id)
    # 密钥本身被禁用（status=0）也跳过：避免被禁用的 API Key 仍被向量化链路使用
    if key is None or key.status != 1 or not (key.url or "").strip():
        logger.warning(
            f"[Embedding] 模型管理默认向量化模型 {row.code or row.id} 关联的 API 密钥"
            f"（id={row.key_id}）缺失/已禁用/无可用地址，忽略并回落环境变量"
        )
        return None
    protocol = (
        PROTOCOL_DASHSCOPE if _is_dashscope_platform(row.platform) else PROTOCOL_OPENAI
    )
    url = (key.url or "").strip()
    # OpenAI 兼容协议自动补全 /v1；本地无鉴权服务允许空 api_key
    if protocol == PROTOCOL_OPENAI:
        url = normalize_openai_base_url(url)
    return EmbeddingConfig(
        provider=f"model_mgmt:{row.code or row.id}",
        protocol=protocol,
        base_url=url,
        api_key=key.api_key or "",
        model=row.model,
        dimension=int(row.dimensions),
    )


def resolve_embedding_config_with_fallback(provider: Optional[str] = None) -> EmbeddingConfig:
    """向量化模型解析：**模型管理默认模型优先，未配置则回落环境变量配置**。

    * 显式传入 ``provider`` → 维持原语义，直接走环境变量映射（调用方明确指定）；
    * 未传 → 先查模型管理里的默认向量化模型；该配置完整（type=5 + is_default +
      status=1 + 关联密钥可用 + 维度非空 + url 非空）即采用，**即便连通性探测不通
      也优先使用**（仅记 warning），不再回落环境变量；只有确实未在模型管理配置
      （``cfg is None``，例如未配置 / 不完整 / 查库异常）时才回落
      ``settings.EMBEDDING_PROVIDER`` 等环境变量配置。
    """
    if provider:
        return resolve_embedding_config(provider)
    try:
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            cfg = resolve_default_embedding_from_db(db)
        finally:
            db.close()
        if cfg is not None:
            # 放宽探测：模型管理默认配置完整即优先采用，连通性探测只用于告警日志，
            # 不再作为回落环境变量的开关（避免 lm-studio 等效配置被静默跳过）。
            if not probe_embedding_config(cfg):
                logger.warning(
                    f"[Embedding] 模型管理默认向量化模型 {cfg.provider} 连通性探测不通，"
                    "仍优先使用该配置（请确认对应向量化服务可用）"
                )
            return cfg
    except Exception as exc:  # noqa: BLE001 - 查库失败不得阻断，回落环境变量
        logger.warning(f"[Embedding] 读取模型管理默认向量化模型失败，回落环境变量配置: {exc}")
    return resolve_embedding_config(None)


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
