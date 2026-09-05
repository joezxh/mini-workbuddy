"""OpenTelemetry Context 传播器"""
import json
from typing import Any, Dict, Optional

from app.ai.telemetry.tracer import _span_context, get_trace_id, get_span_id


TRACE_CONTEXT_HEADER = "x-trace-context"


def inject_context() -> Dict[str, str]:
    """将当前上下文注入到 HTTP headers"""
    trace_id = get_trace_id()
    span_id = get_span_id()
    
    if trace_id and span_id:
        context = {
            "trace_id": trace_id,
            "span_id": span_id,
        }
        return {
            TRACE_CONTEXT_HEADER: json.dumps(context),
        }
    return {}


def extract_context(headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """从 HTTP headers 中提取上下文"""
    context_str = headers.get(TRACE_CONTEXT_HEADER) or headers.get(TRACE_CONTEXT_HEADER.lower())
    
    if context_str:
        try:
            return json.loads(context_str)
        except json.JSONDecodeError:
            pass
    
    return None


def create_child_context(trace_id: str, span_id: str) -> Dict[str, str]:
    """创建子上下文"""
    return {
        "trace_id": trace_id,
        "span_id": span_id,
    }
