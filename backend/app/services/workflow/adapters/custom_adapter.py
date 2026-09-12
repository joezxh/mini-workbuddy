"""通用 HTTP 适配器"""
import time
from typing import Any, Dict
import httpx
from loguru import logger

from app.services.workflow.platform_adapter import PlatformAdapter, PlatformResponse


class CustomHTTPAdapter(PlatformAdapter):
    """通用 HTTP 适配器 — 用于其他 LLM 编排平台"""

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        method = self.config.get("method", "POST").upper()
        extra_headers = self.config.get("headers", {})
        url = self.config.get("url") or f"{self.base_url}/{flow_type.lower()}"
        headers = {**extra_headers, "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"}
        body = {"inputs": inputs, "user": user_id, "flow_type": flow_type}

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, json=body, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            latency = int((time.monotonic() - t0) * 1000)
            return PlatformResponse(success=True, output=data, latency_ms=latency)
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(f"CustomHTTPAdapter.invoke 失败: {e}")
            return PlatformResponse(success=False, error=str(e), latency_ms=latency)

    def extract_output(self, result, flow_type):
        output_path = self.config.get("output_path", "$.output")
        # 简单实现：仅支持 $.key 一级路径
        if output_path.startswith("$."):
            key = output_path[2:]
            return str(result.get(key, ""))
        return str(result)
