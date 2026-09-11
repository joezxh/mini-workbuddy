"""连接器抽象（P3 Task 1）。

外部数据源连接器（HTTP/API、钉钉等）的统一抽象：配置校验、连通性探测、
拉取（pull）、落库（sync，由 Task 7 实现 DB sink，本文件只定义 Sink 协议与
内存实现）。与 dataops 方言适配器、tool 注册表同构：按 ``connector_type`` 分派。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

from app.connectors.mapping import FieldMapItem


class PaginationConfig(BaseModel):
    """分页配置（pull 多页拉取）。"""

    type: str = "none"            # none | page | offset | cursor
    param: str = "page"           # 翻页参数名（page/offset）或游标参数名
    start: int = 1                # page 起始值
    step: int = 100               # offset 步长 / page 大小参考
    next_path: Optional[str] = None  # cursor 模式：响应中下一游标字段（dotted）


class ConnectorConfig(BaseModel):
    """连接器配置（与具体类型无关的通用字段 + 类型专属扩展）。"""

    base_url: str
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    records_path: Optional[str] = None   # 响应 JSON 中记录列表的 dotted 路径，空=响应本身是列表
    auth_token: Optional[str] = None     # Bearer 令牌（注入 Authorization 头）
    timeout: float = 15.0
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    # ---- P3 Task 2~5：字段映射 + 增量 ----
    field_map: Optional[List[FieldMapItem]] = None   # 外部字段 → 内部目标字段映射
    incremental_field: Optional[str] = None          # 映射后用作增量游标的目标字段名
    incremental_param: Optional[str] = None          # 增量游标作为查询参数名传给下一轮拉取（HTTP 类）
    # ---- P3 Task 2~5：OAuth2 类连接器（钉钉/飞书/企业微信）专属 ----
    token_url: Optional[str] = None                  # 获取访问令牌的端点
    client_id: Optional[str] = None                  # appkey / app_id / corpid
    client_secret: Optional[str] = None               # appsecret / corpsecret
    data_path: Optional[str] = None                  # 数据请求路径（OAuth2 类），如 /attendance/list
    token_field: Optional[str] = "access_token"      # 令牌响应 JSON 中令牌字段名
    token_method: Optional[str] = "POST"             # 取令牌的 HTTP 方法
    token_query: Dict[str, Any] = Field(default_factory=dict)   # 令牌请求的查询参数（如 appkey/appsecret）
    token_body: Dict[str, Any] = Field(default_factory=dict)   # 令牌请求的 JSON 体（如 app_id/app_secret）
    token_in: str = "header"                         # 令牌注入方式：header(Bearer) | query(access_token 查询参数)
    token_query_name: str = "access_token"           # query 模式下的参数名（钉钉/企业微信用 access_token）


class SinkResult(BaseModel):
    """一次同步结果（Task 7 落库后填充）。"""

    written: int = 0
    skipped: int = 0
    detail: str = ""


class ConnectorSink(Protocol):
    """落库目标协议（Task 7 提供 DB 实现；本文件给内存实现供测试与默认路径）。"""

    async def write(self, records: List[Dict[str, Any]], meta: Dict[str, Any]) -> SinkResult: ...


class InMemorySink:
    """内存 Sink（测试 / 预览用，不持久化）。"""

    def __init__(self) -> None:
        self.store: List[Dict[str, Any]] = []

    async def write(self, records: List[Dict[str, Any]], meta: Dict[str, Any]) -> SinkResult:
        self.store.extend(records)
        return SinkResult(written=len(records), detail=f"in_memory:{len(self.store)}")


class BaseConnector(ABC):
    """连接器基类（按 connector_type 通过注册表分派）。"""

    connector_type: str = "base"

    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config
        self.validate_config(config)

    # pylint: disable=unused-argument
    def validate_config(self, config: ConnectorConfig) -> None:
        """配置校验；子类可覆盖。基类仅做基础非空检查。"""
        if not (config.base_url or "").strip():
            raise ValueError("base_url 不能为空")

    @abstractmethod
    async def test_connection(self) -> bool:
        """探测连通性；返回是否可达且认证通过。"""

    @abstractmethod
    async def pull(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """拉取记录（遵循分页配置），返回归一化 dict 列表。

        ``since`` 为增量游标（上轮 ``last_cursor``），由支持增量的连接器用于过滤。
        """

    async def sync(self, sink: ConnectorSink, since: Optional[str] = None) -> SinkResult:
        """拉取并落库；把增量游标（若有）透传给 sink 持久化。"""
        records = await self.pull(since=since)
        meta = {
            "connector_type": self.connector_type,
            "incremental_field": self.config.incremental_field,
            "last_cursor": getattr(self, "last_cursor", None),
        }
        return await sink.write(records, meta)
