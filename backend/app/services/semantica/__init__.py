"""Semantica 语义组件适配层。

只做「配置 + 租户隔离 + 编排 + 对外接口」，语义算法一律委托 semantica 包。
所有对 semantica 的 import 均延迟到方法调用时发生（见 ``client.SemanticaClient``），
因此本包可在不安装/未配置 semantica 的情况下被导入，便于测试与故障隔离。
"""
from .client import SemanticaClient, SemanticaUnavailable
from .export_service import SemanticExporter
from .pipeline_service import (
    DEFAULT_STEPS,
    PipelineReport,
    PipelineStepError,
    SemanticaPipelineService,
)
from .retrieval_service import SemanticRetriever
from .scope import TenantScope

__all__ = [
    "TenantScope",
    "SemanticaClient",
    "SemanticaUnavailable",
    "SemanticaPipelineService",
    "PipelineReport",
    "PipelineStepError",
    "DEFAULT_STEPS",
    "SemanticRetriever",
    "SemanticExporter",
]
