# Task 5: 从 P2 元数据生成候选 + 评审流程

来源计划：`docs/superpowers/plans/2026-09-10-p4-ontology.md` Task 5
来源 Spec：`docs/superpowers/specs/2026-09-10-ontology-layer-design.md` §5.3、§8
前置：Task 4（P4.2 六表 + ModelingService）已完成并复审（78 passed）

## 背景

P4.2 建好了治理六表；本任务把 **P2 的元数据产出**变成**本体候选**：
`meta_table` → 对象类型候选、`meta_column` → 属性候选、高重叠列对 → 关系候选，
全部以 `status=suggested`（或按置信度自动接受）进入评审队列，
由人工通过 `update_object_type_status` 接受/拒绝（spec §8 的联动全链路）。

## 关键依赖决策：P2 未实施

Task 5 计划要求「置信度阈值必须复用 P2 的 `rule_engine.CONF_AUTO_ACCEPT / CONF_SUGGEST_MIN`，
不得重新定义」。**P2 尚未实施**，但 P2 计划 Task 12 Step 3 已锁定：

- 定义位置：`backend/app/services/dataops/rule_engine.py`
- 数值：`CONF_AUTO_ACCEPT = 0.85` / `CONF_SUGGEST_MIN = 0.65`
- 分层语义（P2 Task 12 的参数化测试为权威）：`0.90 → accepted`、`0.70 → suggested`、`0.50 → 丢弃`

**决策**：按计划锁定的位置与数值**预占位**该文件（仅含两个常量 + 归属注释），
P2 Task 12 实施时在同一文件扩展规则引擎本体——这是"单一事实来源"约束下
不阻塞 Task 5 的最小方案，不属于重新定义。

**P2 元数据读取层的处理**：P2 的 `meta_table` / `meta_column` 表不存在，
候选生成的输入用**抽象数据类**（字段对齐 P2 计划的 meta 模型与唯一键
`(source_id, database, table_name)`），测试用内存 fixture 模拟 P2 产出。
P2 实施后补一个"从 ORM 行 → 数据类"的薄适配即可接入，不影响本任务接口。

## 涉及文件

| 路径 | 动作 |
|---|---|
| `backend/app/services/dataops/__init__.py` + `rule_engine.py` | 新建：**预占位**，仅 `CONF_AUTO_ACCEPT=0.85` / `CONF_SUGGEST_MIN=0.65`（P2 Task 12 归属） |
| `backend/app/services/ontology/modeling_service.py` | 修改：新增候选生成能力 |
| `backend/tests/ontology/test_candidates.py` | 新建：测试 |

## 需要实现的候选生成能力

`ModelingService.generate_candidates(tables, columns, column_pairs) -> CandidateReport`

输入数据类（字段对齐 P2 meta 模型）：

```
MetaTableRef       source_id · database · table_name · comment · confidence(None=未评分)
MetaColumnRef      source_id · database · table_name · column_name · data_type · comment · confidence
ColumnPairOverlap  left_table · left_column · right_table · right_column · overlap_ratio
```

生成规则（置信度分层语义与 P2 Task 12 参数化测试对齐）：

| 元素 | 规则 |
|---|---|
| 表 → 对象类型候选 | code=表名规范化；`confidence is None`（表扫描无评分）→ `status=suggested`（人工评审，spec §8 主链路）；带 conf 时按分层；同时生成 `ontology_mapping`（target_type=table，evidence 记 source_id/database） |
| 列 → 属性候选 | 挂到表对应的对象类型；conf 分层：`≥ CONF_AUTO_ACCEPT → accepted`、`∈ [CONF_SUGGEST_MIN, AUTO_ACCEPT) → suggested`、`< CONF_SUGGEST_MIN → 不生成` |
| 列对 → 关系候选 | `overlap_ratio ≥ CONF_SUGGEST_MIN` 才生成；同表对的多列对**合并**为一个 link_type（evidence 记录每对列与 overlap_ratio）；cardinality=`N:M`（推断关系） |
| 幂等 | 重复 generate：已存在的 code/object_type.property 跳过（计入 skipped），不产生重复行 |
| source | 全部 `source=rule`，`evidence_json` 必须写入可追溯的 P2 侧证据 |

`CandidateReport`：created / skipped 计数 + 明细（供 API 层与 AgentScope `ontology_suggest` Tool 复用）。

## 必须通过的测试（TDD 先 RED）

1. **联动全链路**（spec §8 原文）：`meta_table` → 对象类型候选（suggested）→ `update_object_type_status(accepted)` → `list_object_types(status="accepted")` 命中
2. **列分层**：conf 0.90→accepted、0.70→suggested、0.50→不生成（阈值语义与 P2 计划示例一致；0.85/0.65 边界值也要测）
3. **关系候选**：overlap≥0.65 生成（evidence 含 overlap_ratio 与列名）、同表对多列对合并、<0.65 丢弃
4. **幂等**：连续两次 generate，第二次 created=0
5. **映射**：表候选顺带生成 ontology_mapping（table 级，evidence 可追溯）
6. **租户隔离**：generate 只影响自己租户的本体
7. **阈值单一来源**：测试断言 `modeling_service` 使用的是 `rule_engine.CONF_AUTO_ACCEPT / CONF_SUGGEST_MIN`（import 复核 + 分层结果隐式锁定数值）

## 验收标准

| 项 | 标准 |
|---|---|
| 分层 | 0.90/0.70/0.50 → accepted/suggested/丢弃，与 P2 计划示例一致 |
| 幂等 | 重复生成不增行 |
| 可追溯 | 每个候选的 evidence_json 能回答"来自哪个 source/database/table/column" |
| 回归 | `tests/ontology` 全绿（78 + 新增） |
| 边界 | 不实现 P2 的元数据扫描/规则引擎本体；不做 REST/Tool |

## 边界（本 Task 不做）

- 不实现 P2 的 `meta_scan_service` / `rule_engine` 规则本体 / `relation_inference`（P2 Task 6/12/13）
- 不做 REST 路由、AgentScope Tool（Task 9）
- 不做版本快照（Task 6）
- 不引入新依赖
- **不执行任何 git 写操作**
