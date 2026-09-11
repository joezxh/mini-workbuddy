# Task 3 报告：类层级与基础一致性校验

- 任务来源：`.superpowers/sdd/p4-task-3-brief.md`（P4 计划 Task 3 + spec §7 范围界定）
- 执行日期：2026-09-11
- 结论：**DONE**（95 passed；V6/V7 变异验证通过）
- 未执行 `git commit`

## 1. 与计划的两处偏差（简报已声明）

| 计划 | 实际 | 理由 |
|---|---|---|
| 新建 `test_hierarchy.py` | **`test_consistency.py`** | `test_hierarchy.py` 已被 P4.1 的 12 条 OWL 层级用例占用 |
| 新建 `class_service.py` | **并入 `ModelingService`**（`check_consistency()` 方法组） | 两层数据访问（建模对象类型 + OWL 类索引 `self._repo`）已在 ModelingService 中，单独建 service 只会拆散职责、重复查询 |

## 2. 设计

三类校验 × 两层数据，纯读产出 `ConsistencyReport`（issues: kind/layer/severity/subject/detail）：

| kind | layer | severity | 说明 |
|---|---|---|---|
| `dangling_parent` | modeling | error | `parent_id` 悬空（正常路径被 DB FK 阻止，出现即数据被绕过服务修改；检测器为防御性） |
| `dangling_parent` | owl | error | `parent_uris` 引用未注册类（**JSONB 无外键，真实可达**：`register_class` 允许悬空父类） |
| `cyclic_inheritance` | modeling / owl | error | 父链成环，detail 给出环路径（`A -> B -> A`），同一环**只报一次** |
| `uri_conflict` | owl | warning | URI 规范化（lowercase、去尾部 `#`/`/`）后相同，如 `#Risk` vs `#risk`——合法但易混淆 |

实现要点：
- 检测器为**纯函数**（`_find_dangling_parents(items, known_keys)` / `_find_parent_cycles(items)` /
  `_find_uri_conflicts(uris)`）——建模层悬空在 PG 外键下不可构造，用纯函数直接喂伪造数据单测；
- `check_consistency()` 走 `_resolve_ontology(create=False)`（纯读不建本体行，有测试固化）；
- **关键坑**（实施中发现并修复）：悬空检测的 key 全集必须包含**无父引用的合法节点**
  ——items 只含有父关系的对，若用 items 的 key 做全集，"已注册但无父"的类会被误判悬空
  （V7 变异即复现此 bug 类别，`test_clean_ontology_reports_no_issues` 捕获）。

## 3. 测试（9 条，`test_consistency.py`）

干净本体+纯读、OWL 悬空、建模层悬空（纯函数）、OWL 环（路径+去重）、建模层环（ORM 直改构造）、
环去重（纯函数）、URI 冲突 warning、URI 无误报、租户隔离。

```
95 passed, 3 warnings in ~59s     （86 旧 + 9 新，全量回归无破坏）
```

## 4. 变异验证（残留 = 0）

| 变异 | 结果 |
|---|---|
| V6 拆除环去重（同环报多次） | `test_owl_cycle_reported_with_path` **RED** ✅ |
| V7 悬空检测丢 key 全集（复现实施中的误判 bug） | `test_clean_ontology_reports_no_issues` **RED** ✅ |

## 5. 遗留与提示

1. 建模层悬空在 DB 外键下不可构造——检测器保留为防御性（数据迁移/手工 SQL 场景）。
2. `uri_conflict` 是 warning 级提示，不阻断任何流程；P4.4 引入推理时应升级为必须修复。
3. `check_consistency()` 尚无 REST/Tool 暴露——与 Task 9（`ontology_query` Tool）一起接入时
   可直接消费 `ConsistencyReport`（dataclass 可序列化）。

## 6. P4 全景进度

| 任务 | 状态 |
|---|---|
| Task 1（P4.1 持久化与租户隔离） | ✅ 两轮复审 + 单一真相源重构 |
| Task 3（一致性校验） | ✅ 本次 |
| Task 4（P4.2 六表 + CQ） | ✅ 含复审 + 4 项修复 |
| Task 5（P2 元数据 → 候选） | ✅ |
| Task 6（版本快照）/ Task 9（AgentScope Tool） | 待做（均无外部依赖） |
| Task 2（TTL，已被 Task 4/5 覆盖）/ Task 7（检索，依赖 P1）/ Task 8（可选） | 见计划 |
