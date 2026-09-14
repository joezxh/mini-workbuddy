"""语音层 Prometheus 指标（差距分析 §12）。

设计约束（与项目既有可观测性约定一致）：
- **监控不得阻塞业务**。prometheus_client 为可选依赖，未安装时降级为
  空实现（Noop），应用正常启动，仅 /metrics 端点不可用。
  （参见 requirements.txt 中 OpenTelemetry exporter 的 fallback 约定）
- 幂等创建：某些环境（如 pytest 跨目录）会重复加载本模块，
  直接 `Counter(...)` 会抛 Duplicated timeseries，故先查注册表复用。
"""
from typing import Any


class _NoopMetric:
    """prometheus_client 缺失时的空指标实现。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def inc(self, *args: Any, **kwargs: Any) -> None:
        pass

    def dec(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set(self, *args: Any, **kwargs: Any) -> None:
        pass

    def observe(self, *args: Any, **kwargs: Any) -> None:
        pass

    def labels(self, *args: Any, **kwargs: Any) -> "_NoopMetric":
        return self


try:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - 依赖缺失时走降级
    PROMETHEUS_AVAILABLE = False
    REGISTRY = None
    Counter = Gauge = Histogram = _NoopMetric  # type: ignore[assignment,misc]


def _get_or_create(factory, name: str, documentation: str, **kwargs):
    if not PROMETHEUS_AVAILABLE or REGISTRY is None:
        return _NoopMetric()
    existing = REGISTRY._names_to_collectors.get(name)
    if existing is not None:
        return existing
    return factory(name, documentation, **kwargs)


# 活跃 WS 连接数
voice_ws_connections = _get_or_create(
    Gauge, "voice_ws_connections", "活跃语音 WebSocket 连接数"
)

# 端到端延迟：用户说完 → AI 首个音频包
voice_e2e_latency = _get_or_create(
    Histogram, "voice_e2e_latency_seconds", "用户说完到 AI 首音频的端到端延迟"
)

# 打断生效延迟
voice_bargein_latency = _get_or_create(
    Histogram, "voice_bargein_latency_seconds", "打断生效延迟"
)

# Provider 错误计数（按 provider 维度）
voice_provider_errors = _get_or_create(
    Counter, "voice_provider_errors_total", "Provider 错误数", labelnames=["provider"]
)

# 重放缓冲水位
voice_replay_watermark = _get_or_create(
    Gauge, "voice_replay_watermark", "事件重放缓冲水位"
)

# 工具调用失败计数
voice_tool_call_failures = _get_or_create(
    Counter, "voice_tool_call_failures_total", "会话级工具调用失败数"
)


def render_metrics() -> bytes:
    """导出 Prometheus 文本格式（供 /metrics 端点）。

    prometheus_client 未安装时返回空内容，不抛异常。
    """
    if not PROMETHEUS_AVAILABLE or REGISTRY is None:
        return b"# prometheus_client not installed\n"
    from prometheus_client import generate_latest

    return generate_latest(REGISTRY)
