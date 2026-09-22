-- 47: Agent 事件体系增强（spec 2026-09-21 §6.1）
-- PostgreSQL 方言（与 45/46 号脚本、alembic env.py 一致）。
-- ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS 保证可重复执行。

-- agent_execution_event：分级与三级关联
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

-- agent_execution：结束原因与用量
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

-- agent_hitl_pause：HITL 暂停记录（模型此前被移除、service 存在悬空引用，本 DDL 重建；spec §5.4/§5.5）
CREATE TABLE IF NOT EXISTS agent_hitl_pause (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       INT8,
    execution_id    VARCHAR(64) NOT NULL,
    reply_id        VARCHAR(64),
    tool_calls      JSONB,
    suggested_rules JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'waiting',
    accept_rules    SMALLINT NOT NULL DEFAULT 0,
    timeout_at      TIMESTAMP,
    answered_at     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
-- 与 TenantMixin 的 index=True 生成的默认索引名对齐
CREATE INDEX IF NOT EXISTS ix_agent_hitl_pause_tenant_id ON agent_hitl_pause(tenant_id);
