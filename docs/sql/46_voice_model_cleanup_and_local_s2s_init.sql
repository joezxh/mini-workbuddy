-- =====================================================================
-- 模块: 语音实时模型 可用性清理 + 本地 S2S 引导数据 (ai_api_key / ai_chat_model)
-- 背景: RTC 演示页下拉列表中出现无效模型名（如 qwen-realtime-v2，为历史
--        测试数据），选中后 DashScope 必然 401；同时需支持本地 Docker 部署的
--        qwen-audio-s2s（OpenAI Realtime GA 协议，见 providers/s2s.py）。
-- 参考: qwen-audio-agent shared/realtime-model-catalog.mjs（有效模型目录）、
--        server/src/voice/providers/s2s.mjs（本地 S2S 端点 ws://127.0.0.1:8765）。
-- 约定: ai_chat_model.type  —— 7=语音实时;  platform —— 'DashScope' / 's2s'
-- 说明: 幂等可执行（重复运行不会重复插入或产生多个默认）。
--       本地 S2S 无需云端 Key；端点记录在 ai_api_key.url，可按实际部署端口修改。
-- =====================================================================

-- 1) 清理：停用 DashScope 平台（含 platform 为空的历史行，密钥平台为 DashScope）
--    下模型名不在官方实时目录内的「语音实时」模型
--    （无效模型名连接必 401，停用后不再出现在下拉列表；不删数据可追溯）
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

-- 2) 有效 DashScope 实时模型：若无任何有效模型则补一条（不抢已有有效默认）
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
