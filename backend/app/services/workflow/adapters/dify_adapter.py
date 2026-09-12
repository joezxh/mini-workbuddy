"""Dify 平台适配器"""
import time
from typing import Any, Dict
import httpx
from loguru import logger

from app.services.workflow.platform_adapter import PlatformAdapter, PlatformResponse


class DifyAdapter(PlatformAdapter):
    """Dify 平台适配器 — 封装 5 种 API 端点"""

    ENDPOINT_MAP = {
        "Workflow": "/v1/workflows/run",
        "Chatflow": "/v1/chat-messages",
        "Chatbot": "/v1/chat-messages",
        "Agent": "/v1/agent/chat",
        "Completion": "/v1/completions",
    }

    def _build_payload(self, flow_type: str, inputs: Dict[str, Any], user_id: str) -> dict:
        if flow_type == "Workflow":
            return {"inputs": inputs, "user": user_id}
        if flow_type in ("Chatflow", "Chatbot"):
            query = inputs.pop("query", inputs.pop("prompt", ""))
            return {"query": query, "inputs": inputs, "user": user_id, "response_mode": "blocking"}
        if flow_type == "Agent":
            query = inputs.pop("query", inputs.pop("prompt", ""))
            return {"query": query, "user": user_id, "response_mode": "blocking"}
        if flow_type == "Completion":
            prompt = inputs.pop("prompt", "")
            return {"prompt": prompt, "user": user_id, **inputs}
        return {"inputs": inputs, "user": user_id}

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
            return PlatformResponse(
                success=True, output=data, latency_ms=latency,
                platform_trace={"status_code": resp.status_code, "headers": dict(resp.headers)},
            )
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            logger.error(f"DifyAdapter.invoke 失败: {e}")
            return PlatformResponse(success=False, error=str(e), latency_ms=latency)

    def extract_output(self, result, flow_type):
        if flow_type == "Workflow":
            outputs = result.get("data", {}).get("outputs", {})
            if isinstance(outputs, dict):
                for key in ("result", "output", "answer", "text", "response"):
                    if key in outputs and outputs[key]:
                        return str(outputs[key])
            return str(outputs) if outputs else ""
        return result.get("answer", "") or result.get("content", "") or ""
