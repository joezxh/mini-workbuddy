"""数据源 → 连接构造（P2 Task 7/9/10 共用；类型体系扩展后按 family 分发）。

约定：
- ``database`` 为**连接级**库名（PG 的 database / MySQL 的 schema / Oracle 的
  service_name|SID）；schema/命名空间（PG 搜索路径、SQLServer/达梦的 dbSchema、
  Kingbase schema）由 ``config["dbSchema"]`` 传入扫描动作。
- ``config`` 为 ``DataSource.config_json``（类型特有参数，永不含密码）。
- 专有驱动（dmPython / elasticsearch）**懒加载**：未安装时抛出带安装指引的
  明确错误，不阻塞应用启动与其他类型。
- excel 类型不建外部连接：文件已落本系统 PG 独立 schema，连接即后台自身引擎。
- 凭据从已解密字段传入，本模块**不**触碰 ``password_enc``。
"""
from __future__ import annotations

from urllib.parse import quote_plus
from typing import Any, Dict, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

#: item_code → 连接族（与 services/dataops/source_types.TYPE_META 的 family 一致；
#: 字典项 extra_data.family 若配置则以字典为准，此处为内置映射）
FAMILY_BY_TYPE: Dict[str, str] = {
    "mysql": "mysql", "doris": "mysql", "starrocks": "mysql",
    "postgresql": "pg", "kingbase": "pg", "excel": "excel",
    "oracle": "oracle", "sqlserver": "sqlserver", "clickhouse": "clickhouse",
    "dm": "dm", "es": "es",
}

_SQLALCHEMY_URLS = {
    "mysql": "mysql+pymysql",
    "pg": "postgresql+psycopg2",
    "oracle": "oracle+oracledb",
    "sqlserver": "mssql+pymssql",
    "clickhouse": "clickhouse+http",
}


class DriverMissingError(RuntimeError):
    """专有驱动未安装：消息即用户可见的安装指引。"""


def resolve_family(source_type: str) -> str:
    fam = FAMILY_BY_TYPE.get((source_type or "").lower().strip())
    if fam is None:
        raise ValueError(f"不支持的数据源类型 {source_type!r}")
    return fam


def build_engine(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    database: str | None,
    *,
    config: Optional[Dict[str, Any]] = None,
    connect_timeout: int = 10,
) -> Engine:
    """按数据源类型（SQLAlchemy 族）构造 Engine；非 SQLAlchemy 族显式失败。"""
    config = config or {}
    fam = resolve_family(source_type)
    if fam == "excel":
        # excel 落本系统 PG：直接复用后台引擎（不另建连接池）
        from app.db.database import engine as _system_engine
        return _system_engine
    if fam in ("dm", "es"):
        raise ValueError(f"{source_type} 不走 SQLAlchemy，请使用 open_connection()")

    user = quote_plus(username or "")
    pwd = quote_plus(password or "")
    db = quote_plus(database or "")
    timeout = int(config.get("timeout") or connect_timeout)
    connect_args: Dict[str, Any] = {}

    if fam == "mysql":
        url = f"{_SQLALCHEMY_URLS[fam]}://{user}:{pwd}@{host}:{port}/{db}"
        # Doris/StarRocks 默认客户端常无 TLS（对齐 SQLBot：ssl_disabled）
        ssl_cfg = config.get("ssl") or ("disabled" if source_type.lower() in ("doris", "starrocks") else None)
        connect_args = {"connect_timeout": timeout, "ssl": None if ssl_cfg == "disabled" else {}}
    elif fam == "pg":
        url = f"{_SQLALCHEMY_URLS[fam]}://{user}:{pwd}@{host}:{port}/{db}"
        connect_args = {"connect_timeout": timeout}
        if config.get("dbSchema"):
            import urllib.parse as _up
            connect_args["options"] = f"-c search_path={_up.quote(config['dbSchema'])}"
    elif fam == "oracle":
        if (config.get("mode") or "service_name") == "service_name":
            url = f"{_SQLALCHEMY_URLS[fam]}://{user}:{pwd}@{host}:{port}?service_name={db}"
        else:  # SID 形态走 TNS 描述符
            url = (f"{_SQLALCHEMY_URLS[fam]}://{user}:{pwd}@"
                   f"(description=(address=(host={host})(port={port}))"
                   f"(connect_data=(sid={database or ''})))")
    elif fam == "sqlserver":
        url = f"{_SQLALCHEMY_URLS[fam]}://{user}:{pwd}@{host}:{port}/{db}"
        connect_args = {"timeout": timeout, "tds_version": config.get("tdsVersion", "7.0")}
    else:  # clickhouse
        url = f"{_SQLALCHEMY_URLS[fam]}://{user}:{pwd}@{host}:{port}/{db}"

    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=4,
                         connect_args=connect_args)


def _dm_connect(host: str, port: int, username: str | None, password: str | None,
                database: str | None, config: Dict[str, Any]):
    try:
        import dmPython  # type: ignore
    except ImportError as exc:
        raise DriverMissingError(
            "达梦驱动 dmPython 未安装：请执行 pip install dmPython，"
            "或从达梦安装目录 drivers/python 安装对应版本"
        ) from exc
    kwargs: Dict[str, Any] = {
        "user": username or "", "password": password or "",
        "server": host, "port": int(port),
    }
    if database:
        kwargs["schema"] = database
    for k, v in (config.get("extra") or {}).items():
        kwargs[k] = v
    return dmPython.connect(**kwargs)


def _es_client(host: str, port: int, username: str | None, password: str | None,
               config: Dict[str, Any]):
    try:
        from elasticsearch import Elasticsearch  # type: ignore
    except ImportError as exc:
        raise DriverMissingError(
            "Elasticsearch 客户端未安装：请执行 pip install elasticsearch"
        ) from exc
    scheme = config.get("scheme") or "http"
    kwargs: Dict[str, Any] = {"request_timeout": int(config.get("timeout") or 10)}
    if username:
        kwargs["basic_auth"] = (username, password or "")
    return Elasticsearch([f"{scheme}://{host}:{port}"], **kwargs)


def open_connection(source_type: str, host: str, port: int, username: str | None,
                    password: str | None, database: str | None,
                    *, config: Optional[Dict[str, Any]] = None):
    """打开连接：SQLAlchemy 族返回 Connection；dm/es 返回原生句柄；excel 返回系统库 Connection。

    调用方负责关闭（推荐 with 语境，dm/es 对象支持 contextlib 协议或显式 close）。
    """
    config = config or {}
    fam = resolve_family(source_type)
    if fam in ("dm", "es"):
        return _dm_connect(host, port, username, password, database, config) if fam == "dm" \
            else _es_client(host, port, username, password, config)
    engine = build_engine(source_type, host, port, username, password, database, config=config)
    return engine.connect(), engine
