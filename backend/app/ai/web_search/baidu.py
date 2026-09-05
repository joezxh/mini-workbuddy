"""百度搜索供应商实现。

百度开放搜索（Baidu Web Search Open API）需要 access_token，
实际接入时需先通过 api_key(api_key)/secret(api_secret) 换取 token。
为兼容通用配置，这里支持两种模式：
  1. url 已配置为完整请求地址（含 token）→ 直接 GET/POST 该地址；
  2. 仅配置通用凭据 → 回退到 Anspire 通用 POST 模式，由上层 get_provider 兜底。
"""
import logging
from typing import Optional

import httpx

from app.ai.web_search.bases import WebSearchProvider, SearchResult, SearchItem

logger = logging.getLogger(__name__)


class BaiduProvider(WebSearchProvider):
    """百度搜索（通用 HTTP 模式）"""

    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        config = config or {}
        if not url:
            return SearchResult(
                results=[],
                total=0,
                raw={"error": "百度搜索需要配置 API 地址（含 access_token）或填写 url"},
            )

        params = {
            "q": query,
            "count": config.get("count", 10),
        }
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, headers=headers, timeout=30.0)
                if resp.status_code != 200:
                    return SearchResult(
                        results=[],
                        total=0,
                        raw={"error": f"HTTP {resp.status_code}", "body": resp.text[:500]},
                    )

                data = resp.json()
                raw = data

                # 兼容常见返回结构：results / data.list / webPages.value
                results_list = (
                    data.get("results")
                    or data.get("data", {}).get("list", [])
                    or data.get("webPages", {}).get("value", [])
                )

                items = []
                for item in results_list:
                    if isinstance(item, dict):
                        items.append(SearchItem(
                            title=item.get("title", ""),
                            url=item.get("url", item.get("link", "")),
                            snippet=item.get("snippet", item.get("content", "")),
                            score=item.get("score", 0.0),
                        ))

                return SearchResult(
                    results=items,
                    total=len(items),
                    raw=raw,
                )

        except httpx.TimeoutException:
            logger.error("百度搜索超时")
            return SearchResult(results=[], total=0, raw={"error": "请求超时"})
        except Exception as e:
            logger.error(f"百度搜索异常: {e}")
            return SearchResult(results=[], total=0, raw={"error": str(e)})
