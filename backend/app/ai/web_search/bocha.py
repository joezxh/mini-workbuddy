"""博查 AI 搜索供应商实现。

API 文档: https://api.bochaai.com/v1/web-search
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)


class BochaProvider(WebSearchProvider):
    """博查 AI 搜索"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        base_url = (url or "https://api.bochaai.com").rstrip("/")
        count = (config or {}).get("count", 10)

        payload = {
            "query": query,
            "count": count,
            "summary": True,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/v1/web-search",
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

                # 博查返回格式: {"data": {"webPages": {"value": [...]}}}
                items = []
                web_pages = data.get("data", {}).get("webPages", {})
                value_list = web_pages.get("value", [])

                for item in value_list:
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
            logger.error("博查搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"博查搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
