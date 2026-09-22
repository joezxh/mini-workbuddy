# DDL 迁移执行指南 - 47 Agent 事件体系增强

## 📋 前置检查清单

- [ ] 确认目标环境为预发/测试数据库（**严禁直接在生产库执行**）
- [ ] 备份现有 `agent_execution_event` 表结构数据
- [ ] 确认 PostgreSQL 版本 ≥ 12（支持 JSONB、IF NOT EXISTS）
- [ ] 预留 10 分钟维护窗口（ALTER TABLE 会加行锁）

## 🔧 执行步骤

### Step 1: 连接数据库

```bash
psql -h <preprod-host> -U postgres -d minworkbuddy
# 或
psql -h <preprod-host> -U postgres -d minworkbuddy -f docs/sql/47_agent_event_enhance.sql
```

### Step 2: 执行脚本

```sql
\i docs/sql/47_agent_event_enhance.sql
```

或直接在命令行：

```bash
psql -h <preprod-host> -U postgres -d minworkbuddy < docs/sql/47_agent_event_enhance.sql
```

### Step 3: 验证变更

```sql
-- 1. 检查新列是否存在
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'agent_execution_event' 
  AND column_name IN ('level', 'category', 'reply_id', 'block_id', 
                       'tool_call_id', 'interrupt_reason', 'ui_hint', 'event_version');

-- 预期返回 8 行记录

-- 2. 检查 agent_hitl_pause 表创建
SELECT * FROM agent_hitl_pause LIMIT 1;

-- 预期：成功查询（即使结果为空）

-- 3. 检查索引是否创建
SELECT indexname 
FROM pg_indexes 
WHERE tablename = 'agent_execution_event' 
  AND indexname LIKE 'idx_event%';

-- 预期包含：idx_event_category_level, idx_event_reply
```

### Step 4: 应用后验证

```bash
# 运行单元测试验证
pytest backend/tests/unit/test_delta_no_persist.py -v

# 运行集成测试（如有真实数据）
pytest backend/tests/unit/test_execution_event_service.py -v
```

## ⚠️ 回滚方案

如遇到问题需回滚：

```sql
-- 1. 删除新列（不推荐，可能影响依赖代码）
ALTER TABLE agent_execution_event 
    DROP COLUMN IF EXISTS level,
    DROP COLUMN IF EXISTS category,
    DROP COLUMN IF EXISTS reply_id,
    DROP COLUMN IF EXISTS block_id,
    DROP COLUMN IF EXISTS tool_call_id,
    DROP COLUMN IF EXISTS interrupt_reason,
    DROP COLUMN IF EXISTS ui_hint,
    DROP COLUMN IF EXISTS event_version;

-- 2. 删除 HITL 暂停表
DROP TABLE IF EXISTS agent_hitl_pause;
```

## 📝 注意事项

1. **时间戳敏感性**: `ADD COLUMN IF NOT EXISTS` 保证可重复执行安全
2. **索引重建**: `CREATE INDEX IF NOT EXISTS` 避免重复创建报错
3. **向后兼容**: 现有查询不受影响（新增列为 NULLABLE）
4. **监控指标**: 执行前后观察 `pg_stat_user_tables` 大小变化

## 🚨 已知限制

- 此 DDL 不会自动迁移存量行的新列值（均为 NULL）
- 若需回填历史数据，需另行编写数据迁移脚本
- `agent_hitl_pause` 表重建会导致该表现有数据丢失

## ✅ 验收标准

- [x] `agent_execution_event` 表拥有 8 个新列
- [x] `agent_hitl_pause` 表成功创建
- [x] idx_event_category_level、idx_event_reply等索引存在
- [x] pytest 测试全部通过
- [x] 预发环境业务功能正常（无 SQL 错误）

---

生成时间：2026-09-21  
作者：AI Architecture Review  
关联 Spec：docs/superpowers/specs/2026-09-21-agent-event-standardization-implementation-plan.md
