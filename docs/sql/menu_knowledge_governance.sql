-- ============================================================
-- 知识治理（Knowledge Governance）菜单初始化 / 统一化覆盖数据（sys_menu）
-- 对应前端：
--   frontend/src/views/kms/KnowledgeBaseManager.vue   （统一工作台，kg-knowledge-manager）
--   frontend/src/views/admin/knowledge/*               （数据源 / 本体 管理视图）
-- 设计文档：docs/superpowers/specs/2026-09-27-knowledge-unification-design.md（§6 统一工作台）
--
-- 路由机制说明（重要）：
--   前端侧栏 onSelect 用正则 /^\/admin\/([^/]+)/ 只取 path 首段作为 tab key，
--   因此菜单 path 必须为「单段」(/admin/kg-knowledge-manager)，
--   path 末段 = componentMap 的 key = sys_menu.i18n_key 的末段。
--   componentMap 见 frontend/src/views/admin/componentMap.ts。
--
-- 统一化映射（spec §2 / §6）：
--   原「知识库」(2403, kg-kb) 升级为「统一知识库工作台」(kg-knowledge-manager)，
--   单页内以 Tab 形态承载三类知识库：LLM Wiki | 通用 KB | 外部集成；
--   外部知识库(原 2404) 已并入统一工作台「外部集成」Tab，不再单独进菜单；
--   /wiki 原路由保留为 type=1（LLM Wiki）深链，由统一工作台统一入口收口。
--   数据源(2402) 与 本体(2405) 为独立支撑模块。
--
-- 应用方式（PostgreSQL）：
--   psql -h <host> -U <user> -d <db> -f docs/sql/menu_knowledge_governance.sql
-- ============================================================

-- 说明：INSERT 用 WHERE NOT EXISTS 做幂等（首次建库）；已存在的 2403 通过下方
-- UPDATE 幂等改写为统一工作台（重跑无害）。部分部署 sys_menu.id 无唯一约束，
-- 故不使用 ON CONFLICT。被并入统一工作台的旧「外部知识库」(2404) 通过下方
-- DELETE 幂等移除（含其角色授权），重跑无害。

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
-- ============ 一级目录：知识治理（type=1，分组，不可点击打开具体页） ============
(2401, '知识治理',           'knowledge.menu.knowledge', '/admin/knowledge',          NULL, 0, 0, 'kg:read',          1, 'DatabaseOutlined',  NULL, false, 1, 0, 0),
-- ============ 二级菜单（type=2，可点击页，path 单段 = componentMap key） ============
-- 统一知识库工作台（spec §6）：Tab 承载 LLM Wiki / 通用 KB / 外部集成，统一入口
(2403, '工作台',   'knowledge.menu.unified',  '/admin/kg-knowledge-manager', 2401, 1, 0, 'kg:kb:read',       2, 'BookOutlined',      NULL, false, 1, 0, 0),
-- 数据源（DataOps，支撑 type=2/table 的 db_table 直连定时同步）
(2402, '数据源',             'knowledge.menu.dataSource','/admin/kg-data-source',     2401, 2, 0, 'kg:datasource:read',2, 'DatabaseOutlined',  NULL, false, 1, 0, 0),
-- 本体（ontology 建模）
(2405, '本体',               'knowledge.menu.ontology',  '/admin/kg-ontology',         2401, 3, 0, 'kg:ontology:read', 2, 'ApartmentOutlined', NULL, false, 1, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

-- 已存在部署：将旧「知识库」(2403, kg-kb) 幂等改写为统一工作台。
-- 重跑无害（仅设置相同值）；统一工作台收口后旧 kg-kb 管理视图不再单独进菜单。
UPDATE "public"."sys_menu"
SET name='统一知识库工作台',
    i18n_key='knowledge.menu.unified',
    path='/admin/kg-knowledge-manager',
    permission='kg:kb:read',
    type=2,
    icon='BookOutlined',
    component=NULL,
    sort=1,
    status=0,
    visible=1,
    keep_alive=0,
    always_show=0,
    updated_at=now()
WHERE id = 2403;

-- 已存在部署：移除旧「外部知识库」(2404)，其能力已由统一工作台「外部集成」Tab 承载。
-- 幂等（无对应行时 no-op）；同步清理其角色授权，避免孤儿引用。
DELETE FROM "public"."sys_role_menu" WHERE menu_id = 2404;
DELETE FROM "public"."sys_menu" WHERE id = 2404;

-- 原「wiki知识库」(id=2, kg-private-kb) 收口进统一工作台「LLM Wiki」Tab，
-- 仅保留路由（/admin/kg-private-kb）作为深链，从侧栏隐藏（visible=0）。权限保留，路由可直接访问。
-- 幂等（无对应行时 no-op）。
UPDATE "public"."sys_menu" SET visible = 0, updated_at = now() WHERE id = 2;

-- 将知识治理菜单赋予所有已存在角色（确保管理员可见），同样用 NOT EXISTS 做幂等。
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2401 AND 2405 AND id <> 2404) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);
