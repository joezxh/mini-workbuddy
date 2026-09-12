"""Coze 平台适配器"""
import time
from typing import Any, Dict
import httpx
from loguru import logger

from app.services.workflow.platform_adapter import PlatformAdapter, PlatformResponse


class CozeAdapter(PlatformAdapter):
    """Coze 平台适配器"""

    ENDPOINT_MAP = {
        "Workflow": "/api/v1/workflow/run",
        "Chatflow": "/api/v1/conversation/chat",
        "Chatbot": "/api/v1/conversation/chat",
        "Agent": "/api/v1/conversation/chat",
        "Completion": "/api/v1/completion",
    }

    def _build_payload(self, flow_type: str, inputs: Dict[str, Any], user_id: str) -> dict:
        if flow_type == "Workflow":
            return {"workflow_id": inputs.pop("workflow_id", ""), "parameters": inputs, "app_id": user_id}
        query = inputs.pop("query", inputs.pop("prompt", ""))
        return {"query": query, "parameters": inputs, "user_id": user_id}

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        endpoint = self.ENDPOINT_MAP.get(flow_type)
        if not endpoint:
            return PlatformResponse(success=False, error=f"不支持的 flow_type: {flow_type}")

        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(flow_type, dict(inputs), user_id)

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            latency = int((time.monotonic() - t0) * 1000)
            return PlatformResponse(success=True, output=data, latency_ms=latency,
                                    platform_trace={"status_code": resp.status_code})
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(f"CozeAdapter.invoke 失败: {e}")
            return PlatformResponse(success=False, error=str(e), latency_ms=latency)

    def extract_output(self, result, flow_type):
        data = result.get("data", {})
        if flow_type == "Workflow":
            return str(data.get("output", ""))
        messages = result.get("messages", [])
        if messages:
            return messages[-1].get("content", "")
        return data.get("output", "") or result.get("answer", "")
