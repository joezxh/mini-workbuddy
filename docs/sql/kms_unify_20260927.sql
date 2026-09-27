-- =============================================================================
-- 知识库管理模块统一化迁移（spec: docs/superpowers/specs/2026-09-27-knowledge-unification-design.md）
-- 日期：2026-09-27    适用：PostgreSQL    执行方式：按序手动执行（无 Alembic）
--
-- ⚠️ 同一套语句已内置于 backend/app/db/startup_migrations.py（_TABLE_RENAME_MAP +
--    _COLUMN_MIGRATIONS），服务启动时幂等执行。本文件用于：
--    1) 生产库在**不重启服务**的情况下先行落库；
--    2) DBA 复核与回滚参考（回滚脚本见文件末尾）。
-- =============================================================================

BEGIN;

-- 001 统一容器 type（kms_knowledge 成为三类知识库唯一一级容器）
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS type INTEGER NOT NULL DEFAULT 1;
COMMENT ON COLUMN kms_knowledge.type IS '知识库类型: 1=llm-wiki 2=general-kb 3=external-kb';
CREATE INDEX IF NOT EXISTS idx_kms_knowledge_tenant_type ON kms_knowledge (tenant_id, type);

-- 001b 二级形态（Dify 对齐，spec §10.2）
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS kb_format VARCHAR(16);
COMMENT ON COLUMN kms_knowledge.kb_format IS '二级形态: type=2 → document|table|qa; type=3 → connector|proxy; type=1 为 NULL';
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS multimodal_enabled BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN kms_knowledge.multimodal_enabled IS 'type=2/document: 图片独立向量化（需 Vision Embedding 模型）';
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS index_mode VARCHAR(16) NOT NULL DEFAULT 'high_quality';
COMMENT ON COLUMN kms_knowledge.index_mode IS '索引模式: high_quality=向量+全文 | economy=仅关键词，不消耗 embedding';
ALTER TABLE kms_knowledge ADD COLUMN IF NOT EXISTS pipeline_config JSONB;
COMMENT ON COLUMN kms_knowledge.pipeline_config IS '摄取编排: {clean:[...], chunker:{type,params}, index:{...}}';

-- 002 分类表改造：kms_category → 通用分类容器 kb_category
ALTER TABLE IF EXISTS kms_category RENAME TO kb_category;
ALTER INDEX IF EXISTS idx_wiki_category_slug   RENAME TO idx_kb_category_slug;
ALTER INDEX IF EXISTS idx_wiki_category_parent RENAME TO idx_kb_category_parent;
ALTER TABLE kb_category ADD COLUMN IF NOT EXISTS kb_type INTEGER;
COMMENT ON COLUMN kb_category.kb_type IS '冗余的知识库类型（随 knowledge_id 回填；null=未归类）';
UPDATE kb_category c SET kb_type = k.type FROM kms_knowledge k
 WHERE c.knowledge_id = k.id AND c.kb_type IS NULL;

-- 003 kb_collection 挂接容器 + 表格 KB 字段定义
ALTER TABLE kb_collection ADD COLUMN IF NOT EXISTS knowledge_id BIGINT REFERENCES kms_knowledge(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_kb_collection_knowledge ON kb_collection (knowledge_id);
ALTER TABLE kb_collection ADD COLUMN IF NOT EXISTS schema_config JSONB;
COMMENT ON COLUMN kb_collection.schema_config IS '表格 KB 字段定义: [{name,type,enabled,embedding(单选),filterable}]';

-- 003b kb_segment 类型化切片（spec §10.2）
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(16) NOT NULL DEFAULT 'text';
COMMENT ON COLUMN kb_segment.chunk_type IS 'text|qa|table_row|image|parent|child';
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES kb_segment(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_kb_segment_parent ON kb_segment (parent_id);
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS answer TEXT;
COMMENT ON COLUMN kb_segment.answer IS 'chunk_type=qa: 完整答案（content=问题，仅问题做 embedding）';
ALTER TABLE kb_segment ADD COLUMN IF NOT EXISTS keywords JSONB;

-- 004 外部连接器实例层（新表；ORM create_all 亦会建，此处为手动执行兜底）
CREATE TABLE IF NOT EXISTS kms_connector_instance (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           BIGINT,
    knowledge_id        BIGINT REFERENCES kms_knowledge(id) ON DELETE SET NULL,
    code                VARCHAR(200) NOT NULL,
    name                VARCHAR(200) NOT NULL,
    connector_type      VARCHAR(32)  NOT NULL,
    config              JSONB,
    sync_enabled        BOOLEAN NOT NULL DEFAULT false,
    sync_interval_min   INTEGER NOT NULL DEFAULT 60,
    target_collection   VARCHAR(128),
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    last_sync_at        TIMESTAMP,
    error_detail        TEXT,
    creator_id          BIGINT,
    updater_id          BIGINT,
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_connector_instance_code UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS idx_kms_connector_instance_knowledge ON kms_connector_instance (knowledge_id);

CREATE TABLE IF NOT EXISTS kms_connector_sync_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT,
    instance_id     BIGINT NOT NULL REFERENCES kms_connector_instance(id) ON DELETE CASCADE,
    connector_type  VARCHAR(32) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    added           INTEGER NOT NULL DEFAULT 0,
    updated         INTEGER NOT NULL DEFAULT 0,
    deleted         INTEGER NOT NULL DEFAULT 0,
    cursor_value    VARCHAR(255),
    duration_ms     INTEGER,
    error_detail    TEXT,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    creator_id      BIGINT,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_kms_connector_sync_log_instance ON kms_connector_sync_log (instance_id);

-- 005 OKF 合规层（spec §9.2，llm-wiki 文章）
ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS okf_type    VARCHAR(64);
ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS resource    VARCHAR(500);
ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS sources     JSONB;
ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS verified    JSONB;
ALTER TABLE kms_article ADD COLUMN IF NOT EXISTS stale_after TIMESTAMP;
COMMENT ON COLUMN kms_article.okf_type IS 'OKF type: concept|howto|reference|decision|metric 或自定义';
COMMENT ON COLUMN kms_article.sources  IS 'OKF §5.1 溯源家族: [{resource(必填), id, title, author, usage_count, last_modified}]';
COMMENT ON COLUMN kms_article.verified IS 'OKF §5.2 验证事件列表: [{by, at}]';
COMMENT ON COLUMN kms_article.stale_after IS 'OKF §5.5 绝对过期时间点';

-- 006 版本快照补列：operation_type 缺失会让「建/改文章」直接 TypeError；
--     summary / owl_class_uris 供回滚完整还原。
ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS operation_type VARCHAR(32);
ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS summary VARCHAR(1000);
ALTER TABLE kms_article_version ADD COLUMN IF NOT EXISTS owl_class_uris JSONB;
COMMENT ON COLUMN kms_article_version.operation_type IS '操作类型: create|edit|rollback';

COMMIT;

-- =============================================================================
-- 回滚脚本（仅在确认无下游依赖后执行；与上面顺序严格相反）
--
-- BEGIN;
-- ALTER TABLE kms_article_version DROP COLUMN IF EXISTS owl_class_uris,
--     DROP COLUMN IF EXISTS summary, DROP COLUMN IF EXISTS operation_type;
-- ALTER TABLE kms_article DROP COLUMN IF EXISTS stale_after, DROP COLUMN IF EXISTS verified,
--     DROP COLUMN IF EXISTS sources, DROP COLUMN IF EXISTS resource, DROP COLUMN IF EXISTS okf_type;
-- DROP TABLE IF EXISTS kms_connector_sync_log;
-- DROP TABLE IF EXISTS kms_connector_instance;
-- ALTER TABLE kb_segment DROP COLUMN IF EXISTS keywords, DROP COLUMN IF EXISTS answer,
--     DROP COLUMN IF EXISTS parent_id, DROP COLUMN IF EXISTS chunk_type;
-- ALTER TABLE kb_collection DROP COLUMN IF EXISTS schema_config, DROP COLUMN IF EXISTS knowledge_id;
-- ALTER TABLE kb_category DROP COLUMN IF EXISTS kb_type;
-- ALTER TABLE kb_category RENAME TO kms_category;
-- ALTER INDEX IF EXISTS idx_kb_category_slug   RENAME TO idx_wiki_category_slug;
-- ALTER INDEX IF EXISTS idx_kb_category_parent RENAME TO idx_wiki_category_parent;
-- ALTER TABLE kms_knowledge DROP COLUMN IF EXISTS pipeline_config, DROP COLUMN IF EXISTS index_mode,
--     DROP COLUMN IF EXISTS multimodal_enabled, DROP COLUMN IF EXISTS kb_format,
--     DROP COLUMN IF EXISTS type;
-- DROP INDEX IF EXISTS idx_kms_knowledge_tenant_type;
-- COMMIT;
-- =============================================================================
