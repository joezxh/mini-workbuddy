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
    # 2026-09-27 知识库统一化（spec §3.2）：kb_* 分类/检索表统一改名 kms_*
    "kb_category": "kms_category",
    "kb_collection": "kms_collection",
    "kb_segment": "kms_segment",
    "kb_ref": "kms_ref",
    "kb_document": "kms_document",
    "kb_segment_asset": "kms_segment_asset",
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
    # 表改名后，原 kb_ 索引名随表保留，需一并改名为 kms_（幂等；
    # 迁移 006 新建库已是 kms_ 名则 no-op；开发库旧索引名随之统一）
    "ALTER INDEX IF EXISTS idx_kb_category_slug RENAME TO idx_kms_category_slug",
    "ALTER INDEX IF EXISTS idx_kb_category_parent RENAME TO idx_kms_category_parent",
    "ALTER INDEX IF EXISTS idx_kb_segment_parent RENAME TO idx_kms_segment_parent",
    "ALTER INDEX IF EXISTS idx_kb_collection_knowledge RENAME TO idx_kms_collection_knowledge",
    "ALTER INDEX IF EXISTS ix_kb_category_knowledge_id RENAME TO ix_kms_category_knowledge_id",
    "ALTER INDEX IF EXISTS ix_kb_collection_knowledge_id RENAME TO ix_kms_collection_knowledge_id",
    "ALTER TABLE agent_async_task ADD COLUMN IF NOT EXISTS execution_id VARCHAR(100)",
    "CREATE INDEX IF NOT EXISTS ix_agent_async_task_execution_id ON agent_async_task (execution_id)",
    "ALTER TABLE agent_scheduled_task ADD COLUMN IF NOT EXISTS skill_info TEXT",
    "ALTER TABLE sys_menu ADD COLUMN IF NOT EXISTS i18n_key VARCHAR(100)",
    # 知识库归属字段：category/article/search_log 补 knowledge_id
    # 注：kb_category 已统一改名 kms_category（见 _TABLE_RENAME_MAP），此处同步改名
    "ALTER TABLE kms_category ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_category_knowledge_id ON kms_category (knowledge_id)",
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
    # 知识库所属类别（知识库管理）：引用 kms_category 树节点
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS category_id BIGINT",
    "CREATE INDEX IF NOT EXISTS idx_kms_knowledge_category ON kms_knowledge (category_id)",
    # 外部知识库平台绑定（spec 知识库管理）：仅 type=3/connector 时有值，
    # 与迁移 2026_10_18_0002_add_external_type 同义，此处用幂等 SQL 兜底
    # （AUTO_CREATE_TABLES 路径下 alembic 重放会因表已存在而失败，故在此补齐）
    "ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS external_type VARCHAR(32)",
    "CREATE INDEX IF NOT EXISTS ix_kms_knowledge_external_type ON kms_knowledge (external_type)",
    # 旧关系清理（2026-10-08）：分类不再归属知识库，移除 knowledge_id / kb_type
    "ALTER TABLE kms_category DROP COLUMN IF EXISTS knowledge_id",
    "ALTER TABLE kms_category DROP COLUMN IF EXISTS kb_type",
    # kms_* 检索表由迁移 006 独占建表，create_all 不加列，故在此补齐
    "ALTER TABLE kms_collection ADD COLUMN IF NOT EXISTS knowledge_id BIGINT",
    "CREATE INDEX IF NOT EXISTS idx_kms_collection_knowledge ON kms_collection (knowledge_id)",
    "ALTER TABLE kms_collection ADD COLUMN IF NOT EXISTS schema_config JSONB",
    # 检索设置面板（spec §10.5）：embedding/rerank 模型 + 检索参数
    "ALTER TABLE kms_collection ADD COLUMN IF NOT EXISTS retrieval_settings JSONB",
    # 外部代理调用方白名单（spec §10.6 引用与调用方管理）
    "ALTER TABLE kms_external_kb_endpoint ADD COLUMN IF NOT EXISTS allowed_callers JSONB",
    # 资产粗分类物化列（AF-01，Q1 裁决 B；与迁移 2026_11_01_0010 同义，AUTO_CREATE_TABLES 路径兜底）
    "ALTER TABLE meta_data_source ADD COLUMN IF NOT EXISTS external_type VARCHAR(32) NOT NULL DEFAULT 'other'",
    "ALTER TABLE meta_data_source DROP CONSTRAINT IF EXISTS ck_meta_data_source_external_type",
    "ALTER TABLE meta_data_source ADD CONSTRAINT ck_meta_data_source_external_type CHECK (external_type IN ('rdbms','tsdb','warehouse','graph','kv','vector','search','file','saas','other'))",
    "CREATE INDEX IF NOT EXISTS idx_meta_data_source_tenant_extype ON meta_data_source (tenant_id, external_type)",
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(16) NOT NULL DEFAULT 'text'",
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS parent_id BIGINT",
    "CREATE INDEX IF NOT EXISTS idx_kms_segment_parent ON kms_segment (parent_id)",
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS answer TEXT",
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS keywords JSONB",
    # 表格知识库多集合归属（spec §10.2）：kms_document 显式记录所属集合 ID
    # （按 ID 精确归属，替代仅按名称字符串 collection 推断）；普通文档库维持
    # kb_{knowledge_id} 1:1，该列可空以保证历史数据兼容。FK 由 alembic 迁移覆盖
    # 全新库，此处仅保证运行库（不走 alembic）补齐列/索引并回填历史文档。
    "ALTER TABLE kms_document ADD COLUMN IF NOT EXISTS collection_id BIGINT",
    "CREATE INDEX IF NOT EXISTS ix_kms_document_collection_id ON kms_document (collection_id)",
    # OKF 合规层（spec §9.2）：文章溯源/验证/过期字段
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS okf_type VARCHAR(64)",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS resource VARCHAR(500)",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS sources JSONB",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS verified JSONB",
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS stale_after TIMESTAMP",
    # OKF §10 Attested Computation 契约（spec §9.6 推迟项，本次补齐）
    "ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS attested_computation JSONB",
    # 版本快照：operation_type 缺失会让建/改文章直接 TypeError，summary/owl_class_uris 供回滚还原
    "ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS operation_type VARCHAR(32)",
    "ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS summary VARCHAR(1000)",
    "ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS owl_class_uris JSONB",
    # ── 2026-10-31 图谱知识库（type=4，spec §3.7）：切片两阶段状态机 ──────────
    # 阶段 1 结构写入（PG 事实 + Neo4j 投影）／阶段 2 向量索引；
    # 两阶段分离使得 Neo4j 或嵌入失败都能断点续跑，不必重复 LLM 抽取。
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS graph_structure_indexed BOOLEAN",
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS graph_indexed BOOLEAN",
    "ALTER TABLE kms_segment ADD COLUMN IF NOT EXISTS graph_extraction_details JSONB",
]


def add_new_columns(engine: Engine) -> None:
    """补齐后加列（幂等）。"""
    with engine.begin() as conn:
        for sql in _COLUMN_MIGRATIONS:
            conn.execute(text(sql))


# ── 默认集合行补齐 + 历史文档归属回填（幂等）──────────────────────────────
# 每个知识库都需存在默认集合 ``kb_{knowledge_id}``（普通文档 / Q&A 库的 1:1 集合），
# 否则「按 collection_id 反查」的接口无法解析。表格库上传未指定集合时自动新建
# ``kb_{kid}_{slug}``，但历史库 / 文档 / Q&A 库未必有该默认行，故在此兜底补齐；
# 随后把 ``kms_document.collection_id`` 按集合名回填，使文档↔集合关联走 id。
def ensure_default_collections(engine: Engine) -> None:
    """为缺失默认集合行的知识库补建 ``kb_{kid}``，并回填历史文档的 collection_id。"""
    from app.config import settings

    dim = int(getattr(settings, "GPUSTACK_EMBEDDING_DIMENSION", 768))
    with engine.begin() as conn:
        # 1) 为每个知识库补默认集合行（名称唯一，NOT EXISTS 防重复）
        conn.execute(text(
            "INSERT INTO kms_collection (tenant_id, name, dimensions, knowledge_id, created_at) "
            "SELECT k.tenant_id, 'kb_' || k.id::text, :dim, k.id, now() "
            "FROM kms_knowledge k "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM kms_collection c WHERE c.name = 'kb_' || k.id::text"
            ")"
        ), {"dim": dim})
        # 2) 回填：按 collection 名（kms_collection.name）反查 id（仅更新未归属行）
        conn.execute(text(
            "UPDATE kms_document AS d SET collection_id = c.id "
            "FROM kms_collection AS c "
            "WHERE d.collection_id IS NULL AND d.collection = c.name"
        ))


# ── 字典数据播种（幂等）──────────────────────────────────────────────────────
# SOP 助手模式（spec §4）作为独立会话类型落地，需在 session_type 字典中登记 sop
# 项，否则前端模式下拉（getDictionaryItems('session_type')）不会展示，用户无法进入。
# 仅插入 sop 一项；其余模式（general/thinking/...）由既有数据/管理后台维护。
_SESSION_TYPE_SEED: list[dict] = [
    {
        "item_code": "sop",
        "item_name": "SOP 流程",
        "item_value": "sop",
        "color": "purple",
        "sort_order": 90,
    },
]


def seed_session_type_dictionary(engine: Engine) -> None:
    """幂等登记 session_type 字典的 sop 项（重复运行安全）。"""
    with engine.begin() as conn:
        for item in _SESSION_TYPE_SEED:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM sys_dictionary_item "
                    "WHERE dict_code = 'session_type' AND item_code = :code"
                ),
                {"code": item["item_code"]},
            ).first()
            if exists:
                continue
            conn.execute(
                text(
                    "INSERT INTO sys_dictionary_item "
                    "(dict_code, item_code, item_name, item_value, color, "
                    " sort_order, is_active, is_deleted, tenant_id) "
                    "VALUES ('session_type', :code, :name, :value, :color, "
                    " :sort, true, false, 0)"
                ),
                {
                    "code": item["item_code"],
                    "name": item["item_name"],
                    "value": item["item_value"],
                    "color": item["color"],
                    "sort": item["sort_order"],
                },
            )
            logger.info(f"已登记 session_type 字典项: {item['item_code']}")


def seed_agent_impl_type_dictionary(engine: Engine) -> None:
    """幂等登记 agent_impl_type 字典的 SUPERAGENT 项（spec 步骤三 4.1）。

    agent_impl_type 字典本身由管理后台维护（无代码 seed），此处仅补 SUPERAGENT
    一项，保证 Agent 配置页能选到 SuperAgent 类型；其余项由既有数据维护。
    """
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM sys_dictionary_item "
                "WHERE dict_code = 'agent_impl_type' AND item_code = 'SUPERAGENT'"
            )
        ).first()
        if exists:
            return
        conn.execute(
            text(
                "INSERT INTO sys_dictionary_item "
                "(dict_code, item_code, item_name, item_value, color, remark, "
                " sort_order, is_active, is_deleted, tenant_id) "
                "VALUES ('agent_impl_type', 'SUPERAGENT', 'SuperAgent 引擎', 'SUPERAGENT', "
                " 'geekblue', 'SuperAgent 自主工单引擎（HITL/ReAct/MCP）', "
                " 90, true, false, 0)"
            )
        )
        logger.info("已登记 agent_impl_type 字典项: SUPERAGENT")


# ── SuperAgent 管理菜单播种（幂等；spec 步骤三 4.4）──────────────────────────
# 显示端整合后：左侧系统菜单只保留一个「超级智能体」入口，进入后用右侧顶部 3 Tab
# 切换工作台 / Muse 执行界面 / 管理界面。下方旧入口 path 由前端重定向，避免历史书签 404，
# 但不再作为菜单展示（seed 时置 visible=0）。
_SUPERAGENT_MENU = {
    # /admin/super-agent 经 resolveMenuTarget 转为 /dashboard?tab=super-agent，
    # 作为控制台外壳的 Tab 打开（path 末段 super-agent 即 componentMap 的 tab key）。
    "path": "/admin/super-agent", "name": "超级智能体", "icon": "RobotOutlined",
    "sort": 70, "i18n_key": "sys.menu.super-agent-home",
}
_SUPERAGENT_LEGACY_MENU_PATHS = [
    "/super-agent", "/super-agent/hitl", "/super-agent/config-source", "/super-agent/chat",
    "/super-agent/feed", "/super-agent/ideas", "/super-agent/goals",
]


def seed_superagent_menus(engine: Engine) -> None:
    """幂等登记单一 SuperAgent 入口，并把旧入口菜单置为不可见（重复运行安全）。"""
    with engine.begin() as conn:
        # 旧入口不再显示在左侧菜单（路由重定向仍保留）
        for legacy in _SUPERAGENT_LEGACY_MENU_PATHS:
            conn.execute(
                text("UPDATE sys_menu SET visible = 0 WHERE path = :path AND is_deleted = false"),
                {"path": legacy},
            )
        for m in [_SUPERAGENT_MENU]:
            exists = conn.execute(
                text("SELECT 1 FROM sys_menu WHERE path = :path AND is_deleted = false LIMIT 1"),
                {"path": m["path"]},
            ).first()
            if exists:
                # 已存在则同步展示字段（幂等更新），使显示端整合后的入口名称生效。
                conn.execute(
                    text(
                        "UPDATE sys_menu SET name = :name, icon = :icon, i18n_key = :i18n_key, "
                        "sort = :sort WHERE path = :path AND is_deleted = false"
                    ),
                    {
                        "name": m["name"], "icon": m["icon"], "i18n_key": m["i18n_key"],
                        "sort": m["sort"], "path": m["path"],
                    },
                )
                continue
            conn.execute(
                text(
                    "INSERT INTO sys_menu "
                    "(name, permission, path, type, sort, parent_id, icon, component, "
                    " component_name, status, visible, keep_alive, always_show, "
                    " i18n_key, is_deleted) "
                    "VALUES (:name, :permission, :path, 2, :sort, 2003, :icon, '', "
                    " '', 0, 1, 1, 0, :i18n_key, false)"
                ),
                {
                    "name": m["name"],
                    "permission": "super-agent:read",
                    "path": m["path"],
                    "sort": m["sort"],
                    "icon": m["icon"],
                    "i18n_key": m["i18n_key"],
                },
            )
            logger.info(f"已登记 SuperAgent 菜单: {m['name']} ({m['path']})")


# ── 统一文件存储管理菜单播种（幂等）────────────────────────────────────────
_FILE_MGMT_MENU = {
    # /admin/file-management：path 末段 file-management 即 componentMap 的 tab key
    "path": "/admin/file-management", "name": "文件存储管理",
    "icon": "CloudServerOutlined", "sort": 10,
    "i18n_key": "sys.menu.file-management",
    "permission": "system:file:query",
    "component": "/views/admin/system/file/index.vue",
}
# 授权角色：平台超管(9999) + 租户管理员(3002)；运营人员(3003)不含系统管理类菜单
_FILE_MGMT_ROLE_IDS = (9999, 3002)


def seed_file_management_menu(engine: Engine) -> None:
    """幂等登记「系统管理 → 文件存储管理」入口（重复运行安全）。"""
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT id FROM sys_menu WHERE path = :path AND is_deleted = false LIMIT 1"),
            {"path": _FILE_MGMT_MENU["path"]},
        ).first()
        if exists:
            # 已存在则同步展示字段（幂等更新），迁移目录调整后仍保持正确归属
            conn.execute(
                text(
                    "UPDATE sys_menu SET name = :name, icon = :icon, i18n_key = :i18n_key, "
                    "component = :component, permission = :permission, sort = :sort, "
                    "parent_id = 2005 WHERE path = :path AND is_deleted = false"
                ),
                {
                    "name": _FILE_MGMT_MENU["name"], "icon": _FILE_MGMT_MENU["icon"],
                    "i18n_key": _FILE_MGMT_MENU["i18n_key"],
                    "component": _FILE_MGMT_MENU["component"],
                    "permission": _FILE_MGMT_MENU["permission"],
                    "sort": _FILE_MGMT_MENU["sort"],
                    "path": _FILE_MGMT_MENU["path"],
                },
            )
            menu_id = exists.id
        else:
            menu_id = conn.execute(
                text(
                    "INSERT INTO sys_menu "
                    "(name, permission, path, type, sort, parent_id, icon, component, "
                    " component_name, status, visible, keep_alive, always_show, "
                    " i18n_key, is_deleted) "
                    "VALUES (:name, :permission, :path, 2, :sort, 2005, :icon, :component, "
                    " '', 0, 1, 1, 0, :i18n_key, false) RETURNING id"
                ),
                {
                    "name": _FILE_MGMT_MENU["name"],
                    "permission": _FILE_MGMT_MENU["permission"],
                    "path": _FILE_MGMT_MENU["path"],
                    "sort": _FILE_MGMT_MENU["sort"],
                    "icon": _FILE_MGMT_MENU["icon"],
                    "component": _FILE_MGMT_MENU["component"],
                    "i18n_key": _FILE_MGMT_MENU["i18n_key"],
                },
            ).scalar_one()
            logger.info(f"已登记文件存储管理菜单: {_FILE_MGMT_MENU['name']} ({_FILE_MGMT_MENU['path']}, id={menu_id})")

        # 幂等授权给管理员角色（角色可能被删过，缺角色则跳过）
        for role_id in _FILE_MGMT_ROLE_IDS:
            conn.execute(
                text(
                    "INSERT INTO sys_role_menu (role_id, menu_id) "
                    "SELECT :role_id, :menu_id WHERE NOT EXISTS ("
                    "  SELECT 1 FROM sys_role_menu WHERE role_id = :role_id AND menu_id = :menu_id)"
                ),
                {"role_id": role_id, "menu_id": menu_id},
            )


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


# ── 图谱实体半精度向量列（幂等；模型后加列的运行库兼底）────────────────
def ensure_kg_entity_half_column(engine: Engine) -> None:
    """确保 ``kg_entity.embedding_half``（halfvec 生成列）与 HNSW 索引存在。

    背景：该列是模型侧后加的 ``Computed("embedding::halfvec")``，而 kg_entity
    的建表走 ``Base.metadata.create_all``（表已存在则整表跳过，**不会补列**），
    于是模型与运行库漂移；ORM 的 SELECT 会展开映射表全部列，直接
    ``column kg_entity.embedding_half does not exist`` 抛 500
    （症状：/graph/cdm-check、/graph/entities、/graph/relations 全 500）。

    维度取自 ``embedding`` 列的真实 typmod（而非配置默认值），
    避免两列维度失配导致生成列表达式校验失败。
    """
    if "kg_entity" not in inspect(engine).get_table_names():
        return

    with engine.begin() as conn:
        if conn.execute(text(
            "SELECT 1 FROM pg_type WHERE typname = 'halfvec'"
        )).first() is None:
            logger.warning(
                "pgvector 未提供 halfvec 类型（< 0.7），跳过 kg_entity.embedding_half；"
                "该列仅用于 ANN 索引，缺失不影响正确性"
            )
            return

        has_col = conn.execute(text(
            "SELECT 1 FROM pg_attribute "
            "WHERE attrelid = 'kg_entity'::regclass "
            "AND attname = 'embedding_half' AND NOT attisdropped"
        )).first()
        if has_col is None:
            dim = conn.execute(text(
                "SELECT a.atttypmod FROM pg_attribute a "
                "WHERE a.attrelid = 'kg_entity'::regclass AND a.attname = 'embedding'"
            )).scalar()
            if not dim or int(dim) <= 0:
                from app.config import settings
                dim = int(settings.EMBEDDING_DIMENSION)
            conn.execute(text(
                f"ALTER TABLE kg_entity ADD COLUMN embedding_half halfvec({int(dim)}) "
                "GENERATED ALWAYS AS (embedding::halfvec) STORED"
            ))
            logger.info(
                f"kg_entity.embedding_half 已补齐（halfvec({int(dim)}) 生成列）"
            )

        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_kg_entity_embedding_half_hnsw "
                "ON kg_entity USING hnsw (embedding_half halfvec_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            ))
        except Exception as exc:  # noqa: BLE001 - 索引失败不阻断启动
            logger.warning(f"kg_entity 半精度 HNSW 索引创建跳过（不影响正确性）: {exc}")


# ── 向量列维度对齐（幂等，仅空表自动执行）────────────────────────────────────
def align_vector_dimensions(engine: Engine) -> None:
    """把 ``kms_segment.embedding`` 维度对齐到当前生效的嵌入配置。

    pgvector 列维度在建表时即固定；当嵌入模型变更（例如改用 2048 维的
    ``qwen3-vl-embedding-2b``）而列仍是 768 时，写入会直接报
    ``expected 768 dimensions, not 2048``。此处按**实际生效配置**
    （模型管理默认向量化模型优先、环境变量兜底）解析目标维度并 ALTER 列类型。

    安全约束：仅当表为空时才自动 ALTER——pgvector 无法无损转换已有向量，
    有数据时只告警并提示先重灌，绝不静默丢弃向量。
    """
    from app.services.kb.embedding_config import resolve_embedding_config_with_fallback

    if "kms_segment" not in inspect(engine).get_table_names():
        return
    try:
        target = int(resolve_embedding_config_with_fallback(None).dimension)
    except Exception as exc:  # noqa: BLE001 - 解析失败不得阻断启动
        logger.warning(f"向量维度对齐跳过（无法解析嵌入配置）: {exc}")
        return
    if not target:
        return

    with engine.begin() as conn:
        current = conn.execute(text(
            "SELECT a.atttypmod FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE c.relname = 'kms_segment' AND a.attname = 'embedding'"
        )).scalar()
        if current == target:
            return
        rows = conn.execute(text("SELECT COUNT(*) FROM kms_segment")).scalar() or 0
        if rows:
            logger.warning(
                f"kms_segment.embedding 维度为 {current}，当前嵌入配置为 {target}，"
                f"但表内已有 {rows} 条切片，无法自动转换；"
                "请先对存量切片执行重灌（换嵌入模型重灌）后再写入"
            )
            return
        # 维度变更必须重建 HNSW 索引（向量算子索引与维度绑定）；
        # pgvector 的 hnsw/ivfflat 索引上限 2000 维，超过则退化为无索引
        # （顺序扫描，检索结果仍正确，只是变慢）
        conn.execute(text("DROP INDEX IF EXISTS idx_kms_segment_embedding_hnsw"))
        conn.execute(text(
            f"ALTER TABLE kms_segment ALTER COLUMN embedding TYPE vector({target})"
        ))
        if target <= 2000:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_kms_segment_embedding_hnsw ON kms_segment "
                "USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            ))
            logger.info(
                f"kms_segment.embedding 维度已对齐：{current} → {target}"
                "（空表，HNSW 索引已重建）"
            )
        else:
            logger.warning(
                f"kms_segment.embedding 维度已对齐：{current} → {target}；"
                f"但 {target} 超过 pgvector hnsw 索引上限 2000，已跳过向量索引"
                "（顺序扫描，检索结果仍正确但更慢；如需索引请改用 ≤2000 维的嵌入模型）"
            )


# ── 默认语音模型播种（幂等；语音 RTC 连接前置条件）────────────────────────
# 语音网关连接前需解析到一条 type=7（语音实时）且可用的模型；若库内无任何
# type=7 模型，前端下拉为空、连接直接报「请新增并启用语音模型(type=7)」。
# 此处自动为已有 DashScope API Key 补一条默认实时模型，保证开箱即用。
def seed_default_voice_model(engine: Engine) -> None:
    """若库内无 type=7 语音模型，则基于首个 DashScope API Key 补建默认模型。

    幂等：已存在任一 type=7 模型则直接返回。模型名取自
    ``voice_config.VALID_DASHSCOPE_REALTIME_MODELS``（官方实时目录），
    保证 ``_voice_row_usable`` 校验通过。若库内无任何 API Key，仅告警不建。
    """
    with engine.begin() as conn:
        exists = conn.execute(text(
            "SELECT 1 FROM ai_chat_model WHERE type = 7 LIMIT 1"
        )).first()
        if exists:
            return

        # 优先取 DashScope 平台 Key（平台名历史大小写不一，用 ILIKE 兜底）
        key_row = conn.execute(text(
            "SELECT id, name, platform FROM ai_api_key "
            "WHERE status = 1 AND (platform ILIKE '%dashscope%' "
            "   OR platform ILIKE '%通义%' OR platform ILIKE '%aliyun%') "
            "ORDER BY sort DESC, id ASC LIMIT 1"
        )).first()
        if key_row is None:
            # 退而求其次：取任意启用 Key（模型仍会展示，但 usable=False 提示用户配置）
            key_row = conn.execute(text(
                "SELECT id, name, platform FROM ai_api_key "
                "WHERE status = 1 ORDER BY sort DESC, id ASC LIMIT 1"
            )).first()
        if key_row is None:
            logger.warning(
                "未找到任何启用的 API Key，跳过默认语音模型播种；"
                "请先在「API 密钥管理」新增 DashScope Key，再到「语音模型配置」创建模型"
            )
            return

        # 默认全双工语音模型 code（DashScope 官方推荐模型）。
        # catalog 现从 DB 读取（voice_catalog.get_provider_catalog），此处迁移阶段
        # 种子数据可能尚未写入，故直接使用默认模型 code，与 voice_full_duplex_models.sql 一致。
        default_model = "qwen3.8-omni-flash-realtime"

        conn.execute(text(
            "INSERT INTO ai_chat_model "
            "(code, key_id, name, model, platform, sort, status, type, is_default, created_at) "
            "VALUES (:code, :key_id, :name, :model, :platform, 0, 1, 7, true, now())"
        ), {
            "code": "voice-realtime-default",
            "key_id": key_row.id,
            "name": "通义千问 Realtime（默认）",
            "model": default_model,
            "platform": key_row.platform or "DashScope",
        })
        logger.info(
            f"已播种默认语音模型: {default_model}（Key={key_row.name}, type=7, is_default=true）"
        )
