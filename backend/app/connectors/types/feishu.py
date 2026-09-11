"""飞书连接器（P3 Task 2~5 具体连接器类型）。

飞书开放平台：``/auth/v3/tenant_access_token/internal`` 以 JSON 体
``{app_id, app_secret}`` 拿 ``tenant_access_token``；数据接口带 Bearer 令牌。
"""
from __future__ import annotations

from app.connectors.base import ConnectorConfig
from app.connectors.types.oauth2 import OAuth2ApiConnector


class FeishuConnector(OAuth2ApiConnector):
    connector_type = "feishu"

    def __init__(self, config: ConnectorConfig) -> None:
        cfg = config.model_copy(deep=True)
        cfg.token_url = cfg.token_url or "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        cfg.token_method = cfg.token_method or "POST"
        cfg.token_field = cfg.token_field or "tenant_access_token"
        if not cfg.token_body and cfg.client_id and cfg.client_secret:
            cfg.token_body = {"app_id": cfg.client_id, "app_secret": cfg.client_secret}
        super().__init__(cfg)
