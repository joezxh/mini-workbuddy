"""Doris 方言适配器入口（P2 Task 4）。

Doris 经 MySQL 协议通信，复用 ``mysql.MysqlAdapter`` 实现；本模块仅做再导出，
便于将来补充 Doris 特有覆盖（如 EXPLAIN 语法、系统库差异）。
"""
from __future__ import annotations

from app.ai.dataops.dialects.mysql import DorisAdapter

__all__ = ["DorisAdapter"]
