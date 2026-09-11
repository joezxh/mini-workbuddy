"""只读 SQL 白名单（P2 Task 8，**单一事实来源**）。

基于 sqlglot 取 AST 节点类型判断（不做正则拼凑）。规则：

- 仅允许**单条**查询语句：``SELECT``（含 CTE ``WITH``）/ ``UNION`` / ``EXCEPT`` /
  ``INTERSECT`` / ``EXPLAIN <查询>``（解包后按查询校验）；
- **拒绝注释**（``--`` / ``/* */``）：注释可隐藏注入语义，运维排错场景无合法用途；
- **拒绝一切写/命令类节点**：INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/
  COPY/CALL/SET/... 以及 ``SELECT ... INTO``；
- **拒绝危险函数**：``pg_sleep`` / ``sleep`` / ``benchmark`` / 文件与 dblink 系列；
- 解析失败一律拒绝（fail-closed）。

P2 Task 14 的 ``PermissionRule`` 与 REST 侧执行入口**必须复用本模块**，
不得另写一份白名单。
"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import expressions as exp

# 注释检测：sqlglot 会保留注释节点，直接在词法层拒绝更直观
_HAS_COMMENT = re.compile(r"--|/\*|\*/")

# 顶层允许的查询节点（CTE 由 Select.args["with"] 携带，无需单独处理）
_ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Except, exp.Intersect, exp.Subquery)

# 语法树任何位置都不允许出现的节点
# （按名称惰性取类：不同 sqlglot 版本的节点集合略有差异，缺省跳过）
_FORBIDDEN_NODE_NAMES = (
    "Command",
    "Insert",
    "Update",
    "Delete",
    "Drop",
    "Create",
    "Alter",
    "AlterTable",
    "TruncateTable",
    "Merge",
    "Grant",
    "Revoke",
    "Set",
    "Use",
    "Call",
    "Copy",
    "Into",
    "Attach",
    "LoadData",
    "Pragma",
    "Analyze",
    "VacuumTable",
)
_FORBIDDEN_NODES = tuple(
    t for t in (getattr(exp, n, None) for n in _FORBIDDEN_NODE_NAMES) if t is not None
)

# 危险函数黑名单：锁表/延时拖库/文件读写/跨库
_FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",
    "sleep",
    "benchmark",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    "dblink",
    "dblink_send_query",
    "copy",
    "load_file",
    "readfile",
    "sys_exec",
}


def _function_name(node) -> str:  # noqa: ANN001
    """提取函数调用名（小写）；非函数节点返回空串。"""
    if isinstance(node, exp.Anonymous):
        name = node.this
        return name.lower() if isinstance(name, str) else ""
    if isinstance(node, exp.Func):
        return node.sql_name().lower()
    return ""


class SqlGuard:
    """只读 SQL 白名单校验器。"""

    def is_readonly(self, sql: str, dialect: Optional[str] = None) -> bool:
        """判断 SQL 是否为单条只读查询；任何不确定情形一律 False。"""
        if not sql or not sql.strip():
            return False
        if _HAS_COMMENT.search(sql):
            return False

        try:
            parsed = sqlglot.parse(sql, dialect=dialect)
        except Exception:  # noqa: BLE001 - 解析失败 = 不认识 = 拒绝
            return False

        statements = [s for s in parsed if s is not None]
        if len(statements) != 1:
            return False

        node = statements[0]
        # EXPLAIN 被解析为 Command（this=EXPLAIN, expression=内层查询），解包复检
        if isinstance(node, exp.Command) and self._is_explain_command(node):
            inner = self._literal_text(node.args.get("expression"))
            if not inner:
                return False
            return self.is_readonly(inner.strip(), dialect=dialect)

        return self._validate_query(node)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _literal_text(value) -> str:  # noqa: ANN001
        """Command 的 this/expression 可能是 str 或 Literal 节点，统一取文本。"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(getattr(value, "name", "") or "")

    def _is_explain_command(self, node) -> bool:  # noqa: ANN001
        return self._literal_text(node.args.get("this")).strip().upper().startswith(
            "EXPLAIN"
        )

    def _validate_query(self, node) -> bool:  # noqa: ANN001
        if not isinstance(node, _ALLOWED_ROOTS):
            return False
        if node.args.get("into"):
            return False

        for sub in node.walk():
            if isinstance(sub, _FORBIDDEN_NODES):
                return False
            if _function_name(sub) in _FORBIDDEN_FUNCTIONS:
                return False
        return True
