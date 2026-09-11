# P4.2 代码复审报告

- 复审日期：2026-09-10
- 复审方式：**主 agent 执行**（复审 subagent 两次被平台中断 `code=10003`，其留下的
  探针脚本 `_rev_tmp*.py` 被接管复用；脚本设计质量很高，租户攻击面与校验缺口探针
  均已跑通并固化为回归测试）
- 复审范围：工作区未提交改动（`git diff HEAD -- backend/`，P4.2 全部）
- 验证环境：PostgreSQL 17.11 / `minworkbuddy_test`（schema-per-test）
- **总体结论：DONE_WITH_CONCERNS → 复审发现的问题已当场全部修复，现为 DONE**

> 复审期间的重大插曲：中断的复审 agent 曾把全套表**误建进 `public` schema 并写入数据**
> （其临时脚本的 search_path 隔离失效），导致探针结果被污染（假"已存在"）。
> 已清理 public 全部残留表 + 3 个 probe_* schema，探针在干净环境重跑。

## 1. 租户安全审查（攻击者视角，全部通过 ✅）

探针实测（已固化为 `test_modeling.py` 的隔离用例）：

| 攻击向量 | 结果 |
|---|---|
| B 读 A 的对象类型/CQ/属性/关系/映射、coverage | 全部为空 ✅ |
| B 改 A 的对象类型状态 / 加属性 / 建关系 / 建映射 / 引用 A 的 code | 全部 `ModelingError` 被拒 ✅ |
| B 用自定义 code 建本体，A 用同 code 访问 | 不可见 ✅ |
| 本体行幂等创建（多次写仅 1 行） | ✅ |
| `auto_commit=False` + rollback 无残留 | ✅ |

`ModelingService` 无任何方法接收裸 `ontology_id`；子表查询全部经由
「tenant_id + code → ontology.id」链路。**未发现绕过路径。**

## 2. 数据模型与迁移审查 ✅

- 六表字段与 spec §5.2 逐一比对一致（实施报告 §2）
- 005 迁移在临时库实跑通过（六表/jsonb/0 ENUM/MI-04 索引已删/uri=500/FK ondelete
  CASCADE 与 SET NULL 抽查正确）+ 幂等重跑通过
- `wiki_owl` 路由确认 `enabled=False`，`ontology_class.uri` 1000→500 的 ALTER 无存量风险

## 3. 复审发现的问题（**已全部修复**）

| ID | 严重度 | 问题 | 修复 |
|---|---|---|---|
| R3-01 | Major | **校验失败留下孤儿本体行**：`_require_ontology()` 幂等创建本体行后，其后的库依赖校验（悬空对象类型/跨租户引用被拒）抛 `ModelingError`，已 INSERT 的本体行留在事务里，随调用方后续 commit 入库（探针实证 0→1） | `ModelingService._write()`：所有写方法主体包进 `begin_nested()` savepoint，失败回滚 savepoint——既不留孤儿行也不毁调用方事务；仓储侧强制 `auto_commit=False`（提交权收口） |
| R3-02 | Minor | **confidence 无范围校验**：`1.5` / `-0.3` 被接受入库 | `_validate_confidence()`：非 None 时必须 ∈ [0,1]，全部写方法生效 |
| R3-03 | Minor | **空 code/name 无校验**：`''`、`'  '`、空 name 被接受（列 nullable=False 只挡 NULL） | `_validate_non_empty()`（strip 后判空），code/name/table_name/question 全部生效 |
| R3-04 | Minor | `question` 未 trim 存储；`linked_object_codes` 重复不去重 | question strip 后存储；codes 用 `dict.fromkeys` 去重保序 |

以上 4 条已固化进 `test_modeling.py`（+4 条用例）：
`test_confidence_out_of_range_rejected` / `test_empty_code_and_name_rejected` /
`test_validation_failure_leaves_no_orphan_ontology` / `test_cq_question_trimmed_and_linked_codes_deduped`。

**记录但未改**（观察项，非缺陷）：
- `add_link_type` 允许 `source_type_code == target_type_code`（自引用关系，如"层级隶属"是合法建模）
- 重复 CQ question / 重复 mapping 无唯一约束（spec 未定义唯一键；Task 5/6 的候选去重与快照对比会处理）
- `mapping.source_id` 不校验 P2 存在性（P2 联动是 Task 5 的职责）

## 4. 变异测试（主 agent 执行，残留 = 0）

| 变异 | 针对用例 | 结果 |
|---|---|---|
| V1 coverage 全算已覆盖 | 覆盖度 2 条 | **RED** ✅ |
| V2 `_resolve_ontology` 去租户过滤 | 跨租户隔离 | **RED** ✅ |
| V3 `add_object_type` 删重复校验 | 唯一性 | **RED** ✅ |
| V4 repo 强制 flush → 跟随自身 | 孤儿行 | **PASSED（等价变异）**——读仓储源码确认 `get_or_create` 创建路径本就只 flush 不 commit |
| V4' 拆除 `_write` 的 savepoint | 孤儿行 | **RED** ✅（真正的防护是 savepoint） |

## 5. 回归

```
78 passed, 3 warnings in ~50s
```
（P4.1 的 60 条 + P4.2 的 18 条；无一删除，无一改松——`git diff` 逐文件核对）

## 6. 约束遵守

简报"边界"（不做路由/Tool/候选/快照/LLM 通道）与"工程纪律"（真实 PG / TDD / 迁移幂等 /
无 git 写操作）逐条 ✅。

## 7. 遗留

1. 复审 agent 曾污染 `minworkbuddy_test.public`（全套表 + 数据），**已彻底清理**
   （表/diag_x/probe_* schema），vector 扩展保留。若后续测试出现诡异"已存在"错误，
   优先排查 public 污染。
2. 复审 subagent 连续两次被平台中断（`code=10003`）。教训已记入 `p4-task-1-report-r3.md` §0；
   P4.2 复审由主 agent 完成。
