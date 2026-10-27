"""Slack 文档源（``source_type=slack``）。

认证：Bot Token（``xoxb-``）或 User Token（``xoxp-``），请求头
``Authorization: Bearer <token>``。

**错误判定与基座约定不同（重要）**：Slack Web API 在 **HTTP 200** 下用
``{"ok": false, "error": "invalid_auth"}`` 表达失败。基类的
``_raise_if_platform_error`` 面向「数值业务码」（飞书 ``code`` / 钉钉 ``errcode``），
无法表达布尔 ``ok``，故本模块在 ``_call()`` 内自行判 ``ok`` 并抛 ``DocSourceError``，
不复用 ``error_code_field``。

枚举：``conversations.list``（跳过归档频道，cursor 分页）→ 频道为目录；
``conversations.history`` 取近期消息，**只有带回复的消息（thread）才作为可导入文档**
——单条孤零零的消息正文过短，导入价值低且噪声大。
正文：``conversations.replies`` 拉整楼，渲染为「作者 + 时间 + 内容」的 Markdown 记录。

权限（Bot Token Scopes）：``channels:read`` / ``groups:read`` / ``channels:history`` /
``groups:history``；私有频道还需把机器人邀请进频道。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.connectors.doc_sources.base import (
    BaseDocSource,
    CredField,
    DocConnResult,
    DocSourceError,
    ExternalDocRef,
    FetchDocResult,
    ProviderMeta,
    register_doc_source,
)

logger = logging.getLogger(__name__)

HOST = "https://slack.com"
API_PREFIX = "/api"
AUTH_TEST = "/api/auth.test"
CONVERSATIONS_LIST = "/api/conversations.list"
CONVERSATIONS_HISTORY = "/api/conversations.history"
CONVERSATIONS_REPLIES = "/api/conversations.replies"

# 频道与历史消息的拉取上限
MAX_CHANNEL_PAGES = 20
CHANNEL_PAGE_SIZE = 200
DEFAULT_HISTORY_LIMIT = 200
HISTORY_LIMIT_MAX = 1000


def _encode_channel(channel_id: str) -> str:
    return f"ch:{channel_id}"


def _encode_thread(channel_id: str, thread_ts: str) -> str:
    return f"th:{channel_id}:{thread_ts}"


def _decode(doc_id: str) -> Tuple[str, ...]:
    parts = (doc_id or "").split(":")
    if len(parts) == 2 and parts[0] == "ch":
        return "ch", parts[1]
    if len(parts) == 3 and parts[0] == "th":
        return "th", parts[1], parts[2]
    raise DocSourceError(f"无法解析的 Slack 标识：{doc_id}")


def _ts_to_text(ts: str) -> str:
    """Slack 的时间戳是 ``秒.微秒`` 字符串。"""
    try:
        seconds = float(ts or 0)
    except ValueError:
        return ""
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class SlackDocSource(BaseDocSource):
    source_type = "slack"
    token_in = "none"   # Bearer 由 _auth_headers 组装
    # 见模块 docstring：自行判 ok，不复用数值业务码机制
    error_code_field = None
    timeout = 30.0

    # ── 凭据 ──────────────────────────────────────────────────
    def _auth_headers(self) -> Dict[str, str]:
        token = (self.credentials.get("token") or "").strip()
        if not token:
            raise DocSourceError("缺少 Slack Token（xoxb- 或 xoxp- 开头）")
        return {"Authorization": f"Bearer {token}"}

    def _history_limit(self) -> int:
        try:
            value = int(str(self.credentials.get("history_limit") or "").strip()
                        or DEFAULT_HISTORY_LIMIT)
        except ValueError:
            value = DEFAULT_HISTORY_LIMIT
        return max(1, min(value, HISTORY_LIMIT_MAX))

    # ── 平台调用 ──────────────────────────────────────────────
    async def _call(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """统一 POST 调用，并把 ``ok: false`` 转成 DocSourceError。"""
        body = await self._request_json(
            "POST", f"{HOST}{path}", headers=self._auth_headers(),
            json_body=dict(payload or {}),
        )
        if not (body or {}).get("ok", False):
            error = (body or {}).get("error") or "unknown_error"
            raise DocSourceError(f"Slack 返回错误：{error}（{_slack_error_hint(error)}）")
        return body or {}

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            data = await self._call(AUTH_TEST, {})
            identity = " · ".join(
                x for x in (data.get("team"), data.get("user")) if x
            ) or "凭据有效"
            return DocConnResult(ok=True, message="连通成功：Token 有效", identity=identity)
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return await self._list_channels()
            parts = _decode(parent_id)
            if parts[0] != "ch":
                return []
            return await self._list_threads(parts[1])
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            parts = _decode(doc_id)
            if parts[0] != "th":
                raise DocSourceError(f"{doc_id} 不是可导入的会话")
            channel_id, thread_ts = parts[1], parts[2]
            data = await self._call(CONVERSATIONS_REPLIES, {
                "channel": channel_id, "ts": thread_ts, "limit": 200,
            })
            messages = data.get("messages") or []
            if not messages:
                raise DocSourceError("该会话下没有可读取的消息")
            title = _first_line(messages[0].get("text")) or f"会话 {thread_ts}"
            return FetchDocResult(
                title=title[:120],
                markdown=render_thread(messages, channel_id),
                updated_at=_ts_to_text(messages[-1].get("ts") or ""),
            )
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _list_channels(self) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        cursor = ""
        for _ in range(MAX_CHANNEL_PAGES):
            payload: Dict[str, Any] = {
                "limit": CHANNEL_PAGE_SIZE,
                "exclude_archived": True,
                "types": "public_channel,private_channel",
            }
            if cursor:
                payload["cursor"] = cursor
            data = await self._call(CONVERSATIONS_LIST, payload)
            for c in data.get("channels") or []:
                cid = c.get("id") or ""
                if not cid:
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=_encode_channel(cid),
                        title=f"# {c.get('name') or cid}",
                        node_type="folder",
                    )
                )
            cursor = ((data.get("response_metadata") or {}).get("next_cursor")) or ""
            if not cursor:
                break
        return refs

    async def _list_threads(self, channel_id: str) -> List[ExternalDocRef]:
        data = await self._call(CONVERSATIONS_HISTORY, {
            "channel": channel_id, "limit": self._history_limit(),
        })
        refs: List[ExternalDocRef] = []
        for m in data.get("messages") or []:
            ts = m.get("ts") or ""
            if not ts:
                continue
            # 只有「有人回复」的消息才作为文档：单条消息信息量过低
            if not (m.get("reply_count") or m.get("thread_ts")):
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=_encode_thread(channel_id, ts),
                    title=_first_line(m.get("text")) or f"会话 {ts}",
                    node_type="doc",
                    parent_id=_encode_channel(channel_id),
                    updated_at=_ts_to_text(ts),
                )
            )
        return refs


def _first_line(text: Optional[str]) -> str:
    """取首行作为标题，去掉 Slack 的换行与多余空白。"""
    return (text or "").strip().splitlines()[0].strip() if (text or "").strip() else ""


def render_thread(messages: List[Dict[str, Any]], channel_id: str) -> str:
    """把整楼消息渲染成 Markdown 记录（作者 / 时间 / 正文）。"""
    lines: List[str] = []
    for m in messages:
        author = m.get("user") or m.get("username") or m.get("bot_id") or "unknown"
        when = _ts_to_text(m.get("ts") or "")
        text = (m.get("text") or "").strip()
        lines.append(f"- **{author}**（{when}）：{text}")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _slack_error_hint(error: str) -> str:
    """把常见 Slack 错误码映射成可操作的中文提示。"""
    return {
        "invalid_auth": "Token 无效或已吊销",
        "not_authed": "未提供凭据",
        "missing_scope": "Token 缺少所需 scope（channels:read / channels:history 等）",
        "channel_not_found": "频道不存在或机器人未被邀请进该私有频道",
        "ratelimited": "被限流，请稍后重试",
    }.get(error, "详见 Slack 错误码文档")


register_doc_source(
    "slack",
    SlackDocSource,
    ProviderMeta(
        source_type="slack",
        name="Slack",
        desc="频道内的讨论串（线程）",
        host=HOST,
        credential_fields=(
            CredField("token", "Bot / User Token", required=True, secret=True,
                      placeholder="xoxb-xxxxxxxx",
                      hint="需 channels:read / groups:read / channels:history 等 scope；"
                           "私有频道还需把机器人邀请进去"),
            CredField("history_limit", "每个频道拉取消息数", placeholder="200",
                      hint=f"默认 {DEFAULT_HISTORY_LIMIT}，上限 {HISTORY_LIMIT_MAX}"),
        ),
    ),
)
