"""OpenTelemetry 导出器配置"""
import logging
from typing import Optional

from loguru import logger

from app.config import settings

_exporter_initialized = False
_exporter = None


def setup_telemetry() -> None:
    """初始化 OpenTelemetry 导出器"""
    global _exporter_initialized, _exporter
    
    if _exporter_initialized:
        return
    
    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry is disabled")
        _exporter_initialized = True
        return
    
    exporter_type = settings.OTEL_EXPORTER.lower()
    
    try:
        if exporter_type == "console":
            _setup_console_exporter()
        elif exporter_type == "jaeger":
            _setup_jaeger_exporter()
        elif exporter_type == "otlp":
            _setup_otlp_exporter()
        else:
            logger.warning(f"Unknown OTEL_EXPORTER type: {exporter_type}, using console")
            _setup_console_exporter()
        
        _exporter_initialized = True
        logger.info(f"OpenTelemetry exporter initialized: type={exporter_type}")
        
    except ImportError as e:
        logger.warning(f"Failed to setup OTEL exporter: {e}. Falling back to console.")
        _setup_console_exporter()
        _exporter_initialized = True
    except Exception as e:
        logger.error(f"Failed to setup OTEL exporter: {e}")
        _setup_console_exporter()
        _exporter_initialized = True


def _setup_console_exporter() -> None:
    """设置 Console 导出器"""
    global _exporter
    _exporter = ConsoleExporter()


def _setup_jaeger_exporter() -> None:
    """设置 Jaeger 导出器"""
    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        
        jaeger_exporter = JaegerExporter(
            agent_host_name=settings.OTEL_JAEGER_AGENT_HOST,
            agent_port=settings.OTEL_JAEGER_AGENT_PORT,
        )
        global _exporter
        _exporter = JaegerExporterWrapper(jaeger_exporter)
    except ImportError:
        logger.warning("Jaeger exporter not available, falling back to console")
        _setup_console_exporter()


def _setup_otlp_exporter() -> None:
    """设置 OTLP 导出器"""
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_OTLP_ENDPOINT,
            insecure=True,
        )
        global _exporter
        _exporter = OTLPSpanExporterWrapper(otlp_exporter)
    except ImportError:
        logger.warning("OTLP exporter not available, falling back to console")
        _setup_console_exporter()


def shutdown_telemetry() -> None:
    """关闭 OpenTelemetry"""
    global _exporter_initialized
    
    if _exporter and hasattr(_exporter, 'shutdown'):
        try:
            _exporter.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down OTEL exporter: {e}")
    
    _exporter_initialized = False


def get_exporter():
    """获取导出器实例"""
    global _exporter
    if not _exporter:
        setup_telemetry()
    return _exporter


class ConsoleExporter:
    """Console 导出器 - 将链路日志输出到控制台"""
    
    def export(self, span_data):
        """导出 span 数据到控制台"""
        import json
        from datetime import datetime
        
        span_dict = span_data.to_dict() if hasattr(span_data, 'to_dict') else span_data
        print(f"\n{'='*60}")
        print(f"[TRACE] {span_dict.get('name', 'unknown')}")
        print(f"{'='*60}")
        print(f"  Trace ID:    {span_dict.get('trace_id', 'N/A')}")
        print(f"  Span ID:     {span_dict.get('span_id', 'N/A')}")
        print(f"  Parent ID:   {span_dict.get('parent_span_id', 'N/A')}")
        print(f"  Service:     {span_dict.get('service_name', 'N/A')}")
        print(f"  Start Time: {span_dict.get('start_time', 'N/A')}")
        print(f"  Duration:   {span_dict.get('duration_ms', 0):.2f}ms")
        print(f"  Status:     {span_dict.get('status', 'OK')}")
        
        attrs = span_dict.get('attributes', {})
        if attrs:
            print(f"  Attributes:")
            for k, v in attrs.items():
                print(f"    - {k}: {v}")
        
        events = span_dict.get('events', [])
        if events:
            print(f"  Events:")
            for e in events:
                print(f"    - [{e.get('timestamp', '')}] {e.get('name', '')}")
        
        children = span_dict.get('children', [])
        if children:
            print(f"  Children: {len(children)}")
        
        print(f"{'='*60}\n")
    
    def shutdown(self):
        """关闭导出器"""
        pass


class JaegerExporterWrapper:
    """Jaeger 导出器包装器"""
    
    def __init__(self, exporter):
        self._exporter = exporter
    
    def export(self, span_data):
        """导出到 Jaeger"""
        try:
            self._exporter.export([span_data])
        except Exception as e:
            logger.error(f"Failed to export to Jaeger: {e}")
    
    def shutdown(self):
        """关闭导出器"""
        if self._exporter:
            self._exporter.shutdown()


class OTLPSpanExporterWrapper:
    """OTLP 导出器包装器"""
    
    def __init__(self, exporter):
        self._exporter = exporter
    
    def export(self, span_data):
        """导出到 OTLP"""
        try:
            self._exporter.export([span_data])
        except Exception as e:
            logger.error(f"Failed to export to OTLP: {e}")
    
    def shutdown(self):
        """关闭导出器"""
        if self._exporter:
            self._exporter.shutdown()
