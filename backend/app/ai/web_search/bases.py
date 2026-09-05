"""搜索供应商抽象基类。"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SearchItem:
    """单条搜索结果"""
    title: str
    url: str
    snippet: str
    score: float = 0.0


@dataclass
class SearchResult:
    """搜索返回结果"""
    results: List[SearchItem] = field(default_factory=list)
    total: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet, "score": r.score}
                for r in self.results
            ],
            "total": self.total,
            "raw": self.raw,
        }


class WebSearchProvider(ABC):
    """搜索供应商抽象基类"""

    @abstractmethod
    async def search(
        self,
        query: str,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
    ) -> SearchResult:
        """执行搜索

        Args:
            query: 搜索关键词
            api_key: 平台 API Key
            url: API 基础地址
            config: 扩展配置（property 字段）

        Returns:
            SearchResult
        """
        ...

    async def health_check(
        self,
        api_key: str,
        url: str = "",
        config: Optional[dict] = None,
        timeout: int = 30,
    ) -> tuple[bool, str, float]:
        """健康检查：用探针关键词探测供应商可用性。

        Returns:
            (ok, message, response_time_ms)
        """
        import time

        start = time.perf_counter()
        try:
            result = await self.search("健康检查探针", api_key=api_key, url=url, config=config)
            elapsed = (time.perf_counter() - start) * 1000
            ok = result.total >= 0 and len(result.results) >= 0
            return ok, f"探测成功，返回 {result.total} 条", round(elapsed, 1)
        except Exception as e:  # noqa: BLE001
            elapsed = (time.perf_counter() - start) * 1000
            return False, f"探测失败：{e}", round(elapsed, 1)
