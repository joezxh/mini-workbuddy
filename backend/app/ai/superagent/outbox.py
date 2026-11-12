"""OutboxService —— 4 类外发消息出口（ack / attention / result / reply）。

对齐 dsh-superagent outbox.ts。通道实现：
  - SSE   — 复用 sse_bus.sse_publish（前端 Feed 实时消费）
  - Feishu — 经 lark-cli `api POST /open-apis/im/v1/messages` 发送群消息
             （与 sources/feishu.py 读取路径同一身份：strict mode bot）。
             目标群解析顺序：显式 default_chat_id → ai_workspace.config
             feishu_source_cfg 首个 chat（发送到 listen 群，不新增配置面）。
"""
from __future__ import annotations
import asyncio
import json

from loguru import logger


class OutboxService:
    """统一外发消息出口 —— Engine/Effect handler 都经由这里投递。"""

    def __init__(self, default_channel: str = "sse",
                 lark_cli: str = "lark-cli",
                 default_chat_id: str | None = None):
        self.default_channel = default_channel
        self.lark_cli = lark_cli
        self.default_chat_id = default_chat_id

    # ---- 4 类消息 ----

    async def send_acknowledgement(self, ticket_id: str, channel: str | None = None) -> None:
        """收到 Trigger 立即通知 —— ack 确认语。"""
        await self._publish(ticket_id, "outbox_acknowledgement", {
            "type": "acknowledgement",
            "message": "已收到任务，正在处理",
        }, channel)

    async def send_attention(self, ticket_id: str, message: str,
                             channel: str | None = None) -> None:
        """Worker 遇到问题 → 通知人（attention）。"""
        await self._publish(ticket_id, "outbox_attention", {
            "type": "attention",
            "message": message,
        }, channel)

    async def send_result(self, ticket_id: str, message: str,
                          channel: str | None = None) -> None:
        """任务结果投递（result）。"""
        await self._publish(ticket_id, "outbox_result", {
            "type": "result",
            "message": message,
        }, channel)

    async def send_reply(self, ticket_id: str, message: str,
                         channel: str | None = None) -> None:
        """Worker 回复投递（reply）。"""
        await self._publish(ticket_id, "outbox_reply", {
            "type": "reply",
            "message": message,
        }, channel)

    async def send_relay(self, ticket_id: str, message: str,
                         channel: str | None = None,
                         chat_id: str | None = None) -> None:
        """跨 Source 消息转发（relay）—— EffectQueue._handle_relay 经由这里
        把 A Source 的消息转发到 B 通道（如 Feishu 群）。"""
        await self._publish(ticket_id, "outbox_relay", {
            "type": "relay",
            "message": message,
        }, channel, chat_id=chat_id)

    # ---- 内部 ----

    async def _publish(self, ticket_id: str, event: str, data: dict,
                       channel: str | None, chat_id: str | None = None) -> None:
        channel = channel or self.default_channel
        payload = {"ticket_id": ticket_id, **data}
        try:
            from .sse_bus import sse_publish
            await sse_publish(event, payload)
        except Exception as e:
            logger.warning(f"OutboxService · SSE publish failed · event={event}: {e}")
        if channel == "feishu":
            await self._send_feishu(ticket_id, str(data.get("message", "")),
                                    event, chat_id=chat_id)

    async def _send_feishu(self, ticket_id: str, message: str, event: str,
                           chat_id: str | None = None) -> bool:
        """经 lark-cli 发送飞书群消息（POST /open-apis/im/v1/messages）。

        与 sources/feishu.py 的读取同一 bot 身份；目标群解析：
        显式 chat_id → default_chat_id → workspace feishu_source_cfg 首个 chat。
        失败只记录日志，不影响 SSE 主通道。
        """
        chat_id = chat_id or self._resolve_feishu_chat()
        if not chat_id:
            logger.warning(
                f"OutboxService · feishu channel skipped · no chat resolved · "
                f"ticket={ticket_id} · event={event}"
            )
            return False
        body = json.dumps({
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": message}, ensure_ascii=False),
        }, ensure_ascii=False)
        args = [
            self.lark_cli, "api", "POST", "/open-apis/im/v1/messages",
            "--params", json.dumps({"receive_id_type": "chat_id"}),
            "--body", body,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            if proc.returncode != 0:
                logger.warning(
                    f"OutboxService · feishu send failed · ticket={ticket_id} · "
                    f"event={event} · exit={proc.returncode} · "
                    f"err={err.decode(errors='replace')[:200]}"
                )
                return False
            logger.info(
                f"OutboxService · feishu sent · ticket={ticket_id} · "
                f"event={event} · chat={chat_id} · msg_len={len(message)}"
            )
            return True
        except Exception as e:  # noqa: BLE001 - 外发失败不应影响主管道
            logger.warning(
                f"OutboxService · feishu send error · ticket={ticket_id} · "
                f"event={event}: {e}"
            )
            return False

    def _resolve_feishu_chat(self) -> str | None:
        """目标群解析：显式 default_chat_id → workspace 配置首个 feishu chat。"""
        if self.default_chat_id:
            return self.default_chat_id
        try:
            from app.db.database import SessionLocal
            from app.models.ai.ai_workspace import AiWorkspace
            db = SessionLocal()
            try:
                ws = db.get(AiWorkspace, 1)
                cfg = (ws.config or {}) if ws else {}
            finally:
                db.close()
            chats = (cfg.get("feishu_source_cfg") or {}).get("chats") or []
            return chats[0].get("chat_id") if chats else None
        except Exception as e:  # noqa: BLE001 - DB 不可用时静默降级
            logger.warning(f"OutboxService · feishu chat resolve failed: {e}")
            return None
