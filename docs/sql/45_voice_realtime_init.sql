-- =====================================================================
-- 模块: 调解语音实时模型 初始数据 (ai_api_key / ai_chat_model)
-- 参考: qwen-audio-agent 配置 (config/settings.json -> voice.dashscope)
--        model = qwen-audio-3.0-realtime-plus
--        baseUrl = wss://dashscope.aliyuncs.com/api-ws/v1/realtime
-- 约定: ai_chat_model.type  —— 1=对话, 5=向量, 7=语音实时
--        (7 取自前端「模型类别」数据字典 model_type 中“语音模型”的取值)
--        status  —— 1=启用, 0=禁用 ; is_default 为布尔
-- 说明: 幂等可执行（重复运行不会重复插入或产生多个默认）。
--       本脚本仅插入「默认密钥 + 默认语音模型」最小引导数据；
--       请将 ai_api_key.api_key 替换为真实的 DashScope API Key 后再启用连接。
-- =====================================================================

-- 0) 迁移：将早期按 type=6 写入的语音模型归正为 type=7（与数据字典对齐，幂等）
UPDATE ai_chat_model SET type = 7 WHERE type = 6;

-- 1) 默认密钥：阿里云 DashScope 实时语音（已存在则跳过）
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
SELECT '阿里云 DashScope 实时语音', '', 'DashScope', 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime', 1, 0, now()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_api_key WHERE platform = 'DashScope' AND name = '阿里云 DashScope 实时语音'
);


-- 2) 语音实时模型：type=7，设为默认（幂等 + 清除同类已有默认）
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
