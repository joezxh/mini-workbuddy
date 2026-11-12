-- ============================================================================
-- 全双工语音大模型厂商配置种子数据
-- 对应表：ai_api_key（API 密钥） + ai_chat_model（模型，type=7 语音实时）
--
-- 使用方法：
--   1. 将下方各厂商的 api_key 占位符替换为真实密钥后执行；
--   2. 或仅执行厂商对应的 INSERT 段；
--   3. 幂等（upsert）：
--      - ai_api_key 按 platform 去重：已存在则仅更新 name/url/status/sort，
--        **不覆盖 api_key**（保留用户已配置的真实密钥）；
--      - ai_chat_model 按 code 去重：已存在则更新全部字段。
--
-- 前置：脚本开头会为 ai_api_key(platform) 与 ai_chat_model(code) 添加唯一约束，
--       若已存在重复数据，保留 id 最大的一行并删除其余重复行。
--
-- 模型清单来源：各厂商官方文档（2025–2026），仅含官方发布的全双工语音大模型。
-- 目录查询见：backend/app/duplex/voice/voice_catalog.py（get_provider_catalog）
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. 唯一约束（幂等创建）+ 重复数据清理（保留 id 最大的一行）
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    -- ai_api_key.platform 唯一约束
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_ai_api_key_platform'
    ) THEN
        -- 清理同 platform 的重复行，保留 id 最大的一行
        DELETE FROM ai_api_key
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY platform ORDER BY id DESC) AS rn
                FROM ai_api_key
            ) t WHERE rn > 1
        );
        ALTER TABLE ai_api_key ADD CONSTRAINT uq_ai_api_key_platform UNIQUE (platform);
    END IF;

    -- ai_chat_model.code 唯一约束
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_ai_chat_model_code'
    ) THEN
        -- 清理同 code 的重复行，保留 id 最大的一行（NULL code 不参与唯一约束）
        DELETE FROM ai_chat_model
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY code ORDER BY id DESC) AS rn
                FROM ai_chat_model
                WHERE code IS NOT NULL
            ) t WHERE rn > 1
        );
        ALTER TABLE ai_chat_model ADD CONSTRAINT uq_ai_chat_model_code UNIQUE (code);
    END IF;
END $$;


-- ----------------------------------------------------------------------------
-- 1. 阿里云 百炼 (DashScope)
--    默认端点：wss://dashscope.aliyuncs.com/api-ws/v1/realtime
--    Key 申请：https://dashscope.console.aliyun.com/apiKey
-- ----------------------------------------------------------------------------
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
VALUES (
  '阿里云 百炼 - 全双工语音',
  'sk-xxxxxxxxxxxxxxxxxxxxxxxx',  -- TODO: 替换为真实 DashScope API Key
  'DashScope',
  'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
  1, 100, now()
)
ON CONFLICT (platform) DO UPDATE SET
  name = EXCLUDED.name,
  url = EXCLUDED.url,
  status = EXCLUDED.status,
  sort = EXCLUDED.sort,
  updated_at = now();
-- 注意：DO UPDATE 不包含 api_key，保留用户已配置的真实密钥

WITH ds_key AS (SELECT id FROM ai_api_key WHERE platform = 'DashScope' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-dashscope-qwen3.8-omni-flash-realtime',
  ds_key.id, 'Qwen3.8-Omni-Flash-Realtime（推荐）',
  'qwen3.8-omni-flash-realtime', 'DashScope', 100, 1, 7, true, now()
FROM ds_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id,
  name = EXCLUDED.name,
  model = EXCLUDED.model,
  platform = EXCLUDED.platform,
  sort = EXCLUDED.sort,
  status = EXCLUDED.status,
  type = EXCLUDED.type,
  is_default = EXCLUDED.is_default,
  updated_at = now();

WITH ds_key AS (SELECT id FROM ai_api_key WHERE platform = 'DashScope' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-dashscope-qwen-audio-3.1-realtime-plus',
  ds_key.id, 'Qwen-Audio-3.1-Realtime-Plus',
  'qwen-audio-3.1-realtime-plus', 'DashScope', 90, 1, 7, false, now()
FROM ds_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH ds_key AS (SELECT id FROM ai_api_key WHERE platform = 'DashScope' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-dashscope-qwen-audio-3.1-realtime-flash',
  ds_key.id, 'Qwen-Audio-3.1-Realtime-Flash',
  'qwen-audio-3.1-realtime-flash', 'DashScope', 80, 1, 7, false, now()
FROM ds_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH ds_key AS (SELECT id FROM ai_api_key WHERE platform = 'DashScope' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-dashscope-qwen3.5-omni-flash-realtime',
  ds_key.id, 'Qwen3.5-Omni-Flash-Realtime',
  'qwen3.5-omni-flash-realtime', 'DashScope', 70, 1, 7, false, now()
FROM ds_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH ds_key AS (SELECT id FROM ai_api_key WHERE platform = 'DashScope' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-dashscope-qwen3.5-omni-plus-realtime',
  ds_key.id, 'Qwen3.5-Omni-Plus-Realtime',
  'qwen3.5-omni-plus-realtime', 'DashScope', 60, 1, 7, false, now()
FROM ds_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();


-- ----------------------------------------------------------------------------
-- 2. OpenAI Realtime
--    默认端点：wss://api.openai.com/v1/realtime
--    Key 申请：https://platform.openai.com/api-keys
-- ----------------------------------------------------------------------------
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
VALUES (
  'OpenAI - Realtime 语音',
  'sk-xxxxxxxxxxxxxxxxxxxxxxxx',  -- TODO: 替换为真实 OpenAI API Key
  'openai',
  'wss://api.openai.com/v1/realtime',
  1, 90, now()
)
ON CONFLICT (platform) DO UPDATE SET
  name = EXCLUDED.name, url = EXCLUDED.url, status = EXCLUDED.status,
  sort = EXCLUDED.sort, updated_at = now();

WITH oai_key AS (SELECT id FROM ai_api_key WHERE platform = 'openai' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-openai-gpt-realtime-2-1',
  oai_key.id, 'GPT Realtime 2.1',
  'gpt-realtime-2.1', 'openai', 100, 1, 7, true, now()
FROM oai_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH oai_key AS (SELECT id FROM ai_api_key WHERE platform = 'openai' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-openai-gpt-realtime-2-1-mini',
  oai_key.id, 'GPT Realtime 2.1 Mini',
  'gpt-realtime-2.1-mini', 'openai', 90, 1, 7, false, now()
FROM oai_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH oai_key AS (SELECT id FROM ai_api_key WHERE platform = 'openai' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-openai-gpt-realtime-mini',
  oai_key.id, 'GPT Realtime Mini',
  'gpt-realtime-mini', 'openai', 80, 1, 7, false, now()
FROM oai_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();


-- ----------------------------------------------------------------------------
-- 3. Google Gemini Live
--    默认端点：wss://generativelanguage.googleapis.com/ws/...
--    Key 申请：https://aistudio.google.com/app/apikey
-- ----------------------------------------------------------------------------
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
VALUES (
  'Google - Gemini Live',
  'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  -- TODO: 替换为真实 Google API Key
  'google',
  'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent',
  1, 80, now()
)
ON CONFLICT (platform) DO UPDATE SET
  name = EXCLUDED.name, url = EXCLUDED.url, status = EXCLUDED.status,
  sort = EXCLUDED.sort, updated_at = now();

WITH gg_key AS (SELECT id FROM ai_api_key WHERE platform = 'google' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-google-gemini-3-8-live',
  gg_key.id, 'Gemini 3.8 Live',
  'gemini-3.8-live', 'google', 100, 1, 7, true, now()
FROM gg_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH gg_key AS (SELECT id FROM ai_api_key WHERE platform = 'google' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-google-gemini-3-8-live-extended-thinking',
  gg_key.id, 'Gemini 3.8 Live Extended Thinking',
  'gemini-3.8-live-extended-thinking', 'google', 90, 1, 7, false, now()
FROM gg_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH gg_key AS (SELECT id FROM ai_api_key WHERE platform = 'google' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-google-gemini-2-5-flash-live',
  gg_key.id, 'Gemini 2.5 Flash Live (native audio)',
  'gemini-2.5-flash-live-native-audio', 'google', 80, 1, 7, false, now()
FROM gg_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();


-- ----------------------------------------------------------------------------
-- 4. 字节跳动 / 火山引擎 豆包 (Volcengine)
--    默认端点：wss://openspeech.bytedance.com/api/v3/sauc
--    Key 申请：https://console.volcengine.com/iam/keymanage
-- ----------------------------------------------------------------------------
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
VALUES (
  '火山引擎 豆包 - 实时语音',
  'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  -- TODO: 替换为真实火山引擎 Access Key
  'volcengine',
  'wss://openspeech.bytedance.com/api/v3/sauc',
  1, 70, now()
)
ON CONFLICT (platform) DO UPDATE SET
  name = EXCLUDED.name, url = EXCLUDED.url, status = EXCLUDED.status,
  sort = EXCLUDED.sort, updated_at = now();

WITH vc_key AS (SELECT id FROM ai_api_key WHERE platform = 'volcengine' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-volcengine-doubao-seed-realtimevoice',
  vc_key.id, 'Doubao-Seed-RealtimeVoice（豆包实时语音）',
  'doubao-seed-realtimevoice', 'volcengine', 100, 1, 7, true, now()
FROM vc_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();

WITH vc_key AS (SELECT id FROM ai_api_key WHERE platform = 'volcengine' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-volcengine-doubao-seed-1-6-realtimevoice',
  vc_key.id, 'Doubao-Seed-1.6-RealtimeVoice（2.0）',
  'doubao-seed-1-6-realtimevoice', 'volcengine', 90, 1, 7, false, now()
FROM vc_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();


-- ----------------------------------------------------------------------------
-- 5. 讯飞 星火 (iFlytek)
--    默认端点：wss://maas-api.cn-huabei-1.xf-yun.com/v1.1/chat
--    Key 申请：https://www.xfyun.cn/services/voiceservice
-- ----------------------------------------------------------------------------
INSERT INTO ai_api_key (name, api_key, platform, url, status, sort, created_at)
VALUES (
  '讯飞 星火 - 超拟人交互',
  'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',  -- TODO: 替换为真实讯飞 API Key
  'iflytek',
  'wss://maas-api.cn-huabei-1.xf-yun.com/v1.1/chat',
  1, 60, now()
)
ON CONFLICT (platform) DO UPDATE SET
  name = EXCLUDED.name, url = EXCLUDED.url, status = EXCLUDED.status,
  sort = EXCLUDED.sort, updated_at = now();

WITH xf_key AS (SELECT id FROM ai_api_key WHERE platform = 'iflytek' ORDER BY id DESC LIMIT 1)
INSERT INTO ai_chat_model (code, key_id, name, model, platform, sort, status, type, is_default, created_at)
SELECT
  'voice-iflytek-spark-ultra-human',
  xf_key.id, '星火超拟人交互（端到端语音对话）',
  'spark-ultra-human', 'iflytek', 100, 1, 7, true, now()
FROM xf_key
ON CONFLICT (code) DO UPDATE SET
  key_id = EXCLUDED.key_id, name = EXCLUDED.name, model = EXCLUDED.model,
  platform = EXCLUDED.platform, sort = EXCLUDED.sort, status = EXCLUDED.status,
  type = EXCLUDED.type, is_default = EXCLUDED.is_default, updated_at = now();
