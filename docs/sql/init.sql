-- ============================================================================
-- MinWorkBuddy · 完整初始化 SQL（PostgreSQL 17+，需 pgvector / pg_trgm 扩展）
-- ----------------------------------------------------------------------------
-- 内容：
--   1) 前置扩展（vector / pg_trgm）
--   2) 全部表 DDL（由 SQLAlchemy 模型编译，表名/列/约束/注释为单一事实来源）
--   3) 索引（含模型内联索引 + 向量 HNSW / 全文 gin_trgm 性能索引）
--   4) 初始化数据（租户/用户/角色/字典/菜单/语音模型等，全部幂等）
--   5) 自增序列重置
--
-- 用法：psql -h <host> -U <user> -d <db> -f docs/sql/init.sql
-- 说明：本文件可由 backend/scripts/_gen_init_sql.py 重新生成。
-- ============================================================================

-- ── 前置扩展 ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── 表定义（共 93 张）──────────────────────────────

-- agent_async_task

CREATE TABLE agent_async_task (
	id SERIAL NOT NULL, 
	task_no VARCHAR(64), 
	session_id VARCHAR(64), 
	user_id INTEGER NOT NULL, 
	task_name VARCHAR(255) NOT NULL, 
	target_mode VARCHAR(32) NOT NULL, 
	payload TEXT, 
	status VARCHAR(16) NOT NULL, 
	priority SMALLINT NOT NULL, 
	progress FLOAT NOT NULL, 
	timeout_seconds INTEGER NOT NULL, 
	max_retries SMALLINT NOT NULL, 
	retry_count SMALLINT NOT NULL, 
	execution_id VARCHAR(100), 
	result_data TEXT, 
	error_message TEXT, 
	log_ref VARCHAR(128), 
	cancel_requested BOOLEAN DEFAULT false NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_async_task.id IS '任务ID';
COMMENT ON COLUMN agent_async_task.task_no IS '任务编号(可读)';
COMMENT ON COLUMN agent_async_task.session_id IS '归属会话ID';
COMMENT ON COLUMN agent_async_task.user_id IS '提交用户ID';
COMMENT ON COLUMN agent_async_task.task_name IS '任务名称';
COMMENT ON COLUMN agent_async_task.target_mode IS '执行模式: agent/team/skill';
COMMENT ON COLUMN agent_async_task.payload IS '执行参数(JSON: message/agent_id/team_id/skill 等)';
COMMENT ON COLUMN agent_async_task.status IS 'queued/running/completed/failed/cancelled';
COMMENT ON COLUMN agent_async_task.priority IS '优先级0-9(越大越优先)';
COMMENT ON COLUMN agent_async_task.progress IS '进度百分比0-100';
COMMENT ON COLUMN agent_async_task.timeout_seconds IS '超时秒数';
COMMENT ON COLUMN agent_async_task.max_retries IS '最大重试次数';
COMMENT ON COLUMN agent_async_task.retry_count IS '已重试次数';
COMMENT ON COLUMN agent_async_task.execution_id IS '网关执行ID(启动即写入, 支持运行中实时回放执行事件)';
COMMENT ON COLUMN agent_async_task.result_data IS '执行结果(JSON)';
COMMENT ON COLUMN agent_async_task.error_message IS '错误信息';
COMMENT ON COLUMN agent_async_task.log_ref IS '执行日志引用(TaskExecutionLog id等)';
COMMENT ON COLUMN agent_async_task.cancel_requested IS '用户请求取消标记，执行中任务轮询该标记主动中断';
COMMENT ON COLUMN agent_async_task.submitted_at IS '提交时间';
COMMENT ON COLUMN agent_async_task.started_at IS '开始执行时间';
COMMENT ON COLUMN agent_async_task.finished_at IS '结束时间';
COMMENT ON COLUMN agent_async_task.created_at IS '创建时间';
COMMENT ON COLUMN agent_async_task.updated_at IS '更新时间';
COMMENT ON COLUMN agent_async_task.tenant_id IS '租户ID';

-- agent_config

CREATE TABLE agent_config (
	id BIGSERIAL NOT NULL, 
	agent_code VARCHAR(100) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	agent_type VARCHAR(20) NOT NULL, 
	category VARCHAR(50), 
	strategy_code VARCHAR(100), 
	execution_mode VARCHAR(50) NOT NULL, 
	system_prompt TEXT, 
	tools JSONB, 
	skills JSONB, 
	mcp_servers JSONB, 
	knowledge_bases JSONB, 
	model_config JSONB, 
	hitl_config JSONB, 
	react_config JSONB, 
	context_config JSONB, 
	config JSONB, 
	description TEXT, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	workspace_id BIGINT, 
	workflow_id BIGINT, 
	created_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN DEFAULT 'false' NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_config.agent_code IS '唯一标识码';
COMMENT ON COLUMN agent_config.name IS 'Agent名称';
COMMENT ON COLUMN agent_config.agent_type IS '实现类型: CHAT/WORKFLOW/SKILL';
COMMENT ON COLUMN agent_config.category IS '用途分类（数据字典: agent_category）';
COMMENT ON COLUMN agent_config.strategy_code IS '策略代码（数据字典: agent_strategy）';
COMMENT ON COLUMN agent_config.execution_mode IS '执行模式';
COMMENT ON COLUMN agent_config.system_prompt IS '系统提示词';
COMMENT ON COLUMN agent_config.tools IS '可用工具列表';
COMMENT ON COLUMN agent_config.skills IS '可用 Skill 列表';
COMMENT ON COLUMN agent_config.mcp_servers IS 'MCP 服务器配置';
COMMENT ON COLUMN agent_config.knowledge_bases IS '关联知识库 ID 列表';
COMMENT ON COLUMN agent_config.model_config IS '模型配置 {provider, model, base_url, temperature, max_tokens}';
COMMENT ON COLUMN agent_config.hitl_config IS 'HITL 配置 {enabled, confirm_tools, plan_approval}';
COMMENT ON COLUMN agent_config.react_config IS 'ReAct 配置 {max_iters, timeout_seconds}';
COMMENT ON COLUMN agent_config.context_config IS '上下文配置 {max_tokens, compression_enabled}';
COMMENT ON COLUMN agent_config.config IS '类型特定配置';
COMMENT ON COLUMN agent_config.description IS '描述';
COMMENT ON COLUMN agent_config.is_active IS '是否启用';
COMMENT ON COLUMN agent_config.sort_order IS '排序权重';
COMMENT ON COLUMN agent_config.workspace_id IS '多租户隔离';
COMMENT ON COLUMN agent_config.workflow_id IS 'FK → workflow_flow.id';
COMMENT ON COLUMN agent_config.created_by IS '创建人ID';
COMMENT ON COLUMN agent_config.is_deleted IS '软删除';
COMMENT ON COLUMN agent_config.tenant_id IS '租户ID';

-- agent_execution

CREATE TABLE agent_execution (
	id BIGSERIAL NOT NULL, 
	execution_id VARCHAR(64) NOT NULL, 
	target_id VARCHAR(128), 
	session_id BIGINT, 
	user_id BIGINT, 
	execution_mode VARCHAR(50) NOT NULL, 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	user_input TEXT, 
	output TEXT, 
	error TEXT, 
	trace_id VARCHAR(64), 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	latency_ms INTEGER, 
	retry_count INTEGER DEFAULT '0' NOT NULL, 
	max_retries INTEGER DEFAULT '3' NOT NULL, 
	metadata_json JSON, 
	finished_reason VARCHAR(20), 
	interrupt_reason VARCHAR(20), 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	iterations INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_execution.execution_id IS '执行ID (UUID)';
COMMENT ON COLUMN agent_execution.target_id IS '被执行对象ID（dify_flow/skill_package/agent_config/agent_team，sqlbot=0）';
COMMENT ON COLUMN agent_execution.session_id IS '会话ID';
COMMENT ON COLUMN agent_execution.user_id IS '用户ID';
COMMENT ON COLUMN agent_execution.execution_mode IS '执行模式';
COMMENT ON COLUMN agent_execution.status IS '状态';
COMMENT ON COLUMN agent_execution.user_input IS '用户输入';
COMMENT ON COLUMN agent_execution.output IS '执行输出';
COMMENT ON COLUMN agent_execution.error IS '错误信息';
COMMENT ON COLUMN agent_execution.trace_id IS '链路追踪ID';
COMMENT ON COLUMN agent_execution.started_at IS '开始时间';
COMMENT ON COLUMN agent_execution.completed_at IS '完成时间';
COMMENT ON COLUMN agent_execution.latency_ms IS '耗时（毫秒）';
COMMENT ON COLUMN agent_execution.retry_count IS '重试次数';
COMMENT ON COLUMN agent_execution.max_retries IS '最大重试次数';
COMMENT ON COLUMN agent_execution.metadata_json IS '执行元数据快照';
COMMENT ON COLUMN agent_execution.finished_reason IS 'completed|interrupted|exceed_max_iters|error';
COMMENT ON COLUMN agent_execution.interrupt_reason IS 'timeout|user_cancel|system|error';
COMMENT ON COLUMN agent_execution.input_tokens IS '累计输入 token';
COMMENT ON COLUMN agent_execution.output_tokens IS '累计输出 token';
COMMENT ON COLUMN agent_execution.iterations IS '推理-行动迭代轮数';
COMMENT ON COLUMN agent_execution.tenant_id IS '租户ID';

-- agent_execution_event

CREATE TABLE agent_execution_event (
	id BIGSERIAL NOT NULL, 
	execution_id VARCHAR(64) NOT NULL, 
	trace_id VARCHAR(64), 
	event_type VARCHAR(30) NOT NULL, 
	sequence INTEGER NOT NULL, 
	content JSON, 
	source VARCHAR(50), 
	source_id VARCHAR(100), 
	metadata JSON, 
	level SMALLINT, 
	category VARCHAR(20), 
	reply_id VARCHAR(64), 
	block_id VARCHAR(64), 
	tool_call_id VARCHAR(64), 
	interrupt_reason VARCHAR(20), 
	ui_hint VARCHAR(20), 
	event_version SMALLINT DEFAULT '1' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_execution_event.execution_id IS '执行 ID';
COMMENT ON COLUMN agent_execution_event.trace_id IS '链路追踪 ID';
COMMENT ON COLUMN agent_execution_event.event_type IS '事件类型';
COMMENT ON COLUMN agent_execution_event.sequence IS '事件序号';
COMMENT ON COLUMN agent_execution_event.content IS '事件内容（根据类型结构化存储）';
COMMENT ON COLUMN agent_execution_event.source IS '事件来源: agent/mcp/skill';
COMMENT ON COLUMN agent_execution_event.source_id IS '来源标识';
COMMENT ON COLUMN agent_execution_event.metadata IS '附加元数据';
COMMENT ON COLUMN agent_execution_event.level IS '最低分发层级 LOG=0/DB=1/STREAM=2/UI=3';
COMMENT ON COLUMN agent_execution_event.category IS '事件分类';
COMMENT ON COLUMN agent_execution_event.reply_id IS 'AgentScope reply_id';
COMMENT ON COLUMN agent_execution_event.block_id IS '内容块 ID';
COMMENT ON COLUMN agent_execution_event.tool_call_id IS '工具调用关联 ID';
COMMENT ON COLUMN agent_execution_event.interrupt_reason IS '中断原因';
COMMENT ON COLUMN agent_execution_event.ui_hint IS '前端渲染路由提示';
COMMENT ON COLUMN agent_execution_event.event_version IS '事件格式版本';
COMMENT ON COLUMN agent_execution_event.tenant_id IS '租户ID';

-- agent_hitl_pause

CREATE TABLE agent_hitl_pause (
	id BIGSERIAL NOT NULL, 
	execution_id VARCHAR(64) NOT NULL, 
	reply_id VARCHAR(64), 
	tool_calls JSON, 
	suggested_rules JSON, 
	status VARCHAR(20) DEFAULT 'waiting' NOT NULL, 
	accept_rules SMALLINT DEFAULT '0' NOT NULL, 
	timeout_at TIMESTAMP WITHOUT TIME ZONE, 
	answered_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_hitl_pause.execution_id IS '执行 ID';
COMMENT ON COLUMN agent_hitl_pause.reply_id IS 'AgentScope reply_id';
COMMENT ON COLUMN agent_hitl_pause.tool_calls IS '待确认工具调用列表';
COMMENT ON COLUMN agent_hitl_pause.suggested_rules IS '建议授权规则';
COMMENT ON COLUMN agent_hitl_pause.status IS 'waiting/approved/rejected/interrupted';
COMMENT ON COLUMN agent_hitl_pause.accept_rules IS '是否接受授权规则';
COMMENT ON COLUMN agent_hitl_pause.timeout_at IS '超时提示时刻';
COMMENT ON COLUMN agent_hitl_pause.answered_at IS '用户应答时刻';
COMMENT ON COLUMN agent_hitl_pause.tenant_id IS '租户ID';

-- agent_scheduled_task

CREATE TABLE agent_scheduled_task (
	id SERIAL NOT NULL, 
	task_name VARCHAR(200) NOT NULL, 
	user_id INTEGER NOT NULL, 
	description TEXT, 
	target_mode VARCHAR(20) NOT NULL, 
	agent_id INTEGER, 
	team_id INTEGER, 
	skill_info TEXT, 
	prompt TEXT NOT NULL, 
	session_id VARCHAR(64), 
	model_id INTEGER, 
	schedule_type VARCHAR(20) NOT NULL, 
	cron_expression VARCHAR(100), 
	interval_seconds INTEGER, 
	run_at TIMESTAMP WITHOUT TIME ZONE, 
	timezone VARCHAR(50) DEFAULT 'Asia/Shanghai' NOT NULL, 
	status VARCHAR(20) DEFAULT 'enabled' NOT NULL, 
	last_run_at TIMESTAMP WITHOUT TIME ZONE, 
	next_run_at TIMESTAMP WITHOUT TIME ZONE, 
	last_task_id INTEGER, 
	run_count INTEGER DEFAULT '0' NOT NULL, 
	fail_count INTEGER DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_scheduled_task.id IS '调度ID';
COMMENT ON COLUMN agent_scheduled_task.task_name IS '调度任务名称';
COMMENT ON COLUMN agent_scheduled_task.user_id IS '归属用户ID';
COMMENT ON COLUMN agent_scheduled_task.description IS '任务描述';
COMMENT ON COLUMN agent_scheduled_task.target_mode IS '执行模式: deep_research/agent/team';
COMMENT ON COLUMN agent_scheduled_task.agent_id IS 'agent 模式：目标智能体ID';
COMMENT ON COLUMN agent_scheduled_task.team_id IS 'team 模式：目标专家团ID(空=默认团队)';
COMMENT ON COLUMN agent_scheduled_task.skill_info IS 'skill 模式：技能信息(JSON: package_id/package_name/script_id/script_name/params)';
COMMENT ON COLUMN agent_scheduled_task.prompt IS '执行输入(深度研究=研究主题, agent/team=指令)';
COMMENT ON COLUMN agent_scheduled_task.session_id IS '关联会话ID';
COMMENT ON COLUMN agent_scheduled_task.model_id IS '指定模型ID(空=默认文本模型)';
COMMENT ON COLUMN agent_scheduled_task.schedule_type IS '调度类型: cron/interval/once';
COMMENT ON COLUMN agent_scheduled_task.cron_expression IS 'Cron 表达式(5段: 分 时 日 月 周)';
COMMENT ON COLUMN agent_scheduled_task.interval_seconds IS '间隔秒数(interval 类型, 最小60)';
COMMENT ON COLUMN agent_scheduled_task.run_at IS '单次执行时间(once 类型)';
COMMENT ON COLUMN agent_scheduled_task.timezone IS '时区';
COMMENT ON COLUMN agent_scheduled_task.status IS 'enabled/paused/deleted';
COMMENT ON COLUMN agent_scheduled_task.last_run_at IS '最近触发时间';
COMMENT ON COLUMN agent_scheduled_task.next_run_at IS '下次触发时间(调度器回填)';
COMMENT ON COLUMN agent_scheduled_task.last_task_id IS '最近生成的异步任务ID';
COMMENT ON COLUMN agent_scheduled_task.run_count IS '累计触发次数';
COMMENT ON COLUMN agent_scheduled_task.fail_count IS '触发失败次数';
COMMENT ON COLUMN agent_scheduled_task.created_at IS '创建时间';
COMMENT ON COLUMN agent_scheduled_task.updated_at IS '更新时间';
COMMENT ON COLUMN agent_scheduled_task.tenant_id IS '租户ID';

-- agent_team

CREATE TABLE agent_team (
	id BIGSERIAL NOT NULL, 
	team_code VARCHAR(100) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	category VARCHAR(50), 
	mode VARCHAR(20) DEFAULT 'sequential' NOT NULL, 
	execution_mode VARCHAR(32) DEFAULT 'llm_orchestrated' NOT NULL, 
	graph JSONB, 
	shared_knowledge_bases JSONB, 
	shared_tools JSONB, 
	run_config JSONB, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	workspace_id BIGINT, 
	created_by BIGINT, 
	updated_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN DEFAULT 'false' NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_team.team_code IS '唯一标识码';
COMMENT ON COLUMN agent_team.name IS '团队名称';
COMMENT ON COLUMN agent_team.description IS '描述';
COMMENT ON COLUMN agent_team.category IS '用途分类（数据字典: agent_team_category）';
COMMENT ON COLUMN agent_team.mode IS '协作模式（来源模板）: sequential/parallel/msghub/supervisor/dag';
COMMENT ON COLUMN agent_team.execution_mode IS '执行模式: llm_orchestrated(生效) / static_dag(废弃回放)';
COMMENT ON COLUMN agent_team.graph IS '画布快照 {nodes:[{node_key,x,y}], viewport:{x,y,zoom}}';
COMMENT ON COLUMN agent_team.shared_knowledge_bases IS '团队共享知识库 ID 列表（全员可访问）';
COMMENT ON COLUMN agent_team.shared_tools IS '团队共享工具列表';
COMMENT ON COLUMN agent_team.run_config IS '运行配置 {max_rounds, max_parallel, node_timeout_seconds, node_timeout_per_batch, node_timeout_max, total_timeout_seconds, on_node_error, supervisor_node_key, aggregator_node_key, allow_intervention, persist_events}';
COMMENT ON COLUMN agent_team.is_active IS '是否启用';
COMMENT ON COLUMN agent_team.sort_order IS '排序权重';
COMMENT ON COLUMN agent_team.workspace_id IS '多租户隔离';
COMMENT ON COLUMN agent_team.created_by IS '创建人ID';
COMMENT ON COLUMN agent_team.updated_by IS '最后修改人ID';
COMMENT ON COLUMN agent_team.is_deleted IS '软删除';
COMMENT ON COLUMN agent_team.tenant_id IS '租户ID';

-- agent_team_edge

CREATE TABLE agent_team_edge (
	id BIGSERIAL NOT NULL, 
	team_id BIGINT NOT NULL, 
	from_node_key VARCHAR(64) NOT NULL, 
	to_node_key VARCHAR(64) NOT NULL, 
	label VARCHAR(100), 
	condition TEXT, 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	edge_config JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_team_edge UNIQUE (team_id, from_node_key, to_node_key)
);
COMMENT ON COLUMN agent_team_edge.team_id IS '所属团队 agent_team.id';
COMMENT ON COLUMN agent_team_edge.from_node_key IS '上游节点 node_key；''__START__'' 表示虚拟入口';
COMMENT ON COLUMN agent_team_edge.to_node_key IS '下游节点 node_key；''__END__'' 表示虚拟出口';
COMMENT ON COLUMN agent_team_edge.label IS '边标签（展示用）';
COMMENT ON COLUMN agent_team_edge.condition IS '条件边表达式（预留，为空=无条件）';
COMMENT ON COLUMN agent_team_edge.sort_order IS '同一 to_node 的多上游拼接顺序';
COMMENT ON COLUMN agent_team_edge.edge_config IS '边的前端样式等附加配置';
COMMENT ON COLUMN agent_team_edge.tenant_id IS '租户ID';

-- agent_team_intervention

CREATE TABLE agent_team_intervention (
	id BIGSERIAL NOT NULL, 
	run_id VARCHAR(64) NOT NULL, 
	intervention_type VARCHAR(30) NOT NULL, 
	node_key VARCHAR(64), 
	round_no INTEGER, 
	payload JSONB, 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	applied_at TIMESTAMP WITHOUT TIME ZONE, 
	reject_reason TEXT, 
	operator_id BIGINT, 
	operator_name VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_team_intervention.run_id IS '所属运行 agent_team_run.run_id';
COMMENT ON COLUMN agent_team_intervention.intervention_type IS 'pause/resume/cancel/edit_output/retry_node/skip_node/inject_message/answer_ask';
COMMENT ON COLUMN agent_team_intervention.node_key IS '目标节点（节点级介入必填）';
COMMENT ON COLUMN agent_team_intervention.round_no IS '目标轮次';
COMMENT ON COLUMN agent_team_intervention.payload IS '介入内容 {content, reason, ...}';
COMMENT ON COLUMN agent_team_intervention.status IS 'pending/applied/expired/rejected';
COMMENT ON COLUMN agent_team_intervention.applied_at IS '被执行引擎消费的时间';
COMMENT ON COLUMN agent_team_intervention.reject_reason IS '拒绝/过期原因';
COMMENT ON COLUMN agent_team_intervention.operator_id IS '操作人ID';
COMMENT ON COLUMN agent_team_intervention.operator_name IS '操作人名称（快照）';
COMMENT ON COLUMN agent_team_intervention.tenant_id IS '租户ID';

-- agent_team_member

CREATE TABLE agent_team_member (
	id BIGSERIAL NOT NULL, 
	team_id BIGINT NOT NULL, 
	agent_config_id BIGINT NOT NULL, 
	node_key VARCHAR(64) NOT NULL, 
	role_name VARCHAR(100) NOT NULL, 
	role_desc TEXT, 
	avatar VARCHAR(200), 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	override_system_prompt TEXT, 
	override_llm_config JSONB, 
	override_knowledge_bases JSONB, 
	override_tools JSONB, 
	override_skills JSONB, 
	tool_preset JSONB, 
	node_config JSONB, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_team_member_node_key UNIQUE (team_id, node_key)
);
COMMENT ON COLUMN agent_team_member.team_id IS '所属团队 agent_team.id';
COMMENT ON COLUMN agent_team_member.agent_config_id IS '引用 agent_config.id';
COMMENT ON COLUMN agent_team_member.node_key IS '节点标识（团队内唯一，供边引用/@提及，如 ''researcher''）';
COMMENT ON COLUMN agent_team_member.role_name IS '团队内角色名（展示用，如 ''风险研判专家''）';
COMMENT ON COLUMN agent_team_member.role_desc IS '角色职责说明，注入 prompt 供其他成员理解分工';
COMMENT ON COLUMN agent_team_member.avatar IS '头像/图标';
COMMENT ON COLUMN agent_team_member.sort_order IS '顺序（sequential 模式的执行序）';
COMMENT ON COLUMN agent_team_member.override_system_prompt IS '覆盖系统提示词';
COMMENT ON COLUMN agent_team_member.override_llm_config IS '覆盖模型配置（深合并，可只改 temperature）';
COMMENT ON COLUMN agent_team_member.override_knowledge_bases IS '覆盖知识库 ID 列表';
COMMENT ON COLUMN agent_team_member.override_tools IS '覆盖工具列表';
COMMENT ON COLUMN agent_team_member.override_skills IS '覆盖技能列表';
COMMENT ON COLUMN agent_team_member.tool_preset IS 'TeamSay 工具预设：单点追问时可被 @提及 调起的成员 node_key 列表；NULL = 使用团队全部成员';
COMMENT ON COLUMN agent_team_member.node_config IS '节点配置 {input_mode, input_template, output_key, condition, retry, timeout_seconds, is_entry, is_terminal}';
COMMENT ON COLUMN agent_team_member.is_active IS '是否启用';
COMMENT ON COLUMN agent_team_member.tenant_id IS '租户ID';

-- agent_team_run

CREATE TABLE agent_team_run (
	id BIGSERIAL NOT NULL, 
	run_id VARCHAR(64) NOT NULL, 
	team_id BIGINT NOT NULL, 
	conversation_id VARCHAR(64), 
	team_snapshot JSONB NOT NULL, 
	input_text TEXT, 
	input_context JSONB, 
	final_output TEXT, 
	node_outputs JSONB, 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	current_round INTEGER DEFAULT '0' NOT NULL, 
	current_nodes JSONB, 
	error_message TEXT, 
	total_tokens INTEGER DEFAULT '0' NOT NULL, 
	total_steps INTEGER DEFAULT '0' NOT NULL, 
	duration_ms INTEGER, 
	trigger_type VARCHAR(20) DEFAULT 'manual' NOT NULL, 
	parent_run_id VARCHAR(64), 
	branch_from_node VARCHAR(64), 
	workspace_id BIGINT, 
	created_by BIGINT, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_team_run.run_id IS '运行唯一标识（UUID），同时作为 agent_execution_event.execution_id';
COMMENT ON COLUMN agent_team_run.team_id IS '所属团队 agent_team.id';
COMMENT ON COLUMN agent_team_run.conversation_id IS '关联会话ID';
COMMENT ON COLUMN agent_team_run.team_snapshot IS '团队配置快照 {team:{...}, members:[...], edges:[...], run_config:{...}}';
COMMENT ON COLUMN agent_team_run.input_text IS '用户原始输入';
COMMENT ON COLUMN agent_team_run.input_context IS '附加上下文（文件、变量等）';
COMMENT ON COLUMN agent_team_run.final_output IS '团队最终输出';
COMMENT ON COLUMN agent_team_run.node_outputs IS '各节点输出汇总 {node_key: output}';
COMMENT ON COLUMN agent_team_run.status IS 'pending/running/paused/success/failed/cancelled';
COMMENT ON COLUMN agent_team_run.current_round IS '当前轮次（msghub/supervisor 模式）';
COMMENT ON COLUMN agent_team_run.current_nodes IS '当前正在执行的节点 node_key 列表';
COMMENT ON COLUMN agent_team_run.error_message IS '失败原因';
COMMENT ON COLUMN agent_team_run.total_tokens IS '累计 token 消耗';
COMMENT ON COLUMN agent_team_run.total_steps IS '累计节点执行次数';
COMMENT ON COLUMN agent_team_run.duration_ms IS '总耗时（毫秒）';
COMMENT ON COLUMN agent_team_run.trigger_type IS 'manual/api/schedule/replay';
COMMENT ON COLUMN agent_team_run.parent_run_id IS '分支重跑时的父运行 run_id';
COMMENT ON COLUMN agent_team_run.branch_from_node IS '分支重跑的起始节点 node_key';
COMMENT ON COLUMN agent_team_run.workspace_id IS '多租户隔离';
COMMENT ON COLUMN agent_team_run.created_by IS '发起人ID';
COMMENT ON COLUMN agent_team_run.started_at IS '开始执行时间';
COMMENT ON COLUMN agent_team_run.finished_at IS '结束时间';
COMMENT ON COLUMN agent_team_run.tenant_id IS '租户ID';

-- agent_team_run_step

CREATE TABLE agent_team_run_step (
	id BIGSERIAL NOT NULL, 
	run_id VARCHAR(64) NOT NULL, 
	node_key VARCHAR(64) NOT NULL, 
	role_name VARCHAR(100), 
	agent_config_id BIGINT, 
	round_no INTEGER DEFAULT '0' NOT NULL, 
	layer_no INTEGER, 
	seq INTEGER DEFAULT '0' NOT NULL, 
	input_text TEXT, 
	upstream_nodes JSONB, 
	output_text TEXT, 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	error_message TEXT, 
	retry_count INTEGER DEFAULT '0' NOT NULL, 
	tokens INTEGER DEFAULT '0' NOT NULL, 
	duration_ms INTEGER, 
	extra_data JSONB, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_team_run_step.run_id IS '所属运行 agent_team_run.run_id';
COMMENT ON COLUMN agent_team_run_step.node_key IS '节点标识';
COMMENT ON COLUMN agent_team_run_step.role_name IS '角色名（快照，防止团队改名后失真）';
COMMENT ON COLUMN agent_team_run_step.agent_config_id IS '实际执行的 agent_config.id';
COMMENT ON COLUMN agent_team_run_step.round_no IS '轮次（动态模式下同节点可多次执行）';
COMMENT ON COLUMN agent_team_run_step.layer_no IS 'DAG 拓扑层号（同层并行）';
COMMENT ON COLUMN agent_team_run_step.seq IS '全局执行序号';
COMMENT ON COLUMN agent_team_run_step.input_text IS '合并后的实际输入';
COMMENT ON COLUMN agent_team_run_step.upstream_nodes IS '上游节点 node_key 列表';
COMMENT ON COLUMN agent_team_run_step.output_text IS '节点输出';
COMMENT ON COLUMN agent_team_run_step.status IS 'pending/running/success/failed/skipped/intervened';
COMMENT ON COLUMN agent_team_run_step.error_message IS '失败原因';
COMMENT ON COLUMN agent_team_run_step.retry_count IS '重试次数';
COMMENT ON COLUMN agent_team_run_step.tokens IS 'token 消耗';
COMMENT ON COLUMN agent_team_run_step.duration_ms IS '耗时（毫秒）';
COMMENT ON COLUMN agent_team_run_step.extra_data IS '扩展信息（工具调用摘要、引用来源等）';
COMMENT ON COLUMN agent_team_run_step.tenant_id IS '租户ID';

-- agent_trace

CREATE TABLE agent_trace (
	id BIGSERIAL NOT NULL, 
	trace_id VARCHAR(64) NOT NULL, 
	session_id BIGINT, 
	user_id BIGINT, 
	agent_id VARCHAR(100) NOT NULL, 
	agent_type VARCHAR(20) NOT NULL, 
	input_prompt TEXT, 
	output_result TEXT, 
	skills_used JSONB, 
	tools_used JSONB, 
	error TEXT, 
	status VARCHAR(20) DEFAULT 'OK' NOT NULL, 
	start_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	end_time TIMESTAMP WITHOUT TIME ZONE, 
	duration_ms INTEGER, 
	metadata JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	agent_config_id BIGINT, 
	team_config_id BIGINT, 
	workspace_config_id BIGINT, 
	component_ids JSONB, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN agent_trace.trace_id IS '链路ID';
COMMENT ON COLUMN agent_trace.session_id IS '会话ID';
COMMENT ON COLUMN agent_trace.user_id IS '用户ID';
COMMENT ON COLUMN agent_trace.agent_id IS 'Agent ID';
COMMENT ON COLUMN agent_trace.agent_type IS 'Agent类型';
COMMENT ON COLUMN agent_trace.input_prompt IS '输入提示词';
COMMENT ON COLUMN agent_trace.output_result IS '输出结果';
COMMENT ON COLUMN agent_trace.skills_used IS '使用的Skill列表';
COMMENT ON COLUMN agent_trace.tools_used IS '使用的工具列表';
COMMENT ON COLUMN agent_trace.error IS '错误信息';
COMMENT ON COLUMN agent_trace.status IS '状态: OK/ERROR';
COMMENT ON COLUMN agent_trace.start_time IS '开始时间';
COMMENT ON COLUMN agent_trace.end_time IS '结束时间';
COMMENT ON COLUMN agent_trace.duration_ms IS '执行耗时(毫秒)';
COMMENT ON COLUMN agent_trace.metadata IS '扩展元数据';
COMMENT ON COLUMN agent_trace.agent_config_id IS '关联 Agent 配置 ID';
COMMENT ON COLUMN agent_trace.team_config_id IS '关联 Team 配置 ID';
COMMENT ON COLUMN agent_trace.workspace_config_id IS '关联 Workspace 配置 ID';
COMMENT ON COLUMN agent_trace.component_ids IS '关联组件 ID 集合 {"skill": [...], "tool": [...]}';
COMMENT ON COLUMN agent_trace.tenant_id IS '租户ID';

-- ai_agent_config

CREATE TABLE ai_agent_config (
	id BIGSERIAL NOT NULL, 
	agent_id VARCHAR(64) NOT NULL, 
	name VARCHAR(128), 
	type VARCHAR(32) DEFAULT 'agentscope', 
	model VARCHAR(64) DEFAULT 'qwen-plus', 
	system_prompt TEXT, 
	tool_bindings JSON, 
	mcp_bindings JSON, 
	max_react_iters INTEGER DEFAULT '5', 
	enable_plan BOOLEAN DEFAULT 'true', 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_agent_config.type IS 'agentscope（dify/direct 已废弃，见 2026-09-20 spec）';
COMMENT ON COLUMN ai_agent_config.tool_bindings IS '绑定的工具名列表';
COMMENT ON COLUMN ai_agent_config.mcp_bindings IS '绑定的 MCP 服务列表';

-- ai_api_key

CREATE TABLE ai_api_key (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	api_key TEXT NOT NULL, 
	platform VARCHAR(50) NOT NULL, 
	url VARCHAR(500), 
	app_id VARCHAR(100), 
	property JSON, 
	status INTEGER DEFAULT '1' NOT NULL, 
	sort INTEGER DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	creator VARCHAR(64), 
	updater VARCHAR(64), 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_api_key.name IS '密钥名称';
COMMENT ON COLUMN ai_api_key.api_key IS 'API Key';
COMMENT ON COLUMN ai_api_key.platform IS '平台: OpenAI/通义千问/智谱/讯飞等';
COMMENT ON COLUMN ai_api_key.url IS 'API 地址';
COMMENT ON COLUMN ai_api_key.app_id IS 'AppId';
COMMENT ON COLUMN ai_api_key.property IS '配置属性';
COMMENT ON COLUMN ai_api_key.status IS '状态: 1=启用, 0=禁用';
COMMENT ON COLUMN ai_api_key.sort IS '排序';
COMMENT ON COLUMN ai_api_key.creator IS '创建人';
COMMENT ON COLUMN ai_api_key.updater IS '更新人';
COMMENT ON COLUMN ai_api_key.tenant_id IS '租户ID';

-- ai_chat_session

CREATE TABLE ai_chat_session (
	session_id BIGSERIAL NOT NULL, 
	user_id BIGINT NOT NULL, 
	session_title VARCHAR(200), 
	session_type VARCHAR(50), 
	context_data JSON, 
	status VARCHAR(20), 
	message_count INTEGER, 
	is_pinned BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	agent_id VARCHAR(50), 
	context_version INTEGER NOT NULL, 
	agent_mode VARCHAR(32), 
	tenant_id BIGINT, 
	PRIMARY KEY (session_id)
);
COMMENT ON COLUMN ai_chat_session.session_id IS '会话ID';
COMMENT ON COLUMN ai_chat_session.user_id IS '用户ID';
COMMENT ON COLUMN ai_chat_session.session_title IS '会话标题';
COMMENT ON COLUMN ai_chat_session.session_type IS '会话类型：general-通用对话, thinking-深度思考, deep_research-深度研究, skill-技能模式, agent-专家Agent, team-专家团';
COMMENT ON COLUMN ai_chat_session.context_data IS '上下文数据';
COMMENT ON COLUMN ai_chat_session.status IS '状态：active-活跃, archived-归档';
COMMENT ON COLUMN ai_chat_session.message_count IS '消息数量';
COMMENT ON COLUMN ai_chat_session.is_pinned IS '是否置顶';
COMMENT ON COLUMN ai_chat_session.created_at IS '创建时间';
COMMENT ON COLUMN ai_chat_session.updated_at IS '更新时间';
COMMENT ON COLUMN ai_chat_session.agent_id IS '关联的 Agent 配置 ID';
COMMENT ON COLUMN ai_chat_session.context_version IS '上下文版本号';
COMMENT ON COLUMN ai_chat_session.agent_mode IS 'AgentScope 执行模式：skill/agent/team/thinking/deep_research/scheduled';
COMMENT ON COLUMN ai_chat_session.tenant_id IS '租户ID';

-- ai_context_storage

CREATE TABLE ai_context_storage (
	id BIGSERIAL NOT NULL, 
	tenant_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	mode VARCHAR(32) NOT NULL, 
	context_key VARCHAR(255) NOT NULL, 
	context_data JSONB NOT NULL, 
	embedding_vector TEXT, 
	priority INTEGER DEFAULT '5', 
	access_count INTEGER DEFAULT '0', 
	last_accessed TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	source_mode VARCHAR(32) DEFAULT 'shared' NOT NULL, 
	context_tags JSONB DEFAULT '[]', 
	is_cross_mode_accessible BOOLEAN DEFAULT 'false' NOT NULL, 
	case_number VARCHAR(64), 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_context_storage.id IS '主键';
COMMENT ON COLUMN ai_context_storage.tenant_id IS '租户 ID';
COMMENT ON COLUMN ai_context_storage.session_id IS '会话 ID';
COMMENT ON COLUMN ai_context_storage.user_id IS '用户 ID';
COMMENT ON COLUMN ai_context_storage.mode IS '模式(dify/sqlbot/...)';
COMMENT ON COLUMN ai_context_storage.context_key IS '上下文 key';
COMMENT ON COLUMN ai_context_storage.context_data IS '上下文 JSON 数据';
COMMENT ON COLUMN ai_context_storage.embedding_vector IS '向量嵌入(pgvector)';
COMMENT ON COLUMN ai_context_storage.priority IS '优先级 1-10,数字越小越优先';
COMMENT ON COLUMN ai_context_storage.access_count IS '访问次数';
COMMENT ON COLUMN ai_context_storage.last_accessed IS '最后访问时间';
COMMENT ON COLUMN ai_context_storage.created_at IS '创建时间';
COMMENT ON COLUMN ai_context_storage.updated_at IS '更新时间';
COMMENT ON COLUMN ai_context_storage.expires_at IS '过期时间';
COMMENT ON COLUMN ai_context_storage.source_mode IS '业务来源模式(general/react/thinking/deep_research/skill/agent/team/scheduled/shared)';
COMMENT ON COLUMN ai_context_storage.context_tags IS '上下文标签列表';
COMMENT ON COLUMN ai_context_storage.is_cross_mode_accessible IS '是否允许跨模式检索';
COMMENT ON COLUMN ai_context_storage.case_number IS '案件/工作空间标识';

-- ai_mcp_api_key

CREATE TABLE ai_mcp_api_key (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	service_type VARCHAR(20) NOT NULL, 
	platform VARCHAR(50), 
	protocol_type VARCHAR(50), 
	version VARCHAR(20), 
	description VARCHAR(2000), 
	service_url VARCHAR(500), 
	service_name VARCHAR(200), 
	api_key VARCHAR(500), 
	namespace VARCHAR(200), 
	group_key VARCHAR(200), 
	access_path VARCHAR(500), 
	properties JSON, 
	capabilities JSON, 
	remark TEXT, 
	status INTEGER DEFAULT '1' NOT NULL, 
	sort INTEGER DEFAULT '0' NOT NULL, 
	template_id BIGINT DEFAULT '0' NOT NULL, 
	health_status VARCHAR(20) DEFAULT 'unknown' NOT NULL, 
	last_check_at TIMESTAMP WITHOUT TIME ZONE, 
	creator VARCHAR(100), 
	updater VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_mcp_api_key.id IS '主键';
COMMENT ON COLUMN ai_mcp_api_key.name IS '密钥名称';
COMMENT ON COLUMN ai_mcp_api_key.service_type IS '服务类型: nacos2/nacos3/http/sse';
COMMENT ON COLUMN ai_mcp_api_key.platform IS '平台: local/remote';
COMMENT ON COLUMN ai_mcp_api_key.protocol_type IS '协议类型(自动推导)';
COMMENT ON COLUMN ai_mcp_api_key.version IS 'MCP协议版本';
COMMENT ON COLUMN ai_mcp_api_key.description IS '描述信息';
COMMENT ON COLUMN ai_mcp_api_key.service_url IS '服务地址';
COMMENT ON COLUMN ai_mcp_api_key.service_name IS 'Nacos服务名';
COMMENT ON COLUMN ai_mcp_api_key.api_key IS '鉴权密钥';
COMMENT ON COLUMN ai_mcp_api_key.namespace IS 'Nacos命名空间';
COMMENT ON COLUMN ai_mcp_api_key.group_key IS 'Nacos分组';
COMMENT ON COLUMN ai_mcp_api_key.access_path IS 'HTTP/SSE访问路径';
COMMENT ON COLUMN ai_mcp_api_key.properties IS '扩展属性';
COMMENT ON COLUMN ai_mcp_api_key.capabilities IS '能力列表';
COMMENT ON COLUMN ai_mcp_api_key.remark IS '备注';
COMMENT ON COLUMN ai_mcp_api_key.status IS '1=启用,0=禁用';
COMMENT ON COLUMN ai_mcp_api_key.sort IS '排序';
COMMENT ON COLUMN ai_mcp_api_key.template_id IS '广场模板ID';
COMMENT ON COLUMN ai_mcp_api_key.health_status IS '健康状态: healthy/unhealthy/unknown';
COMMENT ON COLUMN ai_mcp_api_key.last_check_at IS '最近一次连接检测时间';
COMMENT ON COLUMN ai_mcp_api_key.creator IS '创建人';
COMMENT ON COLUMN ai_mcp_api_key.updater IS '更新人';
COMMENT ON COLUMN ai_mcp_api_key.tenant_id IS '租户ID';

-- ai_mcp_square_template

CREATE TABLE ai_mcp_square_template (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	icon VARCHAR(200), 
	category VARCHAR(50), 
	platform VARCHAR(50), 
	description VARCHAR(2000), 
	service_type VARCHAR(20) NOT NULL, 
	service_url VARCHAR(500), 
	access_path VARCHAR(500), 
	version VARCHAR(20), 
	capabilities JSON, 
	default_client_config JSON, 
	sort INTEGER DEFAULT '0' NOT NULL, 
	status INTEGER DEFAULT '1' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_mcp_square_template.id IS '主键';
COMMENT ON COLUMN ai_mcp_square_template.name IS '模板名称';
COMMENT ON COLUMN ai_mcp_square_template.icon IS '图标标识';
COMMENT ON COLUMN ai_mcp_square_template.category IS '分类';
COMMENT ON COLUMN ai_mcp_square_template.platform IS '平台类型';
COMMENT ON COLUMN ai_mcp_square_template.description IS '描述';
COMMENT ON COLUMN ai_mcp_square_template.service_type IS '服务类型';
COMMENT ON COLUMN ai_mcp_square_template.service_url IS '服务地址模板';
COMMENT ON COLUMN ai_mcp_square_template.access_path IS '访问路径';
COMMENT ON COLUMN ai_mcp_square_template.version IS '协议版本';
COMMENT ON COLUMN ai_mcp_square_template.capabilities IS '能力列表';
COMMENT ON COLUMN ai_mcp_square_template.default_client_config IS '默认客户端配置模板';
COMMENT ON COLUMN ai_mcp_square_template.sort IS '排序';
COMMENT ON COLUMN ai_mcp_square_template.status IS '1=启用,0=禁用';
COMMENT ON COLUMN ai_mcp_square_template.tenant_id IS '租户ID';

-- ai_session_finalize_log

CREATE TABLE ai_session_finalize_log (
	id BIGSERIAL NOT NULL, 
	tenant_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	session_type VARCHAR(32) NOT NULL, 
	source_mode VARCHAR(32) NOT NULL, 
	l2_record_id BIGINT, 
	mem0_synced BOOLEAN DEFAULT 'false' NOT NULL, 
	mem0_memory_id VARCHAR(64), 
	finalized_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	error_message TEXT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_session_finalize_log.id IS '主键';
COMMENT ON COLUMN ai_session_finalize_log.tenant_id IS '租户 ID';
COMMENT ON COLUMN ai_session_finalize_log.session_id IS '会话 ID';
COMMENT ON COLUMN ai_session_finalize_log.user_id IS '用户 ID';
COMMENT ON COLUMN ai_session_finalize_log.session_type IS '会话类型(general/skill/...)';
COMMENT ON COLUMN ai_session_finalize_log.source_mode IS '业务来源模式';
COMMENT ON COLUMN ai_session_finalize_log.l2_record_id IS 'L2 落库 id';
COMMENT ON COLUMN ai_session_finalize_log.mem0_synced IS '是否已同步到 Mem0';
COMMENT ON COLUMN ai_session_finalize_log.mem0_memory_id IS 'Mem0 记忆 ID';
COMMENT ON COLUMN ai_session_finalize_log.finalized_at IS '收尾时间';
COMMENT ON COLUMN ai_session_finalize_log.error_message IS '错误信息';

-- ai_skill_evolution_config

CREATE TABLE ai_skill_evolution_config (
	id BIGSERIAL NOT NULL, 
	skill_id VARCHAR(100) NOT NULL, 
	threshold FLOAT DEFAULT '0.7' NOT NULL, 
	weight_success FLOAT DEFAULT '0.4' NOT NULL, 
	weight_latency FLOAT DEFAULT '0.2' NOT NULL, 
	weight_user_rating FLOAT DEFAULT '0.3' NOT NULL, 
	resource_score FLOAT DEFAULT '0.8' NOT NULL, 
	is_auto_enabled BOOLEAN DEFAULT 'false' NOT NULL, 
	model_code VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_skill_evolution_config.id IS '主键';
COMMENT ON COLUMN ai_skill_evolution_config.skill_id IS '技能 ID（关联 ai_skill_package.package_id）';
COMMENT ON COLUMN ai_skill_evolution_config.threshold IS '评估阈值，低于此值触发进化';
COMMENT ON COLUMN ai_skill_evolution_config.weight_success IS '成功率权重';
COMMENT ON COLUMN ai_skill_evolution_config.weight_latency IS '延迟权重';
COMMENT ON COLUMN ai_skill_evolution_config.weight_user_rating IS '用户评分权重';
COMMENT ON COLUMN ai_skill_evolution_config.resource_score IS '资源评估得分';
COMMENT ON COLUMN ai_skill_evolution_config.is_auto_enabled IS '是否启用自动进化评估';
COMMENT ON COLUMN ai_skill_evolution_config.model_code IS '进化使用的 LLM 文本模型编码（关联 ai_chat_model.code），空则使用默认模型';
COMMENT ON COLUMN ai_skill_evolution_config.tenant_id IS '租户ID';

-- ai_skill_evolution_log

CREATE TABLE ai_skill_evolution_log (
	id BIGSERIAL NOT NULL, 
	skill_id VARCHAR(100) NOT NULL, 
	from_version INTEGER, 
	to_version INTEGER, 
	trigger_type VARCHAR(50) NOT NULL, 
	result VARCHAR(50) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_skill_evolution_log.id IS '主键';
COMMENT ON COLUMN ai_skill_evolution_log.skill_id IS '技能 ID';
COMMENT ON COLUMN ai_skill_evolution_log.from_version IS '源版本号';
COMMENT ON COLUMN ai_skill_evolution_log.to_version IS '目标版本号';
COMMENT ON COLUMN ai_skill_evolution_log.trigger_type IS '触发类型: performance / requirement / competition';
COMMENT ON COLUMN ai_skill_evolution_log.result IS '结果: success / failed / rolled_back';
COMMENT ON COLUMN ai_skill_evolution_log.tenant_id IS '租户ID';

-- ai_skill_hub_repo

CREATE TABLE ai_skill_hub_repo (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	url VARCHAR(512) NOT NULL, 
	branch VARCHAR(100) DEFAULT 'main' NOT NULL, 
	is_official BOOLEAN DEFAULT 'false' NOT NULL, 
	source_type VARCHAR(20) DEFAULT 'git' NOT NULL, 
	username VARCHAR(200), 
	password VARCHAR(200), 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (url)
);
COMMENT ON COLUMN ai_skill_hub_repo.id IS '主键';
COMMENT ON COLUMN ai_skill_hub_repo.name IS '仓库展示名（如 官方仓库）';
COMMENT ON COLUMN ai_skill_hub_repo.url IS 'Git 仓库地址（https）';
COMMENT ON COLUMN ai_skill_hub_repo.branch IS '克隆分支';
COMMENT ON COLUMN ai_skill_hub_repo.is_official IS '是否官方仓库（官方不可删除）';
COMMENT ON COLUMN ai_skill_hub_repo.source_type IS '仓库来源类型：git=Git 仓库，skillhub=SkillHub 云市场';
COMMENT ON COLUMN ai_skill_hub_repo.username IS '仓库访问账号（留空则用全局配置 OFFICIAL_HUB_USERNAME）';
COMMENT ON COLUMN ai_skill_hub_repo.password IS '仓库访问密码（留空则用全局配置 OFFICIAL_HUB_PASSWORD）';
COMMENT ON COLUMN ai_skill_hub_repo.sort_order IS '展示排序';
COMMENT ON COLUMN ai_skill_hub_repo.tenant_id IS '租户ID';

-- ai_skill_metrics

CREATE TABLE ai_skill_metrics (
	id BIGSERIAL NOT NULL, 
	skill_id VARCHAR(100) NOT NULL, 
	execution_count INTEGER DEFAULT '0' NOT NULL, 
	success_rate FLOAT DEFAULT '0.0' NOT NULL, 
	avg_latency FLOAT DEFAULT '0.0' NOT NULL, 
	user_rating FLOAT DEFAULT '0.0' NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (skill_id)
);
COMMENT ON COLUMN ai_skill_metrics.id IS '主键';
COMMENT ON COLUMN ai_skill_metrics.skill_id IS '技能 ID（关联 ai_skill_package.package_id）';
COMMENT ON COLUMN ai_skill_metrics.execution_count IS '累计执行次数';
COMMENT ON COLUMN ai_skill_metrics.success_rate IS '执行成功率 0-1';
COMMENT ON COLUMN ai_skill_metrics.avg_latency IS '平均耗时（秒）';
COMMENT ON COLUMN ai_skill_metrics.user_rating IS '用户评分 0-1';
COMMENT ON COLUMN ai_skill_metrics.tenant_id IS '租户ID';

-- ai_skill_package

CREATE TABLE ai_skill_package (
	id BIGSERIAL NOT NULL, 
	package_id VARCHAR(64) NOT NULL, 
	name VARCHAR(128) NOT NULL, 
	description TEXT, 
	icon VARCHAR(32) DEFAULT 'tool', 
	category VARCHAR(64) DEFAULT 'other', 
	version VARCHAR(32) DEFAULT '1.0.0', 
	enabled BOOLEAN DEFAULT 'true' NOT NULL, 
	file_path VARCHAR(256) NOT NULL, 
	skill_markdown TEXT, 
	created_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (package_id)
);
COMMENT ON COLUMN ai_skill_package.id IS '主键';
COMMENT ON COLUMN ai_skill_package.package_id IS '技能包业务 ID';
COMMENT ON COLUMN ai_skill_package.name IS '技能包名称';
COMMENT ON COLUMN ai_skill_package.description IS '描述';
COMMENT ON COLUMN ai_skill_package.icon IS '图标标识';
COMMENT ON COLUMN ai_skill_package.category IS '类目';
COMMENT ON COLUMN ai_skill_package.version IS '版本';
COMMENT ON COLUMN ai_skill_package.enabled IS '是否启用';
COMMENT ON COLUMN ai_skill_package.file_path IS '相对于 backend/data/skills/ 的路径';
COMMENT ON COLUMN ai_skill_package.skill_markdown IS 'SKILL.md 文件内容，执行时优先于文件系统';
COMMENT ON COLUMN ai_skill_package.created_by IS '创建者 ID';
COMMENT ON COLUMN ai_skill_package.tenant_id IS '租户ID';

-- ai_skill_rule

CREATE TABLE ai_skill_rule (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	conditions JSONB, 
	package_id VARCHAR(64) NOT NULL, 
	agent_name VARCHAR(200), 
	priority INTEGER DEFAULT '100' NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_skill_rule.name IS '规则名称';
COMMENT ON COLUMN ai_skill_rule.conditions IS '触发条件';
COMMENT ON COLUMN ai_skill_rule.package_id IS 'Skill包ID';
COMMENT ON COLUMN ai_skill_rule.agent_name IS '关联专家名称（为空表示全局规则）';
COMMENT ON COLUMN ai_skill_rule.priority IS '优先级';
COMMENT ON COLUMN ai_skill_rule.is_active IS '是否启用';
COMMENT ON COLUMN ai_skill_rule.tenant_id IS '租户ID';

-- ai_skill_script

CREATE TABLE ai_skill_script (
	id BIGSERIAL NOT NULL, 
	package_id VARCHAR(64) NOT NULL, 
	script_id VARCHAR(64) NOT NULL, 
	name VARCHAR(128) NOT NULL, 
	description TEXT, 
	command TEXT NOT NULL, 
	params JSONB, 
	sort_order INTEGER DEFAULT '0', 
	enabled BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (package_id, script_id)
);
COMMENT ON COLUMN ai_skill_script.id IS '主键';
COMMENT ON COLUMN ai_skill_script.package_id IS '所属技能包 ID';
COMMENT ON COLUMN ai_skill_script.script_id IS '脚本业务 ID';
COMMENT ON COLUMN ai_skill_script.name IS '脚本名称';
COMMENT ON COLUMN ai_skill_script.description IS '描述';
COMMENT ON COLUMN ai_skill_script.command IS '执行命令模板，含 {param} 占位符';
COMMENT ON COLUMN ai_skill_script.params IS '参数定义 JSON';
COMMENT ON COLUMN ai_skill_script.sort_order IS '排序';
COMMENT ON COLUMN ai_skill_script.enabled IS '是否启用';
COMMENT ON COLUMN ai_skill_script.tenant_id IS '租户ID';

-- ai_skill_version

CREATE TABLE ai_skill_version (
	id BIGSERIAL NOT NULL, 
	skill_id VARCHAR(100) NOT NULL, 
	version_number INTEGER NOT NULL, 
	changes JSONB, 
	is_stable BOOLEAN DEFAULT 'false' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_skill_version.id IS '主键';
COMMENT ON COLUMN ai_skill_version.skill_id IS '技能 ID（关联 ai_skill_package.package_id）';
COMMENT ON COLUMN ai_skill_version.version_number IS '版本号（自增）';
COMMENT ON COLUMN ai_skill_version.changes IS '版本变更说明 JSON';
COMMENT ON COLUMN ai_skill_version.is_stable IS '是否稳定版本';
COMMENT ON COLUMN ai_skill_version.tenant_id IS '租户ID';

-- ai_tool_definition

CREATE TABLE ai_tool_definition (
	id BIGSERIAL NOT NULL, 
	tool_key VARCHAR(100) NOT NULL, 
	display_name VARCHAR(200) NOT NULL, 
	category VARCHAR(100), 
	tool_type VARCHAR(20) DEFAULT 'custom' NOT NULL, 
	class_name VARCHAR(500), 
	method_name VARCHAR(200), 
	description VARCHAR(2000), 
	config_schema JSON, 
	config_value JSON, 
	input_schema JSON, 
	output_schema JSON, 
	status VARCHAR(20) DEFAULT 'enabled' NOT NULL, 
	is_system BOOLEAN DEFAULT 'false' NOT NULL, 
	sort BIGINT DEFAULT '0' NOT NULL, 
	creator VARCHAR(100), 
	updater VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (tool_key)
);
COMMENT ON COLUMN ai_tool_definition.id IS '主键';
COMMENT ON COLUMN ai_tool_definition.tool_key IS '工具标识 toolKey（唯一）';
COMMENT ON COLUMN ai_tool_definition.display_name IS '显示名称 displayName';
COMMENT ON COLUMN ai_tool_definition.category IS '分类 category（如：信息查询/数据处理/AI增强）';
COMMENT ON COLUMN ai_tool_definition.tool_type IS '工具类型：custom/skill/mcp/group';
COMMENT ON COLUMN ai_tool_definition.class_name IS '实现类全限定名 className（Python module.Class）';
COMMENT ON COLUMN ai_tool_definition.method_name IS '方法名 methodName';
COMMENT ON COLUMN ai_tool_definition.description IS '描述';
COMMENT ON COLUMN ai_tool_definition.config_schema IS '配置 Schema（JSON）';
COMMENT ON COLUMN ai_tool_definition.config_value IS '配置值（JSON）';
COMMENT ON COLUMN ai_tool_definition.input_schema IS '输入参数 JSON Schema（用于测试表单动态渲染）';
COMMENT ON COLUMN ai_tool_definition.output_schema IS '输出参数 JSON Schema';
COMMENT ON COLUMN ai_tool_definition.status IS '状态：enabled / disabled';
COMMENT ON COLUMN ai_tool_definition.is_system IS '是否系统内置工具（系统工具不允许删除）';
COMMENT ON COLUMN ai_tool_definition.sort IS '排序';
COMMENT ON COLUMN ai_tool_definition.creator IS '创建人';
COMMENT ON COLUMN ai_tool_definition.updater IS '更新人';
COMMENT ON COLUMN ai_tool_definition.tenant_id IS '租户ID';

-- ai_tool_group

CREATE TABLE ai_tool_group (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	display_name VARCHAR(200), 
	description VARCHAR(2000), 
	instructions VARCHAR(4000), 
	is_active BOOLEAN DEFAULT 'false' NOT NULL, 
	sort BIGINT DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
COMMENT ON COLUMN ai_tool_group.id IS '主键';
COMMENT ON COLUMN ai_tool_group.name IS '分组名';
COMMENT ON COLUMN ai_tool_group.display_name IS '分组显示名称';
COMMENT ON COLUMN ai_tool_group.description IS '描述';
COMMENT ON COLUMN ai_tool_group.instructions IS '给 Agent 的使用说明';
COMMENT ON COLUMN ai_tool_group.is_active IS '是否启用';
COMMENT ON COLUMN ai_tool_group.sort IS '排序';
COMMENT ON COLUMN ai_tool_group.tenant_id IS '租户ID';

-- ai_web_search

CREATE TABLE ai_web_search (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	api_key TEXT NOT NULL, 
	platform VARCHAR(50) NOT NULL, 
	url VARCHAR(500), 
	app_id VARCHAR(100), 
	property JSON, 
	timeout INTEGER DEFAULT '30' NOT NULL, 
	max_results INTEGER DEFAULT '10' NOT NULL, 
	daily_quota INTEGER DEFAULT '0' NOT NULL, 
	used_count INTEGER DEFAULT '0' NOT NULL, 
	quota_date DATE, 
	priority INTEGER DEFAULT '50' NOT NULL, 
	status INTEGER DEFAULT '1' NOT NULL, 
	sort INTEGER DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	creator VARCHAR(64), 
	updater VARCHAR(64), 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_web_search.id IS '主键';
COMMENT ON COLUMN ai_web_search.name IS '配置名称';
COMMENT ON COLUMN ai_web_search.api_key IS '平台 API Key';
COMMENT ON COLUMN ai_web_search.platform IS '平台: bocha/anspire/google/bing/custom';
COMMENT ON COLUMN ai_web_search.url IS 'API 地址';
COMMENT ON COLUMN ai_web_search.app_id IS 'AppId';
COMMENT ON COLUMN ai_web_search.property IS '扩展配置(含 api_secret 等敏感项)';
COMMENT ON COLUMN ai_web_search.timeout IS '请求超时(秒)';
COMMENT ON COLUMN ai_web_search.max_results IS '单次最大结果数';
COMMENT ON COLUMN ai_web_search.daily_quota IS '每日配额(0=不限)';
COMMENT ON COLUMN ai_web_search.used_count IS '已使用次数(当日)';
COMMENT ON COLUMN ai_web_search.quota_date IS 'used_count 所属日期(用于每日配额重置)';
COMMENT ON COLUMN ai_web_search.priority IS '优先级(越大越优先)';
COMMENT ON COLUMN ai_web_search.status IS '状态: 1=启用, 0=禁用';
COMMENT ON COLUMN ai_web_search.sort IS '排序';
COMMENT ON COLUMN ai_web_search.creator IS '创建人';
COMMENT ON COLUMN ai_web_search.updater IS '更新人';
COMMENT ON COLUMN ai_web_search.tenant_id IS '租户ID';

-- ai_web_search_log

CREATE TABLE ai_web_search_log (
	id SERIAL NOT NULL, 
	web_search_id INTEGER NOT NULL, 
	service_name VARCHAR(64) NOT NULL, 
	platform VARCHAR(32) NOT NULL, 
	query VARCHAR(512) NOT NULL, 
	response_time FLOAT DEFAULT '0' NOT NULL, 
	results_count INTEGER DEFAULT '0' NOT NULL, 
	success BOOLEAN DEFAULT '1' NOT NULL, 
	error TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN ai_web_search_log.id IS '主键';
COMMENT ON COLUMN ai_web_search_log.web_search_id IS '供应商ID';
COMMENT ON COLUMN ai_web_search_log.service_name IS '供应商名称(冗余)';
COMMENT ON COLUMN ai_web_search_log.platform IS '平台';
COMMENT ON COLUMN ai_web_search_log.query IS '搜索关键词';
COMMENT ON COLUMN ai_web_search_log.response_time IS '响应耗时(ms)';
COMMENT ON COLUMN ai_web_search_log.results_count IS '结果条数';
COMMENT ON COLUMN ai_web_search_log.success IS '是否成功';
COMMENT ON COLUMN ai_web_search_log.error IS '错误信息';
COMMENT ON COLUMN ai_web_search_log.tenant_id IS '租户ID';

-- duplex_voice_config

CREATE TABLE duplex_voice_config (
	id BIGSERIAL NOT NULL, 
	role_id VARCHAR(64) NOT NULL, 
	role_name VARCHAR(128), 
	greeting TEXT, 
	voice_identity VARCHAR(64), 
	language VARCHAR(16) DEFAULT 'zh-CN', 
	agent_id VARCHAR(64), 
	case_type VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN duplex_voice_config.role_id IS '角色标识（如 mediator / party_a）';
COMMENT ON COLUMN duplex_voice_config.role_name IS '角色展示名';
COMMENT ON COLUMN duplex_voice_config.greeting IS '开场白';
COMMENT ON COLUMN duplex_voice_config.voice_identity IS '音色标识';
COMMENT ON COLUMN duplex_voice_config.agent_id IS '绑定的 Agent';
COMMENT ON COLUMN duplex_voice_config.case_type IS '适用案件类型（空表示通用）';

-- duplex_voice_session

CREATE TABLE duplex_voice_session (
	id VARCHAR(36) NOT NULL, 
	duplex_session_id BIGINT NOT NULL, 
	case_number VARCHAR(64), 
	participant_id VARCHAR(64), 
	provider VARCHAR(32) NOT NULL, 
	mode VARCHAR(16) DEFAULT 'single' NOT NULL, 
	status VARCHAR(16) DEFAULT 'connecting' NOT NULL, 
	input_sample_rate INTEGER DEFAULT '16000', 
	output_sample_rate INTEGER DEFAULT '24000', 
	agent_id VARCHAR(64), 
	connected_at TIMESTAMP WITHOUT TIME ZONE, 
	disconnected_at TIMESTAMP WITHOUT TIME ZONE, 
	disconnect_reason VARCHAR(64), 
	reconnect_count INTEGER DEFAULT '0', 
	voice_metadata JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN duplex_voice_session.duplex_session_id IS '关联 duplex_session.id（BigInteger，与存量 ORM 一致）';
COMMENT ON COLUMN duplex_voice_session.case_number IS '案件编号检索键';
COMMENT ON COLUMN duplex_voice_session.participant_id IS '说话人/参与者标识';
COMMENT ON COLUMN duplex_voice_session.provider IS 'dashscope|local';
COMMENT ON COLUMN duplex_voice_session.agent_id IS '绑定的 AI Agent 标识';
COMMENT ON COLUMN duplex_voice_session.voice_metadata IS 'voiceIdentity/language/greeting 快照';

-- duplex_voice_turn

CREATE TABLE duplex_voice_turn (
	id BIGSERIAL NOT NULL, 
	voice_session_id VARCHAR(36) NOT NULL, 
	turn_id VARCHAR(64) NOT NULL, 
	turn_generation INTEGER DEFAULT '0', 
	role VARCHAR(16) NOT NULL, 
	input_type VARCHAR(16) NOT NULL, 
	transcript TEXT, 
	response_text TEXT, 
	interrupted BOOLEAN DEFAULT 'false', 
	audio_duration_ms INTEGER, 
	response_duration_ms INTEGER, 
	latency_ms INTEGER, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	cancelled BOOLEAN DEFAULT 'false', 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN duplex_voice_turn.voice_session_id IS '关联 duplex_voice_session.id';
COMMENT ON COLUMN duplex_voice_turn.turn_generation IS '代际号（打断审计）';
COMMENT ON COLUMN duplex_voice_turn.role IS 'user|assistant|system';
COMMENT ON COLUMN duplex_voice_turn.input_type IS 'voice|text';
COMMENT ON COLUMN duplex_voice_turn.latency_ms IS 'SLO：用户说完→AI 首音频';

-- kms_document

CREATE TABLE kms_document (
	id BIGSERIAL NOT NULL, 
	uuid_code VARCHAR(64) NOT NULL, 
	knowledge_id BIGINT NOT NULL, 
	collection VARCHAR(128) NOT NULL, 
	name VARCHAR(500) NOT NULL, 
	source_type VARCHAR(16) DEFAULT 'upload' NOT NULL, 
	file_type VARCHAR(32), 
	file_size BIGINT, 
	status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
	segment_count INTEGER DEFAULT '0' NOT NULL, 
	error_detail TEXT, 
	meta JSONB, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (uuid_code)
);
COMMENT ON COLUMN kms_document.id IS '主键';
COMMENT ON COLUMN kms_document.uuid_code IS '对外文档 ID（=kb_segment.document_id）';
COMMENT ON COLUMN kms_document.knowledge_id IS '所属统一容器';
COMMENT ON COLUMN kms_document.collection IS '落库集合名 → kb_collection.name';
COMMENT ON COLUMN kms_document.name IS '文档显示名/来源名';
COMMENT ON COLUMN kms_document.source_type IS '来源: upload|db_table|api|qa_import|connector';
COMMENT ON COLUMN kms_document.file_type IS '文件类型（pdf/docx/md/…）';
COMMENT ON COLUMN kms_document.file_size IS '字节数';
COMMENT ON COLUMN kms_document.status IS '状态: pending|processing|completed|failed';
COMMENT ON COLUMN kms_document.segment_count IS '切片数';
COMMENT ON COLUMN kms_document.error_detail IS '失败详情（含步骤名）';
COMMENT ON COLUMN kms_document.meta IS '附加元数据';
COMMENT ON COLUMN kms_document.creator_id IS '创建人';
COMMENT ON COLUMN kms_document.created_at IS '创建时间';
COMMENT ON COLUMN kms_document.updated_at IS '更新时间';
COMMENT ON COLUMN kms_document.tenant_id IS '租户ID';

-- kms_knowledge

CREATE TABLE kms_knowledge (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	slug VARCHAR(200) NOT NULL, 
	description TEXT, 
	icon VARCHAR(100), 
	cover_url VARCHAR(500), 
	owner_id BIGINT, 
	status INTEGER DEFAULT '1' NOT NULL, 
	type INTEGER DEFAULT '1' NOT NULL, 
	kb_format VARCHAR(16), 
	multimodal_enabled BOOLEAN DEFAULT 'false' NOT NULL, 
	index_mode VARCHAR(16) DEFAULT 'high_quality' NOT NULL, 
	pipeline_config JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN kms_knowledge.id IS '主键';
COMMENT ON COLUMN kms_knowledge.name IS '知识库名称';
COMMENT ON COLUMN kms_knowledge.slug IS 'URL 友好标识';
COMMENT ON COLUMN kms_knowledge.description IS '简介';
COMMENT ON COLUMN kms_knowledge.icon IS '图标';
COMMENT ON COLUMN kms_knowledge.cover_url IS '封面图 URL';
COMMENT ON COLUMN kms_knowledge.owner_id IS '负责人 ID';
COMMENT ON COLUMN kms_knowledge.status IS '1=启用 0=归档';
COMMENT ON COLUMN kms_knowledge.type IS '知识库类型: 1=llm-wiki 2=general-kb 3=external-kb';
COMMENT ON COLUMN kms_knowledge.kb_format IS '二级形态: document|table|qa|connector|proxy';
COMMENT ON COLUMN kms_knowledge.multimodal_enabled IS 'type=2/document: 图片独立向量化（需 Vision Embedding 模型）';
COMMENT ON COLUMN kms_knowledge.index_mode IS '索引模式: high_quality=向量+全文 | economy=仅关键词，不消耗 embedding';
COMMENT ON COLUMN kms_knowledge.pipeline_config IS '摄取编排: {clean:[...], chunker:{type,params}, index:{...}}';
COMMENT ON COLUMN kms_knowledge.created_at IS '创建时间';
COMMENT ON COLUMN kms_knowledge.updated_at IS '更新时间';
COMMENT ON COLUMN kms_knowledge.tenant_id IS '租户ID';

-- kms_ref

CREATE TABLE kms_ref (
	id BIGSERIAL NOT NULL, 
	kb_id VARCHAR(64) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	as_user_id VARCHAR(64) NOT NULL, 
	doc_count INTEGER DEFAULT '0' NOT NULL, 
	segment_count INTEGER DEFAULT '0' NOT NULL, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (kb_id)
);
COMMENT ON COLUMN kms_ref.id IS '主键';
COMMENT ON COLUMN kms_ref.kb_id IS 'KB 标识';
COMMENT ON COLUMN kms_ref.name IS '名称';
COMMENT ON COLUMN kms_ref.description IS '描述';
COMMENT ON COLUMN kms_ref.as_user_id IS 'AgentScope 侧 user_id';
COMMENT ON COLUMN kms_ref.doc_count IS '文档数';
COMMENT ON COLUMN kms_ref.segment_count IS '切片数';
COMMENT ON COLUMN kms_ref.creator_id IS '创建人';
COMMENT ON COLUMN kms_ref.created_at IS '创建时间';
COMMENT ON COLUMN kms_ref.updated_at IS '更新时间';
COMMENT ON COLUMN kms_ref.tenant_id IS '租户ID';

-- kms_search_log

CREATE TABLE kms_search_log (
	id BIGSERIAL NOT NULL, 
	user_id BIGINT, 
	knowledge_id BIGINT, 
	query TEXT NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	result_count INTEGER DEFAULT '0' NOT NULL, 
	latency_ms INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN kms_search_log.id IS '主键';
COMMENT ON COLUMN kms_search_log.user_id IS '检索用户 ID';
COMMENT ON COLUMN kms_search_log.knowledge_id IS '检索的知识库 ID (null=全库检索)';
COMMENT ON COLUMN kms_search_log.query IS '检索词';
COMMENT ON COLUMN kms_search_log.mode IS '检索模式：semantic | keyword | hybrid | llm_wiki';
COMMENT ON COLUMN kms_search_log.result_count IS '命中数量';
COMMENT ON COLUMN kms_search_log.latency_ms IS '检索耗时(毫秒)';
COMMENT ON COLUMN kms_search_log.created_at IS '创建时间';
COMMENT ON COLUMN kms_search_log.tenant_id IS '租户ID';

-- kms_segment

CREATE TABLE kms_segment (
	id BIGSERIAL NOT NULL, 
	collection VARCHAR(128) NOT NULL, 
	document_id VARCHAR(128) NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	content TEXT, 
	embedding VECTOR(768), 
	token_count INTEGER, 
	metadata JSONB, 
	class_uris JSONB, 
	chunk_type VARCHAR(16) DEFAULT 'text' NOT NULL, 
	parent_id BIGINT, 
	answer TEXT, 
	keywords JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_kms_segment UNIQUE (collection, document_id, chunk_index), 
	FOREIGN KEY(parent_id) REFERENCES kms_segment (id) ON DELETE CASCADE
);
COMMENT ON COLUMN kms_segment.id IS '主键';
COMMENT ON COLUMN kms_segment.collection IS '集合名';
COMMENT ON COLUMN kms_segment.document_id IS '文档 ID';
COMMENT ON COLUMN kms_segment.chunk_index IS '文档内切片序号';
COMMENT ON COLUMN kms_segment.content IS '切片文本';
COMMENT ON COLUMN kms_segment.embedding IS '向量';
COMMENT ON COLUMN kms_segment.token_count IS 'token 数';
COMMENT ON COLUMN kms_segment.metadata IS '切片元数据';
COMMENT ON COLUMN kms_segment.class_uris IS '映射到的本体类 uri 列表（P4 Task 7 检索过滤用）';
COMMENT ON COLUMN kms_segment.chunk_type IS '切片类型: text|qa|table_row|image|parent|child';
COMMENT ON COLUMN kms_segment.parent_id IS '父子分段: 子块 → 父块';
COMMENT ON COLUMN kms_segment.answer IS 'chunk_type=qa: 完整答案（content=问题，仅问题做 embedding）';
COMMENT ON COLUMN kms_segment.keywords IS '手动关键词（全文检索加权）';
COMMENT ON COLUMN kms_segment.created_at IS '创建时间';
COMMENT ON COLUMN kms_segment.tenant_id IS '租户ID';

-- meta_column_standard_history

CREATE TABLE meta_column_standard_history (
	id BIGSERIAL NOT NULL, 
	column_id BIGINT NOT NULL, 
	standard_id BIGINT NOT NULL, 
	standard_version INTEGER, 
	action VARCHAR(32) NOT NULL, 
	snapshot_json JSONB, 
	actor_user_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN meta_column_standard_history.id IS '主键';
COMMENT ON COLUMN meta_column_standard_history.column_id IS '列 ID';
COMMENT ON COLUMN meta_column_standard_history.standard_id IS '标准项 ID';
COMMENT ON COLUMN meta_column_standard_history.standard_version IS '涉及版本';
COMMENT ON COLUMN meta_column_standard_history.action IS '动作: bind|unbind|accept|reject|override';
COMMENT ON COLUMN meta_column_standard_history.snapshot_json IS '变更时绑定快照';
COMMENT ON COLUMN meta_column_standard_history.actor_user_id IS '操作人';
COMMENT ON COLUMN meta_column_standard_history.created_at IS '创建时间';
COMMENT ON COLUMN meta_column_standard_history.tenant_id IS '租户ID';

-- meta_connector_ingest

CREATE TABLE meta_connector_ingest (
	id BIGSERIAL NOT NULL, 
	connector_type VARCHAR(32) NOT NULL, 
	external_id VARCHAR(255) NOT NULL, 
	payload JSON NOT NULL, 
	cursor_value VARCHAR(255), 
	ingested_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_connector_ingest UNIQUE (tenant_id, connector_type, external_id)
);
COMMENT ON COLUMN meta_connector_ingest.id IS '主键';
COMMENT ON COLUMN meta_connector_ingest.connector_type IS '连接器类型: http|dingtalk|feishu|wecom';
COMMENT ON COLUMN meta_connector_ingest.external_id IS '外部记录唯一标识（缺省由 payload 哈希生成）';
COMMENT ON COLUMN meta_connector_ingest.payload IS '映射后的记录（目标字段）';
COMMENT ON COLUMN meta_connector_ingest.cursor_value IS '该记录的增量游标值';
COMMENT ON COLUMN meta_connector_ingest.ingested_at IS '落库时间';
COMMENT ON COLUMN meta_connector_ingest.tenant_id IS '租户ID';

-- meta_connector_sync_state

CREATE TABLE meta_connector_sync_state (
	id BIGSERIAL NOT NULL, 
	connector_type VARCHAR(32) NOT NULL, 
	last_cursor VARCHAR(255), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_connector_sync_state UNIQUE (tenant_id, connector_type)
);
COMMENT ON COLUMN meta_connector_sync_state.id IS '主键';
COMMENT ON COLUMN meta_connector_sync_state.connector_type IS '连接器类型';
COMMENT ON COLUMN meta_connector_sync_state.last_cursor IS '最近一次同步的最大游标值';
COMMENT ON COLUMN meta_connector_sync_state.updated_at IS '更新时间';
COMMENT ON COLUMN meta_connector_sync_state.tenant_id IS '租户ID';

-- meta_data_source

CREATE TABLE meta_data_source (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(128) NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	host VARCHAR(256) NOT NULL, 
	port INTEGER NOT NULL, 
	username VARCHAR(128), 
	password_enc TEXT, 
	database VARCHAR(128), 
	charset VARCHAR(32) DEFAULT 'utf8mb4' NOT NULL, 
	status VARCHAR(32) DEFAULT 'unknown' NOT NULL, 
	is_default BOOLEAN DEFAULT '0' NOT NULL, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_data_source_name UNIQUE (tenant_id, name)
);
COMMENT ON COLUMN meta_data_source.id IS '主键';
COMMENT ON COLUMN meta_data_source.name IS '显示名称';
COMMENT ON COLUMN meta_data_source.source_type IS '数据源类型: mysql|doris|postgresql';
COMMENT ON COLUMN meta_data_source.host IS '主机';
COMMENT ON COLUMN meta_data_source.port IS '端口';
COMMENT ON COLUMN meta_data_source.username IS '用户名';
COMMENT ON COLUMN meta_data_source.password_enc IS '密码密文（Fernet，永不外显）';
COMMENT ON COLUMN meta_data_source.database IS '默认库';
COMMENT ON COLUMN meta_data_source.charset IS '字符集';
COMMENT ON COLUMN meta_data_source.status IS '状态: unknown|online|offline';
COMMENT ON COLUMN meta_data_source.is_default IS '是否租户默认数据源';
COMMENT ON COLUMN meta_data_source.creator_id IS '创建者 ID';
COMMENT ON COLUMN meta_data_source.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN meta_data_source.created_at IS '创建时间';
COMMENT ON COLUMN meta_data_source.updated_at IS '更新时间';
COMMENT ON COLUMN meta_data_source.tenant_id IS '租户ID';

-- meta_standard

CREATE TABLE meta_standard (
	id BIGSERIAL NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	aliases_json JSONB, 
	description TEXT, 
	semantic_type VARCHAR(64), 
	data_type_expect VARCHAR(64), 
	length_rule_json JSONB, 
	security_level VARCHAR(8), 
	quality_rule_json JSONB, 
	mask_rule VARCHAR(200), 
	domain VARCHAR(64), 
	status VARCHAR(32) DEFAULT 'draft' NOT NULL, 
	current_version INTEGER DEFAULT '1' NOT NULL, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_meta_standard_code UNIQUE (tenant_id, code)
);
COMMENT ON COLUMN meta_standard.id IS '主键';
COMMENT ON COLUMN meta_standard.code IS '标准项编码（租户内唯一）';
COMMENT ON COLUMN meta_standard.name IS '标准名称';
COMMENT ON COLUMN meta_standard.aliases_json IS '别名列表（规则匹配用）';
COMMENT ON COLUMN meta_standard.description IS '说明';
COMMENT ON COLUMN meta_standard.semantic_type IS '语义类型';
COMMENT ON COLUMN meta_standard.data_type_expect IS '期望数据类型';
COMMENT ON COLUMN meta_standard.length_rule_json IS '长度规则';
COMMENT ON COLUMN meta_standard.security_level IS '安全等级: L0|L1|L2|L3';
COMMENT ON COLUMN meta_standard.quality_rule_json IS '质量规则';
COMMENT ON COLUMN meta_standard.mask_rule IS '脱敏规则';
COMMENT ON COLUMN meta_standard.domain IS '主题域';
COMMENT ON COLUMN meta_standard.status IS '状态: draft|published';
COMMENT ON COLUMN meta_standard.current_version IS '当前版本号';
COMMENT ON COLUMN meta_standard.creator_id IS '创建者 ID';
COMMENT ON COLUMN meta_standard.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN meta_standard.created_at IS '创建时间';
COMMENT ON COLUMN meta_standard.updated_at IS '更新时间';
COMMENT ON COLUMN meta_standard.tenant_id IS '租户ID';

-- ontology

CREATE TABLE ontology (
	id BIGSERIAL NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	name VARCHAR(200), 
	description TEXT, 
	namespace_uri VARCHAR(500), 
	version INTEGER DEFAULT '1' NOT NULL, 
	status VARCHAR(32) DEFAULT 'draft' NOT NULL, 
	source VARCHAR(32) DEFAULT 'manual' NOT NULL, 
	ttl_content TEXT, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_code UNIQUE (tenant_id, code)
);
COMMENT ON COLUMN ontology.id IS '主键';
COMMENT ON COLUMN ontology.code IS '本体编码（租户内唯一，如 default）';
COMMENT ON COLUMN ontology.name IS '本体名称';
COMMENT ON COLUMN ontology.description IS '本体描述';
COMMENT ON COLUMN ontology.namespace_uri IS '本体命名空间 URI';
COMMENT ON COLUMN ontology.version IS '本体版本号';
COMMENT ON COLUMN ontology.status IS '状态: draft|published|archived';
COMMENT ON COLUMN ontology.source IS '来源: manual|ttl_import|build';
COMMENT ON COLUMN ontology.ttl_content IS 'TTL 原文（唯一真相源：规范化后的全量内容，类与标注索引均由它派生）';
COMMENT ON COLUMN ontology.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology.created_at IS '创建时间';
COMMENT ON COLUMN ontology.updated_at IS '更新时间';
COMMENT ON COLUMN ontology.tenant_id IS '租户ID';

-- sop_templates

CREATE TABLE sop_templates (
	id BIGSERIAL NOT NULL, 
	template_key VARCHAR(100) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	tags JSON, 
	definition JSON NOT NULL, 
	builtin BOOLEAN DEFAULT 'false' NOT NULL, 
	enabled BOOLEAN DEFAULT 'true' NOT NULL, 
	created_by VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN sop_templates.id IS '主键';
COMMENT ON COLUMN sop_templates.template_key IS '模板稳定标识（对应代码注册表 id），种子幂等依据';
COMMENT ON COLUMN sop_templates.name IS '模板名称';
COMMENT ON COLUMN sop_templates.description IS '模板描述';
COMMENT ON COLUMN sop_templates.tags IS '标签列表';
COMMENT ON COLUMN sop_templates.definition IS 'SOPDefinition 序列化 JSON';
COMMENT ON COLUMN sop_templates.builtin IS '系统内置为 true（由系统拥有，种子可刷新）；用户/预设为 false';
COMMENT ON COLUMN sop_templates.enabled IS '是否启用';
COMMENT ON COLUMN sop_templates.created_by IS '创建人';
COMMENT ON COLUMN sop_templates.created_at IS '创建时间';
COMMENT ON COLUMN sop_templates.updated_at IS '更新时间';

-- sys_audit_log

CREATE TABLE sys_audit_log (
	log_id BIGSERIAL NOT NULL, 
	user_id BIGINT, 
	username VARCHAR(50), 
	operation_type VARCHAR(50) NOT NULL, 
	operation_module VARCHAR(50), 
	operation_desc TEXT, 
	request_method VARCHAR(10), 
	request_url VARCHAR(500), 
	request_params JSONB, 
	request_ip VARCHAR(50), 
	user_agent VARCHAR(500), 
	response_status INTEGER, 
	response_time_ms INTEGER, 
	old_data JSONB, 
	new_data JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (log_id)
);
COMMENT ON COLUMN sys_audit_log.tenant_id IS '租户ID';

-- sys_dictionary

CREATE TABLE sys_dictionary (
	dict_id BIGSERIAL NOT NULL, 
	dict_code VARCHAR(50) NOT NULL, 
	dict_name VARCHAR(100) NOT NULL, 
	dict_type VARCHAR(50) NOT NULL, 
	description TEXT, 
	sort_order INTEGER, 
	is_active BOOLEAN NOT NULL, 
	extra_data JSON, 
	created_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (dict_id), 
	UNIQUE (dict_code)
);
COMMENT ON COLUMN sys_dictionary.dict_id IS '字典ID';
COMMENT ON COLUMN sys_dictionary.dict_code IS '字典编码';
COMMENT ON COLUMN sys_dictionary.dict_name IS '字典名称';
COMMENT ON COLUMN sys_dictionary.dict_type IS '字典类型';
COMMENT ON COLUMN sys_dictionary.description IS '字典描述';
COMMENT ON COLUMN sys_dictionary.sort_order IS '排序顺序';
COMMENT ON COLUMN sys_dictionary.is_active IS '是否启用';
COMMENT ON COLUMN sys_dictionary.extra_data IS '扩展数据';
COMMENT ON COLUMN sys_dictionary.created_by IS '创建人ID';
COMMENT ON COLUMN sys_dictionary.tenant_id IS '租户ID';

-- sys_dictionary_item

CREATE TABLE sys_dictionary_item (
	item_id BIGSERIAL NOT NULL, 
	dict_code VARCHAR(50) NOT NULL, 
	item_code VARCHAR(50) NOT NULL, 
	item_name VARCHAR(100) NOT NULL, 
	item_value VARCHAR(200), 
	parent_code VARCHAR(50), 
	level INTEGER, 
	color VARCHAR(20), 
	icon VARCHAR(50), 
	sort_order INTEGER, 
	is_active BOOLEAN NOT NULL, 
	extra_data JSON, 
	remark TEXT, 
	created_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (item_id)
);
COMMENT ON COLUMN sys_dictionary_item.item_id IS '字典项ID';
COMMENT ON COLUMN sys_dictionary_item.dict_code IS '所属字典编码';
COMMENT ON COLUMN sys_dictionary_item.item_code IS '字典项编码';
COMMENT ON COLUMN sys_dictionary_item.item_name IS '字典项名称';
COMMENT ON COLUMN sys_dictionary_item.item_value IS '字典项值';
COMMENT ON COLUMN sys_dictionary_item.parent_code IS '父级编码';
COMMENT ON COLUMN sys_dictionary_item.level IS '层级';
COMMENT ON COLUMN sys_dictionary_item.color IS '颜色标识';
COMMENT ON COLUMN sys_dictionary_item.icon IS '图标';
COMMENT ON COLUMN sys_dictionary_item.sort_order IS '排序顺序';
COMMENT ON COLUMN sys_dictionary_item.is_active IS '是否启用';
COMMENT ON COLUMN sys_dictionary_item.extra_data IS '扩展数据';
COMMENT ON COLUMN sys_dictionary_item.remark IS '备注';
COMMENT ON COLUMN sys_dictionary_item.created_by IS '创建人ID';
COMMENT ON COLUMN sys_dictionary_item.tenant_id IS '租户ID';

-- sys_infra_file

CREATE TABLE sys_infra_file (
	id INTEGER NOT NULL, 
	config_id BIGINT, 
	name VARCHAR(256), 
	path VARCHAR(512) NOT NULL, 
	url VARCHAR(1024) NOT NULL, 
	type VARCHAR(128), 
	size INTEGER NOT NULL, 
	creator VARCHAR(64), 
	create_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updater VARCHAR(64), 
	update_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	deleted VARCHAR(1) NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN sys_infra_file.id IS '文件编号';
COMMENT ON COLUMN sys_infra_file.config_id IS '配置编号';
COMMENT ON COLUMN sys_infra_file.name IS '文件名';
COMMENT ON COLUMN sys_infra_file.path IS '文件路径（磁盘）';
COMMENT ON COLUMN sys_infra_file.url IS '文件 URL';
COMMENT ON COLUMN sys_infra_file.type IS '文件类型/MIME';
COMMENT ON COLUMN sys_infra_file.size IS '文件大小（字节）';
COMMENT ON COLUMN sys_infra_file.creator IS '创建者';
COMMENT ON COLUMN sys_infra_file.create_time IS '创建时间';
COMMENT ON COLUMN sys_infra_file.updater IS '更新者';
COMMENT ON COLUMN sys_infra_file.update_time IS '更新时间';
COMMENT ON COLUMN sys_infra_file.deleted IS '是否删除';
COMMENT ON COLUMN sys_infra_file.tenant_id IS '租户ID';

-- sys_infra_file_content

CREATE TABLE sys_infra_file_content (
	id INTEGER NOT NULL, 
	config_id BIGINT NOT NULL, 
	path VARCHAR(512) NOT NULL, 
	content TEXT NOT NULL, 
	creator VARCHAR(64), 
	create_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updater VARCHAR(64), 
	update_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	deleted VARCHAR(1) NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN sys_infra_file_content.id IS '编号';
COMMENT ON COLUMN sys_infra_file_content.config_id IS '配置编号';
COMMENT ON COLUMN sys_infra_file_content.path IS '文件路径';
COMMENT ON COLUMN sys_infra_file_content.content IS '文件内容（字节流）';
COMMENT ON COLUMN sys_infra_file_content.creator IS '创建者';
COMMENT ON COLUMN sys_infra_file_content.create_time IS '创建时间';
COMMENT ON COLUMN sys_infra_file_content.updater IS '更新者';
COMMENT ON COLUMN sys_infra_file_content.update_time IS '更新时间';
COMMENT ON COLUMN sys_infra_file_content.deleted IS '是否删除';
COMMENT ON COLUMN sys_infra_file_content.tenant_id IS '租户ID';

-- sys_menu

CREATE TABLE sys_menu (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	permission VARCHAR(100), 
	path VARCHAR(255), 
	type INTEGER, 
	sort INTEGER, 
	parent_id BIGINT, 
	icon VARCHAR(100), 
	component VARCHAR(255), 
	component_name VARCHAR(100), 
	status INTEGER, 
	visible INTEGER, 
	keep_alive INTEGER, 
	always_show INTEGER, 
	i18n_key VARCHAR(100), 
	is_deleted BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

-- sys_region

CREATE TABLE sys_region (
	region_id BIGSERIAL NOT NULL, 
	region_code VARCHAR(20) NOT NULL, 
	region_name VARCHAR(100) NOT NULL, 
	parent_code VARCHAR(20), 
	region_level VARCHAR(20) NOT NULL, 
	full_path VARCHAR(500), 
	sort_order INTEGER, 
	longitude VARCHAR(20), 
	latitude VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (region_id), 
	UNIQUE (region_code)
);

-- sys_role

CREATE TABLE sys_role (
	role_id BIGSERIAL NOT NULL, 
	role_name VARCHAR(100) NOT NULL, 
	role_code VARCHAR(50) NOT NULL, 
	region_code VARCHAR(20), 
	region_level VARCHAR(20), 
	description TEXT, 
	sort_order INTEGER, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (role_id), 
	UNIQUE (role_code)
);
COMMENT ON COLUMN sys_role.tenant_id IS '租户ID';

-- sys_tenant_package

CREATE TABLE sys_tenant_package (
	package_id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	remark VARCHAR(500), 
	menu_ids JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (package_id)
);
COMMENT ON COLUMN sys_tenant_package.name IS '套餐名称';
COMMENT ON COLUMN sys_tenant_package.status IS '状态(active/disabled)';
COMMENT ON COLUMN sys_tenant_package.remark IS '备注';
COMMENT ON COLUMN sys_tenant_package.menu_ids IS '关联菜单ID集合';

-- sys_user

CREATE TABLE sys_user (
	user_id BIGSERIAL NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	real_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(20), 
	email VARCHAR(100), 
	avatar_url VARCHAR(500), 
	status VARCHAR(20) NOT NULL, 
	is_admin BOOLEAN NOT NULL, 
	last_login_at TIMESTAMP WITHOUT TIME ZONE, 
	last_login_ip VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	is_deleted BOOLEAN NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (user_id)
);
COMMENT ON COLUMN sys_user.tenant_id IS '租户ID';

-- sys_user_notification

CREATE TABLE sys_user_notification (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	ntype VARCHAR(32) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	content TEXT, 
	ref_id INTEGER, 
	ref_type VARCHAR(32), 
	is_read BOOLEAN NOT NULL, 
	expire_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN sys_user_notification.id IS '主键';
COMMENT ON COLUMN sys_user_notification.user_id IS '接收用户ID';
COMMENT ON COLUMN sys_user_notification.ntype IS '通知类型: system/async_task/research/scheduled/...';
COMMENT ON COLUMN sys_user_notification.title IS '通知标题';
COMMENT ON COLUMN sys_user_notification.content IS '通知内容';
COMMENT ON COLUMN sys_user_notification.ref_id IS '关联业务ID(如任务ID)';
COMMENT ON COLUMN sys_user_notification.ref_type IS '关联业务类型';
COMMENT ON COLUMN sys_user_notification.is_read IS '已读状态';
COMMENT ON COLUMN sys_user_notification.expire_at IS '过期时间(可空=不过期)';
COMMENT ON COLUMN sys_user_notification.created_at IS '创建时间';
COMMENT ON COLUMN sys_user_notification.tenant_id IS '租户ID';

-- tool_policy

CREATE TABLE tool_policy (
	id BIGSERIAL NOT NULL, 
	tool_name VARCHAR(128) NOT NULL, 
	enabled BOOLEAN DEFAULT 'true', 
	timeout_ms INTEGER DEFAULT '8000', 
	max_calls_per_turn INTEGER DEFAULT '2', 
	max_result_bytes INTEGER DEFAULT '32768', 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

-- workflow_chain

CREATE TABLE workflow_chain (
	id BIGSERIAL NOT NULL, 
	chain_code VARCHAR(100) NOT NULL, 
	chain_name VARCHAR(200) NOT NULL, 
	steps JSONB DEFAULT '[]' NOT NULL, 
	description TEXT, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN DEFAULT 'false' NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN workflow_chain.chain_code IS '链唯一标识码';
COMMENT ON COLUMN workflow_chain.steps IS '步骤列表 JSON';
COMMENT ON COLUMN workflow_chain.tenant_id IS '租户ID';

-- workflow_execution_log

CREATE TABLE workflow_execution_log (
	id BIGSERIAL NOT NULL, 
	flow_id BIGINT NOT NULL, 
	execution_id VARCHAR(64), 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	input_data JSONB, 
	output_data JSONB, 
	error_message TEXT, 
	latency_ms INTEGER, 
	retry_count INTEGER DEFAULT '0' NOT NULL, 
	platform_trace JSONB, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN workflow_execution_log.flow_id IS 'FK → workflow_flow.id';
COMMENT ON COLUMN workflow_execution_log.execution_id IS '关联 agent_execution.execution_id';
COMMENT ON COLUMN workflow_execution_log.status IS 'pending / running / success / failed / timeout / cancelled';
COMMENT ON COLUMN workflow_execution_log.input_data IS '实际输入';
COMMENT ON COLUMN workflow_execution_log.output_data IS '实际输出';
COMMENT ON COLUMN workflow_execution_log.platform_trace IS '平台原始响应';
COMMENT ON COLUMN workflow_execution_log.tenant_id IS '租户ID';

-- workflow_flow

CREATE TABLE workflow_flow (
	id BIGSERIAL NOT NULL, 
	flow_code VARCHAR(100) NOT NULL, 
	flow_name VARCHAR(200) NOT NULL, 
	platform_type VARCHAR(50) DEFAULT 'dify' NOT NULL, 
	flow_type VARCHAR(50) NOT NULL, 
	base_url VARCHAR(500) NOT NULL, 
	api_key_enc TEXT NOT NULL, 
	input_schema JSONB DEFAULT '{}' NOT NULL, 
	output_schema JSONB, 
	config JSONB, 
	description TEXT, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	created_by BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN DEFAULT 'false' NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id)
);
COMMENT ON COLUMN workflow_flow.flow_code IS '业务唯一标识码';
COMMENT ON COLUMN workflow_flow.flow_name IS '工作流名称';
COMMENT ON COLUMN workflow_flow.platform_type IS '平台类型: dify / coze / custom_http';
COMMENT ON COLUMN workflow_flow.flow_type IS '流程类型: Workflow / Chatflow / Chatbot / Agent / Completion';
COMMENT ON COLUMN workflow_flow.base_url IS '平台 API 基地址';
COMMENT ON COLUMN workflow_flow.api_key_enc IS '加密后的 API Key';
COMMENT ON COLUMN workflow_flow.input_schema IS '入参 JSON Schema';
COMMENT ON COLUMN workflow_flow.output_schema IS '出参 JSON Schema';
COMMENT ON COLUMN workflow_flow.config IS '平台扩展配置';
COMMENT ON COLUMN workflow_flow.tenant_id IS '租户ID';

-- ai_chat_message

CREATE TABLE ai_chat_message (
	message_id BIGSERIAL NOT NULL, 
	session_id BIGINT NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	content TEXT NOT NULL, 
	message_type VARCHAR(20), 
	tool_calls JSON, 
	tool_results JSON, 
	extra_data JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	file_id BIGINT, 
	agent_id VARCHAR(50), 
	execution_time_ms INTEGER, 
	execution_id VARCHAR(64), 
	tenant_id BIGINT, 
	PRIMARY KEY (message_id), 
	FOREIGN KEY(session_id) REFERENCES ai_chat_session (session_id), 
	FOREIGN KEY(file_id) REFERENCES sys_infra_file (id) ON DELETE SET NULL
);
COMMENT ON COLUMN ai_chat_message.message_id IS '消息ID';
COMMENT ON COLUMN ai_chat_message.session_id IS '会话ID';
COMMENT ON COLUMN ai_chat_message.role IS '角色：user-用户, assistant-AI助理, system-系统';
COMMENT ON COLUMN ai_chat_message.content IS '消息内容';
COMMENT ON COLUMN ai_chat_message.message_type IS '消息类型：text-文本, chart-图表, table-表格';
COMMENT ON COLUMN ai_chat_message.tool_calls IS '工具调用';
COMMENT ON COLUMN ai_chat_message.tool_results IS '工具结果';
COMMENT ON COLUMN ai_chat_message.extra_data IS '扩展数据';
COMMENT ON COLUMN ai_chat_message.created_at IS '创建时间';
COMMENT ON COLUMN ai_chat_message.file_id IS '文件ID（关联 infra_file.id）';
COMMENT ON COLUMN ai_chat_message.agent_id IS '执行此消息的 Agent ID';
COMMENT ON COLUMN ai_chat_message.execution_time_ms IS '执行耗时(毫秒)';
COMMENT ON COLUMN ai_chat_message.execution_id IS '关联 agent_execution.execution_id';
COMMENT ON COLUMN ai_chat_message.tenant_id IS '租户ID';

-- ai_chat_model

CREATE TABLE ai_chat_model (
	id SERIAL NOT NULL, 
	code VARCHAR(100), 
	key_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	platform VARCHAR(50), 
	sort INTEGER DEFAULT '0' NOT NULL, 
	status INTEGER DEFAULT '1' NOT NULL, 
	type INTEGER, 
	temperature FLOAT, 
	max_tokens INTEGER, 
	top_k INTEGER, 
	top_p FLOAT, 
	seed INTEGER, 
	max_contexts INTEGER, 
	max_turns INTEGER, 
	dimensions INTEGER, 
	retry INTEGER, 
	timeout INTEGER, 
	stream_timeout INTEGER, 
	enable_thinking BOOLEAN, 
	enable_search BOOLEAN, 
	is_default BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(key_id) REFERENCES ai_api_key (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ai_chat_model.code IS '模型编码';
COMMENT ON COLUMN ai_chat_model.key_id IS 'API 密钥编号';
COMMENT ON COLUMN ai_chat_model.name IS '模型名称';
COMMENT ON COLUMN ai_chat_model.model IS '模型标志/模型ID';
COMMENT ON COLUMN ai_chat_model.platform IS '平台';
COMMENT ON COLUMN ai_chat_model.sort IS '排序';
COMMENT ON COLUMN ai_chat_model.status IS '状态: 1=启用, 0=禁用';
COMMENT ON COLUMN ai_chat_model.type IS '类型';
COMMENT ON COLUMN ai_chat_model.temperature IS '温度参数';
COMMENT ON COLUMN ai_chat_model.max_tokens IS '最大 Token 数';
COMMENT ON COLUMN ai_chat_model.top_k IS '保留概率最高的 k 个单词';
COMMENT ON COLUMN ai_chat_model.top_p IS '累积概率阈值 p';
COMMENT ON COLUMN ai_chat_model.seed IS '随机种子';
COMMENT ON COLUMN ai_chat_model.max_contexts IS '上下文最大 Message 数';
COMMENT ON COLUMN ai_chat_model.max_turns IS '最大轮次';
COMMENT ON COLUMN ai_chat_model.dimensions IS '维度';
COMMENT ON COLUMN ai_chat_model.retry IS '重试次数';
COMMENT ON COLUMN ai_chat_model.timeout IS '超时时间(秒)';
COMMENT ON COLUMN ai_chat_model.stream_timeout IS '流式超时(秒)';
COMMENT ON COLUMN ai_chat_model.enable_thinking IS '支持思考';
COMMENT ON COLUMN ai_chat_model.enable_search IS '支持搜索';
COMMENT ON COLUMN ai_chat_model.is_default IS '是否默认模型';
COMMENT ON COLUMN ai_chat_model.tenant_id IS '租户ID';

-- ai_mcp_client

CREATE TABLE ai_mcp_client (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	api_key_id BIGINT NOT NULL, 
	client_type VARCHAR(20) NOT NULL, 
	mcp_type VARCHAR(20) NOT NULL, 
	version VARCHAR(20), 
	description VARCHAR(2000), 
	tools_config JSON, 
	remark TEXT, 
	status INTEGER DEFAULT '1' NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	creator VARCHAR(100), 
	updater VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(api_key_id) REFERENCES ai_mcp_api_key (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ai_mcp_client.id IS '主键';
COMMENT ON COLUMN ai_mcp_client.name IS '客户端名称';
COMMENT ON COLUMN ai_mcp_client.api_key_id IS '关联API Key';
COMMENT ON COLUMN ai_mcp_client.client_type IS '客户端类型: stdio/http/sse';
COMMENT ON COLUMN ai_mcp_client.mcp_type IS '应用类别: tool/resource';
COMMENT ON COLUMN ai_mcp_client.version IS '客户端版本';
COMMENT ON COLUMN ai_mcp_client.description IS '描述';
COMMENT ON COLUMN ai_mcp_client.tools_config IS '工具配置';
COMMENT ON COLUMN ai_mcp_client.remark IS '备注';
COMMENT ON COLUMN ai_mcp_client.status IS '1=启用,0=禁用';
COMMENT ON COLUMN ai_mcp_client.is_active IS '是否启用';
COMMENT ON COLUMN ai_mcp_client.creator IS '创建人';
COMMENT ON COLUMN ai_mcp_client.updater IS '更新人';
COMMENT ON COLUMN ai_mcp_client.tenant_id IS '租户ID';

-- ai_tool_group_member

CREATE TABLE ai_tool_group_member (
	group_id BIGINT NOT NULL, 
	tool_key VARCHAR(100) NOT NULL, 
	sort_order BIGINT DEFAULT '0', 
	tenant_id BIGINT, 
	PRIMARY KEY (group_id, tool_key), 
	FOREIGN KEY(group_id) REFERENCES ai_tool_group (id) ON DELETE CASCADE, 
	FOREIGN KEY(tool_key) REFERENCES ai_tool_definition (tool_key) ON DELETE CASCADE
);
COMMENT ON COLUMN ai_tool_group_member.group_id IS '分组 ID';
COMMENT ON COLUMN ai_tool_group_member.tool_key IS '工具标识 toolKey';
COMMENT ON COLUMN ai_tool_group_member.sort_order IS '组内排序';
COMMENT ON COLUMN ai_tool_group_member.tenant_id IS '租户ID';

-- ai_workspace

CREATE TABLE ai_workspace (
	id SERIAL NOT NULL, 
	workspace_id VARCHAR(100) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description VARCHAR(500), 
	scope VARCHAR(20) NOT NULL, 
	execution_mode VARCHAR(20) NOT NULL, 
	workspace_type VARCHAR(30) NOT NULL, 
	user_id BIGINT, 
	config JSON NOT NULL, 
	mcp_ids JSON, 
	skill_ids JSON, 
	is_default BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES sys_user (user_id)
);
COMMENT ON COLUMN ai_workspace.workspace_id IS '业务唯一标识(UUID)';
COMMENT ON COLUMN ai_workspace.name IS '工作空间名称';
COMMENT ON COLUMN ai_workspace.description IS '描述';
COMMENT ON COLUMN ai_workspace.scope IS 'public/private';
COMMENT ON COLUMN ai_workspace.execution_mode IS 'remote/local';
COMMENT ON COLUMN ai_workspace.workspace_type IS 'local/docker/opensandbox';
COMMENT ON COLUMN ai_workspace.user_id IS '私有空间绑定用户';
COMMENT ON COLUMN ai_workspace.config IS '后端特定配置';
COMMENT ON COLUMN ai_workspace.mcp_ids IS '引用的MCP服务ID列表';
COMMENT ON COLUMN ai_workspace.skill_ids IS '引用的技能ID列表';
COMMENT ON COLUMN ai_workspace.is_default IS '是否为用户默认工作空间';
COMMENT ON COLUMN ai_workspace.status IS 'active/disabled';
COMMENT ON COLUMN ai_workspace.created_by IS '创建者';
COMMENT ON COLUMN ai_workspace.created_at IS '创建时间';
COMMENT ON COLUMN ai_workspace.updated_at IS '更新时间';
COMMENT ON COLUMN ai_workspace.is_deleted IS '软删除';
COMMENT ON COLUMN ai_workspace.tenant_id IS '租户ID';

-- kms_article

CREATE TABLE kms_article (
	id BIGSERIAL NOT NULL, 
	slug VARCHAR(200) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	content TEXT, 
	summary VARCHAR(1000), 
	owl_class_uris JSONB, 
	content_vector VECTOR(768), 
	wiki_links JSONB, 
	backlinks JSONB, 
	knowledge_id BIGINT, 
	category_id BIGINT, 
	tags JSONB, 
	status INTEGER DEFAULT '1' NOT NULL, 
	is_featured BOOLEAN DEFAULT 'false' NOT NULL, 
	view_count INTEGER DEFAULT '0' NOT NULL, 
	version INTEGER DEFAULT '1' NOT NULL, 
	okf_type VARCHAR(64), 
	resource VARCHAR(500), 
	sources JSONB, 
	verified JSONB, 
	stale_after TIMESTAMP WITHOUT TIME ZONE, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(knowledge_id) REFERENCES kms_knowledge (id) ON DELETE CASCADE
);
COMMENT ON COLUMN kms_article.id IS '主键';
COMMENT ON COLUMN kms_article.slug IS 'URL 友好标识';
COMMENT ON COLUMN kms_article.title IS '文章标题';
COMMENT ON COLUMN kms_article.content IS 'Markdown 正文';
COMMENT ON COLUMN kms_article.summary IS '摘要 (自动生成或手动填写)';
COMMENT ON COLUMN kms_article.owl_class_uris IS '关联的 OWL 类 URI 列表';
COMMENT ON COLUMN kms_article.content_vector IS '内容向量 (embedding)';
COMMENT ON COLUMN kms_article.wiki_links IS '本文链接到的其他文章 slug 列表';
COMMENT ON COLUMN kms_article.backlinks IS '链接到本文的其他文章 slug 列表';
COMMENT ON COLUMN kms_article.knowledge_id IS '所属知识库 ID (null=未归类)';
COMMENT ON COLUMN kms_article.category_id IS '所属分类 ID';
COMMENT ON COLUMN kms_article.tags IS '标签列表';
COMMENT ON COLUMN kms_article.status IS '1=发布 0=草稿 -1=归档';
COMMENT ON COLUMN kms_article.is_featured IS '是否精选';
COMMENT ON COLUMN kms_article.view_count IS '浏览次数';
COMMENT ON COLUMN kms_article.version IS '当前版本号';
COMMENT ON COLUMN kms_article.okf_type IS 'OKF type: concept|howto|reference|decision|metric 或自定义（缺省导出为 concept）';
COMMENT ON COLUMN kms_article.resource IS 'OKF resource: 底层资产 URI';
COMMENT ON COLUMN kms_article.sources IS 'OKF §5.1 溯源家族: [{resource(必填), id, title, author, usage_count, last_modified}]';
COMMENT ON COLUMN kms_article.verified IS 'OKF §5.2 验证事件列表: [{by, at}]';
COMMENT ON COLUMN kms_article.stale_after IS 'OKF §5.5 绝对过期时间点';
COMMENT ON COLUMN kms_article.creator_id IS '创建者 ID';
COMMENT ON COLUMN kms_article.updater_id IS '最后编辑者 ID';
COMMENT ON COLUMN kms_article.created_at IS '创建时间';
COMMENT ON COLUMN kms_article.updated_at IS '更新时间';
COMMENT ON COLUMN kms_article.tenant_id IS '租户ID';

-- kms_category

CREATE TABLE kms_category (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	slug VARCHAR(200) NOT NULL, 
	description TEXT, 
	knowledge_id BIGINT, 
	parent_id BIGINT, 
	owl_class_uri VARCHAR(500), 
	sort_order INTEGER DEFAULT '0' NOT NULL, 
	article_count INTEGER DEFAULT '0' NOT NULL, 
	kb_type INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(knowledge_id) REFERENCES kms_knowledge (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_id) REFERENCES kms_category (id) ON DELETE SET NULL
);
COMMENT ON COLUMN kms_category.id IS '主键';
COMMENT ON COLUMN kms_category.name IS '分类名称';
COMMENT ON COLUMN kms_category.slug IS 'URL 友好标识';
COMMENT ON COLUMN kms_category.description IS '分类描述';
COMMENT ON COLUMN kms_category.knowledge_id IS '所属知识库 ID (null=未归类)';
COMMENT ON COLUMN kms_category.parent_id IS '父分类 ID (null=顶级)';
COMMENT ON COLUMN kms_category.owl_class_uri IS '关联的 OWL Class URI（llm-wiki 专用）';
COMMENT ON COLUMN kms_category.sort_order IS '排序权重';
COMMENT ON COLUMN kms_category.article_count IS '文章计数 (冗余)';
COMMENT ON COLUMN kms_category.kb_type IS '冗余的知识库类型（随 knowledge_id 回填；null=未归类）';
COMMENT ON COLUMN kms_category.created_at IS '创建时间';
COMMENT ON COLUMN kms_category.updated_at IS '更新时间';
COMMENT ON COLUMN kms_category.tenant_id IS '租户ID';

-- kms_collection

CREATE TABLE kms_collection (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(128) NOT NULL, 
	dimensions INTEGER NOT NULL, 
	knowledge_id BIGINT, 
	schema_config JSON, 
	retrieval_settings JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(knowledge_id) REFERENCES kms_knowledge (id) ON DELETE SET NULL
);
COMMENT ON COLUMN kms_collection.id IS '主键';
COMMENT ON COLUMN kms_collection.name IS '集合名(逻辑名)';
COMMENT ON COLUMN kms_collection.dimensions IS '向量维度';
COMMENT ON COLUMN kms_collection.knowledge_id IS '所属统一知识库容器（type=2）';
COMMENT ON COLUMN kms_collection.schema_config IS '表格 KB 字段定义';
COMMENT ON COLUMN kms_collection.retrieval_settings IS '检索设置: {embedding_provider,embedding_model,embedding_dimensions,rerank_provider,rerank_model,top_k,score_threshold}';
COMMENT ON COLUMN kms_collection.created_at IS '创建时间';
COMMENT ON COLUMN kms_collection.tenant_id IS '租户ID';

-- kms_connector_instance

CREATE TABLE kms_connector_instance (
	id BIGSERIAL NOT NULL, 
	knowledge_id BIGINT, 
	code VARCHAR(200) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	connector_type VARCHAR(32) NOT NULL, 
	config JSON, 
	sync_enabled BOOLEAN DEFAULT 'false' NOT NULL, 
	sync_interval_min INTEGER DEFAULT '60' NOT NULL, 
	target_collection VARCHAR(128), 
	status VARCHAR(32) DEFAULT 'active' NOT NULL, 
	last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
	error_detail TEXT, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_connector_instance_code UNIQUE (tenant_id, code), 
	FOREIGN KEY(knowledge_id) REFERENCES kms_knowledge (id) ON DELETE SET NULL
);
COMMENT ON COLUMN kms_connector_instance.id IS '主键';
COMMENT ON COLUMN kms_connector_instance.knowledge_id IS '所属统一知识库容器（type=3）';
COMMENT ON COLUMN kms_connector_instance.code IS '实例编码（租户内唯一）';
COMMENT ON COLUMN kms_connector_instance.name IS '实例显示名';
COMMENT ON COLUMN kms_connector_instance.connector_type IS '连接器类型（registry 枚举: http|dingtalk|feishu|wecom）';
COMMENT ON COLUMN kms_connector_instance.config IS '连接参数；敏感字段 Fernet 加密';
COMMENT ON COLUMN kms_connector_instance.sync_enabled IS '是否启用定时同步';
COMMENT ON COLUMN kms_connector_instance.sync_interval_min IS '同步间隔（分钟）';
COMMENT ON COLUMN kms_connector_instance.target_collection IS '落库目标 → kb_collection.name';
COMMENT ON COLUMN kms_connector_instance.status IS 'active|error|disabled';
COMMENT ON COLUMN kms_connector_instance.last_sync_at IS '最近一次同步时间';
COMMENT ON COLUMN kms_connector_instance.error_detail IS '最近一次失败详情';
COMMENT ON COLUMN kms_connector_instance.creator_id IS '创建人';
COMMENT ON COLUMN kms_connector_instance.updater_id IS '更新人';
COMMENT ON COLUMN kms_connector_instance.created_at IS '创建时间';
COMMENT ON COLUMN kms_connector_instance.updated_at IS '更新时间';
COMMENT ON COLUMN kms_connector_instance.tenant_id IS '租户ID';

-- kms_external_kb_endpoint

CREATE TABLE kms_external_kb_endpoint (
	id BIGSERIAL NOT NULL, 
	knowledge_id BIGINT, 
	name VARCHAR(200) NOT NULL, 
	endpoint_url VARCHAR(500) NOT NULL, 
	auth_key VARCHAR(500), 
	index_name VARCHAR(128), 
	metadata_mapping VARCHAR(500), 
	allowed_callers JSONB, 
	status VARCHAR(32) DEFAULT 'active' NOT NULL, 
	error_detail TEXT, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(knowledge_id) REFERENCES kms_knowledge (id) ON DELETE SET NULL
);
COMMENT ON COLUMN kms_external_kb_endpoint.id IS '主键';
COMMENT ON COLUMN kms_external_kb_endpoint.knowledge_id IS '所属统一容器（type=3/proxy）';
COMMENT ON COLUMN kms_external_kb_endpoint.name IS '显示名';
COMMENT ON COLUMN kms_external_kb_endpoint.endpoint_url IS '外部检索 API 地址（https）';
COMMENT ON COLUMN kms_external_kb_endpoint.auth_key IS '鉴权密钥（Fernet 密文）';
COMMENT ON COLUMN kms_external_kb_endpoint.index_name IS '外部索引/集合名';
COMMENT ON COLUMN kms_external_kb_endpoint.metadata_mapping IS '元数据映射说明/JSON 字符串';
COMMENT ON COLUMN kms_external_kb_endpoint.allowed_callers IS '允许调用的 Agent/应用标识列表；null=不限制';
COMMENT ON COLUMN kms_external_kb_endpoint.status IS 'active|error|disabled';
COMMENT ON COLUMN kms_external_kb_endpoint.error_detail IS '最近错误';
COMMENT ON COLUMN kms_external_kb_endpoint.creator_id IS '创建人';
COMMENT ON COLUMN kms_external_kb_endpoint.created_at IS '创建时间';
COMMENT ON COLUMN kms_external_kb_endpoint.updated_at IS '更新时间';
COMMENT ON COLUMN kms_external_kb_endpoint.tenant_id IS '租户ID';

-- kms_segment_asset

CREATE TABLE kms_segment_asset (
	id BIGSERIAL NOT NULL, 
	segment_id BIGINT NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	mime_type VARCHAR(64) NOT NULL, 
	size INTEGER NOT NULL, 
	width INTEGER, 
	height INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(segment_id) REFERENCES kms_segment (id) ON DELETE CASCADE
);
COMMENT ON COLUMN kms_segment_asset.id IS '主键';
COMMENT ON COLUMN kms_segment_asset.segment_id IS '所属切片';
COMMENT ON COLUMN kms_segment_asset.file_path IS '存储路径/对象 URL';
COMMENT ON COLUMN kms_segment_asset.mime_type IS '图片 MIME';
COMMENT ON COLUMN kms_segment_asset.size IS '字节数';
COMMENT ON COLUMN kms_segment_asset.width IS '宽';
COMMENT ON COLUMN kms_segment_asset.height IS '高';
COMMENT ON COLUMN kms_segment_asset.created_at IS '创建时间';
COMMENT ON COLUMN kms_segment_asset.tenant_id IS '租户ID';

-- meta_data_write_request

CREATE TABLE meta_data_write_request (
	id BIGSERIAL NOT NULL, 
	source_id BIGINT NOT NULL, 
	database VARCHAR(128), 
	sql_text TEXT NOT NULL, 
	sql_sha256 VARCHAR(64) NOT NULL, 
	statement_type VARCHAR(32) NOT NULL, 
	token VARCHAR(64), 
	impact_json JSONB, 
	status VARCHAR(32) DEFAULT 'pending' NOT NULL, 
	applicant_id BIGINT, 
	approver_id BIGINT, 
	token_consumed BOOLEAN DEFAULT '0' NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE, 
	executed_at TIMESTAMP WITHOUT TIME ZONE, 
	result_json JSONB, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES meta_data_source (id) ON DELETE CASCADE
);
COMMENT ON COLUMN meta_data_write_request.id IS '主键';
COMMENT ON COLUMN meta_data_write_request.source_id IS '数据源 ID';
COMMENT ON COLUMN meta_data_write_request.database IS '目标库';
COMMENT ON COLUMN meta_data_write_request.sql_text IS '申请时提交的 SQL 原文';
COMMENT ON COLUMN meta_data_write_request.sql_sha256 IS 'SQL 摘要（审批/执行一致性锚点）';
COMMENT ON COLUMN meta_data_write_request.statement_type IS '语句类型: update|delete|insert|ddl';
COMMENT ON COLUMN meta_data_write_request.token IS '一次性执行令牌（approved 时生成）';
COMMENT ON COLUMN meta_data_write_request.impact_json IS 'dry-run 影响预估';
COMMENT ON COLUMN meta_data_write_request.status IS '状态: pending|approved|rejected|executed|expired';
COMMENT ON COLUMN meta_data_write_request.applicant_id IS '申请人';
COMMENT ON COLUMN meta_data_write_request.approver_id IS '批准人';
COMMENT ON COLUMN meta_data_write_request.token_consumed IS '令牌是否已消费（防重放）';
COMMENT ON COLUMN meta_data_write_request.expires_at IS '申请过期时间';
COMMENT ON COLUMN meta_data_write_request.executed_at IS '执行时间';
COMMENT ON COLUMN meta_data_write_request.result_json IS '执行结果（行数、耗时）';
COMMENT ON COLUMN meta_data_write_request.creator_id IS '创建者 ID';
COMMENT ON COLUMN meta_data_write_request.created_at IS '创建时间';
COMMENT ON COLUMN meta_data_write_request.updated_at IS '更新时间';
COMMENT ON COLUMN meta_data_write_request.tenant_id IS '租户ID';

-- meta_relation

CREATE TABLE meta_relation (
	id BIGSERIAL NOT NULL, 
	source_id BIGINT NOT NULL, 
	database VARCHAR(128) NOT NULL, 
	left_table VARCHAR(256) NOT NULL, 
	left_column VARCHAR(256) NOT NULL, 
	right_table VARCHAR(256) NOT NULL, 
	right_column VARCHAR(256) NOT NULL, 
	vote_key FLOAT, 
	vote_name FLOAT, 
	vote_overlap FLOAT, 
	method_votes_json JSONB, 
	confidence FLOAT NOT NULL, 
	status VARCHAR(32) DEFAULT 'suggested' NOT NULL, 
	source VARCHAR(32) DEFAULT 'rule' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES meta_data_source (id) ON DELETE CASCADE
);
COMMENT ON COLUMN meta_relation.id IS '主键';
COMMENT ON COLUMN meta_relation.source_id IS '数据源 ID';
COMMENT ON COLUMN meta_relation.database IS '库/schema';
COMMENT ON COLUMN meta_relation.left_table IS '左表';
COMMENT ON COLUMN meta_relation.left_column IS '左列';
COMMENT ON COLUMN meta_relation.right_table IS '右表';
COMMENT ON COLUMN meta_relation.right_column IS '右列';
COMMENT ON COLUMN meta_relation.vote_key IS '键/外键命名法投票';
COMMENT ON COLUMN meta_relation.vote_name IS '同名属性法投票';
COMMENT ON COLUMN meta_relation.vote_overlap IS '采样重叠率法投票';
COMMENT ON COLUMN meta_relation.method_votes_json IS '各方法依据明细';
COMMENT ON COLUMN meta_relation.confidence IS '综合置信度（取各票最大）';
COMMENT ON COLUMN meta_relation.status IS '评审状态: suggested|accepted|rejected';
COMMENT ON COLUMN meta_relation.source IS '来源: rule';
COMMENT ON COLUMN meta_relation.created_at IS '创建时间';
COMMENT ON COLUMN meta_relation.updated_at IS '更新时间';
COMMENT ON COLUMN meta_relation.tenant_id IS '租户ID';

-- meta_scan_job

CREATE TABLE meta_scan_job (
	id BIGSERIAL NOT NULL, 
	source_id BIGINT NOT NULL, 
	database VARCHAR(128) NOT NULL, 
	job_kind VARCHAR(32) DEFAULT 'scan' NOT NULL, 
	status VARCHAR(32) DEFAULT 'pending' NOT NULL, 
	progress FLOAT DEFAULT '0' NOT NULL, 
	with_profile BOOLEAN DEFAULT '0' NOT NULL, 
	tables_json JSONB, 
	stats_json JSONB, 
	error_detail TEXT, 
	duration_ms INTEGER, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES meta_data_source (id) ON DELETE CASCADE
);
COMMENT ON COLUMN meta_scan_job.id IS '主键';
COMMENT ON COLUMN meta_scan_job.source_id IS '数据源 ID';
COMMENT ON COLUMN meta_scan_job.database IS '扫描的库';
COMMENT ON COLUMN meta_scan_job.job_kind IS '任务类型: scan|profile';
COMMENT ON COLUMN meta_scan_job.status IS '状态: pending|running|succeeded|failed';
COMMENT ON COLUMN meta_scan_job.progress IS '进度 0-100';
COMMENT ON COLUMN meta_scan_job.with_profile IS '是否顺带列画像';
COMMENT ON COLUMN meta_scan_job.tables_json IS '待扫描表清单';
COMMENT ON COLUMN meta_scan_job.stats_json IS '统计（表数/列数/truncated 等）';
COMMENT ON COLUMN meta_scan_job.error_detail IS '失败详情';
COMMENT ON COLUMN meta_scan_job.duration_ms IS '耗时毫秒';
COMMENT ON COLUMN meta_scan_job.started_at IS '开始时间';
COMMENT ON COLUMN meta_scan_job.finished_at IS '结束时间';
COMMENT ON COLUMN meta_scan_job.creator_id IS '创建者 ID';
COMMENT ON COLUMN meta_scan_job.created_at IS '创建时间';
COMMENT ON COLUMN meta_scan_job.tenant_id IS '租户ID';

-- meta_standard_version

CREATE TABLE meta_standard_version (
	id BIGSERIAL NOT NULL, 
	standard_id BIGINT NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot_json JSONB, 
	change_note TEXT, 
	author_user_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_meta_standard_version UNIQUE (standard_id, version), 
	FOREIGN KEY(standard_id) REFERENCES meta_standard (id) ON DELETE CASCADE
);
COMMENT ON COLUMN meta_standard_version.id IS '主键';
COMMENT ON COLUMN meta_standard_version.standard_id IS '标准项 ID';
COMMENT ON COLUMN meta_standard_version.version IS '版本号（标准项内自增）';
COMMENT ON COLUMN meta_standard_version.snapshot_json IS '版本快照（字段全量冻结）';
COMMENT ON COLUMN meta_standard_version.change_note IS '变更说明';
COMMENT ON COLUMN meta_standard_version.author_user_id IS '操作人';
COMMENT ON COLUMN meta_standard_version.created_at IS '创建时间';
COMMENT ON COLUMN meta_standard_version.tenant_id IS '租户ID';

-- meta_table

CREATE TABLE meta_table (
	id BIGSERIAL NOT NULL, 
	source_id BIGINT NOT NULL, 
	database VARCHAR(128) NOT NULL, 
	table_name VARCHAR(256) NOT NULL, 
	table_type VARCHAR(32), 
	table_comment TEXT, 
	row_count BIGINT, 
	engine VARCHAR(64), 
	column_count INTEGER, 
	biz_name VARCHAR(200), 
	biz_description TEXT, 
	domain VARCHAR(64), 
	profiled_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_meta_table UNIQUE (source_id, database, table_name), 
	FOREIGN KEY(source_id) REFERENCES meta_data_source (id) ON DELETE CASCADE
);
COMMENT ON COLUMN meta_table.id IS '主键';
COMMENT ON COLUMN meta_table.source_id IS '数据源 ID';
COMMENT ON COLUMN meta_table.database IS '库名';
COMMENT ON COLUMN meta_table.table_name IS '表名';
COMMENT ON COLUMN meta_table.table_type IS '表类型（BASE TABLE/VIEW 等）';
COMMENT ON COLUMN meta_table.table_comment IS '表注释';
COMMENT ON COLUMN meta_table.row_count IS '行数（近似）';
COMMENT ON COLUMN meta_table.engine IS '存储引擎';
COMMENT ON COLUMN meta_table.column_count IS '列数';
COMMENT ON COLUMN meta_table.biz_name IS '业务名称（人工/规则补充）';
COMMENT ON COLUMN meta_table.biz_description IS '业务描述';
COMMENT ON COLUMN meta_table.domain IS '数仓分层/主题域（ods/dwd/...）';
COMMENT ON COLUMN meta_table.profiled_at IS '最近画像时间';
COMMENT ON COLUMN meta_table.created_at IS '创建时间';
COMMENT ON COLUMN meta_table.updated_at IS '更新时间';
COMMENT ON COLUMN meta_table.tenant_id IS '租户ID';

-- ontology_annotation

CREATE TABLE ontology_annotation (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	target_type VARCHAR(32) DEFAULT 'article' NOT NULL, 
	target_id VARCHAR(500) NOT NULL, 
	class_uris JSONB, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_annotation UNIQUE (ontology_id, target_type, target_id), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_annotation.id IS '主键';
COMMENT ON COLUMN ontology_annotation.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_annotation.target_type IS '目标类型: article|segment|table|column';
COMMENT ON COLUMN ontology_annotation.target_id IS '目标对象 ID（字符串化）';
COMMENT ON COLUMN ontology_annotation.class_uris IS '关联的本体类 URI 列表';
COMMENT ON COLUMN ontology_annotation.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_annotation.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_annotation.created_at IS '创建时间';
COMMENT ON COLUMN ontology_annotation.updated_at IS '更新时间';
COMMENT ON COLUMN ontology_annotation.tenant_id IS '租户ID';

-- ontology_class

CREATE TABLE ontology_class (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	uri VARCHAR(500) NOT NULL, 
	label VARCHAR(500), 
	comment TEXT, 
	parent_uris JSONB, 
	status VARCHAR(32) DEFAULT 'active' NOT NULL, 
	display_order INTEGER DEFAULT '0' NOT NULL, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_class UNIQUE (ontology_id, uri), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_class.id IS '主键';
COMMENT ON COLUMN ontology_class.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_class.uri IS '类 URI（500×3 字节 < PG btree 条目上限 2704，见迁移 005）';
COMMENT ON COLUMN ontology_class.label IS '中文标签';
COMMENT ON COLUMN ontology_class.comment IS '类描述';
COMMENT ON COLUMN ontology_class.parent_uris IS '父类 URI 列表';
COMMENT ON COLUMN ontology_class.status IS '状态: active|deprecated';
COMMENT ON COLUMN ontology_class.display_order IS '展示顺序';
COMMENT ON COLUMN ontology_class.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_class.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_class.created_at IS '创建时间';
COMMENT ON COLUMN ontology_class.updated_at IS '更新时间';
COMMENT ON COLUMN ontology_class.tenant_id IS '租户ID';

-- ontology_cq

CREATE TABLE ontology_cq (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	question TEXT NOT NULL, 
	answer_hint TEXT, 
	status VARCHAR(32) DEFAULT 'active' NOT NULL, 
	linked_object_types JSONB, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_cq.id IS '主键';
COMMENT ON COLUMN ontology_cq.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_cq.question IS '能力问题（自然语言，如「哪些合同将在 30 天内到期？」）';
COMMENT ON COLUMN ontology_cq.answer_hint IS '回答提示（该问题应由哪些数据/路径回答）';
COMMENT ON COLUMN ontology_cq.status IS '状态: active|archived';
COMMENT ON COLUMN ontology_cq.linked_object_types IS '关联的对象类型 code 列表';
COMMENT ON COLUMN ontology_cq.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_cq.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_cq.created_at IS '创建时间';
COMMENT ON COLUMN ontology_cq.updated_at IS '更新时间';

-- ontology_object_type

CREATE TABLE ontology_object_type (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	code VARCHAR(128) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	parent_id BIGINT, 
	status VARCHAR(32) DEFAULT 'suggested' NOT NULL, 
	source VARCHAR(32) DEFAULT 'human' NOT NULL, 
	confidence FLOAT, 
	evidence_json JSONB, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_object_type UNIQUE (ontology_id, code), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_id) REFERENCES ontology_object_type (id) ON DELETE SET NULL
);
COMMENT ON COLUMN ontology_object_type.id IS '主键';
COMMENT ON COLUMN ontology_object_type.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_object_type.code IS '对象类型编码（本体内唯一，如 customer）';
COMMENT ON COLUMN ontology_object_type.name IS '对象类型名称（如 客户）';
COMMENT ON COLUMN ontology_object_type.description IS '业务描述';
COMMENT ON COLUMN ontology_object_type.parent_id IS '父对象类型 ID（自引用，构成概念层级）';
COMMENT ON COLUMN ontology_object_type.status IS '评审状态: suggested|accepted|rejected';
COMMENT ON COLUMN ontology_object_type.source IS '来源: rule|human|llm';
COMMENT ON COLUMN ontology_object_type.confidence IS '置信度 0~1（规则/LLM 通道产生，人工建模为空）';
COMMENT ON COLUMN ontology_object_type.evidence_json IS '来源证据（如 P2 表名、列重叠率等，由生成方写入）';
COMMENT ON COLUMN ontology_object_type.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_object_type.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_object_type.created_at IS '创建时间';
COMMENT ON COLUMN ontology_object_type.updated_at IS '更新时间';

-- ontology_version

CREATE TABLE ontology_version (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	version VARCHAR(32) NOT NULL, 
	snapshot_json JSONB NOT NULL, 
	change_note TEXT, 
	author_user_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_version UNIQUE (ontology_id, version), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_version.id IS '主键';
COMMENT ON COLUMN ontology_version.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_version.version IS '版本号（如 v1.0.0 或 ISO 时间戳，由 Task 6 定义）';
COMMENT ON COLUMN ontology_version.snapshot_json IS '快照内容（对象类型/属性/关系/映射/CQ 的冻结视图）';
COMMENT ON COLUMN ontology_version.change_note IS '变更说明';
COMMENT ON COLUMN ontology_version.author_user_id IS '创建快照的用户 ID';
COMMENT ON COLUMN ontology_version.created_at IS '创建时间';

-- sys_role_menu

CREATE TABLE sys_role_menu (
	id BIGSERIAL NOT NULL, 
	role_id BIGINT NOT NULL, 
	menu_id BIGINT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES sys_role (role_id), 
	FOREIGN KEY(menu_id) REFERENCES sys_menu (id) ON DELETE CASCADE
);

-- sys_tenant

CREATE TABLE sys_tenant (
	tenant_id BIGSERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	contact_name VARCHAR(50), 
	contact_mobile VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	package_id BIGINT, 
	expire_time TIMESTAMP WITHOUT TIME ZONE, 
	account_count INTEGER, 
	websites JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (tenant_id), 
	UNIQUE (name), 
	FOREIGN KEY(package_id) REFERENCES sys_tenant_package (package_id)
);
COMMENT ON COLUMN sys_tenant.name IS '租户名称';
COMMENT ON COLUMN sys_tenant.contact_name IS '联系人';
COMMENT ON COLUMN sys_tenant.contact_mobile IS '联系电话';
COMMENT ON COLUMN sys_tenant.status IS '状态(active/disabled)';
COMMENT ON COLUMN sys_tenant.package_id IS '租户套餐ID';
COMMENT ON COLUMN sys_tenant.expire_time IS '过期时间';
COMMENT ON COLUMN sys_tenant.account_count IS '账号额度';
COMMENT ON COLUMN sys_tenant.websites IS '绑定域名列表';

-- sys_user_role

CREATE TABLE sys_user_role (
	id BIGSERIAL NOT NULL, 
	user_id BIGINT NOT NULL, 
	role_id BIGINT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES sys_user (user_id), 
	FOREIGN KEY(role_id) REFERENCES sys_role (role_id)
);
COMMENT ON COLUMN sys_user_role.tenant_id IS '租户ID';

-- kms_article_version

CREATE TABLE kms_article_version (
	id BIGSERIAL NOT NULL, 
	article_id BIGINT NOT NULL, 
	version INTEGER NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	content TEXT, 
	slug VARCHAR(200), 
	change_note VARCHAR(500), 
	operation_type VARCHAR(32), 
	summary VARCHAR(1000), 
	owl_class_uris JSONB, 
	editor_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(article_id) REFERENCES kms_article (id) ON DELETE CASCADE
);
COMMENT ON COLUMN kms_article_version.id IS '主键';
COMMENT ON COLUMN kms_article_version.article_id IS '关联文章 ID';
COMMENT ON COLUMN kms_article_version.version IS '版本号 (从 1 递增)';
COMMENT ON COLUMN kms_article_version.title IS '版本标题快照';
COMMENT ON COLUMN kms_article_version.content IS '版本正文快照 (Markdown)';
COMMENT ON COLUMN kms_article_version.slug IS '版本 slug 快照';
COMMENT ON COLUMN kms_article_version.change_note IS '编辑说明';
COMMENT ON COLUMN kms_article_version.operation_type IS '操作类型: create|edit|rollback';
COMMENT ON COLUMN kms_article_version.summary IS '版本摘要快照';
COMMENT ON COLUMN kms_article_version.owl_class_uris IS '版本 OWL 类 URI 快照';
COMMENT ON COLUMN kms_article_version.editor_id IS '编辑者 ID';
COMMENT ON COLUMN kms_article_version.created_at IS '版本创建时间';
COMMENT ON COLUMN kms_article_version.tenant_id IS '租户ID';

-- kms_connector_sync_log

CREATE TABLE kms_connector_sync_log (
	id BIGSERIAL NOT NULL, 
	instance_id BIGINT NOT NULL, 
	connector_type VARCHAR(32) NOT NULL, 
	status VARCHAR(32) DEFAULT 'pending' NOT NULL, 
	added INTEGER DEFAULT '0' NOT NULL, 
	updated INTEGER DEFAULT '0' NOT NULL, 
	deleted INTEGER DEFAULT '0' NOT NULL, 
	cursor_value VARCHAR(255), 
	duration_ms INTEGER, 
	error_detail TEXT, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(instance_id) REFERENCES kms_connector_instance (id) ON DELETE CASCADE
);
COMMENT ON COLUMN kms_connector_sync_log.id IS '主键';
COMMENT ON COLUMN kms_connector_sync_log.instance_id IS '所属实例';
COMMENT ON COLUMN kms_connector_sync_log.connector_type IS '连接器类型快照';
COMMENT ON COLUMN kms_connector_sync_log.status IS 'pending|running|success|failed';
COMMENT ON COLUMN kms_connector_sync_log.added IS '新增条数';
COMMENT ON COLUMN kms_connector_sync_log.updated IS '更新条数';
COMMENT ON COLUMN kms_connector_sync_log.deleted IS '删除条数';
COMMENT ON COLUMN kms_connector_sync_log.cursor_value IS '本次同步后的增量游标';
COMMENT ON COLUMN kms_connector_sync_log.duration_ms IS '耗时（毫秒）';
COMMENT ON COLUMN kms_connector_sync_log.error_detail IS '失败详情';
COMMENT ON COLUMN kms_connector_sync_log.started_at IS '开始时间';
COMMENT ON COLUMN kms_connector_sync_log.finished_at IS '结束时间';
COMMENT ON COLUMN kms_connector_sync_log.creator_id IS '触发人';
COMMENT ON COLUMN kms_connector_sync_log.created_at IS '创建时间';
COMMENT ON COLUMN kms_connector_sync_log.tenant_id IS '租户ID';

-- meta_column

CREATE TABLE meta_column (
	id BIGSERIAL NOT NULL, 
	table_id BIGINT NOT NULL, 
	column_name VARCHAR(256) NOT NULL, 
	ordinal INTEGER DEFAULT '0' NOT NULL, 
	data_type VARCHAR(64), 
	column_type VARCHAR(128), 
	nullable BOOLEAN DEFAULT '1' NOT NULL, 
	column_key VARCHAR(16), 
	column_default VARCHAR(256), 
	extra VARCHAR(64), 
	column_comment TEXT, 
	biz_name VARCHAR(200), 
	biz_description TEXT, 
	semantic_type VARCHAR(64), 
	pii_level VARCHAR(8), 
	profile_json JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_meta_column UNIQUE (table_id, column_name), 
	FOREIGN KEY(table_id) REFERENCES meta_table (id) ON DELETE CASCADE
);
COMMENT ON COLUMN meta_column.id IS '主键';
COMMENT ON COLUMN meta_column.table_id IS '所属表 ID';
COMMENT ON COLUMN meta_column.column_name IS '列名';
COMMENT ON COLUMN meta_column.ordinal IS '列序号';
COMMENT ON COLUMN meta_column.data_type IS '数据类型（归一化）';
COMMENT ON COLUMN meta_column.column_type IS '完整列类型定义';
COMMENT ON COLUMN meta_column.nullable IS '是否可空';
COMMENT ON COLUMN meta_column.column_key IS '键类型（PRI/UNI/MUL）';
COMMENT ON COLUMN meta_column.column_default IS '默认值';
COMMENT ON COLUMN meta_column.extra IS '额外信息（auto_increment 等）';
COMMENT ON COLUMN meta_column.column_comment IS '列注释';
COMMENT ON COLUMN meta_column.biz_name IS '业务名称';
COMMENT ON COLUMN meta_column.biz_description IS '业务描述';
COMMENT ON COLUMN meta_column.semantic_type IS '语义类型（手机号/金额/ID 等）';
COMMENT ON COLUMN meta_column.pii_level IS 'PII 等级: L0|L1|L2|L3';
COMMENT ON COLUMN meta_column.profile_json IS '画像结果（不存样本数据）';
COMMENT ON COLUMN meta_column.created_at IS '创建时间';
COMMENT ON COLUMN meta_column.updated_at IS '更新时间';
COMMENT ON COLUMN meta_column.tenant_id IS '租户ID';

-- ontology_link_type

CREATE TABLE ontology_link_type (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	code VARCHAR(128) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	source_type_id BIGINT NOT NULL, 
	target_type_id BIGINT NOT NULL, 
	cardinality VARCHAR(32) DEFAULT 'N:M' NOT NULL, 
	status VARCHAR(32) DEFAULT 'suggested' NOT NULL, 
	source VARCHAR(32) DEFAULT 'human' NOT NULL, 
	confidence FLOAT, 
	evidence_json JSONB, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_link_type UNIQUE (ontology_id, code), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE, 
	FOREIGN KEY(source_type_id) REFERENCES ontology_object_type (id) ON DELETE CASCADE, 
	FOREIGN KEY(target_type_id) REFERENCES ontology_object_type (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_link_type.id IS '主键';
COMMENT ON COLUMN ontology_link_type.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_link_type.code IS '关系类型编码（本体内唯一，如 signs）';
COMMENT ON COLUMN ontology_link_type.name IS '关系类型名称（如 签订）';
COMMENT ON COLUMN ontology_link_type.source_type_id IS '起始对象类型 ID';
COMMENT ON COLUMN ontology_link_type.target_type_id IS '目标对象类型 ID';
COMMENT ON COLUMN ontology_link_type.cardinality IS '基数: 1:1|1:N|N:M';
COMMENT ON COLUMN ontology_link_type.status IS '评审状态: suggested|accepted|rejected';
COMMENT ON COLUMN ontology_link_type.source IS '来源: rule|human|llm';
COMMENT ON COLUMN ontology_link_type.confidence IS '置信度 0~1';
COMMENT ON COLUMN ontology_link_type.evidence_json IS '来源证据（如列对重叠率）';
COMMENT ON COLUMN ontology_link_type.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_link_type.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_link_type.created_at IS '创建时间';
COMMENT ON COLUMN ontology_link_type.updated_at IS '更新时间';

-- ontology_mapping

CREATE TABLE ontology_mapping (
	id BIGSERIAL NOT NULL, 
	ontology_id BIGINT NOT NULL, 
	object_type_id BIGINT NOT NULL, 
	target_type VARCHAR(32) DEFAULT 'table' NOT NULL, 
	source_id VARCHAR(128), 
	database VARCHAR(128), 
	table_name VARCHAR(200) NOT NULL, 
	column_name VARCHAR(200), 
	status VARCHAR(32) DEFAULT 'suggested' NOT NULL, 
	source VARCHAR(32) DEFAULT 'human' NOT NULL, 
	confidence FLOAT, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ontology_id) REFERENCES ontology (id) ON DELETE CASCADE, 
	FOREIGN KEY(object_type_id) REFERENCES ontology_object_type (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_mapping.id IS '主键';
COMMENT ON COLUMN ontology_mapping.ontology_id IS '所属本体 ID';
COMMENT ON COLUMN ontology_mapping.object_type_id IS '映射到的对象类型 ID';
COMMENT ON COLUMN ontology_mapping.target_type IS '映射目标类型: table|column';
COMMENT ON COLUMN ontology_mapping.source_id IS 'P2 元数据对象 ID（字符串化）';
COMMENT ON COLUMN ontology_mapping.database IS '物理库名';
COMMENT ON COLUMN ontology_mapping.table_name IS '物理表名';
COMMENT ON COLUMN ontology_mapping.column_name IS '物理列名（target_type=column 时必填）';
COMMENT ON COLUMN ontology_mapping.status IS '评审状态: suggested|accepted|rejected';
COMMENT ON COLUMN ontology_mapping.source IS '来源: rule|human|llm';
COMMENT ON COLUMN ontology_mapping.confidence IS '置信度 0~1';
COMMENT ON COLUMN ontology_mapping.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_mapping.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_mapping.created_at IS '创建时间';
COMMENT ON COLUMN ontology_mapping.updated_at IS '更新时间';

-- ontology_property

CREATE TABLE ontology_property (
	id BIGSERIAL NOT NULL, 
	object_type_id BIGINT NOT NULL, 
	code VARCHAR(128) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	data_type VARCHAR(64) DEFAULT 'string' NOT NULL, 
	required BOOLEAN DEFAULT 'false' NOT NULL, 
	semantic_type VARCHAR(128), 
	status VARCHAR(32) DEFAULT 'suggested' NOT NULL, 
	source VARCHAR(32) DEFAULT 'human' NOT NULL, 
	confidence FLOAT, 
	creator_id BIGINT, 
	updater_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ontology_property UNIQUE (object_type_id, code), 
	FOREIGN KEY(object_type_id) REFERENCES ontology_object_type (id) ON DELETE CASCADE
);
COMMENT ON COLUMN ontology_property.id IS '主键';
COMMENT ON COLUMN ontology_property.object_type_id IS '所属对象类型 ID';
COMMENT ON COLUMN ontology_property.code IS '属性编码（对象类型内唯一，如 customer_name）';
COMMENT ON COLUMN ontology_property.name IS '属性名称（如 客户名称）';
COMMENT ON COLUMN ontology_property.data_type IS '数据类型: string|int|decimal|date|datetime|boolean 等';
COMMENT ON COLUMN ontology_property.required IS '是否必填';
COMMENT ON COLUMN ontology_property.semantic_type IS '语义类型（如 手机号 / 证件号，供检索与校验使用）';
COMMENT ON COLUMN ontology_property.status IS '评审状态: suggested|accepted|rejected';
COMMENT ON COLUMN ontology_property.source IS '来源: rule|human|llm';
COMMENT ON COLUMN ontology_property.confidence IS '置信度 0~1';
COMMENT ON COLUMN ontology_property.creator_id IS '创建者 ID';
COMMENT ON COLUMN ontology_property.updater_id IS '最后更新者 ID';
COMMENT ON COLUMN ontology_property.created_at IS '创建时间';
COMMENT ON COLUMN ontology_property.updated_at IS '更新时间';

-- meta_column_standard

CREATE TABLE meta_column_standard (
	id BIGSERIAL NOT NULL, 
	column_id BIGINT NOT NULL, 
	standard_id BIGINT NOT NULL, 
	standard_version INTEGER, 
	security_level_override VARCHAR(8), 
	status VARCHAR(32) DEFAULT 'suggested' NOT NULL, 
	source VARCHAR(32) DEFAULT 'human' NOT NULL, 
	confidence FLOAT, 
	evidence_json JSONB, 
	reviewed_by BIGINT, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	creator_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	tenant_id BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_meta_column_standard_column UNIQUE (column_id), 
	FOREIGN KEY(column_id) REFERENCES meta_column (id) ON DELETE CASCADE, 
	FOREIGN KEY(standard_id) REFERENCES meta_standard (id) ON DELETE RESTRICT
);
COMMENT ON COLUMN meta_column_standard.id IS '主键';
COMMENT ON COLUMN meta_column_standard.column_id IS '列 ID（字段侧 1:1 唯一）';
COMMENT ON COLUMN meta_column_standard.standard_id IS '标准项 ID（RESTRICT：有绑定的标准不可删）';
COMMENT ON COLUMN meta_column_standard.standard_version IS '绑定时标准版本';
COMMENT ON COLUMN meta_column_standard.security_level_override IS '安全等级覆盖';
COMMENT ON COLUMN meta_column_standard.status IS '评审状态: suggested|accepted|rejected';
COMMENT ON COLUMN meta_column_standard.source IS '来源: rule|llm|human';
COMMENT ON COLUMN meta_column_standard.confidence IS '置信度（rule 通道产出）';
COMMENT ON COLUMN meta_column_standard.evidence_json IS '判定依据（命中规则等）';
COMMENT ON COLUMN meta_column_standard.reviewed_by IS '评审人';
COMMENT ON COLUMN meta_column_standard.reviewed_at IS '评审时间';
COMMENT ON COLUMN meta_column_standard.creator_id IS '创建者 ID';
COMMENT ON COLUMN meta_column_standard.created_at IS '创建时间';
COMMENT ON COLUMN meta_column_standard.updated_at IS '更新时间';
COMMENT ON COLUMN meta_column_standard.tenant_id IS '租户ID';

-- ── 索引定义 ───────────────────────────────────────────

-- index ix_agent_async_task_task_no on agent_async_task
CREATE UNIQUE INDEX ix_agent_async_task_task_no ON agent_async_task (task_no);

-- index ix_agent_async_task_execution_id on agent_async_task
CREATE INDEX ix_agent_async_task_execution_id ON agent_async_task (execution_id);

-- index ix_agent_async_task_tenant_id on agent_async_task
CREATE INDEX ix_agent_async_task_tenant_id ON agent_async_task (tenant_id);

-- index ix_async_task_status_user on agent_async_task
CREATE INDEX ix_async_task_status_user ON agent_async_task (status, user_id);

-- index ix_agent_async_task_session_id on agent_async_task
CREATE INDEX ix_agent_async_task_session_id ON agent_async_task (session_id);

-- index ix_agent_async_task_user_id on agent_async_task
CREATE INDEX ix_agent_async_task_user_id ON agent_async_task (user_id);

-- index ix_agent_config_agent_code on agent_config
CREATE UNIQUE INDEX ix_agent_config_agent_code ON agent_config (agent_code);

-- index idx_agent_config_mode on agent_config
CREATE INDEX idx_agent_config_mode ON agent_config (execution_mode);

-- index idx_agent_config_strategy on agent_config
CREATE INDEX idx_agent_config_strategy ON agent_config (strategy_code);

-- index idx_agent_config_active on agent_config
CREATE INDEX idx_agent_config_active ON agent_config (is_active);

-- index idx_agent_config_workflow on agent_config
CREATE INDEX idx_agent_config_workflow ON agent_config (workflow_id);

-- index ix_agent_config_strategy_code on agent_config
CREATE INDEX ix_agent_config_strategy_code ON agent_config (strategy_code);

-- index idx_agent_config_category on agent_config
CREATE INDEX idx_agent_config_category ON agent_config (category);

-- index ix_agent_config_tenant_id on agent_config
CREATE INDEX ix_agent_config_tenant_id ON agent_config (tenant_id);

-- index idx_execution_target on agent_execution
CREATE INDEX idx_execution_target ON agent_execution (target_id);

-- index idx_execution_status on agent_execution
CREATE INDEX idx_execution_status ON agent_execution (status);

-- index idx_execution_trace on agent_execution
CREATE INDEX idx_execution_trace ON agent_execution (trace_id);

-- index ix_agent_execution_target_id on agent_execution
CREATE INDEX ix_agent_execution_target_id ON agent_execution (target_id);

-- index ix_agent_execution_session_id on agent_execution
CREATE INDEX ix_agent_execution_session_id ON agent_execution (session_id);

-- index ix_agent_execution_user_id on agent_execution
CREATE INDEX ix_agent_execution_user_id ON agent_execution (user_id);

-- index ix_agent_execution_tenant_id on agent_execution
CREATE INDEX ix_agent_execution_tenant_id ON agent_execution (tenant_id);

-- index ix_agent_execution_execution_id on agent_execution
CREATE UNIQUE INDEX ix_agent_execution_execution_id ON agent_execution (execution_id);

-- index ix_agent_execution_trace_id on agent_execution
CREATE INDEX ix_agent_execution_trace_id ON agent_execution (trace_id);

-- index ix_agent_execution_event_tenant_id on agent_execution_event
CREATE INDEX ix_agent_execution_event_tenant_id ON agent_execution_event (tenant_id);

-- index idx_event_type on agent_execution_event
CREATE INDEX idx_event_type ON agent_execution_event (event_type);

-- index idx_event_trace on agent_execution_event
CREATE INDEX idx_event_trace ON agent_execution_event (trace_id);

-- index idx_event_category_level on agent_execution_event
CREATE INDEX idx_event_category_level ON agent_execution_event (category, level);

-- index ix_agent_execution_event_execution_id on agent_execution_event
CREATE INDEX ix_agent_execution_event_execution_id ON agent_execution_event (execution_id);

-- index idx_event_reply on agent_execution_event
CREATE INDEX idx_event_reply ON agent_execution_event (execution_id, reply_id);

-- index idx_event_execution_seq on agent_execution_event
CREATE INDEX idx_event_execution_seq ON agent_execution_event (execution_id, sequence);

-- index ix_agent_execution_event_trace_id on agent_execution_event
CREATE INDEX ix_agent_execution_event_trace_id ON agent_execution_event (trace_id);

-- index idx_hitl_status on agent_hitl_pause
CREATE INDEX idx_hitl_status ON agent_hitl_pause (status);

-- index idx_hitl_execution on agent_hitl_pause
CREATE INDEX idx_hitl_execution ON agent_hitl_pause (execution_id);

-- index ix_agent_hitl_pause_tenant_id on agent_hitl_pause
CREATE INDEX ix_agent_hitl_pause_tenant_id ON agent_hitl_pause (tenant_id);

-- index ix_agent_scheduled_task_tenant_id on agent_scheduled_task
CREATE INDEX ix_agent_scheduled_task_tenant_id ON agent_scheduled_task (tenant_id);

-- index ix_agent_scheduled_task_user_id on agent_scheduled_task
CREATE INDEX ix_agent_scheduled_task_user_id ON agent_scheduled_task (user_id);

-- index ix_agent_sched_user_status on agent_scheduled_task
CREATE INDEX ix_agent_sched_user_status ON agent_scheduled_task (user_id, status);

-- index ix_agent_team_tenant_id on agent_team
CREATE INDEX ix_agent_team_tenant_id ON agent_team (tenant_id);

-- index idx_agent_team_active on agent_team
CREATE INDEX idx_agent_team_active ON agent_team (is_active);

-- index ix_agent_team_team_code on agent_team
CREATE UNIQUE INDEX ix_agent_team_team_code ON agent_team (team_code);

-- index idx_agent_team_workspace on agent_team
CREATE INDEX idx_agent_team_workspace ON agent_team (workspace_id);

-- index idx_agent_team_category on agent_team
CREATE INDEX idx_agent_team_category ON agent_team (category);

-- index idx_team_edge_to on agent_team_edge
CREATE INDEX idx_team_edge_to ON agent_team_edge (team_id, to_node_key);

-- index ix_agent_team_edge_team_id on agent_team_edge
CREATE INDEX ix_agent_team_edge_team_id ON agent_team_edge (team_id);

-- index idx_team_edge_team on agent_team_edge
CREATE INDEX idx_team_edge_team ON agent_team_edge (team_id);

-- index ix_agent_team_edge_tenant_id on agent_team_edge
CREATE INDEX ix_agent_team_edge_tenant_id ON agent_team_edge (tenant_id);

-- index idx_team_intervention_run on agent_team_intervention
CREATE INDEX idx_team_intervention_run ON agent_team_intervention (run_id, status);

-- index ix_agent_team_intervention_run_id on agent_team_intervention
CREATE INDEX ix_agent_team_intervention_run_id ON agent_team_intervention (run_id);

-- index idx_team_intervention_created on agent_team_intervention
CREATE INDEX idx_team_intervention_created ON agent_team_intervention (created_at);

-- index ix_agent_team_intervention_tenant_id on agent_team_intervention
CREATE INDEX ix_agent_team_intervention_tenant_id ON agent_team_intervention (tenant_id);

-- index ix_agent_team_member_team_id on agent_team_member
CREATE INDEX ix_agent_team_member_team_id ON agent_team_member (team_id);

-- index idx_team_member_team on agent_team_member
CREATE INDEX idx_team_member_team ON agent_team_member (team_id);

-- index ix_agent_team_member_tenant_id on agent_team_member
CREATE INDEX ix_agent_team_member_tenant_id ON agent_team_member (tenant_id);

-- index ix_agent_team_member_agent_config_id on agent_team_member
CREATE INDEX ix_agent_team_member_agent_config_id ON agent_team_member (agent_config_id);

-- index idx_team_member_agent on agent_team_member
CREATE INDEX idx_team_member_agent ON agent_team_member (agent_config_id);

-- index ix_agent_team_run_parent_run_id on agent_team_run
CREATE INDEX ix_agent_team_run_parent_run_id ON agent_team_run (parent_run_id);

-- index idx_team_run_status on agent_team_run
CREATE INDEX idx_team_run_status ON agent_team_run (status);

-- index ix_agent_team_run_team_id on agent_team_run
CREATE INDEX ix_agent_team_run_team_id ON agent_team_run (team_id);

-- index idx_team_run_team_created on agent_team_run
CREATE INDEX idx_team_run_team_created ON agent_team_run (team_id, created_at);

-- index ix_agent_team_run_workspace_id on agent_team_run
CREATE INDEX ix_agent_team_run_workspace_id ON agent_team_run (workspace_id);

-- index ix_agent_team_run_conversation_id on agent_team_run
CREATE INDEX ix_agent_team_run_conversation_id ON agent_team_run (conversation_id);

-- index idx_team_run_workspace on agent_team_run
CREATE INDEX idx_team_run_workspace ON agent_team_run (workspace_id);

-- index idx_team_run_conversation on agent_team_run
CREATE INDEX idx_team_run_conversation ON agent_team_run (conversation_id);

-- index ix_agent_team_run_run_id on agent_team_run
CREATE UNIQUE INDEX ix_agent_team_run_run_id ON agent_team_run (run_id);

-- index ix_agent_team_run_tenant_id on agent_team_run
CREATE INDEX ix_agent_team_run_tenant_id ON agent_team_run (tenant_id);

-- index ix_agent_team_run_step_run_id on agent_team_run_step
CREATE INDEX ix_agent_team_run_step_run_id ON agent_team_run_step (run_id);

-- index idx_team_step_run_seq on agent_team_run_step
CREATE INDEX idx_team_step_run_seq ON agent_team_run_step (run_id, seq);

-- index ix_agent_team_run_step_tenant_id on agent_team_run_step
CREATE INDEX ix_agent_team_run_step_tenant_id ON agent_team_run_step (tenant_id);

-- index idx_team_step_run_node on agent_team_run_step
CREATE INDEX idx_team_step_run_node ON agent_team_run_step (run_id, node_key);

-- index ix_agent_trace_tenant_id on agent_trace
CREATE INDEX ix_agent_trace_tenant_id ON agent_trace (tenant_id);

-- index ix_agent_trace_agent_config_id on agent_trace
CREATE INDEX ix_agent_trace_agent_config_id ON agent_trace (agent_config_id);

-- index ix_agent_trace_trace_id on agent_trace
CREATE INDEX ix_agent_trace_trace_id ON agent_trace (trace_id);

-- index ix_agent_trace_session_id on agent_trace
CREATE INDEX ix_agent_trace_session_id ON agent_trace (session_id);

-- index ix_agent_trace_agent_id on agent_trace
CREATE INDEX ix_agent_trace_agent_id ON agent_trace (agent_id);

-- index ix_agent_trace_user_id on agent_trace
CREATE INDEX ix_agent_trace_user_id ON agent_trace (user_id);

-- index ix_agent_trace_team_config_id on agent_trace
CREATE INDEX ix_agent_trace_team_config_id ON agent_trace (team_config_id);

-- index ix_ai_agent_config_agent_id on ai_agent_config
CREATE UNIQUE INDEX ix_ai_agent_config_agent_id ON ai_agent_config (agent_id);

-- index ix_ai_api_key_platform on ai_api_key
CREATE INDEX ix_ai_api_key_platform ON ai_api_key (platform);

-- index ix_ai_api_key_tenant_id on ai_api_key
CREATE INDEX ix_ai_api_key_tenant_id ON ai_api_key (tenant_id);

-- index ix_ai_chat_session_agent_id on ai_chat_session
CREATE INDEX ix_ai_chat_session_agent_id ON ai_chat_session (agent_id);

-- index ix_ai_chat_session_user_id on ai_chat_session
CREATE INDEX ix_ai_chat_session_user_id ON ai_chat_session (user_id);

-- index ix_ai_chat_session_tenant_id on ai_chat_session
CREATE INDEX ix_ai_chat_session_tenant_id ON ai_chat_session (tenant_id);

-- index uk_ai_context_storage_tenant_session_mode_key on ai_context_storage
CREATE UNIQUE INDEX uk_ai_context_storage_tenant_session_mode_key ON ai_context_storage (tenant_id, session_id, mode, context_key);

-- index ix_ai_context_storage_cross_mode on ai_context_storage
CREATE INDEX ix_ai_context_storage_cross_mode ON ai_context_storage (tenant_id, source_mode, is_cross_mode_accessible);

-- index ix_ai_context_storage_tenant_id on ai_context_storage
CREATE INDEX ix_ai_context_storage_tenant_id ON ai_context_storage (tenant_id);

-- index ix_ai_context_storage_tenant_mode on ai_context_storage
CREATE INDEX ix_ai_context_storage_tenant_mode ON ai_context_storage (tenant_id, mode);

-- index ix_ai_context_storage_user_mode on ai_context_storage
CREATE INDEX ix_ai_context_storage_user_mode ON ai_context_storage (tenant_id, user_id, mode);

-- index ix_ai_context_storage_last_access on ai_context_storage
CREATE INDEX ix_ai_context_storage_last_access ON ai_context_storage (last_accessed);

-- index ix_ai_context_storage_expires on ai_context_storage
CREATE INDEX ix_ai_context_storage_expires ON ai_context_storage (expires_at) WHERE expires_at IS NOT NULL;

-- index ix_ai_context_storage_source_mode on ai_context_storage
CREATE INDEX ix_ai_context_storage_source_mode ON ai_context_storage (tenant_id, session_id, source_mode);

-- index ix_ai_mcp_api_key_tenant_id on ai_mcp_api_key
CREATE INDEX ix_ai_mcp_api_key_tenant_id ON ai_mcp_api_key (tenant_id);

-- index idx_mcp_apikey_template on ai_mcp_api_key
CREATE INDEX idx_mcp_apikey_template ON ai_mcp_api_key (template_id);

-- index idx_mcp_apikey_status on ai_mcp_api_key
CREATE INDEX idx_mcp_apikey_status ON ai_mcp_api_key (status);

-- index ix_ai_mcp_square_template_tenant_id on ai_mcp_square_template
CREATE INDEX ix_ai_mcp_square_template_tenant_id ON ai_mcp_square_template (tenant_id);

-- index idx_mcp_template_category on ai_mcp_square_template
CREATE INDEX idx_mcp_template_category ON ai_mcp_square_template (category);

-- index idx_mcp_template_status on ai_mcp_square_template
CREATE INDEX idx_mcp_template_status ON ai_mcp_square_template (status);

-- index ix_ai_session_finalize_log_session on ai_session_finalize_log
CREATE INDEX ix_ai_session_finalize_log_session ON ai_session_finalize_log (tenant_id, session_id, finalized_at);

-- index ix_ai_session_finalize_log_tenant_id on ai_session_finalize_log
CREATE INDEX ix_ai_session_finalize_log_tenant_id ON ai_session_finalize_log (tenant_id);

-- index ix_ai_session_finalize_log_user_id on ai_session_finalize_log
CREATE INDEX ix_ai_session_finalize_log_user_id ON ai_session_finalize_log (user_id);

-- index ix_ai_session_finalize_log_session_id on ai_session_finalize_log
CREATE INDEX ix_ai_session_finalize_log_session_id ON ai_session_finalize_log (session_id);

-- index ix_ai_skill_evolution_config_model_code on ai_skill_evolution_config
CREATE INDEX ix_ai_skill_evolution_config_model_code ON ai_skill_evolution_config (model_code);

-- index ix_ai_skill_evolution_config_skill_id on ai_skill_evolution_config
CREATE UNIQUE INDEX ix_ai_skill_evolution_config_skill_id ON ai_skill_evolution_config (skill_id);

-- index ix_ai_skill_evolution_config_tenant_id on ai_skill_evolution_config
CREATE INDEX ix_ai_skill_evolution_config_tenant_id ON ai_skill_evolution_config (tenant_id);

-- index ix_ai_skill_evolution_log_tenant_id on ai_skill_evolution_log
CREATE INDEX ix_ai_skill_evolution_log_tenant_id ON ai_skill_evolution_log (tenant_id);

-- index ix_ai_skill_evolution_log_skill_id on ai_skill_evolution_log
CREATE INDEX ix_ai_skill_evolution_log_skill_id ON ai_skill_evolution_log (skill_id);

-- index ix_ai_skill_hub_repo_tenant_id on ai_skill_hub_repo
CREATE INDEX ix_ai_skill_hub_repo_tenant_id ON ai_skill_hub_repo (tenant_id);

-- index ix_ai_skill_metrics_tenant_id on ai_skill_metrics
CREATE INDEX ix_ai_skill_metrics_tenant_id ON ai_skill_metrics (tenant_id);

-- index idx_skill_package_enabled on ai_skill_package
CREATE INDEX idx_skill_package_enabled ON ai_skill_package (enabled);

-- index ix_ai_skill_package_tenant_id on ai_skill_package
CREATE INDEX ix_ai_skill_package_tenant_id ON ai_skill_package (tenant_id);

-- index idx_skill_package_category on ai_skill_package
CREATE INDEX idx_skill_package_category ON ai_skill_package (category);

-- index ix_ai_skill_rule_agent_name on ai_skill_rule
CREATE INDEX ix_ai_skill_rule_agent_name ON ai_skill_rule (agent_name);

-- index ix_ai_skill_rule_tenant_id on ai_skill_rule
CREATE INDEX ix_ai_skill_rule_tenant_id ON ai_skill_rule (tenant_id);

-- index ix_ai_skill_script_tenant_id on ai_skill_script
CREATE INDEX ix_ai_skill_script_tenant_id ON ai_skill_script (tenant_id);

-- index idx_skill_script_package on ai_skill_script
CREATE INDEX idx_skill_script_package ON ai_skill_script (package_id);

-- index idx_skill_script_enabled on ai_skill_script
CREATE INDEX idx_skill_script_enabled ON ai_skill_script (enabled);

-- index ix_ai_skill_version_tenant_id on ai_skill_version
CREATE INDEX ix_ai_skill_version_tenant_id ON ai_skill_version (tenant_id);

-- index ix_ai_skill_version_skill_id on ai_skill_version
CREATE INDEX ix_ai_skill_version_skill_id ON ai_skill_version (skill_id);

-- index idx_tool_definition_category on ai_tool_definition
CREATE INDEX idx_tool_definition_category ON ai_tool_definition (category);

-- index idx_tool_definition_tool_key on ai_tool_definition
CREATE UNIQUE INDEX idx_tool_definition_tool_key ON ai_tool_definition (tool_key);

-- index idx_tool_definition_status on ai_tool_definition
CREATE INDEX idx_tool_definition_status ON ai_tool_definition (status);

-- index ix_ai_tool_definition_tenant_id on ai_tool_definition
CREATE INDEX ix_ai_tool_definition_tenant_id ON ai_tool_definition (tenant_id);

-- index idx_tool_definition_type on ai_tool_definition
CREATE INDEX idx_tool_definition_type ON ai_tool_definition (tool_type);

-- index idx_tool_definition_is_system on ai_tool_definition
CREATE INDEX idx_tool_definition_is_system ON ai_tool_definition (is_system);

-- index ix_ai_tool_group_tenant_id on ai_tool_group
CREATE INDEX ix_ai_tool_group_tenant_id ON ai_tool_group (tenant_id);

-- index idx_tool_group_active on ai_tool_group
CREATE INDEX idx_tool_group_active ON ai_tool_group (is_active);

-- index ix_ai_web_search_tenant_id on ai_web_search
CREATE INDEX ix_ai_web_search_tenant_id ON ai_web_search (tenant_id);

-- index ix_ai_web_search_platform on ai_web_search
CREATE INDEX ix_ai_web_search_platform ON ai_web_search (platform);

-- index ix_ai_web_search_log_created_at on ai_web_search_log
CREATE INDEX ix_ai_web_search_log_created_at ON ai_web_search_log (created_at);

-- index ix_ai_web_search_log_tenant_id on ai_web_search_log
CREATE INDEX ix_ai_web_search_log_tenant_id ON ai_web_search_log (tenant_id);

-- index ix_ai_web_search_log_web_search_id on ai_web_search_log
CREATE INDEX ix_ai_web_search_log_web_search_id ON ai_web_search_log (web_search_id);

-- index ix_duplex_voice_config_role_id on duplex_voice_config
CREATE UNIQUE INDEX ix_duplex_voice_config_role_id ON duplex_voice_config (role_id);

-- index ix_duplex_voice_session_case_number on duplex_voice_session
CREATE INDEX ix_duplex_voice_session_case_number ON duplex_voice_session (case_number);

-- index ix_duplex_voice_session_duplex_session_id on duplex_voice_session
CREATE INDEX ix_duplex_voice_session_duplex_session_id ON duplex_voice_session (duplex_session_id);

-- index ix_duplex_voice_turn_voice_session_id on duplex_voice_turn
CREATE INDEX ix_duplex_voice_turn_voice_session_id ON duplex_voice_turn (voice_session_id);

-- index ix_kms_document_knowledge_id on kms_document
CREATE INDEX ix_kms_document_knowledge_id ON kms_document (knowledge_id);

-- index ix_kms_document_tenant_id on kms_document
CREATE INDEX ix_kms_document_tenant_id ON kms_document (tenant_id);

-- index ix_kms_knowledge_slug on kms_knowledge
CREATE UNIQUE INDEX ix_kms_knowledge_slug ON kms_knowledge (slug);

-- index ix_kms_knowledge_tenant_id on kms_knowledge
CREATE INDEX ix_kms_knowledge_tenant_id ON kms_knowledge (tenant_id);

-- index idx_kms_knowledge_tenant_type on kms_knowledge
CREATE INDEX idx_kms_knowledge_tenant_type ON kms_knowledge (tenant_id, type);

-- index idx_kms_knowledge_tenant on kms_knowledge
CREATE INDEX idx_kms_knowledge_tenant ON kms_knowledge (tenant_id);

-- index idx_kms_knowledge_slug on kms_knowledge
CREATE UNIQUE INDEX idx_kms_knowledge_slug ON kms_knowledge (slug);

-- index ix_kms_ref_tenant_id on kms_ref
CREATE INDEX ix_kms_ref_tenant_id ON kms_ref (tenant_id);

-- index ix_kms_search_log_tenant_id on kms_search_log
CREATE INDEX ix_kms_search_log_tenant_id ON kms_search_log (tenant_id);

-- index ix_kms_search_log_knowledge_id on kms_search_log
CREATE INDEX ix_kms_search_log_knowledge_id ON kms_search_log (knowledge_id);

-- index idx_kms_search_log_tenant on kms_search_log
CREATE INDEX idx_kms_search_log_tenant ON kms_search_log (tenant_id, created_at);

-- index idx_kms_segment_parent on kms_segment
CREATE INDEX idx_kms_segment_parent ON kms_segment (parent_id);

-- index ix_kms_segment_parent_id on kms_segment
CREATE INDEX ix_kms_segment_parent_id ON kms_segment (parent_id);

-- index ix_kms_segment_tenant_id on kms_segment
CREATE INDEX ix_kms_segment_tenant_id ON kms_segment (tenant_id);

-- index idx_meta_column_std_history_column on meta_column_standard_history
CREATE INDEX idx_meta_column_std_history_column ON meta_column_standard_history (column_id);

-- index ix_meta_column_standard_history_tenant_id on meta_column_standard_history
CREATE INDEX ix_meta_column_standard_history_tenant_id ON meta_column_standard_history (tenant_id);

-- index ix_meta_connector_ingest_tenant_id on meta_connector_ingest
CREATE INDEX ix_meta_connector_ingest_tenant_id ON meta_connector_ingest (tenant_id);

-- index ix_meta_connector_sync_state_tenant_id on meta_connector_sync_state
CREATE INDEX ix_meta_connector_sync_state_tenant_id ON meta_connector_sync_state (tenant_id);

-- index ix_meta_data_source_tenant_id on meta_data_source
CREATE INDEX ix_meta_data_source_tenant_id ON meta_data_source (tenant_id);

-- index ix_meta_standard_tenant_id on meta_standard
CREATE INDEX ix_meta_standard_tenant_id ON meta_standard (tenant_id);

-- index ix_ontology_tenant_id on ontology
CREATE INDEX ix_ontology_tenant_id ON ontology (tenant_id);

-- index idx_ontology_status on ontology
CREATE INDEX idx_ontology_status ON ontology (status);

-- index ix_sop_templates_template_key on sop_templates
CREATE UNIQUE INDEX ix_sop_templates_template_key ON sop_templates (template_key);

-- index idx_audit_operation on sys_audit_log
CREATE INDEX idx_audit_operation ON sys_audit_log (operation_type, operation_module);

-- index ix_sys_audit_log_user_id on sys_audit_log
CREATE INDEX ix_sys_audit_log_user_id ON sys_audit_log (user_id);

-- index ix_sys_audit_log_request_ip on sys_audit_log
CREATE INDEX ix_sys_audit_log_request_ip ON sys_audit_log (request_ip);

-- index ix_sys_audit_log_created_at on sys_audit_log
CREATE INDEX ix_sys_audit_log_created_at ON sys_audit_log (created_at);

-- index ix_sys_audit_log_tenant_id on sys_audit_log
CREATE INDEX ix_sys_audit_log_tenant_id ON sys_audit_log (tenant_id);

-- index ix_sys_dictionary_tenant_id on sys_dictionary
CREATE INDEX ix_sys_dictionary_tenant_id ON sys_dictionary (tenant_id);

-- index ix_sys_dictionary_item_tenant_id on sys_dictionary_item
CREATE INDEX ix_sys_dictionary_item_tenant_id ON sys_dictionary_item (tenant_id);

-- index ix_sys_infra_file_config_id on sys_infra_file
CREATE INDEX ix_sys_infra_file_config_id ON sys_infra_file (config_id);

-- index ix_sys_infra_file_tenant_id on sys_infra_file
CREATE INDEX ix_sys_infra_file_tenant_id ON sys_infra_file (tenant_id);

-- index ix_sys_infra_file_content_config_id on sys_infra_file_content
CREATE INDEX ix_sys_infra_file_content_config_id ON sys_infra_file_content (config_id);

-- index ix_sys_infra_file_content_tenant_id on sys_infra_file_content
CREATE INDEX ix_sys_infra_file_content_tenant_id ON sys_infra_file_content (tenant_id);

-- index ix_sys_menu_parent_id on sys_menu
CREATE INDEX ix_sys_menu_parent_id ON sys_menu (parent_id);

-- index ix_sys_menu_permission on sys_menu
CREATE INDEX ix_sys_menu_permission ON sys_menu (permission);

-- index ix_sys_role_tenant_id on sys_role
CREATE INDEX ix_sys_role_tenant_id ON sys_role (tenant_id);

-- index ix_sys_user_username on sys_user
CREATE UNIQUE INDEX ix_sys_user_username ON sys_user (username);

-- index ix_sys_user_tenant_id on sys_user
CREATE INDEX ix_sys_user_tenant_id ON sys_user (tenant_id);

-- index ix_sys_user_notification_created_at on sys_user_notification
CREATE INDEX ix_sys_user_notification_created_at ON sys_user_notification (created_at);

-- index ix_sys_user_notification_user_id on sys_user_notification
CREATE INDEX ix_sys_user_notification_user_id ON sys_user_notification (user_id);

-- index ix_sys_user_notification_tenant_id on sys_user_notification
CREATE INDEX ix_sys_user_notification_tenant_id ON sys_user_notification (tenant_id);

-- index ix_notif_user_read on sys_user_notification
CREATE INDEX ix_notif_user_read ON sys_user_notification (user_id, is_read);

-- index ix_tool_policy_tool_name on tool_policy
CREATE UNIQUE INDEX ix_tool_policy_tool_name ON tool_policy (tool_name);

-- index uq_workflow_chain_code_tenant on workflow_chain
CREATE UNIQUE INDEX uq_workflow_chain_code_tenant ON workflow_chain (chain_code, tenant_id);

-- index ix_workflow_chain_tenant_id on workflow_chain
CREATE INDEX ix_workflow_chain_tenant_id ON workflow_chain (tenant_id);

-- index ix_workflow_execution_log_tenant_id on workflow_execution_log
CREATE INDEX ix_workflow_execution_log_tenant_id ON workflow_execution_log (tenant_id);

-- index idx_wf_exec_log_status on workflow_execution_log
CREATE INDEX idx_wf_exec_log_status ON workflow_execution_log (status);

-- index idx_wf_exec_log_created on workflow_execution_log
CREATE INDEX idx_wf_exec_log_created ON workflow_execution_log (created_at);

-- index idx_wf_exec_log_flow on workflow_execution_log
CREATE INDEX idx_wf_exec_log_flow ON workflow_execution_log (flow_id);

-- index uq_workflow_flow_code_tenant on workflow_flow
CREATE UNIQUE INDEX uq_workflow_flow_code_tenant ON workflow_flow (flow_code, tenant_id);

-- index idx_workflow_flow_platform on workflow_flow
CREATE INDEX idx_workflow_flow_platform ON workflow_flow (platform_type);

-- index ix_workflow_flow_tenant_id on workflow_flow
CREATE INDEX ix_workflow_flow_tenant_id ON workflow_flow (tenant_id);

-- index ix_ai_chat_message_execution_id on ai_chat_message
CREATE INDEX ix_ai_chat_message_execution_id ON ai_chat_message (execution_id);

-- index ix_ai_chat_message_file_id on ai_chat_message
CREATE INDEX ix_ai_chat_message_file_id ON ai_chat_message (file_id);

-- index ix_ai_chat_message_session_id on ai_chat_message
CREATE INDEX ix_ai_chat_message_session_id ON ai_chat_message (session_id);

-- index ix_ai_chat_message_tenant_id on ai_chat_message
CREATE INDEX ix_ai_chat_message_tenant_id ON ai_chat_message (tenant_id);

-- index ix_ai_chat_model_tenant_id on ai_chat_model
CREATE INDEX ix_ai_chat_model_tenant_id ON ai_chat_model (tenant_id);

-- index ix_ai_chat_model_key_id on ai_chat_model
CREATE INDEX ix_ai_chat_model_key_id ON ai_chat_model (key_id);

-- index idx_mcp_client_active on ai_mcp_client
CREATE INDEX idx_mcp_client_active ON ai_mcp_client (is_active);

-- index ix_ai_mcp_client_tenant_id on ai_mcp_client
CREATE INDEX ix_ai_mcp_client_tenant_id ON ai_mcp_client (tenant_id);

-- index idx_mcp_client_apikey on ai_mcp_client
CREATE INDEX idx_mcp_client_apikey ON ai_mcp_client (api_key_id);

-- index ix_ai_tool_group_member_tenant_id on ai_tool_group_member
CREATE INDEX ix_ai_tool_group_member_tenant_id ON ai_tool_group_member (tenant_id);

-- index idx_tool_group_member_tool on ai_tool_group_member
CREATE INDEX idx_tool_group_member_tool ON ai_tool_group_member (tool_key);

-- index ix_ai_workspace_tenant_id on ai_workspace
CREATE INDEX ix_ai_workspace_tenant_id ON ai_workspace (tenant_id);

-- index ix_ai_workspace_workspace_id on ai_workspace
CREATE UNIQUE INDEX ix_ai_workspace_workspace_id ON ai_workspace (workspace_id);

-- index idx_wiki_article_category on kms_article
CREATE INDEX idx_wiki_article_category ON kms_article (category_id);

-- index idx_wiki_article_status on kms_article
CREATE INDEX idx_wiki_article_status ON kms_article (status);

-- index ix_kms_article_slug on kms_article
CREATE UNIQUE INDEX ix_kms_article_slug ON kms_article (slug);

-- index ix_kms_article_tenant_id on kms_article
CREATE INDEX ix_kms_article_tenant_id ON kms_article (tenant_id);

-- index ix_kms_article_category_id on kms_article
CREATE INDEX ix_kms_article_category_id ON kms_article (category_id);

-- index ix_kms_article_knowledge_id on kms_article
CREATE INDEX ix_kms_article_knowledge_id ON kms_article (knowledge_id);

-- index idx_wiki_article_slug on kms_article
CREATE UNIQUE INDEX idx_wiki_article_slug ON kms_article (slug);

-- index ix_kms_category_tenant_id on kms_category
CREATE INDEX ix_kms_category_tenant_id ON kms_category (tenant_id);

-- index ix_kms_category_slug on kms_category
CREATE UNIQUE INDEX ix_kms_category_slug ON kms_category (slug);

-- index ix_kms_category_knowledge_id on kms_category
CREATE INDEX ix_kms_category_knowledge_id ON kms_category (knowledge_id);

-- index idx_kms_category_slug on kms_category
CREATE UNIQUE INDEX idx_kms_category_slug ON kms_category (slug);

-- index ix_kms_category_parent_id on kms_category
CREATE INDEX ix_kms_category_parent_id ON kms_category (parent_id);

-- index idx_kms_category_parent on kms_category
CREATE INDEX idx_kms_category_parent ON kms_category (parent_id);

-- index ix_kms_collection_tenant_id on kms_collection
CREATE INDEX ix_kms_collection_tenant_id ON kms_collection (tenant_id);

-- index ix_kms_collection_knowledge_id on kms_collection
CREATE INDEX ix_kms_collection_knowledge_id ON kms_collection (knowledge_id);

-- index ix_kms_connector_instance_tenant_id on kms_connector_instance
CREATE INDEX ix_kms_connector_instance_tenant_id ON kms_connector_instance (tenant_id);

-- index ix_kms_connector_instance_knowledge_id on kms_connector_instance
CREATE INDEX ix_kms_connector_instance_knowledge_id ON kms_connector_instance (knowledge_id);

-- index ix_kms_external_kb_endpoint_knowledge_id on kms_external_kb_endpoint
CREATE INDEX ix_kms_external_kb_endpoint_knowledge_id ON kms_external_kb_endpoint (knowledge_id);

-- index ix_kms_external_kb_endpoint_tenant_id on kms_external_kb_endpoint
CREATE INDEX ix_kms_external_kb_endpoint_tenant_id ON kms_external_kb_endpoint (tenant_id);

-- index ix_kms_segment_asset_tenant_id on kms_segment_asset
CREATE INDEX ix_kms_segment_asset_tenant_id ON kms_segment_asset (tenant_id);

-- index ix_kms_segment_asset_segment_id on kms_segment_asset
CREATE INDEX ix_kms_segment_asset_segment_id ON kms_segment_asset (segment_id);

-- index ix_meta_data_write_request_tenant_id on meta_data_write_request
CREATE INDEX ix_meta_data_write_request_tenant_id ON meta_data_write_request (tenant_id);

-- index idx_meta_relation_source_db on meta_relation
CREATE INDEX idx_meta_relation_source_db ON meta_relation (source_id, database);

-- index idx_meta_relation_lr on meta_relation
CREATE INDEX idx_meta_relation_lr ON meta_relation (left_table, right_table);

-- index ix_meta_relation_tenant_id on meta_relation
CREATE INDEX ix_meta_relation_tenant_id ON meta_relation (tenant_id);

-- index ix_meta_scan_job_tenant_id on meta_scan_job
CREATE INDEX ix_meta_scan_job_tenant_id ON meta_scan_job (tenant_id);

-- index idx_meta_scan_job_source on meta_scan_job
CREATE INDEX idx_meta_scan_job_source ON meta_scan_job (source_id, status);

-- index ix_meta_standard_version_tenant_id on meta_standard_version
CREATE INDEX ix_meta_standard_version_tenant_id ON meta_standard_version (tenant_id);

-- index idx_meta_table_domain on meta_table
CREATE INDEX idx_meta_table_domain ON meta_table (domain);

-- index ix_meta_table_tenant_id on meta_table
CREATE INDEX ix_meta_table_tenant_id ON meta_table (tenant_id);

-- index idx_ontology_annotation_ontology on ontology_annotation
CREATE INDEX idx_ontology_annotation_ontology ON ontology_annotation (ontology_id);

-- index ix_ontology_annotation_tenant_id on ontology_annotation
CREATE INDEX ix_ontology_annotation_tenant_id ON ontology_annotation (tenant_id);

-- index idx_ontology_annotation_target on ontology_annotation
CREATE INDEX idx_ontology_annotation_target ON ontology_annotation (target_type, target_id);

-- index idx_ontology_class_ontology on ontology_class
CREATE INDEX idx_ontology_class_ontology ON ontology_class (ontology_id);

-- index ix_ontology_class_tenant_id on ontology_class
CREATE INDEX ix_ontology_class_tenant_id ON ontology_class (tenant_id);

-- index idx_ontology_class_status on ontology_class
CREATE INDEX idx_ontology_class_status ON ontology_class (status);

-- index idx_cq_ontology on ontology_cq
CREATE INDEX idx_cq_ontology ON ontology_cq (ontology_id);

-- index idx_cq_status on ontology_cq
CREATE INDEX idx_cq_status ON ontology_cq (status);

-- index idx_object_type_status on ontology_object_type
CREATE INDEX idx_object_type_status ON ontology_object_type (status);

-- index idx_object_type_parent on ontology_object_type
CREATE INDEX idx_object_type_parent ON ontology_object_type (parent_id);

-- index idx_object_type_ontology on ontology_object_type
CREATE INDEX idx_object_type_ontology ON ontology_object_type (ontology_id);

-- index idx_version_ontology on ontology_version
CREATE INDEX idx_version_ontology ON ontology_version (ontology_id);

-- index ix_sys_user_role_tenant_id on sys_user_role
CREATE INDEX ix_sys_user_role_tenant_id ON sys_user_role (tenant_id);

-- index idx_wiki_version_article_version on kms_article_version
CREATE UNIQUE INDEX idx_wiki_version_article_version ON kms_article_version (article_id, version);

-- index ix_kms_article_version_tenant_id on kms_article_version
CREATE INDEX ix_kms_article_version_tenant_id ON kms_article_version (tenant_id);

-- index ix_kms_article_version_article_id on kms_article_version
CREATE INDEX ix_kms_article_version_article_id ON kms_article_version (article_id);

-- index ix_kms_connector_sync_log_instance_id on kms_connector_sync_log
CREATE INDEX ix_kms_connector_sync_log_instance_id ON kms_connector_sync_log (instance_id);

-- index ix_kms_connector_sync_log_tenant_id on kms_connector_sync_log
CREATE INDEX ix_kms_connector_sync_log_tenant_id ON kms_connector_sync_log (tenant_id);

-- index ix_meta_column_tenant_id on meta_column
CREATE INDEX ix_meta_column_tenant_id ON meta_column (tenant_id);

-- index idx_link_type_source on ontology_link_type
CREATE INDEX idx_link_type_source ON ontology_link_type (source_type_id);

-- index idx_link_type_target on ontology_link_type
CREATE INDEX idx_link_type_target ON ontology_link_type (target_type_id);

-- index idx_link_type_ontology on ontology_link_type
CREATE INDEX idx_link_type_ontology ON ontology_link_type (ontology_id);

-- index idx_mapping_target on ontology_mapping
CREATE INDEX idx_mapping_target ON ontology_mapping (target_type, table_name);

-- index idx_mapping_ontology on ontology_mapping
CREATE INDEX idx_mapping_ontology ON ontology_mapping (ontology_id);

-- index idx_mapping_status on ontology_mapping
CREATE INDEX idx_mapping_status ON ontology_mapping (status);

-- index idx_mapping_object_type on ontology_mapping
CREATE INDEX idx_mapping_object_type ON ontology_mapping (object_type_id);

-- index idx_property_status on ontology_property
CREATE INDEX idx_property_status ON ontology_property (status);

-- index idx_property_object_type on ontology_property
CREATE INDEX idx_property_object_type ON ontology_property (object_type_id);

-- index ix_meta_column_standard_tenant_id on meta_column_standard
CREATE INDEX ix_meta_column_standard_tenant_id ON meta_column_standard (tenant_id);

-- ── 性能索引（向量 / 全文检索）────────────────────────────
CREATE INDEX IF NOT EXISTS idx_kms_segment_embedding_hnsw ON kms_segment USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_kms_segment_content_trgm ON kms_segment USING gin (content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_kms_article_vector_hnsw ON kms_article USING hnsw (content_vector vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ══════════════════════════════════════════════════════════════
-- 初始化数据（seed）
-- 来源：docs/sql 下的种子脚本，按依赖顺序拼接；全部幂等。
-- ══════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────
-- 来源：init_tenants.sql
-- ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS ix_sys_user_tenant_id ON sys_user(tenant_id);

INSERT INTO sys_tenant (tenant_id, name, contact_name, contact_mobile, status, account_count)
VALUES
    (1, '金融投资', '金融投资管理員', '13800000001', 'active', 100),
    (2, '销售营销', '销售营销管理员', '13800000002', 'active', 100),
    (3, '法律AI',   '法律AI管理员',   '13800000003', 'active', 100),
    (4, '办公AI',   '办公AI管理员',   '13800000004', 'active', 100),
    (5, '教育AI',   '教育AI管理员',   '13800000005', 'active', 100),
    (6, '学习AI',   '学习AI管理员',   '13800000006', 'active', 100),
    (0, 'MiniWorkBuddy', '系统管理员', NULL, 'active', 9999)
ON CONFLICT DO NOTHING;

INSERT INTO sys_user (user_id, username, password_hash, real_name, status, is_admin, tenant_id, is_deleted)
VALUES
    (1001, 'admin_finance', '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '金融投资管理员', 'active', true, 1, false),
    (1002, 'admin_sales',   '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '销售营销管理员', 'active', true, 2, false),
    (1003, 'admin_legal',   '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '法律AI管理员',   'active', true, 3, false),
    (1004, 'admin_office',  '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '办公AI管理员',   'active', true, 4, false),
    (1005, 'admin_edu',     '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '教育AI管理员',   'active', true, 5, false),
    (1006, 'admin_study',   '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '学习AI管理员',   'active', true, 6, false),
    (9999, 'admin',          '$2b$12$NgRUWcviQryzTh.W2Loryest7q9WNunRhFChbzWMkOaBAk8Wa03t2', '超级管理员',     'active', true, 0, false)
ON CONFLICT (username) DO NOTHING;

INSERT INTO sys_role (role_id, role_name, role_code, status, tenant_id, is_deleted)
VALUES
    (1001, '租户管理员', 'tenant_admin_finance', 'active', 1, false),
    (1002, '租户管理员', 'tenant_admin_sales',   'active', 2, false),
    (1003, '租户管理员', 'tenant_admin_legal',   'active', 3, false),
    (1004, '租户管理员', 'tenant_admin_office',  'active', 4, false),
    (1005, '租户管理员', 'tenant_admin_edu',     'active', 5, false),
    (1006, '租户管理员', 'tenant_admin_study',   'active', 6, false),
    (9999, '超级管理员', 'super_admin',          'active', 0, false)
ON CONFLICT (role_code) DO NOTHING;

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 1001, 1001, 1 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 1001 AND role_id = 1001);

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 1002, 1002, 2 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 1002 AND role_id = 1002);

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 1003, 1003, 3 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 1003 AND role_id = 1003);

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 1004, 1004, 4 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 1004 AND role_id = 1004);

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 1005, 1005, 5 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 1005 AND role_id = 1005);

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 1006, 1006, 6 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 1006 AND role_id = 1006);

INSERT INTO sys_user_role (user_id, role_id, tenant_id)
SELECT 9999, 9999, 0 WHERE NOT EXISTS (SELECT 1 FROM sys_user_role WHERE user_id = 9999 AND role_id = 9999);

SELECT setval(pg_get_serial_sequence('sys_tenant', 'tenant_id'), COALESCE((SELECT MAX(tenant_id) FROM sys_tenant), 1), true);

SELECT setval(pg_get_serial_sequence('sys_user',   'user_id'),   COALESCE((SELECT MAX(user_id)   FROM sys_user),   1), true);

SELECT setval(pg_get_serial_sequence('sys_role',   'role_id'),   COALESCE((SELECT MAX(role_id)   FROM sys_role),   1), true);

SELECT setval(pg_get_serial_sequence('sys_user_role', 'id'),      COALESCE((SELECT MAX(id)        FROM sys_user_role), 1), true);

-- ───────────────────────────────────────────────────────
-- 来源：sys_dictionary.sql
-- ───────────────────────────────────────────────────────
COMMENT ON COLUMN "public"."sys_dictionary"."dict_id" IS '字典ID';

COMMENT ON COLUMN "public"."sys_dictionary"."dict_code" IS '字典编码';

COMMENT ON COLUMN "public"."sys_dictionary"."dict_name" IS '字典名称';

COMMENT ON COLUMN "public"."sys_dictionary"."dict_type" IS '字典类型';

COMMENT ON COLUMN "public"."sys_dictionary"."description" IS '字典描述';

COMMENT ON COLUMN "public"."sys_dictionary"."sort_order" IS '排序顺序';

COMMENT ON COLUMN "public"."sys_dictionary"."is_active" IS '是否启用';

COMMENT ON COLUMN "public"."sys_dictionary"."extra_data" IS '扩展数据';

COMMENT ON COLUMN "public"."sys_dictionary"."tenant_id" IS '租户ID';

COMMENT ON TABLE "public"."sys_dictionary" IS '系统字典表';

INSERT INTO "public"."sys_dictionary" VALUES (5, 'source_type', '来源类型', 'business', '数据来源类型', 5, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (8, 'tag', '标签', 'business', '事件和人员标签', 8, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (91, 'audit_operation_module', '日志-操作模块', 'system', '系统审计日志的操作模块映射，对应各业务功能模块', 101, 'f', NULL, NULL, '2026-03-26 06:29:27.413877', '2026-03-26 06:56:54.412591', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (90, 'audit_operation_type', '日志-操作类型', 'system', '系统审计日志的操作类型映射，用于仪表盘日志显示', 100, 'f', NULL, NULL, '2026-03-26 06:29:27.364697', '2026-03-26 06:57:00.534379', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (126, 'agent_impl_type', '专家实现类型', 'system', '专家（Agent）技术实现类型', 11, 'f', NULL, NULL, '2026-07-16 20:07:21.152191', '2026-07-16 20:07:21.152191', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (132, 'ontology_rel_type', '本体关系类型', 'ontology', 'UML 类图关系类型', 0, 'f', NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (133, 'kg_reasoning_exec_mode', '推理执行模式', 'system', '知识图谱推理规则执行模式（Skill/Tool/P1-P6 推理范式）', 20, 'f', NULL, NULL, '2026-08-13 22:42:34.260358', '2026-08-13 22:42:34.260358', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (134, 'tool_type', '工具类型', 'system', 'AI工具管理-工具类型分类', 10, 'f', NULL, NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (135, 'web_search_platform', 'AI 联网搜索平台', 'business', '联网搜索供应商可选平台', 0, 'f', NULL, NULL, '2026-08-24 15:20:15.892423', '2026-08-24 15:20:15.892423', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (123, 'skill_category', 'AI技能类目', 'config', 'AI技能包的分类，如论证分析、法律推理、文档处理等', 0, 'f', NULL, NULL, '2026-07-13 17:49:59.156076', '2026-07-13 17:49:59.156076', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (136, 'model_type', '模型类型', 'system', '模型类型', 200, 'f', 'null', NULL, '2026-09-03 18:47:30.46293', '2026-09-13 15:59:17.985395', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (124, 'agent_category', '专家用途分类', 'business', '专家（Agent）用途/业务领域分类', 10, 'f', NULL, NULL, '2026-07-16 19:52:43.902779', '2026-09-13 15:59:31.760586', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (80, 'task_type', '任务类型', 'business', '调度任务的任务类型', 10, 'f', 'null', NULL, '2026-03-24 08:55:21.819685', '2026-09-13 15:59:43.373498', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (6, 'dept_type', '部门类型', 'business', '来源部门类型', 6, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-13 15:59:53.446382', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (115, 'agent_type', 'Agent角色类型', 'business', '仿真中Agent的角色类型', 4, 'f', NULL, NULL, '2026-05-06 19:30:56.016168', '2026-09-13 16:00:02.502869', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (81, 'report_type', 'AI报告类型', 'business', 'AI智能报告的类型分类', 1, 'f', NULL, NULL, '2026-03-25 06:07:13.806351', '2026-09-13 16:00:12.969898', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (4, 'region', '行政区域', 'system', '行政区域划分', 120, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-13 16:00:42.794339', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary" VALUES (127, 'session_type', '会话类别', 'system', '会话类别', 160, 'f', 'null', NULL, '2026-07-25 19:54:19.175519', '2026-09-13 16:00:52.83128', 'f', NULL) ON CONFLICT (dict_id) DO NOTHING;

COMMENT ON COLUMN "public"."sys_dictionary_item"."item_id" IS '字典项ID';

COMMENT ON COLUMN "public"."sys_dictionary_item"."dict_code" IS '所属字典编码';

COMMENT ON COLUMN "public"."sys_dictionary_item"."item_code" IS '字典项编码';

COMMENT ON COLUMN "public"."sys_dictionary_item"."item_name" IS '字典项名称';

COMMENT ON COLUMN "public"."sys_dictionary_item"."item_value" IS '字典项值';

COMMENT ON COLUMN "public"."sys_dictionary_item"."parent_code" IS '父级编码';

COMMENT ON COLUMN "public"."sys_dictionary_item"."level" IS '层级';

COMMENT ON COLUMN "public"."sys_dictionary_item"."color" IS '颜色标识';

COMMENT ON COLUMN "public"."sys_dictionary_item"."icon" IS '图标';

COMMENT ON COLUMN "public"."sys_dictionary_item"."sort_order" IS '排序顺序';

COMMENT ON COLUMN "public"."sys_dictionary_item"."is_active" IS '是否启用';

COMMENT ON COLUMN "public"."sys_dictionary_item"."extra_data" IS '扩展数据';

COMMENT ON COLUMN "public"."sys_dictionary_item"."remark" IS '备注';

COMMENT ON COLUMN "public"."sys_dictionary_item"."created_by" IS '创建人ID';

COMMENT ON COLUMN "public"."sys_dictionary_item"."tenant_id" IS '租户ID';

COMMENT ON TABLE "public"."sys_dictionary_item" IS '系统字典项表';

INSERT INTO "public"."sys_dictionary_item" VALUES (872, 'model_type', '6', '向量排序模型', '6', NULL, 1, '#09fb31', '', 6, 'f', 'null', '向量排序模型', NULL, '2026-09-03 18:51:11.925408', '2026-09-13 15:58:58.451592', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (868, 'model_type', '1', '文本模型', '1', NULL, 1, '#0af038', '', 1, 'f', 'null', '文本模型', NULL, '2026-09-03 18:48:23.776542', '2026-09-13 15:59:02.17352', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (400, 'region', '330200', '宁波市', '330200', '330000', 2, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:00.752643', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (403, 'region', '330300', '温州市', '330300', '330000', 2, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:03.724358', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (409, 'region', '330500', '湖州市', '330500', '330000', 2, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:28.655162', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (406, 'region', '330400', '嘉兴市', '330400', '330000', 2, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:30.470621', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (410, 'region', '330502', '吴兴区', '330502', '330500', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:33.598947', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (396, 'region', '330000', '浙江省', '330000', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:21.252077', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (397, 'region', '330100', '杭州市', '330100', '330000', 2, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:23.302803', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (398, 'region', '330106', '西湖区', '330106', '330100', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:26.128346', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (399, 'region', '330106001', '北山街道', '330106001', '330106', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:28.361148', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (401, 'region', '330206', '海曙区', '330206', '330200', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:40.984277', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (402, 'region', '330206001', '白云街道', '330206001', '330206', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:42.80259', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (404, 'region', '330302', '鹿城区', '330302', '330300', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:44.701156', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (405, 'region', '330302001', '五马街道', '330302001', '330302', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:46.593678', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (407, 'region', '330402', '南湖区', '330402', '330400', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:48.368129', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (408, 'region', '330402001', '新嘉街道', '330402001', '330402', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:50.639923', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (33, 'source_type', 'manual', '手动录入', 'manual', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:35.783014', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (34, 'source_type', 'import', '批量导入', 'import', NULL, 1, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:36.357494', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (35, 'source_type', 'api', 'API接入', 'api', NULL, 1, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:36.88575', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (36, 'source_type', 'sync', '数据同步', 'sync', NULL, 1, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:37.407249', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (37, 'source_type', 'crawler', '爬虫采集', 'crawler', NULL, 1, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:38.381007', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (54, 'tag', 'urgent', '紧急', 'urgent', NULL, 1, '#f5222d', NULL, 1, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:53.630597', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (55, 'tag', 'important', '重要', 'important', NULL, 1, '#fa8c16', NULL, 2, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:55.06883', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (58, 'tag', 'repeat', '重复', 'repeat', NULL, 1, '#faad14', NULL, 5, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:56.685079', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (60, 'tag', 'media_attention', '媒体关注', 'media_attention', NULL, 1, '#1890ff', NULL, 7, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:57.654143', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (492, 'task_type', 'report', '报表生成', '报表生成', NULL, 1, '#2889f0', '', 0, 'f', 'null', '', NULL, '2026-03-24 09:16:45.446621', '2026-03-24 09:17:19.893073', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (497, 'task_type', 'migration', '数据迁移', '数据迁移', NULL, 1, '#f4c2c2', '', 6, 'f', 'null', '数据迁移', NULL, '2026-03-24 09:18:36.746462', '2026-03-24 09:18:36.746462', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (501, 'report_type', 'custom', '自定义报告', 'custom', NULL, 1, 'default', NULL, 40, 'f', NULL, NULL, NULL, '2026-03-25 06:07:13.829743', '2026-03-25 06:07:13.829743', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (418, 'region', '330800', '衢州市', '330800', '330000', 2, NULL, NULL, 8, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:48.585408', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (427, 'region', '331100', '丽水市', '331100', '330000', 2, NULL, NULL, 11, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:27.250856', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (424, 'region', '331000', '台州市', '331000', '330000', 2, NULL, NULL, 10, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:44.590585', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (421, 'region', '330900', '舟山市', '330900', '330000', 2, NULL, NULL, 9, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:46.649877', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (425, 'region', '331002', '椒江区', '331002', '331000', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:51.63445', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (426, 'region', '331002001', '海门街道', '331002001', '331002', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:54.473214', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (428, 'region', '331102', '莲都区', '331102', '331100', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:56.520232', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (429, 'region', '331102001', '紫金街道', '331102001', '331102', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:58.310003', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (415, 'region', '330700', '金华市', '330700', '330000', 2, NULL, NULL, 7, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:24.253307', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (412, 'region', '330600', '绍兴市', '330600', '330000', 2, NULL, NULL, 6, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:26.76365', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (411, 'region', '330502001', '月河街道', '330502001', '330502', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:35.534235', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (423, 'region', '330902001', '昌国街道', '330902001', '330902', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:05.016863', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (500, 'report_type', 'trend_forecast', '金融预测报告', 'trend_forecast', NULL, 1, 'purple', '', 30, 'f', NULL, '', NULL, '2026-03-25 06:07:13.829743', '2026-09-13 15:37:27.457003', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (498, 'report_type', 'disposal_analysis', '金融分析报表', 'statistics_analysis', NULL, 1, 'blue', '', 10, 'f', NULL, '', NULL, '2026-03-25 06:07:13.829743', '2026-09-13 15:37:37.193598', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (422, 'region', '330902', '定海区', '330902', '330900', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:06.661638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (420, 'region', '330802001', '府山街道', '330802001', '330802', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:08.222388', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (419, 'region', '330802', '柯城区', '330802', '330800', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:09.820634', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (417, 'region', '330702001', '城东街道', '330702001', '330702', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:11.580468', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (416, 'region', '330702', '婺城区', '330702', '330700', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:14.111021', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (414, 'region', '330602001', '府山街道', '330602001', '330602', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:15.995185', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (413, 'region', '330602', '越城区', '330602', '330600', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:17.955961', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (870, 'model_type', '3', '视频生成', '3', NULL, 1, '#f70808', '', 3, 'f', 'null', '视频生成', NULL, '2026-09-03 18:49:20.695152', '2026-09-13 15:59:00.798713', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (540, 'audit_operation_type', 'login', '登录', 'login', NULL, 1, 'cyan', NULL, 10, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (541, 'audit_operation_type', 'logout', '登出', 'logout', NULL, 1, 'orange', NULL, 20, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (542, 'audit_operation_type', 'create', '创建', 'create', NULL, 1, 'green', NULL, 30, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (543, 'audit_operation_type', 'update', '更新', 'update', NULL, 1, 'blue', NULL, 40, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (544, 'audit_operation_type', 'delete', '删除', 'delete', NULL, 1, 'red', NULL, 50, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (545, 'audit_operation_type', 'query', '查询', 'query', NULL, 1, 'default', NULL, 60, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (546, 'audit_operation_type', 'export', '导出', 'export', NULL, 1, 'purple', NULL, 70, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (547, 'audit_operation_type', 'import', '导入', 'import', NULL, 1, 'geekblue', NULL, 80, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (548, 'audit_operation_type', 'upload', '上传', 'upload', NULL, 1, 'lime', NULL, 90, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (549, 'audit_operation_type', 'analyze', 'AI分析', 'analyze', NULL, 1, 'magenta', NULL, 100, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (550, 'audit_operation_module', 'auth', '身份认证', 'auth', NULL, 1, NULL, NULL, 10, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (551, 'audit_operation_module', 'user', '用户管理', 'user', NULL, 1, NULL, NULL, 20, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (552, 'audit_operation_module', 'role', '角色管理', 'role', NULL, 1, NULL, NULL, 30, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (553, 'audit_operation_module', 'permission', '权限管理', 'permission', NULL, 1, NULL, NULL, 40, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (561, 'audit_operation_module', 'report', 'AI报告', 'report', NULL, 1, NULL, NULL, 120, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (562, 'audit_operation_module', 'dictionary', '字典管理', 'dictionary', NULL, 1, NULL, NULL, 130, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (563, 'audit_operation_module', 'migration', '数据迁移', 'migration', NULL, 1, NULL, NULL, 140, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (564, 'audit_operation_module', 'system', '系统设置', 'system', NULL, 1, NULL, NULL, 150, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (565, 'audit_operation_module', 'dws', '源数据浏览', 'dws', NULL, 1, NULL, NULL, 160, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (566, 'audit_operation_module', 'search', '全局搜索', 'search', NULL, 1, NULL, NULL, 170, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (567, 'audit_operation_module', 'graph', '关系图谱', 'graph', NULL, 1, NULL, NULL, 180, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (568, 'audit_operation_module', 'ai_assistant', 'AI助手', 'ai_assistant', NULL, 1, NULL, NULL, 190, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (839, 'ontology_rel_type', 'aggregation', '聚合', 'aggregation', NULL, 1, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (857, 'web_search_platform', 'bocha', '博查搜索', 'bocha', NULL, 1, 'blue', NULL, 1, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (858, 'web_search_platform', 'anspire', 'Anspire', 'anspire', NULL, 1, 'cyan', NULL, 2, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (859, 'web_search_platform', 'google', 'Google', 'google', NULL, 1, 'red', NULL, 3, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (860, 'web_search_platform', 'bing', 'Bing', 'bing', NULL, 1, 'green', NULL, 4, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (861, 'web_search_platform', 'custom', '自定义平台', 'custom', NULL, 1, 'default', NULL, 5, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (853, 'tool_type', 'group', '分组', 'group', NULL, 1, 'cyan', NULL, 40, 'f', NULL, '工具分组', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (690, 'agent_type', 'simulator', '模拟引擎', 'simulator', NULL, 1, 'magenta', NULL, 70, 'f', NULL, '系统模拟引擎（非人员角色）', NULL, '2026-05-06 19:30:56.057399', '2026-05-06 19:30:56.057399', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (840, 'ontology_rel_type', 'composition', '组合', 'composition', NULL, 1, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (836, 'ontology_rel_type', 'inheritance', '继承', 'inheritance', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (837, 'ontology_rel_type', 'implementation', '实现', 'implementation', NULL, 1, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (838, 'ontology_rel_type', 'association', '关联', 'association', NULL, 1, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (841, 'ontology_rel_type', 'dependency', '依赖', 'dependency', NULL, 1, NULL, NULL, 6, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (862, 'web_search_platform', 'baidu', '百度', 'baidu', NULL, 1, '#99a30f', '', 5, 'f', 'null', '百度', NULL, '2026-08-24 15:21:42.793416', '2026-08-24 15:21:42.793416', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (871, 'model_type', '5', '向量化模型', '5', NULL, 1, '#0a06f9', '', 5, 'f', 'null', '向量化模型', NULL, '2026-09-03 18:50:51.112515', '2026-09-13 15:58:59.247914', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (796, 'agent_impl_type', 'WORKFLOW', '工作流型', 'WORKFLOW', NULL, 1, 'purple', '', 20, 'f', NULL, '适用于执行 Dify 工作流，可配置输入输出映射', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:02.190974', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (795, 'agent_impl_type', 'CHAT', '会话型', 'CHAT', NULL, 1, 'blue', '', 10, 'f', NULL, '适用于通用对话，支持 LLM 调用与工具集成', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:07.870383', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (797, 'agent_impl_type', 'SKILL', '技能型', 'SKILL', NULL, 1, 'green', '', 30, 'f', NULL, '适用于调用技能包，支持规则引擎自动触发', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:14.795326', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (785, 'agent_category', 'legal_consult', '法律处理', 'legal_consult', NULL, 1, 'orange', '', 20, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:29.238758', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (790, 'agent_category', 'general', '通用助手', 'general', NULL, 1, 'default', '', 70, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:52.419216', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (791, 'agent_category', 'other', '其他', 'other', NULL, 1, 'default', '', 99, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:56.249993', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (842, 'kg_reasoning_exec_mode', 'skill', 'Skill（LLM 执行）', 'skill', NULL, 1, 'purple', 'robot', 10, 'f', NULL, '通过 SkillExecutionService 调用 LLM 技能执行', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (873, 'model_type', '4', '多模态理解', '4', NULL, 1, '#f80d0d', '', 4, 'f', 'null', '多模态理解', NULL, '2026-09-03 18:51:37.996039', '2026-09-13 15:58:59.943183', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (869, 'model_type', '2', '图形生成', '2', NULL, 1, '#e0d910', '', 2, 'f', 'null', '图形生成', NULL, '2026-09-03 18:48:51.679812', '2026-09-13 15:59:01.542972', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (784, 'agent_category', 'event_analysis', '事件分析', 'event_analysis', NULL, 1, 'red', '', 10, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-09-13 15:59:36.057253', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (843, 'kg_reasoning_exec_mode', 'tool', 'Tool（MCP Tool 直调）', 'tool', NULL, 1, 'cyan', 'tool', 20, 'f', NULL, '通过 MCP Tool 直调执行', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (848, 'kg_reasoning_exec_mode', 'bayesian', 'Bayesian（贝叶斯）', 'bayesian', NULL, 1, 'orange', 'experiment', 70, 'f', NULL, '贝叶斯推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (849, 'kg_reasoning_exec_mode', 'fusion', 'Fusion（多范式融合）', 'fusion', NULL, 1, 'red', 'deployment', 80, 'f', NULL, '多范式融合推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (847, 'kg_reasoning_exec_mode', 'fuzzy', 'Fuzzy（模糊推理）', 'fuzzy', NULL, 1, 'orange', 'thunderbolt', 60, 'f', NULL, '模糊推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:21:46.39085', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (846, 'kg_reasoning_exec_mode', 'sparql', 'SPARQL（图查询）', 'sparql', NULL, 1, 'blue', 'share-alt', 50, 'f', NULL, 'SPARQL 图查询推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:21:36.023456', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (845, 'kg_reasoning_exec_mode', 'prolog', 'Prolog（逻辑编程）', 'prolog', NULL, 1, 'blue', 'code', 40, 'f', NULL, 'Prolog 逻辑编程推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:20:54.607057', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (844, 'kg_reasoning_exec_mode', 'owl', 'OWL（描述逻辑）', 'owl', NULL, 1, 'blue', 'branches', 30, 'f', NULL, 'OWL 描述逻辑推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:20:45.202335', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (863, 'web_search_platform', 'tavily', 'Tavily', 'tavily', NULL, 1, 'purple', 'robot', 60, 'f', NULL, '面向 LLM 的检索 API，Bearer 鉴权', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (864, 'web_search_platform', 'exa', 'Exa', 'exa', NULL, 1, 'magenta', 'thunderbolt', 70, 'f', NULL, '神经/嵌入搜索 API，Bearer 鉴权', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (865, 'web_search_platform', 'firecrawl', 'Firecrawl', 'firecrawl', NULL, 1, 'volcano', 'cloud', 80, 'f', NULL, '自托管或 SaaS，统一 /v1/search，可免 Key', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (866, 'web_search_platform', 'searxng', 'SearXNG', 'searxng', NULL, 1, 'gold', 'fork', 90, 'f', NULL, '自托管元搜索引擎，GET /search?format=json', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (850, 'tool_type', 'custom', '自定义', 'custom', NULL, 1, 'default', NULL, 10, 'f', NULL, '用户自定义工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (851, 'tool_type', 'skill', '技能', 'skill', NULL, 1, 'blue', NULL, 20, 'f', NULL, '技能类型工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (852, 'tool_type', 'mcp', 'MCP', 'mcp', NULL, 1, 'purple', NULL, 30, 'f', NULL, 'MCP协议工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (798, 'session_type', 'general', '通用对话', 'general', NULL, 1, '#8ae5db', '', 1, 'f', 'null', '通用对话，使用LLM直接调用', NULL, '2026-07-25 19:56:02.887205', '2026-09-13 15:36:59.98139', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (801, 'session_type', 'skill', '技能', 'skill', NULL, 1, 'green', NULL, 4, 'f', NULL, NULL, NULL, '2026-07-25 20:02:15.099158', '2026-09-13 15:37:03.332918', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (803, 'session_type', 'deep_research', '深度研究', 'deep_research', NULL, 1, '#05fa09', 'SearchOutlined', 60, 'f', NULL, '', NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:38:35.3641', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (804, 'session_type', 'agent', '智能体', 'agent', NULL, 1, 'green', 'RobotOutlined', 70, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:37:08.097456', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (805, 'session_type', 'team', '智能体团队', 'team', NULL, 1, 'purple', 'TeamOutlined', 80, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:37:08.79289', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (802, 'session_type', 'thinking', '深度思考', 'thinking', NULL, 1, '#0c08f7', 'BulbOutlined', 50, 'f', NULL, '', NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:38:26.841048', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (800, 'session_type', 'data', 'NL2SQL', 'nl2sql', NULL, 1, '#caee17', '', 3, 'f', 'null', '数据分析', NULL, '2026-07-25 19:57:32.274971', '2026-09-13 15:39:07.028203', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (799, 'session_type', 'legal_consult', '法律咨询', 'legal_consult', NULL, 1, '#2ce713', '', 2, 'f', 'null', '纠纷调解', NULL, '2026-07-25 19:56:25.478394', '2026-09-13 15:36:57.239582', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (854, 'tool_type', 'sqlbot', 'SQLBot', 'sqlbot', NULL, 1, 'orange', NULL, 50, 'f', NULL, 'NL2SQL查询工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (855, 'tool_type', 'agentscope_builtin', 'AgentScope内置', 'agentscope_builtin', NULL, 1, 'geekblue', NULL, 60, 'f', NULL, 'AgentScope 2.0.6 SDK内置工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (856, 'tool_type', 'custom_dev', '自定义开发', 'custom_dev', NULL, 1, 'green', NULL, 70, 'f', NULL, '项目自定义开发的工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (831, 'skill_category', 'ai-skill', 'AI/Skill治理', 'ai-skill', NULL, 1, '#2f54eb', 'robot', 31, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.084964', '2026-08-05 17:56:51.084964', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (2, 'model_type', '8', '语音识别', '8', NULL, NULL, '#0f0bf9', '', 8, 'f', NULL, '', NULL, '2026-09-12 21:10:56.934428', '2026-09-13 15:58:56.304722', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (1, 'model_type', '7', '语音合成', '7', NULL, NULL, '#dffb09', '', 7, 'f', NULL, '', NULL, '2026-09-12 21:10:56.934428', '2026-09-13 15:58:57.689318', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (776, 'skill_category', 'other', '其他', 'other', NULL, 1, '#8c8c8c', 'appstore', 99, 'f', NULL, '未分类或其他类型的技能', NULL, '2026-07-13 17:49:59.179102', '2026-07-30 17:14:44.69585', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (835, 'session_type', 'scheduled', '云端调度', 'scheduled', NULL, 1, '#06f90a', '', 90, 'f', 'null', '云端调度', NULL, '2026-08-06 21:07:12.653836', '2026-09-13 15:37:09.796131', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

INSERT INTO "public"."sys_dictionary_item" VALUES (834, 'skill_category', 'monitoring', '监测与知识运营', '舆情联动与企业信用核查类技能', NULL, 1, '#722ed1', 'radar', 34, 'f', NULL, '', NULL, '2026-08-05 17:56:51.104772', '2026-09-13 15:38:09.669931', 'f', NULL) ON CONFLICT (item_id) DO NOTHING;

-- ───────────────────────────────────────────────────────
-- 来源：menu_init.sql
-- ───────────────────────────────────────────────────────
INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
VALUES
(2001, '工作台',   'sys.menu.console',             '/admin/console',         NULL, 1, 0, 'console:read',         1, 'DashboardOutlined',  NULL,                    false, 1, 0, 0),
(2002, 'AI 助手',  'sys.menu.ai-assistant',        '/admin/ai-assistant',     NULL, 2, 0, 'ai-assistant:read',    1, 'MessageOutlined',    NULL,                    false, 1, 0, 0),
(2003, 'AI 能力',  'sys.menu.ai-capability',       '/admin/ai-capability',    NULL, 3, 0, 'ai-capability:read',   1, 'RobotOutlined',      NULL,                    false, 1, 0, 0),
(2004, '智能体',   'sys.menu.agent',               '/admin/agent',            NULL, 4, 0, 'agent:read',           1, 'ApartmentOutlined',  NULL,                    false, 1, 0, 0),
(2005, '系统管理', 'sys.menu.system',              '/admin/system',           NULL, 5, 0, 'system:read',         1, 'SettingOutlined',    NULL,                    false, 1, 0, 0),

(2011, '控制台门户', 'sys.menu.console-dashboard',   '/admin/dashboard',           2001, 1, 0, 'console:dashboard:read', 2, 'DashboardOutlined', '/views/admin/system/DashboardPanel.vue',          false, 1, 1, 0),

(2021, '智能对话',   'sys.menu.ai-chat',            '/admin/ai-chat',           2002, 1, 0, 'ai-assistant:chat:read',      2, 'MessageOutlined',    '/views/assistant/components/AssistantPanel.vue', false, 1, 1, 0),
(2022, '会话管理',   'sys.menu.ai-sessions',        '/admin/ai-sessions',       2002, 2, 0, 'ai-assistant:sessions:read',  2, 'CommentOutlined',    '/views/assistant/AiSessionPanel.vue',           false, 1, 1, 0),
(2023, '异步任务',   'sys.menu.async-task-manage',  '/admin/async-task-manage', 2002, 3, 0, 'ai-assistant:async-task:read', 2, 'ClockCircleOutlined', '/views/assistant/AsyncTaskManage.vue',       false, 1, 1, 0),

(2031, '技能管理', 'sys.menu.skill-management',    '/admin/skill-management', 2003, 1, 0, 'ai:skill:read',   2, 'ToolOutlined',      '/views/admin/ai/skill/SkillManagement.vue',      false, 1, 1, 0),
(2032, 'API 密钥', 'sys.menu.apikey',             '/admin/apikey',          2003, 2, 0, 'ai:apikey:read',  2, 'KeyOutlined',       '/views/admin/ai/apikey/ApiKeyManagement.vue',   false, 1, 1, 0),
(2033, '联网搜索', 'sys.menu.web-search',         '/admin/web-search',       2003, 3, 0, 'ai:web-search:read',2, 'SearchOutlined',    '/views/admin/ai/websearch/WebSearchManagement.vue', false, 1, 1, 0),
(2034, '工具管理', 'sys.menu.tool-management',    '/admin/tool-management',  2003, 4, 0, 'ai:tool:read',    2, 'ToolOutlined',      '/views/admin/ai/tool/ToolManagement.vue',       false, 1, 1, 0),
(2035, 'MCP 服务', 'sys.menu.mcp-service',        '/admin/mcp-service',     2003, 5, 0, 'ai:mcp:read',     2, 'NodeIndexOutlined', '/views/admin/ai/mcp/McpServiceManagement.vue',  false, 1, 1, 0),

(2041, '智能体管理', 'sys.menu.agent-management',  '/admin/agent-management', 2004, 1, 0, 'agent:read',             2, 'RobotOutlined',     '/views/admin/agent/AgentManagement.vue',           false, 1, 1, 0),
(2042, '调用记录',   'sys.menu.session-agent',     '/admin/session-agent',    2004, 2, 0, 'agent:execution:read',   2, 'MonitorOutlined',   '/views/admin/agent/AgentExecutionManagement.vue', false, 1, 1, 0),
(2043, '智能体团队', 'sys.menu.agent-team',        '/admin/agent-team',       2004, 3, 0, 'agent-team:read',        2, 'ApartmentOutlined', '/views/admin/agent-team/TeamList.vue',           false, 1, 1, 0),

(2051, '系统设置', 'sys.menu.system-management',   '/admin/system-management',        2005, 1, 0, 'system:management:read', 2, 'SettingOutlined',  '/views/admin/system/SystemManagement.vue',   false, 1, 1, 0),
(2052, '个人信息', 'sys.menu.profile',             '/admin/profile',                 2005, 2, 0, 'profile:read',          2, 'UserOutlined',     '/views/admin/system/ProfilePanel.vue',        false, 1, 1, 0),
(2053, '字典管理', 'sys.menu.dictionary',          '/admin/dictionary',              2005, 3, 0, 'dictionary:dictionaries:read', 2, 'DatabaseOutlined', '/views/admin/system/DictionaryPanel.vue', false, 1, 1, 0),
(2054, '区域管理', 'sys.menu.region',             '/admin/region',                  2005, 4, 0, 'dictionary:regions:read', 2, 'GlobalOutlined',   '/views/admin/system/RegionPanel.vue',        false, 1, 1, 0),
(2055, '租户管理', 'sys.menu.tenant-management',   '/admin/tenant-management',       2005, 5, 0, 'tenant:read',            2, 'BankOutlined',     '/views/admin/system/TenantPanel.vue',        false, 1, 1, 0),
(2056, '租户套餐', 'sys.menu.tenant-package-management', '/admin/tenant-package-management', 2005, 6, 0, 'tenant:package:read',  2, 'AppstoreOutlined', '/views/admin/system/TenantPackagePanel.vue', false, 1, 1, 0);

INSERT INTO "public"."sys_role"
  (role_id, role_name, role_code, description, sort_order, status, is_deleted)
VALUES
(9999, '平台超级管理员', 'super_admin', '系统内置超级管理员，拥有全部菜单与接口权限（*:*）', 1, 'active', false),
(3002, '租户管理员',     'tenant_admin', '租户内管理员，拥有管理控制台全部菜单（不含平台级租户/套餐管理）', 2, 'active', false),
(3003, '运营人员',       'operator',     '日常运营角色：工作台/AI助手/AI能力/智能体可读可用，仅限个人信息，不含系统配置类页面', 3, 'active', false) ON CONFLICT (role_id) DO NOTHING;

INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT 9999, m.id FROM "public"."sys_menu" m
WHERE m.id BETWEEN 2001 AND 2056 AND m.is_deleted = false;

INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT 3002, m.id FROM "public"."sys_menu" m
WHERE m.id BETWEEN 2001 AND 2056
  AND m.id NOT IN (2055, 2056)
  AND m.is_deleted = false;

INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT 3003, m.id FROM "public"."sys_menu" m
WHERE m.id IN (
        2001, 2011,                                          2002, 2021, 2022, 2023,                              2003, 2031, 2032, 2033, 2034, 2035,                  2004, 2041, 2042,                                    2005, 2052                                         )
  AND m.is_deleted = false;

-- ───────────────────────────────────────────────────────
-- 来源：dict_missing_items.sql
-- ───────────────────────────────────────────────────────
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

-- ───────────────────────────────────────────────────────
-- 来源：menu_workflow.sql
-- ───────────────────────────────────────────────────────
INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
(2501, '工作流管理', 'sys.menu.workflow',              '/admin/workflow',              NULL, 7, 0, 'workflow:read',                1, 'ApiOutlined',       NULL,                                              false, 1, 0, 0),
(2502, '工作流列表', 'sys.menu.workflow-management',   '/admin/workflow-management',   2501, 1, 0, 'workflow:flow:read',           2, 'ApiOutlined',       '/views/admin/workflow/WorkflowManagement.vue',    false, 1, 1, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2501 AND 2502) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);

-- ───────────────────────────────────────────────────────
-- 来源：menu_knowledge_governance.sql
-- ───────────────────────────────────────────────────────
INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
(2401, '知识治理',           'knowledge.menu.knowledge', '/admin/knowledge',          NULL, 0, 0, 'kg:read',          1, 'DatabaseOutlined',  NULL, false, 1, 0, 0),
(2403, '工作台',   'knowledge.menu.unified',  '/admin/kg-knowledge-manager', 2401, 1, 0, 'kg:kb:read',       2, 'BookOutlined',      NULL, false, 1, 0, 0),
(2402, '数据源',             'knowledge.menu.dataSource','/admin/kg-data-source',     2401, 2, 0, 'kg:datasource:read',2, 'DatabaseOutlined',  NULL, false, 1, 0, 0),
(2405, '本体',               'knowledge.menu.ontology',  '/admin/kg-ontology',         2401, 3, 0, 'kg:ontology:read', 2, 'ApartmentOutlined', NULL, false, 1, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

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

DELETE FROM "public"."sys_role_menu" WHERE menu_id = 2404;

DELETE FROM "public"."sys_menu" WHERE id = 2404;

UPDATE "public"."sys_menu" SET visible = 0, updated_at = now() WHERE id = 2;

INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2401 AND 2405 AND id <> 2404) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);

-- ───────────────────────────────────────────────────────
-- 来源：menu_duplex_voice.sql
-- ───────────────────────────────────────────────────────
INSERT INTO "public"."sys_menu"
  (id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
SELECT v.*
FROM (VALUES
(2601, '调解语音', 'sys.menu.duplex-voice', '/admin/duplex-voice', NULL, 8, 0, 'duplex:voice:read', 1, 'AudioOutlined', NULL, false, 1, 0, 0),
(2602, '语音 RTC 演示',   'sys.menu.voice-demo',        '/admin/voice-demo',        2601, 1, 0, 'duplex:voice:read',      2, 'AudioOutlined', '/views/duplex/VoiceDemo.vue',                        false, 1, 1, 0),
(2603, '语音角色配置',   'sys.menu.voice-roles',       '/admin/voice-roles',       2601, 2, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/duplex/config/VoiceSessionConfig.vue',  false, 1, 1, 0),
(2604, '语音模型配置',   'sys.menu.voice-models',      '/admin/voice-models',      2601, 3, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/duplex/config/VoiceModelConfig.vue',    false, 1, 1, 0),
(2605, '语音 Agent 配置','sys.menu.voice-agents',      '/admin/voice-agents',      2601, 4, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/ai-config/agents/AgentConfigPanel.vue',    false, 1, 1, 0),
(2606, '语音工具策略',   'sys.menu.voice-tool-policy', '/admin/voice-tool-policy', 2601, 5, 0, 'duplex:voice:config',    2, 'AudioOutlined', '/views/admin/ai/components/ToolPolicyEditor.vue',       false, 1, 1, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);

INSERT INTO "public"."sys_role_menu" (role_id, menu_id)
SELECT r.role_id, m.id
FROM "public"."sys_role" r
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2601 AND 2606) m
WHERE NOT EXISTS (
  SELECT 1 FROM "public"."sys_role_menu" rm
  WHERE rm.role_id = r.role_id AND rm.menu_id = m.id
);

-- ───────────────────────────────────────────────────────
-- 来源：fix_menu_private_kb.sql
-- ───────────────────────────────────────────────────────
UPDATE "public"."sys_menu"
SET path = '/admin/kg-private-kb',
    component = '/views/kms/wiki/index.vue'
WHERE i18n_key = 'knowledge.menu.private.knowledge'
  AND path = '/views/kms/wiki/index.vue';

-- ───────────────────────────────────────────────────────
-- 来源：45_voice_realtime_init.sql
-- ───────────────────────────────────────────────────────
UPDATE ai_chat_model SET type = 7 WHERE type = 6;

INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
SELECT '阿里云 DashScope 实时语音', '', 'DashScope', 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime', 1, 0, now()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_api_key WHERE platform = 'DashScope' AND name = '阿里云 DashScope 实时语音'
);

DO $$
DECLARE
    v_key_id INTEGER;
BEGIN
    SELECT id INTO v_key_id
    FROM ai_api_key
    WHERE platform = 'DashScope' AND name = '阿里云 DashScope 实时语音'
    LIMIT 1;

    IF v_key_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM ai_chat_model WHERE model = 'qwen-audio-3.0-realtime-plus' AND type = 7
    ) THEN
        -- 设为默认前，清除同类型下的其它默认，保证全局单一默认（跨 key）
        UPDATE ai_chat_model
        SET is_default = false
        WHERE type = 7 AND is_default = true;

        INSERT INTO ai_chat_model
            (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
        VALUES
            ('dashscope-realtime', v_key_id,
             '通义千问实时语音 qwen-audio-3.0-realtime-plus',
             'qwen-audio-3.0-realtime-plus', 'DashScope', 0, 1, 7, true, now());
    END IF;
END $$;

-- ───────────────────────────────────────────────────────
-- 来源：46_voice_model_cleanup_and_local_s2s_init.sql
-- ───────────────────────────────────────────────────────
UPDATE ai_chat_model
SET status = 0, is_default = false
WHERE type = 7
  AND (platform = 'DashScope' OR platform IS NULL)
  AND model NOT IN (
      'qwen-audio-3.0-realtime-plus',
      'qwen-audio-3.0-realtime-flash',
      'qwen3.5-omni-flash-realtime',
      'qwen3.5-omni-plus-realtime'
  );

INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
SELECT '阿里云 DashScope 实时语音', '', 'DashScope', 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime', 1, 0, now()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_api_key WHERE platform = 'DashScope' AND name = '阿里云 DashScope 实时语音'
);

DO $$
DECLARE
    v_key_id INTEGER;
BEGIN
    SELECT id INTO v_key_id
    FROM ai_api_key
    WHERE platform = 'DashScope' AND name = '阿里云 DashScope 实时语音'
    LIMIT 1;

    IF v_key_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM ai_chat_model
        WHERE type = 7 AND status = 1 AND platform = 'DashScope'
          AND model IN (
              'qwen-audio-3.0-realtime-plus',
              'qwen-audio-3.0-realtime-flash',
              'qwen3.5-omni-flash-realtime',
              'qwen3.5-omni-plus-realtime'
          )
    ) THEN
        INSERT INTO ai_chat_model
            (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
        VALUES
            ('dashscope-realtime', v_key_id,
             '通义千问实时语音 qwen-audio-3.0-realtime-plus',
             'qwen-audio-3.0-realtime-plus', 'DashScope', 0, 1, 7, false, now());
    END IF;
END $$;

-- 3) 本地 Docker S2S：密钥记录仅承载端点 url（api_key 可留空做可选 Token）
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
SELECT '本地 qwen-audio-s2s（Docker）', '', 's2s', 'ws://127.0.0.1:8765/v1/realtime', 1, 10, now()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_api_key WHERE platform = 's2s' AND name = '本地 qwen-audio-s2s（Docker）'
);

DO $$
DECLARE
    v_key_id INTEGER;
BEGIN
    SELECT id INTO v_key_id
    FROM ai_api_key
    WHERE platform = 's2s' AND name = '本地 qwen-audio-s2s（Docker）'
    LIMIT 1;

    IF v_key_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM ai_chat_model WHERE model = 'qwen-audio-s2s' AND type = 7
    ) THEN
        INSERT INTO ai_chat_model
            (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
        VALUES
            ('local-s2s', v_key_id,
             '本地 qwen-audio-s2s（Docker）',
             'qwen-audio-s2s', 's2s', 10, 1, 7, false, now());
    END IF;
END $$;

-- ───────────────────────────────────────────────────────
-- 来源：47_agent_event_enhance.sql
-- ───────────────────────────────────────────────────────
ALTER TABLE agent_execution_event
    ADD COLUMN IF NOT EXISTS level            SMALLINT,
    ADD COLUMN IF NOT EXISTS category         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS reply_id         VARCHAR(64),
    ADD COLUMN IF NOT EXISTS block_id         VARCHAR(64),
    ADD COLUMN IF NOT EXISTS tool_call_id     VARCHAR(64),
    ADD COLUMN IF NOT EXISTS interrupt_reason VARCHAR(20),
    ADD COLUMN IF NOT EXISTS ui_hint          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS event_version    SMALLINT NOT NULL DEFAULT 1;

COMMENT ON COLUMN agent_execution_event.level IS '最低分发层级 LOG=0/DB=1/STREAM=2/UI=3';

COMMENT ON COLUMN agent_execution_event.category IS '事件分类（EventCategory）';

COMMENT ON COLUMN agent_execution_event.reply_id IS 'AgentScope reply_id';

COMMENT ON COLUMN agent_execution_event.block_id IS '内容块 ID';

COMMENT ON COLUMN agent_execution_event.tool_call_id IS '工具调用关联 ID';

COMMENT ON COLUMN agent_execution_event.interrupt_reason IS 'timeout|user_cancel|system|error';

COMMENT ON COLUMN agent_execution_event.ui_hint IS '前端渲染路由提示';

COMMENT ON COLUMN agent_execution_event.event_version IS '事件格式版本';

CREATE INDEX IF NOT EXISTS idx_event_reply ON agent_execution_event(execution_id, reply_id);

CREATE INDEX IF NOT EXISTS idx_event_category_level ON agent_execution_event(category, level);

ALTER TABLE agent_execution
    ADD COLUMN IF NOT EXISTS finished_reason  VARCHAR(20),
    ADD COLUMN IF NOT EXISTS interrupt_reason VARCHAR(20),
    ADD COLUMN IF NOT EXISTS input_tokens     INT,
    ADD COLUMN IF NOT EXISTS output_tokens    INT,
    ADD COLUMN IF NOT EXISTS iterations       INT;

COMMENT ON COLUMN agent_execution.finished_reason IS 'completed|interrupted|exceed_max_iters|error';

COMMENT ON COLUMN agent_execution.interrupt_reason IS 'timeout|user_cancel|system|error';

COMMENT ON COLUMN agent_execution.input_tokens IS '累计输入 token';

COMMENT ON COLUMN agent_execution.output_tokens IS '累计输出 token';

COMMENT ON COLUMN agent_execution.iterations IS '推理-行动迭代轮数';

COMMENT ON TABLE agent_hitl_pause IS 'Agent/Skill 人机交互暂停记录';

COMMENT ON COLUMN agent_hitl_pause.tenant_id IS '租户ID';

COMMENT ON COLUMN agent_hitl_pause.execution_id IS '执行 ID';

COMMENT ON COLUMN agent_hitl_pause.reply_id IS 'AgentScope reply_id';

COMMENT ON COLUMN agent_hitl_pause.tool_calls IS '待确认工具调用列表（id/name/input）';

COMMENT ON COLUMN agent_hitl_pause.suggested_rules IS '建议授权规则';

COMMENT ON COLUMN agent_hitl_pause.status IS 'waiting/approved/rejected/interrupted';

COMMENT ON COLUMN agent_hitl_pause.accept_rules IS '是否接受授权规则';

COMMENT ON COLUMN agent_hitl_pause.timeout_at IS '超时提示时刻';

COMMENT ON COLUMN agent_hitl_pause.answered_at IS '用户应答时刻';

CREATE INDEX IF NOT EXISTS idx_hitl_execution ON agent_hitl_pause(execution_id);

CREATE INDEX IF NOT EXISTS idx_hitl_status ON agent_hitl_pause(status);

CREATE INDEX IF NOT EXISTS ix_agent_hitl_pause_tenant_id ON agent_hitl_pause(tenant_id);

-- ── 重置自增序列（避免显式 ID 插入后与自增默认值冲突）────
SELECT setval(pg_get_serial_sequence('sys_tenant', 'tenant_id'), COALESCE((SELECT MAX(tenant_id) FROM sys_tenant), 1), true);
SELECT setval(pg_get_serial_sequence('sys_user', 'user_id'), COALESCE((SELECT MAX(user_id) FROM sys_user), 1), true);
SELECT setval(pg_get_serial_sequence('sys_role', 'role_id'), COALESCE((SELECT MAX(role_id) FROM sys_role), 1), true);
SELECT setval(pg_get_serial_sequence('sys_user_role', 'id'), COALESCE((SELECT MAX(id) FROM sys_user_role), 1), true);
SELECT setval(pg_get_serial_sequence('sys_menu', 'id'), COALESCE((SELECT MAX(id) FROM sys_menu), 1), true);
SELECT setval(pg_get_serial_sequence('sys_role_menu', 'id'), COALESCE((SELECT MAX(id) FROM sys_role_menu), 1), true);
SELECT setval(pg_get_serial_sequence('sys_dictionary', 'dict_id'), COALESCE((SELECT MAX(dict_id) FROM sys_dictionary), 1), true);
SELECT setval(pg_get_serial_sequence('sys_dictionary_item', 'item_id'), COALESCE((SELECT MAX(item_id) FROM sys_dictionary_item), 1), true);
SELECT setval(pg_get_serial_sequence('ai_api_key', 'id'), COALESCE((SELECT MAX(id) FROM ai_api_key), 1), true);
SELECT setval(pg_get_serial_sequence('ai_chat_model', 'id'), COALESCE((SELECT MAX(id) FROM ai_chat_model), 1), true);

