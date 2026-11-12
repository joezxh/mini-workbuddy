"""失败分类层回归测试：异常 → 稳定错误码。

覆盖用户实际会看到的三条路径（本轮实测/评审提出）：
* 嵌入模型调不通（未配置维度、端点不可达）；
* LLM 响应不是合法 JSON；
* ``max_tokens`` 撞顶把 JSON 拦腰截断。

码是前端 i18n 的取键依据，所以断言的是**码本身**，不是报错句子。
"""
import asyncio

import pytest

from app.services.kb.kg import kg_failure as kf


@pytest.mark.parametrize(
    "exc,stage,expected",
    [
        # ── LLM 响应侧（结构阶段）──
        (ValueError("模型只返回了思考/工具块，没有正文文本（blocks=['thinking']）"),
         kf.STAGE_STRUCTURE, kf.MODEL_NO_TEXT),
        (ValueError("模型返回空响应（可能是端点不可达或超时后被截断）"),
         kf.STAGE_STRUCTURE, kf.MODEL_NO_TEXT),
        (ValueError("响应不是 JSON（前 200 字）: '抱歉'"),
         kf.STAGE_STRUCTURE, kf.JSON_INVALID),
        (ValueError("响应无法解析为 JSON（前 200 字）: '{\"entities'"),
         kf.STAGE_STRUCTURE, kf.JSON_INVALID),
        (ValueError("响应截断修复后无任何实体/关系（前 200 字）: '{\"entities\": ['"),
         kf.STAGE_STRUCTURE, kf.JSON_TRUNCATED),
        # 思考链吃满输出预算：正文一个字都没有，与「模型转去调工具」修法不同
        (ValueError("思考链占满输出预算，正文为空（thinking_chars=119 output_tokens=64 budget=64）"),
         kf.STAGE_STRUCTURE, kf.THINKING_OVERFLOW),
        # ── 模型与容量 ──
        (RuntimeError("图谱抽取模型未配置，无法调用 LLM 通道（provider=openai model=None）"),
         kf.STAGE_STRUCTURE, kf.MODEL_UNAVAILABLE),
        (RuntimeError("模型管理中无可用的默认对话模型"),
         kf.STAGE_STRUCTURE, kf.MODEL_UNAVAILABLE),
        (RuntimeError(
            "Error code: 400 - Engine protocol predict stream returned an error: "
            "Context size has been exceeded."),
         kf.STAGE_STRUCTURE, kf.CTX_WINDOW_EXCEEDED),
        (asyncio.TimeoutError(), kf.STAGE_STRUCTURE, kf.TIMEOUT),
        # ── 鉴权 / 限流 / 网络 ──
        (RuntimeError("Error code: 401 - {'error': {'message': 'invalid api key'}}"),
         kf.STAGE_STRUCTURE, kf.AUTH_FAILED),
        (RuntimeError("Error code: 429 - Too Many Requests"),
         kf.STAGE_STRUCTURE, kf.RATE_LIMITED),
        (RuntimeError("[Errno 10061] Connect call failed ('127.0.0.1', 8000) - "
                      "Failed to establish a new connection"),
         kf.STAGE_STRUCTURE, kf.ENDPOINT_UNREACHABLE),
        # ── 降级与兜底 ──
        (ValueError("规则抽取零产出（LLM 通道已降级）"),
         kf.STAGE_STRUCTURE, kf.RULE_ZERO_OUTPUT),
        (ValueError("boom"), kf.STAGE_STRUCTURE, kf.UNKNOWN),
    ],
)
def test_classify_structure_stage(exc, stage, expected):
    assert kf.classify(exc, stage=stage) == expected


@pytest.mark.parametrize(
    "exc,expected",
    [
        # 嵌入模型未配置：build_embedding_model 的必填校验
        (ValueError("嵌入维度未配置（dimensions 为契约层必填）"),
         kf.EMBEDDING_UNAVAILABLE),
        # 嵌入端点不可达：结构阶段同类消息要说「对话模型」，此处必须说「嵌入模型」
        (RuntimeError("Failed to establish a new connection: 目标计算机积极拒绝"),
         kf.EMBEDDING_UNAVAILABLE),
        # pgvector 列维度与返回向量长度不符
        (RuntimeError("expected 1024 dimensions, not 1536"),
         kf.EMBEDDING_DIM_MISMATCH),
        (RuntimeError("pgvector: different vector size in comparison"),
         kf.EMBEDDING_DIM_MISMATCH),
        # 「服务端不支持 dimensions 参数」不是维度不符，别误判
        (RuntimeError("Error code: 400 - 'dimensions' is not supported by this model"),
         kf.EMBEDDING_UNAVAILABLE),
        # 向量阶段出现 LLM 侧消息（配置错乱/复用抽取器）也归嵌入不可用
        (ValueError("模型只返回了思考/工具块，没有正文文本"),
         kf.EMBEDDING_UNAVAILABLE),
    ],
)
def test_classify_vector_stage_says_embedding(exc, expected):
    assert kf.classify(exc, stage=kf.STAGE_VECTOR) == expected


def test_thinking_overflow_is_a_typed_code():
    """撞顶是新码：本体由抽取通道在发生处抛出，分类只认码不认句子。"""
    assert kf.THINKING_OVERFLOW in kf.ALL_CODES
    exc = kf.ThinkingOverflowError("任意改写后的句子")
    assert kf.classify(exc) == kf.THINKING_OVERFLOW
    assert isinstance(exc, ValueError), "旧 except ValueError 分支照旧能接"


def test_thinking_overflow_wins_over_truncation_wording():
    """同一句话既说「占满」又说「截断」时按思考链定码：占满才是成因，截断只是表象。"""
    assert kf.classify_message(
        "思考链占满输出预算，正文被截断"
    ) == kf.THINKING_OVERFLOW


def test_thinking_overflow_in_vector_stage_says_embedding():
    """向量阶段不可能出现思考链，出现即嵌入侧配置错乱，要说嵌入模型的问题。"""
    assert kf.classify_message(
        "思考链占满输出预算，正文为空", stage=kf.STAGE_VECTOR
    ) == kf.EMBEDDING_UNAVAILABLE


def test_no_text_still_distinct_from_thinking_overflow():
    """没有预算证据时不许改判：「只有思考块」与「思考吃满预算」是两条码。"""
    assert kf.classify_message(
        "模型只返回了思考/工具块，没有正文文本（blocks=['thinking']）"
    ) == kf.MODEL_NO_TEXT


def test_typed_error_code_wins_over_message():
    """带码异常按码归类，不再回头看消息——消息会改写，码不会。"""
    exc = kf.TruncatedResponseError("任意改写后的句子")
    assert kf.classify(exc) == kf.JSON_TRUNCATED
    assert isinstance(exc, ValueError), "对外仍是 ValueError，旧 except 分支不受影响"


def test_typed_error_keeps_original_cause():
    origin = ValueError("底层原始异常")
    exc = kf.NoTextResponseError("模型没有正文", cause=origin)
    assert exc.__cause__ is origin
    assert kf.classify(exc) == kf.MODEL_NO_TEXT


@pytest.mark.parametrize("code", kf.ALL_CODES)
def test_every_declared_code_round_trips(code):
    """码集合本身即契约：classify 只会产出声明过的码。"""
    exc = kf.KgExtractionError("x", code=code)
    assert kf.classify(exc) == code
    assert isinstance(exc, ValueError)


def test_classify_never_raises_on_odd_objects():
    """分类层不得成为第二个故障点：拿什么异常都得给个码。"""
    for weird in (KeyError("k"), Exception(), OSError(2, "No such file"), TypeError(None)):
        assert kf.classify(weird) in kf.ALL_CODES


def test_classify_message_is_the_string_only_path():
    """构建服务只拿到 ``errors[0]`` 文本时也要求出同一个码。"""
    reason = "LLM 抽取失败: ValueError: 模型只返回了思考/工具块，没有正文文本"
    assert kf.classify_message(reason) == kf.MODEL_NO_TEXT
    assert kf.classify_message(reason, stage=kf.STAGE_VECTOR) == kf.EMBEDDING_UNAVAILABLE
    assert kf.classify_message("") == kf.UNKNOWN


def test_format_error_keeps_type_and_message():
    assert kf.format_error(ValueError("炸了")) == "ValueError: 炸了"
