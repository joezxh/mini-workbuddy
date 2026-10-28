"""StarRocks 适配器（复用 MySQL 协议实现）。

StarRocks FE 兼容 MySQL 协议（默认 9030 端口），information_schema 语义与
MySQL 一致，故与 Doris 同法：直接继承 ``MysqlAdapter``，仅系统库过滤微调。
"""
from __future__ import annotations

from app.ai.dataops.dialects.mysql import MysqlAdapter

_SR_SYSTEM_DBS = {"information_schema", "mysql", "sys", "performance_schema", "_statistics_"}


class StarrocksAdapter(MysqlAdapter):
    """StarRocks 适配器（MySQL 协议族）。"""

    name = "starrocks"

    def list_databases(self, conn):
        rows = conn.exec_driver_sql("SHOW DATABASES").fetchall()
        names = [r[0] for r in rows]
        return [n for n in names if n.lower() not in _SR_SYSTEM_DBS]
