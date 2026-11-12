"""voice-demo /asr/correct 端点测试（service 层 monkeypatch，不触真实 DB/LLM）
+ 服务层关思考/容量退避测试（fake build_model，不触真实引擎）。"""
import asyncio

import pytest

from tests.voice_demo.test_health import make_client  # 复用（带 auth override）
from app.services.voice_demo import asr_correct


@pytest.fixture()
def patched(monkeypatch):
    async def fake_correct(text: str, db) -> str:
        return f"corrected:{text}"

    monkeypatch.setattr(asr_correct, "correct", fake_correct)


def test_correct_shape(patched):
    r = make_client().post("/api/v1/voice-demo/asr/correct", json={"text": "今天天汽很好"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "corrected:今天天汽很好"
    assert isinstance(body["cost_ms"], int)


def test_correct_empty_text_422(patched):
    r = make_client().post("/api/v1/voice-demo/asr/correct", json={"text": "  "})
    assert r.status_code == 422


def test_correct_no_default_model_503(monkeypatch):
    async def boom(text: str, db) -> str:
        raise asr_correct.NoDefaultModel("无默认模型")

    monkeypatch.setattr(asr_correct, "correct", boom)
    r = make_client().post("/api/v1/voice-demo/asr/correct", json={"text": "x"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "NO_DEFAULT_MODEL"


def test_correct_failed_502(monkeypatch):
    async def boom(text: str, db) -> str:
        raise asr_correct.CorrectFailed("上游超时")

    monkeypatch.setattr(asr_correct, "correct", boom)
    r = make_client().post("/api/v1/voice-demo/asr/correct", json={"text": "x"})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "CORRECT_FAILED"


# ── 服务层：关思考双方言 + 输出预算封顶 + 容量撞窗减半重试 ──────────────
FAKE_CFG = {
    "provider": "openai", "model": "qwen3.5-0.8b",
    "base_url": "http://127.0.0.1:1234/compatible-mode/v1", "api_key": "lm-studio",
    "max_tokens": 8192,  # 模型行声明超大 → 必须被封顶到 MAX_OUTPUT_TOKENS
}


def _patch_service(monkeypatch, model_factory):
    monkeypatch.setattr(
        "app.services.kb.kg.kg_llm_extractor.resolve_llm_config", lambda db: dict(FAKE_CFG)
    )

    async def _noop_close(_m):
        return None

    monkeypatch.setattr("app.ai.research.llm._aclose_model", _noop_close)
    monkeypatch.setattr("app.ai.strategy.factory_ext.build_model", model_factory)


def test_correct_sends_thinking_off_and_capped_budget(monkeypatch):
    captured: list[dict] = []

    def fake_build_model(cfg):
        captured.append(cfg)

        async def call(_msgs):
            return "纠正后正文"

        return call

    _patch_service(monkeypatch, fake_build_model)
    out = asyncio.run(asr_correct.correct("今天天汽很好", None))
    assert out == "纠正后正文"
    assert len(captured) == 1
    cfg = captured[0]
    assert cfg["stream"] is False
    # 输出预算封顶：模型行 8192 → 压到 MAX_OUTPUT_TOKENS
    assert cfg["max_tokens"] == asr_correct.MAX_OUTPUT_TOKENS
    # 关思考双方言一起发（本机 llama.cpp 只认 reasoning_effort=none）
    eb = cfg["extra_body"]
    assert eb["reasoning_effort"] == "none"
    assert eb["chat_template_kwargs"]["enable_thinking"] is False


def test_correct_context_exceeded_halves_budget_and_retries(monkeypatch):
    captured: list[dict] = []
    state = {"n": 0}

    def fake_build_model(cfg):
        captured.append(cfg)

        async def call(_msgs):
            state["n"] += 1
            if state["n"] <= 2:
                raise RuntimeError("Context size has been exceeded.")
            return "终于纠正成功"

        return call

    _patch_service(monkeypatch, fake_build_model)
    out = asyncio.run(asr_correct.correct("长文本", None))
    assert out == "终于纠正成功"
    # 预算逐次减半：2048 → 1024 → 512（下限 256 未触发）
    assert [c["max_tokens"] for c in captured] == [2048, 1024, 512]


def test_correct_input_truncated_to_max_chars(monkeypatch):
    captured_msgs: list = []

    def fake_build_model(_cfg):
        async def call(msgs):
            captured_msgs.append(msgs)
            return "ok"

        return call

    _patch_service(monkeypatch, fake_build_model)
    asyncio.run(asr_correct.correct("字" * (asr_correct.MAX_TEXT_CHARS + 5000), None))
    user_msg = captured_msgs[0][-1]
    sent_text = user_msg.content[0]["text"] if isinstance(user_msg.content[0], dict) else user_msg.content[0].text
    assert len(sent_text) == asr_correct.MAX_TEXT_CHARS
