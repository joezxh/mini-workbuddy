"""图谱构建失败的**分类层** —— 把「异常」翻译成「原因」。

为什么要有这一层
----------------
失败原因原本只以 ``f"{type(exc).__name__}: {exc}"`` 的形态写进
``kms_segment.graph_extraction_details``，前端把它原样倒出来，用户看到的是
``ValueError: 模型只返回了思考/工具块，没有正文文本（blocks=...）`` 这类半截技术句，
既读不出「该改哪个配置」，也让中英文环境混着英文报错。

本模块把「异常 → 稳定错误码」这件事收在一处：

* **码在发生处定**：抽取通道能直接抛带码的 :class:`KgExtractionError`（它最清楚
  自己是截断还是解析失败）；第三方 SDK 的异常则由 :func:`classify` 按消息特征归类。
* **码是对外契约**：前端按码取 i18n 文案（``kbMgmt.kg.fail.<code>``），所以码只增不改，
  文案与语言包都跟着码走，改句子不需要发后端。
* **原始串绝不丢**：``details.error`` 继续存技术细节，UI 折叠展示 / 悬浮可见。

``classify`` 只用标准库，不导入 agentscope/openai：抽取链路的异常可能在任何
loop 之外被搬运，分类层多一个依赖就多一处导入失败的风险。
"""
from __future__ import annotations

import asyncio
from typing import Optional

# ── 错误码（稳定契约：只增不改不删）──────────────────────────────────────
MODEL_UNAVAILABLE = "model_unavailable"          # 模型管理里没有可用对话模型/密钥
MODEL_NO_TEXT = "model_no_text"                  # 模型只回思考或工具块，没有正文
THINKING_OVERFLOW = "thinking_overflow"          # 思考链吃满输出预算，正文为空
JSON_TRUNCATED = "json_truncated"                # max_tokens 撞顶，JSON 被拦腰截断
JSON_INVALID = "json_invalid"                    # 返回了正文但不是合法 JSON
CTX_WINDOW_EXCEEDED = "ctx_window_exceeded"      # 引擎按上下文窗口容量拒绝请求
TIMEOUT = "timeout"                              # 单次调用超时
AUTH_FAILED = "auth_failed"                      # 鉴权失败（401/403/无效密钥）
ENDPOINT_UNREACHABLE = "endpoint_unreachable"    # 端点不可达/连接失败
RATE_LIMITED = "rate_limited"                    # 限流/配额用尽
EMBEDDING_UNAVAILABLE = "embedding_unavailable"  # 嵌入模型未配置或调不通
EMBEDDING_DIM_MISMATCH = "embedding_dim_mismatch"  # 向量维度与库表列不符
RULE_ZERO_OUTPUT = "rule_zero_output"            # 规则通道（无 LLM）中文零产出
UNKNOWN = "unknown"

ALL_CODES = (
    MODEL_UNAVAILABLE, MODEL_NO_TEXT, THINKING_OVERFLOW, JSON_TRUNCATED,
    JSON_INVALID, CTX_WINDOW_EXCEEDED, TIMEOUT, AUTH_FAILED, ENDPOINT_UNREACHABLE,
    RATE_LIMITED, EMBEDDING_UNAVAILABLE, EMBEDDING_DIM_MISMATCH,
    RULE_ZERO_OUTPUT, UNKNOWN,
)

# 阶段（与 kms_segment 的两个标志位一一对应，是对外契约的一部分）
STAGE_STRUCTURE = "structure"
STAGE_VECTOR = "vector"


class KgExtractionError(ValueError):
    """带码的抽取异常。

    基类是 ``ValueError`` 而不是 ``RuntimeError``：抽取通道历史上一直抛
    ``ValueError``（解析响应、模型未配置都是「值不合法」），既有调用方与回归
    测试按 ``except ValueError`` 接。改基类会让老代码漏接，码只是**附加**信息。

    ``code`` 必须来自本模块常量；``cause`` 保留原始异常（若有），
    日志侧继续按堆栈打印，分类侧只看 ``code``。
    """

    def __init__(self, message: str, *, code: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.code = code
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause


class ModelUnavailableError(KgExtractionError):
    def __init__(self, message: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, code=MODEL_UNAVAILABLE, cause=cause)


class NoTextResponseError(KgExtractionError):
    def __init__(self, message: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, code=MODEL_NO_TEXT, cause=cause)


class ThinkingOverflowError(KgExtractionError):
    """思考链把输出预算吃光、正文一个字都没有。

    与 :class:`NoTextResponseError` 分开是因为修法不同：「只有思考块」可能是
    模型行为/引擎不认识关思考字段；而「思考占满预算」是容量问题——把
    ``max_output_tokens`` 调大或真正关掉思考才有解，换模型多半照旧失败。
    """

    def __init__(self, message: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, code=THINKING_OVERFLOW, cause=cause)


class TruncatedResponseError(KgExtractionError):
    def __init__(self, message: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, code=JSON_TRUNCATED, cause=cause)


class InvalidResponseError(KgExtractionError):
    def __init__(self, message: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, code=JSON_INVALID, cause=cause)


# ── 消息特征表 ───────────────────────────────────────────────────────────
# 引擎「窗口不够用」的文案特征（LM Studio/llama.cpp、vLLM、OpenAI 兼容后端各一套说法）。
# 抽取通道的退避重试另有 :func:`kg_llm_extractor.is_context_exceeded`（只看请求能不能重试，
# 不含中文说法）：改这里时记得同步那一份，否则「减半重试了但分类成 unknown」。
_CTX_MARKERS = (
    "context size has been exceeded",
    "maximum context length",
    "context_length_exceeded",
    "context window",
    "exceeds the model",
    "too many tokens",
    "上下文窗口",
)

# PGVector/驱动在「向量长度 ≠ 列定义维度」时的说法。
# 只收不会误伤日常报错的特征短语：拿 "expected"/"dimensions" 这种常见词当依据，
# 会把「服务端不支持 dimensions 参数」一类调用错误误判成维度不符，两者修法不同。
_DIM_MARKERS = (
    "dimensions, not",              # psycopg: expected 1024 dimensions, not 1536
    "vector size",                  # pgvector: different vector size
    "different size",               # column size mismatch
    "invalid input syntax for type vector",
)

_AUTH_MARKERS = (
    "401", "403", "unauthorized", "forbidden",
    "invalid api key", "incorrect api key", "invalid_api_key",
    "authentication", "api key", "密钥",
)

_RATE_MARKERS = (
    "429", "rate limit", "rate_limit", "too many requests",
    "quota", "allocated capacity",
)

_UNREACHABLE_MARKERS = (
    "connection error", "connection refused", "connection reset",
    "connection aborted", "failed to establish a new connection",
    "cannot connect", "can't connect", "unreachable", "getaddrinfo",
    "nodename nor servname", "max retries exceeded", "eof occurred",
    "remote name could not be resolved", "winerror",
    "timed out",            # 连接层超时（与本地 wait_for 超时同类，都归不可达）
)

# 项目自产消息：抽取/解析各分支的固定说法
# 顺序即优先级：思考链占满的句子常带「截断」字样，必须排在 JSON_TRUNCATED 前。
_SELF_MARKERS = (
    (THINKING_OVERFLOW, ("思考链占满",)),
    (MODEL_NO_TEXT, ("没有正文文本", "思考/工具块", "流式响应无终块", "空响应")),
    (JSON_TRUNCATED, ("截断", "truncat", "max_tokens", "输出预算")),
    (JSON_INVALID, ("不是 json", "无法解析", "顶层不是对象")),
    (RULE_ZERO_OUTPUT, ("零产出",)),
    (MODEL_UNAVAILABLE, ("模型不可用", "模型未配置", "默认对话模型", "api 密钥缺失",
                        "已禁用", "不走 llm 通道", "通道不可用")),
)


def _hits(text: str, markers) -> bool:
    return any(m in text for m in markers)


def _match_self_code(message: str) -> Optional[str]:
    """先按项目**自产**消息定码：这些文案由本仓代码写出，比猜第三方字符串可靠。"""
    for code, markers in _SELF_MARKERS:
        if _hits(message, markers):
            return code
    return None


def format_error(exc: BaseException) -> str:
    """技术细节原文（``类型名: 消息``），继续存进 ``details.error`` 供悬浮/排障。"""
    return f"{type(exc).__name__}: {exc}"


def classify_message(message: str, *, stage: str = STAGE_STRUCTURE) -> str:
    """手上只有字符串（``ExtractionResult.errors`` 里搬过来的）时按消息定码。

    构建服务拿到的是抽取器吞掉异常后留下的文本，没有异常对象可用；
    复用 :func:`classify` 的消息特征表，避免两处各写一套判定。
    """
    return classify(ValueError(message or ""), stage=stage)


def classify(exc: BaseException, *, stage: str = STAGE_STRUCTURE) -> str:
    """异常 → 错误码。永不抛错，兜不到就返回 :data:`UNKNOWN`（原始串仍由调用方带出）。

    ``stage`` 参与判定：同为「连接不上」，结构阶段要说「对话模型调不通」，
    向量阶段要说「嵌入模型调不通」——两阶段的修法完全不同，不能共用一个码。
    """
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in ALL_CODES:
        return code

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return TIMEOUT

    text = f"{type(exc).__name__}: {exc}".lower()

    # 维度不符只在向量阶段有意义（PG 写入时才可能撞列定义）
    if stage == STAGE_VECTOR and _hits(text, _DIM_MARKERS):
        return EMBEDDING_DIM_MISMATCH

    # 自产消息优先（含中文固定说法）
    self_code = _match_self_code(text)
    if self_code:
        if stage == STAGE_VECTOR and self_code in (
            MODEL_UNAVAILABLE, MODEL_NO_TEXT, THINKING_OVERFLOW,
            JSON_INVALID, JSON_TRUNCATED, RULE_ZERO_OUTPUT
        ):
            # 向量阶段不可能出现「解析 LLM 响应」类消息，出现即嵌入侧问题
            return EMBEDDING_UNAVAILABLE
        return self_code

    if _hits(text, _CTX_MARKERS):
        return CTX_WINDOW_EXCEEDED
    if _hits(text, _RATE_MARKERS):
        return RATE_LIMITED
    if _hits(text, _AUTH_MARKERS):
        return AUTH_FAILED
    if _hits(text, _UNREACHABLE_MARKERS):
        return EMBEDDING_UNAVAILABLE if stage == STAGE_VECTOR else ENDPOINT_UNREACHABLE

    if stage == STAGE_VECTOR:
        # 向量阶段的失败绝大多数来自嵌入模型调用（构造失败、返回空、协议不兼容）
        return EMBEDDING_UNAVAILABLE
    return UNKNOWN
