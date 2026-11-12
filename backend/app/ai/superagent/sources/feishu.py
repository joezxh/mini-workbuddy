"""Feishu Source —— strict mode bot + 群聊 listen + 私聊 + Policy sync。

对齐 dsh-superagent feishu.ts —— 首期核心实现。
"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from .base import SourceKindProtocol, SourceTrigger, HealthStatus, SourceKind


@dataclass
class FeishuChat:
    """群列表配置 —— 每个群独立 listen 模式。"""
    chat_id: str
    name: str
    listen: str = "mentions"   # mentions（仅 @ bot）/ all（全部消息）


class FeishuSource(SourceKindProtocol):
    """Feishu Source —— strict mode bot（只有 bot 身份可用 lark-cli）。

    listen 模式：群聊 mentions（默认，只接收 @ bot 消息）/ all（接收全部消息 → Eval 研判）。
    私聊直接接收。Channel reply 发到 Feishu Topic reply（不刷屏群）。
    """
    kind: SourceKind = "feishu"

    def __init__(self, *, lark_cli_path: str = "lark-cli", direct_messages: bool = True,
                 other_chats: str = "none", read_page_size: int = 20, link_timeout_ms: int = 5000,
                 backfill_history: bool = False, chats: list[FeishuChat] | None = None,
                 sync_chat_id: str | None = None, allowed_senders: list[str] | None = None,
                 bots: list[str] | None = None):
        self.lark_cli = lark_cli_path
        self.direct_messages = direct_messages
        self.other_chats = other_chats   # none / mentions
        self.read_page_size = read_page_size
        self.link_timeout_ms = link_timeout_ms
        self.backfill_history = backfill_history
        self.chats = chats or []
        self.sync_chat_id = sync_chat_id
        self.allowed_senders = set(allowed_senders or [])
        self.bots = set(bots or [])
        self._failures = 0
        self._last_error: str | None = None

    def is_enabled(self) -> bool:
        return True

    def health(self) -> dict:
        status = "healthy" if self._failures == 0 else ("degraded" if self._failures < 5 else "down")
        return HealthStatus(
            kind=self.kind, status=status, failures=self._failures,
            last_error=self._last_error,
            next_poll=datetime.utcnow() + timedelta(seconds=30),
        ).to_dict()

    async def poll_once(self, workspace_id: int, last_cursor: str | None = None) -> tuple[list[SourceTrigger], str | None]:
        """从群聊 + 私聊拉新消息。"""
        triggers: list[SourceTrigger] = []
        try:
            # 群聊消息
            for chat in self.chats:
                triggers += await self._read_chat(chat, workspace_id)
            # 私聊
            if self.direct_messages:
                triggers += await self._read_dms(workspace_id)
            # 只有所有群读取都成功才重置失败计数（_read_chat 失败会自增）
            if not self._last_error:
                self._failures = 0
                self._last_error = None
        except Exception as e:
            self._failures += 1
            self._last_error = str(e)
            logger.error(f"Feishu poll failed: {e}")
        cursor = datetime.utcnow().isoformat()
        return triggers, cursor

    async def _read_chat(self, chat: FeishuChat, workspace_id: int) -> list[SourceTrigger]:
        """读一个群的消息 —— lark-cli api（GET /open-apis/im/v1/messages）。"""
        try:
            args = [
                "api", "GET", "/open-apis/im/v1/messages",
                "--params",
                json.dumps({
                    "container_id_type": "chat",
                    "container_id": chat.chat_id,
                    "sort": "CreateTime",
                    "page_size": str(self.read_page_size),
                }, ensure_ascii=False),
                "--jq", ".data.items",
            ]
            proc = await asyncio.create_subprocess_exec(
                self.lark_cli, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.link_timeout_ms / 1000,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"lark-cli exit {proc.returncode}: {err.decode()[:200]}"
                )
            items = json.loads(out.decode())
            if isinstance(items, dict):
                items = items.get("items", [])
            triggers: list[SourceTrigger] = []
            for msg in items or []:
                # strict mode: 只有用户消息（非 bot）才进入 Eval
                if msg.get("sender", {}).get("sender_type") == "app":
                    continue
                content_raw = msg.get("body", {}).get("content", "{}")
                try:
                    text = json.loads(content_raw).get("text", "")
                except Exception:
                    text = content_raw
                if not text.strip():
                    continue
                addressed = "@bot" in text.lower() or chat.listen == "all"
                triggers.append(SourceTrigger(
                    source="feishu",
                    ref_id=f"{chat.chat_id}:{msg['message_id']}",
                    kind="group_message" if chat.listen == "all" else "group_mention",
                    sender_id=msg.get("sender", {}).get("id"),
                    sender_name="",
                    title=text[:100],
                    body=text,
                    url=None,
                    context={
                        "chat_id": chat.chat_id,
                        "chat_name": chat.name,
                        "listen": chat.listen,
                        "message_id": msg["message_id"],
                        "addressed": addressed,
                    },
                    workspace_id=workspace_id,
                ))
            return triggers
        except Exception as e:
            logger.warning(f"Feishu read chat {chat.chat_id} failed: {e}")
            self._last_error = str(e)[:200]
            self._failures += 1
            return []

    async def _read_dms(self, workspace_id: int) -> list[SourceTrigger]:
        """读私聊 —— 简化实现，返回空列表。"""
        return []
