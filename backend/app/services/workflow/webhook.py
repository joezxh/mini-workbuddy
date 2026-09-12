"""异步 Webhook 回调"""
import hashlib
import hmac
import json
import time
from typing import Optional

import httpx
from loguru import logger


class WebhookDispatcher:
    """Webhook 回调分发器"""

    async def dispatch(self, event_type: str, flow_config: dict,
                       execution_data: dict):
        """发送 Webhook 回调

        Args:
            event_type: on_success / on_failure / on_timeout
            flow_config: workflow_flow.config JSONB
            execution_data: 执行结果数据
        """
        webhook_url = flow_config.get("webhook_url") if flow_config else None
        if not webhook_url:
            return

        webhook_secret = flow_config.get("webhook_secret", "")
        payload = {
            "event": event_type,
            "timestamp": int(time.time()),
            "data": execution_data,
        }
        body = json.dumps(payload, ensure_ascii=False)
        signature = hmac.new(
            webhook_secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest() if webhook_secret else ""

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, content=body, headers=headers, timeout=10.0)
        except Exception as e:
            logger.warning(f"Webhook 回调失败: {webhook_url} -> {e}")
