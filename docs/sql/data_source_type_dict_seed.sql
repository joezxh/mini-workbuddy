-- ============================================================================
-- 数据源类型字典一次性写入 SQL（PostgreSQL）
-- dict_code = data_source_type，与 alembic 迁移
--   2026_10_28_0001_seed_data_source_type_dict 等价，数据源为
--   backend/app/services/dataops/source_types.py 的 TYPE_META（单一事实来源）。
-- 特性：幂等（已存在则跳过）、tenant_id 置 NULL（全局字典）。
-- extra_data 携带 family / default_port / fields（前端动态表单声明）。
-- ============================================================================

-- 1) 字典头（sys_dictionary）
INSERT INTO sys_dictionary
    (dict_code, dict_name, dict_type, description, sort_order, is_active, is_deleted)
SELECT 'data_source_type',
       '数据源类型',
       'dataops',
       '数据源管理可选类型；启用/停用即时生效于新建表单下拉',
       0, TRUE, FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM sys_dictionary WHERE dict_code = 'data_source_type'
);

-- 2) 字典项（sys_dictionary_item，11 类，按 sort_order 排序）
INSERT INTO sys_dictionary_item
    (dict_code, item_code, item_name, item_value, level, color, sort_order, is_active, extra_data, is_deleted)
SELECT v.dict_code, v.item_code, v.item_name, v.item_value, v.level,
       v.color, v.sort_order, v.is_active, v.extra_data, v.is_deleted
FROM (VALUES
    -- Excel/CSV：无主机连接，文件上传落本系统 PG 隔离 schema
    ('data_source_type', 'excel', 'Excel/CSV', 'excel', 1, 'green', 1, TRUE,
     '{"family": "excel", "default_port": null, "fields": [{"key": "filename", "label_key": "kbMgmt.ds.excelFile", "type": "upload", "required": true}]}'::json,
     FALSE),
    -- MySQL
    ('data_source_type', 'mysql', 'MySQL', 'mysql', 1, 'blue', 2, TRUE,
     '{"family": "mysql", "default_port": 3306, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "charset", "label_key": "kbMgmt.ds.charset", "type": "string", "default": "utf8mb4"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- Oracle：service_name / sid 双模式
    ('data_source_type', 'oracle', 'Oracle', 'oracle', 1, 'red', 3, TRUE,
     '{"family": "oracle", "default_port": 1521, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "mode", "label_key": "kbMgmt.ds.oracleMode", "type": "select", "options": [{"value": "service_name", "label": "Service Name"}, {"value": "sid", "label": "SID"}], "default": "service_name"}, {"key": "database", "label_key": "kbMgmt.ds.oracleDb", "type": "string"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- PostgreSQL
    ('data_source_type', 'postgresql', 'PostgreSQL', 'postgresql', 1, 'geekblue', 4, TRUE,
     '{"family": "pg", "default_port": 5432, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "dbSchema", "label_key": "kbMgmt.ds.dbSchema", "type": "string", "default": "public"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- SQL Server：顶层作用域是 schema（默认 dbo）
    ('data_source_type', 'sqlserver', 'SQL Server', 'sqlserver', 1, 'purple', 5, TRUE,
     '{"family": "sqlserver", "default_port": 1433, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "dbSchema", "label_key": "kbMgmt.ds.dbSchema", "type": "string", "default": "dbo"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- ClickHouse
    ('data_source_type', 'clickhouse', 'ClickHouse', 'clickhouse', 1, 'gold', 6, TRUE,
     '{"family": "clickhouse", "default_port": 8123, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- 达梦（原生 dmPython，驱动未装时探活返回安装指引）
    ('data_source_type', 'dm', '达梦', 'dm', 1, 'volcano', 7, TRUE,
     '{"family": "dm", "default_port": 5236, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- Apache Doris（MySQL 协议，family=mysql）
    ('data_source_type', 'doris', 'Apache Doris', 'doris', 1, 'cyan', 8, TRUE,
     '{"family": "mysql", "default_port": 9030, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- ElasticSearch：无库层级，scheme 走 http/https 选择
    ('data_source_type', 'es', 'ElasticSearch', 'es', 1, 'lime', 9, TRUE,
     '{"family": "es", "default_port": 9200, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "scheme", "label_key": "kbMgmt.ds.esScheme", "type": "select", "options": [{"value": "http", "label": "HTTP"}, {"value": "https", "label": "HTTPS"}], "default": "http"}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- Kingbase（PG 协议，family=pg）
    ('data_source_type', 'kingbase', 'Kingbase', 'kingbase', 1, 'orange', 10, TRUE,
     '{"family": "pg", "default_port": 54321, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "dbSchema", "label_key": "kbMgmt.ds.dbSchema", "type": "string", "default": "public"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE),
    -- StarRocks（MySQL 协议，family=mysql）
    ('data_source_type', 'starrocks', 'StarRocks', 'starrocks', 1, 'magenta', 11, TRUE,
     '{"family": "mysql", "default_port": 9030, "fields": [{"key": "host", "label_key": "kbMgmt.ds.host", "type": "string", "required": true}, {"key": "port", "label_key": "kbMgmt.ds.port", "type": "number", "required": true}, {"key": "username", "label_key": "kbMgmt.ds.username", "type": "string"}, {"key": "password", "label_key": "kbMgmt.ds.password", "type": "password"}, {"key": "database", "label_key": "kbMgmt.ds.defaultDb", "type": "string"}, {"key": "timeout", "label_key": "kbMgmt.ds.timeout", "type": "number", "default": 30}]}'::json,
     FALSE)
) AS v(dict_code, item_code, item_name, item_value, level, color, sort_order, is_active, extra_data, is_deleted)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_dictionary_item s
    WHERE s.dict_code = v.dict_code AND s.item_code = v.item_code
);

-- 回滚（如需删除本次 seed）：
-- DELETE FROM sys_dictionary_item WHERE dict_code = 'data_source_type';
-- DELETE FROM sys_dictionary      WHERE dict_code = 'data_source_type';
