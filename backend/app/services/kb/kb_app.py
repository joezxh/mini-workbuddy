"""知识库 RAG Service 子应用（AgentScope RAG Service 内核 HTTP 面）。

挂载点：``/agentscope/knowledge_bases``
两种部署形态共用本文件：
- 主应用挂载：``main.py`` 中 ``app.mount("/agentscope/knowledge_bases", kb_app)``
- 独立部署：``uvicorn app.services.kb.kb_app:kb_app``

生命周期说明（P1 简报 Task 8 检查点）：
Starlette 挂载子应用**不会自动触发子应用 lifespan**，因此 KB 的关键初始化
放在主应用 lifespan（``app.state.kb_ready``）兜底；本 lifespan 仅做标记与日志，
不作为存储初始化的唯一事实来源。

挂载后端点：
- ``GET  /health`` / ``GET  /``           健康检查与元信息
- ``POST /kb``  ``GET /kb``  ``GET /kb/{kb_id}``  ``DELETE /kb/{kb_id}``
  kb_ref 知识库登记（P1 Task 9），全部强制 ``X-Tenant-Id`` 隔离（Task 6 纵深防御）
- ``GET  /embedding_models``              embedding 配置映射（api_key 脱敏，Task 7）
- ``GET  /chunkers``                      已注册切片器（approx_token / qa，Task 10）
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from loguru import logger

from agentscope.rag import ApproxTokenChunker

from app.services.kb.embedding_config import (
    SUPPORTED_PROVIDERS,
    describe_embedding_config,
    resolve_embedding_config,
)
from app.services.kb.kb_router import router as kb_router
from app.services.kb.parent_child_chunker import ParentChildChunker
from app.services.kb.qa_chunker import QaChunker


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.initialized = True
    app.state.ready_at = time.time()
    logger.info("[KB-RAG] 子应用 lifespan 执行（注意：挂载时不会自动触发，初始化见主应用 lifespan）")
    yield
    logger.info("[KB-RAG] 子应用 lifespan 关闭")


def kb_service_token() -> str:
    """服务化部署间调用凭证（spec T6）。空值=通道禁用（fail-closed）。"""
    from app.config import settings

    return getattr(settings, "KB_SERVICE_TOKEN", "") or ""


async def require_service_auth(request: Request) -> None:
    """子应用写面认证收口（spec §5 T6）：废除裸 ``X-Tenant-Id`` 信任。

    接受任一凭证，否则 401：
    1. ``Authorization: Bearer <JWT>``（语义校验由主应用依赖链完成，此处做门禁）；
    2. ``X-KB-Service-Token`` == ``settings.KB_SERVICE_TOKEN``（非空才启用）。
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 7:
        return
    service_token = kb_service_token()
    if service_token and request.headers.get("x-kb-service-token", "") == service_token:
        return
    raise HTTPException(status_code=401, detail="kb_subapp_unauthorized")


kb_app = FastAPI(title="AgentScope KB RAG Service", lifespan=_lifespan)

# kb_ref 知识库登记 REST 端点：/kb（创建/列出/获取/删除）
# 认证收口（spec T6）：写面强制 Bearer JWT 或 X-KB-Service-Token，不再裸信任 X-Tenant-Id
kb_app.include_router(kb_router, dependencies=[Depends(require_service_auth)])

# 切片器注册表（P1 Task 10 + spec §10.3）：索引管线按 chunker_type 选择切片策略
CHUNKER_REGISTRY = {
    ApproxTokenChunker.chunker_type: ApproxTokenChunker,
    QaChunker.chunker_type: QaChunker,
    ParentChildChunker.chunker_type: ParentChildChunker,
}


@kb_app.get("/health")
async def health():
    return {"status": "ok", "initialized": getattr(kb_app.state, "initialized", False)}


@kb_app.get("/")
async def info():
    return {
        "service": "AgentScope KB RAG Service",
        "mount": "/agentscope/knowledge_bases",
        "initialized": getattr(kb_app.state, "initialized", False),
    }


@kb_app.get("/embedding_models")
async def embedding_models():
    """当前 embedding 配置（api_key 脱敏）与支持的 provider 列表（P1 Task 7）。"""
    return {
        "current": describe_embedding_config(resolve_embedding_config()),
        "supported": list(SUPPORTED_PROVIDERS),
    }


@kb_app.get("/chunkers")
async def list_chunkers():
    """已注册切片器列表（含参数 JSON Schema，P1 Task 10）。"""
    return [
        {
            "chunker_type": chunker_type,
            "parameters_schema": cls.Parameters.model_json_schema(),
        }
        for chunker_type, cls in CHUNKER_REGISTRY.items()
    ]
