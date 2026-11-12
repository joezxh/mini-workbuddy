"""KnowledgeTools —— KB RAG 检索的 SuperAgent 工具封装（规格 2.4）。

薄封装：直接调用 ``app.services.kb.retrieval_service.KbRetrievalService``
（向量 + 关键词 RRF 混合检索），不重复实现检索逻辑。
service 不存在 / tenant 不可解析 / 初始化失败 → 降级返回空列表并 loguru warning，不抛异常。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from .toolkit import LocalTool, resolve_workspace_tenant, run_with_session

_KB_SEARCH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "检索问题或关键词"},
        "collection": {
            "type": "string",
            "description": "知识库集合名；缺省检索配置的全部 collection",
        },
        "top_k": {"type": "integer", "description": "每个集合返回条数上限，默认 5"},
    },
    "required": ["query"],
}


class KnowledgeTools:
    """kb_search 工具 —— 按 collection_ids 检索 MinWorkBuddy 知识库。"""

    @classmethod
    def build(cls, workspace_id: int | None,
              collection_ids: list[str] | None = None,
              db: Any = None,
              tenant_id: int | None = None) -> list[LocalTool]:
        try:
            return cls._build(workspace_id, collection_ids, db, tenant_id)
        except Exception as e:  # noqa: BLE001 —— 降级不抛
            logger.warning(f"KnowledgeTools degraded → no tools (ws={workspace_id}): {e}")
            return []

    @classmethod
    def _build(cls, workspace_id: int | None, collection_ids: list[str] | None,
               db: Any, tenant_id: int | None) -> list[LocalTool]:
        collections = [str(c).strip() for c in (collection_ids or []) if str(c).strip()]
        if not collections:
            logger.warning(f"KnowledgeTools degraded → kb_ids 未配置 (ws={workspace_id})")
            return []
        # service 可用性检查（ImportError → 降级）；真正实例化在调用时进行
        from app.services.kb.retrieval_service import KbRetrievalService  # noqa: F401

        tid = tenant_id if tenant_id is not None else resolve_workspace_tenant(db, workspace_id)
        if tid is None:
            logger.warning(f"KnowledgeTools degraded → tenant_id 不可解析 (ws={workspace_id})")
            return []

        def _search(args: dict[str, Any]) -> dict[str, Any]:
            import app.services.kb.retrieval_service as _mod

            query = str(args.get("query") or "").strip()
            if not query:
                return {"error": "query 不能为空"}
            top_k = int(args.get("top_k") or 5)
            wanted = str(args.get("collection") or "").strip()
            targets = [wanted] if wanted else collections
            try:

                def _run(session: Any) -> dict[str, Any]:
                    svc = _mod.KbRetrievalService.from_session(session, tid)
                    out = []
                    for col in targets:
                        rows = svc.hybrid_search_by_text(col, query, top_k=top_k)
                        out.append({
                            "collection": col,
                            "items": [
                                {
                                    "document_id": r.document_id,
                                    "chunk_index": r.chunk_index,
                                    "content": r.content,
                                    "score": float(r.score),
                                }
                                for r in rows
                            ],
                        })
                    return {
                        "query": query,
                        "collections": out,
                        "count": sum(len(c["items"]) for c in out),
                    }

                return run_with_session(db, _run)
            except Exception as e:  # noqa: BLE001 —— 工具调用错误折叠为 error 字段
                logger.warning(f"kb_search failed (ws={workspace_id}): {e}")
                return {"error": str(e)}

        logger.info(f"KnowledgeTools ws={workspace_id} · collections={collections} · tenant={tid}")
        return [LocalTool(
            name="kb_search",
            description=(
                "检索 MinWorkBuddy 知识库（向量 + 关键词混合检索，按租户隔离）。"
                "返回每个集合的命中文档片段（document_id / content / score）。"
            ),
            input_schema=_KB_SEARCH_SCHEMA,
            handler=_search,
        )]
