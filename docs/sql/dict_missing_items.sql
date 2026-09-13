-- ============================================================================
-- 补充缺失的数据字典及字典项
-- 来源：views/ 目录下 Vue 组件中硬编码的下拉选项，在 sys_dictionary 中无对应记录
-- 格式与 sys_dictionary.sql / menu_init.sql 保持一致，幂等可重复执行
-- Date: 2026-09-13
-- ============================================================================

-- ==========================================
-- 1. ai_platform — AI 模型供应商平台
--    原硬编码位置：api/ai-apikey.ts AI_PLATFORMS 常量
--    使用组件：ApiKeyFormModal.vue、ApiKeyManagement.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (140, 'ai_platform', 'AI模型供应商', 'system', 'AI API Key 管理中的供应商平台选择', 200, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (900, 'ai_platform', 'openai',       'OpenAI',     'openai',       NULL::varchar, 1, 'green',   NULL::varchar, 10,  true, NULL::json, 'GPT 系列模型',   NULL::int8, now(), now(), false, NULL::int8),
  (901, 'ai_platform', 'qwen',         '通义千问',    'qwen',         NULL::varchar, 1, 'blue',    NULL::varchar, 20,  true, NULL::json, '阿里云通义千问',  NULL::int8, now(), now(), false, NULL::int8),
  (902, 'ai_platform', 'zhipu',        '智谱',        'zhipu',        NULL::varchar, 1, 'purple',  NULL::varchar, 30,  true, NULL::json, '智谱 AI GLM 系列', NULL::int8, now(), now(), false, NULL::int8),
  (903, 'ai_platform', 'iflytek',      '讯飞',        'iflytek',      NULL::varchar, 1, 'cyan',    NULL::varchar, 40,  true, NULL::json, '科大讯飞星火',    NULL::int8, now(), now(), false, NULL::int8),
  (904, 'ai_platform', 'baidu',        '百度',        'baidu',        NULL::varchar, 1, 'orange',  NULL::varchar, 50,  true, NULL::json, '百度文心一言',    NULL::int8, now(), now(), false, NULL::int8),
  (905, 'ai_platform', 'claude',       'Claude',      'claude',       NULL::varchar, 1, 'volcano', NULL::varchar, 60,  true, NULL::json, 'Anthropic Claude', NULL::int8, now(), now(), false, NULL::int8),
  (906, 'ai_platform', 'gemini',       'Gemini',      'gemini',       NULL::varchar, 1, 'geekblue', NULL::varchar, 70, true, NULL::json, 'Google Gemini',   NULL::int8, now(), now(), false, NULL::int8),
  (907, 'ai_platform', 'dify',         'Dify',        'dify',         NULL::varchar, 1, 'default', NULL::varchar, 80,  true, NULL::json, 'Dify 开源 LLMOps', NULL::int8, now(), now(), false, NULL::int8),
  (908, 'ai_platform', 'coze',         'Coze',        'coze',         NULL::varchar, 1, 'magenta', NULL::varchar, 90,  true, NULL::json, '字节跳动 Coze',   NULL::int8, now(), now(), false, NULL::int8),
  (909, 'ai_platform', 'other',        '其他',        'other',        NULL::varchar, 1, 'default', NULL::varchar, 99,  true, NULL::json, '自定义供应商',    NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 2. mcp_service_type — MCP 服务注册类型
--    原硬编码位置：McpServiceManagement.vue <a-select-option>
--    使用组件：McpServiceManagement.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (141, 'mcp_service_type', 'MCP服务类型', 'system', 'MCP 服务注册中心类型', 210, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (910, 'mcp_service_type', 'nacos2', 'Nacos 2.x', 'nacos2', NULL::varchar, 1, 'blue',   NULL::varchar, 10, true, NULL::json, 'Nacos 2.x 注册中心', NULL::int8, now(), now(), false, NULL::int8),
  (911, 'mcp_service_type', 'nacos3', 'Nacos 3.x', 'nacos3', NULL::varchar, 1, 'geekblue', NULL::varchar, 20, true, NULL::json, 'Nacos 3.x 注册中心', NULL::int8, now(), now(), false, NULL::int8),
  (912, 'mcp_service_type', 'http',   'HTTP',      'http',   NULL::varchar, 1, 'green',  NULL::varchar, 30, true, NULL::json, 'HTTP 直连',          NULL::int8, now(), now(), false, NULL::int8),
  (913, 'mcp_service_type', 'sse',    'SSE',       'sse',    NULL::varchar, 1, 'purple', NULL::varchar, 40, true, NULL::json, 'Server-Sent Events',  NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 3. mcp_category — MCP 广场分类
--    原硬编码位置：McpServiceManagement.vue、McpInstallModal.vue 等
--    使用组件：McpServiceManagement.vue、McpInstallModal.vue、McpSquareDetailModal.vue、McpSquareTemplateFormModal.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (142, 'mcp_category', 'MCP广场分类', 'system', 'MCP 服务广场模板分类', 220, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (920, 'mcp_category', 'finance',   '金融',   'finance',   NULL::varchar, 1, 'blue',    NULL::varchar, 10, true, NULL::json, '金融类 MCP 服务',   NULL::int8, now(), now(), false, NULL::int8),
  (921, 'mcp_category', 'sales',     '销售',   'sales',     NULL::varchar, 1, 'green',   NULL::varchar, 20, true, NULL::json, '销售类 MCP 服务',   NULL::int8, now(), now(), false, NULL::int8),
  (922, 'mcp_category', 'office',    '办公',   'office',    NULL::varchar, 1, 'cyan',    NULL::varchar, 30, true, NULL::json, '办公协作类 MCP 服务', NULL::int8, now(), now(), false, NULL::int8),
  (923, 'mcp_category', 'education', '教育',   'education', NULL::varchar, 1, 'orange',  NULL::varchar, 40, true, NULL::json, '教育类 MCP 服务',   NULL::int8, now(), now(), false, NULL::int8),
  (924, 'mcp_category', 'legal',     '法律',   'legal',     NULL::varchar, 1, 'purple',  NULL::varchar, 50, true, NULL::json, '法律类 MCP 服务',   NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 4. execution_status — 异步任务执行状态
--    原硬编码位置：AsyncTaskManage.vue statusLabel()、ScheduledTaskManage.vue
--    使用组件：AsyncTaskManage.vue、ScheduledTaskManage.vue、WorkflowExecutionTable.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (143, 'execution_status', '执行状态', 'system', '异步任务 / 工作流执行状态', 230, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (930, 'execution_status', 'queued',    '排队中',   'queued',    NULL::varchar, 1, 'default',   NULL::varchar, 10, true, NULL::json, '任务已提交等待执行',   NULL::int8, now(), now(), false, NULL::int8),
  (931, 'execution_status', 'running',   '执行中',   'running',   NULL::varchar, 1, 'processing', NULL::varchar, 20, true, NULL::json, '任务正在执行中',       NULL::int8, now(), now(), false, NULL::int8),
  (932, 'execution_status', 'completed', '已完成',   'completed', NULL::varchar, 1, 'success',   NULL::varchar, 30, true, NULL::json, '任务已成功完成',       NULL::int8, now(), now(), false, NULL::int8),
  (933, 'execution_status', 'failed',    '失败',     'failed',    NULL::varchar, 1, 'error',     NULL::varchar, 40, true, NULL::json, '任务执行失败',         NULL::int8, now(), now(), false, NULL::int8),
  (934, 'execution_status', 'cancelled', '已取消',   'cancelled', NULL::varchar, 1, 'warning',   NULL::varchar, 50,  true, NULL::json, '任务已被取消',         NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 5. workflow_exec_status — 工作流执行状态
--    原硬编码位置：WorkflowExecutionTable.vue <a-select-option>、statusColor()
--    使用组件：WorkflowExecutionTable.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (144, 'workflow_exec_status', '工作流执行状态', 'system', '工作流执行实例状态', 240, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (940, 'workflow_exec_status', 'success', '成功',   'success', NULL::varchar, 1, 'green',  NULL::varchar, 10, true, NULL::json, '工作流执行成功', NULL::int8, now(), now(), false, NULL::int8),
  (941, 'workflow_exec_status', 'failed',  '失败',   'failed',  NULL::varchar, 1, 'red',    NULL::varchar, 20, true, NULL::json, '工作流执行失败', NULL::int8, now(), now(), false, NULL::int8),
  (942, 'workflow_exec_status', 'running', '运行中', 'running', NULL::varchar, 1, 'blue',   NULL::varchar, 30, true, NULL::json, '工作流正在运行', NULL::int8, now(), now(), false, NULL::int8),
  (943, 'workflow_exec_status', 'pending', '等待中', 'pending', NULL::varchar, 1, 'default', NULL::varchar, 40, true, NULL::json, '工作流等待执行', NULL::int8, now(), now(), false, NULL::int8),
  (944, 'workflow_exec_status', 'timeout', '超时',   'timeout', NULL::varchar, 1, 'orange', NULL::varchar, 50, true, NULL::json, '工作流执行超时', NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 6. mcp_client_transport — MCP 客户端传输协议类型
--    原硬编码位置：McpClientFormModal.vue <a-select-option>
--    使用组件：McpClientFormModal.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (145, 'mcp_client_transport', 'MCP客户端传输协议', 'system', 'MCP 客户端连接传输协议类型', 250, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (950, 'mcp_client_transport', 'stdio', 'Stdio',     'stdio', NULL::varchar, 1, 'blue',   NULL::varchar, 10, true, NULL::json, '标准输入输出',      NULL::int8, now(), now(), false, NULL::int8),
  (951, 'mcp_client_transport', 'http',  'HTTP',      'http',  NULL::varchar, 1, 'green',  NULL::varchar, 20, true, NULL::json, 'HTTP 传输',         NULL::int8, now(), now(), false, NULL::int8),
  (952, 'mcp_client_transport', 'sse',   'SSE',       'sse',   NULL::varchar, 1, 'purple', NULL::varchar, 30, true, NULL::json, 'Server-Sent Events', NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 7. mcp_capability — MCP 服务能力类型
--    原硬编码位置：McpSquareTemplateFormModal.vue、McpClientFormModal.vue
--    使用组件：McpSquareTemplateFormModal.vue、McpClientFormModal.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (146, 'mcp_capability', 'MCP服务能力类型', 'system', 'MCP 服务支持的能力集（Tools/Resources/Prompts）', 260, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (960, 'mcp_capability', 'tools',     'Tools',     'tools',     NULL::varchar, 1, 'blue',   NULL::varchar, 10, true, NULL::json, '工具调用能力',   NULL::int8, now(), now(), false, NULL::int8),
  (961, 'mcp_capability', 'resources', 'Resources', 'resources', NULL::varchar, 1, 'green',  NULL::varchar, 20, true, NULL::json, '资源访问能力',   NULL::int8, now(), now(), false, NULL::int8),
  (962, 'mcp_capability', 'prompts',   'Prompts',   'prompts',   NULL::varchar, 1, 'purple', NULL::varchar, 30, true, NULL::json, '提示词模板能力', NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 8. scheduled_task_status — 调度任务状态
--    原硬编码位置：ScheduledTaskManage.vue statusOptions
--    使用组件：ScheduledTaskManage.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (147, 'scheduled_task_status', '调度任务状态', 'system', '定时调度任务运行状态', 270, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (970, 'scheduled_task_status', 'enabled', '启用中', 'enabled', NULL::varchar, 1, 'processing', NULL::varchar, 10, true, NULL::json, '调度任务已启用', NULL::int8, now(), now(), false, NULL::int8),
  (971, 'scheduled_task_status', 'paused',  '已暂停', 'paused',  NULL::varchar, 1, 'default',    NULL::varchar, 20, true, NULL::json, '调度任务已暂停', NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 9. schedule_type — 调度类型
--    原硬编码位置：ScheduledTaskManage.vue scheduleTypeOptions
--    使用组件：ScheduledTaskManage.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (148, 'schedule_type', '调度类型', 'system', '定时任务的调度触发方式', 280, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (980, 'schedule_type', 'cron',     'Cron 定时',   'cron',     NULL::varchar, 1, 'blue',    NULL::varchar, 10, true, NULL::json, 'Cron 表达式定时触发', NULL::int8, now(), now(), false, NULL::int8),
  (981, 'schedule_type', 'interval', '固定间隔',    'interval', NULL::varchar, 1, 'green',   NULL::varchar, 20, true, NULL::json, '固定秒数间隔触发',    NULL::int8, now(), now(), false, NULL::int8),
  (982, 'schedule_type', 'once',     '单次执行',    'once',     NULL::varchar, 1, 'default', NULL::varchar, 30, true, NULL::json, '指定时间单次执行',    NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 10. target_mode — 异步任务执行类型
--     原硬编码位置：ScheduledTaskManage.vue targetModeOptions、AsyncTaskManage.vue modeFilterOptions
--     使用组件：ScheduledTaskManage.vue、AsyncTaskManage.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (149, 'target_mode', '任务执行类型', 'system', '异步任务 / 调度任务的执行模式', 290, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (990, 'target_mode', 'deep_research', '深度研究',   'deep_research', NULL::varchar, 1, 'geekblue', NULL::varchar, 10, true, NULL::json, '深度研究模式',   NULL::int8, now(), now(), false, NULL::int8),
  (991, 'target_mode', 'agent',         '智能体',     'agent',         NULL::varchar, 1, 'green',    NULL::varchar, 20, true, NULL::json, '单智能体执行',   NULL::int8, now(), now(), false, NULL::int8),
  (992, 'target_mode', 'team',          '专家团队',   'team',          NULL::varchar, 1, 'purple',   NULL::varchar, 30, true, NULL::json, '智能体团队执行', NULL::int8, now(), now(), false, NULL::int8),
  (993, 'target_mode', 'skill',         '技能',       'skill',         NULL::varchar, 1, 'cyan',     NULL::varchar, 40, true, NULL::json, '技能包执行',     NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 11. agent_exec_mode — Agent 执行调用模式
--     原硬编码位置：AgentExecutionManagement.vue modeOptions
--     使用组件：AgentExecutionManagement.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (150, 'agent_exec_mode', 'Agent执行模式', 'system', 'Agent 执行管理的调用模式筛选', 300, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (1000, 'agent_exec_mode', 'dify',      'Dify',       'dify',      NULL::varchar, 1, 'blue',   NULL::varchar, 10, true, NULL::json, 'Dify 工作流执行',  NULL::int8, now(), now(), false, NULL::int8),
  (1001, 'agent_exec_mode', 'skill',     'Skill',      'skill',     NULL::varchar, 1, 'cyan',   NULL::varchar, 20, true, NULL::json, '技能执行',         NULL::int8, now(), now(), false, NULL::int8),
  (1002, 'agent_exec_mode', 'agent',     'Agent',      'agent',     NULL::varchar, 1, 'green',  NULL::varchar, 30, true, NULL::json, '单智能体执行',     NULL::int8, now(), now(), false, NULL::int8),
  (1003, 'agent_exec_mode', 'agent_team','Agent Team', 'agent_team',NULL::varchar, 1, 'purple', NULL::varchar, 40, true, NULL::json, '智能体团队执行',   NULL::int8, now(), now(), false, NULL::int8),
  (1004, 'agent_exec_mode', 'sqlbot',    'SqlBot',     'sqlbot',    NULL::varchar, 1, 'orange', NULL::varchar, 50, true, NULL::json, 'SQL Bot 查询',     NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 12. workflow_category — 工作流流程类别
--     原硬编码位置：WorkflowFlowForm.vue、WorkflowFlowTable.vue
--     使用组件：WorkflowFlowForm.vue、WorkflowFlowTable.vue
--     金融证券 AI 分析场景分类
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (151, 'workflow_category', '工作流流程类别', 'system', '金融证券 AI 分析工作流分类', 310, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (1010, 'workflow_category', 'compliance_review',    '合规审查',     'compliance_review',    NULL::varchar, 1, 'blue',     NULL::varchar, 10, true, NULL::json, '金融合规审查与法规遵从分析',   NULL::int8, now(), now(), false, NULL::int8),
  (1011, 'workflow_category', 'risk_assessment',      '风险评估',     'risk_assessment',      NULL::varchar, 1, 'red',      NULL::varchar, 20, true, NULL::json, '投资风险识别与量化评估',         NULL::int8, now(), now(), false, NULL::int8),
  (1012, 'workflow_category', 'market_analysis',      '市场分析',     'market_analysis',      NULL::varchar, 1, 'green',    NULL::varchar, 30, true, NULL::json, '宏观经济与行业市场分析',         NULL::int8, now(), now(), false, NULL::int8),
  (1013, 'workflow_category', 'trading_strategy',     '交易策略',     'trading_strategy',     NULL::varchar, 1, 'purple',   NULL::varchar, 40, true, NULL::json, '量化交易策略生成与回测',         NULL::int8, now(), now(), false, NULL::int8),
  (1014, 'workflow_category', 'investor_relations',   '投资者关系',   'investor_relations',   NULL::varchar, 1, 'cyan',     NULL::varchar, 50, true, NULL::json, '投资者沟通与关系管理分析',       NULL::int8, now(), now(), false, NULL::int8),
  (1015, 'workflow_category', 'portfolio_management', '投资组合管理', 'portfolio_management', NULL::varchar, 1, 'orange',   NULL::varchar, 60, true, NULL::json, '资产配置与投资组合优化',         NULL::int8, now(), now(), false, NULL::int8),
  (1016, 'workflow_category', 'regulatory_reporting', '监管报告',     'regulatory_reporting', NULL::varchar, 1, 'geekblue', NULL::varchar, 70, true, NULL::json, '监管合规报告自动生成',           NULL::int8, now(), now(), false, NULL::int8),
  (1017, 'workflow_category', 'other',                '其他',         'other',                NULL::varchar, 1, 'default',  NULL::varchar, 99, true, NULL::json, '其他自定义分析类别',               NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 13. workflow_platform — 工作流平台类型
--     原使用 ai_platform 字典（AI 模型供应商），语义不符
--     实际指工作流编排平台（Dify/Coze）
--     使用组件：WorkflowFlowForm.vue、WorkflowFlowTable.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (152, 'workflow_platform', '工作流平台', 'system', '工作流编排平台类型（Dify/Coze）', 320, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (1020, 'workflow_platform', 'dify', 'Dify', 'dify', NULL::varchar, 1, 'blue',    NULL::varchar, 10, true, NULL::json, 'Dify 工作流编排平台', NULL::int8, now(), now(), false, NULL::int8),
  (1021, 'workflow_platform', 'coze', 'Coze', 'coze', NULL::varchar, 1, 'magenta', NULL::varchar, 20, true, NULL::json, 'Coze 工作流编排平台', NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);

-- ==========================================
-- 14. flow_type — Dify 工作流类型
--     原通过后端 getPlatformTypes() API 动态返回
--     改为数据字典统一管理
--     使用组件：WorkflowFlowForm.vue、WorkflowFlowTable.vue
-- ==========================================
INSERT INTO "public"."sys_dictionary"
  (dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (153, 'flow_type', '工作流类型', 'system', 'Dify 工作流类型（对话型/任务型）', 330, true, NULL::jsonb, NULL::int8, now(), now(), false, NULL::int8)
) AS v(dict_id, dict_code, dict_name, dict_type, description, sort_order, is_active, extra_data, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary" s WHERE s.dict_id = v.dict_id);

INSERT INTO "public"."sys_dictionary_item"
  (item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
SELECT v.*
FROM (VALUES
  (1030, 'flow_type', 'agent_chat',     '对话型工作流', 'agent_chat',     NULL::varchar, 1, 'green',  NULL::varchar, 10, true, NULL::json, 'Chatflow — 多轮对话交互式工作流', NULL::int8, now(), now(), false, NULL::int8),
  (1031, 'flow_type', 'agent_workflow', '任务型工作流', 'agent_workflow', NULL::varchar, 1, 'blue',   NULL::varchar, 20, true, NULL::json, 'Workflow — 单次任务批处理工作流', NULL::int8, now(), now(), false, NULL::int8)
) AS v(item_id, dict_code, item_code, item_name, item_value, parent_code, level, color, icon, sort_order, is_active, extra_data, remark, created_by, created_at, updated_at, is_deleted, tenant_id)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_dictionary_item" s WHERE s.item_id = v.item_id);
