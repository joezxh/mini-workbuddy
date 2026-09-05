# -*- coding: utf-8 -*-
"""智能体团队运行的错误归一化。

团队运行依赖底层模型的 native function calling。当底层模型服务未开启自动工具调用时，
会以 400 拒绝。本模块把这类报错归一为前端可读、且带可操作配置提示的文案。
"""
from __future__ import annotations


def render_team_error(exc: Exception) -> str:
    """将团队运行异常渲染为前端可读的提示。"""
    err_msg = str(exc)
    if (
        "tool_choice" in err_msg
        or "tool-call-parser" in err_msg
        or "enable-auto-tool-choice" in err_msg
    ):
        return (
            "团队运行失败：当前模型服务未开启自动工具调用。"
            "请使用支持 function calling 的模型，或启动模型服务时带上 "
            "--enable-auto-tool-choice --tool-call-parser <解析器> "
            "(如 qwen 系列用 hermes) 后重试。"
        )
    return err_msg
