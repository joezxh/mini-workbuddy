"""ASR 转写结果的 LLM 文本纠正（语音 Demo §ASR 增强）。

模型选择与 kg 抽取/技能执行同一口径：``AiChatModel`` type=1 + is_default=True +
status=1 → 关联 ``AiApiKey``（api_key/url/platform）→ ``factory_ext.build_model``
（不另起一套模型栈）。prompt 只允许修同音字/断句/标点，不改变原意。

思考链必须显式关闭（本机 LM Studio qwen3.5-0.8b 实测：思考链吃满小窗口 →
"Context size has been exceeded"）：复用 kg 抽取的双方言 ``thinking_off_body``
（``chat_template_kwargs.enable_thinking=False`` + ``reasoning_effort="none"``
一起发，谁认谁生效；被引擎点名拒绝时只撤被拒字段重试）。
容量撞窗同款退避：输出预算封顶 + 减半重试（并发 slot 共享窗口，声明越大越易被拒）。
"""
from __future__ import annotations

import asyncio
import types

from loguru import logger

# 待纠正文本上限（字符）：小窗口引擎（8k context）下 12000 字符必超窗，压到 4000
MAX_TEXT_CHARS = 4000
CORRECT_TIMEOUT_SECONDS = 120
# 输出预算：纠正正文≈输入长度，封顶 2048（模型行 max_tokens 更小则照用更小值）；
# 撞窗后减半重试，下限 256、至多 3 次（kg 抽取同款策略）
MAX_OUTPUT_TOKENS = 2048
MIN_OUTPUT_TOKENS = 256
CTX_RETRY_LIMIT = 3

SYSTEM_PROMPT = (
    "你是语音转写文本校对助手。只修正语音识别输出中的同音字错误、断句不当、"
    "标点缺失或误用，输出纠正后的正文。不改变原意，不增删实质内容，不翻译，"
    "不输出任何解释、前后缀或代码块围栏。"
)


class NoDefaultModel(Exception):
    """模型管理中无默认对话模型（AiChatModel is_default=True 且 status=1）"""


class CorrectFailed(Exception):
    """LLM 纠正调用失败（端点/鉴权/超时/无正文/窗口超限重试耗尽）"""


async def correct(text: str, db) -> str:
    """纠正一段转写文本；空文本原样返回。

    async 端点内直接 await：``build_model`` 与请求在同一 loop 构造/发出，
    规避 openai AsyncClient 跨 loop 的连接归属问题（kg 抽取同款结论）。
    """
    from agentscope.message import Msg, TextBlock

    from app.ai.research.llm import _aclose_model
    from app.ai.strategy.factory_ext import build_model
    from app.services.kb.kg.kg_llm_extractor import (
        _collect_text,
        is_context_exceeded,
        rejected_thinking_dialect,
        resolve_llm_config,
        thinking_off_body,
    )

    body = (text or "").strip()[:MAX_TEXT_CHARS]
    if not body:
        return ""

    cfg = resolve_llm_config(db)
    if not cfg or not cfg.get("model"):
        raise NoDefaultModel(
            "模型管理中无可用默认对话模型（需 AiChatModel is_default=True 且 status=1，"
            "关联的 AiApiKey 也已启用）"
        )

    # 输出预算只往下压、绝不放大（模型行 max_tokens=8192 一类会直接撞小窗口引擎）
    declared = int(cfg.get("max_tokens") or 0)
    budget = min(declared, MAX_OUTPUT_TOKENS) if declared else MAX_OUTPUT_TOKENS

    msgs = [
        Msg(name="system", role="system", content=[TextBlock(text=SYSTEM_PROMPT)]),
        Msg(name="user", role="user", content=[TextBlock(text=body)]),
    ]

    rejected: set = set()   # 已被该引擎点名拒绝的关思考方言键
    ctx_attempt = 0
    while True:
        call_cfg = {
            **cfg,
            "stream": False,
            "max_tokens": budget,
            # 关思考双方言一起发（本机 llama.cpp 只认 reasoning_effort=none，
            # chat_template_kwargs 被静默忽略；OpenAI 官方端点则相反）
            "extra_body": {**(cfg.get("extra_body") or {}), **thinking_off_body(rejected)},
        }
        model = build_model(call_cfg)
        try:
            resp = await asyncio.wait_for(model(msgs), timeout=CORRECT_TIMEOUT_SECONDS)
            if isinstance(resp, types.AsyncGeneratorType):
                # 模型类不支持关流式：消费到 is_last 的累计响应（kg 抽取同款兜底）
                final = None
                async for chunk in resp:
                    if getattr(chunk, "is_last", False):
                        final = chunk
                if final is None:
                    raise CorrectFailed("流式响应无终块")
                resp = final
            try:
                corrected = _collect_text(resp, budget=budget)
            except ValueError as exc:  # kg_failure 带码异常均为 ValueError 子类（无正文/思考溢出）
                raise CorrectFailed(str(exc)) from exc
            return corrected.strip()
        except (NoDefaultModel, CorrectFailed):
            raise
        except Exception as exc:  # noqa: BLE001 - 两类可退避重试，其余统一转 CorrectFailed
            # ① 方言被拒（引擎说请求体有非法字段）→ 只撤被点名的关思考字段重试
            sent = set(thinking_off_body(rejected))
            dropped = rejected_thinking_dialect(exc) & sent
            if dropped:
                rejected.update(dropped)
                logger.warning(
                    "voice-demo 纠正：引擎拒绝请求字段 %s，撤掉后重试: %r",
                    sorted(dropped), exc,
                )
                continue
            # ② 容量被拒（Context size has been exceeded）→ 输出预算减半重试
            if is_context_exceeded(exc) and ctx_attempt < CTX_RETRY_LIMIT:
                ctx_attempt += 1
                halved = max(MIN_OUTPUT_TOKENS, budget // 2)
                logger.warning(
                    "voice-demo 纠正：超出模型上下文窗口，输出预算减半重试 (%s -> %s)",
                    budget, halved,
                )
                budget = halved
                continue
            if isinstance(exc, asyncio.TimeoutError):
                raise CorrectFailed(f"LLM 纠正超时（>{CORRECT_TIMEOUT_SECONDS}s）") from exc
            logger.opt(exception=True).warning("voice-demo LLM 纠正失败: {!r}", exc)
            raise CorrectFailed(str(exc) or exc.__class__.__name__) from exc
        finally:
            await _aclose_model(model)
