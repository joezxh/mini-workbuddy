"""搜索服务配置（4 个供应商 + 通用配置）"""
from pydantic import BaseModel


class SearchSettings(BaseModel):
    """搜索服务配置字段"""
    # 博查
    BOCHA_ENABLED: bool = True
    BOCHA_API_BASE_URL: str = "https://api.bocha.com"
    BOCHA_API_KEY: str = ""
    BOCHA_API_SECRET: str = ""
    BOCHA_TIMEOUT: int = 30
    BOCHA_MAX_RESULTS: int = 50
    BOCHA_DAILY_QUOTA: int = 1000

    # 数眼智能
    SHUYAN_ENABLED: bool = True
    SHUYAN_API_BASE_URL: str = "https://api.shuyanai.com/v1"
    SHUYAN_API_KEY: str = ""
    SHUYAN_TIMEOUT: int = 30
    SHUYAN_MAX_RESULTS: int = 50
    SHUYAN_DAILY_QUOTA: int = 500
    SHUYAN_PRIORITY: int = 1

    # 安思派
    ANSPIRE_ENABLED: bool = True
    ANSPIRE_API_BASE_URL: str = "https://api.anspire.com/v1"
    ANSPIRE_API_KEY: str = ""
    ANSPIRE_TIMEOUT: int = 30
    ANSPIRE_MAX_RESULTS: int = 50
    ANSPIRE_DAILY_QUOTA: int = 500
    ANSPIRE_PRIORITY: int = 2

    # Firecrawl
    FIRECRAWL_ENABLED: bool = True
    FIRECRAWL_API_BASE_URL: str = "http://localhost:3002"
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_TIMEOUT: int = 60
    FIRECRAWL_MAX_RESULTS: int = 100
    FIRECRAWL_DAILY_QUOTA: int = 10000
    FIRECRAWL_PRIORITY: int = 99

    # 搜索服务通用配置
    SEARCH_AUTO_FALLBACK: bool = True
    SEARCH_RETRY_TIMES: int = 3
    SEARCH_CACHE_ENABLED: bool = True
    SEARCH_CACHE_TTL: int = 3600
