-- ============================================================
-- 工作流管理（Workflow Management）菜单初始化数据（sys_menu）
-- 对应前端：frontend/src/views/admin/workflow/*
-- 设计文档：docs/superpowers/specs/2026-09-12-workflow-management-design.md
--
-- 路由机制说明：
--   前端侧栏 onSelect 用正则 /^\/admin\/([^/]+)/ 只取 path 首段作为 tab key，
--   因此菜单 path 必须为「单段」(/admin/workflow-management)，
--   path 首段 = componentMap 的 key = sys_menu.i18n_key 的末段。
--   componentMap 见 frontend/src/views/admin/componentMap.ts。
--
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_workflow.sql
-- ============================================================

-- 说明：使用 WHERE NOT EXISTS 做幂等插入，不依赖唯一约束，有无主键均可安全重复执行。

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
-- ============ 一级目录：工作流管理（type=1，分组，不可点击打开具体页） ============
(2501, '工作流管理', 'sys.menu.workflow',              '/admin/workflow',              NULL, 7, 0, 'workflow:read',                1, 'ApiOutlined',       NULL,                                              false, 1, 0, 0),
-- ============ 二级菜单（type=2，可点击页，path 单段 = componentMap key） ============
(2502, '工作流列表', 'sys.menu.workflow-management',   '/admin/workflow-management',   2501, 1, 0, 'workflow:flow:read',           2, 'ApiOutlined',       '/views/admin/workflow/WorkflowManagement.vue',    false, 1, 1, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

-- 将工作流管理菜单的 id 存入 @wf_menu_ids 供后续角色分配使用（PostgreSQL DO 块）
-- 将工作流菜单赋予所有已存在角色（确保管理员可见），同样用 NOT EXISTS 做幂等。
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2501 AND 2502) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);
