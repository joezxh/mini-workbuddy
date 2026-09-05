"""搜索供应商工厂 — 根据 platform 返回对应的 Provider 实例。"""
from app.ai.web_search.bases import WebSearchProvider
from app.ai.web_search.bocha import BochaProvider
from app.ai.web_search.anspire import AnspireProvider
from app.ai.web_search.google import GoogleProvider
from app.ai.web_search.bing import BingProvider
from app.ai.web_search.baidu import BaiduProvider
from app.ai.web_search.tavily import TavilyProvider
from app.ai.web_search.exa import ExaProvider
from app.ai.web_search.firecrawl import FirecrawlProvider
from app.ai.web_search.searxng import SearXNGProvider

_PROVIDERS: dict[str, type[WebSearchProvider]] = {
    "bocha": BochaProvider,
    "anspire": AnspireProvider,
    "google": GoogleProvider,
    "bing": BingProvider,
    "baidu": BaiduProvider,
    "tavily": TavilyProvider,
    "exa": ExaProvider,
    "firecrawl": FirecrawlProvider,
    "searxng": SearXNGProvider,
}


def get_provider(platform: str) -> WebSearchProvider:
    """根据平台标识获取搜索供应商实例。

    未注册的平台会回退到 AnspireProvider（通用 POST + Bearer 模式）。
    """
    cls = _PROVIDERS.get(platform.lower())
    if cls is None:
        # 未知平台使用通用实现（Anspire 的 POST + Bearer 模式作为兜底）
        return AnspireProvider()
    return cls()
