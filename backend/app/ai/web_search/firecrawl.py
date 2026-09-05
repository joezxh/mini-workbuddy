"""Firecrawl 搜索供应商实现（自托管 / SaaS 通用）。

API 文档: https://docs.firecrawl.dev/
接口: POST {base}/v1/search
认证: Authorization: Bearer {api_key}
返回: {"data": [{"title", "url", "description" / "markdown"}, ...]}
自托管时 base 通过 url 传入（如 http://localhost:3002），SaaS 默认 https://api.firecrawl.dev。
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://api.firecrawl.dev"


class FirecrawlProvider(WebSearchProvider):
    """Firecrawl 搜索（自托管或 SaaS，统一 /v1/search 接口）"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        config = config or {}
        base = (url or _DEFAULT_ENDPOINT).rstrip("/")
        endpoint = f"{base}/v1/search"
        if not url and not api_key:
            return SearchResult(
                results=[],
                total=0,
                raw={"error": "Firecrawl 需要配置 API Key（SaaS）或自托管地址 url（免 Key 亦可）"},
            )

        payload = {
            "query": query,
            "limit": config.get("count", 10),
            "lang": config.get("lang", "zh"),
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

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

                # 兼容 {"data": [...]} 与直接 [...] 两种结构
                result_list = data.get("data", []) if isinstance(data, dict) else data

                items = []
                for item in result_list:
                    items.append(SearchItem(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", item.get("markdown", "")),
                        score=item.get("score", 0.0),
                    ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("Firecrawl 搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"Firecrawl 搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
