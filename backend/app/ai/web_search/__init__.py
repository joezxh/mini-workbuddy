"""Web Search 搜索执行层。"""
from app.ai.web_search.factory import get_provider
from app.ai.web_search.bases import WebSearchProvider, SearchResult

__all__ = ["get_provider", "WebSearchProvider", "SearchResult"]
