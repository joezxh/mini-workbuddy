-- ============================================================================
-- 清空 public 模式下的全部用户表（用于重新执行 init.sql 前）
-- ----------------------------------------------------------------------------
-- 说明：
--   - 仅删除表/视图及其依赖，保留 扩展(vector/pg_trgm)、schema 与权限；
--     init.sql 顶部自带 CREATE EXTENSION IF NOT EXISTS，会自愈扩展。
--   - init.sql 不含 CREATE FUNCTION/TYPE/VIEW/SEQUENCE，故无需额外清理。
--   - 本操作为破坏性操作，会清空 public 下所有数据，请在执行前确认已备份。
-- ============================================================================

DO $$
DECLARE
  r RECORD;
BEGIN
  -- 先删视图（依赖表），再删表（CASCADE 一并删除外键与随表序列）
  FOR r IN (SELECT viewname FROM pg_views WHERE schemaname = 'public') LOOP
    EXECUTE 'DROP VIEW IF EXISTS public.' || quote_ident(r.viewname) || ' CASCADE';
  END LOOP;

  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END
$$;
