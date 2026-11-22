-- ============================================================
-- 统一文件存储管理（File Management）菜单初始化（sys_menu）
--
-- 注意：后端启动时会自动幂等播种此菜单（app/db/startup_migrations.py
--       seed_file_management_menu，parent=2005 系统管理），通常无需手动执行本文件。
--       本文件仅供「关闭启动迁移」或手工初始化库的环境兜底使用。
--
-- 对应前端：frontend/src/views/admin/system/file/index.vue
-- 路由机制：path 末段 = componentMap key = file-management
--   componentMap 见 frontend/src/views/admin/componentMap.ts
--
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_file_management.sql
-- ============================================================

-- 幂等登记菜单（按 path 判重，不指定固定 id，避免与播种自增 id 冲突）
INSERT INTO "public"."sys_menu"
  (name, permission, path, type, sort, parent_id, icon, component, component_name,
   status, visible, keep_alive, always_show, i18n_key, is_deleted)
SELECT '文件存储管理', 'system:file:query', '/admin/file-management', 2, 10, 2005,
       'CloudServerOutlined', '/views/admin/system/file/index.vue', '',
       0, 1, 1, 0, 'sys.menu.file-management', false
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_menu" WHERE path = '/admin/file-management' AND is_deleted = false
);

-- 幂等授权：平台超管(9999) + 租户管理员(3002)
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM (VALUES (9999), (3002)) AS r(role_id)
CROSS JOIN "public"."sys_menu" m
WHERE m.path = '/admin/file-management' AND m.is_deleted = false
  AND EXISTS (SELECT 1 FROM "public"."sys_role" rr WHERE rr.role_id = r.role_id)
  AND NOT EXISTS (
    SELECT 1 FROM "public"."sys_role_menu" rm
    WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
  );
