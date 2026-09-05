"""内置演示 Tool - 用于工具测试端到端验证。"""
from __future__ import annotations
import json
from typing import Any, Dict


class EchoTool:
    """回显工具：原样返回输入，便于联调测试。"""
    name = "echo_tool"
    description = "回显输入参数，用于工具执行链路联调"

    def execute(self, message: str = "", **kwargs: Any) -> Dict[str, Any]:
        return {
            "echo": message,
            "received": kwargs,
        }


def demo_add(a: int = 0, b: int = 0) -> Dict[str, Any]:
    """两数相加演示函数。"""
    return {"a": a, "b": b, "sum": a + b}


def demo_upper(text: str = "") -> Dict[str, Any]:
    """字符串大写演示函数。"""
    return {"original": text, "upper": (text or "").upper()}
