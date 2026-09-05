"""Bing Web Search 供应商实现。

API 文档: https://learn.microsoft.com/bing/search-apis/bing-web-search/
接口: GET https://api.bing.microsoft.com/v7.0/search
认证: Ocp-Apim-Subscription-Key: {api_key}
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


class BingProvider(WebSearchProvider):
    """Bing Web Search"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        config = config or {}
        endpoint = (url or _DEFAULT_ENDPOINT).rstrip("/")

        params = {
            "q": query,
            "count": config.get("count", 10),
        }
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(endpoint, params=params, headers=headers, timeout=30.0)
                if resp.status_code != 200:
                    return SearchResult(
                        results=[],
                        total=0,
                        raw={"error": f"HTTP {resp.status_code}", "body": resp.text[:500]},
                    )

                data = resp.json()
                raw = data

                items = []
                for item in data.get("webPages", {}).get("value", []):
                    items.append(SearchItem(
                        title=item.get("name", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        score=item.get("score", 0.0),
                    ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("Bing 搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"Bing 搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
