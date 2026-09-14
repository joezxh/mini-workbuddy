"""VoiceFallback 语音降级策略单测。"""
import asyncio
from unittest.mock import MagicMock

from app.duplex.voice.fallback import VoiceFallback


def test_fallback_to_second_provider():
    """主 Provider 连接失败 → 自动降级到备用 Provider。"""
    async def run():
        calls = []

        async def act(p):
            calls.append(p)
            if p == "dashscope":
                raise ConnectionError()
            return f"ok:{p}"

        fb = VoiceFallback(["dashscope", "local"])
        return await fb.with_fallback("dashscope", act), calls

    res, calls = asyncio.run(run())
    assert res == "ok:local" and "local" in calls


def test_fallback_to_text_mode_when_no_backup():
    """无可用备用 → 降级为文字模式。"""
    async def run():
        async def act(p):
            raise ConnectionError()

        fb = VoiceFallback(["dashscope"])
        return await fb.with_fallback("dashscope", act)

    res = asyncio.run(run())
    assert res["type"] == "text_only"


def test_fallback_non_provider_error_goes_text():
    """非 Provider 错误（超时/致命）→ 直接文字模式，不走备用链。"""
    async def run():
        calls = []

        async def act(p):
            calls.append(p)
            raise TimeoutError()

        fb = VoiceFallback(["dashscope", "local"])
        return await fb.with_fallback("dashscope", act), calls

    res, calls = asyncio.run(run())
    assert res["type"] == "text_only"
    assert calls == ["dashscope"]  # 未尝试备用


def test_fallback_raises_when_text_mode_disabled():
    """关闭文字降级 → 原样抛出。"""
    async def run():
        async def act(p):
            raise ConnectionError()

        fb = VoiceFallback(["dashscope"], max_text_mode=False)
        return await fb.with_fallback("dashscope", act)

    try:
        asyncio.run(run())
    except ConnectionError:
        return
    raise AssertionError("expected ConnectionError to be raised")


def test_provider_error_tries_backup():
    """Provider 连接错误 → 尝试备用 Provider。"""
    request = MagicMock()
    request.context = {"provider": "dashscope", "input_mode": "voice"}

    error = Exception("provider connection failed")
    result = VoiceFallback.try_fallback(
        request, error, available_providers=["dashscope", "openai"],
    )

    assert result.context["provider"] == "openai"
    assert result.context["input_mode"] == "voice"


def test_no_backup_falls_to_text():
    """无备用 Provider → 降级为文字模式。"""
    request = MagicMock()
    request.context = {"provider": "dashscope", "input_mode": "voice"}

    error = Exception("provider connection failed")
    result = VoiceFallback.try_fallback(
        request, error, available_providers=["dashscope"],
    )

    assert result.context["input_mode"] == "text"
    assert result.context["fallback_reason"] == "provider connection failed"


def test_connection_error_during_call():
    """通话中连接断开 → 尝试备用 Provider。"""
    request = MagicMock()
    request.context = {"provider": "dashscope", "input_mode": "voice"}

    error = Exception("connection lost")
    result = VoiceFallback.try_fallback(
        request, error, available_providers=["dashscope", "openai"],
    )

    assert result.context["provider"] == "openai"


def test_non_provider_error_falls_to_text():
    """非 Provider 错误（如麦克风不可用）→ 直接降级文字。"""
    request = MagicMock()
    request.context = {"provider": "dashscope", "input_mode": "voice"}

    error = Exception("microphone permission denied")
    result = VoiceFallback.try_fallback(
        request, error, available_providers=["dashscope"],
    )

    assert result.context["input_mode"] == "text"
