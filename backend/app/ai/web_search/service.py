"""联网搜索统一服务（方案 1）。

将 DEEP_RESEARCH、知识库联合检索、web_search 工具等全部收敛到本服务，
统一读取管理后台配置的 ``AiWebSearch`` 表，按优先级选择启用供应商，
调用 factory 中的 provider 执行搜索，并落 ``AiWebSearchLog`` 调用日志。

该服务是体系 A（factory + AiWebSearch 表）的唯一对外入口，替代原
``app/services/search_manager.SearchServiceManager`` 体系 B。
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai.web_search.factory import get_provider
from app.models.ai.ai_web_search import AiWebSearch, AiWebSearchLog

logger = logging.getLogger(__name__)


class WebSearchToolService:
    """统一联网搜索服务：多供应商按优先级回退 + 每日配额耗尽自动切换 + 日志落库。"""

    def __init__(self, db: Optional[Session] = None):
        # db 可为 None：运行时通过 _session() 惰性创建（用于无请求上下文的调用方）
        self._db = db

    # ── 会话管理 ───────────────────────────────────────────────
    def _session(self) -> Session:
        if self._db is not None:
            return self._db
        from app.db.database import SessionLocal

        return SessionLocal()

    def _owns_session(self) -> bool:
        return self._db is None

    # ── 供应商选择 / 配额 ──────────────────────────────────────
    def _rollover_quota(self, item: AiWebSearch, today: date) -> None:
        """按日重置配额：若 used_count 所属日期不是今天，则归零并写入今天。

        直接修改内存对象，由调用方在合适时机 commit。
        """
        if item.quota_date != today:
            item.used_count = 0
            item.quota_date = today

    def _quota_remaining(self, item: AiWebSearch, today: date) -> int:
        """返回当天剩余配额。daily_quota<=0 表示不限，返回 -1。"""
        if (item.daily_quota or 0) <= 0:
            return -1
        self._rollover_quota(item, today)
        return max((item.daily_quota or 0) - (item.used_count or 0), 0)

    def _select_providers(
        self, db: Session, prefer_platform: Optional[str] = None
    ) -> List[Tuple[AiWebSearch, bool]]:
        """返回启用的、当天配额未耗尽的供应商列表（按优先级降序）。

        返回 ``(供应商, 是否因配额跳过)``：因配额跳过的供应商单独标记，不计入失败日志。

        优先级规则：
        1. 若指定 ``prefer_platform`` 且该供应商启用且配额充足，则前置（优先尝试）；
        2. 其余按 priority 降序、sort 降序、id 降序排列；
        3. 当天配额已用尽的供应商被跳过（不调用、不记失败日志），自动切换到下一优先级。
        """
        today = date.today()
        enabled = (
            db.query(AiWebSearch)
            .filter(AiWebSearch.status == 1)
            .order_by(
                AiWebSearch.priority.desc(),
                AiWebSearch.sort.desc(),
                AiWebSearch.id.desc(),
            )
            .all()
        )

        preferred: List[Tuple[AiWebSearch, bool]] = []
        others: List[Tuple[AiWebSearch, bool]] = []
        skipped_quota: List[str] = []
        for item in enabled:
            remaining = self._quota_remaining(item, today)
            if remaining == 0:
                skipped_quota.append(item.platform)
                continue
            if prefer_platform and item.platform == prefer_platform:
                preferred.append((item, False))
            else:
                others.append((item, False))

        if skipped_quota:
            logger.info(
                "联网搜索：以下供应商今日配额已用尽，已跳过并切换至下一优先级: %s",
                ", ".join(skipped_quota),
            )
        # 优先平台前置，其余按优先级
        return preferred + others

    # ── 核心搜索 ───────────────────────────────────────────────
    def _normalize(self, result: Dict) -> List[Dict]:
        return result.get("results", []) if isinstance(result, dict) else []

    async def search(
        self,
        query: str,
        max_results: int = 10,
        prefer_platform: Optional[str] = None,
    ) -> Dict:
        """执行联网搜索（按优先级顺序 + 配额耗尽自动切换）。

        按顺序尝试高优先级搜索源；若某源当天配额已用尽，则自动跳过并尝试下一优先级；
        若调用失败（网络/API 错误），同样回退到下一源。返回首个成功且结果足够的源数据。

        Returns:
            {
                "results": [{"title","url","snippet","score"}, ...],
                "total": int,
                "raw": {...},
                "provider": str,   # 实际命中的供应商 platform
            }
        """
        db = self._session()
        own = self._owns_session()
        try:
            providers = self._select_providers(db, prefer_platform)
            if not providers:
                return {
                    "results": [],
                    "total": 0,
                    "raw": {"error": "未配置任何启用且当日配额充足的联网搜索供应商"},
                    "provider": None,
                }

            seen_urls: set = set()
            merged: List[Dict] = []
            last_error: Optional[str] = None
            used_provider: Optional[str] = None

            for item, _skipped in providers:
                provider = get_provider(item.platform)
                start = time.perf_counter()
                ok = False
                error = ""
                result_dict: Dict = {"results": []}
                try:
                    result = await provider.search(
                        query=query,
                        api_key=item.api_key,
                        url=item.url or "",
                        config=item.property,
                    )
                    result_dict = result.to_dict()
                    ok = not result.raw.get("error")
                    error = result.raw.get("error", "") if not ok else ""
                except Exception as e:  # noqa: BLE001
                    ok = False
                    error = f"{type(e).__name__}: {e}"
                finally:
                    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                    self._record_log(
                        db, item, query, elapsed_ms,
                        result_dict.get("total", 0) if ok else 0, ok, error,
                    )

                if not ok:
                    last_error = error
                    logger.warning(f"联网搜索供应商 {item.platform} 失败: {error}")
                    continue

                used_provider = item.platform
                for r in self._normalize(result_dict):
                    url = r.get("url", "")
                    if url and url in seen_urls:
                        continue
                    if url:
                        seen_urls.add(url)
                    merged.append(r)
                    if len(merged) >= max_results:
                        break

                if len(merged) >= max_results:
                    break

            if not merged:
                return {
                    "results": [],
                    "total": 0,
                    "raw": {"error": last_error or "所有供应商均无结果或配额已用尽"},
                    "provider": used_provider,
                }

            return {
                "results": merged[:max_results],
                "total": len(merged),
                "raw": {"providers_tried": [p.platform for p, _ in providers]},
                "provider": used_provider,
            }
        finally:
            if own:
                db.close()

    # ── 日志落库 ───────────────────────────────────────────────
    def _record_log(
        self,
        db: Session,
        item: AiWebSearch,
        query: str,
        elapsed_ms: float,
        results_count: int,
        success: bool,
        error: str,
    ) -> None:
        try:
            log = AiWebSearchLog(
                web_search_id=item.id,
                service_name=item.name,
                platform=item.platform,
                query=query,
                response_time=elapsed_ms,
                results_count=results_count,
                success=success,
                error=error or "",
            )
            db.add(log)
            if success:
                item.used_count = (item.used_count or 0) + 1
                # 记录 used_count 所属日期，保证每日配额在日期边界自动重置
                item.quota_date = date.today()
            db.commit()
        except Exception as e:  # noqa: BLE001
            logger.error(f"联网搜索日志落库失败: {e}")
            db.rollback()
