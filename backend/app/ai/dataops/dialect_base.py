"""方言适配器协议与数据类（P2 Task 3）。

服务层不感知方言：所有元数据读取 / 画像 / 只读取样 / dry-run 都经由本协议。
标识符引用统一走 SQLAlchemy dialect.identifier_preparer.quote()，
禁止手写反引号/双引号（spec 6.2）。

PG 注意：information_schema 无注释列，表/列注释必须从 pg_catalog
（obj_description / col_description）取。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class TableMeta:
    """表级元数据（list_tables 行）。"""

    name: str
    table_type: str = "BASE TABLE"       # BASE TABLE | VIEW | ...
    comment: Optional[str] = None
    row_count: Optional[int] = None      # 近似值（pg_class.reltuples）
    engine: Optional[str] = None         # PG 无引擎概念，留空；MySQL 为 InnoDB 等
    column_count: Optional[int] = None


@dataclass
class ColumnMeta:
    """列级元数据（list_columns 行）。"""

    name: str
    ordinal: int
    data_type: str                        # 归一化类型（integer/varchar/...）
    column_type: str = ""                 # 完整类型定义（varchar(32) 等）
    nullable: bool = True
    column_key: Optional[str] = None      # PRI/UNI/MUL（MySQL 语义；PG 仅推 PRI）
    column_default: Optional[str] = None
    extra: Optional[str] = None           # auto_increment 等
    comment: Optional[str] = None


@dataclass
class ColumnProfile:
    """列画像结果（spec 6.3：只存结果不存样本）。"""

    total: int = 0
    non_null: int = 0
    distinct_count: int = 0
    null_rate: float = 0.0
    distinct_ratio: float = 0.0
    min_value: Optional[str] = None       # 数值/日期时间型
    max_value: Optional[str] = None
    top_values: List[Dict[str, Any]] = field(default_factory=list)  # 非数值型 Top-10


@dataclass
class QueryResult:
    """只读取样结果。"""

    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False               # 是否被行数上限截断


@dataclass
class ColRef:
    """列引用（overlap_ratio 的左右两列）。"""

    table: str
    column: str


@dataclass
class WriteImpact:
    """写操作 dry-run 影响预估（spec 7.3）。"""

    statement_type: str                   # update|delete|insert|ddl
    estimated_rows: Optional[int] = None  # EXPLAIN 估算行数（取不到为 None）
    detail: str = ""


@runtime_checkable
class DialectAdapter(Protocol):
    """方言适配器协议（spec 6.1；类型体系扩展后增 open/test_connect）。"""

    name: str

    def open(self, ds, connect_database: Optional[str] = None) -> tuple:
        """打开连接，返回 (conn_handle, cleanup)；cleanup 为无参关闭函数。

        ``ds`` 为 DataSource ORM 对象（密码由服务层先行解密后传入 ds._password_plain
        临时属性，避免适配器层触碰 password_enc）。

        ``connect_database``：PG 族跨物理库浏览时的连接目标覆盖（选另一个库时传入）；
        缺省连 ds.database。非 SQLAlchemy 族（dm/es）忽略。
        """
        ...

    def list_schemas(self, conn) -> List[str]:
        """当前连接库内的 schema 清单（仅 PG 族实现；其余族无 schema 概念）。"""
        ...

    def test_connect(self, ds) -> tuple[bool, Optional[str]]:
        """探活：返回 (ok, error)；error 为用户可读的失败原因（含驱动未安装指引）。"""
        ...

    def list_databases(self, conn) -> List[str]: ...
    def list_tables(self, conn, database: str) -> List[TableMeta]: ...
    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]: ...
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile: ...
    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float: ...
    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult: ...
    def dry_run(self, conn, sql: str) -> WriteImpact: ...
