/*
 Navicat Premium Data Transfer

 Source Server         : pgvector-localhost
 Source Server Type    : PostgreSQL
 Source Server Version : 170011 (170011)
 Source Host           : localhost:5432
 Source Catalog        : minworkbuddy
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170011 (170011)
 File Encoding         : 65001

 Date: 08/09/2026 09:29:39
*/


-- ----------------------------
-- Sequence structure for agent_async_task_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_async_task_id_seq";
CREATE SEQUENCE "agent_async_task_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_config_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_config_id_seq";
CREATE SEQUENCE "agent_config_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_execution_event_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_execution_event_id_seq";
CREATE SEQUENCE "agent_execution_event_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_execution_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_execution_id_seq";
CREATE SEQUENCE "agent_execution_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_scheduled_task_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_scheduled_task_id_seq";
CREATE SEQUENCE "agent_scheduled_task_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_team_edge_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_team_edge_id_seq";
CREATE SEQUENCE "agent_team_edge_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_team_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_team_id_seq";
CREATE SEQUENCE "agent_team_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_team_intervention_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_team_intervention_id_seq";
CREATE SEQUENCE "agent_team_intervention_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_team_member_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_team_member_id_seq";
CREATE SEQUENCE "agent_team_member_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_team_run_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_team_run_id_seq";
CREATE SEQUENCE "agent_team_run_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_team_run_step_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_team_run_step_id_seq";
CREATE SEQUENCE "agent_team_run_step_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for agent_trace_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "agent_trace_id_seq";
CREATE SEQUENCE "agent_trace_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_api_key_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_api_key_id_seq";
CREATE SEQUENCE "ai_api_key_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_chat_message_message_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_chat_message_message_id_seq";
CREATE SEQUENCE "ai_chat_message_message_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_chat_model_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_chat_model_id_seq";
CREATE SEQUENCE "ai_chat_model_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_chat_session_session_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_chat_session_session_id_seq";
CREATE SEQUENCE "ai_chat_session_session_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_evolution_config_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_evolution_config_id_seq";
CREATE SEQUENCE "ai_skill_evolution_config_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_evolution_log_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_evolution_log_id_seq";
CREATE SEQUENCE "ai_skill_evolution_log_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_hub_repo_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_hub_repo_id_seq";
CREATE SEQUENCE "ai_skill_hub_repo_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_metrics_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_metrics_id_seq";
CREATE SEQUENCE "ai_skill_metrics_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_package_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_package_id_seq";
CREATE SEQUENCE "ai_skill_package_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_rule_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_rule_id_seq";
CREATE SEQUENCE "ai_skill_rule_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_script_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_script_id_seq";
CREATE SEQUENCE "ai_skill_script_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_skill_version_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_skill_version_id_seq";
CREATE SEQUENCE "ai_skill_version_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_web_search_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_web_search_id_seq";
CREATE SEQUENCE "ai_web_search_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_web_search_log_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_web_search_log_id_seq";
CREATE SEQUENCE "ai_web_search_log_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_workspace_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "ai_workspace_id_seq";
CREATE SEQUENCE "ai_workspace_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for infra_file_content_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "infra_file_content_id_seq";
CREATE SEQUENCE "infra_file_content_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for infra_file_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "infra_file_id_seq";
CREATE SEQUENCE "infra_file_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for kms_legal_item_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "kms_legal_item_id_seq";
CREATE SEQUENCE "kms_legal_item_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for kms_legal_paper_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "kms_legal_paper_id_seq";
CREATE SEQUENCE "kms_legal_paper_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for kms_legal_paper_legal_item_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "kms_legal_paper_legal_item_id_seq";
CREATE SEQUENCE "kms_legal_paper_legal_item_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for legal_info_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "legal_info_id_seq";
CREATE SEQUENCE "legal_info_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for mcp_api_key_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "mcp_api_key_id_seq";
CREATE SEQUENCE "mcp_api_key_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for mcp_client_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "mcp_client_id_seq";
CREATE SEQUENCE "mcp_client_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for mcp_square_template_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "mcp_square_template_id_seq";
CREATE SEQUENCE "mcp_square_template_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_audit_log_log_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_audit_log_log_id_seq";
CREATE SEQUENCE "sys_audit_log_log_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_dictionary_dict_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_dictionary_dict_id_seq";
CREATE SEQUENCE "sys_dictionary_dict_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_dictionary_item_item_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_dictionary_item_item_id_seq";
CREATE SEQUENCE "sys_dictionary_item_item_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_menu_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_menu_id_seq";
CREATE SEQUENCE "sys_menu_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_region_region_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_region_region_id_seq";
CREATE SEQUENCE "sys_region_region_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_role_menu_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_role_menu_id_seq";
CREATE SEQUENCE "sys_role_menu_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_role_role_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_role_role_id_seq";
CREATE SEQUENCE "sys_role_role_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_tenant_package_package_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_tenant_package_package_id_seq";
CREATE SEQUENCE "sys_tenant_package_package_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_tenant_tenant_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_tenant_tenant_id_seq";
CREATE SEQUENCE "sys_tenant_tenant_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_user_notification_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_user_notification_id_seq";
CREATE SEQUENCE "sys_user_notification_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_user_role_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_user_role_id_seq";
CREATE SEQUENCE "sys_user_role_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for sys_user_user_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "sys_user_user_id_seq";
CREATE SEQUENCE "sys_user_user_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tool_definition_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "tool_definition_id_seq";
CREATE SEQUENCE "tool_definition_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tool_group_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "tool_group_id_seq";
CREATE SEQUENCE "tool_group_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for wiki_article_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "wiki_article_id_seq";
CREATE SEQUENCE "wiki_article_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for wiki_article_version_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "wiki_article_version_id_seq";
CREATE SEQUENCE "wiki_article_version_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for wiki_category_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "wiki_category_id_seq";
CREATE SEQUENCE "wiki_category_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Table structure for agent_async_task
-- ----------------------------
DROP TABLE IF EXISTS "agent_async_task";
CREATE TABLE "agent_async_task" (
  "id" int4 NOT NULL DEFAULT nextval('agent_async_task_id_seq'::regclass),
  "task_no" varchar(64) COLLATE "pg_catalog"."default",
  "session_id" varchar(64) COLLATE "pg_catalog"."default",
  "user_id" int4 NOT NULL,
  "task_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "target_mode" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "payload" text COLLATE "pg_catalog"."default",
  "status" varchar(16) COLLATE "pg_catalog"."default" NOT NULL,
  "priority" int2 NOT NULL,
  "progress" float8 NOT NULL,
  "timeout_seconds" int4 NOT NULL,
  "max_retries" int2 NOT NULL,
  "retry_count" int2 NOT NULL,
  "execution_id" varchar(100) COLLATE "pg_catalog"."default",
  "result_data" text COLLATE "pg_catalog"."default",
  "error_message" text COLLATE "pg_catalog"."default",
  "log_ref" varchar(128) COLLATE "pg_catalog"."default",
  "cancel_requested" bool NOT NULL DEFAULT false,
  "submitted_at" timestamp(6) DEFAULT now(),
  "started_at" timestamp(6),
  "finished_at" timestamp(6),
  "created_at" timestamp(6) DEFAULT now(),
  "updated_at" timestamp(6) DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_async_task"."id" IS '任务ID';
COMMENT ON COLUMN "agent_async_task"."task_no" IS '任务编号(可读)';
COMMENT ON COLUMN "agent_async_task"."session_id" IS '归属会话ID';
COMMENT ON COLUMN "agent_async_task"."user_id" IS '提交用户ID';
COMMENT ON COLUMN "agent_async_task"."task_name" IS '任务名称';
COMMENT ON COLUMN "agent_async_task"."target_mode" IS '执行模式: agent/team/skill';
COMMENT ON COLUMN "agent_async_task"."payload" IS '执行参数(JSON: message/agent_id/team_id/skill 等)';
COMMENT ON COLUMN "agent_async_task"."status" IS 'queued/running/completed/failed/cancelled';
COMMENT ON COLUMN "agent_async_task"."priority" IS '优先级0-9(越大越优先)';
COMMENT ON COLUMN "agent_async_task"."progress" IS '进度百分比0-100';
COMMENT ON COLUMN "agent_async_task"."timeout_seconds" IS '超时秒数';
COMMENT ON COLUMN "agent_async_task"."max_retries" IS '最大重试次数';
COMMENT ON COLUMN "agent_async_task"."retry_count" IS '已重试次数';
COMMENT ON COLUMN "agent_async_task"."execution_id" IS '网关执行ID(启动即写入, 支持运行中实时回放执行事件)';
COMMENT ON COLUMN "agent_async_task"."result_data" IS '执行结果(JSON)';
COMMENT ON COLUMN "agent_async_task"."error_message" IS '错误信息';
COMMENT ON COLUMN "agent_async_task"."log_ref" IS '执行日志引用(TaskExecutionLog id等)';
COMMENT ON COLUMN "agent_async_task"."cancel_requested" IS '用户请求取消标记，执行中任务轮询该标记主动中断';
COMMENT ON COLUMN "agent_async_task"."submitted_at" IS '提交时间';
COMMENT ON COLUMN "agent_async_task"."started_at" IS '开始执行时间';
COMMENT ON COLUMN "agent_async_task"."finished_at" IS '结束时间';
COMMENT ON COLUMN "agent_async_task"."created_at" IS '创建时间';
COMMENT ON COLUMN "agent_async_task"."updated_at" IS '更新时间';
COMMENT ON COLUMN "agent_async_task"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_async_task
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_config
-- ----------------------------
DROP TABLE IF EXISTS "agent_config";
CREATE TABLE "agent_config" (
  "id" int8 NOT NULL DEFAULT nextval('agent_config_id_seq'::regclass),
  "agent_code" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "agent_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(50) COLLATE "pg_catalog"."default",
  "strategy_code" varchar(100) COLLATE "pg_catalog"."default",
  "execution_mode" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "system_prompt" text COLLATE "pg_catalog"."default",
  "tools" jsonb,
  "skills" jsonb,
  "mcp_servers" jsonb,
  "knowledge_bases" jsonb,
  "model_config" jsonb,
  "hitl_config" jsonb,
  "react_config" jsonb,
  "context_config" jsonb,
  "config" jsonb,
  "description" text COLLATE "pg_catalog"."default",
  "is_active" bool NOT NULL DEFAULT true,
  "sort_order" int4 NOT NULL DEFAULT 0,
  "workspace_id" int8,
  "created_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "is_deleted" bool NOT NULL DEFAULT false,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_config"."agent_code" IS '唯一标识码';
COMMENT ON COLUMN "agent_config"."name" IS 'Agent名称';
COMMENT ON COLUMN "agent_config"."agent_type" IS '实现类型: CHAT/WORKFLOW/SKILL';
COMMENT ON COLUMN "agent_config"."category" IS '用途分类（数据字典: agent_category）';
COMMENT ON COLUMN "agent_config"."strategy_code" IS '策略代码（数据字典: agent_strategy）';
COMMENT ON COLUMN "agent_config"."execution_mode" IS '执行模式';
COMMENT ON COLUMN "agent_config"."system_prompt" IS '系统提示词';
COMMENT ON COLUMN "agent_config"."tools" IS '可用工具列表';
COMMENT ON COLUMN "agent_config"."skills" IS '可用 Skill 列表';
COMMENT ON COLUMN "agent_config"."mcp_servers" IS 'MCP 服务器配置';
COMMENT ON COLUMN "agent_config"."knowledge_bases" IS '关联知识库 ID 列表';
COMMENT ON COLUMN "agent_config"."model_config" IS '模型配置 {provider, model, base_url, temperature, max_tokens}';
COMMENT ON COLUMN "agent_config"."hitl_config" IS 'HITL 配置 {enabled, confirm_tools, plan_approval}';
COMMENT ON COLUMN "agent_config"."react_config" IS 'ReAct 配置 {max_iters, timeout_seconds}';
COMMENT ON COLUMN "agent_config"."context_config" IS '上下文配置 {max_tokens, compression_enabled}';
COMMENT ON COLUMN "agent_config"."config" IS '类型特定配置';
COMMENT ON COLUMN "agent_config"."description" IS '描述';
COMMENT ON COLUMN "agent_config"."is_active" IS '是否启用';
COMMENT ON COLUMN "agent_config"."sort_order" IS '排序权重';
COMMENT ON COLUMN "agent_config"."workspace_id" IS '多租户隔离';
COMMENT ON COLUMN "agent_config"."created_by" IS '创建人ID';
COMMENT ON COLUMN "agent_config"."is_deleted" IS '软删除';
COMMENT ON COLUMN "agent_config"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_config
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_execution
-- ----------------------------
DROP TABLE IF EXISTS "agent_execution";
CREATE TABLE "agent_execution" (
  "id" int8 NOT NULL DEFAULT nextval('agent_execution_id_seq'::regclass),
  "execution_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "target_id" varchar(128) COLLATE "pg_catalog"."default",
  "session_id" int8,
  "user_id" int8,
  "execution_mode" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "user_input" text COLLATE "pg_catalog"."default",
  "output" text COLLATE "pg_catalog"."default",
  "error" text COLLATE "pg_catalog"."default",
  "trace_id" varchar(64) COLLATE "pg_catalog"."default",
  "started_at" timestamp(6),
  "completed_at" timestamp(6),
  "latency_ms" int4,
  "retry_count" int4 NOT NULL DEFAULT 0,
  "max_retries" int4 NOT NULL DEFAULT 3,
  "metadata_json" json,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_execution"."execution_id" IS '执行ID (UUID)';
COMMENT ON COLUMN "agent_execution"."target_id" IS '被执行对象ID（dify_flow/skill_package/agent_config/agent_team，sqlbot=0）';
COMMENT ON COLUMN "agent_execution"."session_id" IS '会话ID';
COMMENT ON COLUMN "agent_execution"."user_id" IS '用户ID';
COMMENT ON COLUMN "agent_execution"."execution_mode" IS '执行模式';
COMMENT ON COLUMN "agent_execution"."status" IS '状态';
COMMENT ON COLUMN "agent_execution"."user_input" IS '用户输入';
COMMENT ON COLUMN "agent_execution"."output" IS '执行输出';
COMMENT ON COLUMN "agent_execution"."error" IS '错误信息';
COMMENT ON COLUMN "agent_execution"."trace_id" IS '链路追踪ID';
COMMENT ON COLUMN "agent_execution"."started_at" IS '开始时间';
COMMENT ON COLUMN "agent_execution"."completed_at" IS '完成时间';
COMMENT ON COLUMN "agent_execution"."latency_ms" IS '耗时（毫秒）';
COMMENT ON COLUMN "agent_execution"."retry_count" IS '重试次数';
COMMENT ON COLUMN "agent_execution"."max_retries" IS '最大重试次数';
COMMENT ON COLUMN "agent_execution"."metadata_json" IS '执行元数据快照';
COMMENT ON COLUMN "agent_execution"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_execution
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_execution_event
-- ----------------------------
DROP TABLE IF EXISTS "agent_execution_event";
CREATE TABLE "agent_execution_event" (
  "id" int8 NOT NULL DEFAULT nextval('agent_execution_event_id_seq'::regclass),
  "execution_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "trace_id" varchar(64) COLLATE "pg_catalog"."default",
  "event_type" varchar(30) COLLATE "pg_catalog"."default" NOT NULL,
  "sequence" int4 NOT NULL,
  "content" json,
  "source" varchar(50) COLLATE "pg_catalog"."default",
  "source_id" varchar(100) COLLATE "pg_catalog"."default",
  "metadata" json,
  "created_at" timestamptz(6) DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_execution_event"."execution_id" IS '执行 ID';
COMMENT ON COLUMN "agent_execution_event"."trace_id" IS '链路追踪 ID';
COMMENT ON COLUMN "agent_execution_event"."event_type" IS '事件类型';
COMMENT ON COLUMN "agent_execution_event"."sequence" IS '事件序号';
COMMENT ON COLUMN "agent_execution_event"."content" IS '事件内容（根据类型结构化存储）';
COMMENT ON COLUMN "agent_execution_event"."source" IS '事件来源: agent/mcp/skill';
COMMENT ON COLUMN "agent_execution_event"."source_id" IS '来源标识';
COMMENT ON COLUMN "agent_execution_event"."metadata" IS '附加元数据';
COMMENT ON COLUMN "agent_execution_event"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_execution_event
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_scheduled_task
-- ----------------------------
DROP TABLE IF EXISTS "agent_scheduled_task";
CREATE TABLE "agent_scheduled_task" (
  "id" int4 NOT NULL DEFAULT nextval('agent_scheduled_task_id_seq'::regclass),
  "task_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" int4 NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "target_mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "agent_id" int4,
  "team_id" int4,
  "skill_info" text COLLATE "pg_catalog"."default",
  "prompt" text COLLATE "pg_catalog"."default" NOT NULL,
  "session_id" varchar(64) COLLATE "pg_catalog"."default",
  "model_id" int4,
  "schedule_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "cron_expression" varchar(100) COLLATE "pg_catalog"."default",
  "interval_seconds" int4,
  "run_at" timestamp(6),
  "timezone" varchar(50) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'Asia/Shanghai'::character varying,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'enabled'::character varying,
  "last_run_at" timestamp(6),
  "next_run_at" timestamp(6),
  "last_task_id" int4,
  "run_count" int4 NOT NULL DEFAULT 0,
  "fail_count" int4 NOT NULL DEFAULT 0,
  "created_at" timestamp(6) DEFAULT now(),
  "updated_at" timestamp(6) DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_scheduled_task"."id" IS '调度ID';
COMMENT ON COLUMN "agent_scheduled_task"."task_name" IS '调度任务名称';
COMMENT ON COLUMN "agent_scheduled_task"."user_id" IS '归属用户ID';
COMMENT ON COLUMN "agent_scheduled_task"."description" IS '任务描述';
COMMENT ON COLUMN "agent_scheduled_task"."target_mode" IS '执行模式: deep_research/agent/team';
COMMENT ON COLUMN "agent_scheduled_task"."agent_id" IS 'agent 模式：目标智能体ID';
COMMENT ON COLUMN "agent_scheduled_task"."team_id" IS 'team 模式：目标专家团ID(空=默认团队)';
COMMENT ON COLUMN "agent_scheduled_task"."skill_info" IS 'skill 模式：技能信息(JSON: package_id/package_name/script_id/script_name/params)';
COMMENT ON COLUMN "agent_scheduled_task"."prompt" IS '执行输入(深度研究=研究主题, agent/team=指令)';
COMMENT ON COLUMN "agent_scheduled_task"."session_id" IS '关联会话ID';
COMMENT ON COLUMN "agent_scheduled_task"."model_id" IS '指定模型ID(空=默认文本模型)';
COMMENT ON COLUMN "agent_scheduled_task"."schedule_type" IS '调度类型: cron/interval/once';
COMMENT ON COLUMN "agent_scheduled_task"."cron_expression" IS 'Cron 表达式(5段: 分 时 日 月 周)';
COMMENT ON COLUMN "agent_scheduled_task"."interval_seconds" IS '间隔秒数(interval 类型, 最小60)';
COMMENT ON COLUMN "agent_scheduled_task"."run_at" IS '单次执行时间(once 类型)';
COMMENT ON COLUMN "agent_scheduled_task"."timezone" IS '时区';
COMMENT ON COLUMN "agent_scheduled_task"."status" IS 'enabled/paused/deleted';
COMMENT ON COLUMN "agent_scheduled_task"."last_run_at" IS '最近触发时间';
COMMENT ON COLUMN "agent_scheduled_task"."next_run_at" IS '下次触发时间(调度器回填)';
COMMENT ON COLUMN "agent_scheduled_task"."last_task_id" IS '最近生成的异步任务ID';
COMMENT ON COLUMN "agent_scheduled_task"."run_count" IS '累计触发次数';
COMMENT ON COLUMN "agent_scheduled_task"."fail_count" IS '触发失败次数';
COMMENT ON COLUMN "agent_scheduled_task"."created_at" IS '创建时间';
COMMENT ON COLUMN "agent_scheduled_task"."updated_at" IS '更新时间';
COMMENT ON COLUMN "agent_scheduled_task"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_scheduled_task
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_team
-- ----------------------------
DROP TABLE IF EXISTS "agent_team";
CREATE TABLE "agent_team" (
  "id" int8 NOT NULL DEFAULT nextval('agent_team_id_seq'::regclass),
  "team_code" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "category" varchar(50) COLLATE "pg_catalog"."default",
  "mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'sequential'::character varying,
  "execution_mode" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'llm_orchestrated'::character varying,
  "graph" jsonb,
  "shared_knowledge_bases" jsonb,
  "shared_tools" jsonb,
  "run_config" jsonb,
  "is_active" bool NOT NULL DEFAULT true,
  "sort_order" int4 NOT NULL DEFAULT 0,
  "workspace_id" int8,
  "created_by" int8,
  "updated_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "is_deleted" bool NOT NULL DEFAULT false,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_team"."team_code" IS '唯一标识码';
COMMENT ON COLUMN "agent_team"."name" IS '团队名称';
COMMENT ON COLUMN "agent_team"."description" IS '描述';
COMMENT ON COLUMN "agent_team"."category" IS '用途分类（数据字典: agent_team_category）';
COMMENT ON COLUMN "agent_team"."mode" IS '协作模式（来源模板）: sequential/parallel/msghub/supervisor/dag';
COMMENT ON COLUMN "agent_team"."execution_mode" IS '执行模式: llm_orchestrated(生效) / static_dag(废弃回放)';
COMMENT ON COLUMN "agent_team"."graph" IS '画布快照 {nodes:[{node_key,x,y}], viewport:{x,y,zoom}}';
COMMENT ON COLUMN "agent_team"."shared_knowledge_bases" IS '团队共享知识库 ID 列表（全员可访问）';
COMMENT ON COLUMN "agent_team"."shared_tools" IS '团队共享工具列表';
COMMENT ON COLUMN "agent_team"."run_config" IS '运行配置 {max_rounds, max_parallel, node_timeout_seconds, node_timeout_per_batch, node_timeout_max, total_timeout_seconds, on_node_error, supervisor_node_key, aggregator_node_key, allow_intervention, persist_events}';
COMMENT ON COLUMN "agent_team"."is_active" IS '是否启用';
COMMENT ON COLUMN "agent_team"."sort_order" IS '排序权重';
COMMENT ON COLUMN "agent_team"."workspace_id" IS '多租户隔离';
COMMENT ON COLUMN "agent_team"."created_by" IS '创建人ID';
COMMENT ON COLUMN "agent_team"."updated_by" IS '最后修改人ID';
COMMENT ON COLUMN "agent_team"."is_deleted" IS '软删除';
COMMENT ON COLUMN "agent_team"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_team
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_team_edge
-- ----------------------------
DROP TABLE IF EXISTS "agent_team_edge";
CREATE TABLE "agent_team_edge" (
  "id" int8 NOT NULL DEFAULT nextval('agent_team_edge_id_seq'::regclass),
  "team_id" int8 NOT NULL,
  "from_node_key" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "to_node_key" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "label" varchar(100) COLLATE "pg_catalog"."default",
  "condition" text COLLATE "pg_catalog"."default",
  "sort_order" int4 NOT NULL DEFAULT 0,
  "edge_config" jsonb,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_team_edge"."team_id" IS '所属团队 agent_team.id';
COMMENT ON COLUMN "agent_team_edge"."from_node_key" IS '上游节点 node_key；''__START__'' 表示虚拟入口';
COMMENT ON COLUMN "agent_team_edge"."to_node_key" IS '下游节点 node_key；''__END__'' 表示虚拟出口';
COMMENT ON COLUMN "agent_team_edge"."label" IS '边标签（展示用）';
COMMENT ON COLUMN "agent_team_edge"."condition" IS '条件边表达式（预留，为空=无条件）';
COMMENT ON COLUMN "agent_team_edge"."sort_order" IS '同一 to_node 的多上游拼接顺序';
COMMENT ON COLUMN "agent_team_edge"."edge_config" IS '边的前端样式等附加配置';
COMMENT ON COLUMN "agent_team_edge"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_team_edge
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_team_intervention
-- ----------------------------
DROP TABLE IF EXISTS "agent_team_intervention";
CREATE TABLE "agent_team_intervention" (
  "id" int8 NOT NULL DEFAULT nextval('agent_team_intervention_id_seq'::regclass),
  "run_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "intervention_type" varchar(30) COLLATE "pg_catalog"."default" NOT NULL,
  "node_key" varchar(64) COLLATE "pg_catalog"."default",
  "round_no" int4,
  "payload" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "applied_at" timestamp(6),
  "reject_reason" text COLLATE "pg_catalog"."default",
  "operator_id" int8,
  "operator_name" varchar(100) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_team_intervention"."run_id" IS '所属运行 agent_team_run.run_id';
COMMENT ON COLUMN "agent_team_intervention"."intervention_type" IS 'pause/resume/cancel/edit_output/retry_node/skip_node/inject_message/answer_ask';
COMMENT ON COLUMN "agent_team_intervention"."node_key" IS '目标节点（节点级介入必填）';
COMMENT ON COLUMN "agent_team_intervention"."round_no" IS '目标轮次';
COMMENT ON COLUMN "agent_team_intervention"."payload" IS '介入内容 {content, reason, ...}';
COMMENT ON COLUMN "agent_team_intervention"."status" IS 'pending/applied/expired/rejected';
COMMENT ON COLUMN "agent_team_intervention"."applied_at" IS '被执行引擎消费的时间';
COMMENT ON COLUMN "agent_team_intervention"."reject_reason" IS '拒绝/过期原因';
COMMENT ON COLUMN "agent_team_intervention"."operator_id" IS '操作人ID';
COMMENT ON COLUMN "agent_team_intervention"."operator_name" IS '操作人名称（快照）';
COMMENT ON COLUMN "agent_team_intervention"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_team_intervention
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_team_member
-- ----------------------------
DROP TABLE IF EXISTS "agent_team_member";
CREATE TABLE "agent_team_member" (
  "id" int8 NOT NULL DEFAULT nextval('agent_team_member_id_seq'::regclass),
  "team_id" int8 NOT NULL,
  "agent_config_id" int8 NOT NULL,
  "node_key" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "role_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "role_desc" text COLLATE "pg_catalog"."default",
  "avatar" varchar(200) COLLATE "pg_catalog"."default",
  "sort_order" int4 NOT NULL DEFAULT 0,
  "override_system_prompt" text COLLATE "pg_catalog"."default",
  "override_llm_config" jsonb,
  "override_knowledge_bases" jsonb,
  "override_tools" jsonb,
  "override_skills" jsonb,
  "tool_preset" jsonb,
  "node_config" jsonb,
  "is_active" bool NOT NULL DEFAULT true,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_team_member"."team_id" IS '所属团队 agent_team.id';
COMMENT ON COLUMN "agent_team_member"."agent_config_id" IS '引用 agent_config.id';
COMMENT ON COLUMN "agent_team_member"."node_key" IS '节点标识（团队内唯一，供边引用/@提及，如 ''researcher''）';
COMMENT ON COLUMN "agent_team_member"."role_name" IS '团队内角色名（展示用，如 ''风险研判专家''）';
COMMENT ON COLUMN "agent_team_member"."role_desc" IS '角色职责说明，注入 prompt 供其他成员理解分工';
COMMENT ON COLUMN "agent_team_member"."avatar" IS '头像/图标';
COMMENT ON COLUMN "agent_team_member"."sort_order" IS '顺序（sequential 模式的执行序）';
COMMENT ON COLUMN "agent_team_member"."override_system_prompt" IS '覆盖系统提示词';
COMMENT ON COLUMN "agent_team_member"."override_llm_config" IS '覆盖模型配置（深合并，可只改 temperature）';
COMMENT ON COLUMN "agent_team_member"."override_knowledge_bases" IS '覆盖知识库 ID 列表';
COMMENT ON COLUMN "agent_team_member"."override_tools" IS '覆盖工具列表';
COMMENT ON COLUMN "agent_team_member"."override_skills" IS '覆盖技能列表';
COMMENT ON COLUMN "agent_team_member"."tool_preset" IS 'TeamSay 工具预设：单点追问时可被 @提及 调起的成员 node_key 列表；NULL = 使用团队全部成员';
COMMENT ON COLUMN "agent_team_member"."node_config" IS '节点配置 {input_mode, input_template, output_key, condition, retry, timeout_seconds, is_entry, is_terminal}';
COMMENT ON COLUMN "agent_team_member"."is_active" IS '是否启用';
COMMENT ON COLUMN "agent_team_member"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_team_member
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_team_run
-- ----------------------------
DROP TABLE IF EXISTS "agent_team_run";
CREATE TABLE "agent_team_run" (
  "id" int8 NOT NULL DEFAULT nextval('agent_team_run_id_seq'::regclass),
  "run_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "team_id" int8 NOT NULL,
  "conversation_id" varchar(64) COLLATE "pg_catalog"."default",
  "team_snapshot" jsonb NOT NULL,
  "input_text" text COLLATE "pg_catalog"."default",
  "input_context" jsonb,
  "final_output" text COLLATE "pg_catalog"."default",
  "node_outputs" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "current_round" int4 NOT NULL DEFAULT 0,
  "current_nodes" jsonb,
  "error_message" text COLLATE "pg_catalog"."default",
  "total_tokens" int4 NOT NULL DEFAULT 0,
  "total_steps" int4 NOT NULL DEFAULT 0,
  "duration_ms" int4,
  "trigger_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'manual'::character varying,
  "parent_run_id" varchar(64) COLLATE "pg_catalog"."default",
  "branch_from_node" varchar(64) COLLATE "pg_catalog"."default",
  "workspace_id" int8,
  "created_by" int8,
  "started_at" timestamp(6),
  "finished_at" timestamp(6),
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_team_run"."run_id" IS '运行唯一标识（UUID），同时作为 agent_execution_event.execution_id';
COMMENT ON COLUMN "agent_team_run"."team_id" IS '所属团队 agent_team.id';
COMMENT ON COLUMN "agent_team_run"."conversation_id" IS '关联会话ID';
COMMENT ON COLUMN "agent_team_run"."team_snapshot" IS '团队配置快照 {team:{...}, members:[...], edges:[...], run_config:{...}}';
COMMENT ON COLUMN "agent_team_run"."input_text" IS '用户原始输入';
COMMENT ON COLUMN "agent_team_run"."input_context" IS '附加上下文（文件、变量等）';
COMMENT ON COLUMN "agent_team_run"."final_output" IS '团队最终输出';
COMMENT ON COLUMN "agent_team_run"."node_outputs" IS '各节点输出汇总 {node_key: output}';
COMMENT ON COLUMN "agent_team_run"."status" IS 'pending/running/paused/success/failed/cancelled';
COMMENT ON COLUMN "agent_team_run"."current_round" IS '当前轮次（msghub/supervisor 模式）';
COMMENT ON COLUMN "agent_team_run"."current_nodes" IS '当前正在执行的节点 node_key 列表';
COMMENT ON COLUMN "agent_team_run"."error_message" IS '失败原因';
COMMENT ON COLUMN "agent_team_run"."total_tokens" IS '累计 token 消耗';
COMMENT ON COLUMN "agent_team_run"."total_steps" IS '累计节点执行次数';
COMMENT ON COLUMN "agent_team_run"."duration_ms" IS '总耗时（毫秒）';
COMMENT ON COLUMN "agent_team_run"."trigger_type" IS 'manual/api/schedule/replay';
COMMENT ON COLUMN "agent_team_run"."parent_run_id" IS '分支重跑时的父运行 run_id';
COMMENT ON COLUMN "agent_team_run"."branch_from_node" IS '分支重跑的起始节点 node_key';
COMMENT ON COLUMN "agent_team_run"."workspace_id" IS '多租户隔离';
COMMENT ON COLUMN "agent_team_run"."created_by" IS '发起人ID';
COMMENT ON COLUMN "agent_team_run"."started_at" IS '开始执行时间';
COMMENT ON COLUMN "agent_team_run"."finished_at" IS '结束时间';
COMMENT ON COLUMN "agent_team_run"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_team_run
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_team_run_step
-- ----------------------------
DROP TABLE IF EXISTS "agent_team_run_step";
CREATE TABLE "agent_team_run_step" (
  "id" int8 NOT NULL DEFAULT nextval('agent_team_run_step_id_seq'::regclass),
  "run_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "node_key" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "role_name" varchar(100) COLLATE "pg_catalog"."default",
  "agent_config_id" int8,
  "round_no" int4 NOT NULL DEFAULT 0,
  "layer_no" int4,
  "seq" int4 NOT NULL DEFAULT 0,
  "input_text" text COLLATE "pg_catalog"."default",
  "upstream_nodes" jsonb,
  "output_text" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "error_message" text COLLATE "pg_catalog"."default",
  "retry_count" int4 NOT NULL DEFAULT 0,
  "tokens" int4 NOT NULL DEFAULT 0,
  "duration_ms" int4,
  "extra_data" jsonb,
  "started_at" timestamp(6),
  "finished_at" timestamp(6),
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_team_run_step"."run_id" IS '所属运行 agent_team_run.run_id';
COMMENT ON COLUMN "agent_team_run_step"."node_key" IS '节点标识';
COMMENT ON COLUMN "agent_team_run_step"."role_name" IS '角色名（快照，防止团队改名后失真）';
COMMENT ON COLUMN "agent_team_run_step"."agent_config_id" IS '实际执行的 agent_config.id';
COMMENT ON COLUMN "agent_team_run_step"."round_no" IS '轮次（动态模式下同节点可多次执行）';
COMMENT ON COLUMN "agent_team_run_step"."layer_no" IS 'DAG 拓扑层号（同层并行）';
COMMENT ON COLUMN "agent_team_run_step"."seq" IS '全局执行序号';
COMMENT ON COLUMN "agent_team_run_step"."input_text" IS '合并后的实际输入';
COMMENT ON COLUMN "agent_team_run_step"."upstream_nodes" IS '上游节点 node_key 列表';
COMMENT ON COLUMN "agent_team_run_step"."output_text" IS '节点输出';
COMMENT ON COLUMN "agent_team_run_step"."status" IS 'pending/running/success/failed/skipped/intervened';
COMMENT ON COLUMN "agent_team_run_step"."error_message" IS '失败原因';
COMMENT ON COLUMN "agent_team_run_step"."retry_count" IS '重试次数';
COMMENT ON COLUMN "agent_team_run_step"."tokens" IS 'token 消耗';
COMMENT ON COLUMN "agent_team_run_step"."duration_ms" IS '耗时（毫秒）';
COMMENT ON COLUMN "agent_team_run_step"."extra_data" IS '扩展信息（工具调用摘要、引用来源等）';
COMMENT ON COLUMN "agent_team_run_step"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_team_run_step
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for agent_trace
-- ----------------------------
DROP TABLE IF EXISTS "agent_trace";
CREATE TABLE "agent_trace" (
  "id" int8 NOT NULL DEFAULT nextval('agent_trace_id_seq'::regclass),
  "trace_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "session_id" int8,
  "user_id" int8,
  "agent_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "agent_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "input_prompt" text COLLATE "pg_catalog"."default",
  "output_result" text COLLATE "pg_catalog"."default",
  "skills_used" jsonb,
  "tools_used" jsonb,
  "error" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'OK'::character varying,
  "start_time" timestamp(6) NOT NULL DEFAULT now(),
  "end_time" timestamp(6),
  "duration_ms" int4,
  "metadata" jsonb,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "agent_config_id" int8,
  "team_config_id" int8,
  "workspace_config_id" int8,
  "component_ids" jsonb,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "agent_trace"."trace_id" IS '链路ID';
COMMENT ON COLUMN "agent_trace"."session_id" IS '会话ID';
COMMENT ON COLUMN "agent_trace"."user_id" IS '用户ID';
COMMENT ON COLUMN "agent_trace"."agent_id" IS 'Agent ID';
COMMENT ON COLUMN "agent_trace"."agent_type" IS 'Agent类型';
COMMENT ON COLUMN "agent_trace"."input_prompt" IS '输入提示词';
COMMENT ON COLUMN "agent_trace"."output_result" IS '输出结果';
COMMENT ON COLUMN "agent_trace"."skills_used" IS '使用的Skill列表';
COMMENT ON COLUMN "agent_trace"."tools_used" IS '使用的工具列表';
COMMENT ON COLUMN "agent_trace"."error" IS '错误信息';
COMMENT ON COLUMN "agent_trace"."status" IS '状态: OK/ERROR';
COMMENT ON COLUMN "agent_trace"."start_time" IS '开始时间';
COMMENT ON COLUMN "agent_trace"."end_time" IS '结束时间';
COMMENT ON COLUMN "agent_trace"."duration_ms" IS '执行耗时(毫秒)';
COMMENT ON COLUMN "agent_trace"."metadata" IS '扩展元数据';
COMMENT ON COLUMN "agent_trace"."agent_config_id" IS '关联 Agent 配置 ID';
COMMENT ON COLUMN "agent_trace"."team_config_id" IS '关联 Team 配置 ID';
COMMENT ON COLUMN "agent_trace"."workspace_config_id" IS '关联 Workspace 配置 ID';
COMMENT ON COLUMN "agent_trace"."component_ids" IS '关联组件 ID 集合 {"skill": [...], "tool": [...]}';
COMMENT ON COLUMN "agent_trace"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of agent_trace
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_api_key
-- ----------------------------
DROP TABLE IF EXISTS "ai_api_key";
CREATE TABLE "ai_api_key" (
  "id" int4 NOT NULL DEFAULT nextval('ai_api_key_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "api_key" text COLLATE "pg_catalog"."default" NOT NULL,
  "platform" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "url" varchar(500) COLLATE "pg_catalog"."default",
  "app_id" varchar(100) COLLATE "pg_catalog"."default",
  "property" json,
  "status" int4 NOT NULL DEFAULT 1,
  "sort" int4 NOT NULL DEFAULT 0,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6),
  "creator" varchar(64) COLLATE "pg_catalog"."default",
  "updater" varchar(64) COLLATE "pg_catalog"."default",
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_api_key"."name" IS '密钥名称';
COMMENT ON COLUMN "ai_api_key"."api_key" IS 'API Key';
COMMENT ON COLUMN "ai_api_key"."platform" IS '平台: OpenAI/通义千问/智谱/讯飞等';
COMMENT ON COLUMN "ai_api_key"."url" IS 'API 地址';
COMMENT ON COLUMN "ai_api_key"."app_id" IS 'AppId';
COMMENT ON COLUMN "ai_api_key"."property" IS '配置属性';
COMMENT ON COLUMN "ai_api_key"."status" IS '状态: 1=启用, 0=禁用';
COMMENT ON COLUMN "ai_api_key"."sort" IS '排序';
COMMENT ON COLUMN "ai_api_key"."creator" IS '创建人';
COMMENT ON COLUMN "ai_api_key"."updater" IS '更新人';
COMMENT ON COLUMN "ai_api_key"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_api_key
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_chat_message
-- ----------------------------
DROP TABLE IF EXISTS "ai_chat_message";
CREATE TABLE "ai_chat_message" (
  "message_id" int8 NOT NULL DEFAULT nextval('ai_chat_message_message_id_seq'::regclass),
  "session_id" int8 NOT NULL,
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "message_type" varchar(20) COLLATE "pg_catalog"."default",
  "tool_calls" json,
  "tool_results" json,
  "extra_data" json,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "file_id" int8,
  "agent_id" varchar(50) COLLATE "pg_catalog"."default",
  "execution_time_ms" int4,
  "execution_id" varchar(64) COLLATE "pg_catalog"."default",
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_chat_message"."message_id" IS '消息ID';
COMMENT ON COLUMN "ai_chat_message"."session_id" IS '会话ID';
COMMENT ON COLUMN "ai_chat_message"."role" IS '角色：user-用户, assistant-AI助理, system-系统';
COMMENT ON COLUMN "ai_chat_message"."content" IS '消息内容';
COMMENT ON COLUMN "ai_chat_message"."message_type" IS '消息类型：text-文本, chart-图表, table-表格';
COMMENT ON COLUMN "ai_chat_message"."tool_calls" IS '工具调用';
COMMENT ON COLUMN "ai_chat_message"."tool_results" IS '工具结果';
COMMENT ON COLUMN "ai_chat_message"."extra_data" IS '扩展数据';
COMMENT ON COLUMN "ai_chat_message"."created_at" IS '创建时间';
COMMENT ON COLUMN "ai_chat_message"."file_id" IS '文件ID（关联 infra_file.id）';
COMMENT ON COLUMN "ai_chat_message"."agent_id" IS '执行此消息的 Agent ID';
COMMENT ON COLUMN "ai_chat_message"."execution_time_ms" IS '执行耗时(毫秒)';
COMMENT ON COLUMN "ai_chat_message"."execution_id" IS '关联 agent_execution.execution_id';
COMMENT ON COLUMN "ai_chat_message"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_chat_message
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_chat_model
-- ----------------------------
DROP TABLE IF EXISTS "ai_chat_model";
CREATE TABLE "ai_chat_model" (
  "id" int4 NOT NULL DEFAULT nextval('ai_chat_model_id_seq'::regclass),
  "code" varchar(100) COLLATE "pg_catalog"."default",
  "key_id" int4 NOT NULL,
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "model" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "platform" varchar(50) COLLATE "pg_catalog"."default",
  "sort" int4 NOT NULL DEFAULT 0,
  "status" int4 NOT NULL DEFAULT 1,
  "type" int4,
  "temperature" float8,
  "max_tokens" int4,
  "top_k" int4,
  "top_p" float8,
  "seed" int4,
  "max_contexts" int4,
  "max_turns" int4,
  "dimensions" int4,
  "retry" int4,
  "timeout" int4,
  "stream_timeout" int4,
  "enable_thinking" bool,
  "enable_search" bool,
  "is_default" bool,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_chat_model"."code" IS '模型编码';
COMMENT ON COLUMN "ai_chat_model"."key_id" IS 'API 密钥编号';
COMMENT ON COLUMN "ai_chat_model"."name" IS '模型名称';
COMMENT ON COLUMN "ai_chat_model"."model" IS '模型标志/模型ID';
COMMENT ON COLUMN "ai_chat_model"."platform" IS '平台';
COMMENT ON COLUMN "ai_chat_model"."sort" IS '排序';
COMMENT ON COLUMN "ai_chat_model"."status" IS '状态: 1=启用, 0=禁用';
COMMENT ON COLUMN "ai_chat_model"."type" IS '类型';
COMMENT ON COLUMN "ai_chat_model"."temperature" IS '温度参数';
COMMENT ON COLUMN "ai_chat_model"."max_tokens" IS '最大 Token 数';
COMMENT ON COLUMN "ai_chat_model"."top_k" IS '保留概率最高的 k 个单词';
COMMENT ON COLUMN "ai_chat_model"."top_p" IS '累积概率阈值 p';
COMMENT ON COLUMN "ai_chat_model"."seed" IS '随机种子';
COMMENT ON COLUMN "ai_chat_model"."max_contexts" IS '上下文最大 Message 数';
COMMENT ON COLUMN "ai_chat_model"."max_turns" IS '最大轮次';
COMMENT ON COLUMN "ai_chat_model"."dimensions" IS '维度';
COMMENT ON COLUMN "ai_chat_model"."retry" IS '重试次数';
COMMENT ON COLUMN "ai_chat_model"."timeout" IS '超时时间(秒)';
COMMENT ON COLUMN "ai_chat_model"."stream_timeout" IS '流式超时(秒)';
COMMENT ON COLUMN "ai_chat_model"."enable_thinking" IS '支持思考';
COMMENT ON COLUMN "ai_chat_model"."enable_search" IS '支持搜索';
COMMENT ON COLUMN "ai_chat_model"."is_default" IS '是否默认模型';
COMMENT ON COLUMN "ai_chat_model"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_chat_model
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_chat_session
-- ----------------------------
DROP TABLE IF EXISTS "ai_chat_session";
CREATE TABLE "ai_chat_session" (
  "session_id" int8 NOT NULL DEFAULT nextval('ai_chat_session_session_id_seq'::regclass),
  "user_id" int8 NOT NULL,
  "session_title" varchar(200) COLLATE "pg_catalog"."default",
  "session_type" varchar(50) COLLATE "pg_catalog"."default",
  "context_data" json,
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "message_count" int4,
  "is_pinned" bool,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "agent_id" varchar(50) COLLATE "pg_catalog"."default",
  "context_version" int4 NOT NULL,
  "agent_mode" varchar(32) COLLATE "pg_catalog"."default",
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_chat_session"."session_id" IS '会话ID';
COMMENT ON COLUMN "ai_chat_session"."user_id" IS '用户ID';
COMMENT ON COLUMN "ai_chat_session"."session_title" IS '会话标题';
COMMENT ON COLUMN "ai_chat_session"."session_type" IS '会话类型：general-通用对话, thinking-深度思考, deep_research-深度研究, skill-技能模式, agent-专家Agent, team-专家团';
COMMENT ON COLUMN "ai_chat_session"."context_data" IS '上下文数据';
COMMENT ON COLUMN "ai_chat_session"."status" IS '状态：active-活跃, archived-归档';
COMMENT ON COLUMN "ai_chat_session"."message_count" IS '消息数量';
COMMENT ON COLUMN "ai_chat_session"."is_pinned" IS '是否置顶';
COMMENT ON COLUMN "ai_chat_session"."created_at" IS '创建时间';
COMMENT ON COLUMN "ai_chat_session"."updated_at" IS '更新时间';
COMMENT ON COLUMN "ai_chat_session"."agent_id" IS '关联的 Agent 配置 ID';
COMMENT ON COLUMN "ai_chat_session"."context_version" IS '上下文版本号';
COMMENT ON COLUMN "ai_chat_session"."agent_mode" IS 'AgentScope 执行模式：skill/agent/team/thinking/deep_research/scheduled';
COMMENT ON COLUMN "ai_chat_session"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_chat_session
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_mcp_api_key
-- ----------------------------
DROP TABLE IF EXISTS "ai_mcp_api_key";
CREATE TABLE "ai_mcp_api_key" (
  "id" int8 NOT NULL DEFAULT nextval('mcp_api_key_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "service_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "platform" varchar(50) COLLATE "pg_catalog"."default",
  "protocol_type" varchar(50) COLLATE "pg_catalog"."default",
  "version" varchar(20) COLLATE "pg_catalog"."default",
  "description" varchar(2000) COLLATE "pg_catalog"."default",
  "service_url" varchar(500) COLLATE "pg_catalog"."default",
  "service_name" varchar(200) COLLATE "pg_catalog"."default",
  "api_key" varchar(500) COLLATE "pg_catalog"."default",
  "namespace" varchar(200) COLLATE "pg_catalog"."default",
  "group_key" varchar(200) COLLATE "pg_catalog"."default",
  "access_path" varchar(500) COLLATE "pg_catalog"."default",
  "properties" json,
  "capabilities" json,
  "remark" text COLLATE "pg_catalog"."default",
  "status" int4 NOT NULL DEFAULT 1,
  "sort" int4 NOT NULL DEFAULT 0,
  "template_id" int8 NOT NULL DEFAULT '0'::bigint,
  "health_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'unknown'::character varying,
  "last_check_at" timestamp(6),
  "creator" varchar(100) COLLATE "pg_catalog"."default",
  "updater" varchar(100) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_mcp_api_key"."id" IS '主键';
COMMENT ON COLUMN "ai_mcp_api_key"."name" IS '密钥名称';
COMMENT ON COLUMN "ai_mcp_api_key"."service_type" IS '服务类型: nacos2/nacos3/http/sse';
COMMENT ON COLUMN "ai_mcp_api_key"."platform" IS '平台: local/remote';
COMMENT ON COLUMN "ai_mcp_api_key"."protocol_type" IS '协议类型(自动推导)';
COMMENT ON COLUMN "ai_mcp_api_key"."version" IS 'MCP协议版本';
COMMENT ON COLUMN "ai_mcp_api_key"."description" IS '描述信息';
COMMENT ON COLUMN "ai_mcp_api_key"."service_url" IS '服务地址';
COMMENT ON COLUMN "ai_mcp_api_key"."service_name" IS 'Nacos服务名';
COMMENT ON COLUMN "ai_mcp_api_key"."api_key" IS '鉴权密钥';
COMMENT ON COLUMN "ai_mcp_api_key"."namespace" IS 'Nacos命名空间';
COMMENT ON COLUMN "ai_mcp_api_key"."group_key" IS 'Nacos分组';
COMMENT ON COLUMN "ai_mcp_api_key"."access_path" IS 'HTTP/SSE访问路径';
COMMENT ON COLUMN "ai_mcp_api_key"."properties" IS '扩展属性';
COMMENT ON COLUMN "ai_mcp_api_key"."capabilities" IS '能力列表';
COMMENT ON COLUMN "ai_mcp_api_key"."remark" IS '备注';
COMMENT ON COLUMN "ai_mcp_api_key"."status" IS '1=启用,0=禁用';
COMMENT ON COLUMN "ai_mcp_api_key"."sort" IS '排序';
COMMENT ON COLUMN "ai_mcp_api_key"."template_id" IS '广场模板ID';
COMMENT ON COLUMN "ai_mcp_api_key"."health_status" IS '健康状态: healthy/unhealthy/unknown';
COMMENT ON COLUMN "ai_mcp_api_key"."last_check_at" IS '最近一次连接检测时间';
COMMENT ON COLUMN "ai_mcp_api_key"."creator" IS '创建人';
COMMENT ON COLUMN "ai_mcp_api_key"."updater" IS '更新人';
COMMENT ON COLUMN "ai_mcp_api_key"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_mcp_api_key
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_mcp_client
-- ----------------------------
DROP TABLE IF EXISTS "ai_mcp_client";
CREATE TABLE "ai_mcp_client" (
  "id" int8 NOT NULL DEFAULT nextval('mcp_client_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "api_key_id" int8 NOT NULL,
  "client_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "mcp_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "version" varchar(20) COLLATE "pg_catalog"."default",
  "description" varchar(2000) COLLATE "pg_catalog"."default",
  "tools_config" json,
  "remark" text COLLATE "pg_catalog"."default",
  "status" int4 NOT NULL DEFAULT 1,
  "is_active" bool NOT NULL DEFAULT true,
  "creator" varchar(100) COLLATE "pg_catalog"."default",
  "updater" varchar(100) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_mcp_client"."id" IS '主键';
COMMENT ON COLUMN "ai_mcp_client"."name" IS '客户端名称';
COMMENT ON COLUMN "ai_mcp_client"."api_key_id" IS '关联API Key';
COMMENT ON COLUMN "ai_mcp_client"."client_type" IS '客户端类型: stdio/http/sse';
COMMENT ON COLUMN "ai_mcp_client"."mcp_type" IS '应用类别: tool/resource';
COMMENT ON COLUMN "ai_mcp_client"."version" IS '客户端版本';
COMMENT ON COLUMN "ai_mcp_client"."description" IS '描述';
COMMENT ON COLUMN "ai_mcp_client"."tools_config" IS '工具配置';
COMMENT ON COLUMN "ai_mcp_client"."remark" IS '备注';
COMMENT ON COLUMN "ai_mcp_client"."status" IS '1=启用,0=禁用';
COMMENT ON COLUMN "ai_mcp_client"."is_active" IS '是否启用';
COMMENT ON COLUMN "ai_mcp_client"."creator" IS '创建人';
COMMENT ON COLUMN "ai_mcp_client"."updater" IS '更新人';
COMMENT ON COLUMN "ai_mcp_client"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_mcp_client
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_mcp_square_template
-- ----------------------------
DROP TABLE IF EXISTS "ai_mcp_square_template";
CREATE TABLE "ai_mcp_square_template" (
  "id" int8 NOT NULL DEFAULT nextval('mcp_square_template_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "icon" varchar(200) COLLATE "pg_catalog"."default",
  "category" varchar(50) COLLATE "pg_catalog"."default",
  "platform" varchar(50) COLLATE "pg_catalog"."default",
  "description" varchar(2000) COLLATE "pg_catalog"."default",
  "service_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "service_url" varchar(500) COLLATE "pg_catalog"."default",
  "access_path" varchar(500) COLLATE "pg_catalog"."default",
  "version" varchar(20) COLLATE "pg_catalog"."default",
  "capabilities" json,
  "default_client_config" json,
  "sort" int4 NOT NULL DEFAULT 0,
  "status" int4 NOT NULL DEFAULT 1,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_mcp_square_template"."id" IS '主键';
COMMENT ON COLUMN "ai_mcp_square_template"."name" IS '模板名称';
COMMENT ON COLUMN "ai_mcp_square_template"."icon" IS '图标标识';
COMMENT ON COLUMN "ai_mcp_square_template"."category" IS '分类';
COMMENT ON COLUMN "ai_mcp_square_template"."platform" IS '平台类型';
COMMENT ON COLUMN "ai_mcp_square_template"."description" IS '描述';
COMMENT ON COLUMN "ai_mcp_square_template"."service_type" IS '服务类型';
COMMENT ON COLUMN "ai_mcp_square_template"."service_url" IS '服务地址模板';
COMMENT ON COLUMN "ai_mcp_square_template"."access_path" IS '访问路径';
COMMENT ON COLUMN "ai_mcp_square_template"."version" IS '协议版本';
COMMENT ON COLUMN "ai_mcp_square_template"."capabilities" IS '能力列表';
COMMENT ON COLUMN "ai_mcp_square_template"."default_client_config" IS '默认客户端配置模板';
COMMENT ON COLUMN "ai_mcp_square_template"."sort" IS '排序';
COMMENT ON COLUMN "ai_mcp_square_template"."status" IS '1=启用,0=禁用';
COMMENT ON COLUMN "ai_mcp_square_template"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_mcp_square_template
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_evolution_config
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_evolution_config";
CREATE TABLE "ai_skill_evolution_config" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_evolution_config_id_seq'::regclass),
  "skill_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "threshold" float8 NOT NULL DEFAULT '0.7'::double precision,
  "weight_success" float8 NOT NULL DEFAULT '0.4'::double precision,
  "weight_latency" float8 NOT NULL DEFAULT '0.2'::double precision,
  "weight_user_rating" float8 NOT NULL DEFAULT '0.3'::double precision,
  "resource_score" float8 NOT NULL DEFAULT '0.8'::double precision,
  "is_auto_enabled" bool NOT NULL DEFAULT false,
  "model_code" varchar(100) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_evolution_config"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_evolution_config"."skill_id" IS '技能 ID（关联 ai_skill_package.package_id）';
COMMENT ON COLUMN "ai_skill_evolution_config"."threshold" IS '评估阈值，低于此值触发进化';
COMMENT ON COLUMN "ai_skill_evolution_config"."weight_success" IS '成功率权重';
COMMENT ON COLUMN "ai_skill_evolution_config"."weight_latency" IS '延迟权重';
COMMENT ON COLUMN "ai_skill_evolution_config"."weight_user_rating" IS '用户评分权重';
COMMENT ON COLUMN "ai_skill_evolution_config"."resource_score" IS '资源评估得分';
COMMENT ON COLUMN "ai_skill_evolution_config"."is_auto_enabled" IS '是否启用自动进化评估';
COMMENT ON COLUMN "ai_skill_evolution_config"."model_code" IS '进化使用的 LLM 文本模型编码（关联 ai_chat_model.code），空则使用默认模型';
COMMENT ON COLUMN "ai_skill_evolution_config"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_evolution_config
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_evolution_log
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_evolution_log";
CREATE TABLE "ai_skill_evolution_log" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_evolution_log_id_seq'::regclass),
  "skill_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "from_version" int4,
  "to_version" int4,
  "trigger_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "result" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_evolution_log"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_evolution_log"."skill_id" IS '技能 ID';
COMMENT ON COLUMN "ai_skill_evolution_log"."from_version" IS '源版本号';
COMMENT ON COLUMN "ai_skill_evolution_log"."to_version" IS '目标版本号';
COMMENT ON COLUMN "ai_skill_evolution_log"."trigger_type" IS '触发类型: performance / requirement / competition';
COMMENT ON COLUMN "ai_skill_evolution_log"."result" IS '结果: success / failed / rolled_back';
COMMENT ON COLUMN "ai_skill_evolution_log"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_evolution_log
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_hub_repo
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_hub_repo";
CREATE TABLE "ai_skill_hub_repo" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_hub_repo_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "url" varchar(512) COLLATE "pg_catalog"."default" NOT NULL,
  "branch" varchar(100) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'main'::character varying,
  "is_official" bool NOT NULL DEFAULT false,
  "username" varchar(200) COLLATE "pg_catalog"."default",
  "password" varchar(200) COLLATE "pg_catalog"."default",
  "sort_order" int4 NOT NULL DEFAULT 0,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8,
  "source_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'git'::character varying
)
;
COMMENT ON COLUMN "ai_skill_hub_repo"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_hub_repo"."name" IS '仓库展示名（如 官方仓库）';
COMMENT ON COLUMN "ai_skill_hub_repo"."url" IS 'Git 仓库地址（https）';
COMMENT ON COLUMN "ai_skill_hub_repo"."branch" IS '克隆分支';
COMMENT ON COLUMN "ai_skill_hub_repo"."is_official" IS '是否官方仓库（官方不可删除）';
COMMENT ON COLUMN "ai_skill_hub_repo"."username" IS '仓库访问账号（留空则用全局配置 OFFICIAL_HUB_USERNAME）';
COMMENT ON COLUMN "ai_skill_hub_repo"."password" IS '仓库访问密码（留空则用全局配置 OFFICIAL_HUB_PASSWORD）';
COMMENT ON COLUMN "ai_skill_hub_repo"."sort_order" IS '展示排序';
COMMENT ON COLUMN "ai_skill_hub_repo"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_hub_repo
-- ----------------------------
BEGIN;
INSERT INTO "ai_skill_hub_repo" ("id", "name", "url", "branch", "is_official", "username", "password", "sort_order", "created_at", "updated_at", "tenant_id", "source_type") VALUES (3, 'scientific-agent-skills', 'https://github.com/K-Dense-AI/scientific-agent-skills.git', 'main', 'f', NULL, NULL, 1, '2026-09-07 14:32:31.270223', '2026-09-07 14:32:31.270223', NULL, 'git'), (2, 'SkillHub 云市场', 'skillhub://cloud', 'main', 'f', 'joezxh@qq.com', '', 0, '2026-09-07 09:25:29.703403', '2026-09-07 09:25:29.703403', NULL, 'skillhub'), (1, '官方仓库', 'http://gitee.com/joezxh/mwb-skills.git', 'master', 'f', 'joezxh@qq.com', '', 0, '2026-09-07 09:25:29.703403', '2026-09-07 09:25:29.703403', NULL, 'git');
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_metrics
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_metrics";
CREATE TABLE "ai_skill_metrics" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_metrics_id_seq'::regclass),
  "skill_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "execution_count" int4 NOT NULL DEFAULT 0,
  "success_rate" float8 NOT NULL DEFAULT '0'::double precision,
  "avg_latency" float8 NOT NULL DEFAULT '0'::double precision,
  "user_rating" float8 NOT NULL DEFAULT '0'::double precision,
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_metrics"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_metrics"."skill_id" IS '技能 ID（关联 ai_skill_package.package_id）';
COMMENT ON COLUMN "ai_skill_metrics"."execution_count" IS '累计执行次数';
COMMENT ON COLUMN "ai_skill_metrics"."success_rate" IS '执行成功率 0-1';
COMMENT ON COLUMN "ai_skill_metrics"."avg_latency" IS '平均耗时（秒）';
COMMENT ON COLUMN "ai_skill_metrics"."user_rating" IS '用户评分 0-1';
COMMENT ON COLUMN "ai_skill_metrics"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_metrics
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_package
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_package";
CREATE TABLE "ai_skill_package" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_package_id_seq'::regclass),
  "package_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(128) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "icon" varchar(32) COLLATE "pg_catalog"."default" DEFAULT 'tool'::character varying,
  "category" varchar(64) COLLATE "pg_catalog"."default" DEFAULT 'other'::character varying,
  "version" varchar(32) COLLATE "pg_catalog"."default" DEFAULT '1.0.0'::character varying,
  "enabled" bool NOT NULL DEFAULT true,
  "file_path" varchar(256) COLLATE "pg_catalog"."default" NOT NULL,
  "skill_markdown" text COLLATE "pg_catalog"."default",
  "created_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_package"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_package"."package_id" IS '技能包业务 ID';
COMMENT ON COLUMN "ai_skill_package"."name" IS '技能包名称';
COMMENT ON COLUMN "ai_skill_package"."description" IS '描述';
COMMENT ON COLUMN "ai_skill_package"."icon" IS '图标标识';
COMMENT ON COLUMN "ai_skill_package"."category" IS '类目';
COMMENT ON COLUMN "ai_skill_package"."version" IS '版本';
COMMENT ON COLUMN "ai_skill_package"."enabled" IS '是否启用';
COMMENT ON COLUMN "ai_skill_package"."file_path" IS '相对于 backend/data/skills/ 的路径';
COMMENT ON COLUMN "ai_skill_package"."skill_markdown" IS 'SKILL.md 文件内容，执行时优先于文件系统';
COMMENT ON COLUMN "ai_skill_package"."created_by" IS '创建者 ID';
COMMENT ON COLUMN "ai_skill_package"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_package
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_rule
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_rule";
CREATE TABLE "ai_skill_rule" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_rule_id_seq'::regclass),
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "conditions" jsonb,
  "package_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "agent_name" varchar(200) COLLATE "pg_catalog"."default",
  "priority" int4 NOT NULL DEFAULT 100,
  "is_active" bool NOT NULL DEFAULT true,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_rule"."name" IS '规则名称';
COMMENT ON COLUMN "ai_skill_rule"."conditions" IS '触发条件';
COMMENT ON COLUMN "ai_skill_rule"."package_id" IS 'Skill包ID';
COMMENT ON COLUMN "ai_skill_rule"."agent_name" IS '关联专家名称（为空表示全局规则）';
COMMENT ON COLUMN "ai_skill_rule"."priority" IS '优先级';
COMMENT ON COLUMN "ai_skill_rule"."is_active" IS '是否启用';
COMMENT ON COLUMN "ai_skill_rule"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_rule
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_script
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_script";
CREATE TABLE "ai_skill_script" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_script_id_seq'::regclass),
  "package_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "script_id" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(128) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "command" text COLLATE "pg_catalog"."default" NOT NULL,
  "params" jsonb,
  "sort_order" int4 DEFAULT 0,
  "enabled" bool NOT NULL DEFAULT true,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_script"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_script"."package_id" IS '所属技能包 ID';
COMMENT ON COLUMN "ai_skill_script"."script_id" IS '脚本业务 ID';
COMMENT ON COLUMN "ai_skill_script"."name" IS '脚本名称';
COMMENT ON COLUMN "ai_skill_script"."description" IS '描述';
COMMENT ON COLUMN "ai_skill_script"."command" IS '执行命令模板，含 {param} 占位符';
COMMENT ON COLUMN "ai_skill_script"."params" IS '参数定义 JSON';
COMMENT ON COLUMN "ai_skill_script"."sort_order" IS '排序';
COMMENT ON COLUMN "ai_skill_script"."enabled" IS '是否启用';
COMMENT ON COLUMN "ai_skill_script"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_script
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_skill_version
-- ----------------------------
DROP TABLE IF EXISTS "ai_skill_version";
CREATE TABLE "ai_skill_version" (
  "id" int8 NOT NULL DEFAULT nextval('ai_skill_version_id_seq'::regclass),
  "skill_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "version_number" int4 NOT NULL,
  "changes" jsonb,
  "is_stable" bool NOT NULL DEFAULT false,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_skill_version"."id" IS '主键';
COMMENT ON COLUMN "ai_skill_version"."skill_id" IS '技能 ID（关联 ai_skill_package.package_id）';
COMMENT ON COLUMN "ai_skill_version"."version_number" IS '版本号（自增）';
COMMENT ON COLUMN "ai_skill_version"."changes" IS '版本变更说明 JSON';
COMMENT ON COLUMN "ai_skill_version"."is_stable" IS '是否稳定版本';
COMMENT ON COLUMN "ai_skill_version"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_skill_version
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_tool_definition
-- ----------------------------
DROP TABLE IF EXISTS "ai_tool_definition";
CREATE TABLE "ai_tool_definition" (
  "id" int8 NOT NULL DEFAULT nextval('tool_definition_id_seq'::regclass),
  "tool_key" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "display_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(100) COLLATE "pg_catalog"."default",
  "tool_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'custom'::character varying,
  "class_name" varchar(500) COLLATE "pg_catalog"."default",
  "method_name" varchar(200) COLLATE "pg_catalog"."default",
  "description" varchar(2000) COLLATE "pg_catalog"."default",
  "config_schema" json,
  "config_value" json,
  "input_schema" json,
  "output_schema" json,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'enabled'::character varying,
  "is_system" bool NOT NULL DEFAULT false,
  "sort" int8 NOT NULL DEFAULT '0'::bigint,
  "creator" varchar(100) COLLATE "pg_catalog"."default",
  "updater" varchar(100) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_tool_definition"."id" IS '主键';
COMMENT ON COLUMN "ai_tool_definition"."tool_key" IS '工具标识 toolKey（唯一）';
COMMENT ON COLUMN "ai_tool_definition"."display_name" IS '显示名称 displayName';
COMMENT ON COLUMN "ai_tool_definition"."category" IS '分类 category（如：信息查询/数据处理/AI增强）';
COMMENT ON COLUMN "ai_tool_definition"."tool_type" IS '工具类型：custom/skill/mcp/group';
COMMENT ON COLUMN "ai_tool_definition"."class_name" IS '实现类全限定名 className（Python module.Class）';
COMMENT ON COLUMN "ai_tool_definition"."method_name" IS '方法名 methodName';
COMMENT ON COLUMN "ai_tool_definition"."description" IS '描述';
COMMENT ON COLUMN "ai_tool_definition"."config_schema" IS '配置 Schema（JSON）';
COMMENT ON COLUMN "ai_tool_definition"."config_value" IS '配置值（JSON）';
COMMENT ON COLUMN "ai_tool_definition"."input_schema" IS '输入参数 JSON Schema（用于测试表单动态渲染）';
COMMENT ON COLUMN "ai_tool_definition"."output_schema" IS '输出参数 JSON Schema';
COMMENT ON COLUMN "ai_tool_definition"."status" IS '状态：enabled / disabled';
COMMENT ON COLUMN "ai_tool_definition"."is_system" IS '是否系统内置工具（系统工具不允许删除）';
COMMENT ON COLUMN "ai_tool_definition"."sort" IS '排序';
COMMENT ON COLUMN "ai_tool_definition"."creator" IS '创建人';
COMMENT ON COLUMN "ai_tool_definition"."updater" IS '更新人';
COMMENT ON COLUMN "ai_tool_definition"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_tool_definition
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_tool_group
-- ----------------------------
DROP TABLE IF EXISTS "ai_tool_group";
CREATE TABLE "ai_tool_group" (
  "id" int8 NOT NULL DEFAULT nextval('tool_group_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "display_name" varchar(200) COLLATE "pg_catalog"."default",
  "description" varchar(2000) COLLATE "pg_catalog"."default",
  "instructions" varchar(4000) COLLATE "pg_catalog"."default",
  "is_active" bool NOT NULL DEFAULT false,
  "sort" int8 NOT NULL DEFAULT '0'::bigint,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_tool_group"."id" IS '主键';
COMMENT ON COLUMN "ai_tool_group"."name" IS '分组名';
COMMENT ON COLUMN "ai_tool_group"."display_name" IS '分组显示名称';
COMMENT ON COLUMN "ai_tool_group"."description" IS '描述';
COMMENT ON COLUMN "ai_tool_group"."instructions" IS '给 Agent 的使用说明';
COMMENT ON COLUMN "ai_tool_group"."is_active" IS '是否启用';
COMMENT ON COLUMN "ai_tool_group"."sort" IS '排序';
COMMENT ON COLUMN "ai_tool_group"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_tool_group
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_tool_group_member
-- ----------------------------
DROP TABLE IF EXISTS "ai_tool_group_member";
CREATE TABLE "ai_tool_group_member" (
  "group_id" int8 NOT NULL,
  "tool_key" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "sort_order" int8 DEFAULT '0'::bigint,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_tool_group_member"."group_id" IS '分组 ID';
COMMENT ON COLUMN "ai_tool_group_member"."tool_key" IS '工具标识 toolKey';
COMMENT ON COLUMN "ai_tool_group_member"."sort_order" IS '组内排序';
COMMENT ON COLUMN "ai_tool_group_member"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_tool_group_member
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_web_search
-- ----------------------------
DROP TABLE IF EXISTS "ai_web_search";
CREATE TABLE "ai_web_search" (
  "id" int4 NOT NULL DEFAULT nextval('ai_web_search_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "api_key" text COLLATE "pg_catalog"."default" NOT NULL,
  "platform" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "url" varchar(500) COLLATE "pg_catalog"."default",
  "app_id" varchar(100) COLLATE "pg_catalog"."default",
  "property" json,
  "timeout" int4 NOT NULL DEFAULT 30,
  "max_results" int4 NOT NULL DEFAULT 10,
  "daily_quota" int4 NOT NULL DEFAULT 0,
  "used_count" int4 NOT NULL DEFAULT 0,
  "quota_date" date,
  "priority" int4 NOT NULL DEFAULT 50,
  "status" int4 NOT NULL DEFAULT 1,
  "sort" int4 NOT NULL DEFAULT 0,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6),
  "creator" varchar(64) COLLATE "pg_catalog"."default",
  "updater" varchar(64) COLLATE "pg_catalog"."default",
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_web_search"."id" IS '主键';
COMMENT ON COLUMN "ai_web_search"."name" IS '配置名称';
COMMENT ON COLUMN "ai_web_search"."api_key" IS '平台 API Key';
COMMENT ON COLUMN "ai_web_search"."platform" IS '平台: bocha/anspire/google/bing/custom';
COMMENT ON COLUMN "ai_web_search"."url" IS 'API 地址';
COMMENT ON COLUMN "ai_web_search"."app_id" IS 'AppId';
COMMENT ON COLUMN "ai_web_search"."property" IS '扩展配置(含 api_secret 等敏感项)';
COMMENT ON COLUMN "ai_web_search"."timeout" IS '请求超时(秒)';
COMMENT ON COLUMN "ai_web_search"."max_results" IS '单次最大结果数';
COMMENT ON COLUMN "ai_web_search"."daily_quota" IS '每日配额(0=不限)';
COMMENT ON COLUMN "ai_web_search"."used_count" IS '已使用次数(当日)';
COMMENT ON COLUMN "ai_web_search"."quota_date" IS 'used_count 所属日期(用于每日配额重置)';
COMMENT ON COLUMN "ai_web_search"."priority" IS '优先级(越大越优先)';
COMMENT ON COLUMN "ai_web_search"."status" IS '状态: 1=启用, 0=禁用';
COMMENT ON COLUMN "ai_web_search"."sort" IS '排序';
COMMENT ON COLUMN "ai_web_search"."creator" IS '创建人';
COMMENT ON COLUMN "ai_web_search"."updater" IS '更新人';
COMMENT ON COLUMN "ai_web_search"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_web_search
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_web_search_log
-- ----------------------------
DROP TABLE IF EXISTS "ai_web_search_log";
CREATE TABLE "ai_web_search_log" (
  "id" int4 NOT NULL DEFAULT nextval('ai_web_search_log_id_seq'::regclass),
  "web_search_id" int4 NOT NULL,
  "service_name" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "platform" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "query" varchar(512) COLLATE "pg_catalog"."default" NOT NULL,
  "response_time" float8 NOT NULL DEFAULT '0'::double precision,
  "results_count" int4 NOT NULL DEFAULT 0,
  "success" bool NOT NULL DEFAULT true,
  "error" text COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_web_search_log"."id" IS '主键';
COMMENT ON COLUMN "ai_web_search_log"."web_search_id" IS '供应商ID';
COMMENT ON COLUMN "ai_web_search_log"."service_name" IS '供应商名称(冗余)';
COMMENT ON COLUMN "ai_web_search_log"."platform" IS '平台';
COMMENT ON COLUMN "ai_web_search_log"."query" IS '搜索关键词';
COMMENT ON COLUMN "ai_web_search_log"."response_time" IS '响应耗时(ms)';
COMMENT ON COLUMN "ai_web_search_log"."results_count" IS '结果条数';
COMMENT ON COLUMN "ai_web_search_log"."success" IS '是否成功';
COMMENT ON COLUMN "ai_web_search_log"."error" IS '错误信息';
COMMENT ON COLUMN "ai_web_search_log"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_web_search_log
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for ai_workspace
-- ----------------------------
DROP TABLE IF EXISTS "ai_workspace";
CREATE TABLE "ai_workspace" (
  "id" int4 NOT NULL DEFAULT nextval('ai_workspace_id_seq'::regclass),
  "workspace_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "description" varchar(500) COLLATE "pg_catalog"."default",
  "scope" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "execution_mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "workspace_type" varchar(30) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" int8,
  "config" json NOT NULL,
  "mcp_ids" json,
  "skill_ids" json,
  "is_default" bool NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "created_by" varchar(64) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "is_deleted" bool NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "ai_workspace"."workspace_id" IS '业务唯一标识(UUID)';
COMMENT ON COLUMN "ai_workspace"."name" IS '工作空间名称';
COMMENT ON COLUMN "ai_workspace"."description" IS '描述';
COMMENT ON COLUMN "ai_workspace"."scope" IS 'public/private';
COMMENT ON COLUMN "ai_workspace"."execution_mode" IS 'remote/local';
COMMENT ON COLUMN "ai_workspace"."workspace_type" IS 'local/docker/opensandbox';
COMMENT ON COLUMN "ai_workspace"."user_id" IS '私有空间绑定用户';
COMMENT ON COLUMN "ai_workspace"."config" IS '后端特定配置';
COMMENT ON COLUMN "ai_workspace"."mcp_ids" IS '引用的MCP服务ID列表';
COMMENT ON COLUMN "ai_workspace"."skill_ids" IS '引用的技能ID列表';
COMMENT ON COLUMN "ai_workspace"."is_default" IS '是否为用户默认工作空间';
COMMENT ON COLUMN "ai_workspace"."status" IS 'active/disabled';
COMMENT ON COLUMN "ai_workspace"."created_by" IS '创建者';
COMMENT ON COLUMN "ai_workspace"."created_at" IS '创建时间';
COMMENT ON COLUMN "ai_workspace"."updated_at" IS '更新时间';
COMMENT ON COLUMN "ai_workspace"."is_deleted" IS '软删除';
COMMENT ON COLUMN "ai_workspace"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of ai_workspace
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS "alembic_version";
CREATE TABLE "alembic_version" (
  "version_num" varchar(32) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Records of alembic_version
-- ----------------------------
BEGIN;
INSERT INTO "alembic_version" ("version_num") VALUES ('003_add_sys_dictionary_tenant_id');
COMMIT;

-- ----------------------------
-- Table structure for sys_audit_log
-- ----------------------------
DROP TABLE IF EXISTS "sys_audit_log";
CREATE TABLE "sys_audit_log" (
  "log_id" int8 NOT NULL DEFAULT nextval('sys_audit_log_log_id_seq'::regclass),
  "user_id" int8,
  "username" varchar(50) COLLATE "pg_catalog"."default",
  "operation_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "operation_module" varchar(50) COLLATE "pg_catalog"."default",
  "operation_desc" text COLLATE "pg_catalog"."default",
  "request_method" varchar(10) COLLATE "pg_catalog"."default",
  "request_url" varchar(500) COLLATE "pg_catalog"."default",
  "request_params" jsonb,
  "request_ip" varchar(50) COLLATE "pg_catalog"."default",
  "user_agent" varchar(500) COLLATE "pg_catalog"."default",
  "response_status" int4,
  "response_time_ms" int4,
  "old_data" jsonb,
  "new_data" jsonb,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_audit_log"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_audit_log
-- ----------------------------
BEGIN;
INSERT INTO "sys_audit_log" ("log_id", "user_id", "username", "operation_type", "operation_module", "operation_desc", "request_method", "request_url", "request_params", "request_ip", "user_agent", "response_status", "response_time_ms", "old_data", "new_data", "created_at", "tenant_id") VALUES (1, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin"}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 401, 26, NULL, 'null', '2026-09-05 06:34:17.165728', NULL), (2, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin"}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 401, 17, NULL, 'null', '2026-09-05 06:34:59.264493', NULL), (3, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin"}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 401, 16, NULL, 'null', '2026-09-05 06:35:02.946123', NULL), (4, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 1}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 401, 47, NULL, 'null', '2026-09-05 07:58:21.138477', NULL), (5, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 550, NULL, 'null', '2026-09-05 08:11:18.782961', NULL), (6, 9999, 'admin', 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 519, NULL, 'null', '2026-09-05 08:11:46.926728', NULL), (7, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 26, NULL, 'null', '2026-09-05 18:14:45.822059', NULL), (8, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 511, NULL, 'null', '2026-09-05 18:14:53.009829', NULL), (9, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 18, NULL, 'null', '2026-09-05 19:46:45.561599', NULL), (10, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 498, NULL, 'null', '2026-09-05 19:46:53.569609', NULL), (11, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 22, NULL, 'null', '2026-09-05 20:01:10.635934', NULL), (12, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 506, NULL, 'null', '2026-09-05 20:01:16.506972', NULL), (13, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 21, NULL, 'null', '2026-09-05 20:08:32.180795', NULL), (14, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 494, NULL, 'null', '2026-09-05 20:08:38.233668', NULL), (15, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-05 20:36:26.062129', NULL), (16, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 704, NULL, 'null', '2026-09-05 20:36:32.053714', NULL), (17, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 135, NULL, 'null', '2026-09-05 20:37:18.936237', NULL), (18, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 503, NULL, 'null', '2026-09-05 20:37:25.685138', NULL), (19, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 20, NULL, 'null', '2026-09-05 20:37:41.134868', NULL), (20, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 502, NULL, 'null', '2026-09-05 20:37:52.428483', NULL), (21, 9999, 'admin', 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 501, NULL, 'null', '2026-09-05 20:38:46.790849', NULL), (22, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 145, NULL, 'null', '2026-09-05 20:42:21.896782', NULL), (23, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 492, NULL, 'null', '2026-09-05 20:42:27.080293', NULL), (24, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 31, NULL, 'null', '2026-09-05 22:39:27.556127', NULL), (25, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 543, NULL, 'null', '2026-09-05 22:39:42.414848', NULL), (26, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 26, NULL, 'null', '2026-09-05 22:45:24.251318', NULL), (27, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 490, NULL, 'null', '2026-09-05 22:45:31.461937', NULL), (28, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 32, NULL, 'null', '2026-09-05 23:47:25.610154', NULL), (29, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 517, NULL, 'null', '2026-09-05 23:47:42.159624', NULL), (30, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 32, NULL, 'null', '2026-09-05 23:47:55.78173', NULL), (31, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2041', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2041', '{"icon": "RobotOutlined", "name": "智能体管理", "path": "/admin/agent-management", "sort": 1, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/agent/AgentManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "agent:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 69, NULL, 'null', '2026-09-06 10:26:13.747389', NULL), (32, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2042', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2042', '{"icon": "MonitorOutlined", "name": "调用记录", "path": "/admin/session-agent", "sort": 2, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/agent/AgentExecutionManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "agent:execution:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 34, NULL, 'null', '2026-09-06 10:26:20.626213', NULL), (33, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2043', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2043', '{"icon": "ApartmentOutlined", "name": "智能体团队", "path": "/admin/agent-team", "sort": 3, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/agent-team/TeamList.vue", "parent_id": 2003, "keep_alive": 1, "permission": "agent-team:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 37, NULL, 'null', '2026-09-06 10:26:25.899225', NULL), (34, 9999, 'admin', 'delete', 'admin', 'Invoke API /api/v1/admin/menus/2004', 'DELETE', 'http://127.0.0.1:8000/api/v1/admin/menus/2004', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 43, NULL, 'null', '2026-09-06 10:26:29.069806', NULL), (35, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2033', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2033', '{"icon": "SearchOutlined", "name": "联网搜索", "path": "/admin/web-search", "sort": 30, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/ai/websearch/WebSearchManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "ai:web-search:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 30, NULL, 'null', '2026-09-06 10:26:45.955923', NULL), (36, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2035', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2035', '{"icon": "NodeIndexOutlined", "name": "MCP 服务", "path": "/admin/mcp-service", "sort": 50, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/ai/mcp/McpServiceManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "ai:mcp:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 31, NULL, 'null', '2026-09-06 10:26:53.776863', NULL), (37, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2034', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2034', '{"icon": "ToolOutlined", "name": "工具管理", "path": "/admin/tool-management", "sort": 40, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/ai/tool/ToolManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "ai:tool:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 100, NULL, 'null', '2026-09-06 10:27:00.659513', NULL), (38, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2032', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2032', '{"icon": "KeyOutlined", "name": "API 密钥", "path": "/admin/apikey", "sort": 20, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/ai/apikey/ApiKeyManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "ai:apikey:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 40, NULL, 'null', '2026-09-06 10:27:08.430708', NULL), (39, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2042', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2042', '{"icon": "MonitorOutlined", "name": "调用记录", "path": "/admin/session-agent", "sort": 60, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/agent/AgentExecutionManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "agent:execution:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 33, NULL, 'null', '2026-09-06 10:27:29.098293', NULL), (40, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2041', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2041', '{"icon": "RobotOutlined", "name": "智能体管理", "path": "/admin/agent-management", "sort": 2, "type": 2, "status": 0, "visible": 1, "component": "/views/admin/agent/AgentManagement.vue", "parent_id": 2003, "keep_alive": 1, "permission": "agent:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 32, NULL, 'null', '2026-09-06 10:27:37.465861', NULL), (41, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2003', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2003', '{"icon": "RobotOutlined", "name": "AI 能力配置", "path": "/admin/ai-capability", "sort": 3, "type": 1, "status": 0, "visible": 1, "component": "", "parent_id": 0, "keep_alive": 0, "permission": "ai-capability:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 39, NULL, 'null', '2026-09-06 10:30:45.21384', NULL), (42, 9999, 'admin', 'create', 'admin', 'Invoke API /api/v1/admin/menus', 'POST', 'http://127.0.0.1:8000/api/v1/admin/menus', '{"icon": "DatabaseOutlined", "name": "知识管理", "path": "views/kms/wiki/index.vue", "sort": 3, "type": 1, "status": 0, "visible": 1, "component": "", "parent_id": 0, "keep_alive": 0, "permission": "", "always_show": 1, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 64, NULL, 'null', '2026-09-06 10:32:19.731557', NULL), (46, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/9999/menus', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/9999/menus', '{"menuIds": [2, 2001, 2011, 2021, 2031, 2051, 2002, 2022, 2041, 2052, 1, 2023, 2043, 2053, 2003, 2054, 2005, 2055, 2056, 2032, 2033, 2034, 2035, 2042]}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 50, NULL, 'null', '2026-09-06 10:34:07.576375', NULL), (43, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/menus/2003', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/menus/2003', '{"icon": "RobotOutlined", "name": "AI 能力配置", "path": "/admin/ai-capability", "sort": 4, "type": 1, "status": 0, "visible": 1, "component": "", "parent_id": 0, "keep_alive": 0, "permission": "ai-capability:read", "always_show": 0, "component_name": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 40, NULL, 'null', '2026-09-06 10:32:26.986446', NULL), (47, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/1001', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/1001', '{"roleCode": "tenant_admin_finance", "roleName": "金融租户管理员", "description": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 47, NULL, 'null', '2026-09-06 10:37:15.621838', NULL), (49, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/1003', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/1003', '{"roleCode": "tenant_admin_legal", "roleName": "法律租户管理员", "description": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 34, NULL, 'null', '2026-09-06 10:37:44.747838', NULL), (51, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/1005', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/1005', '{"roleCode": "tenant_admin_edu", "roleName": "教学租户管理员", "description": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 45, NULL, 'null', '2026-09-06 10:38:03.563322', NULL), (44, 9999, 'admin', 'create', 'admin', 'Invoke API /api/v1/admin/menus', 'POST', 'http://127.0.0.1:8000/api/v1/admin/menus', '{"icon": "ProfileOutlined", "name": "私有知识库", "path": "kms/wiki", "sort": 1, "type": 2, "status": 0, "visible": 1, "component": "/views/kms/wiki/index.vue", "parent_id": 1, "keep_alive": 0, "permission": "", "always_show": 0, "component_name": "llm-wiki"}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 56, NULL, 'null', '2026-09-06 10:33:44.681512', NULL), (45, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/9999/menus', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/9999/menus', '{"menuIds": [2, 2001, 2011, 2021, 2031, 2051, 2002, 2022, 2041, 2052, 1, 2023, 2043, 2053, 2003, 2054, 2005, 2055, 2056, 2032, 2033, 2034, 2035, 2042]}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 63, NULL, 'null', '2026-09-06 10:34:01.34646', NULL), (48, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/1002', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/1002', '{"roleCode": "tenant_admin_sales", "roleName": "营销租户管理员", "description": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 39, NULL, 'null', '2026-09-06 10:37:35.536803', NULL), (50, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/1004', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/1004', '{"roleCode": "tenant_admin_office", "roleName": "办公租户管理员", "description": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 32, NULL, 'null', '2026-09-06 10:37:53.474419', NULL), (52, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/1006', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/1006', '{"roleCode": "tenant_admin_study", "roleName": "学习租户管理员", "description": ""}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 37, NULL, 'null', '2026-09-06 10:38:14.560872', NULL), (53, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 19, NULL, 'null', '2026-09-06 11:12:10.4434', NULL), (54, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 484, NULL, 'null', '2026-09-06 11:12:18.946761', NULL), (55, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-06 11:12:19.077347', NULL), (56, 9999, 'admin', 'update', 'admin', 'Invoke API /api/v1/admin/roles/3003/menus', 'PUT', 'http://127.0.0.1:8000/api/v1/admin/roles/3003/menus', '{"menuIds": [2001, 2011, 2002, 2021, 2022, 2023, 1, 2, 2003, 2031, 2041, 2043, 2032, 2033, 2034, 2035, 2042, 2005, 2051, 2052, 2053, 2054, 2055, 2056]}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 73, NULL, 'null', '2026-09-06 11:47:50.672787', NULL), (57, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 19, NULL, 'null', '2026-09-06 13:17:12.487777', NULL), (58, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 531, NULL, 'null', '2026-09-06 13:17:24.57068', NULL), (59, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 24, NULL, 'null', '2026-09-06 13:17:24.65137', NULL), (60, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-06 13:24:28.196282', NULL), (61, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 483, NULL, 'null', '2026-09-06 13:25:06.070308', NULL), (62, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 22, NULL, 'null', '2026-09-06 13:25:06.169475', NULL), (63, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin_finance", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Qoder/1.7.0 Chrome/138.0.7204.251 Electron/37.7.0 Safari/537.36', 401, 20, NULL, 'null', '2026-09-06 13:26:59.255103', NULL), (64, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin"}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 583, NULL, 'null', '2026-09-06 21:41:32.044725', NULL), (65, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 31, NULL, 'null', '2026-09-06 21:41:32.189863', NULL), (66, 9999, 'admin', 'delete', 'admin', 'Invoke API /api/v1/admin/menus/2011', 'DELETE', 'http://127.0.0.1:8000/api/v1/admin/menus/2011', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 59, NULL, 'null', '2026-09-06 22:09:26.760918', NULL), (67, 9999, 'admin', 'delete', 'admin', 'Invoke API /api/v1/admin/menus/2001', 'DELETE', 'http://127.0.0.1:8000/api/v1/admin/menus/2001', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 51, NULL, 'null', '2026-09-06 22:09:29.576377', NULL), (68, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-06 22:09:32.292554', NULL), (69, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 505, NULL, 'null', '2026-09-06 22:09:39.792321', NULL), (70, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 18, NULL, 'null', '2026-09-06 22:09:39.86957', NULL), (71, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 26, NULL, 'null', '2026-09-06 22:09:51.219352', NULL), (73, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 20, NULL, 'null', '2026-09-06 22:09:57.483635', NULL), (74, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 22, NULL, 'null', '2026-09-06 22:36:14.311037', NULL), (76, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 16, NULL, 'null', '2026-09-06 22:36:21.622316', NULL), (72, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 495, NULL, 'null', '2026-09-06 22:09:57.412759', NULL), (75, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 480, NULL, 'null', '2026-09-06 22:36:21.54111', NULL), (77, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-06 22:52:49.015727', NULL), (78, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 471, NULL, 'null', '2026-09-06 22:52:57.7742', NULL), (79, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 18, NULL, 'null', '2026-09-06 22:52:57.843824', NULL), (80, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 26, NULL, 'null', '2026-09-06 22:56:35.764136', NULL), (81, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 479, NULL, 'null', '2026-09-06 22:56:43.42664', NULL), (82, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 20, NULL, 'null', '2026-09-06 22:56:43.496353', NULL), (83, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 22, NULL, 'null', '2026-09-06 23:03:37.280788', NULL), (84, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 401, 31, NULL, 'null', '2026-09-06 23:03:38.945384', NULL), (85, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 494, NULL, 'null', '2026-09-06 23:03:45.747124', NULL), (86, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 27, NULL, 'null', '2026-09-06 23:03:45.848374', NULL), (87, 9999, 'admin', 'logout', 'auth', 'Invoke API /api/v1/auth/logout', 'POST', 'http://127.0.0.1:8000/api/v1/auth/logout', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 19, NULL, 'null', '2026-09-06 23:09:59.323214', NULL), (88, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 487, NULL, 'null', '2026-09-06 23:10:06.71162', NULL), (89, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 16, NULL, 'null', '2026-09-06 23:10:06.776844', NULL), (90, 9999, 'admin', 'update', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/report_type/items/disposal_analysis', 'PUT', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/report_type/items/disposal_analysis', '{"icon": "", "color": "blue", "remark": "", "is_active": false, "item_code": "disposal_analysis", "item_name": "统计分析报表", "item_value": "statistics_analysis", "sort_order": 10}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 80, NULL, 'null', '2026-09-07 10:52:39.347154', NULL), (91, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/report_type/items/risk_assessment', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/report_type/items/risk_assessment', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 29, NULL, 'null', '2026-09-07 10:52:53.832399', NULL), (92, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/agent_type/items/follower', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/agent_type/items/follower', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 28, NULL, 'null', '2026-09-07 10:53:21.308977', NULL), (93, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/agent_type/items/organizer', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/agent_type/items/organizer', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-07 10:53:23.278922', NULL), (94, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/agent_type/items/coordinator', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/agent_type/items/coordinator', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 20, NULL, 'null', '2026-09-07 10:53:27.29991', NULL), (95, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/agent_type/items/officer', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/agent_type/items/officer', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 21, NULL, 'null', '2026-09-07 10:53:29.744686', NULL), (96, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/agent_type/items/main_petitioner', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/agent_type/items/main_petitioner', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 28, NULL, 'null', '2026-09-07 10:53:34.884079', NULL), (97, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/provincial_political_legal', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/provincial_political_legal', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-07 10:53:45.365556', NULL), (98, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/provincial_petition', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/provincial_petition', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 24, NULL, 'null', '2026-09-07 10:53:47.293783', NULL), (99, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/provincial_court', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/provincial_court', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-07 10:53:49.537299', NULL), (100, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/provincial_justice', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/provincial_justice', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-07 10:53:51.374211', NULL), (101, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/cyberspace_12345', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/cyberspace_12345', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-07 10:53:55.33868', NULL), (102, 9999, 'admin', 'update', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/human_resources', 'PUT', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/human_resources', '{"icon": "", "color": "#91cc75", "remark": "", "is_active": false, "item_code": "human_resources", "item_name": "科研机构", "item_value": "科研机构", "sort_order": 2}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 38, NULL, 'null', '2026-09-07 10:54:13.051665', NULL), (103, 9999, 'admin', 'update', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/dept_type/items/public_security', 'PUT', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/dept_type/items/public_security', '{"icon": "", "color": "#fac858", "remark": "", "is_active": false, "item_code": "public_security", "item_name": "企业", "item_value": "企业", "sort_order": 3}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 43, NULL, 'null', '2026-09-07 10:54:21.503867', NULL), (104, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/tag/items/sensitive', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/tag/items/sensitive', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 24, NULL, 'null', '2026-09-07 10:54:31.334739', NULL), (105, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/tag/items/group', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/tag/items/group', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 21, NULL, 'null', '2026-09-07 10:54:33.329805', NULL), (106, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/tag/items/cross_region', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/tag/items/cross_region', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-07 10:54:35.752877', NULL), (107, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/risk_event', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/risk_event', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 32, NULL, 'null', '2026-09-07 10:55:04.930895', NULL), (108, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/risk_person', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/risk_person', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-07 10:55:07.030643', NULL), (109, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/risk_location', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/risk_location', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 23, NULL, 'null', '2026-09-07 10:55:11.80524', NULL), (110, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/risk_entity', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/risk_entity', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 24, NULL, 'null', '2026-09-07 10:55:16.035398', NULL), (111, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/cluster', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/cluster', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 22, NULL, 'null', '2026-09-07 10:55:18.305612', NULL), (112, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/disposal', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/disposal', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 25, NULL, 'null', '2026-09-07 10:55:20.558673', NULL), (113, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/audit_operation_module/items/dispute', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/audit_operation_module/items/dispute', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 24, NULL, 'null', '2026-09-07 10:55:22.797843', NULL), (114, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/task_type/items/cluster_stats', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/task_type/items/cluster_stats', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 42, NULL, 'null', '2026-09-07 10:55:45.244691', NULL), (115, 9999, 'admin', 'delete', 'dictionary', 'Invoke API /api/v1/dictionary/dictionaries/task_type/items/cluster_ai_analysis', 'DELETE', 'http://127.0.0.1:8000/api/v1/dictionary/dictionaries/task_type/items/cluster_ai_analysis', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 28, NULL, 'null', '2026-09-07 10:55:47.198122', NULL), (116, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 834, NULL, 'null', '2026-09-07 11:19:48.639932', NULL), (117, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 40646, NULL, 'null', '2026-09-07 14:29:42.140254', NULL), (118, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 51385, NULL, 'null', '2026-09-07 14:31:00.851207', NULL), (119, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 10819, NULL, 'null', '2026-09-07 14:31:41.722798', NULL), (120, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos', '{"url": "https://github.com/K-Dense-AI/scientific-agent-skills.git", "name": "scientific-agent-skills", "branch": "main"}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 173, NULL, 'null', '2026-09-07 14:32:31.347192', NULL), (121, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 15255, NULL, 'null', '2026-09-07 14:36:21.376828', NULL), (122, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/3/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/3/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 8582, NULL, 'null', '2026-09-07 14:37:28.044035', NULL), (123, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 64205, NULL, 'null', '2026-09-07 14:39:08.2196', NULL), (124, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 5332, NULL, 'null', '2026-09-07 14:39:23.804356', NULL), (125, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 3702, NULL, 'null', '2026-09-07 14:43:37.060491', NULL), (126, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 4138, NULL, 'null', '2026-09-07 14:43:54.087582', NULL), (127, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 4218, NULL, 'null', '2026-09-07 14:44:08.982723', NULL), (128, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 59015, NULL, 'null', '2026-09-07 14:48:29.07261', NULL), (129, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 13820, NULL, 'null', '2026-09-07 14:49:16.543735', NULL), (130, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 67036, NULL, 'null', '2026-09-07 15:28:25.553227', NULL), (131, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 8463, NULL, 'null', '2026-09-07 15:29:45.516903', NULL), (132, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 3877, NULL, 'null', '2026-09-07 15:35:04.854525', NULL), (133, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 153438, NULL, 'null', '2026-09-07 15:51:24.317883', NULL), (134, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 4676, NULL, 'null', '2026-09-07 15:53:09.187669', NULL), (135, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 242733, NULL, 'null', '2026-09-07 15:54:19.692833', NULL), (136, NULL, NULL, 'login', 'auth', 'Invoke API /api/v1/auth/login', 'POST', 'http://127.0.0.1:8000/api/v1/auth/login', '{"password": "********", "username": "admin", "tenant_id": 0}', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 445, NULL, 'null', '2026-09-07 20:42:33.984633', NULL), (137, 9999, 'admin', 'create', 'dictionary', 'Invoke API /api/v1/dictionary/dict/batch', 'POST', 'http://127.0.0.1:8000/api/v1/dictionary/dict/batch', '["disposal_status", "person_type", "person_manage_status", "event_type", "risk_level"]', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 200, 32, NULL, 'null', '2026-09-07 20:42:34.129398', NULL), (138, 9999, 'admin', 'create', 'ai-system', 'Invoke API /api/v1/ai-system/skill-hub/repos/1/refresh', 'POST', 'http://127.0.0.1:8000/api/v1/ai-system/skill-hub/repos/1/refresh', 'null', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36', 500, 173, NULL, 'null', '2026-09-07 20:43:22.277132', NULL);
COMMIT;

-- ----------------------------
-- Table structure for sys_dictionary
-- ----------------------------
DROP TABLE IF EXISTS "sys_dictionary";
CREATE TABLE "sys_dictionary" (
  "dict_id" int8 NOT NULL DEFAULT nextval('sys_dictionary_dict_id_seq'::regclass),
  "dict_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "dict_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "dict_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "sort_order" int4 DEFAULT 0,
  "is_active" bool NOT NULL DEFAULT true,
  "extra_data" jsonb,
  "created_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "is_deleted" bool NOT NULL DEFAULT false,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_dictionary"."dict_id" IS '字典ID';
COMMENT ON COLUMN "sys_dictionary"."dict_code" IS '字典编码';
COMMENT ON COLUMN "sys_dictionary"."dict_name" IS '字典名称';
COMMENT ON COLUMN "sys_dictionary"."dict_type" IS '字典类型';
COMMENT ON COLUMN "sys_dictionary"."description" IS '字典描述';
COMMENT ON COLUMN "sys_dictionary"."sort_order" IS '排序顺序';
COMMENT ON COLUMN "sys_dictionary"."is_active" IS '是否启用';
COMMENT ON COLUMN "sys_dictionary"."extra_data" IS '扩展数据';
COMMENT ON COLUMN "sys_dictionary"."tenant_id" IS '租户ID';
COMMENT ON TABLE "sys_dictionary" IS '系统字典表';

-- ----------------------------
-- Records of sys_dictionary
-- ----------------------------
BEGIN;
INSERT INTO "sys_dictionary" ("dict_id", "dict_code", "dict_name", "dict_type", "description", "sort_order", "is_active", "extra_data", "created_by", "created_at", "updated_at", "is_deleted", "tenant_id") VALUES (4, 'region', '行政区域', 'system', '行政区域划分', 4, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL), (5, 'source_type', '来源类型', 'business', '数据来源类型', 5, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL), (6, 'dept_type', '部门类型', 'system', '来源部门类型', 6, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL), (8, 'tag', '标签', 'business', '事件和人员标签', 8, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL), (80, 'task_type', '任务类型', 'system', '调度任务的任务类型', 10, 'f', 'null', NULL, '2026-03-24 08:55:21.819685', '2026-03-24 08:55:21.819685', 'f', NULL), (81, 'report_type', 'AI报告类型', 'system', 'AI智能报告的类型分类', 1, 'f', NULL, NULL, '2026-03-25 06:07:13.806351', '2026-03-25 06:07:13.806351', 'f', NULL), (91, 'audit_operation_module', '日志-操作模块', 'system', '系统审计日志的操作模块映射，对应各业务功能模块', 101, 'f', NULL, NULL, '2026-03-26 06:29:27.413877', '2026-03-26 06:56:54.412591', 'f', NULL), (90, 'audit_operation_type', '日志-操作类型', 'system', '系统审计日志的操作类型映射，用于仪表盘日志显示', 100, 'f', NULL, NULL, '2026-03-26 06:29:27.364697', '2026-03-26 06:57:00.534379', 'f', NULL), (115, 'agent_type', 'Agent角色类型', 'system', '仿真中Agent的角色类型', 4, 'f', NULL, NULL, '2026-05-06 19:30:56.016168', '2026-05-06 19:30:56.016168', 'f', NULL), (123, 'skill_category', 'AI技能类目', 'config', 'AI技能包的分类，如论证分析、法律推理、文档处理等', 0, 'f', NULL, NULL, '2026-07-13 17:49:59.156076', '2026-07-13 17:49:59.156076', 'f', NULL), (124, 'agent_category', '专家用途分类', 'system', '专家（Agent）用途/业务领域分类', 10, 'f', NULL, NULL, '2026-07-16 19:52:43.902779', '2026-07-16 19:52:43.902779', 'f', NULL), (126, 'agent_impl_type', '专家实现类型', 'system', '专家（Agent）技术实现类型', 11, 'f', NULL, NULL, '2026-07-16 20:07:21.152191', '2026-07-16 20:07:21.152191', 'f', NULL), (127, 'session_type', '会话类别', 'system', '会话类别', 1, 'f', 'null', NULL, '2026-07-25 19:54:19.175519', '2026-07-25 19:54:19.175519', 'f', NULL), (132, 'ontology_rel_type', '本体关系类型', 'ontology', 'UML 类图关系类型', 0, 'f', NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (133, 'kg_reasoning_exec_mode', '推理执行模式', 'system', '知识图谱推理规则执行模式（Skill/Tool/P1-P6 推理范式）', 20, 'f', NULL, NULL, '2026-08-13 22:42:34.260358', '2026-08-13 22:42:34.260358', 'f', NULL), (134, 'tool_type', '工具类型', 'system', 'AI工具管理-工具类型分类', 10, 'f', NULL, NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (135, 'web_search_platform', 'AI 联网搜索平台', 'business', '联网搜索供应商可选平台', 0, 'f', NULL, NULL, '2026-08-24 15:20:15.892423', '2026-08-24 15:20:15.892423', 'f', NULL), (136, 'model_type', '模型类型', 'business', '模型类型', 200, 'f', 'null', NULL, '2026-09-03 18:47:30.46293', '2026-09-03 18:47:30.46293', 'f', NULL);
COMMIT;

-- ----------------------------
-- Table structure for sys_dictionary_item
-- ----------------------------
DROP TABLE IF EXISTS "sys_dictionary_item";
CREATE TABLE "sys_dictionary_item" (
  "item_id" int8 NOT NULL DEFAULT nextval('sys_dictionary_item_item_id_seq'::regclass),
  "dict_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "item_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "item_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "item_value" varchar(200) COLLATE "pg_catalog"."default",
  "parent_code" varchar(50) COLLATE "pg_catalog"."default",
  "level" int4,
  "color" varchar(20) COLLATE "pg_catalog"."default",
  "icon" varchar(50) COLLATE "pg_catalog"."default",
  "sort_order" int4,
  "is_active" bool NOT NULL,
  "extra_data" json,
  "remark" text COLLATE "pg_catalog"."default",
  "created_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "is_deleted" bool NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_dictionary_item"."item_id" IS '字典项ID';
COMMENT ON COLUMN "sys_dictionary_item"."dict_code" IS '所属字典编码';
COMMENT ON COLUMN "sys_dictionary_item"."item_code" IS '字典项编码';
COMMENT ON COLUMN "sys_dictionary_item"."item_name" IS '字典项名称';
COMMENT ON COLUMN "sys_dictionary_item"."item_value" IS '字典项值';
COMMENT ON COLUMN "sys_dictionary_item"."parent_code" IS '父级编码';
COMMENT ON COLUMN "sys_dictionary_item"."level" IS '层级';
COMMENT ON COLUMN "sys_dictionary_item"."color" IS '颜色标识';
COMMENT ON COLUMN "sys_dictionary_item"."icon" IS '图标';
COMMENT ON COLUMN "sys_dictionary_item"."sort_order" IS '排序顺序';
COMMENT ON COLUMN "sys_dictionary_item"."is_active" IS '是否启用';
COMMENT ON COLUMN "sys_dictionary_item"."extra_data" IS '扩展数据';
COMMENT ON COLUMN "sys_dictionary_item"."remark" IS '备注';
COMMENT ON COLUMN "sys_dictionary_item"."created_by" IS '创建人ID';
COMMENT ON COLUMN "sys_dictionary_item"."tenant_id" IS '租户ID';
COMMENT ON TABLE "sys_dictionary_item" IS '系统字典项表';

-- ----------------------------
-- Records of sys_dictionary_item
-- ----------------------------
BEGIN;
INSERT INTO "sys_dictionary_item" ("item_id", "dict_code", "item_code", "item_name", "item_value", "parent_code", "level", "color", "icon", "sort_order", "is_active", "extra_data", "remark", "created_by", "created_at", "updated_at", "is_deleted", "tenant_id") VALUES (828, 'skill_category', 'legal-reasoning', '深度推理', 'legal-reasoning', NULL, 1, '#ffeb0f', '', 6, 'f', 'null', '深度推理', NULL, '2026-07-31 18:10:58.216957', '2026-07-31 18:10:58.216957', 'f', NULL), (867, 'skill_category', 'risk-assessment', 'risk-assessment', 'risk-assessment', NULL, 1, '#703333', '', 0, 'f', 'null', '', NULL, '2026-09-01 16:21:46.100627', '2026-09-01 16:41:45.631799', 'f', NULL), (56, 'tag', 'sensitive', '敏感', 'sensitive', NULL, 1, '#eb2f96', NULL, 3, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-07 10:54:31.313163', 'f', NULL), (57, 'tag', 'group', '群体性', 'group', NULL, 1, '#722ed1', NULL, 4, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-07 10:54:33.30887', 'f', NULL), (59, 'tag', 'cross_region', '跨区域', 'cross_region', NULL, 1, '#13c2c2', NULL, 6, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-07 10:54:35.730731', 'f', NULL), (495, 'task_type', 'cluster_stats', '聚合事件更新统计', '聚合事件更新统计', NULL, 1, '#c9c5c5', '', 4, 'f', 'null', '聚合事件更新统计', NULL, '2026-03-24 09:18:00.920219', '2026-09-07 10:55:45.216945', 'f', NULL), (496, 'task_type', 'cluster_ai_analysis', '聚合事件AI分析', '聚合事件AI分析', NULL, 1, '#c3a7a7', '', 5, 'f', 'null', '聚合事件AI分析', NULL, '2026-03-24 09:18:20.165482', '2026-09-07 10:55:47.172433', 'f', NULL), (400, 'region', '330200', '宁波市', '330200', '330000', 2, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:00.752643', 'f', NULL), (403, 'region', '330300', '温州市', '330300', '330000', 2, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:03.724358', 'f', NULL), (409, 'region', '330500', '湖州市', '330500', '330000', 2, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:28.655162', 'f', NULL), (406, 'region', '330400', '嘉兴市', '330400', '330000', 2, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:30.470621', 'f', NULL), (410, 'region', '330502', '吴兴区', '330502', '330500', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:33.598947', 'f', NULL), (396, 'region', '330000', '浙江省', '330000', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:21.252077', 'f', NULL), (397, 'region', '330100', '杭州市', '330100', '330000', 2, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:23.302803', 'f', NULL), (398, 'region', '330106', '西湖区', '330106', '330100', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:26.128346', 'f', NULL), (399, 'region', '330106001', '北山街道', '330106001', '330106', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:28.361148', 'f', NULL), (401, 'region', '330206', '海曙区', '330206', '330200', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:40.984277', 'f', NULL), (402, 'region', '330206001', '白云街道', '330206001', '330206', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:42.80259', 'f', NULL), (404, 'region', '330302', '鹿城区', '330302', '330300', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:44.701156', 'f', NULL), (405, 'region', '330302001', '五马街道', '330302001', '330302', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:46.593678', 'f', NULL), (407, 'region', '330402', '南湖区', '330402', '330400', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:48.368129', 'f', NULL), (408, 'region', '330402001', '新嘉街道', '330402001', '330402', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:50.639923', 'f', NULL), (33, 'source_type', 'manual', '手动录入', 'manual', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:35.783014', 'f', NULL), (34, 'source_type', 'import', '批量导入', 'import', NULL, 1, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:36.357494', 'f', NULL), (35, 'source_type', 'api', 'API接入', 'api', NULL, 1, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:36.88575', 'f', NULL), (36, 'source_type', 'sync', '数据同步', 'sync', NULL, 1, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:37.407249', 'f', NULL), (37, 'source_type', 'crawler', '爬虫采集', 'crawler', NULL, 1, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:38.381007', 'f', NULL), (54, 'tag', 'urgent', '紧急', 'urgent', NULL, 1, '#f5222d', NULL, 1, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:53.630597', 'f', NULL), (55, 'tag', 'important', '重要', 'important', NULL, 1, '#fa8c16', NULL, 2, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:55.06883', 'f', NULL), (58, 'tag', 'repeat', '重复', 'repeat', NULL, 1, '#faad14', NULL, 5, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:56.685079', 'f', NULL), (60, 'tag', 'media_attention', '媒体关注', 'media_attention', NULL, 1, '#1890ff', NULL, 7, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:57.654143', 'f', NULL), (829, 'skill_category', 'document', '写文书', 'document', NULL, 1, '#05fa2e', '', 7, 'f', 'null', '写文书', NULL, '2026-07-31 18:11:27.670315', '2026-07-31 18:11:27.670315', 'f', NULL), (868, 'model_type', '1', '文本模型', '1', NULL, 1, '#0af038', '', 1, 'f', 'null', '文本模型', NULL, '2026-09-03 18:48:23.776542', '2026-09-03 18:48:23.776542', 'f', NULL), (872, 'model_type', '6', '向量排序模型', '6', NULL, 1, '#09fb31', '', 6, 'f', 'null', '向量排序模型', NULL, '2026-09-03 18:51:11.925408', '2026-09-03 18:51:11.925408', 'f', NULL), (493, 'task_type', 'event', '事件处理', '事件处理', NULL, 1, '#ed0c0c', '', 2, 'f', 'null', '事件处理', NULL, '2026-03-24 09:17:11.219506', '2026-03-24 09:17:11.219506', 'f', NULL), (492, 'task_type', 'report', '报表生成', '报表生成', NULL, 1, '#2889f0', '', 0, 'f', 'null', '', NULL, '2026-03-24 09:16:45.446621', '2026-03-24 09:17:19.893073', 'f', NULL), (494, 'task_type', 'cluster', '聚合事件', '聚合事件', NULL, 1, '#4618ec', '', 3, 'f', 'null', '聚合事件', NULL, '2026-03-24 09:17:41.19426', '2026-03-24 09:17:41.19426', 'f', NULL), (497, 'task_type', 'migration', '数据迁移', '数据迁移', NULL, 1, '#f4c2c2', '', 6, 'f', 'null', '数据迁移', NULL, '2026-03-24 09:18:36.746462', '2026-03-24 09:18:36.746462', 'f', NULL), (500, 'report_type', 'trend_forecast', '趋势预测报告', 'trend_forecast', NULL, 1, 'purple', NULL, 30, 'f', NULL, NULL, NULL, '2026-03-25 06:07:13.829743', '2026-03-25 06:07:13.829743', 'f', NULL), (501, 'report_type', 'custom', '自定义报告', 'custom', NULL, 1, 'default', NULL, 40, 'f', NULL, NULL, NULL, '2026-03-25 06:07:13.829743', '2026-03-25 06:07:13.829743', 'f', NULL), (498, 'report_type', 'disposal_analysis', '统计分析报表', 'statistics_analysis', NULL, 1, 'blue', '', 10, 'f', NULL, '', NULL, '2026-03-25 06:07:13.829743', '2026-09-07 10:52:39.290066', 'f', NULL), (499, 'report_type', 'risk_assessment', '风险评估报告', 'risk_assessment', NULL, 1, 'orange', NULL, 20, 'f', NULL, NULL, NULL, '2026-03-25 06:07:13.829743', '2026-09-07 10:52:53.804202', 'f', NULL), (472, 'dept_type', 'provincial_political_legal', '省政法委', '省政法委', NULL, 1, '#fc8452', '', 7, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:53:45.34274', 'f', NULL), (470, 'dept_type', 'provincial_petition', '省信访', '省信访', NULL, 1, '#73c0de', '', 5, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:53:47.271111', 'f', NULL), (469, 'dept_type', 'provincial_court', '省法院', '省法院', NULL, 1, '#ee6666', '', 4, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:53:49.513898', 'f', NULL), (471, 'dept_type', 'provincial_justice', '省司法厅', '省司法厅', NULL, 1, '#9a60b4', '', 6, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:53:51.352267', 'f', NULL), (466, 'dept_type', 'cyberspace_12345', '12345网信平台', '12345网信平台', NULL, 1, '#5470c6', '', 1, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:53:55.31618', 'f', NULL), (418, 'region', '330800', '衢州市', '330800', '330000', 2, NULL, NULL, 8, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:48.585408', 'f', NULL), (467, 'dept_type', 'human_resources', '科研机构', '科研机构', NULL, 1, '#91cc75', '', 2, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:54:13.015538', 'f', NULL), (427, 'region', '331100', '丽水市', '331100', '330000', 2, NULL, NULL, 11, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:27.250856', 'f', NULL), (424, 'region', '331000', '台州市', '331000', '330000', 2, NULL, NULL, 10, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:44.590585', 'f', NULL), (421, 'region', '330900', '舟山市', '330900', '330000', 2, NULL, NULL, 9, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:46.649877', 'f', NULL), (425, 'region', '331002', '椒江区', '331002', '331000', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:51.63445', 'f', NULL), (426, 'region', '331002001', '海门街道', '331002001', '331002', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:54.473214', 'f', NULL), (428, 'region', '331102', '莲都区', '331102', '331100', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:56.520232', 'f', NULL), (429, 'region', '331102001', '紫金街道', '331102001', '331102', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:58.310003', 'f', NULL), (415, 'region', '330700', '金华市', '330700', '330000', 2, NULL, NULL, 7, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:24.253307', 'f', NULL), (412, 'region', '330600', '绍兴市', '330600', '330000', 2, NULL, NULL, 6, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:26.76365', 'f', NULL), (411, 'region', '330502001', '月河街道', '330502001', '330502', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:35.534235', 'f', NULL), (423, 'region', '330902001', '昌国街道', '330902001', '330902', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:05.016863', 'f', NULL), (422, 'region', '330902', '定海区', '330902', '330900', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:06.661638', 'f', NULL), (420, 'region', '330802001', '府山街道', '330802001', '330802', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:08.222388', 'f', NULL), (419, 'region', '330802', '柯城区', '330802', '330800', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:09.820634', 'f', NULL), (417, 'region', '330702001', '城东街道', '330702001', '330702', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:11.580468', 'f', NULL), (416, 'region', '330702', '婺城区', '330702', '330700', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:14.111021', 'f', NULL), (414, 'region', '330602001', '府山街道', '330602001', '330602', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:15.995185', 'f', NULL), (413, 'region', '330602', '越城区', '330602', '330600', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:17.955961', 'f', NULL), (468, 'dept_type', 'public_security', '企业', '企业', NULL, 1, '#fac858', '', 3, 'f', NULL, '', NULL, '2026-03-23 09:14:33.57867', '2026-09-07 10:54:21.466111', 'f', NULL), (554, 'audit_operation_module', 'risk_event', '风险事件', 'risk_event', NULL, 1, NULL, NULL, 50, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:04.903278', 'f', NULL), (555, 'audit_operation_module', 'risk_person', '风险人员', 'risk_person', NULL, 1, NULL, NULL, 60, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:07.008692', 'f', NULL), (830, 'skill_category', 'compliance', '合规与个保', '个人信息保护、数据安全与合规审计类技能', NULL, 1, '#fa541c', 'safety', 30, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.078629', '2026-08-05 17:56:51.078629', 'f', NULL), (831, 'skill_category', 'ai-governance', 'AI/Skill治理', '算法审计、自动化决策告知、Skill质量与编写治理类技能', NULL, 1, '#2f54eb', 'robot', 31, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.084964', '2026-08-05 17:56:51.084964', 'f', NULL), (832, 'skill_category', 'dispute-specific', '纠纷专项', '诉调对接与高频纠纷处置专项技能', NULL, 1, '#389e0d', 'solution', 32, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.092091', '2026-08-05 17:56:51.092091', 'f', NULL), (833, 'skill_category', 'public-service', '群众服务协同', '诉求分流、弱势群体帮扶与跨部门协同类技能', NULL, 1, '#13c2c2', 'team', 33, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.097423', '2026-08-05 17:56:51.097423', 'f', NULL), (557, 'audit_operation_module', 'risk_location', '风险地点', 'risk_location', NULL, 1, NULL, NULL, 80, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:11.783605', 'f', NULL), (556, 'audit_operation_module', 'risk_entity', '风险企业', 'risk_entity', NULL, 1, NULL, NULL, 70, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:16.013932', 'f', NULL), (558, 'audit_operation_module', 'cluster', '事件聚合', 'cluster', NULL, 1, NULL, NULL, 90, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:18.283962', 'f', NULL), (559, 'audit_operation_module', 'disposal', '处置管理', 'disposal', NULL, 1, NULL, NULL, 100, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:20.533204', 'f', NULL), (560, 'audit_operation_module', 'dispute', '纠纷案例', 'dispute', NULL, 1, NULL, NULL, 110, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-09-07 10:55:22.774076', 'f', NULL), (540, 'audit_operation_type', 'login', '登录', 'login', NULL, 1, 'cyan', NULL, 10, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (541, 'audit_operation_type', 'logout', '登出', 'logout', NULL, 1, 'orange', NULL, 20, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (542, 'audit_operation_type', 'create', '创建', 'create', NULL, 1, 'green', NULL, 30, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (543, 'audit_operation_type', 'update', '更新', 'update', NULL, 1, 'blue', NULL, 40, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (544, 'audit_operation_type', 'delete', '删除', 'delete', NULL, 1, 'red', NULL, 50, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (545, 'audit_operation_type', 'query', '查询', 'query', NULL, 1, 'default', NULL, 60, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (546, 'audit_operation_type', 'export', '导出', 'export', NULL, 1, 'purple', NULL, 70, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (547, 'audit_operation_type', 'import', '导入', 'import', NULL, 1, 'geekblue', NULL, 80, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (548, 'audit_operation_type', 'upload', '上传', 'upload', NULL, 1, 'lime', NULL, 90, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (549, 'audit_operation_type', 'analyze', 'AI分析', 'analyze', NULL, 1, 'magenta', NULL, 100, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL), (550, 'audit_operation_module', 'auth', '身份认证', 'auth', NULL, 1, NULL, NULL, 10, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (551, 'audit_operation_module', 'user', '用户管理', 'user', NULL, 1, NULL, NULL, 20, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (552, 'audit_operation_module', 'role', '角色管理', 'role', NULL, 1, NULL, NULL, 30, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (553, 'audit_operation_module', 'permission', '权限管理', 'permission', NULL, 1, NULL, NULL, 40, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (561, 'audit_operation_module', 'report', 'AI报告', 'report', NULL, 1, NULL, NULL, 120, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (562, 'audit_operation_module', 'dictionary', '字典管理', 'dictionary', NULL, 1, NULL, NULL, 130, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (563, 'audit_operation_module', 'migration', '数据迁移', 'migration', NULL, 1, NULL, NULL, 140, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (564, 'audit_operation_module', 'system', '系统设置', 'system', NULL, 1, NULL, NULL, 150, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (565, 'audit_operation_module', 'dws', '源数据浏览', 'dws', NULL, 1, NULL, NULL, 160, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (566, 'audit_operation_module', 'search', '全局搜索', 'search', NULL, 1, NULL, NULL, 170, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (567, 'audit_operation_module', 'graph', '关系图谱', 'graph', NULL, 1, NULL, NULL, 180, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (568, 'audit_operation_module', 'ai_assistant', 'AI助手', 'ai_assistant', NULL, 1, NULL, NULL, 190, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (569, 'audit_operation_module', 'deduction', '推演分析', 'deduction', NULL, 1, NULL, NULL, 200, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL), (834, 'skill_category', 'monitoring', '监测与知识运营', '法规变更监测、舆情联动与企业信用核查类技能', NULL, 1, '#722ed1', 'radar', 34, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.104772', '2026-08-05 17:56:51.104772', 'f', NULL), (870, 'model_type', '3', '视频生成', '3', NULL, 1, '#f70808', '', 3, 'f', 'null', '视频生成', NULL, '2026-09-03 18:49:20.695152', '2026-09-03 18:49:20.695152', 'f', NULL), (839, 'ontology_rel_type', 'aggregation', '聚合', 'aggregation', NULL, 1, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (686, 'agent_type', 'follower', '跟随者', 'follower', NULL, 1, 'blue', NULL, 30, 'f', NULL, '参与跟随者', NULL, '2026-05-06 19:30:56.057399', '2026-09-07 10:53:21.284249', 'f', NULL), (685, 'agent_type', 'organizer', '组织者', 'organizer', NULL, 1, 'purple', NULL, 20, 'f', NULL, '组织策划者', NULL, '2026-05-06 19:30:56.057399', '2026-09-07 10:53:23.257717', 'f', NULL), (688, 'agent_type', 'coordinator', '协调员', 'coordinator', NULL, 1, 'cyan', NULL, 50, 'f', NULL, '跨部门协调人员', NULL, '2026-05-06 19:30:56.057399', '2026-09-07 10:53:27.279948', 'f', NULL), (687, 'agent_type', 'officer', '处置官员', 'officer', NULL, 1, 'green', NULL, 40, 'f', NULL, '政府处置工作人员', NULL, '2026-05-06 19:30:56.057399', '2026-09-07 10:53:29.726227', 'f', NULL), (684, 'agent_type', 'main_petitioner', '主要当事人', 'main_petitioner', NULL, 1, 'red', NULL, 10, 'f', NULL, '事件主要发起者/当事人', NULL, '2026-05-06 19:30:56.057399', '2026-09-07 10:53:34.856455', 'f', NULL), (689, 'agent_type', 'bystander', '旁观者', 'bystander', NULL, 1, 'default', NULL, 60, 'f', NULL, '围观群众/旁观者', NULL, '2026-05-06 19:30:56.057399', '2026-05-06 19:30:56.057399', 'f', NULL), (857, 'web_search_platform', 'bocha', '博查搜索', 'bocha', NULL, 1, 'blue', NULL, 1, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL), (858, 'web_search_platform', 'anspire', 'Anspire', 'anspire', NULL, 1, 'cyan', NULL, 2, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL), (859, 'web_search_platform', 'google', 'Google', 'google', NULL, 1, 'red', NULL, 3, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL), (860, 'web_search_platform', 'bing', 'Bing', 'bing', NULL, 1, 'green', NULL, 4, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL), (861, 'web_search_platform', 'custom', '自定义平台', 'custom', NULL, 1, 'default', NULL, 5, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL), (690, 'agent_type', 'simulator', '模拟引擎', 'simulator', NULL, 1, 'magenta', NULL, 70, 'f', NULL, '系统模拟引擎（非人员角色）', NULL, '2026-05-06 19:30:56.057399', '2026-05-06 19:30:56.057399', 'f', NULL), (840, 'ontology_rel_type', 'composition', '组合', 'composition', NULL, 1, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (836, 'ontology_rel_type', 'inheritance', '继承', 'inheritance', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (837, 'ontology_rel_type', 'implementation', '实现', 'implementation', NULL, 1, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (838, 'ontology_rel_type', 'association', '关联', 'association', NULL, 1, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (841, 'ontology_rel_type', 'dependency', '依赖', 'dependency', NULL, 1, NULL, NULL, 6, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL), (862, 'web_search_platform', 'baidu', '百度', 'baidu', NULL, 1, '#99a30f', '', 5, 'f', 'null', '百度', NULL, '2026-08-24 15:21:42.793416', '2026-08-24 15:21:42.793416', 'f', NULL), (869, 'model_type', '2', '图形生成', '2', NULL, 1, '#e0d910', '', 2, 'f', 'null', '图形生成', NULL, '2026-09-03 18:48:51.679812', '2026-09-03 18:49:26.942665', 'f', NULL), (786, 'agent_category', 'dispute_proc', '纠纷处置', 'dispute_proc', NULL, 1, 'blue', '', 30, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:33.252299', 'f', NULL), (796, 'agent_impl_type', 'WORKFLOW', '工作流型', 'WORKFLOW', NULL, 1, 'purple', '', 20, 'f', NULL, '适用于执行 Dify 工作流，可配置输入输出映射', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:02.190974', 'f', NULL), (795, 'agent_impl_type', 'CHAT', '会话型', 'CHAT', NULL, 1, 'blue', '', 10, 'f', NULL, '适用于通用对话，支持 LLM 调用与工具集成', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:07.870383', 'f', NULL), (797, 'agent_impl_type', 'SKILL', '技能型', 'SKILL', NULL, 1, 'green', '', 30, 'f', NULL, '适用于调用技能包，支持规则引擎自动触发', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:14.795326', 'f', NULL), (785, 'agent_category', 'legal_consult', '法律处理', 'legal_consult', NULL, 1, 'orange', '', 20, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:29.238758', 'f', NULL), (799, 'session_type', 'dispute', '纠纷调解', 'dispute', NULL, 1, '#2ce713', '', 2, 'f', 'null', '纠纷调解', NULL, '2026-07-25 19:56:25.478394', '2026-07-25 19:56:25.478394', 'f', NULL), (798, 'session_type', 'general', '通用对话', 'general', NULL, 1, '#8ae5db', '', 1, 'f', 'null', '通用对话，使用LLM直接调用', NULL, '2026-07-25 19:56:02.887205', '2026-07-25 19:56:42.262055', 'f', NULL), (800, 'session_type', 'data', '数据分析', 'data', NULL, 1, '#caee17', '', 3, 'f', 'null', '数据分析', NULL, '2026-07-25 19:57:32.274971', '2026-07-25 19:57:32.274971', 'f', NULL), (790, 'agent_category', 'general', '通用助手', 'general', NULL, 1, 'default', '', 70, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:52.419216', 'f', NULL), (791, 'agent_category', 'other', '其他', 'other', NULL, 1, 'default', '', 99, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:56.249993', 'f', NULL), (784, 'agent_category', 'event_analysis', '事件分析', 'event_analysis', NULL, 1, 'red', '', 10, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:25.194989', 'f', NULL), (801, 'session_type', 'skill', '技能', 'skill', NULL, 1, 'green', NULL, 4, 'f', NULL, NULL, NULL, '2026-07-25 20:02:15.099158', '2026-07-25 20:02:15.099158', 'f', NULL), (802, 'session_type', 'thinking', '深度思考', 'thinking', NULL, 1, 'geekblue', 'BulbOutlined', 50, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-07-29 14:08:01.977271', 'f', NULL), (803, 'session_type', 'deep_research', '深度研究', 'deep_research', NULL, 1, 'volcano', 'SearchOutlined', 60, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-07-29 14:08:01.977271', 'f', NULL), (804, 'session_type', 'agent', '智能体', 'agent', NULL, 1, 'green', 'RobotOutlined', 70, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-07-29 14:08:01.977271', 'f', NULL), (805, 'session_type', 'team', '智能体团队', 'team', NULL, 1, 'purple', 'TeamOutlined', 80, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-07-29 14:08:01.977271', 'f', NULL), (842, 'kg_reasoning_exec_mode', 'skill', 'Skill（LLM 执行）', 'skill', NULL, 1, 'purple', 'robot', 10, 'f', NULL, '通过 SkillExecutionService 调用 LLM 技能执行', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL), (815, 'skill_category', 'mediation-assist', '调解助手', 'mediation-assist', NULL, 1, '#389e0d', 'heart', 3, 'f', NULL, '"调解的时候怎么说话？用什么策略？有没有类似的案例？"
包含：类案匹配、策略推荐、调解金句、流程指引、法律检索、调解简报、截止日期提醒', NULL, '2026-07-30 16:02:29.605054', '2026-07-31 18:03:51.147668', 'f', NULL), (776, 'skill_category', 'other', '其他', 'other', NULL, 1, '#8c8c8c', 'appstore', 99, 'f', NULL, '未分类或其他类型的技能', NULL, '2026-07-13 17:49:59.179102', '2026-07-30 17:14:44.69585', 'f', NULL), (772, 'skill_category', 'risk-warning', '风险预警', 'risk-warning', NULL, 1, '#faad14', 'warning', 2, 'f', NULL, '包含：风险评分、BIRT五维分析、重点人/事/地识别、升级检测、热点监控、地点风险评估
', NULL, '2026-07-13 17:49:59.179102', '2026-07-31 18:01:55.306269', 'f', NULL), (771, 'skill_category', 'knowledge-qa', '政策法律', 'knowledge-qa', NULL, 1, '#722ed1', 'search', 4, 'f', NULL, '包含：法条检索、政策解读、法律问答、合规检查、流程指引
', NULL, '2026-07-13 17:49:59.179102', '2026-07-31 18:04:50.554771', 'f', NULL), (770, 'skill_category', 'situation-report', '态势报告', 'situation-report', NULL, 1, '#1890ff', 'brain', 5, 'f', NULL, '包含：趋势分析、热点检测、区域巡查、报告生成、图谱关系查看', NULL, '2026-07-13 17:49:59.179102', '2026-07-31 18:05:03.008313', 'f', NULL), (768, 'skill_category', 'event-handling', '事件处理', 'event-handling', NULL, 1, '#eb2f96', 'bar-chart', 1, 'f', NULL, '包含：事件分类、事件摘要、异常检测、纠纷登记、大事记梳理、争议焦点识别', NULL, '2026-07-13 17:49:59.179102', '2026-07-31 18:04:27.223085', 'f', NULL), (843, 'kg_reasoning_exec_mode', 'tool', 'Tool（MCP Tool 直调）', 'tool', NULL, 1, 'cyan', 'tool', 20, 'f', NULL, '通过 MCP Tool 直调执行', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL), (871, 'model_type', '5', '向量化模型', '5', NULL, 1, '#0a06f9', '', 5, 'f', 'null', '向量化模型', NULL, '2026-09-03 18:50:51.112515', '2026-09-03 18:50:51.112515', 'f', NULL), (873, 'model_type', '4', '多模态理解', '4', NULL, 1, '#f80d0d', '', 4, 'f', 'null', '多模态理解', NULL, '2026-09-03 18:51:37.996039', '2026-09-03 18:51:37.996039', 'f', NULL), (848, 'kg_reasoning_exec_mode', 'bayesian', 'Bayesian（贝叶斯）', 'bayesian', NULL, 1, 'orange', 'experiment', 70, 'f', NULL, '贝叶斯推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL), (849, 'kg_reasoning_exec_mode', 'fusion', 'Fusion（多范式融合）', 'fusion', NULL, 1, 'red', 'deployment', 80, 'f', NULL, '多范式融合推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL), (847, 'kg_reasoning_exec_mode', 'fuzzy', 'Fuzzy（模糊推理）', 'fuzzy', NULL, 1, 'orange', 'thunderbolt', 60, 'f', NULL, '模糊推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:21:46.39085', 'f', NULL), (846, 'kg_reasoning_exec_mode', 'sparql', 'SPARQL（图查询）', 'sparql', NULL, 1, 'blue', 'share-alt', 50, 'f', NULL, 'SPARQL 图查询推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:21:36.023456', 'f', NULL), (845, 'kg_reasoning_exec_mode', 'prolog', 'Prolog（逻辑编程）', 'prolog', NULL, 1, 'blue', 'code', 40, 'f', NULL, 'Prolog 逻辑编程推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:20:54.607057', 'f', NULL), (844, 'kg_reasoning_exec_mode', 'owl', 'OWL（描述逻辑）', 'owl', NULL, 1, 'blue', 'branches', 30, 'f', NULL, 'OWL 描述逻辑推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:20:45.202335', 'f', NULL), (863, 'web_search_platform', 'tavily', 'Tavily', 'tavily', NULL, 1, 'purple', 'robot', 60, 'f', NULL, '面向 LLM 的检索 API，Bearer 鉴权', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL), (864, 'web_search_platform', 'exa', 'Exa', 'exa', NULL, 1, 'magenta', 'thunderbolt', 70, 'f', NULL, '神经/嵌入搜索 API，Bearer 鉴权', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL), (865, 'web_search_platform', 'firecrawl', 'Firecrawl', 'firecrawl', NULL, 1, 'volcano', 'cloud', 80, 'f', NULL, '自托管或 SaaS，统一 /v1/search，可免 Key', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL), (866, 'web_search_platform', 'searxng', 'SearXNG', 'searxng', NULL, 1, 'gold', 'fork', 90, 'f', NULL, '自托管元搜索引擎，GET /search?format=json', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL), (850, 'tool_type', 'custom', '自定义', 'custom', NULL, 1, 'default', NULL, 10, 'f', NULL, '用户自定义工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (851, 'tool_type', 'skill', '技能', 'skill', NULL, 1, 'blue', NULL, 20, 'f', NULL, '技能类型工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (852, 'tool_type', 'mcp', 'MCP', 'mcp', NULL, 1, 'purple', NULL, 30, 'f', NULL, 'MCP协议工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (853, 'tool_type', 'group', '分组', 'group', NULL, 1, 'cyan', NULL, 40, 'f', NULL, '工具分组', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (854, 'tool_type', 'sqlbot', 'SQLBot', 'sqlbot', NULL, 1, 'orange', NULL, 50, 'f', NULL, 'NL2SQL查询工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (855, 'tool_type', 'agentscope_builtin', 'AgentScope内置', 'agentscope_builtin', NULL, 1, 'geekblue', NULL, 60, 'f', NULL, 'AgentScope 2.0.6 SDK内置工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (856, 'tool_type', 'custom_dev', '自定义开发', 'custom_dev', NULL, 1, 'green', NULL, 70, 'f', NULL, '项目自定义开发的工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL), (835, 'session_type', 'scheduled', '云端调度', 'scheduled', NULL, 1, '#06f90a', '', 90, 'f', 'null', '云端调度', NULL, '2026-08-06 21:07:12.653836', '2026-09-01 13:35:23.455162', 'f', NULL);
COMMIT;

-- ----------------------------
-- Table structure for sys_infra_file
-- ----------------------------
DROP TABLE IF EXISTS "sys_infra_file";
CREATE TABLE "sys_infra_file" (
  "id" int4 NOT NULL,
  "config_id" int8,
  "name" varchar(256) COLLATE "pg_catalog"."default",
  "path" varchar(512) COLLATE "pg_catalog"."default" NOT NULL,
  "url" varchar(1024) COLLATE "pg_catalog"."default" NOT NULL,
  "type" varchar(128) COLLATE "pg_catalog"."default",
  "size" int4 NOT NULL,
  "creator" varchar(64) COLLATE "pg_catalog"."default",
  "create_time" timestamp(6) NOT NULL DEFAULT now(),
  "updater" varchar(64) COLLATE "pg_catalog"."default",
  "update_time" timestamp(6) NOT NULL DEFAULT now(),
  "deleted" varchar(1) COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_infra_file"."id" IS '文件编号';
COMMENT ON COLUMN "sys_infra_file"."config_id" IS '配置编号';
COMMENT ON COLUMN "sys_infra_file"."name" IS '文件名';
COMMENT ON COLUMN "sys_infra_file"."path" IS '文件路径（磁盘）';
COMMENT ON COLUMN "sys_infra_file"."url" IS '文件 URL';
COMMENT ON COLUMN "sys_infra_file"."type" IS '文件类型/MIME';
COMMENT ON COLUMN "sys_infra_file"."size" IS '文件大小（字节）';
COMMENT ON COLUMN "sys_infra_file"."creator" IS '创建者';
COMMENT ON COLUMN "sys_infra_file"."create_time" IS '创建时间';
COMMENT ON COLUMN "sys_infra_file"."updater" IS '更新者';
COMMENT ON COLUMN "sys_infra_file"."update_time" IS '更新时间';
COMMENT ON COLUMN "sys_infra_file"."deleted" IS '是否删除';
COMMENT ON COLUMN "sys_infra_file"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_infra_file
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for sys_infra_file_content
-- ----------------------------
DROP TABLE IF EXISTS "sys_infra_file_content";
CREATE TABLE "sys_infra_file_content" (
  "id" int4 NOT NULL,
  "config_id" int8 NOT NULL,
  "path" varchar(512) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "creator" varchar(64) COLLATE "pg_catalog"."default",
  "create_time" timestamp(6) NOT NULL DEFAULT now(),
  "updater" varchar(64) COLLATE "pg_catalog"."default",
  "update_time" timestamp(6) NOT NULL DEFAULT now(),
  "deleted" varchar(1) COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_infra_file_content"."id" IS '编号';
COMMENT ON COLUMN "sys_infra_file_content"."config_id" IS '配置编号';
COMMENT ON COLUMN "sys_infra_file_content"."path" IS '文件路径';
COMMENT ON COLUMN "sys_infra_file_content"."content" IS '文件内容（字节流）';
COMMENT ON COLUMN "sys_infra_file_content"."creator" IS '创建者';
COMMENT ON COLUMN "sys_infra_file_content"."create_time" IS '创建时间';
COMMENT ON COLUMN "sys_infra_file_content"."updater" IS '更新者';
COMMENT ON COLUMN "sys_infra_file_content"."update_time" IS '更新时间';
COMMENT ON COLUMN "sys_infra_file_content"."deleted" IS '是否删除';
COMMENT ON COLUMN "sys_infra_file_content"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_infra_file_content
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for sys_menu
-- ----------------------------
DROP TABLE IF EXISTS "sys_menu";
CREATE TABLE "sys_menu" (
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
BEGIN;
INSERT INTO "sys_menu" ("id", "name", "permission", "path", "type", "sort", "parent_id", "icon", "component", "component_name", "status", "visible", "keep_alive", "always_show", "i18n_key", "is_deleted", "created_at", "updated_at") VALUES (2002, 'AI 助手', 'ai-assistant:read', '/admin/ai-assistant', 1, 2, NULL, 'MessageOutlined', NULL, NULL, 0, 1, 0, 0, 'sys.menu.ai-assistant', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2005, '系统管理', 'system:read', '/admin/system', 1, 5, NULL, 'SettingOutlined', NULL, NULL, 0, 1, 0, 0, 'sys.menu.system', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2021, '智能对话', 'ai-assistant:chat:read', '/admin/ai-chat', 2, 1, 2002, 'MessageOutlined', '/views/assistant/components/AssistantPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.ai-chat', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2022, '会话管理', 'ai-assistant:sessions:read', '/admin/ai-sessions', 2, 2, 2002, 'CommentOutlined', '/views/assistant/AiSessionPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.ai-sessions', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2023, '异步任务', 'ai-assistant:async-task:read', '/admin/async-task-manage', 2, 3, 2002, 'ClockCircleOutlined', '/views/assistant/AsyncTaskManage.vue', NULL, 0, 1, 1, 0, 'sys.menu.async-task-manage', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2031, '技能管理', 'ai:skill:read', '/admin/skill-management', 2, 1, 2003, 'ToolOutlined', '/views/admin/ai/skill/SkillManagement.vue', NULL, 0, 1, 1, 0, 'sys.menu.skill-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2051, '系统设置', 'system:management:read', '/admin/system-management', 2, 1, 2005, 'SettingOutlined', '/views/admin/system/SystemManagement.vue', NULL, 0, 1, 1, 0, 'sys.menu.system-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2052, '个人信息', 'profile:read', '/admin/profile', 2, 2, 2005, 'UserOutlined', '/views/admin/system/ProfilePanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.profile', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2053, '字典管理', 'dictionary:dictionaries:read', '/admin/dictionary', 2, 3, 2005, 'DatabaseOutlined', '/views/admin/system/DictionaryPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.dictionary', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2054, '区域管理', 'dictionary:regions:read', '/admin/region', 2, 4, 2005, 'GlobalOutlined', '/views/admin/system/RegionPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.region', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2055, '租户管理', 'tenant:read', '/admin/tenant-management', 2, 5, 2005, 'BankOutlined', '/views/admin/system/TenantPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.tenant-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2056, '租户套餐', 'tenant:package:read', '/admin/tenant-package-management', 2, 6, 2005, 'AppstoreOutlined', '/views/admin/system/TenantPackagePanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.tenant-package-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-05 19:25:45.436047'), (2043, '智能体团队', 'agent-team:read', '/admin/agent-team', 2, 3, 2003, 'ApartmentOutlined', '/views/admin/agent-team/TeamList.vue', '', 0, 1, 1, 0, 'sys.menu.agent-team', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:25.865559'), (2004, '智能体', 'agent:read', '/admin/agent', 1, 4, NULL, 'ApartmentOutlined', NULL, NULL, 0, 1, 0, 0, 'sys.menu.agent', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:29.0292'), (2033, '联网搜索', 'ai:web-search:read', '/admin/web-search', 2, 30, 2003, 'SearchOutlined', '/views/admin/ai/websearch/WebSearchManagement.vue', '', 0, 1, 1, 0, 'sys.menu.web-search', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:45.927455'), (2035, 'MCP 服务', 'ai:mcp:read', '/admin/mcp-service', 2, 50, 2003, 'NodeIndexOutlined', '/views/admin/ai/mcp/McpServiceManagement.vue', '', 0, 1, 1, 0, 'sys.menu.mcp-service', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:26:53.749403'), (2034, '工具管理', 'ai:tool:read', '/admin/tool-management', 2, 40, 2003, 'ToolOutlined', '/views/admin/ai/tool/ToolManagement.vue', '', 0, 1, 1, 0, 'sys.menu.tool-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:00.562597'), (2032, 'API 密钥', 'ai:apikey:read', '/admin/apikey', 2, 20, 2003, 'KeyOutlined', '/views/admin/ai/apikey/ApiKeyManagement.vue', '', 0, 1, 1, 0, 'sys.menu.apikey', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:08.391515'), (2042, '调用记录', 'agent:execution:read', '/admin/session-agent', 2, 60, 2003, 'MonitorOutlined', '/views/admin/agent/AgentExecutionManagement.vue', '', 0, 1, 1, 0, 'sys.menu.session-agent', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:29.068539'), (2041, '智能体管理', 'agent:read', '/admin/agent-management', 2, 2, 2003, 'RobotOutlined', '/views/admin/agent/AgentManagement.vue', '', 0, 1, 1, 0, 'sys.menu.agent-management', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:27:37.436257'), (1, '知识管理', '', 'views/kms/wiki/index.vue', 1, 3, 0, 'DatabaseOutlined', '', '', 0, 1, 0, 1, NULL, 'f', '2026-09-06 10:32:19.669125', '2026-09-06 10:32:19.669125'), (2003, 'AI 能力配置', 'ai-capability:read', '/admin/ai-capability', 1, 4, 0, 'RobotOutlined', '', '', 0, 1, 0, 0, 'sys.menu.ai-capability', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 10:32:26.952141'), (2, '私有知识库', '', 'kms/wiki', 2, 1, 1, 'ProfileOutlined', '/views/kms/wiki/index.vue', 'llm-wiki', 0, 1, 0, 0, NULL, 'f', '2026-09-06 10:33:44.643016', '2026-09-06 10:33:44.643016'), (2011, '控制台门户', 'console:dashboard:read', '/admin/dashboard', 2, 1, 2001, 'DashboardOutlined', '/views/admin/system/DashboardPanel.vue', NULL, 0, 1, 1, 0, 'sys.menu.console-dashboard', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 22:09:26.705857'), (2001, '工作台', 'console:read', '/admin/console', 1, 1, NULL, 'DashboardOutlined', NULL, NULL, 0, 1, 0, 0, 'sys.menu.console', 'f', '2026-09-05 19:25:45.436047', '2026-09-06 22:09:29.537923');
COMMIT;

-- ----------------------------
-- Table structure for sys_region
-- ----------------------------
DROP TABLE IF EXISTS "sys_region";
CREATE TABLE "sys_region" (
  "region_id" int8 NOT NULL DEFAULT nextval('sys_region_region_id_seq'::regclass),
  "region_code" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "region_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "parent_code" varchar(20) COLLATE "pg_catalog"."default",
  "region_level" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "full_path" varchar(500) COLLATE "pg_catalog"."default",
  "sort_order" int4,
  "longitude" varchar(20) COLLATE "pg_catalog"."default",
  "latitude" varchar(20) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Records of sys_region
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for sys_role
-- ----------------------------
DROP TABLE IF EXISTS "sys_role";
CREATE TABLE "sys_role" (
  "role_id" int8 NOT NULL DEFAULT nextval('sys_role_role_id_seq'::regclass),
  "role_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "role_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "region_code" varchar(20) COLLATE "pg_catalog"."default",
  "region_level" varchar(20) COLLATE "pg_catalog"."default",
  "description" text COLLATE "pg_catalog"."default",
  "sort_order" int4,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "is_deleted" bool NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_role"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_role
-- ----------------------------
BEGIN;
INSERT INTO "sys_role" ("role_id", "role_name", "role_code", "region_code", "region_level", "description", "sort_order", "status", "created_at", "updated_at", "is_deleted", "tenant_id") VALUES (9999, '超级管理员', 'super_admin', NULL, NULL, NULL, NULL, 'active', '2026-09-05 08:01:50.754776', '2026-09-05 08:01:50.754776', 'f', 0), (1001, '金融租户管理员', 'tenant_admin_finance', NULL, NULL, '', NULL, 'active', '2026-09-05 07:57:49.436762', '2026-09-06 10:37:15.59101', 'f', 1), (1002, '营销租户管理员', 'tenant_admin_sales', NULL, NULL, '', NULL, 'active', '2026-09-05 07:57:49.436762', '2026-09-06 10:37:35.502221', 'f', 2), (1003, '法律租户管理员', 'tenant_admin_legal', NULL, NULL, '', NULL, 'active', '2026-09-05 07:57:49.436762', '2026-09-06 10:37:44.71707', 'f', 3), (1004, '办公租户管理员', 'tenant_admin_office', NULL, NULL, '', NULL, 'active', '2026-09-05 07:57:49.436762', '2026-09-06 10:37:53.446857', 'f', 4), (1005, '教学租户管理员', 'tenant_admin_edu', NULL, NULL, '', NULL, 'active', '2026-09-05 07:57:49.436762', '2026-09-06 10:38:03.52385', 'f', 5), (1006, '学习租户管理员', 'tenant_admin_study', NULL, NULL, '', NULL, 'active', '2026-09-05 07:57:49.436762', '2026-09-06 10:38:14.527168', 'f', 6), (3002, '租户管理员', 'tenant_admin', NULL, NULL, '租户内管理员，拥有管理控制台全部菜单（不含平台级租户/套餐管理）', 2, 'active', '2026-09-05 18:12:10.903126', '2026-09-05 18:12:10.903126', 'f', 0), (3003, '运营人员', 'operator', NULL, NULL, '日常运营角色：工作台/AI助手/AI能力/智能体可读可用，仅限个人信息，不含系统配置类页面', 3, 'active', '2026-09-05 18:12:10.903126', '2026-09-05 18:12:10.903126', 'f', 0);
COMMIT;

-- ----------------------------
-- Table structure for sys_role_menu
-- ----------------------------
DROP TABLE IF EXISTS "sys_role_menu";
CREATE TABLE "sys_role_menu" (
  "id" int8 NOT NULL DEFAULT nextval('sys_role_menu_id_seq'::regclass),
  "role_id" int8 NOT NULL,
  "menu_id" int8 NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Records of sys_role_menu
-- ----------------------------
BEGIN;
INSERT INTO "sys_role_menu" ("id", "role_id", "menu_id", "created_at") VALUES (86, 9999, 2, '2026-09-06 10:34:07.529024'), (87, 9999, 2001, '2026-09-06 10:34:07.529024'), (88, 9999, 2011, '2026-09-06 10:34:07.529024'), (89, 9999, 2021, '2026-09-06 10:34:07.529024'), (90, 9999, 2031, '2026-09-06 10:34:07.529024'), (91, 9999, 2051, '2026-09-06 10:34:07.529024'), (92, 9999, 2002, '2026-09-06 10:34:07.529024'), (93, 9999, 2022, '2026-09-06 10:34:07.529024'), (94, 9999, 2041, '2026-09-06 10:34:07.529024'), (95, 9999, 2052, '2026-09-06 10:34:07.529024'), (96, 9999, 1, '2026-09-06 10:34:07.529024'), (97, 9999, 2023, '2026-09-06 10:34:07.529024'), (98, 9999, 2043, '2026-09-06 10:34:07.529024'), (99, 9999, 2053, '2026-09-06 10:34:07.529024'), (100, 9999, 2003, '2026-09-06 10:34:07.529024'), (101, 9999, 2054, '2026-09-06 10:34:07.529024'), (102, 9999, 2005, '2026-09-06 10:34:07.529024'), (103, 9999, 2055, '2026-09-06 10:34:07.529024'), (104, 9999, 2056, '2026-09-06 10:34:07.529024'), (105, 9999, 2032, '2026-09-06 10:34:07.529024'), (106, 9999, 2033, '2026-09-06 10:34:07.529024'), (107, 9999, 2034, '2026-09-06 10:34:07.529024'), (108, 9999, 2035, '2026-09-06 10:34:07.529024'), (109, 9999, 2042, '2026-09-06 10:34:07.529024'), (110, 3003, 2001, '2026-09-06 11:47:50.600705'), (111, 3003, 2011, '2026-09-06 11:47:50.600705'), (112, 3003, 2002, '2026-09-06 11:47:50.600705'), (113, 3003, 2021, '2026-09-06 11:47:50.600705'), (114, 3003, 2022, '2026-09-06 11:47:50.600705'), (115, 3003, 2023, '2026-09-06 11:47:50.600705'), (116, 3003, 1, '2026-09-06 11:47:50.600705'), (117, 3003, 2, '2026-09-06 11:47:50.600705'), (118, 3003, 2003, '2026-09-06 11:47:50.600705'), (119, 3003, 2031, '2026-09-06 11:47:50.600705'), (120, 3003, 2041, '2026-09-06 11:47:50.600705'), (121, 3003, 2043, '2026-09-06 11:47:50.600705'), (122, 3003, 2032, '2026-09-06 11:47:50.600705'), (123, 3003, 2033, '2026-09-06 11:47:50.600705'), (124, 3003, 2034, '2026-09-06 11:47:50.600705'), (125, 3003, 2035, '2026-09-06 11:47:50.600705'), (126, 3003, 2042, '2026-09-06 11:47:50.600705'), (127, 3003, 2005, '2026-09-06 11:47:50.600705'), (128, 3003, 2051, '2026-09-06 11:47:50.600705'), (129, 3003, 2052, '2026-09-06 11:47:50.600705'), (130, 3003, 2053, '2026-09-06 11:47:50.600705'), (131, 3003, 2054, '2026-09-06 11:47:50.600705'), (132, 3003, 2055, '2026-09-06 11:47:50.600705'), (133, 3003, 2056, '2026-09-06 11:47:50.600705');
COMMIT;

-- ----------------------------
-- Table structure for sys_tenant
-- ----------------------------
DROP TABLE IF EXISTS "sys_tenant";
CREATE TABLE "sys_tenant" (
  "tenant_id" int8 NOT NULL DEFAULT nextval('sys_tenant_tenant_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "contact_name" varchar(50) COLLATE "pg_catalog"."default",
  "contact_mobile" varchar(20) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "package_id" int8,
  "expire_time" timestamp(6),
  "account_count" int4,
  "websites" json,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now()
)
;
COMMENT ON COLUMN "sys_tenant"."name" IS '租户名称';
COMMENT ON COLUMN "sys_tenant"."contact_name" IS '联系人';
COMMENT ON COLUMN "sys_tenant"."contact_mobile" IS '联系电话';
COMMENT ON COLUMN "sys_tenant"."status" IS '状态(active/disabled)';
COMMENT ON COLUMN "sys_tenant"."package_id" IS '租户套餐ID';
COMMENT ON COLUMN "sys_tenant"."expire_time" IS '过期时间';
COMMENT ON COLUMN "sys_tenant"."account_count" IS '账号额度';
COMMENT ON COLUMN "sys_tenant"."websites" IS '绑定域名列表';

-- ----------------------------
-- Records of sys_tenant
-- ----------------------------
BEGIN;
INSERT INTO "sys_tenant" ("tenant_id", "name", "contact_name", "contact_mobile", "status", "package_id", "expire_time", "account_count", "websites", "created_at", "updated_at") VALUES (0, 'MiniWorkBuddy', '系统管理员', NULL, 'active', NULL, NULL, 9999, NULL, '2026-09-05 08:01:50.744461', '2026-09-05 08:01:50.744461'), (5, '教育AI', '教育AI管理员', '13800000005', 'active', 5, NULL, 100, '[]', '2026-09-05 07:55:31.885519', '2026-09-06 15:59:25.620594'), (6, '学习AI', '学习AI管理员', '13800000006', 'active', 5, NULL, 100, '[]', '2026-09-05 07:55:31.885519', '2026-09-06 15:59:31.887641'), (4, '办公AI', '办公AI管理员', '13800000004', 'active', 4, NULL, 100, '[]', '2026-09-05 07:55:31.885519', '2026-09-06 15:59:38.146231'), (3, '法律AI', '法律AI管理员', '13800000003', 'active', 1, NULL, 100, '[]', '2026-09-05 07:55:31.885519', '2026-09-06 15:59:44.2456'), (2, '销售营销', '销售营销管理员', '13800000002', 'active', 3, NULL, 100, '[]', '2026-09-05 07:55:31.885519', '2026-09-06 15:59:51.114205'), (1, '金融投资', '金融投资管理員', '13800000001', 'active', 2, NULL, 100, '[]', '2026-09-05 07:55:31.885519', '2026-09-06 15:59:56.201412');
COMMIT;

-- ----------------------------
-- Table structure for sys_tenant_package
-- ----------------------------
DROP TABLE IF EXISTS "sys_tenant_package";
CREATE TABLE "sys_tenant_package" (
  "package_id" int8 NOT NULL DEFAULT nextval('sys_tenant_package_package_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "remark" varchar(500) COLLATE "pg_catalog"."default",
  "menu_ids" json,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now()
)
;
COMMENT ON COLUMN "sys_tenant_package"."name" IS '套餐名称';
COMMENT ON COLUMN "sys_tenant_package"."status" IS '状态(active/disabled)';
COMMENT ON COLUMN "sys_tenant_package"."remark" IS '备注';
COMMENT ON COLUMN "sys_tenant_package"."menu_ids" IS '关联菜单ID集合';

-- ----------------------------
-- Records of sys_tenant_package
-- ----------------------------
BEGIN;
INSERT INTO "sys_tenant_package" ("package_id", "name", "status", "remark", "menu_ids", "created_at", "updated_at") VALUES (1, '法律AI', 'active', '法律AI', '[2002, 2021, 2022, 2023]', '2026-09-06 10:50:01.816167', '2026-09-06 15:57:31.063521'), (3, '营销推广', 'active', '', '[2002, 2021, 2022, 2023]', '2026-09-06 15:58:10.963431', '2026-09-06 15:58:10.963431'), (4, '办公OA', 'active', '', '[2002, 2021, 2022, 2023, 1, 2]', '2026-09-06 15:58:21.108454', '2026-09-06 15:58:21.108454'), (5, '教育学习', 'active', '', '[2002, 2021, 2022, 2023, 2001, 2011]', '2026-09-06 15:58:51.746161', '2026-09-06 15:58:51.746161'), (2, '金融投资', 'active', '金融投资', '[2002, 2021, 2022, 2023, 1, 2]', '2026-09-06 15:47:04.012155', '2026-09-06 15:58:59.169196');
COMMIT;

-- ----------------------------
-- Table structure for sys_user
-- ----------------------------
DROP TABLE IF EXISTS "sys_user";
CREATE TABLE "sys_user" (
  "user_id" int8 NOT NULL DEFAULT nextval('sys_user_user_id_seq'::regclass),
  "username" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "password_hash" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "real_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "phone" varchar(20) COLLATE "pg_catalog"."default",
  "email" varchar(100) COLLATE "pg_catalog"."default",
  "avatar_url" varchar(500) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "is_admin" bool NOT NULL,
  "last_login_at" timestamp(6),
  "last_login_ip" varchar(50) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "deleted_at" timestamp(6),
  "is_deleted" bool NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_user"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_user
-- ----------------------------
BEGIN;
INSERT INTO "sys_user" ("user_id", "username", "password_hash", "real_name", "phone", "email", "avatar_url", "status", "is_admin", "last_login_at", "last_login_ip", "created_at", "updated_at", "deleted_at", "is_deleted", "tenant_id") VALUES (1001, 'admin_finance', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '金融投资管理员', NULL, NULL, NULL, 'active', 'f', NULL, NULL, '2026-09-05 07:57:49.428925', '2026-09-05 07:57:49.428925', NULL, 'f', 1), (1002, 'admin_sales', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '销售营销管理员', NULL, NULL, NULL, 'active', 'f', NULL, NULL, '2026-09-05 07:57:49.428925', '2026-09-05 07:57:49.428925', NULL, 'f', 2), (1003, 'admin_legal', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '法律AI管理员', NULL, NULL, NULL, 'active', 'f', NULL, NULL, '2026-09-05 07:57:49.428925', '2026-09-05 07:57:49.428925', NULL, 'f', 3), (1004, 'admin_office', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '办公AI管理员', NULL, NULL, NULL, 'active', 'f', NULL, NULL, '2026-09-05 07:57:49.428925', '2026-09-05 07:57:49.428925', NULL, 'f', 4), (1005, 'admin_edu', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '教育AI管理员', NULL, NULL, NULL, 'active', 'f', NULL, NULL, '2026-09-05 07:57:49.428925', '2026-09-05 07:57:49.428925', NULL, 'f', 5), (1006, 'admin_study', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '学习AI管理员', NULL, NULL, NULL, 'active', 'f', NULL, NULL, '2026-09-05 07:57:49.428925', '2026-09-05 07:57:49.428925', NULL, 'f', 6), (9999, 'admin', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '超级管理员', NULL, NULL, NULL, 'active', 'f', '2026-09-07 12:42:34.062236', NULL, '2026-09-05 08:01:50.750804', '2026-09-07 20:42:33.551318', NULL, 'f', 0);
COMMIT;

-- ----------------------------
-- Table structure for sys_user_notification
-- ----------------------------
DROP TABLE IF EXISTS "sys_user_notification";
CREATE TABLE "sys_user_notification" (
  "id" int4 NOT NULL DEFAULT nextval('sys_user_notification_id_seq'::regclass),
  "user_id" int4 NOT NULL,
  "ntype" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default",
  "ref_id" int4,
  "ref_type" varchar(32) COLLATE "pg_catalog"."default",
  "is_read" bool NOT NULL,
  "expire_at" timestamp(6),
  "created_at" timestamp(6) DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_user_notification"."id" IS '主键';
COMMENT ON COLUMN "sys_user_notification"."user_id" IS '接收用户ID';
COMMENT ON COLUMN "sys_user_notification"."ntype" IS '通知类型: system/async_task/research/scheduled/...';
COMMENT ON COLUMN "sys_user_notification"."title" IS '通知标题';
COMMENT ON COLUMN "sys_user_notification"."content" IS '通知内容';
COMMENT ON COLUMN "sys_user_notification"."ref_id" IS '关联业务ID(如任务ID)';
COMMENT ON COLUMN "sys_user_notification"."ref_type" IS '关联业务类型';
COMMENT ON COLUMN "sys_user_notification"."is_read" IS '已读状态';
COMMENT ON COLUMN "sys_user_notification"."expire_at" IS '过期时间(可空=不过期)';
COMMENT ON COLUMN "sys_user_notification"."created_at" IS '创建时间';
COMMENT ON COLUMN "sys_user_notification"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_user_notification
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for sys_user_role
-- ----------------------------
DROP TABLE IF EXISTS "sys_user_role";
CREATE TABLE "sys_user_role" (
  "id" int8 NOT NULL DEFAULT nextval('sys_user_role_id_seq'::regclass),
  "user_id" int8 NOT NULL,
  "role_id" int8 NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "sys_user_role"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of sys_user_role
-- ----------------------------
BEGIN;
INSERT INTO "sys_user_role" ("id", "user_id", "role_id", "created_at", "tenant_id") VALUES (1, 1001, 1001, '2026-09-05 07:57:49.442932', 1), (2, 1002, 1002, '2026-09-05 07:57:49.451548', 2), (3, 1003, 1003, '2026-09-05 07:57:49.454919', 3), (4, 1004, 1004, '2026-09-05 07:57:49.457215', 4), (5, 1005, 1005, '2026-09-05 07:57:49.460177', 5), (6, 1006, 1006, '2026-09-05 07:57:49.462573', 6), (7, 9999, 9999, '2026-09-05 08:01:50.769974', 0);
COMMIT;

-- ----------------------------
-- Table structure for wiki_article
-- ----------------------------
DROP TABLE IF EXISTS "wiki_article";
CREATE TABLE "wiki_article" (
  "id" int8 NOT NULL DEFAULT nextval('wiki_article_id_seq'::regclass),
  "slug" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default",
  "summary" varchar(1000) COLLATE "pg_catalog"."default",
  "owl_class_uris" jsonb,
  "content_vector" "public"."vector",
  "wiki_links" jsonb,
  "backlinks" jsonb,
  "category_id" int8,
  "tags" jsonb,
  "status" int4 NOT NULL DEFAULT 1,
  "is_featured" bool NOT NULL DEFAULT false,
  "view_count" int4 NOT NULL DEFAULT 0,
  "version" int4 NOT NULL DEFAULT 1,
  "creator_id" int8,
  "updater_id" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "wiki_article"."id" IS '主键';
COMMENT ON COLUMN "wiki_article"."slug" IS 'URL 友好标识';
COMMENT ON COLUMN "wiki_article"."title" IS '文章标题';
COMMENT ON COLUMN "wiki_article"."content" IS 'Markdown 正文';
COMMENT ON COLUMN "wiki_article"."summary" IS '摘要 (自动生成或手动填写)';
COMMENT ON COLUMN "wiki_article"."owl_class_uris" IS '关联的 OWL 类 URI 列表';
COMMENT ON COLUMN "wiki_article"."content_vector" IS '内容向量 (embedding)';
COMMENT ON COLUMN "wiki_article"."wiki_links" IS '本文链接到的其他文章 slug 列表';
COMMENT ON COLUMN "wiki_article"."backlinks" IS '链接到本文的其他文章 slug 列表';
COMMENT ON COLUMN "wiki_article"."category_id" IS '所属分类 ID';
COMMENT ON COLUMN "wiki_article"."tags" IS '标签列表';
COMMENT ON COLUMN "wiki_article"."status" IS '1=发布 0=草稿 -1=归档';
COMMENT ON COLUMN "wiki_article"."is_featured" IS '是否精选';
COMMENT ON COLUMN "wiki_article"."view_count" IS '浏览次数';
COMMENT ON COLUMN "wiki_article"."version" IS '当前版本号';
COMMENT ON COLUMN "wiki_article"."creator_id" IS '创建者 ID';
COMMENT ON COLUMN "wiki_article"."updater_id" IS '最后编辑者 ID';
COMMENT ON COLUMN "wiki_article"."created_at" IS '创建时间';
COMMENT ON COLUMN "wiki_article"."updated_at" IS '更新时间';
COMMENT ON COLUMN "wiki_article"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of wiki_article
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for wiki_article_version
-- ----------------------------
DROP TABLE IF EXISTS "wiki_article_version";
CREATE TABLE "wiki_article_version" (
  "id" int8 NOT NULL DEFAULT nextval('wiki_article_version_id_seq'::regclass),
  "article_id" int8 NOT NULL,
  "version" int4 NOT NULL,
  "title" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default",
  "slug" varchar(200) COLLATE "pg_catalog"."default",
  "change_note" varchar(500) COLLATE "pg_catalog"."default",
  "editor_id" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "wiki_article_version"."id" IS '主键';
COMMENT ON COLUMN "wiki_article_version"."article_id" IS '关联文章 ID';
COMMENT ON COLUMN "wiki_article_version"."version" IS '版本号 (从 1 递增)';
COMMENT ON COLUMN "wiki_article_version"."title" IS '版本标题快照';
COMMENT ON COLUMN "wiki_article_version"."content" IS '版本正文快照 (Markdown)';
COMMENT ON COLUMN "wiki_article_version"."slug" IS '版本 slug 快照';
COMMENT ON COLUMN "wiki_article_version"."change_note" IS '编辑说明';
COMMENT ON COLUMN "wiki_article_version"."editor_id" IS '编辑者 ID';
COMMENT ON COLUMN "wiki_article_version"."created_at" IS '版本创建时间';
COMMENT ON COLUMN "wiki_article_version"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of wiki_article_version
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Table structure for wiki_category
-- ----------------------------
DROP TABLE IF EXISTS "wiki_category";
CREATE TABLE "wiki_category" (
  "id" int8 NOT NULL DEFAULT nextval('wiki_category_id_seq'::regclass),
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "slug" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "parent_id" int8,
  "owl_class_uri" varchar(500) COLLATE "pg_catalog"."default",
  "sort_order" int4 NOT NULL DEFAULT 0,
  "article_count" int4 NOT NULL DEFAULT 0,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "tenant_id" int8
)
;
COMMENT ON COLUMN "wiki_category"."id" IS '主键';
COMMENT ON COLUMN "wiki_category"."name" IS '分类名称';
COMMENT ON COLUMN "wiki_category"."slug" IS 'URL 友好标识';
COMMENT ON COLUMN "wiki_category"."description" IS '分类描述';
COMMENT ON COLUMN "wiki_category"."parent_id" IS '父分类 ID (null=顶级)';
COMMENT ON COLUMN "wiki_category"."owl_class_uri" IS '关联的 OWL Class URI';
COMMENT ON COLUMN "wiki_category"."sort_order" IS '排序权重';
COMMENT ON COLUMN "wiki_category"."article_count" IS '文章计数 (冗余)';
COMMENT ON COLUMN "wiki_category"."created_at" IS '创建时间';
COMMENT ON COLUMN "wiki_category"."updated_at" IS '更新时间';
COMMENT ON COLUMN "wiki_category"."tenant_id" IS '租户ID';

-- ----------------------------
-- Records of wiki_category
-- ----------------------------
BEGIN;
COMMIT;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_halfvec"(_float4, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_halfvec"(_float4, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_halfvec"(_numeric, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_halfvec"(_numeric, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_halfvec"(_int4, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_halfvec"(_int4, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_halfvec"(_float8, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_halfvec"(_float8, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_sparsevec"(_numeric, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_sparsevec"(_numeric, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_sparsevec"(_int4, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_sparsevec"(_int4, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_sparsevec"(_float4, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_sparsevec"(_float4, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_sparsevec"(_float8, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_sparsevec"(_float8, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_vector"(_float8, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_vector"(_float8, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_vector"(_int4, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_vector"(_int4, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_vector"(_float4, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_vector"(_float4, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "array_to_vector"(_numeric, int4, bool);
CREATE OR REPLACE FUNCTION "array_to_vector"(_numeric, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for binary_quantize
-- ----------------------------
DROP FUNCTION IF EXISTS "binary_quantize"("public"."halfvec");
CREATE OR REPLACE FUNCTION "binary_quantize"("public"."halfvec")
  RETURNS "pg_catalog"."bit" AS '$libdir/vector', 'halfvec_binary_quantize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for binary_quantize
-- ----------------------------
DROP FUNCTION IF EXISTS "binary_quantize"("public"."vector");
CREATE OR REPLACE FUNCTION "binary_quantize"("public"."vector")
  RETURNS "pg_catalog"."bit" AS '$libdir/vector', 'binary_quantize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for cosine_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "cosine_distance"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "cosine_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'cosine_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for cosine_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "cosine_distance"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "cosine_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_cosine_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for cosine_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "cosine_distance"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "cosine_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_cosine_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gin_extract_query_trgm
-- ----------------------------
DROP FUNCTION IF EXISTS "gin_extract_query_trgm"(text, internal, int2, internal, internal, internal, internal);
CREATE OR REPLACE FUNCTION "gin_extract_query_trgm"(text, internal, int2, internal, internal, internal, internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gin_extract_query_trgm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gin_extract_value_trgm
-- ----------------------------
DROP FUNCTION IF EXISTS "gin_extract_value_trgm"(text, internal);
CREATE OR REPLACE FUNCTION "gin_extract_value_trgm"(text, internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gin_extract_value_trgm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gin_trgm_consistent
-- ----------------------------
DROP FUNCTION IF EXISTS "gin_trgm_consistent"(internal, int2, text, int4, internal, internal, internal, internal);
CREATE OR REPLACE FUNCTION "gin_trgm_consistent"(internal, int2, text, int4, internal, internal, internal, internal)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'gin_trgm_consistent'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gin_trgm_triconsistent
-- ----------------------------
DROP FUNCTION IF EXISTS "gin_trgm_triconsistent"(internal, int2, text, int4, internal, internal, internal);
CREATE OR REPLACE FUNCTION "gin_trgm_triconsistent"(internal, int2, text, int4, internal, internal, internal)
  RETURNS "pg_catalog"."char" AS '$libdir/pg_trgm', 'gin_trgm_triconsistent'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_compress
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_compress"(internal);
CREATE OR REPLACE FUNCTION "gtrgm_compress"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gtrgm_compress'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_consistent
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_consistent"(internal, text, int2, oid, internal);
CREATE OR REPLACE FUNCTION "gtrgm_consistent"(internal, text, int2, oid, internal)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'gtrgm_consistent'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_decompress
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_decompress"(internal);
CREATE OR REPLACE FUNCTION "gtrgm_decompress"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gtrgm_decompress'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_distance"(internal, text, int2, oid, internal);
CREATE OR REPLACE FUNCTION "gtrgm_distance"(internal, text, int2, oid, internal)
  RETURNS "pg_catalog"."float8" AS '$libdir/pg_trgm', 'gtrgm_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_in
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_in"(cstring);
CREATE OR REPLACE FUNCTION "gtrgm_in"(cstring)
  RETURNS "public"."gtrgm" AS '$libdir/pg_trgm', 'gtrgm_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_options
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_options"(internal);
CREATE OR REPLACE FUNCTION "gtrgm_options"(internal)
  RETURNS "pg_catalog"."void" AS '$libdir/pg_trgm', 'gtrgm_options'
  LANGUAGE c IMMUTABLE
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_out
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_out"("public"."gtrgm");
CREATE OR REPLACE FUNCTION "gtrgm_out"("public"."gtrgm")
  RETURNS "pg_catalog"."cstring" AS '$libdir/pg_trgm', 'gtrgm_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_penalty
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_penalty"(internal, internal, internal);
CREATE OR REPLACE FUNCTION "gtrgm_penalty"(internal, internal, internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gtrgm_penalty'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_picksplit
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_picksplit"(internal, internal);
CREATE OR REPLACE FUNCTION "gtrgm_picksplit"(internal, internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gtrgm_picksplit'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_same
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_same"("public"."gtrgm", "public"."gtrgm", internal);
CREATE OR REPLACE FUNCTION "gtrgm_same"("public"."gtrgm", "public"."gtrgm", internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/pg_trgm', 'gtrgm_same'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gtrgm_union
-- ----------------------------
DROP FUNCTION IF EXISTS "gtrgm_union"(internal, internal);
CREATE OR REPLACE FUNCTION "gtrgm_union"(internal, internal)
  RETURNS "public"."gtrgm" AS '$libdir/pg_trgm', 'gtrgm_union'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec"("public"."halfvec", int4, bool);
CREATE OR REPLACE FUNCTION "halfvec"("public"."halfvec", int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_accum
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_accum"(_float8, "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_accum"(_float8, "public"."halfvec")
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'halfvec_accum'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_add
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_add"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_add"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_add'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_avg
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_avg"(_float8);
CREATE OR REPLACE FUNCTION "halfvec_avg"(_float8)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_avg'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_cmp
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_cmp"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_cmp"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'halfvec_cmp'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_combine
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_combine"(_float8, _float8);
CREATE OR REPLACE FUNCTION "halfvec_combine"(_float8, _float8)
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'vector_combine'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_concat
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_concat"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_concat"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_concat'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_eq
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_eq"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_eq"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_eq'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_ge
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_ge"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_ge"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_ge'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_gt
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_gt"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_gt"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_gt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_in
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_in"(cstring, oid, int4);
CREATE OR REPLACE FUNCTION "halfvec_in"(cstring, oid, int4)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_l2_squared_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_l2_squared_distance"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_l2_squared_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l2_squared_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_le
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_le"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_le"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_le'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_lt
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_lt"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_lt"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_lt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_mul
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_mul"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_mul"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_mul'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_ne
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_ne"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_ne"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_ne'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_negative_inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_negative_inner_product"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_negative_inner_product"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_negative_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_out
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_out"("public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_out"("public"."halfvec")
  RETURNS "pg_catalog"."cstring" AS '$libdir/vector', 'halfvec_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_recv
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_recv"(internal, oid, int4);
CREATE OR REPLACE FUNCTION "halfvec_recv"(internal, oid, int4)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_recv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_send
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_send"("public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_send"("public"."halfvec")
  RETURNS "pg_catalog"."bytea" AS '$libdir/vector', 'halfvec_send'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_spherical_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_spherical_distance"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_spherical_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_spherical_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_sub
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_sub"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "halfvec_sub"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_sub'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_to_float4
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_to_float4"("public"."halfvec", int4, bool);
CREATE OR REPLACE FUNCTION "halfvec_to_float4"("public"."halfvec", int4, bool)
  RETURNS "pg_catalog"."_float4" AS '$libdir/vector', 'halfvec_to_float4'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_to_sparsevec"("public"."halfvec", int4, bool);
CREATE OR REPLACE FUNCTION "halfvec_to_sparsevec"("public"."halfvec", int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'halfvec_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_to_vector"("public"."halfvec", int4, bool);
CREATE OR REPLACE FUNCTION "halfvec_to_vector"("public"."halfvec", int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'halfvec_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_typmod_in
-- ----------------------------
DROP FUNCTION IF EXISTS "halfvec_typmod_in"(_cstring);
CREATE OR REPLACE FUNCTION "halfvec_typmod_in"(_cstring)
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'halfvec_typmod_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for hamming_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "hamming_distance"(bit, bit);
CREATE OR REPLACE FUNCTION "hamming_distance"(bit, bit)
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'hamming_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for hnsw_bit_support
-- ----------------------------
DROP FUNCTION IF EXISTS "hnsw_bit_support"(internal);
CREATE OR REPLACE FUNCTION "hnsw_bit_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'hnsw_bit_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for hnsw_halfvec_support
-- ----------------------------
DROP FUNCTION IF EXISTS "hnsw_halfvec_support"(internal);
CREATE OR REPLACE FUNCTION "hnsw_halfvec_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'hnsw_halfvec_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for hnsw_sparsevec_support
-- ----------------------------
DROP FUNCTION IF EXISTS "hnsw_sparsevec_support"(internal);
CREATE OR REPLACE FUNCTION "hnsw_sparsevec_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'hnsw_sparsevec_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for hnswhandler
-- ----------------------------
DROP FUNCTION IF EXISTS "hnswhandler"(internal);
CREATE OR REPLACE FUNCTION "hnswhandler"(internal)
  RETURNS "pg_catalog"."index_am_handler" AS '$libdir/vector', 'hnswhandler'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "inner_product"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "inner_product"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "inner_product"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "inner_product"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "inner_product"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "inner_product"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for ivfflat_bit_support
-- ----------------------------
DROP FUNCTION IF EXISTS "ivfflat_bit_support"(internal);
CREATE OR REPLACE FUNCTION "ivfflat_bit_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'ivfflat_bit_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for ivfflat_halfvec_support
-- ----------------------------
DROP FUNCTION IF EXISTS "ivfflat_halfvec_support"(internal);
CREATE OR REPLACE FUNCTION "ivfflat_halfvec_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'ivfflat_halfvec_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for ivfflathandler
-- ----------------------------
DROP FUNCTION IF EXISTS "ivfflathandler"(internal);
CREATE OR REPLACE FUNCTION "ivfflathandler"(internal)
  RETURNS "pg_catalog"."index_am_handler" AS '$libdir/vector', 'ivfflathandler'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for jaccard_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "jaccard_distance"(bit, bit);
CREATE OR REPLACE FUNCTION "jaccard_distance"(bit, bit)
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'jaccard_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l1_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "l1_distance"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "l1_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l1_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l1_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "l1_distance"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "l1_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'l1_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l1_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "l1_distance"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "l1_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l1_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_distance"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "l2_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l2_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_distance"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "l2_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'l2_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_distance"("public"."halfvec", "public"."halfvec");
CREATE OR REPLACE FUNCTION "l2_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l2_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_norm
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_norm"("public"."halfvec");
CREATE OR REPLACE FUNCTION "l2_norm"("public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l2_norm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_norm
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_norm"("public"."sparsevec");
CREATE OR REPLACE FUNCTION "l2_norm"("public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l2_norm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_normalize
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_normalize"("public"."vector");
CREATE OR REPLACE FUNCTION "l2_normalize"("public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'l2_normalize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_normalize
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_normalize"("public"."sparsevec");
CREATE OR REPLACE FUNCTION "l2_normalize"("public"."sparsevec")
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec_l2_normalize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_normalize
-- ----------------------------
DROP FUNCTION IF EXISTS "l2_normalize"("public"."halfvec");
CREATE OR REPLACE FUNCTION "l2_normalize"("public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_l2_normalize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for set_limit
-- ----------------------------
DROP FUNCTION IF EXISTS "set_limit"(float4);
CREATE OR REPLACE FUNCTION "set_limit"(float4)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'set_limit'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for show_limit
-- ----------------------------
DROP FUNCTION IF EXISTS "show_limit"();
CREATE OR REPLACE FUNCTION "show_limit"()
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'show_limit'
  LANGUAGE c STABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for show_trgm
-- ----------------------------
DROP FUNCTION IF EXISTS "show_trgm"(text);
CREATE OR REPLACE FUNCTION "show_trgm"(text)
  RETURNS "pg_catalog"."_text" AS '$libdir/pg_trgm', 'show_trgm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for similarity
-- ----------------------------
DROP FUNCTION IF EXISTS "similarity"(text, text);
CREATE OR REPLACE FUNCTION "similarity"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'similarity'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for similarity_dist
-- ----------------------------
DROP FUNCTION IF EXISTS "similarity_dist"(text, text);
CREATE OR REPLACE FUNCTION "similarity_dist"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'similarity_dist'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for similarity_op
-- ----------------------------
DROP FUNCTION IF EXISTS "similarity_op"(text, text);
CREATE OR REPLACE FUNCTION "similarity_op"(text, text)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'similarity_op'
  LANGUAGE c STABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec"("public"."sparsevec", int4, bool);
CREATE OR REPLACE FUNCTION "sparsevec"("public"."sparsevec", int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_cmp
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_cmp"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_cmp"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'sparsevec_cmp'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_eq
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_eq"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_eq"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_eq'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_ge
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_ge"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_ge"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_ge'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_gt
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_gt"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_gt"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_gt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_in
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_in"(cstring, oid, int4);
CREATE OR REPLACE FUNCTION "sparsevec_in"(cstring, oid, int4)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_l2_squared_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_l2_squared_distance"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_l2_squared_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l2_squared_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_le
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_le"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_le"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_le'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_lt
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_lt"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_lt"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_lt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_ne
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_ne"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_ne"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_ne'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_negative_inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_negative_inner_product"("public"."sparsevec", "public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_negative_inner_product"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_negative_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_out
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_out"("public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_out"("public"."sparsevec")
  RETURNS "pg_catalog"."cstring" AS '$libdir/vector', 'sparsevec_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_recv
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_recv"(internal, oid, int4);
CREATE OR REPLACE FUNCTION "sparsevec_recv"(internal, oid, int4)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec_recv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_send
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_send"("public"."sparsevec");
CREATE OR REPLACE FUNCTION "sparsevec_send"("public"."sparsevec")
  RETURNS "pg_catalog"."bytea" AS '$libdir/vector', 'sparsevec_send'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_to_halfvec"("public"."sparsevec", int4, bool);
CREATE OR REPLACE FUNCTION "sparsevec_to_halfvec"("public"."sparsevec", int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'sparsevec_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_to_vector"("public"."sparsevec", int4, bool);
CREATE OR REPLACE FUNCTION "sparsevec_to_vector"("public"."sparsevec", int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'sparsevec_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_typmod_in
-- ----------------------------
DROP FUNCTION IF EXISTS "sparsevec_typmod_in"(_cstring);
CREATE OR REPLACE FUNCTION "sparsevec_typmod_in"(_cstring)
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'sparsevec_typmod_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for strict_word_similarity
-- ----------------------------
DROP FUNCTION IF EXISTS "strict_word_similarity"(text, text);
CREATE OR REPLACE FUNCTION "strict_word_similarity"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'strict_word_similarity'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for strict_word_similarity_commutator_op
-- ----------------------------
DROP FUNCTION IF EXISTS "strict_word_similarity_commutator_op"(text, text);
CREATE OR REPLACE FUNCTION "strict_word_similarity_commutator_op"(text, text)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'strict_word_similarity_commutator_op'
  LANGUAGE c STABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for strict_word_similarity_dist_commutator_op
-- ----------------------------
DROP FUNCTION IF EXISTS "strict_word_similarity_dist_commutator_op"(text, text);
CREATE OR REPLACE FUNCTION "strict_word_similarity_dist_commutator_op"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'strict_word_similarity_dist_commutator_op'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for strict_word_similarity_dist_op
-- ----------------------------
DROP FUNCTION IF EXISTS "strict_word_similarity_dist_op"(text, text);
CREATE OR REPLACE FUNCTION "strict_word_similarity_dist_op"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'strict_word_similarity_dist_op'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for strict_word_similarity_op
-- ----------------------------
DROP FUNCTION IF EXISTS "strict_word_similarity_op"(text, text);
CREATE OR REPLACE FUNCTION "strict_word_similarity_op"(text, text)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'strict_word_similarity_op'
  LANGUAGE c STABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for subvector
-- ----------------------------
DROP FUNCTION IF EXISTS "subvector"("public"."vector", int4, int4);
CREATE OR REPLACE FUNCTION "subvector"("public"."vector", int4, int4)
  RETURNS "public"."vector" AS '$libdir/vector', 'subvector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for subvector
-- ----------------------------
DROP FUNCTION IF EXISTS "subvector"("public"."halfvec", int4, int4);
CREATE OR REPLACE FUNCTION "subvector"("public"."halfvec", int4, int4)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_subvector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector
-- ----------------------------
DROP FUNCTION IF EXISTS "vector"("public"."vector", int4, bool);
CREATE OR REPLACE FUNCTION "vector"("public"."vector", int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_accum
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_accum"(_float8, "public"."vector");
CREATE OR REPLACE FUNCTION "vector_accum"(_float8, "public"."vector")
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'vector_accum'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_add
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_add"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_add"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_add'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_avg
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_avg"(_float8);
CREATE OR REPLACE FUNCTION "vector_avg"(_float8)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_avg'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_cmp
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_cmp"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_cmp"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'vector_cmp'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_combine
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_combine"(_float8, _float8);
CREATE OR REPLACE FUNCTION "vector_combine"(_float8, _float8)
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'vector_combine'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_concat
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_concat"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_concat"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_concat'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_dims
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_dims"("public"."vector");
CREATE OR REPLACE FUNCTION "vector_dims"("public"."vector")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'vector_dims'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_dims
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_dims"("public"."halfvec");
CREATE OR REPLACE FUNCTION "vector_dims"("public"."halfvec")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'halfvec_vector_dims'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_eq
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_eq"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_eq"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_eq'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_ge
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_ge"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_ge"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_ge'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_gt
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_gt"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_gt"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_gt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_in
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_in"(cstring, oid, int4);
CREATE OR REPLACE FUNCTION "vector_in"(cstring, oid, int4)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_l2_squared_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_l2_squared_distance"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_l2_squared_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_l2_squared_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_le
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_le"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_le"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_le'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_lt
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_lt"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_lt"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_lt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_mul
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_mul"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_mul"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_mul'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_ne
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_ne"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_ne"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_ne'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_negative_inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_negative_inner_product"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_negative_inner_product"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_negative_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_norm
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_norm"("public"."vector");
CREATE OR REPLACE FUNCTION "vector_norm"("public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_norm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_out
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_out"("public"."vector");
CREATE OR REPLACE FUNCTION "vector_out"("public"."vector")
  RETURNS "pg_catalog"."cstring" AS '$libdir/vector', 'vector_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_recv
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_recv"(internal, oid, int4);
CREATE OR REPLACE FUNCTION "vector_recv"(internal, oid, int4)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_recv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_send
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_send"("public"."vector");
CREATE OR REPLACE FUNCTION "vector_send"("public"."vector")
  RETURNS "pg_catalog"."bytea" AS '$libdir/vector', 'vector_send'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_spherical_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_spherical_distance"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_spherical_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_spherical_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_sub
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_sub"("public"."vector", "public"."vector");
CREATE OR REPLACE FUNCTION "vector_sub"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_sub'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_to_float4
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_to_float4"("public"."vector", int4, bool);
CREATE OR REPLACE FUNCTION "vector_to_float4"("public"."vector", int4, bool)
  RETURNS "pg_catalog"."_float4" AS '$libdir/vector', 'vector_to_float4'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_to_halfvec"("public"."vector", int4, bool);
CREATE OR REPLACE FUNCTION "vector_to_halfvec"("public"."vector", int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'vector_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_to_sparsevec"("public"."vector", int4, bool);
CREATE OR REPLACE FUNCTION "vector_to_sparsevec"("public"."vector", int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'vector_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_typmod_in
-- ----------------------------
DROP FUNCTION IF EXISTS "vector_typmod_in"(_cstring);
CREATE OR REPLACE FUNCTION "vector_typmod_in"(_cstring)
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'vector_typmod_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for word_similarity
-- ----------------------------
DROP FUNCTION IF EXISTS "word_similarity"(text, text);
CREATE OR REPLACE FUNCTION "word_similarity"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'word_similarity'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for word_similarity_commutator_op
-- ----------------------------
DROP FUNCTION IF EXISTS "word_similarity_commutator_op"(text, text);
CREATE OR REPLACE FUNCTION "word_similarity_commutator_op"(text, text)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'word_similarity_commutator_op'
  LANGUAGE c STABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for word_similarity_dist_commutator_op
-- ----------------------------
DROP FUNCTION IF EXISTS "word_similarity_dist_commutator_op"(text, text);
CREATE OR REPLACE FUNCTION "word_similarity_dist_commutator_op"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'word_similarity_dist_commutator_op'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for word_similarity_dist_op
-- ----------------------------
DROP FUNCTION IF EXISTS "word_similarity_dist_op"(text, text);
CREATE OR REPLACE FUNCTION "word_similarity_dist_op"(text, text)
  RETURNS "pg_catalog"."float4" AS '$libdir/pg_trgm', 'word_similarity_dist_op'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for word_similarity_op
-- ----------------------------
DROP FUNCTION IF EXISTS "word_similarity_op"(text, text);
CREATE OR REPLACE FUNCTION "word_similarity_op"(text, text)
  RETURNS "pg_catalog"."bool" AS '$libdir/pg_trgm', 'word_similarity_op'
  LANGUAGE c STABLE STRICT
  COST 1;

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_async_task_id_seq"
OWNED BY "agent_async_task"."id";
SELECT setval('"agent_async_task_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_config_id_seq"
OWNED BY "agent_config"."id";
SELECT setval('"agent_config_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_execution_event_id_seq"
OWNED BY "agent_execution_event"."id";
SELECT setval('"agent_execution_event_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_execution_id_seq"
OWNED BY "agent_execution"."id";
SELECT setval('"agent_execution_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_scheduled_task_id_seq"
OWNED BY "agent_scheduled_task"."id";
SELECT setval('"agent_scheduled_task_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_team_edge_id_seq"
OWNED BY "agent_team_edge"."id";
SELECT setval('"agent_team_edge_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_team_id_seq"
OWNED BY "agent_team"."id";
SELECT setval('"agent_team_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_team_intervention_id_seq"
OWNED BY "agent_team_intervention"."id";
SELECT setval('"agent_team_intervention_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_team_member_id_seq"
OWNED BY "agent_team_member"."id";
SELECT setval('"agent_team_member_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_team_run_id_seq"
OWNED BY "agent_team_run"."id";
SELECT setval('"agent_team_run_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_team_run_step_id_seq"
OWNED BY "agent_team_run_step"."id";
SELECT setval('"agent_team_run_step_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "agent_trace_id_seq"
OWNED BY "agent_trace"."id";
SELECT setval('"agent_trace_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_api_key_id_seq"
OWNED BY "ai_api_key"."id";
SELECT setval('"ai_api_key_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_chat_message_message_id_seq"
OWNED BY "ai_chat_message"."message_id";
SELECT setval('"ai_chat_message_message_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_chat_model_id_seq"
OWNED BY "ai_chat_model"."id";
SELECT setval('"ai_chat_model_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_chat_session_session_id_seq"
OWNED BY "ai_chat_session"."session_id";
SELECT setval('"ai_chat_session_session_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_evolution_config_id_seq"
OWNED BY "ai_skill_evolution_config"."id";
SELECT setval('"ai_skill_evolution_config_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_evolution_log_id_seq"
OWNED BY "ai_skill_evolution_log"."id";
SELECT setval('"ai_skill_evolution_log_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_hub_repo_id_seq"
OWNED BY "ai_skill_hub_repo"."id";
SELECT setval('"ai_skill_hub_repo_id_seq"', 3, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_metrics_id_seq"
OWNED BY "ai_skill_metrics"."id";
SELECT setval('"ai_skill_metrics_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_package_id_seq"
OWNED BY "ai_skill_package"."id";
SELECT setval('"ai_skill_package_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_rule_id_seq"
OWNED BY "ai_skill_rule"."id";
SELECT setval('"ai_skill_rule_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_script_id_seq"
OWNED BY "ai_skill_script"."id";
SELECT setval('"ai_skill_script_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_skill_version_id_seq"
OWNED BY "ai_skill_version"."id";
SELECT setval('"ai_skill_version_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_web_search_id_seq"
OWNED BY "ai_web_search"."id";
SELECT setval('"ai_web_search_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_web_search_log_id_seq"
OWNED BY "ai_web_search_log"."id";
SELECT setval('"ai_web_search_log_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "ai_workspace_id_seq"
OWNED BY "ai_workspace"."id";
SELECT setval('"ai_workspace_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"infra_file_content_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"infra_file_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"kms_legal_item_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"kms_legal_paper_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"kms_legal_paper_legal_item_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
SELECT setval('"legal_info_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "mcp_api_key_id_seq"
OWNED BY "ai_mcp_api_key"."id";
SELECT setval('"mcp_api_key_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "mcp_client_id_seq"
OWNED BY "ai_mcp_client"."id";
SELECT setval('"mcp_client_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "mcp_square_template_id_seq"
OWNED BY "ai_mcp_square_template"."id";
SELECT setval('"mcp_square_template_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_audit_log_log_id_seq"
OWNED BY "sys_audit_log"."log_id";
SELECT setval('"sys_audit_log_log_id_seq"', 138, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_dictionary_dict_id_seq"
OWNED BY "sys_dictionary"."dict_id";
SELECT setval('"sys_dictionary_dict_id_seq"', 136, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_dictionary_item_item_id_seq"
OWNED BY "sys_dictionary_item"."item_id";
SELECT setval('"sys_dictionary_item_item_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_menu_id_seq"
OWNED BY "sys_menu"."id";
SELECT setval('"sys_menu_id_seq"', 2, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_region_region_id_seq"
OWNED BY "sys_region"."region_id";
SELECT setval('"sys_region_region_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_role_menu_id_seq"
OWNED BY "sys_role_menu"."id";
SELECT setval('"sys_role_menu_id_seq"', 133, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_role_role_id_seq"
OWNED BY "sys_role"."role_id";
SELECT setval('"sys_role_role_id_seq"', 9999, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_tenant_package_package_id_seq"
OWNED BY "sys_tenant_package"."package_id";
SELECT setval('"sys_tenant_package_package_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_tenant_tenant_id_seq"
OWNED BY "sys_tenant"."tenant_id";
SELECT setval('"sys_tenant_tenant_id_seq"', 6, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_user_notification_id_seq"
OWNED BY "sys_user_notification"."id";
SELECT setval('"sys_user_notification_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_user_role_id_seq"
OWNED BY "sys_user_role"."id";
SELECT setval('"sys_user_role_id_seq"', 7, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "sys_user_user_id_seq"
OWNED BY "sys_user"."user_id";
SELECT setval('"sys_user_user_id_seq"', 9999, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "tool_definition_id_seq"
OWNED BY "ai_tool_definition"."id";
SELECT setval('"tool_definition_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "tool_group_id_seq"
OWNED BY "ai_tool_group"."id";
SELECT setval('"tool_group_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "wiki_article_id_seq"
OWNED BY "wiki_article"."id";
SELECT setval('"wiki_article_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "wiki_article_version_id_seq"
OWNED BY "wiki_article_version"."id";
SELECT setval('"wiki_article_version_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "wiki_category_id_seq"
OWNED BY "wiki_category"."id";
SELECT setval('"wiki_category_id_seq"', 1, false);

-- ----------------------------
-- Indexes structure for table agent_async_task
-- ----------------------------
CREATE INDEX "ix_agent_async_task_execution_id" ON "agent_async_task" USING btree (
  "execution_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_async_task_session_id" ON "agent_async_task" USING btree (
  "session_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_agent_async_task_task_no" ON "agent_async_task" USING btree (
  "task_no" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_async_task_tenant_id" ON "agent_async_task" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_async_task_user_id" ON "agent_async_task" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_async_task_status_user" ON "agent_async_task" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_async_task
-- ----------------------------
ALTER TABLE "agent_async_task" ADD CONSTRAINT "agent_async_task_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_config
-- ----------------------------
CREATE INDEX "idx_agent_config_active" ON "agent_config" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_config_category" ON "agent_config" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_config_mode" ON "agent_config" USING btree (
  "execution_mode" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_config_strategy" ON "agent_config" USING btree (
  "strategy_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_agent_config_agent_code" ON "agent_config" USING btree (
  "agent_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_config_strategy_code" ON "agent_config" USING btree (
  "strategy_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_config_tenant_id" ON "agent_config" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_config
-- ----------------------------
ALTER TABLE "agent_config" ADD CONSTRAINT "agent_config_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_execution
-- ----------------------------
CREATE INDEX "idx_execution_status" ON "agent_execution" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_execution_target" ON "agent_execution" USING btree (
  "target_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_execution_trace" ON "agent_execution" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_agent_execution_execution_id" ON "agent_execution" USING btree (
  "execution_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_session_id" ON "agent_execution" USING btree (
  "session_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_target_id" ON "agent_execution" USING btree (
  "target_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_tenant_id" ON "agent_execution" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_trace_id" ON "agent_execution" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_user_id" ON "agent_execution" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_execution
-- ----------------------------
ALTER TABLE "agent_execution" ADD CONSTRAINT "agent_execution_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_execution_event
-- ----------------------------
CREATE INDEX "idx_event_execution_seq" ON "agent_execution_event" USING btree (
  "execution_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "sequence" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_event_trace" ON "agent_execution_event" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_event_type" ON "agent_execution_event" USING btree (
  "event_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_event_execution_id" ON "agent_execution_event" USING btree (
  "execution_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_event_tenant_id" ON "agent_execution_event" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_execution_event_trace_id" ON "agent_execution_event" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_execution_event
-- ----------------------------
ALTER TABLE "agent_execution_event" ADD CONSTRAINT "agent_execution_event_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_scheduled_task
-- ----------------------------
CREATE INDEX "ix_agent_sched_user_status" ON "agent_scheduled_task" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_scheduled_task_tenant_id" ON "agent_scheduled_task" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_scheduled_task_user_id" ON "agent_scheduled_task" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_scheduled_task
-- ----------------------------
ALTER TABLE "agent_scheduled_task" ADD CONSTRAINT "agent_scheduled_task_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_team
-- ----------------------------
CREATE INDEX "idx_agent_team_active" ON "agent_team" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_team_category" ON "agent_team" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_team_workspace" ON "agent_team" USING btree (
  "workspace_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_agent_team_team_code" ON "agent_team" USING btree (
  "team_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_tenant_id" ON "agent_team" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_team
-- ----------------------------
ALTER TABLE "agent_team" ADD CONSTRAINT "agent_team_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_team_edge
-- ----------------------------
CREATE INDEX "idx_team_edge_team" ON "agent_team_edge" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_edge_to" ON "agent_team_edge" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST,
  "to_node_key" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_edge_team_id" ON "agent_team_edge" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_edge_tenant_id" ON "agent_team_edge" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table agent_team_edge
-- ----------------------------
ALTER TABLE "agent_team_edge" ADD CONSTRAINT "uq_team_edge" UNIQUE ("team_id", "from_node_key", "to_node_key");

-- ----------------------------
-- Primary Key structure for table agent_team_edge
-- ----------------------------
ALTER TABLE "agent_team_edge" ADD CONSTRAINT "agent_team_edge_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_team_intervention
-- ----------------------------
CREATE INDEX "idx_team_intervention_created" ON "agent_team_intervention" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_intervention_run" ON "agent_team_intervention" USING btree (
  "run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_intervention_run_id" ON "agent_team_intervention" USING btree (
  "run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_intervention_tenant_id" ON "agent_team_intervention" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_team_intervention
-- ----------------------------
ALTER TABLE "agent_team_intervention" ADD CONSTRAINT "agent_team_intervention_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_team_member
-- ----------------------------
CREATE INDEX "idx_team_member_agent" ON "agent_team_member" USING btree (
  "agent_config_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_member_team" ON "agent_team_member" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_member_agent_config_id" ON "agent_team_member" USING btree (
  "agent_config_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_member_team_id" ON "agent_team_member" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_member_tenant_id" ON "agent_team_member" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table agent_team_member
-- ----------------------------
ALTER TABLE "agent_team_member" ADD CONSTRAINT "uq_team_member_node_key" UNIQUE ("team_id", "node_key");

-- ----------------------------
-- Primary Key structure for table agent_team_member
-- ----------------------------
ALTER TABLE "agent_team_member" ADD CONSTRAINT "agent_team_member_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_team_run
-- ----------------------------
CREATE INDEX "idx_team_run_conversation" ON "agent_team_run" USING btree (
  "conversation_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_run_status" ON "agent_team_run" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_run_team_created" ON "agent_team_run" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_run_workspace" ON "agent_team_run" USING btree (
  "workspace_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_conversation_id" ON "agent_team_run" USING btree (
  "conversation_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_parent_run_id" ON "agent_team_run" USING btree (
  "parent_run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_agent_team_run_run_id" ON "agent_team_run" USING btree (
  "run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_team_id" ON "agent_team_run" USING btree (
  "team_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_tenant_id" ON "agent_team_run" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_workspace_id" ON "agent_team_run" USING btree (
  "workspace_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_team_run
-- ----------------------------
ALTER TABLE "agent_team_run" ADD CONSTRAINT "agent_team_run_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_team_run_step
-- ----------------------------
CREATE INDEX "idx_team_step_run_node" ON "agent_team_run_step" USING btree (
  "run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "node_key" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_team_step_run_seq" ON "agent_team_run_step" USING btree (
  "run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "seq" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_step_run_id" ON "agent_team_run_step" USING btree (
  "run_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_team_run_step_tenant_id" ON "agent_team_run_step" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_team_run_step
-- ----------------------------
ALTER TABLE "agent_team_run_step" ADD CONSTRAINT "agent_team_run_step_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_trace
-- ----------------------------
CREATE INDEX "ix_agent_trace_agent_config_id" ON "agent_trace" USING btree (
  "agent_config_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_trace_agent_id" ON "agent_trace" USING btree (
  "agent_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_trace_session_id" ON "agent_trace" USING btree (
  "session_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_trace_team_config_id" ON "agent_trace" USING btree (
  "team_config_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_trace_tenant_id" ON "agent_trace" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_trace_trace_id" ON "agent_trace" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_trace_user_id" ON "agent_trace" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_trace
-- ----------------------------
ALTER TABLE "agent_trace" ADD CONSTRAINT "agent_trace_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_api_key
-- ----------------------------
CREATE INDEX "ix_ai_api_key_platform" ON "ai_api_key" USING btree (
  "platform" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_api_key_tenant_id" ON "ai_api_key" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_api_key
-- ----------------------------
ALTER TABLE "ai_api_key" ADD CONSTRAINT "ai_api_key_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_chat_message
-- ----------------------------
CREATE INDEX "ix_ai_chat_message_execution_id" ON "ai_chat_message" USING btree (
  "execution_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_chat_message_file_id" ON "ai_chat_message" USING btree (
  "file_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_chat_message_session_id" ON "ai_chat_message" USING btree (
  "session_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_chat_message_tenant_id" ON "ai_chat_message" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_chat_message
-- ----------------------------
ALTER TABLE "ai_chat_message" ADD CONSTRAINT "ai_chat_message_pkey" PRIMARY KEY ("message_id");

-- ----------------------------
-- Indexes structure for table ai_chat_model
-- ----------------------------
CREATE INDEX "ix_ai_chat_model_key_id" ON "ai_chat_model" USING btree (
  "key_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_chat_model_tenant_id" ON "ai_chat_model" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_chat_model
-- ----------------------------
ALTER TABLE "ai_chat_model" ADD CONSTRAINT "ai_chat_model_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_chat_session
-- ----------------------------
CREATE INDEX "ix_ai_chat_session_agent_id" ON "ai_chat_session" USING btree (
  "agent_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_chat_session_tenant_id" ON "ai_chat_session" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_chat_session_user_id" ON "ai_chat_session" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_chat_session
-- ----------------------------
ALTER TABLE "ai_chat_session" ADD CONSTRAINT "ai_chat_session_pkey" PRIMARY KEY ("session_id");

-- ----------------------------
-- Indexes structure for table ai_mcp_api_key
-- ----------------------------
CREATE INDEX "idx_mcp_apikey_status" ON "ai_mcp_api_key" USING btree (
  "status" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_mcp_apikey_template" ON "ai_mcp_api_key" USING btree (
  "template_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_mcp_api_key_tenant_id" ON "ai_mcp_api_key" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_mcp_api_key
-- ----------------------------
ALTER TABLE "ai_mcp_api_key" ADD CONSTRAINT "mcp_api_key_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_mcp_client
-- ----------------------------
CREATE INDEX "idx_mcp_client_active" ON "ai_mcp_client" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_mcp_client_apikey" ON "ai_mcp_client" USING btree (
  "api_key_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_mcp_client_tenant_id" ON "ai_mcp_client" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_mcp_client
-- ----------------------------
ALTER TABLE "ai_mcp_client" ADD CONSTRAINT "mcp_client_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_mcp_square_template
-- ----------------------------
CREATE INDEX "idx_mcp_template_category" ON "ai_mcp_square_template" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_mcp_template_status" ON "ai_mcp_square_template" USING btree (
  "status" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_mcp_square_template_tenant_id" ON "ai_mcp_square_template" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_mcp_square_template
-- ----------------------------
ALTER TABLE "ai_mcp_square_template" ADD CONSTRAINT "mcp_square_template_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_evolution_config
-- ----------------------------
CREATE INDEX "ix_ai_skill_evolution_config_model_code" ON "ai_skill_evolution_config" USING btree (
  "model_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_ai_skill_evolution_config_skill_id" ON "ai_skill_evolution_config" USING btree (
  "skill_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_skill_evolution_config_tenant_id" ON "ai_skill_evolution_config" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_skill_evolution_config
-- ----------------------------
ALTER TABLE "ai_skill_evolution_config" ADD CONSTRAINT "ai_skill_evolution_config_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_evolution_log
-- ----------------------------
CREATE INDEX "ix_ai_skill_evolution_log_skill_id" ON "ai_skill_evolution_log" USING btree (
  "skill_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_skill_evolution_log_tenant_id" ON "ai_skill_evolution_log" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_skill_evolution_log
-- ----------------------------
ALTER TABLE "ai_skill_evolution_log" ADD CONSTRAINT "ai_skill_evolution_log_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_hub_repo
-- ----------------------------
CREATE INDEX "ix_ai_skill_hub_repo_tenant_id" ON "ai_skill_hub_repo" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table ai_skill_hub_repo
-- ----------------------------
ALTER TABLE "ai_skill_hub_repo" ADD CONSTRAINT "ai_skill_hub_repo_url_key" UNIQUE ("url");

-- ----------------------------
-- Primary Key structure for table ai_skill_hub_repo
-- ----------------------------
ALTER TABLE "ai_skill_hub_repo" ADD CONSTRAINT "ai_skill_hub_repo_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_metrics
-- ----------------------------
CREATE INDEX "ix_ai_skill_metrics_tenant_id" ON "ai_skill_metrics" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table ai_skill_metrics
-- ----------------------------
ALTER TABLE "ai_skill_metrics" ADD CONSTRAINT "ai_skill_metrics_skill_id_key" UNIQUE ("skill_id");

-- ----------------------------
-- Primary Key structure for table ai_skill_metrics
-- ----------------------------
ALTER TABLE "ai_skill_metrics" ADD CONSTRAINT "ai_skill_metrics_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_package
-- ----------------------------
CREATE INDEX "idx_skill_package_category" ON "ai_skill_package" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_skill_package_enabled" ON "ai_skill_package" USING btree (
  "enabled" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_skill_package_tenant_id" ON "ai_skill_package" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table ai_skill_package
-- ----------------------------
ALTER TABLE "ai_skill_package" ADD CONSTRAINT "ai_skill_package_package_id_key" UNIQUE ("package_id");

-- ----------------------------
-- Primary Key structure for table ai_skill_package
-- ----------------------------
ALTER TABLE "ai_skill_package" ADD CONSTRAINT "ai_skill_package_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_rule
-- ----------------------------
CREATE INDEX "ix_ai_skill_rule_agent_name" ON "ai_skill_rule" USING btree (
  "agent_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_skill_rule_tenant_id" ON "ai_skill_rule" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_skill_rule
-- ----------------------------
ALTER TABLE "ai_skill_rule" ADD CONSTRAINT "ai_skill_rule_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_script
-- ----------------------------
CREATE INDEX "idx_skill_script_enabled" ON "ai_skill_script" USING btree (
  "enabled" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_skill_script_package" ON "ai_skill_script" USING btree (
  "package_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_skill_script_tenant_id" ON "ai_skill_script" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table ai_skill_script
-- ----------------------------
ALTER TABLE "ai_skill_script" ADD CONSTRAINT "ai_skill_script_package_id_script_id_key" UNIQUE ("package_id", "script_id");

-- ----------------------------
-- Primary Key structure for table ai_skill_script
-- ----------------------------
ALTER TABLE "ai_skill_script" ADD CONSTRAINT "ai_skill_script_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_skill_version
-- ----------------------------
CREATE INDEX "ix_ai_skill_version_skill_id" ON "ai_skill_version" USING btree (
  "skill_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_skill_version_tenant_id" ON "ai_skill_version" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_skill_version
-- ----------------------------
ALTER TABLE "ai_skill_version" ADD CONSTRAINT "ai_skill_version_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_tool_definition
-- ----------------------------
CREATE INDEX "idx_tool_definition_category" ON "ai_tool_definition" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_tool_definition_is_system" ON "ai_tool_definition" USING btree (
  "is_system" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_tool_definition_status" ON "ai_tool_definition" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "idx_tool_definition_tool_key" ON "ai_tool_definition" USING btree (
  "tool_key" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_tool_definition_type" ON "ai_tool_definition" USING btree (
  "tool_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tool_definition_tenant_id" ON "ai_tool_definition" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table ai_tool_definition
-- ----------------------------
ALTER TABLE "ai_tool_definition" ADD CONSTRAINT "tool_definition_tool_key_key" UNIQUE ("tool_key");

-- ----------------------------
-- Primary Key structure for table ai_tool_definition
-- ----------------------------
ALTER TABLE "ai_tool_definition" ADD CONSTRAINT "tool_definition_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_tool_group
-- ----------------------------
CREATE INDEX "idx_tool_group_active" ON "ai_tool_group" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tool_group_tenant_id" ON "ai_tool_group" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table ai_tool_group
-- ----------------------------
ALTER TABLE "ai_tool_group" ADD CONSTRAINT "tool_group_name_key" UNIQUE ("name");

-- ----------------------------
-- Primary Key structure for table ai_tool_group
-- ----------------------------
ALTER TABLE "ai_tool_group" ADD CONSTRAINT "tool_group_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_tool_group_member
-- ----------------------------
CREATE INDEX "idx_tool_group_member_tool" ON "ai_tool_group_member" USING btree (
  "tool_key" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tool_group_member_tenant_id" ON "ai_tool_group_member" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_tool_group_member
-- ----------------------------
ALTER TABLE "ai_tool_group_member" ADD CONSTRAINT "tool_group_member_pkey" PRIMARY KEY ("group_id", "tool_key");

-- ----------------------------
-- Indexes structure for table ai_web_search
-- ----------------------------
CREATE INDEX "ix_ai_web_search_platform" ON "ai_web_search" USING btree (
  "platform" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_web_search_tenant_id" ON "ai_web_search" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_web_search
-- ----------------------------
ALTER TABLE "ai_web_search" ADD CONSTRAINT "ai_web_search_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_web_search_log
-- ----------------------------
CREATE INDEX "ix_ai_web_search_log_created_at" ON "ai_web_search_log" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_web_search_log_tenant_id" ON "ai_web_search_log" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_ai_web_search_log_web_search_id" ON "ai_web_search_log" USING btree (
  "web_search_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_web_search_log
-- ----------------------------
ALTER TABLE "ai_web_search_log" ADD CONSTRAINT "ai_web_search_log_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table ai_workspace
-- ----------------------------
CREATE INDEX "ix_ai_workspace_tenant_id" ON "ai_workspace" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_ai_workspace_workspace_id" ON "ai_workspace" USING btree (
  "workspace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_workspace
-- ----------------------------
ALTER TABLE "ai_workspace" ADD CONSTRAINT "ai_workspace_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table alembic_version
-- ----------------------------
ALTER TABLE "alembic_version" ADD CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num");

-- ----------------------------
-- Indexes structure for table sys_audit_log
-- ----------------------------
CREATE INDEX "idx_audit_operation" ON "sys_audit_log" USING btree (
  "operation_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "operation_module" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_audit_log_created_at" ON "sys_audit_log" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_audit_log_request_ip" ON "sys_audit_log" USING btree (
  "request_ip" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_audit_log_tenant_id" ON "sys_audit_log" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_audit_log_user_id" ON "sys_audit_log" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_audit_log
-- ----------------------------
ALTER TABLE "sys_audit_log" ADD CONSTRAINT "sys_audit_log_pkey" PRIMARY KEY ("log_id");

-- ----------------------------
-- Indexes structure for table sys_dictionary
-- ----------------------------
CREATE INDEX "idx_dict_active" ON "sys_dictionary" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "idx_dict_code" ON "sys_dictionary" USING btree (
  "dict_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "idx_dict_type" ON "sys_dictionary" USING btree (
  "dict_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "ix_sys_dictionary_tenant_id" ON "sys_dictionary" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table sys_dictionary
-- ----------------------------
ALTER TABLE "sys_dictionary" ADD CONSTRAINT "sys_dictionary_dict_code_key" UNIQUE ("dict_code");

-- ----------------------------
-- Primary Key structure for table sys_dictionary
-- ----------------------------
ALTER TABLE "sys_dictionary" ADD CONSTRAINT "sys_dictionary_pkey" PRIMARY KEY ("dict_id");

-- ----------------------------
-- Indexes structure for table sys_dictionary_item
-- ----------------------------
CREATE INDEX "idx_dict_item_code_order" ON "sys_dictionary_item" USING btree (
  "dict_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "sort_order" "pg_catalog"."int4_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "idx_item_active" ON "sys_dictionary_item" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "idx_item_code" ON "sys_dictionary_item" USING btree (
  "item_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "idx_item_dict_code" ON "sys_dictionary_item" USING btree (
  "dict_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "idx_item_parent" ON "sys_dictionary_item" USING btree (
  "parent_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
) WHERE is_deleted = false;
CREATE INDEX "ix_sys_dictionary_item_tenant_id" ON "sys_dictionary_item" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table sys_dictionary_item
-- ----------------------------
ALTER TABLE "sys_dictionary_item" ADD CONSTRAINT "sys_dictionary_item_dict_code_item_code_key" UNIQUE ("dict_code", "item_code");

-- ----------------------------
-- Primary Key structure for table sys_dictionary_item
-- ----------------------------
ALTER TABLE "sys_dictionary_item" ADD CONSTRAINT "sys_dictionary_item_pkey" PRIMARY KEY ("item_id");

-- ----------------------------
-- Indexes structure for table sys_infra_file
-- ----------------------------
CREATE INDEX "ix_infra_file_config_id" ON "sys_infra_file" USING btree (
  "config_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_infra_file_tenant_id" ON "sys_infra_file" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_infra_file
-- ----------------------------
ALTER TABLE "sys_infra_file" ADD CONSTRAINT "infra_file_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table sys_infra_file_content
-- ----------------------------
CREATE INDEX "ix_infra_file_content_config_id" ON "sys_infra_file_content" USING btree (
  "config_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_infra_file_content_tenant_id" ON "sys_infra_file_content" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_infra_file_content
-- ----------------------------
ALTER TABLE "sys_infra_file_content" ADD CONSTRAINT "infra_file_content_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table sys_menu
-- ----------------------------
CREATE INDEX "ix_sys_menu_parent_id" ON "sys_menu" USING btree (
  "parent_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_menu_permission" ON "sys_menu" USING btree (
  "permission" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_menu
-- ----------------------------
ALTER TABLE "sys_menu" ADD CONSTRAINT "sys_menu_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table sys_region
-- ----------------------------
ALTER TABLE "sys_region" ADD CONSTRAINT "sys_region_region_code_key" UNIQUE ("region_code");

-- ----------------------------
-- Primary Key structure for table sys_region
-- ----------------------------
ALTER TABLE "sys_region" ADD CONSTRAINT "sys_region_pkey" PRIMARY KEY ("region_id");

-- ----------------------------
-- Indexes structure for table sys_role
-- ----------------------------
CREATE INDEX "ix_sys_role_tenant_id" ON "sys_role" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table sys_role
-- ----------------------------
ALTER TABLE "sys_role" ADD CONSTRAINT "sys_role_role_code_key" UNIQUE ("role_code");

-- ----------------------------
-- Primary Key structure for table sys_role
-- ----------------------------
ALTER TABLE "sys_role" ADD CONSTRAINT "sys_role_pkey" PRIMARY KEY ("role_id");

-- ----------------------------
-- Primary Key structure for table sys_role_menu
-- ----------------------------
ALTER TABLE "sys_role_menu" ADD CONSTRAINT "sys_role_menu_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table sys_tenant
-- ----------------------------
ALTER TABLE "sys_tenant" ADD CONSTRAINT "sys_tenant_name_key" UNIQUE ("name");

-- ----------------------------
-- Primary Key structure for table sys_tenant
-- ----------------------------
ALTER TABLE "sys_tenant" ADD CONSTRAINT "sys_tenant_pkey" PRIMARY KEY ("tenant_id");

-- ----------------------------
-- Primary Key structure for table sys_tenant_package
-- ----------------------------
ALTER TABLE "sys_tenant_package" ADD CONSTRAINT "sys_tenant_package_pkey" PRIMARY KEY ("package_id");

-- ----------------------------
-- Indexes structure for table sys_user
-- ----------------------------
CREATE INDEX "ix_sys_user_tenant_id" ON "sys_user" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_sys_user_username" ON "sys_user" USING btree (
  "username" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_user
-- ----------------------------
ALTER TABLE "sys_user" ADD CONSTRAINT "sys_user_pkey" PRIMARY KEY ("user_id");

-- ----------------------------
-- Indexes structure for table sys_user_notification
-- ----------------------------
CREATE INDEX "ix_notif_user_read" ON "sys_user_notification" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "is_read" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_user_notification_created_at" ON "sys_user_notification" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_user_notification_tenant_id" ON "sys_user_notification" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_sys_user_notification_user_id" ON "sys_user_notification" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_user_notification
-- ----------------------------
ALTER TABLE "sys_user_notification" ADD CONSTRAINT "sys_user_notification_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table sys_user_role
-- ----------------------------
CREATE INDEX "ix_sys_user_role_tenant_id" ON "sys_user_role" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table sys_user_role
-- ----------------------------
ALTER TABLE "sys_user_role" ADD CONSTRAINT "sys_user_role_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table wiki_article
-- ----------------------------
CREATE INDEX "idx_wiki_article_category" ON "wiki_article" USING btree (
  "category_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "idx_wiki_article_slug" ON "wiki_article" USING btree (
  "slug" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_wiki_article_status" ON "wiki_article" USING btree (
  "status" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_wiki_article_category_id" ON "wiki_article" USING btree (
  "category_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_wiki_article_slug" ON "wiki_article" USING btree (
  "slug" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_wiki_article_tenant_id" ON "wiki_article" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table wiki_article
-- ----------------------------
ALTER TABLE "wiki_article" ADD CONSTRAINT "wiki_article_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table wiki_article_version
-- ----------------------------
CREATE UNIQUE INDEX "idx_wiki_version_article_version" ON "wiki_article_version" USING btree (
  "article_id" "pg_catalog"."int8_ops" ASC NULLS LAST,
  "version" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_wiki_article_version_article_id" ON "wiki_article_version" USING btree (
  "article_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ix_wiki_article_version_tenant_id" ON "wiki_article_version" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table wiki_article_version
-- ----------------------------
ALTER TABLE "wiki_article_version" ADD CONSTRAINT "wiki_article_version_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table wiki_category
-- ----------------------------
CREATE INDEX "idx_wiki_category_parent" ON "wiki_category" USING btree (
  "parent_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "idx_wiki_category_slug" ON "wiki_category" USING btree (
  "slug" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_wiki_category_parent_id" ON "wiki_category" USING btree (
  "parent_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_wiki_category_slug" ON "wiki_category" USING btree (
  "slug" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_wiki_category_tenant_id" ON "wiki_category" USING btree (
  "tenant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table wiki_category
-- ----------------------------
ALTER TABLE "wiki_category" ADD CONSTRAINT "wiki_category_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table ai_chat_message
-- ----------------------------
ALTER TABLE "ai_chat_message" ADD CONSTRAINT "ai_chat_message_file_id_fkey" FOREIGN KEY ("file_id") REFERENCES "sys_infra_file" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "ai_chat_message" ADD CONSTRAINT "ai_chat_message_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "ai_chat_session" ("session_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table ai_chat_model
-- ----------------------------
ALTER TABLE "ai_chat_model" ADD CONSTRAINT "ai_chat_model_key_id_fkey" FOREIGN KEY ("key_id") REFERENCES "ai_api_key" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table ai_mcp_client
-- ----------------------------
ALTER TABLE "ai_mcp_client" ADD CONSTRAINT "mcp_client_api_key_id_fkey" FOREIGN KEY ("api_key_id") REFERENCES "ai_mcp_api_key" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table ai_tool_group_member
-- ----------------------------
ALTER TABLE "ai_tool_group_member" ADD CONSTRAINT "tool_group_member_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "ai_tool_group" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "ai_tool_group_member" ADD CONSTRAINT "tool_group_member_tool_key_fkey" FOREIGN KEY ("tool_key") REFERENCES "ai_tool_definition" ("tool_key") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table ai_workspace
-- ----------------------------
ALTER TABLE "ai_workspace" ADD CONSTRAINT "ai_workspace_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "sys_user" ("user_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table sys_role_menu
-- ----------------------------
ALTER TABLE "sys_role_menu" ADD CONSTRAINT "sys_role_menu_menu_id_fkey" FOREIGN KEY ("menu_id") REFERENCES "sys_menu" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "sys_role_menu" ADD CONSTRAINT "sys_role_menu_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "sys_role" ("role_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table sys_tenant
-- ----------------------------
ALTER TABLE "sys_tenant" ADD CONSTRAINT "sys_tenant_package_id_fkey" FOREIGN KEY ("package_id") REFERENCES "sys_tenant_package" ("package_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table sys_user_role
-- ----------------------------
ALTER TABLE "sys_user_role" ADD CONSTRAINT "sys_user_role_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "sys_role" ("role_id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "sys_user_role" ADD CONSTRAINT "sys_user_role_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "sys_user" ("user_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table wiki_article_version
-- ----------------------------
ALTER TABLE "wiki_article_version" ADD CONSTRAINT "wiki_article_version_article_id_fkey" FOREIGN KEY ("article_id") REFERENCES "wiki_article" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table wiki_category
-- ----------------------------
ALTER TABLE "wiki_category" ADD CONSTRAINT "wiki_category_parent_id_fkey" FOREIGN KEY ("parent_id") REFERENCES "wiki_category" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
