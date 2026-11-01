"""统一错误契约（本体端点，修 OntoMind R3）。

设计真源：docs/superpowers/specs/2026-10-31-ontology-capability-design.md §6.1「错误契约」。

向后兼容收敛（用户裁决 R3=A）：
- **仅本体新端点**抛 :class:`ApiError`，响应体固定顶层 ``{code, message, detail?}``；
- 既有 47 个 dataops 端点保持原样（``HTTPException`` 的 ``{detail}``），不批量改造；
- 前端 ``api/dataops.ts`` 拦截器优先按 ``code`` 映射 i18n 文案，缺 ``code`` 时回落 ``detail``，
  因此两套契约共存、互不影响。

服务层抛 :class:`ApiError`，由 :func:`register_api_error_handler` 注册的处理器统一渲染，
无需在每条路由里手写 try/except 翻译错误码。
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """带机器可读 ``code`` 的业务错误。

    :param code: 稳定错误码（前端据此映射 i18n），见下方 ``ONTOLOGY_*`` 常量
    :param message: 人类可读兜底文案（不参与 i18n 映射，仅当 code 未识别时展示）
    :param http_status: HTTP 状态码
    :param detail: 可选结构化补充信息（字典/列表，原样透传）
    """

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        detail: Optional[object] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.detail = detail
        super().__init__(message)


# --- 错误码常量（§6.1「主要 code」+「本次新增 code」；命名与文档严格一致）---
ONTOLOGY_NOT_FOUND = "ONTOLOGY_NOT_FOUND"
ONTOLOGY_CODE_DUPLICATED = "ONTOLOGY_CODE_DUPLICATED"
ONTOLOGY_STOPPED = "ONTOLOGY_STOPPED"
ONTOLOGY_HAS_VERSIONS = "ONTOLOGY_HAS_VERSIONS"  # 有版本则拒绝删除（§6.1 E3）
BUILD_SCOPE_EMPTY = "BUILD_SCOPE_EMPTY"
BUILD_ALREADY_RUNNING = "BUILD_ALREADY_RUNNING"
REVIEW_ITEM_NOT_FOUND = "REVIEW_ITEM_NOT_FOUND"
PUBLISH_BLOCKED_PENDING_REVIEW = "PUBLISH_BLOCKED_PENDING_REVIEW"
PUBLISH_BLOCKED_REGRESSION = "PUBLISH_BLOCKED_REGRESSION"
PUBLISH_BLOCKED_INTEGRITY = "PUBLISH_BLOCKED_INTEGRITY"
PUBLISH_BLOCKED_MASK_COVERAGE = "PUBLISH_BLOCKED_MASK_COVERAGE"
PUBLISH_BLOCKED_UNREVIEWED_SOURCE = "PUBLISH_BLOCKED_UNREVIEWED_SOURCE"
SEMANTIC_UNAVAILABLE = "SEMANTIC_UNAVAILABLE"
EXPORT_EMPTY = "EXPORT_EMPTY"
DRAFT_SCOPE_EMPTY = "DRAFT_SCOPE_EMPTY"
BUILD_SCOPE_SINGLE_SOURCE = "BUILD_SCOPE_SINGLE_SOURCE"  # 送数跨源/失表实查拦截（AF-08）
SOURCE_UNREACHABLE = "SOURCE_UNREACHABLE"                # 表级探活：数据源不可达（AF-06）
TABLE_NOT_READABLE = "TABLE_NOT_READABLE"                # 表级探活：表不可读（AF-06）
ASSET_TAG_IN_USE = "ASSET_TAG_IN_USE"
TAG_CODE_DUPLICATED = "TAG_CODE_DUPLICATED"
PUBLISH_TARGET_NOT_FOUND = "PUBLISH_TARGET_NOT_FOUND"
ASSISTANT_INTENT_UNSUPPORTED = "ASSISTANT_INTENT_UNSUPPORTED"
ASSISTANT_BUILD_PREVIEW_STALE = "ASSISTANT_BUILD_PREVIEW_STALE"
ASSISTANT_BUILD_EMPTY = "ASSISTANT_BUILD_EMPTY"


def register_api_error_handler(app: FastAPI) -> None:
    """注册 :class:`ApiError` 处理器：输出顶层 ``{code, message, detail?}``。

    在 ``main.py`` 建 app 后调用一次即可；比既有 ``Exception`` handler 更具体，
    Starlette 按异常类 MRO 选择处理器，故 ``ApiError`` 命中本处理器、其余落全局 500。
    """

    @app.exception_handler(ApiError)
    async def _handle_api_error(_request, exc: ApiError):  # noqa: ANN001
        payload = {"code": exc.code, "message": exc.message}
        if exc.detail is not None:
            payload["detail"] = exc.detail
        return JSONResponse(status_code=exc.http_status, content=payload)
