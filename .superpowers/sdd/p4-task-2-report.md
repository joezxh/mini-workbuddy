# P4.2 建模六表与 CQ 一致性 —— 实施报告

- 任务来源：`.superpowers/sdd/p4-task-2-brief.md`（P4 计划 Task 4 + spec §5.2）
- 执行日期：2026-09-10
- 结论：**DONE**（74 passed；迁移实跑 + 幂等验证通过；3 组变异验证新用例有效）
- 未执行 `git commit`（改动保留在工作区）
- 复审注意：**本次实施由主 agent 直接执行**（原因：`gsd-code-fixer` 的强制
  worktree/commit 内置流程与「禁止 git 写操作」约束冲突，上一轮曾被中断，
  见 `p4-task-1-report-r3.md` §0）。

## 1. 改动清单

### 新建

| 路径 | 说明 |
|---|---|
| `backend/app/models/ontology/model.py` | 六张建模表：`ontology_object_type`（自引用父子层级）/ `ontology_property` / `ontology_link_type`（两端 FK + cardinality）/ `ontology_mapping` / `ontology_cq` / `ontology_version`（仅表结构，快照逻辑是 Task 6） |
| `backend/alembic/versions/2026_09_10_0001-005_add_ontology_modeling_tables.py` | 迁移（revises 004）：六表 + 顺带 MI-04 重复索引清理 + `ontology_class.uri` 列宽 1000→500 |
| `backend/app/services/ontology/modeling_service.py` | `ModelingService`：对象类型/属性/关系/映射/CQ 的租户安全 CRUD + `cq_coverage()` |
| `backend/tests/ontology/test_modeling.py` | 14 条测试（CQ 覆盖度 / 租户隔离 / 各类校验 / 持久化） |

### 修改

| 路径 | 说明 |
|---|---|
| `backend/app/db/init_models.py` | 登记六个新模型 |
| `backend/app/models/ontology/ontology.py` | 删手动 `idx_ontology_tenant`（与 TenantMixin 自动索引重复，MI-04）；`uri` 列宽 1000→500 |
| `backend/app/services/ontology/ontology_repository.py` | 删 `append_ttl_content()`（单一真相源后死代码）；`MAX_URI_LENGTH` 1000→500；新增 `OntologyStoreProtocol`（MI-08，结构化协议，两个后端无需显式继承） |
| `backend/app/ai/knowledge/owl_engine.py` | store 类型注解改用 `OntologyStoreProtocol` |
| `backend/tests/ontology/conftest.py` | `_tables()` 加入六张新表；删空转的 `_reset_legacy_singleton`（autouse） |
| `backend/tests/ontology/test_persistence.py` | 删 2 处 `pytest.importorskip`（模型必在） |
| `backend/tests/ontology/test_ttl_roundtrip.py` | `import pytest` 提到模块顶部 |

## 2. 关键设计

- **租户安全（六表无 tenant_id 的安全前提）**：`ModelingService` 全部方法走
  「`tenant_id + code` → 解析 ontology 行 → 用其 `ontology_id` 过滤子表」链路，
  不接收裸 `ontology_id`。读路径 `_resolve_ontology(create=False)` **不建行**；
  写路径经 `OntologyRepository.get_or_create_ontology()` 幂等创建（复用 P4.1 的
  savepoint + IntegrityError 兜底）。变异 V2 证明隔离测试真实有效。
- **cq_coverage 口径**（计划示例为权威）：`linked_object_types` 非空的 active CQ 数
  ÷ active CQ 总数；无 CQ 返回 `0.0`。`linked_object_types` 存对象类型 **code**
  （建模语言，快照可读），写入时校验存在性。
- **校验**：评审状态 ∈ suggested|accepted|rejected（可逆流转）；source ∈ rule|human|llm
  （llm 保留取值不产生）；cardinality ∈ 1:1|1:N|N:1|N:M；mapping `target_type=column`
  时 `column_name` 必填；各类 code 重复、悬空引用均抛 `ModelingError(ValueError)`。
- **auto_commit**：与 P4.1 一致，支持批量写场景由调用方在一个事务里收口。

## 3. Minor 清单处理结果（简报 6 条全闭环）

| # | 事项 | 结果 |
|---|---|---|
| MI-04 | `ontology.tenant_id` 重复索引 | 模型删手动索引 + 迁移 `DROP INDEX IF EXISTS idx_ontology_tenant`，实跑验证已消失 |
| MI-01 | TTL 语言标记 | **决策：不加语言列**。`ttl_content` 原文已保真（Literal lang 保留），导出路径不受影响；仅索引丢 lang，且索引随时可从原文重建。若前端/检索未来需要再加列 |
| — | `append_ttl_content` 死代码 | PG 版 + InMemory 版均删除 |
| — | 测试卫生 | `importorskip` ×2、`_reset_legacy_singleton`、函数体内 `import pytest` 均清理；`_tables()` 无 try-except（此前已不存） |
| — | `uri String(1000)` btree 上限 | **决策：收敛到 500**（500×3=1500 < 2704），迁移 `ALTER COLUMN TYPE varchar(500)`，`MAX_URI_LENGTH` 同步 500，入库校验兜底 |
| MI-08 | Protocol 抽取 | 新增 `OntologyStoreProtocol`（get_class/list_classes/upsert_class/unregister/annotation×3/ttl×2），`WikiOwlEngine` 注解改用它 |

## 4. 测试

### 全量（PG 17.11 / minworkbuddy_test / schema-per-test）

```
74 passed, 3 warnings in ~46s
```

（P4.1 的 60 条 + 新增 14 条，无一条旧用例被改松或删除）

### 迁移验证（临时库 `minworkbuddy_migrate_check`，已删除）

alembic 链从 001 起为增量迁移（基础表由 init.sql/create_all 负责），故按真实路径验证：
`create_all 建基础表（排除六表）→ stamp 004 → upgrade head（只跑 005）`：

- 六表全部创建；`linked_object_types` / `snapshot_json` 等实为 jsonb
- **0 个 PG ENUM**（约束 5）
- `idx_ontology_tenant` 已消失（MI-04）；`ontology_class.uri` maxlen=500
- **幂等重跑通过**（drop alembic_version → re-stamp 004 → upgrade，exit=0）

### 变异测试（每组验证后即还原，残留检查 = 0）

| 变异 | 模拟 | 结果 |
|---|---|---|
| V1 `cq_coverage` 全算已覆盖 | 口径失效 | 覆盖度 2 条 **RED** ✅ |
| V2 `_resolve_ontology` 去掉 tenant_id 过滤 | 跨租户串数据 | 隔离用例 **RED** ✅ |
| V3 `add_object_type` 删重复校验 | 唯一性失守（仅剩 DB 约束抛 IntegrityError） | **RED** ✅ |

## 5. 约束遵守

| 约束 | 结论 |
|---|---|
| 不引入新依赖 | ✅ |
| 六表字段以 spec §5.2 为权威 | ✅ |
| 状态用 String(32) 禁 SAEnum | ✅（迁移实跑验证 0 ENUM） |
| 迁移幂等 | ✅ |
| 不做路由 / Tool / 候选生成 / 快照逻辑 / LLM 通道 | ✅ 未越界 |
| 不执行 git 写操作 | ✅ |

## 6. 遗留与提示

1. `ontology_version` 只有表结构，快照生成/对比/回滚在 Task 6。
2. `ModelingService` 尚无 REST 暴露——P4 前端管理台（知识治理）任务接入时需补路由层
   （`ModelingError` 已按 ValueError 子类设计，路由可统一 400）。
3. Task 5 实现候选生成时，须复用 P2 的 `rule_engine.CONF_AUTO_ACCEPT` / `CONF_SUGGEST_MIN`，
   并往 `evidence_json` 写入证据（本表结构已就绪）。
