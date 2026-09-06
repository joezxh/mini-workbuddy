"""agentscope 2.x 消息工具 —— 统一 Msg 构造与文本抽取。

2.x 的两处关键契约（与旧版不兼容）：
- ``Msg`` 是 pydantic v2 模型，**不支持位置参数** ``Msg("user", text, "user")``；
- ``Msg.content`` 是 block 列表（``TextBlock`` 等），不再是裸字符串，
  直接当文本透传会把列表传下去。

全项目统一走本模块，避免各模块重复实现且实现分叉。
"""
from __future__ import annotations

from typing import Any, List


def text_msg(name: str, role: str, text: str):
    """构造纯文本 Msg。

    Args:
        name: 消息发送者名称。
        role: 角色（``user`` / ``assistant`` 等）。
        text: 文本内容。
    """
    from agentscope.message import Msg, TextBlock

    return Msg(name=name, role=role, content=[TextBlock(text=text)])


def text_of(msg: Any) -> str:
    """从 AgentScope 响应对象中安全抽取纯文本。

    兼容多种形态：str / Msg（content 为 block 列表）/ 带 ``.text`` 的对象。
    """
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg

    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if not text and isinstance(block, dict):
                text = block.get("text")
            if text:
                parts.append(str(text))
        if parts:
            return "".join(parts)

    text = getattr(msg, "text", None)
    return text if isinstance(text, str) else ""


__all__ = ["text_msg", "text_of"]
