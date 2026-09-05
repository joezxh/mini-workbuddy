"""OpenTelemetry Tracer 核心实现"""
import functools
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional

from loguru import logger

from app.config import settings

_tracer_instance = None
_initialized = False


class Span:
    """简单的 Span 实现，用于链路记录"""
    
    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
        service_name: str = None,
    ):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.service_name = service_name or settings.OTEL_SERVICE_NAME
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.status: str = "OK"
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.children: List["Span"] = []
    
    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        })
    
    def set_status(self, status: str) -> None:
        self.status = status
    
    def record_exception(self, exception: Exception) -> None:
        self.attributes["exception.type"] = type(exception).__name__
        self.attributes["exception.message"] = str(exception)
        self.status = "ERROR"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "children": [c.to_dict() for c in self.children],
        }
    
    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


class SpanContext:
    """当前 Span 上下文"""
    
    def __init__(self):
        self._stack: List[Span] = []
    
    def push(self, span: Span) -> None:
        self._stack.append(span)
    
    def pop(self) -> Optional[Span]:
        return self._stack.pop() if self._stack else None
    
    def current(self) -> Optional[Span]:
        return self._stack[-1] if self._stack else None
    
    def root(self) -> Optional[Span]:
        return self._stack[0] if self._stack else None


_span_context = SpanContext()


def _generate_trace_id() -> str:
    return uuid.uuid4().hex[:32].upper()


def _generate_span_id() -> str:
    return uuid.uuid4().hex[:16].upper()


def setup_tracer() -> "Tracer":
    """初始化 Tracer"""
    global _tracer_instance, _initialized
    
    if _initialized:
        return _tracer_instance
    
    _tracer_instance = Tracer()
    _initialized = True
    logger.info(f"OpenTelemetry Tracer initialized: service={settings.OTEL_SERVICE_NAME}")
    return _tracer_instance


def get_tracer() -> "Tracer":
    """获取 Tracer 实例"""
    global _tracer_instance
    if not _initialized:
        return setup_tracer()
    return _tracer_instance


class Tracer:
    """AgentScope 追踪器"""
    
    def __init__(self):
        self.service_name = settings.OTEL_SERVICE_NAME
        self._all_spans: List[Span] = []
    
    def start_span(
        self,
        name: str,
        parent_span: Optional[Span] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """开始一个新的 Span"""
        parent = parent_span or _span_context.current()
        trace_id = parent.trace_id if parent else _generate_trace_id()
        parent_span_id = parent.span_id if parent else None
        
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=_generate_span_id(),
            parent_span_id=parent_span_id,
            service_name=self.service_name,
        )
        span.start_time = datetime.utcnow()
        
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        
        if parent:
            parent.children.append(span)
        
        _span_context.push(span)
        self._all_spans.append(span)
        
        return span
    
    def end_span(self, span: Span, status: str = "OK") -> None:
        """结束一个 Span"""
        span.end_time = datetime.utcnow()
        span.set_status(status)
        _span_context.pop()
    
    def get_current_span(self) -> Optional[Span]:
        """获取当前 Span"""
        return _span_context.current()
    
    def get_root_span(self) -> Optional[Span]:
        """获取根 Span"""
        return _span_context.root()
    
    def get_all_spans(self) -> List[Span]:
        """获取所有记录过的 Span"""
        return self._all_spans
    
    def get_trace(self, trace_id: str) -> List[Span]:
        """根据 trace_id 获取整条链路"""
        return [s for s in self._all_spans if s.trace_id == trace_id]
    
    def clear(self) -> None:
        """清空所有 Span（用于测试）"""
        self._all_spans.clear()


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[Span, None, None]:
    """创建 Span 的上下文管理器"""
    tracer = get_tracer()
    span = tracer.start_span(name, attributes=attributes)
    try:
        yield span
    except Exception as e:
        span.record_exception(e)
        tracer.end_span(span, status="ERROR")
        raise
    else:
        tracer.end_span(span)


def trace_async(name: Optional[str] = None):
    """异步函数的装饰器"""
    def decorator(func: Callable) -> Callable:
        _name = name or f"{func.__module__}.{func.__qualname__}"
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with create_span(_name) as span:
                span.set_attribute("function", func.__qualname__)
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator


def trace_sync(name: Optional[str] = None):
    """同步函数的装饰器"""
    def decorator(func: Callable) -> Callable:
        _name = name or f"{func.__module__}.{func.__qualname__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with create_span(_name) as span:
                span.set_attribute("function", func.__qualname__)
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator


def get_current_span() -> Optional[Span]:
    """获取当前 Span"""
    return _span_context.current()


def get_trace_id() -> Optional[str]:
    """获取当前 Trace ID"""
    span = _span_context.current()
    if span:
        return span.trace_id
    return None


def get_span_id() -> Optional[str]:
    """获取当前 Span ID"""
    span = _span_context.current()
    if span:
        return span.span_id
    return None
