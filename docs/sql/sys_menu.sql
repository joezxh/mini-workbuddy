/*
 Navicat Premium Dump SQL

 Source Server         : pgvector-localhost
 Source Server Type    : PostgreSQL
 Source Server Version : 170011 (170011)
 Source Host           : localhost:5432
 Source Catalog        : miniworkbuddy
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170011 (170011)
 File Encoding         : 65001

 Date: 01/10/2026 16:49:44
*/


-- ----------------------------
-- Table structure for sys_menu
-- ----------------------------
DROP TABLE IF EXISTS "public"."sys_menu";
CREATE TABLE "public"."sys_menu" (
  "id" int8 NOT NULL DEFAULT nextval('sys_menu_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "permission" varchar(100) COLLATE "pg_catalog"."default",
  "path" varchar(255) COLLATE "pg_catalog"."default",
  "type" int4,
  "sort" int4,
  "parent_id" int8,
  "icon" varchar(100) COLLATE "pg_catalog"."default",
  "component" varchar(255) COLLATE "pg_catalog"."default",
  "component_name" varchar(100) COLLATE "pg_catalog"."default",
  "status" int4,
  "visible" int4,
  "keep_alive" int4,
  "always_show" int4,
  "i18n_key" varchar(100) COLLATE "pg_catalog"."default",
  "is_deleted" bool NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Records of sys_menu
-- ----------------------------
INSERT INTO "public"."sys_menu" VALUES (2002, 'AI 助手', 'ai-assistant:read', '/admin/ai-assistant', 1, 2, NULL, 'MessageOutlined', NULL, NULL, 0, 1, 0, 0, 'sys.menu.ai-assistant', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2031, '技能管理', 'ai:skill:read', '/admin/skill-management', 2, 1, 2003, 'ToolOutlined', '/views/admin/ai/skill/SkillManagement.vue', NULL, 0, 1, 1, 0, 'sys.menu.skill-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2051, '系统设置', 'system:management:read', '/admin/system-management', 2, 1, 2005, 'SettingOutlined', '/views/admin/system/SystemManagement.vue', NULL, 0, 1, 1, 0, 'sys.menu.system-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2052, '个人信息', 'profile:read', '/admin/profile', 2, 2, 2005, 'UserOutlined', '/views/admin/system/ProfilePanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.profile', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2053, '字典管理', 'dictionary:dictionaries:read', '/admin/dictionary', 2, 3, 2005, 'DatabaseOutlined', '/views/admin/system/DictionaryPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.dictionary', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2054, '区域管理', 'dictionary:regions:read', '/admin/region', 2, 4, 2005, 'GlobalOutlined', '/views/admin/system/RegionPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.region', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2055, '租户管理', 'tenant:read', '/admin/tenant-management', 2, 5, 2005, 'BankOutlined', '/views/admin/system/TenantPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.tenant-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2056, '租户套餐', 'tenant:package:read', '/admin/tenant-package-management', 2, 6, 2005, 'AppstoreOutlined', '/views/admin/system/TenantPackagePanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.tenant-package-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047');
INSERT INTO "public"."sys_menu" VALUES (2043, '智能体团队', 'agent-team:read', '/admin/agent-team', 2, 3, 2003, 'ApartmentOutlined', '/views/admin/agent-team/TeamList.vue', '', 0, 1, 1, 0, 'sys.menu.agent-team', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:25.865559');
INSERT INTO "public"."sys_menu" VALUES (2033, '联网搜索', 'ai:web-search:read', '/admin/web-search', 2, 30, 2003, 'SearchOutlined', '/views/admin/ai/websearch/WebSearchManagement.vue', '', 0, 1, 1, 0, 'sys.menu.web-search', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:45.927455');
INSERT INTO "public"."sys_menu" VALUES (2035, 'MCP 服务', 'ai:mcp:read', '/admin/mcp-service', 2, 50, 2003, 'NodeIndexOutlined', '/views/admin/ai/mcp/McpServiceManagement.vue', '', 0, 1, 1, 0, 'sys.menu.mcp-service', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:53.749403');
INSERT INTO "public"."sys_menu" VALUES (2034, '工具管理', 'ai:tool:read', '/admin/tool-management', 2, 40, 2003, 'ToolOutlined', '/views/admin/ai/tool/ToolManagement.vue', '', 0, 1, 1, 0, 'sys.menu.tool-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:00.562597');
INSERT INTO "public"."sys_menu" VALUES (2032, 'API 密钥', 'ai:apikey:read', '/admin/apikey', 2, 20, 2003, 'KeyOutlined', '/views/admin/ai/apikey/ApiKeyManagement.vue', '', 0, 1, 1, 0, 'sys.menu.apikey', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:08.391515');
INSERT INTO "public"."sys_menu" VALUES (2042, '调用记录', 'agent:execution:read', '/admin/session-agent', 2, 60, 2003, 'MonitorOutlined', '/views/admin/agent/AgentExecutionManagement.vue', '', 0, 1, 1, 0, 'sys.menu.session-agent', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:29.068539');
INSERT INTO "public"."sys_menu" VALUES (2041, '智能体管理', 'agent:read', '/admin/agent-management', 2, 2, 2003, 'RobotOutlined', '/views/admin/agent/AgentManagement.vue', '', 0, 1, 1, 0, 'sys.menu.agent-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:37.436257');
INSERT INTO "public"."sys_menu" VALUES (2402, '数据源', 'kg:datasource:read', '/admin/kg-data-source', 2, 5, 2401, 'DatabaseOutlined', '/views/admin/knowledge/DataSourcePanel.vue', 'kg-data-source', 0, 1, 0, 0, 'knowledge.menu.dataSource', 'f', '2026-09-12 13:35:28.947913', '2026-09-12 13:35:28.947913');
INSERT INTO "public"."sys_menu" VALUES (2004, '智能体', 'agent:read', '/admin/agent', 1, 40, 0, 'ApartmentOutlined', '', '', 1, 0, 0, 0, 'sys.menu.agent', 'f', '2026-09-05 19:25:45.436047', '2026-09-12 13:36:54.914762');
INSERT INTO "public"."sys_menu" VALUES (2005, '系统管理', 'system:read', '/admin/system', 1, 90, 0, 'SettingOutlined', '', '', 0, 1, 0, 0, 'sys.menu.system', 'f', '2026-09-05 19:25:45.436047', '2026-09-12 13:37:04.520665');
INSERT INTO "public"."sys_menu" VALUES (2401, '知识治理', 'kg:read', '/admin/knowledge', 1, 60, 0, 'DatabaseOutlined', '', '', 0, 1, 0, 0, 'knowledge.menu.knowledge', 'f', '2026-09-12 13:35:28.947913', '2026-09-12 13:37:20.62148');
INSERT INTO "public"."sys_menu" VALUES (2003, 'AI 能力配置', 'ai-capability:read', '/admin/ai-capability', 1, 80, 0, 'RobotOutlined', '', '', 0, 1, 0, 0, 'sys.menu.ai-capability', 'f', '2026-09-05 19:25:45.436047', '2026-09-12 13:37:31.134645');
INSERT INTO "public"."sys_menu" VALUES (2403, '知识库', 'kg:kb:read', '/admin/kg-kb', 2, 2, 2401, 'BookOutlined', '/views/admin/knowledge/KnowledgeBasePanel.vue', 'kg-kb', 0, 1, 0, 0, 'knowledge.menu.kb', 'f', '2026-09-12 13:35:28.947913', '2026-09-12 13:35:28.947913');
INSERT INTO "public"."sys_menu" VALUES (2502, '工作流列表', 'workflow:flow:read', '/admin/workflow-management', 2, 90, 2003, 'ApiOutlined', '/views/admin/workflow/WorkflowManagement.vue', '', 0, 1, 1, 0, 'sys.menu.workflow-management', 'f', '2026-09-13 01:08:59.060274', '2026-09-13 01:10:41.434168');
INSERT INTO "public"."sys_menu" VALUES (2, 'wiki知识库', '', '/admin/kg-private-kb', 2, 1, 2401, 'ProfileOutlined', '/views/kms/wiki/index.vue', 'llm-wiki', 0, 0, 1, 1, 'knowledge.menu.private.knowledge', 'f', '2026-09-06 10:33:44.643016', '2026-09-12 17:29:18.329448');
INSERT INTO "public"."sys_menu" VALUES (2404, '外部知识库', 'kg:external:read', '/admin/kg-external-kb', 2, 3, 2401, 'CloudSyncOutlined', '/views/admin/knowledge/ExternalKbPanel.vue', 'kg-external-kb', 0, 1, 0, 0, 'knowledge.menu.externalKb', 'f', '2026-09-12 13:35:28.947913', '2026-09-12 13:35:28.947913');
INSERT INTO "public"."sys_menu" VALUES (2405, '本体', 'kg:ontology:read', '/admin/kg-ontology', 2, 4, 2401, 'ApartmentOutlined', '/views/admin/knowledge/OntologyPanel.vue', 'kg-ontology', 0, 1, 0, 0, 'knowledge.menu.ontology', 'f', '2026-09-12 13:35:28.947913', '2026-09-12 13:35:28.947913');
INSERT INTO "public"."sys_menu" VALUES (4, '语音对话', '', '/admin/voice-demo', 2, 0, 2002, 'TeamOutlined', '/views/duplex/VoiceDemo.vue', 'voice-demo', 0, 1, 0, 0, 'sys.menu.ai-rtc', 'f', '2026-09-14 21:24:02.928505', '2026-09-27 16:20:13.04504');
INSERT INTO "public"."sys_menu" VALUES (2022, '会话管理', 'ai-assistant:sessions:read', '/admin/ai-sessions', 2, 200, 2002, 'CommentOutlined', '/views/assistant/AiSessionPanel.vue', '', 0, 1, 1, 0, 'sys.menu.ai-sessions', 'f', '2026-09-05 19:25:45.436047', '2026-09-14 21:28:58.74485');
INSERT INTO "public"."sys_menu" VALUES (2023, '异步任务', 'ai-assistant:async-task:read', '/admin/async-task-manage', 2, 100, 2002, 'ClockCircleOutlined', '/views/assistant/AsyncTaskManage.vue', '', 0, 1, 1, 0, 'sys.menu.async-task-manage', 'f', '2026-09-05 19:25:45.436047', '2026-09-14 21:29:07.14613');
INSERT INTO "public"."sys_menu" VALUES (2021, '智能对话', 'ai-assistant:chat:read', '/admin/ai-chat', 2, 3, 2002, 'MessageOutlined', '/views/assistant/components/AssistantPanel.vue', '', 0, 1, 1, 0, 'sys.menu.ai-chat', 'f', '2026-09-05 19:25:45.436047', '2026-09-14 21:29:14.006333');
