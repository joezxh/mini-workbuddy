"""OntologyTools —— 本体资产检索的 SuperAgent 工具封装（规格 2.4）。

薄封装：直接调用 ``app.services.ontology.ontology_asset_service.OntologyAssetService.search``
（资产关键词检索 + 三档确定性打分），不重复实现检索逻辑。
service 不存在 / tenant 不可解析 / 初始化失败 → 降级返回空列表并 loguru warning，不抛异常。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from .toolkit import LocalTool, resolve_workspace_tenant, run_with_session

_ONTOLOGY_SEARCH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "kw": {"type": "string", "description": "检索关键词（表名/库名/注释/列名命中）"},
        "kind": {
            "type": "string",
            "enum": ["table", "column"],
            "description": "检索维度：table（默认）按表聚合，column 只返回含命中列的表",
        },
        "size": {"type": "integer", "description": "返回条数上限，默认 20"},
    },
}


class OntologyTools:
    """ontology_search 工具 —— 本体资产检索（按租户隔离，只读）。"""

    @classmethod
    def build(cls, workspace_id: int | None,
              db: Any = None,
              tenant_id: int | None = None) -> list[LocalTool]:
        try:
            return cls._build(workspace_id, db, tenant_id)
        except Exception as e:  # noqa: BLE001 —— 降级不抛
            logger.warning(f"OntologyTools degraded → no tools (ws={workspace_id}): {e}")
            return []

    @classmethod
    def _build(cls, workspace_id: int | None, db: Any,
               tenant_id: int | None) -> list[LocalTool]:
        # service 可用性检查（ImportError → 降级）；真正实例化在调用时进行
        from app.services.ontology.ontology_asset_service import OntologyAssetService  # noqa: F401

        tid = tenant_id if tenant_id is not None else resolve_workspace_tenant(db, workspace_id)
        if tid is None:
            logger.warning(f"OntologyTools degraded → tenant_id 不可解析 (ws={workspace_id})")
            return []

        def _search(args: dict[str, Any]) -> dict[str, Any]:
            import app.services.ontology.ontology_asset_service as _mod

            kw = str(args.get("kw") or "").strip()
            kind = str(args.get("kind") or "table")
            size = int(args.get("size") or 20)
            try:

                def _run(session: Any) -> dict[str, Any]:
                    svc = _mod.OntologyAssetService(session, tid)
                    return svc.search(kw=kw or None, kind=kind, size=size)

                return run_with_session(db, _run)
            except Exception as e:  # noqa: BLE001 —— 工具调用错误折叠为 error 字段
                logger.warning(f"ontology_search failed (ws={workspace_id}): {e}")
                return {"error": str(e)}

        logger.info(f"OntologyTools ws={workspace_id} · tenant={tid}")
        return [LocalTool(
            name="ontology_search",
            description=(
                "检索 MinWorkBuddy 本体资产（数据表/字段，按关键词打分排序，按租户隔离，只读）。"
                "返回 total 与 items（表卡片：表名/注释/命中得分等）。"
            ),
            input_schema=_ONTOLOGY_SEARCH_SCHEMA,
            handler=_search,
        )]
