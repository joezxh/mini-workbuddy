"""平台适配器单元测试"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.workflow.platform_adapter import PlatformResponse
from app.services.workflow.adapters.dify_adapter import DifyAdapter
from app.services.workflow.adapters.coze_adapter import CozeAdapter
from app.services.workflow.adapters.custom_adapter import CustomHTTPAdapter
from app.services.workflow.adapter_factory import AdapterFactory


# ── DifyAdapter ──────────────────────────────────────────────

class TestDifyAdapter:
    def test_build_payload_workflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Workflow", {"key": "val"}, "user1")
        assert payload == {"inputs": {"key": "val"}, "user": "user1"}

    def test_build_payload_chatflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Chatflow", {"query": "hello", "extra": "data"}, "user1")
        assert payload["query"] == "hello"
        assert payload["response_mode"] == "blocking"

    def test_build_payload_agent(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Agent", {"prompt": "analyze"}, "user1")
        assert payload["query"] == "analyze"

    def test_build_payload_completion(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        payload = adapter._build_payload("Completion", {"prompt": "write"}, "user1")
        assert payload["prompt"] == "write"
        assert payload["user"] == "user1"

    def test_extract_output_workflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        result = {"data": {"outputs": {"result": "hello world"}}}
        assert adapter.extract_output(result, "Workflow") == "hello world"

    def test_extract_output_chatflow(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        result = {"answer": "response text"}
        assert adapter.extract_output(result, "Chatflow") == "response text"

    def test_extract_output_agent(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        result = {"answer": "agent response"}
        assert adapter.extract_output(result, "Agent") == "agent response"

    def test_unsupported_flow_type(self):
        adapter = DifyAdapter("https://dify.test", "sk-test")
        # 测试不存在类型
        import asyncio
        resp = asyncio.run(adapter.invoke("UnknownType", {}, "user1"))
        assert resp.success is False


# ── AdapterFactory ───────────────────────────────────────────

class TestAdapterFactory:
    def test_create_dify(self):
        adapter = AdapterFactory.create("dify", "https://dify.test", "sk-test")
        assert isinstance(adapter, DifyAdapter)

    def test_create_coze(self):
        adapter = AdapterFactory.create("coze", "https://coze.test", "sk-test")
        assert isinstance(adapter, CozeAdapter)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="不支持的平台类型"):
            AdapterFactory.create("unknown_platform", "https://x.test", "sk")

    def test_list_platforms(self):
        platforms = AdapterFactory.list_platforms()
        assert "dify" in platforms
        assert "coze" in platforms
        assert "custom_http" in platforms
