"""Excel/CSV 数据源适配器（类型体系扩展：文件落本系统 PG 临时 schema）。

形态（P2 决策）：上传的 Excel/CSV 由服务层解析后写入**后台自身 PG** 的独立
schema（``excel_ds_<数据源id>``，与 SQLBot excel→PG 引擎同款思路），因此：

- 连接族为 ``excel``：``build_engine`` 直接返回系统引擎（不建外部连接池）；
- 元数据/画像/取样能力与 PostgreSQL 完全一致 → 继承 ``PostgresAdapter``；
- ``list_databases`` 只枚举本模块前缀的 excel schema，避免把系统 schema
  （public 等）暴露成"数据库"造成误选；
- schema 命名约定由本模块单源提供（``schema_name_for``），上传落库服务复用，
  保证「落库 ↔ 读取」两侧一致。
"""
from __future__ import annotations

from typing import List

from sqlalchemy import text as _text

from app.ai.dataops.dialects.postgres import PostgresAdapter

#: excel 落库 schema 前缀（与数据源 id 绑定；改名需同步历史数据源，勿轻动）
SCHEMA_PREFIX = "excel_ds_"


def schema_name_for(source_id: int | str) -> str:
    """数据源 → 落库 schema 名（服务层建表与本适配器扫描共用）。"""
    return f"{SCHEMA_PREFIX}{source_id}"


class ExcelPgAdapter(PostgresAdapter):
    """Excel/CSV 适配器（系统 PG 上的隔离 schema 族）。"""

    name = "excel"

    def list_databases(self, conn) -> List[str]:
        rows = conn.execute(
            _text(
                "SELECT n.nspname FROM pg_namespace n "
                "WHERE n.nspname LIKE :prefix ORDER BY n.nspname"
            ),
            {"prefix": f"{SCHEMA_PREFIX}%"},
        ).fetchall()
        return [r[0] for r in rows]
