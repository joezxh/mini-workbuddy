"""SearXNG 搜索供应商实现（自托管）。

接口: GET {base}/search?q=关键词&format=json
认证: 一般无需 Key；若实例开启了 limiter 可用可选 api_key 作为请求头。
返回: [{"title", "url", "content", "score"?}, ...]  （JSON 数组）
建议在 property 中配置 base（如 http://localhost:8080）。
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "http://localhost:8080"


class SearXNGProvider(WebSearchProvider):
    """SearXNG 自托管元搜索引擎（聚合多家结果）"""

    async def search(
        self,
        query: str,
        api_key: str = "",
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        config = config or {}
        base = (url or _DEFAULT_ENDPOINT).rstrip("/")
        endpoint = f"{base}/search"

        params = {
            "q": query,
            "format": "json",
            "pageno": config.get("pageno", 1),
        }
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    endpoint,
                    params=params,
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

                # SearXNG JSON 返回为数组；部分版本包在 {"results": [...]}
                result_list = data if isinstance(data, list) else data.get("results", [])

                items = []
                for item in result_list:
                    if isinstance(item, dict):
                        items.append(SearchItem(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("content", ""),
                            score=item.get("score", 0.0),
                        ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("SearXNG 搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"SearXNG 搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
