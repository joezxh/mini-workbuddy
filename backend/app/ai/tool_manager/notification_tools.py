"""通知发送工具 - 邮件(SMTP) + 钉钉 Webhook。

基于 AgentScope 2.0.4 ToolBase 协议实现。
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, List, Optional

from agentscope.tool import ToolBase, ToolChunk
from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)

logger = logging.getLogger(__name__)


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class NotificationSender(ToolBase):
    """通知发送 - 邮件 + 钉钉。"""

    name: str = "notification_sender"
    description: str = "发送邮件（SMTP）或钉钉 Webhook 通知消息"
    input_schema: dict = {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "enum": ["email", "dingtalk"],
                "description": "通知渠道：email-邮件 / dingtalk-钉钉",
            },
            "to": {
                "type": "string",
                "description": "收件人邮箱地址（email 渠道，多个用逗号分隔）",
            },
            "subject": {
                "type": "string",
                "description": "邮件主题（email 渠道）",
            },
            "body": {
                "type": "string",
                "description": "消息正文",
            },
            "body_type": {
                "type": "string",
                "enum": ["text", "html", "markdown"],
                "description": "正文格式",
                "default": "text",
            },
            "webhook_url": {
                "type": "string",
                "description": "钉钉 Webhook URL（dingtalk 渠道）",
            },
            "at_mobiles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "@指定手机号列表（dingtalk 渠道）",
            },
            "is_at_all": {
                "type": "boolean",
                "description": "是否@所有人（dingtalk 渠道）",
                "default": False,
            },
        },
        "required": ["channel", "body"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = False

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            message="Sending notifications to external recipients.",
        )

    async def call(
        self,
        channel: str,
        body: str,
        to: Optional[str] = None,
        subject: Optional[str] = None,
        body_type: str = "text",
        webhook_url: Optional[str] = None,
        at_mobiles: Optional[List[str]] = None,
        is_at_all: bool = False,
    ) -> ToolChunk:
        if channel == "email":
            return await self._send_email(to, subject, body, body_type)
        elif channel == "dingtalk":
            return await self._send_dingtalk(webhook_url, body, body_type, at_mobiles, is_at_all)
        else:
            return _text_chunk({"error": f"不支持的渠道: {channel}，支持 email/dingtalk"})

    async def _send_email(
        self,
        to: Optional[str],
        subject: Optional[str],
        body: str,
        body_type: str,
    ) -> ToolChunk:
        """发送邮件（SMTP）。"""
        if not to:
            return _text_chunk({"error": "email 渠道需要提供 to（收件人）"})

        # 从环境变量获取 SMTP 配置
        smtp_host = os.getenv("SMTP_HOST", "smtp.163.com")
        smtp_port = int(os.getenv("SMTP_PORT", "465"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        smtp_from = os.getenv("SMTP_FROM", smtp_user)

        if not smtp_user or not smtp_password:
            return _text_chunk({
                "error": "SMTP 未配置，请设置环境变量: SMTP_USER, SMTP_PASSWORD",
                "config_needed": ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"],
            })

        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = to
            msg["Subject"] = subject or "(无主题)"

            if body_type == "html":
                msg.attach(MIMEText(body, "html", "utf-8"))
            else:
                msg.attach(MIMEText(body, "plain", "utf-8"))

            # 发送
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.starttls()

            server.login(smtp_user, smtp_password)
            recipients = [addr.strip() for addr in to.split(",")]
            server.sendmail(smtp_from, recipients, msg.as_string())
            server.quit()

            return _text_chunk({
                "channel": "email",
                "status": "sent",
                "to": to,
                "subject": subject,
            })

        except Exception as exc:
            logger.warning("email send failed: %s", exc)
            return _text_chunk({"channel": "email", "status": "failed", "error": str(exc)})

    async def _send_dingtalk(
        self,
        webhook_url: Optional[str],
        body: str,
        body_type: str,
        at_mobiles: Optional[List[str]],
        is_at_all: bool,
    ) -> ToolChunk:
        """发送钉钉 Webhook 消息。"""
        if not webhook_url:
            return _text_chunk({"error": "dingtalk 渠道需要提供 webhook_url"})

        try:
            import httpx
        except ImportError:
            return _text_chunk({"error": "httpx 未安装"})

        # 构建消息体
        if body_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "通知",
                    "text": body,
                },
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": is_at_all,
                },
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": body,
                },
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": is_at_all,
                },
            }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(webhook_url, json=payload)
                result = resp.json()
                if result.get("errcode") == 0:
                    return _text_chunk({
                        "channel": "dingtalk",
                        "status": "sent",
                    })
                else:
                    return _text_chunk({
                        "channel": "dingtalk",
                        "status": "failed",
                        "error": result.get("errmsg", "未知错误"),
                    })
        except Exception as exc:
            logger.warning("dingtalk send failed: %s", exc)
            return _text_chunk({"channel": "dingtalk", "status": "failed", "error": str(exc)})
