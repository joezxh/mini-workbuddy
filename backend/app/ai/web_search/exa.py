"""Exa 搜索供应商实现。

API 文档: https://docs.exa.ai/
接口: POST https://api.exa.ai/search
认证: Authorization: Bearer {api_key}
返回: {"results": [{"title", "url", "text", "score"}, ...]}
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://api.exa.ai/search"


class ExaProvider(WebSearchProvider):
    """Exa 神经搜索（基于嵌入/模型的全文检索）"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        config = config or {}
        endpoint = (url or _DEFAULT_ENDPOINT).rstrip("/")

        payload = {
            "query": query,
            "numResults": config.get("count", 10),
            "type": config.get("type", "keyword"),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    endpoint,
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

                items = []
                for item in data.get("results", []):
                    items.append(SearchItem(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("text", ""),
                        score=item.get("score", 0.0),
                    ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("Exa 搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"Exa 搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
