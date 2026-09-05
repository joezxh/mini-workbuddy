"""
SQLBot 中间件
封装 SQLBot API Key (ASK Token) 认证及所有 API 调用。

认证原理：
  - Access Key 存储在 JWT payload 中（明文，作为公开标识符）
  - Secret Key 用于本地签名 JWT（不传输，仅用于签名）
  - 后端使用数据库中存储的 Secret Key 验证签名
  - Header 格式：X-SQLBOT-ASK-TOKEN: SK {jwt_token}

参考：docs/sqlbot/examples/apikey_example.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import jwt
from loguru import logger

from app.config import settings


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _sse(obj: dict) -> str:
    """将字典序列化为 SSE 行字符串"""
    return f'data: {json.dumps(obj, ensure_ascii=False)}\n\n'


def generate_ask_token(
    access_key: str,
    secret_key: str,
    expire_hours: int = 1,
) -> str:
    """
    生成 ASK Token（API Key Token）。

    Args:
        access_key: 公开标识符（来自 SQLBot 管理界面）
        secret_key: 私钥，仅用于本地 JWT 签名，不传输
        expire_hours: Token 有效期（小时），默认 1 小时

    Returns:
        JWT 字符串，使用方式：``X-SQLBOT-ASK-TOKEN: SK {token}``
    """
    now = datetime.utcnow()
    payload = {
        "access_key": access_key,
        "exp": now + timedelta(hours=expire_hours),
        "iat": now,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


# ---------------------------------------------------------------------------
# SQLBot 客户端
# ---------------------------------------------------------------------------

class SqlBotClient:
    """
    SQLBot 私有化部署 API 客户端。

    封装完整的 API Key 认证流程及所有 API 接口调用。
    Token 在有效期内自动缓存复用，避免重复生成。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        datasource_id: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.SQLBOT_API_URL).rstrip("/")
        self.access_key = access_key or settings.SQLBOT_ACCESS_KEY
        self.secret_key = secret_key or settings.SQLBOT_SECRET_KEY
        self.datasource_id = datasource_id or settings.SQLBOT_DATASOURCE_ID
        self.timeout = timeout or settings.SQLBOT_TIMEOUT
        # Token 缓存
        self._token: Optional[str] = None
        self._token_expire: float = 0.0
        # 数据源列表缓存（10 分钟过期）
        self._datasources_cache: Optional[List[Dict[str, Any]]] = None
        self._datasources_cache_expire: float = 0.0
        self._datasources_cache_ttl: float = 600  # 10 分钟

    # ------------------------------------------------------------------
    # 认证
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """获取或复用 ASK Token（有效期内缓存，提前 60s 续期）"""
        now = time.time()
        if self._token and now < self._token_expire:
            return self._token
        self._token = generate_ask_token(self.access_key, self.secret_key, expire_hours=1)
        self._token_expire = now + 3600 - 60
        logger.debug("SQLBot ASK Token 已生成/刷新")
        return self._token

    def _headers(self) -> Dict[str, str]:
        """构造请求 Header，使用 X-SQLBOT-ASK-TOKEN: SK {token}"""
        return {
            "X-SQLBOT-ASK-TOKEN": f"SK {self._get_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "zh-CN",
        }

    def _api(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    # ------------------------------------------------------------------
    # 系统 / 数据源接口
    # ------------------------------------------------------------------

    async def get_user_info(self) -> Dict[str, Any]:
        """获取当前用户信息"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(self._api("/user/info"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def list_datasources(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """GET /api/v1/datasource/list — 数据源列表（带缓存，默认 10 分钟）"""
        now = time.time()
        if use_cache and self._datasources_cache and now < self._datasources_cache_expire:
            logger.debug("SQLBot 数据源列表命中缓存")
            return self._datasources_cache
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(self._api("/datasource/list"), headers=self._headers())
            r.raise_for_status()
            data = r.json()
            result = data if isinstance(data, list) else data.get("data", data)
            # 写入缓存
            self._datasources_cache = result
            self._datasources_cache_expire = now + self._datasources_cache_ttl
            logger.debug(f"SQLBot 数据源列表已刷新缓存（{len(result) if isinstance(result, list) else 0} 条）")
            return result

    def invalidate_datasources_cache(self) -> None:
        """手动清除数据源列表缓存（供外部调用以强制刷新）"""
        self._datasources_cache = None
        self._datasources_cache_expire = 0.0
        logger.debug("SQLBot 数据源列表缓存已清除")

    async def list_datasources_for_dict(self) -> List[Dict[str, Any]]:
        """获取 SQLBot 数据源列表，用于数据字典同步参考。
        返回格式: [{"id": 4, "name": "xxx", "db_type": "postgresql", ...}]
        """
        try:
            raw = await self.list_datasources()
            result = []
            for ds in (raw if isinstance(raw, list) else []):
                result.append({
                    "id": ds.get("id"),
                    "name": ds.get("name") or ds.get("title"),
                    "db_type": ds.get("db_type") or ds.get("type"),
                    "host": ds.get("host", ""),
                    "database": ds.get("database") or ds.get("db_name", ""),
                })
            return result
        except Exception as exc:
            logger.error(f"获取 SQLBot 数据源列表失败: {exc}")
            return []

    async def get_workspace(self) -> Dict[str, Any]:
        """GET /api/v1/system/workspace — 查询所有工作空间"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(self._api("/system/workspace"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # 对话管理接口
    # ------------------------------------------------------------------

    async def list_chats(
        self,
        page: int = 1,
        page_size: int = 20,
        datasource_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/chat/list — 获取对话列表"""
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if datasource_id is not None:
            params["datasource_id"] = datasource_id
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(self._api("/chat/list"), headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()

    async def get_chat(self, chat_id: int) -> Dict[str, Any]:
        """GET /api/v1/chat/{chat_id} — 获取对话详情"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(self._api(f"/chat/{chat_id}"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def get_chat_with_data(self, chat_id: int) -> Dict[str, Any]:
        """GET /api/v1/chat/{chat_id}/with_data — 获取对话详情（带数据）"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(self._api(f"/chat/{chat_id}/with_data"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def get_record_data(self, chat_record_id: int) -> List[Dict[str, Any]]:
        """GET /api/v1/chat/record/{chat_record_id}/data — 获取图表数据（纯净列表）"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(
                self._api(f"/chat/record/{chat_record_id}/data"),
                headers=self._headers(),
            )
            r.raise_for_status()
            data = r.json()
            inner = data.get("data", {})
            return inner.get("data", []) if isinstance(inner, dict) else []

    async def get_record_predict_data(self, chat_record_id: int) -> Dict[str, Any]:
        """GET /api/v1/chat/record/{chat_record_id}/predict_data — 获取图表预测数据"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(
                self._api(f"/chat/record/{chat_record_id}/predict_data"),
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_record_log(self, chat_record_id: int) -> Dict[str, Any]:
        """GET /api/v1/chat/record/{chat_record_id}/log — 获取对话日志"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(
                self._api(f"/chat/record/{chat_record_id}/log"),
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_record_usage(self, chat_record_id: int) -> Dict[str, Any]:
        """GET /api/v1/chat/record/{chat_record_id}/usage — 获取 Token 使用量及耗时"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(
                self._api(f"/chat/record/{chat_record_id}/usage"),
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # 核心查询流程（4 步合并）
    # ------------------------------------------------------------------

    async def _start_chat(self, client: httpx.AsyncClient, question: str, datasource_id: Optional[int] = None) -> int:
        """Step 2: POST /api/v1/chat/start — 建立会话，返回 chat_id"""
        ds_id = datasource_id or self.datasource_id
        payload = {
            "question": question,
            "datasource": ds_id,
            "origin": 0,
        }
        r = await client.post(
            self._api("/chat/start"),
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        chat_id: int = data["data"]["id"]
        logger.debug(f"SQLBot 会话建立成功 chat_id={chat_id}")
        return chat_id

    async def _ask_question_stream(
        self,
        client: httpx.AsyncClient,
        question: str,
        chat_id: int,
        datasource_id: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Step 3: POST /api/v1/chat/question（流式）。
        yield 各阶段事件字典：
          {"event": "record_id", "id": 107}
          {"event": "sql",       "sql": "SELECT ..."}
          {"event": "info",      "msg": "sql generated"}
          {"event": "finish"}
        """
        ds_id = datasource_id or self.datasource_id
        payload = {
            "question": question,
            "ai_modal_id": 0,
            "ai_modal_name": "",
            "engine": "",
            "db_schema": "public",
            "sql": "",
            "rule": "",
            "fields": "",
            "data": "",
            "lang": "简体中文",
            "sub_query": [],
            "terminologies": "",
            "data_training": "",
            "custom_prompt": "",
            "error_msg": "",
            "regenerate_record_id": 0,
            "chat_id": chat_id,
            "datasource_id": ds_id,
        }
        async with client.stream(
            "POST",
            self._api("/chat/question"),
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                ctype = chunk.get("type", "")
                if ctype == "id":
                    yield {"event": "record_id", "id": chunk.get("id")}
                elif ctype == "sql":
                    yield {"event": "sql", "sql": chunk.get("content", "")}
                elif ctype == "info":
                    yield {"event": "info", "msg": chunk.get("msg", "")}
                elif ctype == "finish":
                    yield {"event": "finish"}
                    return

    async def query(self, question: str, datasource_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        段式查询：完整执行 4 步流程，阻塞返回纯净数据列表。

        步骤：
          1. 生成 ASK Token（本地 JWT 签名，无网络请求）
          2. POST /api/v1/chat/start
          3. POST /api/v1/chat/question（流式，收取 record_id）
          4. GET  /api/v1/chat/record/{record_id}/data
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            chat_id = await self._start_chat(client, question, datasource_id=datasource_id)
            record_id: Optional[int] = None
            async for evt in self._ask_question_stream(client, question, chat_id, datasource_id=datasource_id):
                if evt["event"] == "record_id":
                    record_id = evt["id"]
                elif evt["event"] == "finish":
                    break
                elif evt["event"] == "error":
                    raise RuntimeError(f"SQLBot 查询失败: {evt.get('msg')}")
            if record_id is None:
                raise RuntimeError("SQLBot 未返回 record_id，无法获取数据")
            return await self.get_record_data(record_id)

    async def query_stream(
        self,
        question: str,
        chat_id: Optional[int] = None,
        datasource_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式查询：支持多轮对话上下文。

        Args:
            question: 用户自然语言问题
            chat_id: 已有的 SQLBot 会话 ID。传入时复用该会话（多轮对话），
                     不传则新建会话。
            datasource_id: 数据源 ID，不传则使用默认数据源。

        SSE 事件格式::

            data: {"type": "info",    "message": "Step X/4: ..."}
            data: {"type": "sql",     "sql": "SELECT ..."}
            data: {"type": "done",    "records": [...], "total": N, "chat_id": M}
            data: {"type": "error",   "message": "..."}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Step 1: 生成 Token（本地，无网络请求）
                self._get_token()
                yield _sse({"type": "info", "message": "Step 1/4: ASK Token 已就绪"})

                # Step 2: 建立或复用会话
                if chat_id:
                    # 复用已有 SQLBot 会话（多轮对话）
                    yield _sse({"type": "info", "message": f"Step 2/4: 复用 SQLBot 会话 chat_id={chat_id}"})
                else:
                    # 新建会话
                    yield _sse({"type": "info", "message": "Step 2/4: 建立 SQLBot 查询会话..."})
                    chat_id = await self._start_chat(client, question, datasource_id=datasource_id)
                    yield _sse({"type": "info", "message": f"Step 2/4: 会话建立成功 chat_id={chat_id}"})

                # Step 3: 提交问题（流式）
                yield _sse({"type": "info", "message": "Step 3/4: 提交 NL2SQL 查询，等待 SQL 生成..."})
                record_id: Optional[int] = None
                async for evt in self._ask_question_stream(client, question, chat_id, datasource_id=datasource_id):
                    if evt["event"] == "record_id":
                        record_id = evt["id"]
                    elif evt["event"] == "sql":
                        yield _sse({"type": "sql", "sql": evt["sql"]})
                    elif evt["event"] == "info":
                        yield _sse({"type": "info", "message": evt["msg"]})
                    elif evt["event"] == "finish":
                        break
                    elif evt["event"] == "error":
                        yield _sse({"type": "error", "message": evt.get("msg", "未知错误")})
                        return

                if record_id is None:
                    yield _sse({"type": "error", "message": "SQLBot 未返回 record_id"})
                    return

                # Step 4: 获取数据
                yield _sse({"type": "info", "message": f"Step 4/4: 获取查询结果 record_id={record_id}..."})
                records = await self.get_record_data(record_id)
                # done 事件中携带 chat_id，供前端回传实现多轮对话
                yield _sse({"type": "done", "records": records, "total": len(records), "chat_id": chat_id})

            except Exception as exc:
                logger.error(f"SqlBotClient.query_stream 失败: {exc}")
                yield _sse({"type": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# 模块级单例（token 在进程内复用）
# ---------------------------------------------------------------------------

sqlbot_client = SqlBotClient()

