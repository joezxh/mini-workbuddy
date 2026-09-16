"""OpenTelemetry 可观测性配置"""
from pydantic import BaseModel


class OTelSettings(BaseModel):
    """OpenTelemetry 配置字段"""
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "minworkbuddy"
    OTEL_EXPORTER: str = "console"                    # console | jaeger | otlp
    OTEL_JAEGER_AGENT_HOST: str = "localhost"
    OTEL_JAEGER_AGENT_PORT: int = 6831
    OTEL_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SAMPLE_RATE: float = 1.0
