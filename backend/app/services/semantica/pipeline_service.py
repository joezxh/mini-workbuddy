"""分步编排 semantica 语义能力（替代旧 modeling_service / search_filter 的编排职责）。

每步失败抛 ``PipelineStepError(step, cause)``，沿用 kb ``pipeline_runner`` 的
PipelineStepError 风格，便于上游按步骤名做故障定位与重试。

步骤顺序（默认）：extract → conflicts → dedup → kg → vector。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import settings
from .client import SemanticaClient, SemanticaUnavailable
from .scope import TenantScope


class PipelineStepError(RuntimeError):
    """语义管道在某步骤失败时抛出。"""

    def __init__(self, step: str, cause: Exception) -> None:
        self.step = step
        self.__cause__ = cause
        super().__init__(f"语义管道在步骤 {step!r} 失败: {cause}")


@dataclass
class PipelineReport:
    ok: bool = True
    steps: List[str] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)


DEFAULT_STEPS = ["extract", "conflicts", "dedup", "kg", "vector"]


class SemanticaPipelineService:
    """本体/语义管道编排服务。

    :param db: SQLAlchemy Session（预留：后续步骤如需落库可注入），当前未使用。
    :param scope: 租户隔离范围；不传则使用 ``tenant_id=0`` 的默认范围。
    """

    def __init__(self, db: Any = None, scope: Optional[TenantScope] = None) -> None:
        self.db = db
        self.scope = scope or TenantScope(tenant_id=0)
        self.client = SemanticaClient(scope=self.scope)

    def _resolve_entities(self, source: Any) -> List[dict]:
        """数据源 → 实体列表。文本直接抽取，列表原样透传。"""
        if isinstance(source, str):
            return self.client.extract_entities(source)
        if isinstance(source, (list, tuple)):
            return list(source)
        raise ValueError(f"不支持的 source 类型: {type(source)!r}")

    def run(self, source: Any, *, steps: Optional[List[str]] = None) -> PipelineReport:
        steps = steps or DEFAULT_STEPS
        report = PipelineReport(ok=True)
        try:
            entities = self._resolve_entities(source)
            report.summary["entities"] = len(entities)
            for step in steps:
                if step == "extract":
                    continue  # 已在 _resolve_entities 完成
                t0 = time.perf_counter()
                try:
                    result = self._run_step(step, entities)
                except SemanticaUnavailable as exc:
                    raise PipelineStepError(step, exc)
                except Exception as exc:  # 业务/依赖异常封装为步骤错误
                    raise PipelineStepError(step, exc)
                finally:
                    report.timings[step] = round(time.perf_counter() - t0, 3)
                    report.steps.append(step)
                if result is not None:
                    report.summary.update(result)
            return report
        finally:
            logger.info(
                "Semantica 管道完成 steps={} summary={}", report.steps, report.summary
            )

    def _run_step(self, step: str, entities: List[dict]) -> Optional[Dict[str, Any]]:
        """执行单步，返回要合并进 ``report.summary`` 的计数字典。"""
        if step == "conflicts":
            conflicts = self.client.detect_conflicts(entities) or []
            return {"conflicts": len(conflicts)}
        if step == "dedup":
            dups = self.client.deduplicate(entities) or []
            return {"duplicates": len(dups)}
        if step == "kg":
            kg = self.client.build_graph(entities, [])
            return {"graph": bool(kg)}
        if step == "vector":
            store = self.client.vector_store("entity")
            # 索引预建（已存在则忽略）；实际向量写入由调用方 embedding 后 add
            if hasattr(store, "create_index"):
                try:
                    store.create_index()
                except Exception as exc:  # 索引已存在等情况不阻塞
                    logger.debug("vector index 预建跳过: {}", exc)
            return {"vector_index": self.scope.collection("entity")}
        raise ValueError(f"未知步骤: {step}")
