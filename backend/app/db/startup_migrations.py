"""启动期 SQL 迁移 —— 表名重命名 + 轻量列迁移。

从 ``app/main.py`` 的 ``lifespan()`` 中提取，使启动流程更清晰：
lifespan 只负责按序编排各初始化阶段，具体 SQL 细节集中在此文件。

所有操作均为幂等（``IF NOT EXISTS`` / 先检查再执行），重复运行安全。
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ── 表名重命名映射 ─────────────────────────────────────────────────────────
# 旧表 → 新表：仅在旧表存在且新表不存在时执行 ALTER TABLE RENAME。
_TABLE_RENAME_MAP: dict[str, str] = {
    # sys_ 前缀：用户与权限
    "user": "sys_user",
    "role": "sys_role",
    "user_role": "sys_user_role",
    "region": "sys_region",
    "menu": "sys_menu",
    "role_menu": "sys_role_menu",
    "audit_log": "sys_audit_log",
    "user_notification": "sys_user_notification",
    # sys_ 前缀：字典
    "dictionary": "sys_dictionary",
    "dictionary_item": "sys_dictionary_item",
    # ai_ 前缀
    "workspace": "ai_workspace",
    "web_search": "ai_web_search",
    "web_search_log": "ai_web_search_log",
    # sys_ 前缀：基础设施文件
    "infra_file": "sys_infra_file",
    "infra_file_content": "sys_infra_file_content",
    # ai_ 前缀：MCP / Tool
    "mcp_api_key": "ai_mcp_api_key",
    "mcp_client": "ai_mcp_client",
    "mcp_square_template": "ai_mcp_square_template",
    "tool_definition": "ai_tool_definition",
    "tool_group": "ai_tool_group",
    "tool_group_member": "ai_tool_group_member",
}


def rename_legacy_tables(engine: Engine) -> None:
    """将旧表名重命名为新命名规范（幂等）。"""
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    renamed = 0
    with engine.begin() as conn:
        for old, new in _TABLE_RENAME_MAP.items():
            if old in existing and new not in existing:
                conn.execute(text(f"ALTER TABLE {old} RENAME TO {new}"))
                logger.info(f"已重命名表: {old} → {new}")
                renamed += 1
    if renamed:
        logger.info(f"表名迁移完成（{renamed} 张表）")


# ── 轻量列迁移 ─────────────────────────────────────────────────────────────
# 每条 SQL 均为幂等（ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS）。
_COLUMN_MIGRATIONS: list[str] = [
    "ALTER TABLE agent_async_task ADD COLUMN IF NOT EXISTS execution_id VARCHAR(100)",
    "CREATE INDEX IF NOT EXISTS ix_agent_async_task_execution_id ON agent_async_task (execution_id)",
    "ALTER TABLE agent_scheduled_task ADD COLUMN IF NOT EXISTS skill_info TEXT",
    "ALTER TABLE sys_menu ADD COLUMN IF NOT EXISTS i18n_key VARCHAR(100)",
    # 知识库归属字段：category/article/search_log 补 knowledge_id
    "ALTER TABLE kms_category ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_category_knowledge_id ON kms_category (knowledge_id)",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_article_knowledge_id ON kms_article (knowledge_id)",
    "ALTER TABLE kms_search_log ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_search_log_knowledge_id ON kms_search_log (knowledge_id)",
]


def add_new_columns(engine: Engine) -> None:
    """补齐后加列（幂等）。"""
    with engine.begin() as conn:
        for sql in _COLUMN_MIGRATIONS:
            conn.execute(text(sql))
