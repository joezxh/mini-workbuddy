-- ============================================================
-- 语音能力 Demo（Voice Demo）菜单初始化数据（sys_menu）
-- 对应前端：frontend/src/views/voice-demo/VoiceDemo.vue
-- 设计文档：docs/superpowers/specs/2026-11-10-voice-demo-design.md
--
-- 路由机制说明（同 menu_duplex_voice.sql）：
--   菜单 path 必须为「单段」(/admin/<key>)，path 首段 = componentMap key。
--   componentMap 见 frontend/src/views/admin/componentMap.ts。
--   注意：componentMap 的 'voice-demo' key 已被调解语音（duplex）占用，
--   故本菜单使用 'voice-demo-lab'（实现时已在 componentMap.ts 注册）。
--
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_voice_demo.sql
-- ============================================================

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
-- ============ 一级目录：语音演示（type=1，分组） ============
(2607, '语音演示', 'sys.menu.voice-demo-lab', '/admin/voice-demo-lab', NULL, 9, 0, '', 1, 'AudioOutlined', NULL, false, 1, 0, 0),
-- ============ 二级菜单（type=2，path 单段 = componentMap key） ============
(2608, '语音能力 Demo', 'sys.menu.voice-demo-lab.demo', '/admin/voice-demo-lab', 2607, 1, 0, '', 2, 'AudioOutlined', '/views/voice-demo/VoiceDemo.vue', false, 1, 1, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

-- 将菜单赋予所有已存在角色（确保管理员可见），幂等。
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id IN (2607, 2608)) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);
