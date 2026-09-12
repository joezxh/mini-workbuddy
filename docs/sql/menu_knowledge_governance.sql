-- ============================================================
-- 知识治理（Knowledge Governance）菜单初始化数据（sys_menu）
-- 对应前端：frontend/src/views/admin/knowledge/*
-- 设计文档：docs/superpowers/specs/2026-09-10-knowledge-governance-frontend-design.md
--
-- 路由机制说明（重要）：
--   前端侧栏 onSelect 用正则 /^\/admin\/([^/]+)/ 只取 path 首段作为 tab key，
--   因此菜单 path 必须为「单段」(/admin/kg-data-source)，
--   path 首段 = componentMap 的 key = sys_menu.i18n_key 的末段。
--   componentMap 见 frontend/src/views/admin/componentMap.ts。
--
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_knowledge_governance.sql
-- ============================================================

-- 说明：改用 WHERE NOT EXISTS 做幂等插入，而非 ON CONFLICT。
-- 部分部署的 sys_menu.id 并非主键 / 无唯一索引，ON CONFLICT (id) 会报
-- "there is no unique or exclusion constraint matching the ON CONFLICT specification"；
-- WHERE NOT EXISTS 不依赖唯一约束，有无主键均可安全重复执行。

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
-- ============ 一级目录：知识治理（type=1，分组，不可点击打开具体页） ============
(2401, '知识治理', 'knowledge.menu.knowledge',     '/admin/knowledge',       NULL, 6, 0, 'kg:read',             1, 'DatabaseOutlined',  NULL,                    false, 1, 0, 0),
-- ============ 二级菜单（type=2，可点击页，path 单段 = componentMap key） ============
(2402, '数据源',   'knowledge.menu.dataSource',    '/admin/kg-data-source',  2401, 1, 0, 'kg:datasource:read',  2, 'DatabaseOutlined',  NULL,                    false, 1, 0, 0),
(2403, '知识库',   'knowledge.menu.kb',             '/admin/kg-kb',           2401, 2, 0, 'kg:kb:read',          2, 'BookOutlined',      NULL,                    false, 1, 0, 0),
(2404, '外部知识库','knowledge.menu.externalKb',    '/admin/kg-external-kb',   2401, 3, 0, 'kg:external:read',    2, 'CloudSyncOutlined', NULL,                    false, 1, 0, 0),
(2405, '本体',     'knowledge.menu.ontology',       '/admin/kg-ontology',      2401, 4, 0, 'kg:ontology:read',    2, 'ApartmentOutlined', NULL,                    false, 1, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

-- 将知识治理菜单赋予所有已存在角色（确保管理员可见），同样用 NOT EXISTS 做幂等。
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2401 AND 2405) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);
