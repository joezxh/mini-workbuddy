"""数据源 → SQLAlchemy Engine 构造（P2 Task 7/9/10 共用）。

约定：
- ``database`` 为**连接级**库名（PG 的 database / MySQL 的 schema）；
  schema/命名空间（PG 的搜索路径）由具体扫描动作另行传入。
- 凭据从已解密字段传入，本模块**不**触碰 ``password_enc``（解密在前置服务完成）。
- 连接带 ``connect_timeout`` 与 ``pool_pre_ping``，避免脏连接拖垮工作流。
"""
from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_DIALECT_DRIVER = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "doris": "mysql+pymysql",  # Doris 兼容 MySQL 协议（查询走 9030 端口）
}


def build_engine(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    database: str | None,
    *,
    connect_timeout: int = 10,
) -> Engine:
    """按数据源类型构造 SQLAlchemy Engine。"""
    driver = _DIALECT_DRIVER.get((source_type or "").lower().strip())
    if driver is None:
        raise ValueError(f"不支持的数据源类型 {source_type!r}")

    user = quote_plus(username or "")
    pwd = quote_plus(password or "")
    db = quote_plus(database or "")
    url = f"{driver}://{user}:{pwd}@{host}:{port}/{db}"

    if driver.startswith("postgresql"):
        connect_args = {"connect_timeout": connect_timeout}
    else:
        connect_args = {"connect_timeout": connect_timeout}

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=4,
        connect_args=connect_args,
    )
