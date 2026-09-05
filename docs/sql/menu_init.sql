-- ============================================================
-- MinWorkBuddy 菜单权限初始化数据（sys_menu）
-- 依据：frontend/src/views 实际页面 + admin/index.vue 的 componentMap
-- 规则：
--   1. type: 1=目录(一级分组) 2=菜单(可点击页) 3=按钮权限(本脚本未用)
--   2. menuKey = path 最后一段，必须与前端 componentMap 的 key 完全一致
--      （见 frontend/src/views/admin/index.vue 的 componentMap）
--   3. 顶层导航 dashboard/ai-assistant/wiki/admin/agent-team 由 router 硬编码，
--      不走 sys_menu，故本表只含「管理控制台」内能渲染的页面
--   4. agent-team-editor(团队编排) 为事件弹出的上下文页，无独立菜单，已剔除
--   5. i18n_key 必填，约定为 'sys.menu.<menuKey>'（menuKey = path 末段）；
--      前端 admin/index.vue 通过 t(menu.i18nKey) 渲染标题，回退到 name。
--      对应国际化资源见 frontend/src/i18n/locales/{zh-CN,zh-TW,en-US,ja-JP}.ts 的 sys.menu 段
--      （注意 'sys.menu.dashboard' 已被顶层导航占用，门户页 2011 改用 'sys.menu.console-dashboard'）
-- ============================================================

-- 若需清空旧数据（避开旧 risk_control 数据的 1001-1059 段），可先执行：
-- TRUNCATE TABLE "public"."sys_menu" RESTART IDENTITY CASCADE;

INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
VALUES
-- ============ 一级目录（type=1） ============  i18n_key = 'sys.menu.' + menuKey
(2001, '工作台',   'sys.menu.console',             '/admin/console',         NULL, 1, 0, 'console:read',         1, 'DashboardOutlined',  NULL,                    false, 1, 0, 0),
(2002, 'AI 助手',  'sys.menu.ai-assistant',        '/admin/ai-assistant',     NULL, 2, 0, 'ai-assistant:read',    1, 'MessageOutlined',    NULL,                    false, 1, 0, 0),
(2003, 'AI 能力',  'sys.menu.ai-capability',       '/admin/ai-capability',    NULL, 3, 0, 'ai-capability:read',   1, 'RobotOutlined',      NULL,                    false, 1, 0, 0),
(2004, '智能体',   'sys.menu.agent',               '/admin/agent',            NULL, 4, 0, 'agent:read',           1, 'ApartmentOutlined',  NULL,                    false, 1, 0, 0),
(2005, '系统管理', 'sys.menu.system',              '/admin/system',           NULL, 5, 0, 'system:read',         1, 'SettingOutlined',    NULL,                    false, 1, 0, 0),

-- ============ 工作台（parent=2001） ============
(2011, '控制台门户', 'sys.menu.console-dashboard',   '/admin/dashboard',           2001, 1, 0, 'console:dashboard:read', 2, 'DashboardOutlined', '/views/admin/system/DashboardPanel.vue',          false, 1, 1, 0),

-- ============ AI 助手（parent=2002） ============
(2021, '智能对话',   'sys.menu.ai-chat',            '/admin/ai-chat',           2002, 1, 0, 'ai-assistant:chat:read',      2, 'MessageOutlined',    '/views/assistant/components/AssistantPanel.vue', false, 1, 1, 0),
(2022, '会话管理',   'sys.menu.ai-sessions',        '/admin/ai-sessions',       2002, 2, 0, 'ai-assistant:sessions:read',  2, 'CommentOutlined',    '/views/assistant/AiSessionPanel.vue',           false, 1, 1, 0),
(2023, '异步任务',   'sys.menu.async-task-manage',  '/admin/async-task-manage', 2002, 3, 0, 'ai-assistant:async-task:read', 2, 'ClockCircleOutlined', '/views/assistant/AsyncTaskManage.vue',       false, 1, 1, 0),

-- ============ AI 能力（parent=2003，对应 views/admin/ai/*） ============
(2031, '技能管理', 'sys.menu.skill-management',    '/admin/skill-management', 2003, 1, 0, 'ai:skill:read',   2, 'ToolOutlined',      '/views/admin/ai/skill/SkillManagement.vue',      false, 1, 1, 0),
(2032, 'API 密钥', 'sys.menu.apikey',             '/admin/apikey',          2003, 2, 0, 'ai:apikey:read',  2, 'KeyOutlined',       '/views/admin/ai/apikey/ApiKeyManagement.vue',   false, 1, 1, 0),
(2033, '联网搜索', 'sys.menu.web-search',         '/admin/web-search',       2003, 3, 0, 'ai:web-search:read',2, 'SearchOutlined',    '/views/admin/ai/websearch/WebSearchManagement.vue', false, 1, 1, 0),
(2034, '工具管理', 'sys.menu.tool-management',    '/admin/tool-management',  2003, 4, 0, 'ai:tool:read',    2, 'ToolOutlined',      '/views/admin/ai/tool/ToolManagement.vue',       false, 1, 1, 0),
(2035, 'MCP 服务', 'sys.menu.mcp-service',        '/admin/mcp-service',     2003, 5, 0, 'ai:mcp:read',     2, 'NodeIndexOutlined', '/views/admin/ai/mcp/McpServiceManagement.vue',  false, 1, 1, 0),

-- ============ 智能体（parent=2004，对应 views/admin/agent/* + agent-team/*） ============
(2041, '智能体管理', 'sys.menu.agent-management',  '/admin/agent-management', 2004, 1, 0, 'agent:read',             2, 'RobotOutlined',     '/views/admin/agent/AgentManagement.vue',           false, 1, 1, 0),
(2042, '调用记录',   'sys.menu.session-agent',     '/admin/session-agent',    2004, 2, 0, 'agent:execution:read',   2, 'MonitorOutlined',   '/views/admin/agent/AgentExecutionManagement.vue', false, 1, 1, 0),
(2043, '智能体团队', 'sys.menu.agent-team',        '/admin/agent-team',       2004, 3, 0, 'agent-team:read',        2, 'ApartmentOutlined', '/views/admin/agent-team/TeamList.vue',           false, 1, 1, 0),

-- ============ 系统管理（parent=2005，对应 views/admin/system/*） ============
(2051, '系统设置', 'sys.menu.system-management',   '/admin/system-management',        2005, 1, 0, 'system:management:read', 2, 'SettingOutlined',  '/views/admin/system/SystemManagement.vue',   false, 1, 1, 0),
(2052, '个人信息', 'sys.menu.profile',             '/admin/profile',                 2005, 2, 0, 'profile:read',          2, 'UserOutlined',     '/views/admin/system/ProfilePanel.vue',        false, 1, 1, 0),
(2053, '字典管理', 'sys.menu.dictionary',          '/admin/dictionary',              2005, 3, 0, 'dictionary:dictionaries:read', 2, 'DatabaseOutlined', '/views/admin/system/DictionaryPanel.vue', false, 1, 1, 0),
(2054, '区域管理', 'sys.menu.region',             '/admin/region',                  2005, 4, 0, 'dictionary:regions:read', 2, 'GlobalOutlined',   '/views/admin/system/RegionPanel.vue',        false, 1, 1, 0),
(2055, '租户管理', 'sys.menu.tenant-management',   '/admin/tenant-management',       2005, 5, 0, 'tenant:read',            2, 'BankOutlined',     '/views/admin/system/TenantPanel.vue',        false, 1, 1, 0),
(2056, '租户套餐', 'sys.menu.tenant-package-management', '/admin/tenant-package-management', 2005, 6, 0, 'tenant:package:read',  2, 'AppstoreOutlined', '/views/admin/system/TenantPackagePanel.vue', false, 1, 1, 0);


-- ============================================================
-- 二、角色定义（sys_role）
-- 说明：
--   - 鉴权逻辑见 backend/app/routers/auth.py：
--       * is_admin 用户 或 role_code='super_admin' → 权限为 ['*:*']，菜单返回全部
--       * 普通用户：菜单可见性由 sys_role_menu(role_id→menu_id) 决定；
--         接口权限(permissions) 由所关联菜单的 sys_menu.permission 汇总得到
--   - 因此给角色分配菜单时，必须同时包含「目录(type=1)」与其下「菜单(type=2)」，
--     否则菜单树会丢失父级分组
-- ============================================================

INSERT INTO "public"."sys_role"
  (role_id, role_name, role_code, description, sort_order, status, is_deleted)
VALUES
(9999, '平台超级管理员', 'super_admin', '系统内置超级管理员，拥有全部菜单与接口权限（*:*）', 1, 'active', false),
(3002, '租户管理员',     'tenant_admin', '租户内管理员，拥有管理控制台全部菜单（不含平台级租户/套餐管理）', 2, 'active', false),
(3003, '运营人员',       'operator',     '日常运营角色：工作台/AI助手/AI能力/智能体可读可用，仅限个人信息，不含系统配置类页面', 3, 'active', false);


-- ============================================================
-- 三、角色-菜单关联（sys_role_menu）
-- role_id 引用上方 sys_role；menu_id 引用上方 sys_menu 的显式主键
-- ============================================================

-- 3.1 平台超级管理员：全部 23 个菜单（含 5 个目录 + 18 个页面）
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT 9999, m.id FROM "public"."sys_menu" m
WHERE m.id BETWEEN 2001 AND 2056 AND m.is_deleted = false;

-- 3.2 租户管理员：除平台级「租户管理(2055)」「租户套餐(2056)」外的全部菜单
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT 3002, m.id FROM "public"."sys_menu" m
WHERE m.id BETWEEN 2001 AND 2056
  AND m.id NOT IN (2055, 2056)
  AND m.is_deleted = false;

-- 3.3 运营人员：工作台 + AI助手 + AI能力 + 智能体(管理/调用记录) + 系统管理(仅个人信息)
--     不含：智能体团队(2043)、系统设置(2051)、字典(2053)、区域(2054)、租户管理(2055)、租户套餐(2056)
INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT 3003, m.id FROM "public"."sys_menu" m
WHERE m.id IN (
        2001, 2011,                                  -- 工作台目录 + 控制台门户
        2002, 2021, 2022, 2023,                      -- AI助手目录 + 智能对话/会话管理/异步任务
        2003, 2031, 2032, 2033, 2034, 2035,          -- AI能力目录 + 技能/API密钥/联网搜索/工具/MCP
        2004, 2041, 2042,                            -- 智能体目录 + 智能体管理/调用记录
        2005, 2052                                   -- 系统管理目录 + 个人信息
      )
  AND m.is_deleted = false;


-- ============================================================
-- 四、用户-角色关联（sys_user_role，可选）
-- 说明：平台引导创建的租户管理员（tenant_service 在创建租户时自动建账号，is_admin=true）
--       已自带 is_admin 语义，无需额外绑定角色即拥有全部权限。
--       下方为「给指定用户绑定角色」的模板，请将 <USER_ID> 替换为真实 sys_user.user_id：
-- ============================================================
--
-- INSERT INTO "public"."sys_user_role" (user_id, role_id)
-- VALUES
--   (<USER_ID>, 9999);   -- 绑定为平台超级管理员
--
-- 示例：将用户 admin(假设 user_id=1) 绑定为租户管理员
-- INSERT INTO "public"."sys_user_role" (user_id, role_id) VALUES (1, 3002);
--
-- 注意：sys_user.password_hash 为 bcrypt 哈希，不可明文写入；
--       如需新增可登录用户，请通过后端接口或以下等价逻辑生成哈希后插入：
--       from app.services.auth_service import AuthService
--       hash = AuthService.get_password_hash('admin123')
