-- ============================================================
-- 本体领域管理（onto_domain）菜单初始化（sys_menu）
-- 对应前端：frontend/src/views/data-source/ontology/DomainManagement.vue
-- 路由机制：侧栏 onSelect 取 path 首段，path 必须为单段 /admin/ontology-domain，
--           path 末段 ontology-domain = componentMap key = i18n_key 末段。
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_ontology_domain.sql
-- ============================================================

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
(2409, '本体领域', 'knowledge.menu.ontologyDomain', '/admin/ontology-domain', 2401, 7, 0, 'kg:domain:read', 2, 'AppstoreOutlined', NULL, false, 1, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);
