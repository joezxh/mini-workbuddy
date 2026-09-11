# Task 3: 类层级与基础一致性校验

来源计划：`docs/superpowers/plans/2026-09-10-p4-ontology.md` Task 3
来源 Spec：`docs/superpowers/specs/2026-09-10-ontology-layer-design.md` §7（范围界定）
前置：Task 4/5 已完成（ModelingService + 候选生成，86 passed）

## 与计划的两处偏差（提前声明）

1. **文件名**：计划指定 `tests/ontology/test_hierarchy.py`，已被 P4.1 占用
   （12 条 OWL 引擎层级/循环用例）。本任务新建 `test_consistency.py`。
2. **service 归属**：计划指定新建 `class_service.py`；一致性校验所需的两层数据
   访问（建模对象类型 + OWL 类索引）已全部在 `ModelingService` 中
   （`self._repo` 即 OWL 仓储），单独建 service 只会造成职责拆散与重复查询。
   **实现并入 `ModelingService`**（方法组 `check_consistency`），报告记录该偏差。

## 目标

对**两层**本体数据做三类基础一致性校验，产出结构化报告（不做 SHACL、不自动修复）：

| 层 | 数据 | 校验点 |
|---|---|---|
| 建模层 | `ontology_object_type`（parent_id 自引用） | 悬空父类、循环继承 |
| OWL 层 | `ontology_class`（parent_uris JSONB，无 FK） | 悬空父类（引用了不存在的类 uri）、循环继承、URI 规范化冲突 |

三类定义：

1. **DanglingParent**：`parent_id` 指向不存在的对象类型（防御性：正常路径被 DB FK
   兜底，此校验面向手工 SQL/数据迁移场景）；`parent_uris` 引用本体内不存在的类 uri
   （JSONB 无 FK，**真实风险**，P4.1 的 register_class 允许悬空父类）。
2. **CyclicInheritance**：父类链成环。返回**环路径**（如 `A -> B -> C -> A`）；
   两层各自独立检测。注意 OWL 层 `get_ancestors/get_hierarchy` 已有 visited 防护
   （不死循环），本校验负责**检测并报告环的存在**。
3. **UriConflict**：同一本体内两个类 uri 的**规范化形式**（lowercase、去尾部
   `#`/`/`）相同 —— 如 `http://x#Risk` 与 `http://x#risk`：Turtle 里是两个合法
   URIRef，但极易混淆且在工具间往返时可能折叠。severity=warning（不判错）。

## 涉及文件

| 路径 | 动作 |
|---|---|
| `backend/app/services/ontology/modeling_service.py` | 修改：新增 `ConsistencyIssue` / `ConsistencyReport` 数据类 + `check_consistency()` |
| `backend/tests/ontology/test_consistency.py` | 新建 |

## 验收标准

| 项 | 标准 |
|---|---|
| 报告结构 | 每条 issue 含 kind（dangling_parent/cyclic_inheritance/uri_conflict）、layer（modeling/owl）、severity（error/warning）、subject（uri 或 code）、detail（人话描述，环要给路径） |
| 覆盖 | 三类 × 两层，干净本体 → 空报告 |
| 幂等 | 校验为纯读操作（读路径不建本体行——复用 Task 4 的 `_resolve_ontology(create=False)`） |
| 租户 | 只检查自己租户的本体 |
| 回归 | `tests/ontology` 全绿（86 + 新增） |

## 边界（本 Task 不做）

- 不做 SHACL 完整校验（P4.4 评估）
- 不做自动修复/级联删除（报告只读）
- 不做 REST/Tool 暴露
- 不引入新依赖；**不执行任何 git 写操作**
