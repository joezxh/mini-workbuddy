"""Anspire 搜索供应商实现。

API: POST {url}，Authorization: Bearer {api_key}
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)


class AnspireProvider(WebSearchProvider):
    """Anspire 搜索"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        if not url:
            return SearchResult(results=[], total=0, raw={"error": "Anspire 需要配置 API 地址"})

        payload = {
            "query": query,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                if resp.status_code != 200:
                    return SearchResult(
                        results=[],
                        total=0,
                        raw={"error": f"HTTP {resp.status_code}", "body": resp.text[:500]},
                    )

                data = resp.json()
                raw = data

                # Anspire 返回格式: {"data": {"results": [...]}}  或 {"results": [...]}
                items = []
                results_list = (
                    data.get("data", {}).get("results", [])
                    or data.get("results", [])
                )

                for item in results_list:
                    items.append(SearchItem(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", item.get("content", "")),
                        score=item.get("score", item.get("relevance", 0.0)),
                    ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("Anspire 搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"Anspire 搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
