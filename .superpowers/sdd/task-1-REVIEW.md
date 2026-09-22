# Task 1 Review: DDL 47 + ORM 新列 + AgentHitlPause

**Base:** 637d441 · **Head:** f5be34d · **Depth:** standard（逐列核对 + 定点风险检查）

## Spec Compliance

✅ Spec compliant — brief 全部步骤（1/1b/2/3/5）逐条落地，且忠实于 brief 原文；无 Python 枚举改动；DDL 位于仓库根 `docs/sql/`；`init_models.py` 注册位置正确（`AgentExecutionEvent` 之后）。验证结果（import 冒烟 + 92 通过）来自实现者报告，未复跑（按门禁约定），但代码静态可证 import 链正确。

## 检查记录（named risks）

1. **风险：DDL 建表缺 `tenant_id` 而 ORM 继承 TenantMixin** → 查 `backend/app/models/tenant_mixin.py:14`（tenant_id, index=True）与 `docs/sql/init.sql:750`（既有 agent 表均含 tenant_id）。证实为 DDL/ORM 漂移。
2. **风险：DDL 47 为 MySQL 方言，与仓库其余 DDL 不符** → 查 `docs/sql/45_voice_realtime_init.sql:26`（`DO $$` PG 语法）、`backend/alembic/env.py:36`（硬编码 `postgresql://`）、`backend/README.md:64`（DATABASE_URL 为 postgresql）。仓库证据指向 PostgreSQL，与 brief 声称的 MySQL 8 冲突。

## Strengths

- 逐字忠实 brief：8+5 列、2 索引、DDL 头部一次性警告均与 brief 一致。
- `init_models.py` 注册位置正确（diff 行 23，紧跟 `AgentExecutionEvent`）。
- 未触碰 `ExecutionEventType` 枚举（diff 上下文可见其未改动）——严守任务边界。
- 修正了 brief Step 5 `git add` 漏列 2 个文件的笔误并如实上报——正确判断。

## Issues

### Important

1. **（plan-mandated）`agent_hitl_pause` DDL 缺 `tenant_id` 列及其索引**
   `docs/sql/47_agent_event_enhance.sql:28-40` vs `backend/app/models/agent/agent_hitl_pause.py:14`（TenantMixin → tenant_id, index=True）。
   仓库所有既有 agent 表 DDL 均含 `tenant_id`（`docs/sql/init.sql:750`）。DDL 执行后，ORM 对 `tenant_id` 的任何过滤/赋值将报 Unknown column。
   修复：DDL 增 `tenant_id BIGINT NULL` + `INDEX idx_hitl_tenant (tenant_id)`。DDL 尚未应用，趁现在改零成本。

2. **（plan-mandated / ⚠️ 需确认）DDL 47 方言与仓库实际数据库疑似冲突**
   脚本使用 `AUTO_INCREMENT` / `TINYINT(1)` / 行内 `COMMENT` —— 纯 MySQL 语法，在 PostgreSQL 上全部非法。但 `backend/alembic/env.py:36` 与 `backend/README.md:64` 均指向 PostgreSQL，同级 45/46 号脚本也是 PG 语法。brief 声称 MySQL 8，二者必有一错。
   修复：与 plan 作者确认目标库；若为 PG，需重写为 PG 方言（`SERIAL`/`SMALLINT`/`COMMENT ON COLUMN`）后再合入。

### Minor

3. **DDL 与 ORM 索引声明漂移**：DDL 有 `idx_hitl_status(status)`，ORM 无对应 `Index`；ORM `execution_id index=True` 会生成 `ix_agent_hitl_pause_execution_id` 而非 DDL 的 `idx_hitl_execution`。仅在 create_all/autogenerate 场景才暴露。
   `backend/app/models/agent/agent_hitl_pause.py:16` / `docs/sql/47_agent_event_enhance.sql:36-37`。建议改用 `__table_args__` 显式命名索引（与 `agent_execution_event.py` 模式一致）。

4. **`accept_rules` 类型不一致**：DDL `TINYINT(1)`（47:36）vs ORM `SmallInteger`（SMALLINT）。brief 两侧原文如此，功能兼容，仅类型宽度漂移。

## Assessment

**Task quality:** Approved（附条件）
**Reasoning:** ORM 侧逐列对齐、注册、边界控制全部正确；两条 Important 均为 brief 原文自带的缺陷（tenant_id 缺列、方言存疑），在 DDL 实际应用前必须澄清/修正，但不动摇本任务的实现质量。
