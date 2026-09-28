"""RAGMiddleware 装配（对齐文档 §5.6 / D16）：Agent 侧唯一 RAG 集成方式。

两种模式可叠加（同时挂两个实例）：
    agentic（默认）→ 暴露 ``search_knowledge`` 工具（需手动并入 Toolkit）
    static          → 首轮推理前检索并注入 HintBlock
"""
from __future__ import annotations

from typing import Optional

from agentscope.middleware import RAGMiddleware
from agentscope.rag import KnowledgeBase


def build_rag_middleware(
    knowledge_bases: list[KnowledgeBase],
    rag_cfg: dict | None = None,
    rerank_model=None,
) -> RAGMiddleware:
    cfg = rag_cfg or {}
    return RAGMiddleware(
        knowledge_bases=knowledge_bases,
        parameters=RAGMiddleware.Parameters(
            mode=cfg.get("mode", "agentic"),
            top_k=cfg.get("top_k", 5),
            score_threshold=cfg.get("score_threshold"),
            rerank_candidate_k=cfg.get("rerank_candidate_k"),
            emit_hint_event=cfg.get("emit_hint_event", True),
            persist_hint=cfg.get("persist_hint", False),
        ),
        rerank_model=rerank_model,
    )


async def collect_rag_tools(mw: RAGMiddleware) -> list:
    """agentic 模式下 Agent.__init__ 不会自动收集 list_tools，需手动并入 Toolkit。"""
    return list(await mw.list_tools()) if hasattr(mw, "list_tools") else []


def rag_parameters_schema() -> dict:
    """前端创建向导直接消费（对齐文档 §6.1）。"""
    return RAGMiddleware.Parameters.model_json_schema()
