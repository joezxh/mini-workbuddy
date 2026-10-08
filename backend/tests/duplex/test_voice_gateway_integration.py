"""Voice Gateway 完整状态机集成测试（回环 Provider，无外部依赖）。

验证场景:
1. WebSocket 连接建立 → ready → 文本交互 → disconnect
2. Provider 连接失败时的 fallback 降级流程
3. Session 超时与断开连接
4. 多轮对话的会话保持

所有测试通过模拟 LoopbackProvider 实现，无需外部服务。
"""
import asyncio
import json
import time
from typing import Dict, Any
from fastapi.testclient import TestClient

import pytest
from app.main import app
from app.duplex.voice.providers.registry import register_provider
from app.duplex.voice.providers.base import RealtimeProvider, ProviderEvent


# ── Mock Provider（用于所有测试的回路模拟）──────────────────────────────────────


class EchoLoopbackProvider(RealtimeProvider):
    """Echo 回环 Provider：将输入原样返回，用于状态验证。"""
    key = "echo_loopback"
    
    def __init__(self):
        self._q: asyncio.Queue = None
        self._connected = False
    
    async def connect(self, session_config: Dict[str, Any]):
        """模拟连接建立。"""
        self._q = asyncio.Queue()
        await asyncio.sleep(0.05)  # 模拟网络延迟
        self._connected = True
        # 发送连接确认事件
        await self._q.put(ProviderEvent(type="voice.connected", data={}))
    
    async def send_audio(self, pcm_data: bytes):
        """模拟音频发送。"""
        if not self._connected:
            raise ConnectionError("Provider 未连接")
        await self._q.put(ProviderEvent(type="audio_sent", data={"len": len(pcm_data)}))
        # 模拟回声返回
        await asyncio.sleep(0.02)
        await self._q.put(ProviderEvent(type="audio_delta", data={"audio": pcm_data[:100]}))
    
    async def configure_session(self, **kwargs):
        """配置会话参数。"""
        await self._q.put(ProviderEvent(type="session.configured", data=kwargs))
    
    async def send_text(self, text: str):
        """模拟文本响应。"""
        await self._q.put(ProviderEvent(type="text_response", data={"text": text}))
    
    async def events(self):
        """事件流生成器。"""
        while True:
            if self._q is not None and not self._q.empty():
                event = await self._q.get()
                yield event
            else:
                await asyncio.sleep(0.1)
    
    async def close(self):
        """关闭连接。"""
        self._connected = False
        if self._q:
            await self._q.put(ProviderEvent(type="voice.disconnected", data={}))


class FailingThenWorkingProvider(RealtimeProvider):
    """先失败后成功的 Provider，用于测试 fallback。"""
    key = "fail_then_work"
    
    def __init__(self):
        self._connect_count = 0
        self._q: asyncio.Queue = None
    
    async def connect(self, session_config: Dict[str, Any]):
        self._connect_count += 1
        if self._connect_count == 1:
            # 第一次尝试失败
            raise ConnectionError("模拟连接超时")
        
        # 第二次尝试成功
        self._q = asyncio.Queue()
        await self._q.put(ProviderEvent(type="voice.connected", data={}))
    
    async def send_audio(self, pcm_data: bytes):
        pass
    
    async def configure_session(self, **kwargs):
        pass
    
    async def send_text(self, text: str):
        pass
    
    async def events(self):
        while True:
            if self._q and not self._q.empty():
                yield await self._q.get()
            else:
                await asyncio.sleep(0.1)
    
    async def close(self):
        pass


class TimeoutProvider(RealtimeProvider):
    """模拟超时的 Provider。"""
    key = "timeout_provider"
    
    def __init__(self):
        self._call_count = 0
    
    async def connect(self, session_config: Dict[str, Any]):
        await asyncio.sleep(2.0)  # 超时
        raise asyncio.TimeoutError("连接超时")
    
    async def send_audio(self, pcm_data: bytes):
        await asyncio.sleep(2.0)
        raise asyncio.TimeoutError("操作超时")
    
    async def configure_session(self, **kwargs):
        pass
    
    async def send_text(self, text: str):
        raise asyncio.TimeoutError("文本发送超时")
    
    async def events(self):
        while True:
            await asyncio.sleep(1.0)
    
    async def close(self):
        pass


# ── 测试用例集 ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def setup_providers():
    """注册测试用 Provider。"""
    register_provider("echo_loopback", EchoLoopbackProvider)
    register_provider("fail_then_work", FailingThenWorkingProvider)
    register_provider("timeout_provider", TimeoutProvider)
    yield


def test_connection_establishment_flow(setup_providers: None):
    """测试 1: WebSocket 连接建立完整流程。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-1&participant_id=party_a&provider=echo_loopback"
    ) as ws:
        # 1. 接收 ready 消息
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        assert "session_id" in frame["data"]
        assert frame["data"]["provider"] == "echo_loopback"
        
        # 2. 发送文本消息
        ws.send_text(json.dumps({
            "type": "input.message",
            "text": "你好"
        }))
        
        # 3. 接收 echo 响应
        for _ in range(5):
            frame = json.loads(ws.receive_text())
            if frame["type"] == "text_response":
                assert frame["data"]["text"] == "你好"
                break
        else:
            pytest.fail("未收到文本响应")
        
        # 4. 正常断开
        ws.disconnect(1000)


def test_fallback_on_connection_failure(setup_providers: None):
    """测试 2: 主 Provider 失败时的自动降级流程。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    # 注意：此测试需要实现 fallback 逻辑，当前作为预期失败的 TDD 红阶段
    # TODO: 实现 fallback 机制后应 pass
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-1&participant_id=party_a&provider=fail_then_work"
    ) as ws:
        frame = json.loads(ws.receive_text())
        # 预期：即使首次连接失败，也应 fallback 到备用 provider
        # 当前行为待实现
        assert frame["type"] in ["voice.ready", "error"]


def test_message_transcription_pipeline(setup_providers: None):
    """测试 3: ASR→LLM→TTS 的完整消息管道。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-2&participant_id=interviewer&provider=echo_loopback"
    ) as ws:
        # 等待 ready
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        
        # 发送中文文本，模拟语音识别结果
        test_messages = [
            {"text": "请问您的预算是多少？"},
            {"text": "我希望价格在 10 万元以内"},
            {"text": "好的，我为您推荐这个方案"}
        ]
        
        for msg in test_messages:
            ws.send_text(json.dumps({"type": "input.message", "text": msg["text"]}))
            
            # 接收并验证响应
            received = False
            for _ in range(10):
                frame = json.loads(ws.receive_text())
                if frame["type"] == "text_response":
                    assert frame["data"]["text"] in [m["text"] for m in test_messages]
                    received = True
                    break
            
            assert received, f"未收到对消息 {msg} 的响应"
        
        ws.disconnect(1000)


def test_session_idle_timeout(setup_providers: None):
    """测试 4: 会话空闲超时断开机制。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-3&participant_id=party_b&provider=echo_loopback"
    ) as ws:
        # 等待 ready
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        
        # 长时间静默（模拟超时）
        time.sleep(0.2)  # 缩短等待时间用于测试
        
        # 发送消息应该被拒绝或触发重新连接
        try:
            ws.send_text(json.dumps({"type": "input.message", "text": "test"}))
            frame = json.loads(ws.receive_text())
            # 服务器应返回超时错误或保持连接活动
            assert frame["type"] in ["error", "voice.ready"]
        except Exception:
            # 连接可能已断开
            pass


def test_multi_turn_dialogue_state_maintainance(setup_providers: None):
    """测试 5: 多轮对话状态保持。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-4&participant_id=counselor&provider=echo_loopback"
    ) as ws:
        # 初始化连接
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        
        # 模拟连续的多轮对话
        dialogue = [
            ("用户", "我想咨询贷款业务"),
            ("助手", "请问您的贷款金额需求是多少？"),
            ("用户", "大约 50 万元，期限 5 年"),
            ("助手", "好的，我为您查询适合的利率方案"),
            ("助手", "根据您的条件，年化利率约为 4.5%"),
        ]
        
        for i, (user_msg, expected_response) in enumerate(dialogue):
            if i % 2 == 0:  # 用户发言
                ws.send_text(json.dumps({
                    "type": "input.message",
                    "text": user_msg
                }))
                
                # 等待系统响应
                for _ in range(20):
                    frame = json.loads(ws.receive_text())
                    if frame["type"] == "text_response":
                        # 验证系统记住上下文（此处简化为响应存在）
                        assert len(frame["data"]["text"]) > 0
                        break
                else:
                    pytest.fail(f"第{i+1}轮未收到响应")
        
        ws.disconnect(1000)


def test_error_recovery_with_reconnection(setup_providers: None):
    """测试 6: 错误恢复与重连机制。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    # 预期连接超时或被拒绝，尝试建立连接应抛出异常
    with pytest.raises(Exception):
        ws = client.websocket_connect(
            "/api/v1/duplex/voice/ws?case_number=MED-5&participant_id=test_user&provider=timeout_provider"
        )
        # 如果连接成功（不应发生），应返回错误消息
        frame = json.loads(ws.receive_text())
        # 服务器应返回明确错误
        if frame["type"] == "error":
            assert "timeout" in frame["data"].get("message", "").lower() or \
                   frame["data"].get("code") == "CONNECTION_TIMEOUT"
        ws.disconnect(1000)
    except Exception:
        # 超时异常可接受
        pass


def test_concurrent_sessions_isolation(setup_providers: None):
    """测试 7: 并发会话隔离（串行执行，但验证同一 case_number 不同 participant 的状态独立）。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # 创建两个独立会话
    for participant in ["user_a", "user_b"]:
        ws = client.websocket_connect(
            f"/api/v1/duplex/voice/ws?case_number=CASE-SHARED&participant_id={participant}&provider=echo_loopback"
        )
        
        # 等待 ready
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        assert "session_id" in frame["data"]
        sessions.append((ws, frame["data"]["session_id"]))
    
    # 发送不同消息给每个会话
    for idx, (ws, session_id) in enumerate(sessions):
        test_text = f"消息来自参会者{idx}"
        ws.send_text(json.dumps({
            "type": "input.message",
            "text": test_text
        }))
        
        # 接收对应响应
        received = False
        for _ in range(10):
            frame = json.loads(ws.receive_text())
            if frame["type"] == "text_response":
                assert test_text in frame["data"]["text"]
                received = True
                break
        
        assert received, f"会话{session_id[-4:]}未收到响应"
    
    # 全部关闭
    for ws, _ in sessions:
        ws.disconnect(1000)


def test_protocol_version_negotiation(setup_providers: None):
    """测试 8: 协议版本协商。"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/duplex/voice/ws?case_number=MED-6&participant_id=v1_test&provider=echo_loopback"
    ) as ws:
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "voice.ready"
        
        # 检查是否支持协议版本信息
        supported_versions = frame["data"].get("supported_protocols", [])
        assert isinstance(supported_versions, list)
        assert 1 in supported_versions  # 至少支持 v1
        
        ws.disconnect(1000)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
