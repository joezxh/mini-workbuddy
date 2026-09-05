"""LLM 上下文窗口与 token 预算常量（跨模式统一）。

背景：系统主用模型为 GPUStack 上部署的 qwen3-32b。其上下文窗口为
**硬约束**，input(prompt) + output(completion) 必须 <= 窗口大小，否则
vLLM/SGLang 侧直接返回 400：

    "'max_tokens' or 'max_completion_tokens' is too large: N. This model's
     maximum context length is 32768 tokens and your request has M input
     tokens (N > 32768 - M)."

此前各模式（skill / agent / agentTeam）各自硬编码 token 上限，且互不知晓
对方的预算，存在「input 预算 + output 预算 > 窗口」而报错的风险（典型如
skills/execution.py 曾硬截断 output 到 8192，叠加 28000 的 input 预算即
32768+，必然触发 400）。本模块提供单一事实来源 + clamp 工具函数，保证
任意组合下都不会超出模型窗口。

实测方式（2026-08-31）：
    POST http://192.168.40.30/v1/chat/completions
    {"model":"qwen3-32b","messages":[{"role":"user","content":"hi"}],
     "max_tokens":200000}
    → 400 "This model's maximum context length is 32768 tokens"
即当前 GPUStack 未启用 YaRN 扩展（启用后为 131072），窗口为 32768。
"""
from __future__ import annotations

from typing import Dict, Optional

# ── 模型上下文窗口（input + output 总预算）──────────────────────────────
# Qwen3-32B 官方规格：原生 32768 tokens，YaRN 扩展后 131072 tokens。
# 当前 GPUStack 实例未启用 YaRN，实测上限为 32768。
# 若后续在推理框架侧开启 YaRN，只需改这里（或加环境变量覆盖）即可全局生效。
MODEL_CONTEXT_WINDOWS: Dict[str, int] = {
    "qwen3-32b": 32768,
    "qwen3-8b": 32768,
    "qwen-plus": 131072,
}

# 模型名称未登记在上面的兜底窗口（保守取 Qwen3-32B 原生值）
DEFAULT_CONTEXT_WINDOW: int = 32768

# ── 安全余量 ────────────────────────────────────────────────────────────
# 预留给 chat template（role 标记、<|im_start|> 等特殊 token）、工具 schema、
# 以及 token 估算误差的缓冲。_estimate_tokens 采用「1 字符 ≈ 1.5 token」的
# 保守校准，但中英混排/代码/JSON 场景下仍可能低估，必须留余量。
SAFETY_MARGIN_TOKENS: int = 1024

# ── 各模式默认 output(completion) 上限 ──────────────────────────────────
# Qwen3 在 enable_thinking=True 时，推理(thinking) token 也计入 output 预算，
# 因此 output 不能压得太小，否则会截断推理过程导致工具调用/JSON 输出残缺。
# 4096 时长报告/多段结论易被截断，上调至 6144（与 ai_chat_model 表保持同步）。
# 对应 input 预算自动变为：32768 - 1024 - 6144 = 25600。
DEFAULT_MAX_OUTPUT_TOKENS: int = 6144

# input 预算的绝对下限：即使 output 配置得极大，也至少保留这么多给 prompt，
# 避免 clamp 后 input 被压到 0 造成 prompt 被整体丢弃。
MIN_INPUT_BUDGET_TOKENS: int = 4096


def resolve_context_window(model_name: Optional[str]) -> int:
    """按模型名解析上下文窗口，未登记则返回兜底值。

    匹配时忽略大小写与常见前后缀差异（如 "Qwen3-32B" / "gpustack-qwen3-32b"）。
    """
    if not model_name:
        return DEFAULT_CONTEXT_WINDOW
    key = str(model_name).strip().lower()
    if key in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[key]
    # 处理 "gpustack-qwen3-32b" 这类带前缀的写法
    for known, window in MODEL_CONTEXT_WINDOWS.items():
        if known in key:
            return window
    return DEFAULT_CONTEXT_WINDOW


def clamp_output_tokens(
    requested: Optional[int],
    *,
    window: Optional[int] = None,
    input_budget: int = 0,
) -> int:
    """将 output(completion) 上限收敛到不超出模型窗口的安全值。

    约束：input_budget + output <= window - SAFETY_MARGIN_TOKENS
    """
    if window is None:
        window = DEFAULT_CONTEXT_WINDOW
    usable = window - SAFETY_MARGIN_TOKENS
    if not requested or requested <= 0:
        return min(DEFAULT_MAX_OUTPUT_TOKENS, max(usable - input_budget, 1))
    return max(min(int(requested), usable - input_budget), 1)


def clamp_input_budget(
    requested: Optional[int],
    *,
    window: Optional[int] = None,
    output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> int:
    """将 input(prompt) 预算收敛到不超出模型窗口的安全值。

    约束：input + output_tokens <= window - SAFETY_MARGIN_TOKENS
    """
    if window is None:
        window = DEFAULT_CONTEXT_WINDOW
    usable = window - SAFETY_MARGIN_TOKENS
    if not requested or requested <= 0:
        requested = usable - output_tokens
    capped = min(int(requested), usable - output_tokens)
    return max(capped, MIN_INPUT_BUDGET_TOKENS)


def safe_input_budget(
    output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    *,
    model_name: Optional[str] = None,
) -> int:
    """在给定 output 预算下，可用的最大安全 input 预算（默认模型）。"""
    window = resolve_context_window(model_name)
    return clamp_input_budget(None, window=window, output_tokens=output_tokens)


__all__ = [
    "MODEL_CONTEXT_WINDOWS",
    "DEFAULT_CONTEXT_WINDOW",
    "SAFETY_MARGIN_TOKENS",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "MIN_INPUT_BUDGET_TOKENS",
    "resolve_context_window",
    "clamp_output_tokens",
    "clamp_input_budget",
    "safe_input_budget",
]
