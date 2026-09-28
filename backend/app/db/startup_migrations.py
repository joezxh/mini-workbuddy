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
    # 2026-09-27 知识库统一化（spec §3.2）：kms_category → 通用分类容器 kb_category
    "kms_category": "kb_category",
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
    # 注：kms_category 已重命名为 kb_category（见 _TABLE_RENAME_MAP），此处同步改名
    "ALTER TABLE kb_category ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kb_category_knowledge_id ON kb_category (knowledge_id)",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_article_knowledge_id ON kms_article (knowledge_id)",
    "ALTER TABLE kms_search_log ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_search_log_knowledge_id ON kms_search_log (knowledge_id)",
    # ── 2026-09-27 知识库统一化（spec §3 / §10.2）───────────────────────────
    # 统一容器类型与二级形态
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS type INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS kb_format VARCHAR(16)",
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS multimodal_enabled BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS index_mode VARCHAR(16) NOT NULL DEFAULT 'high_quality'",
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS pipeline_config JSONB",
    "CREATE INDEX IF NOT EXISTS idx_kms_knowledge_tenant_type ON kms_knowledge (tenant_id, type)",
    # 分类容器冗余类型（RENAME 后回填；仅补空值，重复执行安全）
    "ALTER TABLE kb_category ADD COLUMN IF NOT EXISTS kb_type INTEGER",
    "UPDATE kb_category c SET kb_type = k.type FROM kms_knowledge k "
    "WHERE c.knowledge_id = k.id AND c.kb_type IS NULL",
    # kb_* 三表由迁移 006 独占建表，create_all 不加列，故在此补齐
    "ALTER TABLE kb_collection ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS idx_kb_collection_knowledge ON kb_collection (knowledge_id)",
    "ALTER TABLE kb_collection ADD COLUMN IF NOT EXISTS schema_config JSONB",
    "ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(16) NOT NULL DEFAULT 'text'",
    "ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS parent_id BIGINT",
    "CREATE INDEX IF NOT EXISTS idx_kb_segment_parent ON kb_segment (parent_id)",
    "ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS answer TEXT",
    "ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS keywords JSONB",
    # OKF 合规层（spec §9.2）：文章溯源/验证/过期字段
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS okf_type VARCHAR(64)",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS resource VARCHAR(500)",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS sources JSONB",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS verified JSONB",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS stale_after TIMESTAMP",
    # 版本快照：operation_type 缺失会让建/改文章直接 TypeError，summary/owl_class_uris 供回滚还原
    "ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS operation_type VARCHAR(32)",
    "ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS summary VARCHAR(1000)",
    "ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS owl_class_uris JSONB",
]


def add_new_columns(engine: Engine) -> None:
    """补齐后加列（幂等）。"""
    with engine.begin() as conn:
        for sql in _COLUMN_MIGRATIONS:
            conn.execute(text(sql))


# ── 索引迁移（幂等；Phase 3 T1）──────────────────────────────────────────
# 每项依次尝试执行，任一项失败仅告警不阻断启动（索引属性能优化，非正确性依赖）。
_INDEX_MIGRATIONS: list[str] = [
    # kb_segment 向量列：默认暴力 KNN → HNSW（m=16, ef_construction=64，P95 < 100ms）
    "CREATE INDEX IF NOT EXISTS idx_kb_segment_embedding_hnsw ON kb_segment "
    "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)",
    # 中文子串检索（pg_trgm）供混合检索关键词分支
    "CREATE INDEX IF NOT EXISTS idx_kb_segment_content_trgm ON kb_segment "
    "USING gin (content gin_trgm_ops)",
    # wiki 文章向量（kms_article.content_vector）
    "CREATE INDEX IF NOT EXISTS idx_kms_article_vector_hnsw ON kms_article "
    "USING hnsw (content_vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)",
]


def create_performance_indexes(engine: Engine) -> None:
    """创建/补齐性能索引（幂等）；失败仅告警。"""
    with engine.begin() as conn:
        for sql in _INDEX_MIGRATIONS:
            try:
                conn.execute(text(sql))
            except Exception as exc:  # noqa: BLE001 - 索引失败不阻断启动
                logger.warning(f"索引创建跳过（不影响正确性）: {exc}")
