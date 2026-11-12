"""LLM 抽取通道回归测试。

覆盖本轮修复的三件事：
* ``extractor_type=llm`` + ``model_spec`` 真正解析到模型管理的对话模型；
* LLM 响应 → 实体/关系走与规则通道**同一套规整层**（含 ``relation_type``）；
* 模型不可用时**显式**给出降级原因（静默退回规则通道 = 前端「成功但 0 实体」）。

不发真实网络请求：模型补全一律用 ``complete=`` 注入。
"""
import json

import pytest

from app.models.ai.ai_api_key import AiApiKey, AiChatModel
from app.services.kb.kg import kg_extractor, kg_failure, kg_llm_extractor

TENANT_A = 100


# ── fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def kb(db):
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    obj = WikiKnowledge(name="图谱库", slug="kg-llm-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def ai_db(engine, db):
    """补建模型管理两张表（conftest 的白名单只含 kb/kg 表）。"""
    from app.db.database import Base

    Base.metadata.create_all(
        engine, tables=[AiApiKey.__table__, AiChatModel.__table__]
    )
    return db


def add_key(db, *, url="http://192.168.40.30", platform="gpustack", status=1):
    key = AiApiKey(name="本地网关", api_key="sk-test", platform=platform,
                   url=url, status=status, tenant_id=TENANT_A)
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def add_model(db, key, *, code="m-1", platform=None, type=1, status=1,
              is_default=False, sort=0, model="qwen"):
    row = AiChatModel(
        code=code, key_id=key.id, name="测试对话模型", model=model,
        platform=platform or "gpustack", status=status, type=type,
        is_default=is_default, sort=sort, tenant_id=TENANT_A,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── 响应解析 ─────────────────────────────────────────────────────────────
def test_parse_response_plain_json():
    raw = json.dumps({
        "entities": [{"name": "星海科技", "label": "客户"}],
        "relations": [{"source": "星海科技", "target": "订单B1",
                       "relation_type": "下达"}],
    }, ensure_ascii=False)
    ents, rels = kg_llm_extractor.parse_response(raw)
    assert ents[0]["name"] == "星海科技"
    assert rels[0]["relation_type"] == "下达"


def test_parse_response_strips_fence_and_prose():
    """模型爱加 ```json 围栏、爱在 JSON 前后写解释——都要能吃下。"""
    raw = "好的，抽取结果如下：\n```json\n{\"entities\": [], \"relations\": []}\n```\n"
    ents, rels = kg_llm_extractor.parse_response(raw)
    assert ents == [] and rels == []


def test_parse_response_converts_dict_endpoints_to_text():
    raw = json.dumps({
        "entities": [{"name": "A"}, {"name": "B"}],
        "relations": [{"source": {"name": "A"}, "target": "B",
                       "relation_type": "属于"}],
    })
    _, rels = kg_llm_extractor.parse_response(raw)
    assert rels[0]["source"] == "A", "端点必须收敛成字符串，与规则通道判定一致"


@pytest.mark.parametrize("bad", ["", "抱歉，我无法抽取", "entities = [A]"])
def test_parse_response_raises_instead_of_returning_empty(bad):
    """解析失败必须抛错：返回空列表在前端与「文本确实没实体」不可区分。"""
    with pytest.raises(ValueError):
        kg_llm_extractor.parse_response(bad)


@pytest.mark.parametrize(
    "bad,code",
    [
        ("", kg_failure.MODEL_NO_TEXT),
        ("抱歉，我无法抽取", kg_failure.JSON_INVALID),
        ('{"entities": [{"name": "星海', kg_failure.JSON_INVALID),
        ('{"entities": []', kg_failure.JSON_TRUNCATED),
    ],
)
def test_parse_response_raises_typed_errors(bad, code):
    """失败在发生处就被归成稳定码：前端按码取文案，不靠识别报错句子。"""
    with pytest.raises(kg_failure.KgExtractionError) as ei:
        kg_llm_extractor.parse_response(bad)
    assert ei.value.code == code
    assert isinstance(ei.value, ValueError), "旧调用方的 except ValueError 照旧能接"


def test_extractor_call_keeps_code_when_annotating_model():
    """补上「是哪个模型」的包装不得丢掉码，否则按码取文案在这一层断掉。"""
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "qwen", "provider": "openai"}, complete=lambda p: ""
    )
    with pytest.raises(kg_failure.KgExtractionError) as ei:
        llm("正文")
    assert ei.value.code == kg_failure.MODEL_NO_TEXT
    assert "model=qwen" in str(ei.value), "报错仍要保留模型身份便于定位模型行"


def test_extract_llm_failure_attaches_error_code():
    """抽取器吞异常的地方就是定码的地方：上游只拿到字符串时已无法回溯。"""
    def boom(text, *, schema_hint=""):
        raise kg_failure.TruncatedResponseError("响应截断修复后无任何实体/关系")

    out = kg_extractor.extract("文本", llm=boom)
    assert out.codes == [kg_failure.JSON_TRUNCATED]
    assert out.as_details()["error_code"] == kg_failure.JSON_TRUNCATED
    assert out.errors and "LLM 抽取失败" in out.errors[0]


# ── prompt ───────────────────────────────────────────────────────────────
def test_build_prompt_injects_schema_hint_and_limits():
    p = kg_llm_extractor.build_prompt("正文", schema_hint="只抽客户与订单",
                                      max_entities=7, max_relations=9)
    assert "只抽客户与订单" in p
    assert "不超过 7 个" in p and "不超过 9 个" in p


def test_build_prompt_truncates_oversized_text():
    p = kg_llm_extractor.build_prompt("x" * (kg_llm_extractor.MAX_TEXT_CHARS + 999))
    assert len(p) < kg_llm_extractor.MAX_TEXT_CHARS + 2000


# ── 模型配置解析 ─────────────────────────────────────────────────────────
def test_resolve_llm_config_by_code(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="chat-a")
    cfg = kg_llm_extractor.resolve_llm_config(ai_db, "chat-a")
    assert cfg["model"] == "qwen"
    assert cfg["api_key"] == "sk-test"


def test_resolve_llm_config_by_model_id_dict(ai_db):
    key = add_key(ai_db)
    row = add_model(ai_db, key, code="chat-b")
    cfg = kg_llm_extractor.resolve_llm_config(ai_db, {"model_id": row.id})
    assert cfg["model_code"] == "chat-b"


def test_resolve_llm_config_prefers_default_chat_model(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="other", sort=99)
    add_model(ai_db, key, code="default-one", is_default=True, sort=0)
    cfg = kg_llm_extractor.resolve_llm_config(ai_db, None)
    assert cfg["model_code"] == "default-one", "未指定 model_spec 时取默认对话模型"


def test_resolve_llm_config_falls_back_to_sort_when_no_default(ai_db):
    """没标默认时按 sort 取最大者（与技能执行侧同一口径）。"""
    key = add_key(ai_db)
    add_model(ai_db, key, code="low", sort=1)
    add_model(ai_db, key, code="high", sort=9)
    assert kg_llm_extractor.resolve_llm_config(ai_db, None)["model_code"] == "high"


def test_resolve_llm_config_ignores_embedding_model(ai_db):
    """type=5 是向量化模型，不能被当成对话抽取模型用。"""
    key = add_key(ai_db)
    add_model(ai_db, key, code="vec", type=5, is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, None) is None


def test_resolve_llm_config_rejects_disabled_model_and_key(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="off", status=0, is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "off") is None

    key2 = add_key(ai_db, status=0)
    add_model(ai_db, key2, code="on", is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "on") is None, \
        "密钥被禁用不得仍被抽取链路使用"


def test_resolve_llm_config_unknown_code_returns_none(ai_db):
    add_key(ai_db)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "not-exist") is None


def test_resolve_llm_config_appends_v1_for_openai_compatible(ai_db):
    """gpustack 一类 OpenAI 兼容地址必须补 /v1，否则打到错误路径。"""
    key = add_key(ai_db, url="http://192.168.40.30")
    add_model(ai_db, key, code="m", is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "m")["base_url"] \
        == "http://192.168.40.30/v1"


def test_resolve_llm_config_keeps_dashscope_url(ai_db):
    key = add_key(ai_db, url="https://dashscope.aliyuncs.com/compatible-mode",
                  platform="通义千问")
    add_model(ai_db, key, code="q", platform="通义千问", is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "q")["base_url"] \
        == "https://dashscope.aliyuncs.com/compatible-mode"


def test_resolve_llm_config_no_table_is_graceful(db):
    """无模型管理表（本用例未建表）时不抛错，返回 None 让上层降级。"""
    assert kg_llm_extractor.resolve_llm_config(db, None) is None


# ── 抽取器构造 ───────────────────────────────────────────────────────────
def test_build_llm_extractor_rule_type_returns_note(db):
    llm, note = kg_llm_extractor.build_llm_extractor(
        db, {"extractor_type": "rule", "timeout_seconds": 30}
    )
    assert llm is None and "rule" in note


def test_build_llm_extractor_reports_why_model_unavailable(ai_db):
    """模型不可用时 note 必须说清原因——这是本轮「静默降级」的正面修复。"""
    llm, note = kg_llm_extractor.build_llm_extractor(
        ai_db, {"extractor_type": "llm", "timeout_seconds": 30}
    )
    assert llm is None
    assert "默认对话模型" in note


def test_build_llm_extractor_uses_model_spec(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="picked", is_default=True)
    llm, note = kg_llm_extractor.build_llm_extractor(
        ai_db, {"extractor_type": "llm", "model_spec": "picked",
                "timeout_seconds": 15}
    )
    assert llm is not None and llm.timeout_seconds == 15
    assert note == "qwen"
    assert "model=qwen" in llm.model_desc


# ── LLMExtractor（注入补全，不发网络请求）───────────────────────────────
def test_llm_extractor_end_to_end_with_injected_complete():
    seen = {}

    def fake_complete(prompt):
        seen["prompt"] = prompt
        return json.dumps({
            "entities": [{"name": "星海科技", "label": "客户"},
                         {"name": "订单B1", "label": "订单"}],
            "relations": [{"source": "星海科技", "target": "订单B1",
                           "relation_type": "下达", "text": "星海科技向订单B1下达采购"}],
        }, ensure_ascii=False)

    llm = kg_llm_extractor.LLMExtractor({"model": "m"}, complete=fake_complete)
    ents, rels = llm("星海科技向订单B1下达采购", schema_hint="只抽客户与订单")
    assert "只抽客户与订单" in seen["prompt"]
    assert len(ents) == 2 and rels[0]["relation_type"] == "下达"


def test_llm_extractor_without_model_or_complete_raises():
    llm = kg_llm_extractor.LLMExtractor({})
    with pytest.raises(ValueError):
        llm("文本")


def test_llm_extractor_parse_failure_carries_model_desc():
    """错误信息带上模型标识，排障时不必回去翻配置。"""
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "qwen-plus", "provider": "openai"},
        complete=lambda p: "我不确定，无法抽取。",
    )
    with pytest.raises(ValueError) as exc:
        llm("文本")
    assert "qwen-plus" in str(exc.value)


# ── _call_model：agentscope 默认 stream=True，返回 async_generator ────
class _FakeChatModel:
    """假 ChatModel：返回形态可配，并记录构造后的调用。

    真实回归背景：agentscope 2.x 各 ChatModel 的 ``stream`` 默认 **True**，
    ``await model(...)`` 拿到的是 async_generator 而非 ChatResponse；旧代码
    用 ``_safe_text`` 抽不到文本 → ``str()`` 出 repr → 「响应不是 JSON」，
    整个 LLM 通道对每一段都报结构失败。
    """

    def __init__(self, *, stream_mode: str, thinking: bool = False) -> None:
        self.stream_mode = stream_mode
        self.thinking = thinking
        self.received: list = []

    async def __call__(self, msgs):
        self.received.append(msgs)
        payload = json.dumps(
            {"entities": [{"name": "星海科技", "label": "客户"}], "relations": []},
            ensure_ascii=False,
        )
        if self.stream_mode == "generator":
            return self._stream(payload)
        return self._resp(payload, is_last=True)

    def _resp(self, text, is_last):
        from agentscope.message import TextBlock, ThinkingBlock
        from agentscope.model import ChatResponse

        content = []
        if self.thinking:
            # 思考链里带花括号：若被拼进正文，粗切的 {...} 会解出错对象
            content.append(ThinkingBlock(thinking="思考：先想 {bad} 再答"))
        content.append(TextBlock(text=text))
        return ChatResponse(content=content, is_last=is_last)

    async def _stream(self, text):
        # 模拟真实语义：逐块产出增量，最后一块 is_last=True 携完整累计文本
        for i in range(0, len(text), 10):
            yield self._resp(text[i:i + 10], is_last=False)
        yield self._resp(text, is_last=True)


def _patch_build_model(monkeypatch, model):
    import app.ai.strategy.factory_ext as factory_ext

    captured = {"cfg": None, "cfgs": []}

    def fake_build(cfg):
        captured["cfg"] = dict(cfg)
        captured["cfgs"].append(dict(cfg))
        return model

    monkeypatch.setattr(factory_ext, "build_model", fake_build)
    return captured


class _FlakyChatModel:
    """假模型：前 ``fail_times`` 次调用抛指定错误，之后正常返回 JSON。

    用于复现自托管引擎的窗口溢出 400（真实形态是 ``BadRequestError``，文案含
    「Context size has been exceeded」），检验抽取通道的退避重试。
    """

    CTX_MSG = (
        "Error code: 400 - Engine protocol predict stream returned an error: "
        "Context size has been exceeded."
    )

    def __init__(self, *, fail_times: int, message: str = CTX_MSG) -> None:
        self.fail_times = fail_times
        self.message = message
        self.calls = 0

    async def __call__(self, msgs):
        from agentscope.message import TextBlock
        from agentscope.model import ChatResponse

        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(self.message)
        payload = json.dumps(
            {"entities": [{"name": "星海科技", "label": "客户"}], "relations": []},
            ensure_ascii=False,
        )
        return ChatResponse(content=[TextBlock(text=payload)], is_last=True)


class _StaticChatModel:
    """假模型：每次都返回同一个响应（用来固定 ``usage`` 与块形态）。"""

    def __init__(self, resp) -> None:
        self._resp = resp

    async def __call__(self, msgs):
        return self._resp


def test_call_model_accepts_streaming_generator(monkeypatch):
    """模型返回流式 async_generator 时必须聚合分块，不得把 repr 当正文。"""
    fake = _FakeChatModel(stream_mode="generator")
    _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    raw = llm._call_model("抽取吧")
    assert json.loads(raw)["entities"][0]["name"] == "星海科技"
    assert "async_generator" not in raw


def test_call_model_requests_non_stream_and_accepts_chat_response(monkeypatch):
    """优先以 stream=False 构造模型；非流式返回（ChatResponse）仍能直接抽文本。"""
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    raw = llm._call_model("抽取吧")
    assert captured["cfg"].get("stream") is False, "后台一次性补全必须显式关闭流式"
    assert json.loads(raw)["entities"][0]["name"] == "星海科技"


def test_call_model_ignores_thinking_blocks(monkeypatch):
    """思考链（ThinkingBlock）不得拼进正文：思考里的花括号会破坏 JSON 截取。"""
    fake = _FakeChatModel(stream_mode="response", thinking=True)
    _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    raw = llm._call_model("抽取吧")
    assert "思考" not in raw and "{" in raw
    assert json.loads(raw)["entities"][0]["name"] == "星海科技"


def test_call_model_thinking_only_reports_block_types(monkeypatch):
    """零正文时错误要带块类型：「思考链没关掉」与「模型改去调工具」处置完全不同。"""
    from agentscope.message import ThinkingBlock
    from agentscope.model import ChatResponse

    class _ThinkingOnly:
        async def __call__(self, msgs):
            return ChatResponse(content=[ThinkingBlock(thinking="只想不答")], is_last=True)

    _patch_build_model(monkeypatch, _ThinkingOnly())
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    with pytest.raises(ValueError) as ei:
        llm._call_model("抽取吧")
    msg = str(ei.value)
    assert "没有正文文本" in msg
    assert "thinking" in msg, "报错需点明拿到了什么块，否则只能盲猜模型行为"


def test_build_model_forwards_explicit_stream(monkeypatch):
    """factory_ext.build_model 把 cfg["stream"] 透传给支持它的模型类，缺省则不传。"""
    import app.ai.strategy.factory_ext as factory_ext

    seen = {}

    class _SpyModel:
        """对齐真实 OpenAIChatModel 的构造签名（含 stream）。"""

        Parameters: object = None

        def __init__(self, credential, model, parameters=None, stream=True, **kw):
            seen["stream"] = stream

    class _SpyCred:
        model_fields: dict = {}

        def __init__(self, **kw):
            pass

    # 真实类在 build_model 函数体内局部导入：改包级属性才能被函数体拿到
    import agentscope.model as as_model

    monkeypatch.setattr(as_model, "OpenAIChatModel", _SpyModel)
    import agentscope.credential as as_cred

    monkeypatch.setattr(as_cred, "OpenAICredential", _SpyCred)

    base_cfg = {"provider": "openai", "model": "m", "api_key": "k"}

    factory_ext.build_model({**base_cfg, "stream": False})
    assert seen["stream"] is False, "后台一次性补全要能显式关闭流式"

    seen.clear()
    seen["stream"] = None
    factory_ext.build_model(base_cfg)
    assert seen["stream"] is True, "不传 stream 时保持模型默认（agent 侧依赖流式，不得全局改变）"


def test_build_model_forwards_extra_body_only_when_supported(monkeypatch):
    """extra_body 只透传给构造器支持它的模型类（openai 兼容类支持）。"""
    import app.ai.strategy.factory_ext as factory_ext

    seen = {}

    class _SpyModel:
        Parameters: object = None

        def __init__(self, credential, model, parameters=None, stream=True,
                     extra_body=None, **kw):
            seen["extra_body"] = extra_body

    class _SpyCred:
        model_fields: dict = {}

        def __init__(self, **kw):
            pass

    import agentscope.model as as_model
    import agentscope.credential as as_cred

    monkeypatch.setattr(as_model, "OpenAIChatModel", _SpyModel)
    monkeypatch.setattr(as_cred, "OpenAICredential", _SpyCred)

    eb = {"chat_template_kwargs": {"enable_thinking": False}}
    factory_ext.build_model(
        {"provider": "openai", "model": "m", "api_key": "k", "extra_body": eb}
    )
    assert seen["extra_body"] == eb, "extra_body 必须透传到构造器"


def test_call_model_disables_thinking_by_default(monkeypatch):
    """抽取通道默认向请求体注入关思考字段（适配 vLLM/SGLang 等后端）。"""
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    llm._call_model("抽取吧")
    cfg = captured["cfg"]
    assert cfg["stream"] is False
    assert cfg["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_call_model_keeps_thinking_when_opted_out(monkeypatch):
    """disable_thinking=False 时不得注入关思考字段（留给真需要推理的模型）。"""
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "m", "provider": "openai"}, disable_thinking=False
    )
    llm._call_model("抽取吧")
    assert "extra_body" not in captured["cfg"]


def test_call_model_applies_default_output_token_ceiling(monkeypatch):
    """模型行未配 max_tokens 时按抽取预算封顶。

    真实回归背景：小上下文自托管引擎上输出无上限，0.8B 模型会生成上千条
    冗长 JSON 吃满窗口 → 概率性 400「Context size has been exceeded」。
    """
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    llm._call_model("抽取吧")
    assert captured["cfg"]["max_tokens"] == kg_llm_extractor.DEFAULT_MAX_OUTPUT_TOKENS


def test_call_model_keeps_smaller_explicit_max_tokens(monkeypatch):
    """模型行 max_tokens 比抽取预算更小时照用（封顶只往下压，绝不放大）。"""
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "m", "provider": "openai", "max_tokens": 256}
    )
    llm._call_model("抽取吧")
    assert captured["cfg"]["max_tokens"] == 256


def test_call_model_caps_oversized_model_row_max_tokens(monkeypatch):
    """模型行的对话输出上限不得照抄进抽取通道——那是引擎拒绝整条请求的直接原因。

    真实回归背景：LM Studio 实例 context_length=8192 / parallel=4，模型行
    ``max_tokens=8192`` 配上默认 concurrency_count=8 后，每个请求都向引擎预订
    整个窗口：实测 4 路并发下 max_tokens=4096 有 3/4 直接 400，而 ≤1024 全通过
    （45 段抽取失败 40 段的成因）。
    """
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "m", "provider": "openai", "max_tokens": 8192}
    )
    llm._call_model("抽取吧")
    assert captured["cfg"]["max_tokens"] == kg_llm_extractor.DEFAULT_MAX_OUTPUT_TOKENS


def test_call_model_retries_with_halved_budget_on_context_exceeded(monkeypatch):
    """撞窗口（引擎 400）属可退避的容量问题：减半输出预算重试，而不是判死该段。"""
    fake = _FlakyChatModel(fail_times=1)
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    raw = llm._call_model("抽取吧")
    assert json.loads(raw)["entities"][0]["name"] == "星海科技"
    budgets = [c["max_tokens"] for c in captured["cfgs"]]
    assert len(budgets) == 2, "窗口溢出应重试一次"
    assert budgets[1] == max(
        kg_llm_extractor.MIN_OUTPUT_TOKENS, budgets[0] // 2
    ), budgets


def test_call_model_gives_up_after_retry_limit(monkeypatch):
    """退避到下限仍被拒 → 抛出原始错误（保留引擎文案），不无限重试拖垮整批。"""
    fake = _FlakyChatModel(fail_times=99)
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    with pytest.raises(Exception) as exc:
        llm._call_model("抽取吧")
    assert "Context size has been exceeded" in str(exc.value)
    assert len(captured["cfgs"]) == kg_llm_extractor.CTX_RETRY_LIMIT + 1
    assert captured["cfgs"][-1]["max_tokens"] == kg_llm_extractor.MIN_OUTPUT_TOKENS


def test_call_model_does_not_retry_on_non_context_error(monkeypatch):
    """非容量类错误（端点不可达等）不占用退避预算：一次即抛，交给上层记账。"""
    fake = _FlakyChatModel(fail_times=99, message="Connection refused")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    with pytest.raises(Exception) as exc:
        llm._call_model("抽取吧")
    assert "Connection refused" in str(exc.value)
    assert len(captured["cfgs"]) == 1


# ── 关思考方言协商 ──────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _fresh_dialect_cache():
    """「哪个字段被哪家引擎拒了」是模块级缓存：用例之间必须清空。

    autouse 对**整个文件**生效（pytest 不按定义位置限定作用域）：否则前面用例
    的降级结论会泄露到后面，``extra_body`` 断言随机红。
    """
    kg_llm_extractor._REJECTED_THINKING_DIALECTS.clear()
    yield
    kg_llm_extractor._REJECTED_THINKING_DIALECTS.clear()


def test_thinking_off_body_skips_rejected_dialects():
    """纯函数：未撤的方言全给，撤掉的不给，全撤干净时为空 dict。"""
    full = kg_llm_extractor.thinking_off_body()
    assert full == {
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
    }
    assert kg_llm_extractor.thinking_off_body({"reasoning_effort"}) == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert kg_llm_extractor.thinking_off_body({"chat_template_kwargs"}) == {
        "reasoning_effort": "none"
    }
    assert kg_llm_extractor.thinking_off_body(
        {"chat_template_kwargs", "reasoning_effort"}
    ) == {}


@pytest.mark.parametrize(
    "message,expected",
    [
        # 点名字段：只撤被点名的那个，另一个仍有机会生效
        ("Error code: 400 - Unknown parameter: 'reasoning_effort'.",
         {"reasoning_effort"}),
        ("Error code: 400 - {'error': {'message': \"unrecognized key: chat_template_kwargs\"}}",
         {"chat_template_kwargs"}),
        # 泛化说法（不给字段名）：两条方言一起撤，换回裸请求先跑通
        ("Error code: 400 - 2 extra fields not permitted",
         {"chat_template_kwargs", "reasoning_effort"}),
        # 容量拒绝与字段无关：撤字段只是白耗一次重试
        (_FlakyChatModel.CTX_MSG, set()),
        # 鉴权/网络类不能被当成「字段不对」，否则错误方向全跑偏
        ("Error code: 401 - invalid api key", set()),
        ("Connection refused", set()),
    ],
)
def test_rejected_thinking_dialect_only_for_field_complaints(message, expected):
    got = kg_llm_extractor.rejected_thinking_dialect(RuntimeError(message))
    assert got == expected, message


def test_call_model_sends_both_thinking_dialects(monkeypatch):
    """一次把两种写法都发出去：vLLM/SGLang 认 ``chat_template_kwargs``，
    LM Studio/llama.cpp 认 ``reasoning_effort``——谁认谁生效，不认的静默忽略。

    真实回归背景：本机 LM Studio（unsloth qwen3.5-0.8b GGUF）实测只认后者，
    原先单发 ``chat_template_kwargs`` 等于没传，思考链吃满预算 → ``blocks=['thinking']``。
    """
    fake = _FakeChatModel(stream_mode="response")
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    llm._call_model("抽取吧")
    body = captured["cfg"]["extra_body"]
    assert body["chat_template_kwargs"]["enable_thinking"] is False
    assert body["reasoning_effort"] == "none"


def test_call_model_drops_named_dialect_and_retries(monkeypatch):
    """被点名的字段撤掉重试一次，而不是整段判死；且不占用容量退避的减半语义。"""
    fake = _FlakyChatModel(
        fail_times=1,
        message="Error code: 400 - Unknown parameter: 'reasoning_effort'.",
    )
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    raw = llm._call_model("抽取吧")
    assert json.loads(raw)["entities"][0]["name"] == "星海科技"
    bodies = [c["extra_body"] for c in captured["cfgs"]]
    assert len(bodies) == 2, "字段被拒应重试一次"
    assert "reasoning_effort" in bodies[0]
    assert "reasoning_effort" not in bodies[1], "点名的字段必须撤掉再重试"
    assert bodies[1]["chat_template_kwargs"]["enable_thinking"] is False
    assert captured["cfgs"][1]["max_tokens"] == captured["cfgs"][0]["max_tokens"], \
        "字段降级与输出预算无关，不要把减半退避的额度花在这里"


def test_call_model_drops_all_dialects_on_generic_rejection(monkeypatch):
    """引擎只说「有非法字段」不点名时，两条方言一起撤，退到裸请求。"""
    fake = _FlakyChatModel(
        fail_times=1, message="Error code: 400 - 2 extra fields not permitted"
    )
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    raw = llm._call_model("抽取吧")
    assert json.loads(raw)["entities"][0]["name"] == "星海科技"
    assert not captured["cfgs"][1].get("extra_body"), captured["cfgs"][1]


def test_dialect_rejection_is_cached_per_model(monkeypatch):
    """同一模型只协商一次：结论缓存后下一段不再重复吃 400（45 段就是 45 次）。"""
    fake = _FlakyChatModel(
        fail_times=1,
        message='Error code: 400 - unrecognized key: "chat_template_kwargs"',
    )
    captured = _patch_build_model(monkeypatch, fake)
    cfg = {"model": "m", "provider": "openai"}
    kg_llm_extractor.LLMExtractor(cfg)._call_model("抽取吧")
    assert "chat_template_kwargs" in kg_llm_extractor._REJECTED_THINKING_DIALECTS[
        kg_llm_extractor.LLMExtractor(cfg).model_desc
    ]

    second = _patch_build_model(monkeypatch, _FakeChatModel(stream_mode="response"))
    kg_llm_extractor.LLMExtractor(cfg)._call_model("抽取吧")
    assert len(second["cfgs"]) == 1, "已协商过的模型不该再被拒一次"
    body = second["cfgs"][0]["extra_body"]
    assert "chat_template_kwargs" not in body
    assert body["reasoning_effort"] == "none"


def test_context_400_does_not_drop_dialects(monkeypatch):
    """窗口溢出的 400 只减半预算，关思考字段一个都不能撤（撤了思考更吃窗口）。"""
    fake = _FlakyChatModel(fail_times=1)
    captured = _patch_build_model(monkeypatch, fake)
    llm = kg_llm_extractor.LLMExtractor({"model": "m", "provider": "openai"})
    llm._call_model("抽取吧")
    assert len(captured["cfgs"]) == 2
    for c in captured["cfgs"]:
        assert c["extra_body"]["reasoning_effort"] == "none"
        assert c["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert captured["cfgs"][1]["max_tokens"] == captured["cfgs"][0]["max_tokens"] // 2


# ── 思考链撞顶：空正文要报出数值 ────────────────────────────────────────
def _resp_with_thinking(*, usage=None, thinking="先想再说", blocks=None):
    from agentscope.message import ThinkingBlock
    from agentscope.model import ChatResponse

    # blocks=None 时默认一个思考块；显式传 [] 才是「内容列表为空」的形态
    content = list(
        blocks if blocks is not None else [ThinkingBlock(thinking=thinking)]
    )
    return ChatResponse(content=content, is_last=True, usage=usage)


def test_call_model_thinking_overflow_reports_numbers(monkeypatch):
    """思考链吃满输出预算、正文为空：错误要带三个数值，用户才知道该调预算还是关思考。

    真实回归背景：LM Studio 上 64 token 预算被思考链全吃掉（``completion_tokens=64``、
    ``reasoning_len=119``、``content=''``），旧报错只有 ``blocks=['thinking']``，
    看不出是容量问题还是模型行为问题。
    """
    from agentscope.model import ChatUsage

    _patch_build_model(
        monkeypatch,
        _StaticChatModel(
            _resp_with_thinking(
                thinking="先" * 119,
                usage=ChatUsage(input_tokens=10, output_tokens=64, time=0.1),
            )
        ),
    )
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "m", "provider": "openai"}, max_output_tokens=64
    )
    with pytest.raises(kg_failure.KgExtractionError) as ei:
        llm._call_model("抽取吧")
    assert ei.value.code == kg_failure.THINKING_OVERFLOW
    msg = str(ei.value)
    assert "思考链占满" in msg
    assert "output_tokens=64" in msg and "budget=64" in msg
    assert "thinking_chars=119" in msg
    assert isinstance(ei.value, ValueError)


@pytest.mark.parametrize(
    "usage,blocks",
    [
        # 无 usage：拿不出撞顶证据，仍按「只回思考块」报
        (None, None),
        # 有用量但远未到预算：是模型行为问题，不是容量问题
        ({"output_tokens": 8}, None),
        # 撞顶但一个思考字符都没有（空内容）：不能凭空归给思考链
        ({"output_tokens": 64}, []),
    ],
)
def test_call_model_no_text_without_overflow_evidence(monkeypatch, usage, blocks):
    """没有「思考 + 用量顶满」双证据时绝不改判 thinking_overflow。"""
    from agentscope.model import ChatUsage

    resp = _resp_with_thinking(
        thinking="先" * 119,
        usage=ChatUsage(input_tokens=1, time=0.1, **(usage or {})) if usage else None,
        blocks=blocks,
    )
    _patch_build_model(monkeypatch, _StaticChatModel(resp))
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "m", "provider": "openai"}, max_output_tokens=64
    )
    with pytest.raises(kg_failure.KgExtractionError) as ei:
        llm._call_model("抽取吧")
    assert ei.value.code == kg_failure.MODEL_NO_TEXT


# ── 截断补齐的裁剪留痕 ──────────────────────────────────────────────────
TRUNCATED_SAMPLE = (
    '{"entities": ['
    '{"name": "星海科技", "label": "客户", "aliases": [], "properties": {}}, '
    '{"name": "北京仓", "label": "仓库", "aliases": [], "properties": {}}], '
    '"relations": ['
    '{"source": "星海科技", "target": "北京仓", "relation_type": "库存", "text": "库存于北京仓"}, '
    '{"source": "星海科技", "target": "上海仓", "relation_type":'
)


def test_parse_response_flags_truncated_repair():
    """补齐成功也要留痕：不写「裁掉了什么」，前端就会把残缺结果当成抽全了。"""
    out = kg_llm_extractor.parse_response(
        TRUNCATED_SAMPLE,
        truncation={"output_tokens": 1024, "budget": 1024,
                    "had_thinking": True, "thinking_chars": 80},
    )
    entities, triplets = out  # 老调用按 2 元组解包不能破
    assert [e["name"] for e in entities] == ["星海科技", "北京仓"]
    notice = out.notice
    assert notice["type"] == "truncated_json"
    assert notice["kept_entities"] == 2 and notice["kept_relations"] == 2
    assert notice["dropped_chars"] > 0, "被丢弃的尾部长度必须量得出来"
    assert notice["output_tokens"] == 1024 and notice["budget"] == 1024
    assert notice["budget_hit"] is True and notice["thinking_chars"] == 80


def test_parse_response_no_notice_when_complete():
    """正常响应不得凭空造留痕（``truncated`` 键存在即会被当成被裁过）。"""
    raw = json.dumps({"entities": [{"name": "A"}], "relations": []})
    out = kg_llm_extractor.parse_response(raw)
    assert out.notice is None
    assert "truncated" not in kg_extractor.ExtractionResult().as_details(0)


def test_parse_response_notice_without_usage_evidence():
    """只有正文、没有用量证据时（注入的 ``complete=`` 通道）留痕仍要写，字段缺省为 0。"""
    out = kg_llm_extractor.parse_response(TRUNCATED_SAMPLE)
    assert out.notice and out.notice["budget"] == 0
    assert out.notice["budget_hit"] is False and out.notice["had_thinking"] is False


def test_extractor_call_carries_usage_evidence_into_notice(monkeypatch):
    """用量证据从响应侧走到解析侧：两边合起来才判得出「这一段的 JSON 被裁剪过」。"""
    from agentscope.message import TextBlock
    from agentscope.model import ChatResponse, ChatUsage

    _patch_build_model(
        monkeypatch,
        _StaticChatModel(
            ChatResponse(
                content=[TextBlock(text=TRUNCATED_SAMPLE)], is_last=True,
                usage=ChatUsage(input_tokens=5, output_tokens=64, time=0.1),
            )
        ),
    )
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "m", "provider": "openai"}, max_output_tokens=64
    )
    out = llm("文本")
    entities, triplets = out
    assert entities and out.notice and out.notice["budget"] == 64
    assert out.notice["budget_hit"] is True


def test_repair_reports_dropped_chars():
    """修复函数直接给出丢弃长度：留痕的 ``dropped_chars`` 只能在这里量到。"""
    fixed, dropped = kg_llm_extractor._repair_truncated_json(TRUNCATED_SAMPLE)
    assert fixed and json.loads(fixed)["entities"][0]["name"] == "星海科技"
    assert dropped == len(TRUNCATED_SAMPLE) - len(
        TRUNCATED_SAMPLE[: TRUNCATED_SAMPLE.index('"上海仓"') + len('"上海仓"')]
    )


# ── 截断续抽与输入留痕 ────────────────────────────────────────────────
def test_extractor_continuation_recovers_dropped_relations():
    """首轮 JSON 被裁 → 一轮有界续抽补回遗漏关系，合并去重且留痕如实更新。"""
    calls: list[str] = []

    def fake_complete(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return TRUNCATED_SAMPLE
        # 续抽只回遗漏项；故意重复「星海科技」与北京仓那条，验证合并去重
        return json.dumps({
            "entities": [{"name": "星海科技", "label": "客户"},
                         {"name": "上海仓", "label": "仓库"}],
            "relations": [{"source": "星海科技", "target": "上海仓",
                           "relation_type": "库存", "text": "在上海仓设库存"},
                          {"source": "星海科技", "target": "北京仓",
                           "relation_type": "库存", "text": "库存于北京仓"}],
        }, ensure_ascii=False)

    llm = kg_llm_extractor.LLMExtractor({"model": "m"}, complete=fake_complete)
    out = llm("星海科技在北京仓和上海仓都设库存")
    ents, rels = out
    assert len(calls) == 2, "首轮被裁后应恰好触发一轮续抽"
    assert any(r.get("relation_type") == "库存" and r.get("target") == "上海仓"
               for r in rels), "续抽补回的关系必须出现在合并结果里"
    assert [e.get("name") for e in ents].count("星海科技") == 1, "重复实体按名去重"
    notice = out.notice or {}
    assert notice.get("continued") is True
    assert notice.get("kept_relations") == len(rels)
    assert notice.get("budget_hit") is False, "续抽没撞顶就不该再报缺口"
    # 续抽指令要带上已抽取清单，避免模型整段重输出
    assert "星海科技|库存|北京仓" in calls[1]


def test_extractor_continuation_failure_keeps_first_pass():
    """续抽失败（网络/解析炸）不得丢掉首轮已拿到的部分结果。"""
    calls: list[str] = []

    def fake_complete(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return TRUNCATED_SAMPLE
        raise RuntimeError("continuation boom")

    llm = kg_llm_extractor.LLMExtractor({"model": "m"}, complete=fake_complete)
    out = llm("文本")
    ents, rels = out
    assert len(calls) == 2, "续抽会被尝试（哪怕失败）"
    assert ents, "首轮部分结果必须保留"
    assert out.notice and out.notice.get("dropped_chars")
    assert "continued" not in out.notice


def test_extractor_input_truncation_notice():
    """输入超过 6000 字符被 prompt 硬切：解析正常时也要留痕，别静默丢尾。"""
    seen: dict = {}

    def fake_complete(prompt):
        seen["prompt"] = prompt
        return json.dumps({"entities": [{"name": "实体A"}], "relations": []},
                          ensure_ascii=False)

    llm = kg_llm_extractor.LLMExtractor({"model": "m"}, complete=fake_complete)
    out = llm("字" * (kg_llm_extractor.MAX_TEXT_CHARS + 10))
    assert out.notice and out.notice["type"] == "input_truncated"
    assert out.notice["kept_chars"] == kg_llm_extractor.MAX_TEXT_CHARS
    assert out.notice["text_chars"] == kg_llm_extractor.MAX_TEXT_CHARS + 10
    # prompt 正文确实被切到上限以内
    assert len(seen["prompt"]) < kg_llm_extractor.MAX_TEXT_CHARS + 2000


def test_build_prompt_limits_evidence_text():
    """证据片段限长 + 空字段省略：压缩单条体积，同一预算能装下更多关系。"""
    p = kg_llm_extractor.build_prompt("正文")
    assert "不超过 60 字" in p


# ── parse_response：输出预算下的截断修复 ────────────────────────────
def test_parse_response_repairs_truncated_json():
    """撞输出上限被拦腰截断的 JSON：回退到最后一个完整值、补齐闭合符，前部条目不得丢。

    真实回归背景：小上下文引擎上抽取响应偶发被 max_tokens 截断在对象中途
    （实测尾部停在 `"relation_type":`），旧逻辑直接报「无法解析」→ 整段结构失败，
    而前 90% 的实体/关系其实完好。
    """
    truncated = (
        '{"entities": ['
        '{"name": "星海科技", "label": "客户", "aliases": []}, '
        '{"name": "北京仓", "label": "仓库", "aliases": []}], '
        '"relations": ['
        '{"source": "星海科技", "target": "北京仓", "relation_type": "库存", "text": "库存于北京仓"}, '
        '{"source": "星海科技", "target": "上海仓", "relation_type":'
    )
    entities, triplets = kg_llm_extractor.parse_response(truncated)
    assert [e["name"] for e in entities] == ["星海科技", "北京仓"]
    # 截断点前的完整键全部保留；末尾那条缺谓词，交给规整层按悬空关系丢弃
    assert [t["target"] for t in triplets] == ["北京仓", "上海仓"]
    assert triplets[0]["relation_type"] == "库存"
    assert "relation_type" not in triplets[1]


def test_parse_response_repair_gives_up_on_unsalvageable():
    """修无可修（连一个完整条目都没有）仍须抛错，不得静默返回空。"""
    with pytest.raises(ValueError):
        kg_llm_extractor.parse_response('{"entities": [{"name": "星海')


def test_parse_response_repairs_truncation_without_any_closer():
    """截断得更狠（整个响应只开了头、没有一个闭合符）也要能保住已完整的条目。"""
    truncated = '{"entities": [{"name'
    with pytest.raises(ValueError):
        # 前部无任何完整条目 → 修复只剩空壳，同样不得静默返回 0 实体
        kg_llm_extractor.parse_response(truncated)
    ok = (
        '{"entities": [{"name": "星海科技", "label": "客户", '
        '"aliases": [], "properties": {}}], "relations": [{"source": '
    )
    entities, triplets = kg_llm_extractor.parse_response(ok)
    assert [e["name"] for e in entities] == ["星海科技"]
    assert triplets == []


# ── kg_extractor 双通道 ──────────────────────────────────────────────────
def test_extract_via_llm_keeps_relation_type_and_unresolved_endpoints():
    def llm(text, *, schema_hint=""):
        return (
            [{"name": "实体A", "label": "T"}, {"name": "实体B", "label": "T"}],
            [{"source": "实体A", "target": "实体B", "relation_type": "属于"},
             {"source": "实体A", "target": "不存在的实体", "relation_type": "属于"}],
        )

    out = kg_extractor.extract("文本", llm=llm)
    assert len(out.relations) == 2, "relation_type 必须被认作谓词，否则关系全被丢弃"
    assert out.relations[0]["relation_type"] == "属于"
    # 端点不在实体清单的关系不再在抽取器丢弃：或已在库内（跨片段），
    # 解析权在构建层（_run_structure 按名查库，都不中才丢）
    assert out.dropped_relations == 0


def test_extract_llm_failure_does_not_fall_back_to_rule_channel():
    """LLM 失败绝不回落规则通道：回落会造出一堆 related_to 弱关系，比空结果更隐蔽。"""
    client_calls = []

    class SpyClient:
        def extract_entities(self, text, **options):
            client_calls.append(text)
            return [{"name": "不该出现", "label": "T"}]

        def extract_triplets(self, text, **kwargs):
            client_calls.append(text)
            return []

    def boom_llm(text, *, schema_hint=""):
        raise RuntimeError("endpoint down")

    out = kg_extractor.extract("文本", client=SpyClient(), llm=boom_llm)
    assert out.entities == [] and out.relations == []
    assert client_calls == [], "LLM 通道失败时不得调用规则通道"
    assert out.errors and "LLM 抽取失败" in out.errors[0]


def test_extract_llm_failure_logs_stack_trace():
    """抽取异常的堆栈必须落日志：errors 里只有一句话，看不出在哪一层、带什么入参炸的。

    本轮实测教训：文档只留下「[graph_extract] 结构失败 22 段」与一句
    ``ValueError: 模型只返回了思考/工具块``，没有栈就无法判断是模型侧还是接线侧。
    """
    from loguru import logger

    def boom(text, *, schema_hint=""):
        raise ValueError("模型只返回了思考/工具块，没有正文文本")

    rendered: list[str] = []
    sink_id = logger.add(
        lambda message: rendered.append(str(message)),
        level="ERROR", format="{level} {message} {exception}",
    )
    try:
        out = kg_extractor.extract("文本", llm=boom)
    finally:
        logger.remove(sink_id)

    assert out.errors and "LLM 抽取失败" in out.errors[0]
    logged = "\n".join(rendered)
    assert "没有正文文本" in logged
    assert "def boom" in logged or "raise ValueError" in logged, \
        "日志里必须带 traceback（含报错帧），不能只有一行异常摘要"


def test_extract_llm_shares_normalization_with_rule_channel():
    """超长名 / 重复实体在两条通道下的处置必须一致。"""
    def llm(text, *, schema_hint=""):
        return (
            [{"name": "x" * (kg_extractor.MAX_ENTITY_NAME_LENGTH + 1)},
             {"name": "实体A"}, {"name": "实体A "}],
            [],
        )

    out = kg_extractor.extract("文本", llm=llm)
    assert len(out.entities) == 1 and out.dropped_entities == 1


# ── 构建服务接线 ─────────────────────────────────────────────────────────
def test_build_records_explicit_downgrade_when_model_missing(db, kb, monkeypatch):
    """LLM 通道不可用时，降级原因必须进构建报告，且抽取按「无 llm」执行。

    静默退回规则通道在本轮之前就这么错过去一次：前端看到「构建成功、0 实体」，
    与「文本确实没有实体」完全不可区分。
    """
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service

    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技向订单B1下达采购", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    seen_kwargs = []
    real_extract = kg_extractor.extract

    def spy_extract(text, **kwargs):
        seen_kwargs.append(kwargs)
        return real_extract(text, **kwargs)

    # 未建 ai_chat_model 表 → resolve_llm_config 拿不到模型 → 通道不可用
    monkeypatch.setattr(kg_extractor, "extract", spy_extract)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")
    db.refresh(seg)

    assert any("LLM 抽取通道不可用" in e for e in report.errors), \
        "降级必须显式记录在报告里"
    assert seen_kwargs and all("llm" not in kw for kw in seen_kwargs), \
        "降级后按规则通道抽取（不给 llm 参数）"
    # 降级后的中文切片零产出 → 不得被标成「抽取完成」（否则配好模型也不再重跑）
    assert seg.graph_structure_indexed is False
    assert report.structure_failed == 1


def test_rule_mode_is_not_reported_as_downgrade(db, kb, monkeypatch):
    """``extractor_type=rule`` 是用户显式选的通道，不该叫「降级」。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service, kg_config

    kg_config.save_graph_config(db, kb.id, {"extractor_type": "rule"})
    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="Oriental Bank", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    def rule_extract(text, **kwargs):
        return kg_extractor.ExtractionResult(entities=[{
            "name": "Oriental Bank", "label": "ORG", "aliases": [],
            "properties": {}, "normalized": kg_extractor.normalize_entity_name("Oriental Bank"),
        }])

    monkeypatch.setattr(kg_extractor, "extract", rule_extract)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")
    db.refresh(seg)

    assert not any("LLM 抽取通道不可用" in e for e in report.errors)
    assert report.structure_done == 1 and seg.graph_structure_indexed is True


def test_llm_channel_is_passed_to_extractor(db, kb, monkeypatch):
    """``extractor_type=llm`` 必须真的把抽取器接到通道上，且 ``model_spec`` 逐层传到。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service, kg_config

    kg_config.save_graph_config(db, kb.id, {"extractor_type": "llm",
                                            "model_spec": "pick"})
    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    got = {}
    payload = json.dumps(
        {"entities": [{"name": "星海科技", "label": "客户"}], "relations": []},
        ensure_ascii=False,
    )

    def fake_build(db_, graph_cfg, *, complete=None):
        got["spec"] = graph_cfg.get("model_spec")
        return kg_llm_extractor.LLMExtractor(complete=lambda p: payload), "qwen"

    monkeypatch.setattr(kg_llm_extractor, "build_llm_extractor", fake_build)
    real_extract = kg_extractor.extract

    def spy_extract(text, **kwargs):
        got["llm"] = kwargs.get("llm")
        return real_extract(text, **kwargs)

    monkeypatch.setattr(kg_extractor, "extract", spy_extract)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")

    assert got["spec"] == "pick", "model_spec 必须原样传到通道构造处"
    assert isinstance(got["llm"], kg_llm_extractor.LLMExtractor), "LLM 通道须接线到抽取"
    assert report.entities == 1
    assert not any("LLM 抽取通道不可用" in e for e in report.errors)


def test_graph_config_output_budget_reaches_extractor(db, kb):
    """KB 级 ``max_output_tokens`` 必须活着走到抽取通道。

    ``resolve_graph_config`` 只透传 DEFAULTS 里登记过的键：没登记的配置项会被
    静默丢掉，小上下文引擎的运维口径（把抽取输出预算调到 512）就变成
    写了不生效的假开关。
    """
    from app.services.kb.kg import kg_config

    kg_config.save_graph_config(db, kb.id, {"max_output_tokens": 512})
    cfg = kg_config.get_graph_config(db, kb.id)
    assert cfg["max_output_tokens"] == 512, "抽取预算需可在 KB 级配置"
    llm, _note = kg_llm_extractor.build_llm_extractor(
        db, cfg, complete=lambda p: "{}"
    )
    assert llm is not None and llm.max_output_tokens == 512, \
        "graph 配置要接到 LLMExtractor 的预算参数上"


def test_extract_error_with_nothing_extracted_counts_as_failure(db, kb):
    """抽取报错且一无所出 → 切片归为失败，否则停在「已抽取但空」永不重试。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service

    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    def extractor(text, **kwargs):
        return kg_extractor.ExtractionResult(errors=["LLM 抽取失败: timeout"])

    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id,
                                          extractor=extractor, embed_fn=vec_fn)
    report = svc.run("build")

    db.refresh(seg)
    assert seg.graph_structure_indexed is False, "空结果不得标记为抽取完成"
    assert report.structure_failed == 1 and report.structure_done == 0


# ── 裁剪留痕到构建详情 ────────────────────────────────────────────
def _notice(**kw) -> dict:
    base = {
        "type": "truncated_json", "output_tokens": 64, "budget": 64,
        "budget_hit": True, "had_thinking": False, "thinking_chars": 0,
        "kept_entities": 1, "kept_relations": 0, "dropped_chars": 12,
    }
    base.update(kw)
    return base


def test_extract_records_truncation_notice():
    """抽取层把补齐留痕搬进 :class:`ExtractionResult`，才能一路走落到段详情。"""
    def llm(text, *, schema_hint=""):
        return kg_llm_extractor.ParsedOutput(
            [{"name": "实体A", "label": "T"}], [], notice=_notice()
        )

    out = kg_extractor.extract("文本", llm=llm)
    assert out.truncation["dropped_chars"] == 12
    assert out.as_details(0)["truncated"]["kept_entities"] == 1


def test_extract_without_truncation_has_no_truncated_key():
    def llm(text, *, schema_hint=""):
        return [{"name": "实体A", "label": "T"}], []

    out = kg_extractor.extract("文本", llm=llm)
    assert out.truncation is None
    assert "truncated" not in out.as_details(0)


def test_build_records_truncation_and_warns(db, kb, monkeypatch):
    """残缺结果照常入库，但详情要带 ``truncated``、日志要告警：否则前端看到
    「抽取成功 1 实体」而不知道后半段 JSON 被裁掉了，运维也无从发现预算不够。
    """
    from loguru import logger

    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service

    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    def extractor(text, **kwargs):
        return kg_extractor.ExtractionResult(
            entities=[{
                "name": "星海科技", "label": "客户", "aliases": [], "properties": {},
                "normalized": kg_extractor.normalize_entity_name("星海科技"),
            }],
            truncation=_notice(),
        )

    rendered: list[str] = []
    sink_id = logger.add(
        lambda message: rendered.append(str(message)),
        level="WARNING", format="{level} {message}",
    )
    monkeypatch.setattr(kg_extractor, "extract", extractor)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")
    logger.remove(sink_id)

    db.refresh(seg)
    assert report.structure_done == 1, "补齐的部分结果仍有价值，不归失败"
    assert seg.graph_extraction_details["truncated"]["dropped_chars"] == 12
    warned = "\n".join(rendered)
    assert "裁剪" in warned and "星海" not in warned, \
        "告警要写预算/丢弃长度，不得把正文刷进日志"


def vec_fn(texts):
    return [[0.1] * 8 for _ in texts]
