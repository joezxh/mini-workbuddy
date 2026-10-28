"""数据源类型元数据（字典 ``data_source_type`` 的 seed 源 + 后端兜底）。

设计（对齐 SQLBot ``apps/db/constant.py`` 的 DB 枚举，但取值以后端字典为准）：
- 类型的**合法性**以 ``sys_dictionary_item``（dict_code=data_source_type，
  is_active 且未删除）为准，管理员可在「系统管理 → 数据字典」增删类型；
- 本模块的 ``TYPE_META`` 是**内置种子**：① 迁移 seed 的数据源；② 字典表为空/
  不可用时的兜底集合（仿 app/ai/skills/categories.py 的降级策略）；
- 字典项 ``extra_data`` 可覆盖此处的 family/default_port/fields（增量优先）。

family 决定连接构建与方言适配器分派（dialects/registry.py 的注册 key）：
- mysql:   SQLAlchemy mysql+pymysql（MySQL/Doris/StarRocks 同协议）
- pg:      SQLAlchemy postgresql+psycopg2（PostgreSQL/Kingbase 同协议，PG 系）
- oracle:  SQLAlchemy oracle+oracledb（thin mode，config.mode=service_name|sid）
- sqlserver: SQLAlchemy mssql+pymssql
- clickhouse: SQLAlchemy clickhouse+http
- dm:      dmPython 原生连接（懒加载，未安装时探活返回安装指引）
- es:      elasticsearch-py 客户端（懒加载）
- excel:   文件上传落本系统 PG 独立 schema，连接即指向后台自身库

fields 为前端动态表单声明（label_key 走 i18n，缺 label_key 用 label 兜底）：
type ∈ string|number|select|switch；when 表示条件显示（值为等值匹配）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DICT_CODE_DATA_SOURCE_TYPE = "data_source_type"

#: 公共连接字段（所有 connection 类型都带，excel 除外）
_COMMON_FIELDS: List[Dict[str, Any]] = [
    {"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": True},
    {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": True},
    {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"},
    {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"},
    {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"},
]

_TIMEOUT_FIELD = {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}

#: 内置 11 类（item_code 与 dialects/registry 注册 key 对齐）
TYPE_META: Dict[str, Dict[str, Any]] = {
    "excel": {
        "item_name": "Excel/CSV", "color": "green", "sort": 1,
        "family": "excel", "default_port": None,
        "fields": [
            {"key": "filename", "label_key": "kbMgmt.ds.excelFile", "type": "upload", "required": True},
        ],
    },
    "mysql": {
        "item_name": "MySQL", "color": "blue", "sort": 2,
        "family": "mysql", "default_port": 3306,
        "fields": [*_COMMON_FIELDS,
                   {"key": "charset", "label_key": "kbMgmt.ds.charset", "type": "string", "default": "utf8mb4"},
                   _TIMEOUT_FIELD],
    },
    "oracle": {
        "item_name": "Oracle", "color": "red", "sort": 3,
        "family": "oracle", "default_port": 1521,
        "fields": [*_COMMON_FIELDS[:-1],
                   {"key": "mode", "label_key": "kbMgmt.ds.oracleMode", "type": "select",
                    "options": [{"value": "service_name", "label": "Service Name"},
                                {"value": "sid", "label": "SID"}], "default": "service_name"},
                   {"key": "database", "label_key": "kbMgmt.ds.oracleDb", "type": "string"},
                   _TIMEOUT_FIELD],
    },
    "postgresql": {
        "item_name": "PostgreSQL", "color": "geekblue", "sort": 4,
        "family": "pg", "default_port": 5432,
        "fields": [*_COMMON_FIELDS,
                   {"key": "dbSchema", "label_key": "kbMgmt.ds.dbSchema", "type": "string", "default": "public"},
                   _TIMEOUT_FIELD],
    },
    "sqlserver": {
        "item_name": "SQL Server", "color": "purple", "sort": 5,
        "family": "sqlserver", "default_port": 1433,
        "fields": [*_COMMON_FIELDS,
                   {"key": "dbSchema", "label_key": "kbMgmt.ds.dbSchema", "type": "string", "default": "dbo"},
                   _TIMEOUT_FIELD],
    },
    "clickhouse": {
        "item_name": "ClickHouse", "color": "gold", "sort": 6,
        "family": "clickhouse", "default_port": 8123,
        "fields": [*_COMMON_FIELDS, _TIMEOUT_FIELD],
    },
    "dm": {
        "item_name": "达梦", "color": "volcano", "sort": 7,
        "family": "dm", "default_port": 5236,
        "fields": [*_COMMON_FIELDS, _TIMEOUT_FIELD],
    },
    "doris": {
        "item_name": "Apache Doris", "color": "cyan", "sort": 8,
        "family": "mysql", "default_port": 9030,
        "fields": [*_COMMON_FIELDS, _TIMEOUT_FIELD],
    },
    "es": {
        "item_name": "ElasticSearch", "color": "lime", "sort": 9,
        "family": "es", "default_port": 9200,
        "fields": [
            {"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": True},
            {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": True},
            {"key": "scheme", "label_key": "kbMgmt.ds.esScheme", "type": "select",
             "options": [{"value": "http", "label": "HTTP"}, {"value": "https", "label": "HTTPS"}],
             "default": "http"},
            {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"},
            {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"},
            _TIMEOUT_FIELD,
        ],
    },
    "kingbase": {
        "item_name": "Kingbase", "color": "orange", "sort": 10,
        "family": "pg", "default_port": 54321,
        "fields": [*_COMMON_FIELDS,
                   {"key": "dbSchema", "label_key": "kbMgmt.ds.dbSchema", "type": "string", "default": "public"},
                   _TIMEOUT_FIELD],
    },
    "starrocks": {
        "item_name": "StarRocks", "color": "magenta", "sort": 11,
        "family": "mysql", "default_port": 9030,
        "fields": [*_COMMON_FIELDS, _TIMEOUT_FIELD],
    },
}


def builtin_types() -> List[str]:
    """内置类型全集（字典不可用时的兜底合法集）。"""
    return list(TYPE_META)


def meta_for(item_code: str) -> Optional[Dict[str, Any]]:
    return TYPE_META.get((item_code or "").lower().strip())


def seed_rows() -> List[Dict[str, Any]]:
    """迁移 seed 用：sys_dictionary_item 行（dict_code=data_source_type）。"""
    rows: List[Dict[str, Any]] = []
    for code, meta in TYPE_META.items():
        rows.append({
            "dict_code": DICT_CODE_DATA_SOURCE_TYPE,
            "item_code": code,
            "item_name": meta["item_name"],
            "item_value": code,
            "level": 1,
            "color": meta.get("color"),
            "sort_order": meta.get("sort", 0),
            "is_active": True,
            "extra_data": {"family": meta["family"], "default_port": meta.get("default_port"),
                           "fields": meta.get("fields", [])},
            "is_deleted": False,
        })
    return rows
