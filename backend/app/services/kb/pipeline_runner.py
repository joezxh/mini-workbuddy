"""摄取编排执行器（spec §10.7 / D8）：dry-run 与真实 ingest 共用同一条链路。

链路固定为 ``parser.parse → clean → chunker.chunk``，三步全部由
``pipeline_config`` 驱动。``POST /kb/pipelines/dry-run`` 与
``document_pipeline.run_document_ingest`` 调用同一入口，保证 dry-run 预览的
切片与真实落库的切片由同一份配置产出（「所见即所得」）。

原生参数零转换（D8）：``parser.type`` 为原生 Parser 类名，``chunker.params``
直喂 ``ChunkerBase.Parameters``；未知类型显式失败，不静默降级。
DataBlock 段（图片等）在清洗步原样透传（D13）。
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from agentscope.message import TextBlock

from app.services.kb.parser_selector import (
    guess_media_type,
    parser_names,
    select_parser,
    select_parser_by_name,
)
from app.services.kb.rag.chunker_factory import build_chunker

__all__ = [
    "CLEANER_REGISTRY",
    "PipelinePlan",
    "PipelineRun",
    "PipelineStepError",
    "cleaner_names",
    "parser_names",
    "run_pipeline",
    "run_pipeline_from_config",
]


# ── 清洗算子注册表（pipeline_config.clean）───────────────────────────────

def _remove_extra_spaces(text: str) -> str:
    """折叠连续空格/制表符与 3 行以上空行。"""
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def _remove_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text)


def _remove_emails(text: str) -> str:
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "", text)


def _remove_empty_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.strip())


CLEANER_REGISTRY: dict[str, Callable[[str], str]] = {
    "remove_extra_spaces": _remove_extra_spaces,
    "remove_urls": _remove_urls,
    "remove_emails": _remove_emails,
    "remove_empty_lines": _remove_empty_lines,
}


def cleaner_names() -> list[str]:
    """供前端向导 / Schema 发现可用清洗算子。"""
    return sorted(CLEANER_REGISTRY)


class PipelineStepError(ValueError):
    """某一步执行失败；``step`` 供 ``kb_document.error_detail`` 定位（§10.7）。"""

    def __init__(self, step: str, exc: BaseException) -> None:
        super().__init__(f"[{step}] {type(exc).__name__}: {exc}")
        self.step = step


# ── 执行计划 ──────────────────────────────────────────────────────────────

@dataclass
class PipelinePlan:
    """由 pipeline_config（+ 扁平兜底参数）解析出的执行计划。"""

    parser_type: Optional[str] = None  # 原生 Parser 类名；None → 按 mime 推断
    parser_params: dict = field(default_factory=dict)
    chunker_type: str = "approx_token"
    chunker_params: dict = field(default_factory=dict)
    clean: list[str] = field(default_factory=list)

    @classmethod
    def from_config(
        cls,
        pipeline_config: Optional[dict] = None,
        chunker_type: Optional[str] = None,
        chunker_params: Optional[dict] = None,
    ) -> "PipelinePlan":
        """解析执行计划：``chunker`` 段优先于扁平参数（与 dry-run 旧入参兼容）。"""
        cfg = pipeline_config or {}
        plan = cls(
            chunker_type=chunker_type or "approx_token",
            chunker_params=dict(chunker_params or {}),
        )
        parser_seg = cfg.get("parser") or {}
        if parser_seg:
            plan.parser_type = parser_seg.get("type")
            plan.parser_params = dict(parser_seg.get("params") or {})
        chunker_seg = cfg.get("chunker") or {}
        if chunker_seg.get("type"):
            plan.chunker_type = chunker_seg["type"]
        # 用键存在性而非真值判断：显式 ``params: {}`` 也应覆盖扁平入参
        if "params" in chunker_seg:
            plan.chunker_params = dict(chunker_seg["params"] or {})
        plan.clean = list(cfg.get("clean") or [])
        return plan


# ── 执行 ──────────────────────────────────────────────────────────────────

def _clean_sections(sections: list, clean_steps: list[str]) -> list:
    """按算子顺序清洗 Section 文本；DataBlock 段原样透传（D13）。"""
    if not clean_steps:
        return sections

    cleaners: list[Callable[[str], str]] = []
    for name in clean_steps:
        fn = CLEANER_REGISTRY.get(name)
        if fn is None:
            raise ValueError(f"未知 clean 算子: {name!r}；可选 {cleaner_names()}")
        cleaners.append(fn)

    out: list = []
    for sec in sections:
        text = getattr(getattr(sec, "content", None), "text", None)
        if text is None:  # DataBlock（图片等）不参与文本清洗
            out.append(sec)
            continue
        cleaned = text
        for fn in cleaners:
            cleaned = fn(cleaned)
        out.append(sec.model_copy(update={"content": TextBlock(text=cleaned)}))
    return out


@dataclass
class PipelineRun:
    """一次链路执行的产物：中间 Section / 最终 Chunk / 各步摘要。"""

    sections: list = field(default_factory=list)
    chunks: list = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)

    def to_preview(self, limit: int = 200) -> dict:
        """dry-run 响应体：各步中间产物预览（不落库、不嵌入）。"""
        def _text(obj: Any) -> str:
            content = getattr(obj, "content", None)
            if not hasattr(content, "text"):
                return "[DataBlock]"
            return (content.text or "")[:limit]

        return {
            "steps": list(self.steps),
            "sections": [
                {"source": s.source, "preview": _text(s)} for s in self.sections
            ],
            "chunks": [
                {
                    "chunk_index": c.chunk_index,
                    "total_chunks": c.total_chunks,
                    "preview": _text(c),
                    "metadata": c.metadata,
                }
                for c in self.chunks
            ],
        }


def run_pipeline(
    file_bytes: Optional[bytes],
    filename: str,
    plan: Optional[PipelinePlan] = None,
) -> PipelineRun:
    """执行 parse → clean → chunk；失败抛 ``PipelineStepError``（带步名）。"""
    plan = plan or PipelinePlan()
    steps: list[dict] = []

    try:
        parser = (
            select_parser_by_name(plan.parser_type)
            if plan.parser_type
            else select_parser(guess_media_type(filename))
        )
        sections = asyncio.run(
            parser.parse(
                file=file_bytes if file_bytes is not None else filename,
                filename=filename,
            )
        )
    except PipelineStepError:
        raise
    except Exception as exc:  # noqa: BLE001 - 归集为带步名的失败
        raise PipelineStepError("parse", exc) from exc
    steps.append({
        "step": "parse",
        "parser": type(parser).__name__,
        "sections": len(sections),
    })

    try:
        sections = _clean_sections(sections, plan.clean)
    except Exception as exc:  # noqa: BLE001
        raise PipelineStepError("clean", exc) from exc
    steps.append({"step": "clean", "operators": list(plan.clean)})

    try:
        chunker = build_chunker(plan.chunker_type, plan.chunker_params)
        chunks = asyncio.run(chunker.chunk(sections))
    except Exception as exc:  # noqa: BLE001
        raise PipelineStepError("chunk", exc) from exc
    steps.append({
        "step": "chunk",
        "chunker": plan.chunker_type,
        "params": dict(plan.chunker_params),
        "chunks": len(chunks),
    })

    return PipelineRun(sections=sections, chunks=chunks, steps=steps)


def run_pipeline_from_config(
    file_bytes: Optional[bytes],
    filename: str,
    pipeline_config: Optional[dict] = None,
    chunker_type: Optional[str] = None,
    chunker_params: Optional[dict] = None,
) -> PipelineRun:
    """便捷入口：配置 → 计划 → 执行（dry-run 与真实摄取共用）。"""
    return run_pipeline(
        file_bytes,
        filename,
        PipelinePlan.from_config(pipeline_config, chunker_type, chunker_params),
    )
