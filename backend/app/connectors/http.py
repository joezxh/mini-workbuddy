"""HTTP / REST 连接器（P3 Task 1，消费 httpx）。

通用 REST 拉取：支持鉴权头注入、dotted 记录路径提取、三种分页
（page / offset / cursor），连通性探测。覆盖重试用 ``respx`` 单测。

P3 Task 2~5 增强：拉取后应用 ``field_map`` 字段映射，并支持增量游标
（``incremental_field`` + ``incremental_param``）。

实现预留两个扩展钩子供具体连接器（钉钉/飞书/企业微信等 OAuth2 类）覆写：
``_resolve_token``（鉴权令牌来源）与 ``_data_path``（数据请求路径）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.connectors.base import BaseConnector, ConnectorConfig
from app.connectors.mapping import apply_field_map


def _extract_path(obj: Any, path: Optional[str]) -> Any:
    """按 dotted 路径从响应 JSON 取值；路径为空且 obj 是列表则直接返回。"""
    if not path:
        return obj
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


class HttpConnector(BaseConnector):
    """通用 HTTP 连接器。"""

    connector_type = "http"

    async def _resolve_token(self) -> Optional[str]:
        """返回本次请求使用的 Bearer 令牌；子类（OAuth2）可覆写以动态获取。"""
        return self.config.auth_token

    def _data_path(self) -> str:
        """数据请求路径；OAuth2 类连接器覆写为具体 API 路径。"""
        return "/"

    async def _client(self, token: Optional[str] = None) -> httpx.AsyncClient:
        headers = dict(self.config.headers)
        auth = token or self.config.auth_token
        if auth:
            headers.setdefault("Authorization", f"Bearer {auth}")
        return httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            timeout=self.config.timeout,
            follow_redirects=True,
        )

    def _next_page_params(self, params: Dict[str, Any], page_state: Any, body: Any):
        """返回 ``(下一页参数, 新页状态)``；无更多页返回 None。"""
        pg = self.config.pagination
        if pg.type == "none":
            return None
        if pg.type == "page":
            nxt = (page_state or pg.start) + 1
            return {**params, pg.param: nxt}, nxt  # type: ignore[return-value]
        if pg.type == "offset":
            nxt = (page_state or 0) + pg.step
            return {**params, pg.param: nxt}, nxt
        if pg.type == "cursor":
            nxt = _extract_path(body, pg.next_path)
            if not nxt:
                return None
            return {**params, pg.param: nxt}, nxt
        return None

    def _apply_incremental(self, params: Dict[str, Any], since: Optional[str]) -> Dict[str, Any]:
        """若配置了增量参数且提供了 since，把游标作为查询参数注入。"""
        if since and self.config.incremental_param:
            return {**params, self.config.incremental_param: since}
        return params

    async def test_connection(self) -> bool:
        try:
            token = await self._resolve_token()
            async with await self._client(token) as client:
                resp = await client.request(self.config.method, self._data_path(), params=self.config.params)
                return resp.status_code < 400
        except Exception:  # noqa: BLE001 - 任何连接/超时异常均视为不可达
            return False

    async def pull(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        params = self._apply_incremental(dict(self.config.params), since)
        page_state: Any = None
        # 初始页状态：page=start，offset=0
        pg = self.config.pagination
        if pg.type == "page":
            page_state = pg.start
            params = {**params, pg.param: page_state}
        elif pg.type == "offset":
            page_state = 0
            params = {**params, pg.param: page_state}

        token = await self._resolve_token()
        async with await self._client(token) as client:
            while True:
                resp = await client.request(
                    self.config.method, self._data_path(), params=params,
                )
                resp.raise_for_status()
                body = resp.json()
                page_records = _extract_path(body, self.config.records_path)
                if page_records is None:
                    # 路径取不到 → 视为单条记录或无数据
                    if isinstance(body, dict):
                        page_records = [body]
                    else:
                        page_records = []
                if not isinstance(page_records, list):
                    page_records = [page_records]
                records.extend(page_records)

                # 当前页为空 → 已到末页，停止（避免对空页继续翻页耗尽 side_effect）
                if not page_records:
                    break

                nxt = self._next_page_params(params, page_state, body)
                if nxt is None:
                    break
                params, page_state = nxt
                if len(records) > 1_000_000:  # 安全阀，避免异常分页无限循环
                    break

        # 字段映射（外部字段 → 内部目标字段）
        mapped = apply_field_map(records, self.config.field_map)
        # 增量游标：取映射后 incremental_field 的最大值（字符串序，覆盖日期/自增 ID）
        self.last_cursor = self._compute_last_cursor(mapped)
        return mapped

    def _compute_last_cursor(self, mapped: List[Dict[str, Any]]) -> Optional[str]:
        field = self.config.incremental_field
        if not field or not mapped:
            return None
        values = [r.get(field) for r in mapped if r.get(field) is not None]
        if not values:
            return None
        # 若全部可转为数字（自增 ID / 时间戳），用数值比较；否则按字符串序（ISO 日期也正确）
        try:
            nums = [float(v) for v in values]
            return str(int(max(nums))) if all(float(v).is_integer() for v in values) else str(max(nums))
        except (ValueError, TypeError):
            return max(str(v) for v in values)
