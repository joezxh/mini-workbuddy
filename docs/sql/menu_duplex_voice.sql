-- ============================================================
-- 调解语音 RTC（Duplex Voice RTC）菜单初始化数据（sys_menu）
-- 对应前端：frontend/src/views/duplex/VoiceDemo.vue 等（迁移自 risk_control）
-- 设计文档：docs/superpowers/specs/2026-09-05-duplex-voice-communication-design.md 等
--
-- 路由机制说明（同 menu_workflow.sql）：
--   菜单 path 必须为「单段」(/admin/<key>)，path 首段 = componentMap key。
--   componentMap 见 frontend/src/views/admin/componentMap.ts。
--
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_duplex_voice.sql
-- ============================================================

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
-- ============ 一级目录：调解语音（type=1，分组） ============
(2601, '调解语音', 'sys.menu.duplex-voice', '/admin/duplex-voice', NULL, 8, 0, 'duplex:voice:read', 1, 'AudioOutlined', NULL, false, 1, 0, 0),
-- ============ 二级菜单（type=2，path 单段 = componentMap key） ============
(2602, '语音 RTC 演示',   'sys.menu.voice-demo',        '/admin/voice-demo',        2601, 1, 0, 'duplex:voice:read',      2, 'AudioOutlined', '/views/duplex/VoiceDemo.vue',                        false, 1, 1, 0),
(2603, '语音角色配置',   'sys.menu.voice-roles',       '/admin/voice-roles',       2601, 2, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/duplex/config/VoiceSessionConfig.vue',  false, 1, 1, 0),
(2604, '语音模型配置',   'sys.menu.voice-models',      '/admin/voice-models',      2601, 3, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/duplex/config/VoiceModelConfig.vue',    false, 1, 1, 0),
(2605, '语音 Agent 配置','sys.menu.voice-agents',      '/admin/voice-agents',      2601, 4, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/ai-config/agents/AgentConfigPanel.vue',    false, 1, 1, 0),
(2606, '语音工具策略',   'sys.menu.voice-tool-policy', '/admin/voice-tool-policy', 2601, 5, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/ai/components/ToolPolicyEditor.vue',       false, 1, 1, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

-- 将菜单赋予所有已存在角色（确保管理员可见），幂等。
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2601 AND 2606) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);
