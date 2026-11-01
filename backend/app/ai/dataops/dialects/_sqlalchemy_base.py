"""SQLAlchemy 族适配器共用能力：open / test_connect（类型体系扩展新增）。

mysql / doris / starrocks / kingbase / postgresql / oracle / sqlserver /
clickhouse / excel 均经由 SQLAlchemy 连接；dm/es 为原生驱动族，各自实现。
"""
from __future__ import annotations

from sqlalchemy import literal as _sa_literal, text as _text

from typing import Optional, Tuple


class SQLAlchemyProbeMixin:
    #: 探活语句，子类按方言覆盖（oracle/dm 需 FROM DUAL 类语法）
    probe_sql: str = "SELECT 1"

    def open(self, ds, connect_database: Optional[str] = None) -> Tuple[object, callable]:
        """打开连接：返回 (Connection, cleanup)。ds 见 DialectAdapter.open 约定。

        ``connect_database``：PG 族跨物理库浏览时的连接目标覆盖（导入向导选了另一个
        库时由服务层传入）；缺省仍连数据源自身配置的 ``ds.database``。
        非 PG 族/原生驱动族忽略此参数。"""
        from app.ai.dataops.connection import FAMILY_BY_TYPE, build_engine

        engine = build_engine(
            self.name if getattr(ds, "source_type", None) is None else ds.source_type,
            ds.host, ds.port, ds.username,
            getattr(ds, "_password_plain", None),
            connect_database or ds.database,
            config=getattr(ds, "config_json", None) or {},
        )
        conn = engine.connect()
        # excel 族复用后台系统引擎：只关连接、绝不可 dispose 系统池
        if FAMILY_BY_TYPE.get((getattr(ds, "source_type", "") or "").lower().strip()) == "excel":
            return conn, (lambda: conn.close())
        return conn, (lambda: _close(conn, engine))

    def test_connect(self, ds) -> Tuple[bool, Optional[str]]:
        try:
            conn, cleanup = self.open(ds)
            try:
                conn.execute(_text(self.probe_sql))
            finally:
                cleanup()
            return True, None
        except Exception as exc:  # noqa: BLE001 - 探活失败原因原样回传用户
            return False, f"{type(exc).__name__}: {exc}"[:500]

    def probe_table(self, ds, database: Optional[str], table_name: str) -> Tuple[bool, Optional[str]]:
        """表级可读性探活（AF-06）：SELECT 1 FROM <t> LIMIT 1。

        标识符由 SQLAlchemy core 自动按方言加引号，LIMIT 方言改写（Oracle/DM 自动
        FETCH FIRST）免特判；``open`` 失败向上抛，由服务层归因 SOURCE_UNREACHABLE。"""
        from sqlalchemy import select as _sa_select, table as _sa_table

        conn, cleanup = self.open(ds, connect_database=database)
        try:
            conn.execute(_sa_select(_sa_literal(1)).select_from(_sa_table(table_name)).limit(1))
        except Exception as exc:  # noqa: BLE001 - 表不可读原因原样回传
            return False, f"{type(exc).__name__}: {exc}"[:500]
        finally:
            cleanup()
        return True, None


def _close(conn, engine) -> None:
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass
