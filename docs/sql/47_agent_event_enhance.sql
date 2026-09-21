-- 47: Agent 事件体系增强（spec 2026-09-21 §6.1）
-- ⚠️ MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，本脚本只能执行一次。
-- 执行前请确认 47 号未应用过。

-- agent_execution_event：分级与三级关联
ALTER TABLE agent_execution_event
    ADD COLUMN level           SMALLINT     NULL COMMENT '最低分发层级 LOG=0/DB=1/STREAM=2/UI=3',
    ADD COLUMN category        VARCHAR(20)  NULL COMMENT '事件分类（EventCategory）',
    ADD COLUMN reply_id        VARCHAR(64)  NULL COMMENT 'AgentScope reply_id',
    ADD COLUMN block_id        VARCHAR(64)  NULL COMMENT '内容块 ID',
    ADD COLUMN tool_call_id    VARCHAR(64)  NULL COMMENT '工具调用关联 ID',
    ADD COLUMN interrupt_reason VARCHAR(20) NULL COMMENT 'timeout|user_cancel|system|error',
    ADD COLUMN ui_hint         VARCHAR(20)  NULL COMMENT '前端渲染路由提示',
    ADD COLUMN event_version   SMALLINT     NOT NULL DEFAULT 1 COMMENT '事件格式版本';

CREATE INDEX idx_event_reply ON agent_execution_event(execution_id, reply_id);
CREATE INDEX idx_event_category_level ON agent_execution_event(category, level);

-- agent_execution：结束原因与用量
ALTER TABLE agent_execution
    ADD COLUMN finished_reason  VARCHAR(20) NULL COMMENT 'completed|interrupted|exceed_max_iters|error',
    ADD COLUMN interrupt_reason VARCHAR(20) NULL COMMENT 'timeout|user_cancel|system|error',
    ADD COLUMN input_tokens     INT NULL COMMENT '累计输入 token',
    ADD COLUMN output_tokens    INT NULL COMMENT '累计输出 token',
    ADD COLUMN iterations       INT NULL COMMENT '推理-行动迭代轮数';

-- agent_hitl_pause：HITL 暂停记录（模型此前被移除、service 存在悬空引用，本 DDL 重建；spec §5.4/§5.5）
CREATE TABLE IF NOT EXISTS agent_hitl_pause (
    id              BIGINT      PRIMARY KEY AUTO_INCREMENT,
    execution_id    VARCHAR(64) NOT NULL COMMENT '执行 ID',
    reply_id        VARCHAR(64) NULL COMMENT 'AgentScope reply_id',
    tool_calls      JSON        NULL COMMENT '待确认工具调用列表（id/name/input）',
    suggested_rules JSON        NULL COMMENT '建议授权规则',
    status          VARCHAR(20) NOT NULL DEFAULT 'waiting' COMMENT 'waiting/approved/rejected/interrupted',
    accept_rules    TINYINT(1)  NOT NULL DEFAULT 0 COMMENT '是否接受授权规则',
    timeout_at      DATETIME    NULL COMMENT '超时提示时刻',
    answered_at     DATETIME    NULL COMMENT '用户应答时刻',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hitl_execution (execution_id),
    INDEX idx_hitl_status (status)
) COMMENT 'Agent/Skill 人机交互暂停记录';
