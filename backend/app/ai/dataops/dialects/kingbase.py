"""Kingbase（人大金仓）适配器：PG 协议兼容，复用 Postgres 实现。

Kingbase ES 系列默认以 PG 兼容模式运行（psycopg2 可直连，pg_catalog /
information_schema 语义一致），故直接继承 ``PostgresAdapter``。
差异项（sys_ 前缀系统模式等）可在此子类微调。
"""
from __future__ import annotations

from app.ai.dataops.dialects.postgres import PostgresAdapter


class KingbaseAdapter(PostgresAdapter):
    """Kingbase 适配器（PG 协议族）。"""

    name = "kingbase"
