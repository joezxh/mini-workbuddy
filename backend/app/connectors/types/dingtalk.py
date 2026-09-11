"""钉钉连接器（P3 Task 2~5 具体连接器类型）。

钉钉开放平台：``/gettoken?appkey=&appsecret=`` 拿 token；数据接口带 ``access_token``
查询参数。本类仅预置钉钉的令牌端点与请求形态，其余（数据路径、字段映射、
增量）由 ``ConnectorConfig`` 配置驱动。
"""
from __future__ import annotations

from app.connectors.base import ConnectorConfig
from app.connectors.types.oauth2 import OAuth2ApiConnector


class DingtalkConnector(OAuth2ApiConnector):
    connector_type = "dingtalk"

    def __init__(self, config: ConnectorConfig) -> None:
        # 预置钉钉令牌端点与 query 形态（appkey/appsecret），允许配置覆盖
        cfg = config.model_copy(deep=True)
        cfg.token_url = cfg.token_url or "https://oapi.dingtalk.com/gettoken"
        cfg.token_method = "GET"  # 钉钉 gettoken 用 GET + query
        cfg.token_field = cfg.token_field or "access_token"
        cfg.token_in = "query"   # 钉钉数据接口用 access_token 查询参数
        if not cfg.token_query and cfg.client_id and cfg.client_secret:
            cfg.token_query = {"appkey": cfg.client_id, "appsecret": cfg.client_secret}
        super().__init__(cfg)
