"""Google 自定义搜索供应商实现。

API 文档: https://developers.google.com/custom-search/v1
接口: GET https://www.googleapis.com/customsearch/v1
参数: key=API_KEY&cx=搜索引擎ID&q=查询词
cx 可通过 url 传入（完整 base url 含 cx）或 property["cx"]。
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


class GoogleProvider(WebSearchProvider):
    """Google 自定义搜索"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        config = config or {}
        endpoint = (url or _DEFAULT_ENDPOINT).rstrip("/")
        cx = config.get("cx", "")

        params = {
            "key": api_key,
            "q": query,
            "num": config.get("count", 10),
        }
        if cx:
            params["cx"] = cx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(endpoint, params=params, timeout=30.0)
                if resp.status_code != 200:
                    return SearchResult(
                        results=[],
                        total=0,
                        raw={"error": f"HTTP {resp.status_code}", "body": resp.text[:500]},
                    )

                data = resp.json()
                raw = data

                items = []
                for item in data.get("items", []):
                    items.append(SearchItem(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        score=item.get("score", 0.0),
                    ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("Google 搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"Google 搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
