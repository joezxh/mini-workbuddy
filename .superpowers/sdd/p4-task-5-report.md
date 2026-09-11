# Task 5 报告：P2 元数据 → 本体候选生成

- 任务来源：`.superpowers/sdd/p4-task-5-brief.md`（P4 计划 Task 5 + spec §5.3/§8）
- 执行日期：2026-09-10
- 结论：**DONE**（86 passed；阈值单一来源 + 变异验证通过）
- 未执行 `git commit`

## 1. 改动清单

| 路径 | 动作 | 说明 |
|---|---|---|
| `backend/app/services/dataops/__init__.py` | 新建 | P2 服务包预占位 |
| `backend/app/services/dataops/rule_engine.py` | 新建 | **仅含** `CONF_AUTO_ACCEPT=0.85` / `CONF_SUGGEST_MIN=0.65`（P2 计划 Task 12 锁定的定义位置与数值，P4/P2 共用的单一事实来源；P2 实施时在同一文件扩展规则引擎本体） |
| `backend/app/services/ontology/modeling_service.py` | 修改 | 新增 `MetaTableRef` / `MetaColumnRef` / `ColumnPairOverlap` / `CandidateReport` 数据类与 `generate_candidates()` |
| `backend/tests/ontology/test_candidates.py` | 新建 | 8 条测试 |

## 2. 设计要点

- **P2 适配点**：P2 未实施，候选生成输入用抽象数据类（字段对齐 P2 计划的
  `meta_table`/`meta_column` 模型与唯一键 `(source_id, database, table_name)`）。
  P2 落地后补「ORM 行 → 数据类」薄适配即可接入，`generate_candidates` 接口不变。
- **置信度分层**（`_tier()`，语义与 P2 Task 12 参数化示例对齐）：
  `≥0.85 → accepted`（自动接受）、`[0.65, 0.85) → suggested`（人工评审）、
  `<0.65 → 不生成`；`None → suggested`（未评分走人工兜底，仅表/列兜底场景）。
  表候选默认 None（表存在是客观事实）→ suggested，对应 spec §8 的"人工接受"主链路。
- **关系候选**：`overlap_ratio ≥ CONF_SUGGEST_MIN` 才生成；同表对多列对**合并**为
  一个 link_type（code=`rel_<左表>__<右表>`，confidence=最大重叠度，evidence 逐列对
  记录 overlap_ratio）；列对引用的表不存在 → 跳过不报错。
- **幂等**：对象类型/属性/关系/映射全部"存在即跳过"（计入 `skipped`）。
- **溯源**：对象类型候选 `evidence_json` 记 `p2_meta_scan` + source_id/database/table_name；
  mapping 无 evidence 列（spec §5.2），其自身字段即溯源结构。
- 整批在一个 savepoint 内执行（复用 Task 4 复审引入的 `_write`），任何错误整体回滚。

## 3. 测试（8 条）

| 用例 | 验证点 |
|---|---|
| `test_full_chain_table_candidate_then_human_accept` | spec §8 联动全链路：meta_table → suggested 候选 → 人工 accepted → 可查；evidence 可追溯 |
| `test_table_mapping_generated_with_evidence` | 表候选顺带生成 table 级映射 |
| `test_column_confidence_tiers` | 0.90→accepted、0.70→suggested、0.85/0.65 边界（含）、0.50→丢弃、None→suggested |
| `test_link_type_from_column_pairs` | 列对→关系候选、同表对合并、<0.65 丢弃、confidence=最大重叠 |
| `test_link_type_skips_unknown_tables` | 列对引用未知表 → 跳过 |
| `test_generate_candidates_is_idempotent` | 二次生成 created 全 0 + skipped 正确 |
| `test_generate_candidates_tenant_isolated` | 同批元数据跨租户各自生成 |
| `test_thresholds_are_single_sourced` | modeling_service 引用的是 rule_engine 常量本身（`is` 断言），且值 = (0.85, 0.65) |

```
86 passed, 3 warnings in ~54s        （78 旧 + 8 新，全量回归无破坏）
```

## 4. 变异验证

| 变异 | 结果 |
|---|---|
| V5 `>= CONF_AUTO_ACCEPT` → `>` | 边界用例（0.85→accepted）**RED** ✅（还原后 GREEN） |

实施过程修正的两处测试自身问题（非实现缺陷）：mapping 无 `evidence_json` 列（spec 如此）；
`CandidateReport.created` 对零创建的键不存在（改用 `.get` 语义断言）。

## 5. 遗留与提示

1. **P2 Task 12 实施时**：在本文件扩展规则标注本体（PII 识别 / join key 判定等），
   常量保持不动；P2 的 meta ORM 落地后为 `generate_candidates` 补 ORM 适配。
2. 关系候选的合并策略是"同表对合并为一个 link_type"；若 P2 的三方投票（veto/权重）
   产出更细的关系语义，需在适配层扩展 evidence 结构。
3. `CandidateReport` 已为 Task 9 的 `ontology_suggest` Tool 预留（created/skipped 明细可直接序列化）。
