"""OAuth2 REST 连接器基类（P3 Task 2~5）。

钉钉/飞书/企业微信等开放平台通用模式：先拿 access_token，再带令牌请求数据接口。
本类封装「取令牌 → 带令牌拉数据」流程，并把令牌请求形态（query/json、字段名）
与令牌注入方式（Bearer 头 / access_token 查询参数）留给子类配置；数据拉取复用
``HttpConnector`` 的分页/字段映射/增量逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.connectors.http import HttpConnector


class OAuth2ApiConnector(HttpConnector):
    """OAuth2 开放平台连接器基类（connector_type 由子类设定）。"""

    async def _fetch_token(self) -> str:
        cfg = self.config
        if not cfg.token_url:
            raise ValueError("OAuth2 连接器必须配置 token_url")
        async with httpx.AsyncClient(timeout=cfg.timeout, follow_redirects=True) as client:
            method = (cfg.token_method or "POST").upper()
            kwargs: Dict[str, Any] = {}
            if cfg.token_query:
                kwargs["params"] = cfg.token_query
            if cfg.token_body:
                kwargs["json"] = cfg.token_body
            resp = await client.request(method, cfg.token_url, **kwargs)
            resp.raise_for_status()
            data = resp.json()
            token = data.get(cfg.token_field or "access_token")
            if not token:  # 部分平台嵌套字段名不同，做一次兜底
                token = data.get("access_token") or data.get("tenant_access_token")
            if not token:
                raise ValueError(f"获取访问令牌失败，响应: {data}")
            return token

    async def _resolve_token(self) -> Optional[str]:
        # 缓存，避免 test_connection + pull 两次取令牌
        if getattr(self, "_token", None):
            return self._token
        if self.config.auth_token:
            self._token = self.config.auth_token
            return self._token
        self._token = await self._fetch_token()
        return self._token

    async def _prepare_auth(self) -> None:
        """取令牌并注入：Bearer 头（默认）或 access_token 查询参数（钉钉/企业微信）。"""
        token = await self._resolve_token()
        self.config.auth_token = token
        if self.config.token_in == "query":
            self.config.params = {**self.config.params, self.config.token_query_name: token}

    async def test_connection(self) -> bool:
        try:
            await self._prepare_auth()
            async with await self._client() as client:
                resp = await client.request(
                    self.config.method, self._data_path(), params=self.config.params
                )
                return resp.status_code < 400
        except Exception:  # noqa: BLE001 - 任何连接/超时/鉴权异常均视为不可达
            return False

    async def pull(self, since: Optional[str] = None) -> list:
        await self._prepare_auth()
        return await super().pull(since=since)

    def _data_path(self) -> str:
        return self.config.data_path or "/"
