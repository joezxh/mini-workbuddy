"""企业微信连接器（P3 Task 2~5 具体连接器类型）。

企业微信开放平台：``/cgi-bin/gettoken?corpid=&corpsecret=`` 拿 ``access_token``；
数据接口带 ``access_token`` 查询参数。corpid 对应 ``client_id``、corpsecret 对应
``client_secret``。
"""
from __future__ import annotations

from app.connectors.base import ConnectorConfig
from app.connectors.types.oauth2 import OAuth2ApiConnector


class WeComConnector(OAuth2ApiConnector):
    connector_type = "wecom"

    def __init__(self, config: ConnectorConfig) -> None:
        cfg = config.model_copy(deep=True)
        cfg.token_url = cfg.token_url or "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        cfg.token_method = "GET"  # 企业微信 gettoken 用 GET + query
        cfg.token_field = cfg.token_field or "access_token"
        cfg.token_in = "query"   # 企业微信数据接口用 access_token 查询参数
        if not cfg.token_query and cfg.client_id and cfg.client_secret:
            cfg.token_query = {"corpid": cfg.client_id, "corpsecret": cfg.client_secret}
        super().__init__(cfg)
