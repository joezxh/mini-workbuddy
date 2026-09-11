# Task 4（P4.2）: 本体建模六表与 CQ 一致性

来源计划：`docs/superpowers/plans/2026-09-10-p4-ontology.md` Task 4
来源 Spec：`docs/superpowers/specs/2026-09-10-ontology-layer-design.md` §3、§5.2、§6、§8
前置：P4.1 已完成（单一真相源重构 + 60 条测试全绿，见 `.superpowers/sdd/p4-task-1-report-r3.md`）

## 背景

P4.1 解决了「本体存哪里」（`ontology` / `ontology_class` / `ontology_annotation` 三张表，
按租户隔离、TTL 单一真相源）。P4.2 解决「本体怎么治理」——借鉴 ontomind 的
CQ（能力问题）驱动建模方法：

```
ontology_object_type   对象类型（业务概念，如「客户」「合同」）
ontology_property      对象类型的属性（字段级）
ontology_link_type     关系类型（对象类型之间的关系，含基数）
ontology_mapping       对象类型 ↔ 物理表/列 的映射（依赖 P2 的元数据）
ontology_cq            能力问题（Competency Question，本体要回答的业务问题）
ontology_version       版本快照（本任务只建表，快照生成是 Task 6）
```

## 目标

建六张表 + `modeling_service`（租户安全的 CRUD + CQ 覆盖度统计）+
顺带清理 P4.1 复审遗留 Minor。**不做** REST 路由、AgentScope Tool、候选生成、
快照生成——那些是 Task 5/6/9 的内容。

## 涉及文件

| 路径 | 动作 |
|---|---|
| `backend/app/models/ontology/model.py` | 新建：六张建模表 |
| `backend/alembic/versions/` | 新建：005 迁移（revises `004_add_ontology_tables`，幂等：表已存在跳过）+ 顺带 drop P4.1 重复索引 |
| `backend/app/db/init_models.py` | 修改：登记新模型 |
| `backend/app/services/ontology/modeling_service.py` | 新建：建模服务 |
| `backend/app/services/ontology/ontology_repository.py` | 修改：删 `append_ttl_content()` 死代码 |
| `backend/app/models/ontology/ontology.py` | 修改：删重复索引 `idx_ontology_tenant` |
| `backend/tests/ontology/conftest.py` 等 | 修改：测试卫生清理 |
| `backend/tests/ontology/test_modeling.py` | 新建：测试 |

## 数据模型

### 约定（沿用 P4.1 简报）

* `Base` 从 `app.db.database` 导入；审计列 `creator_id / updater_id / created_at / updated_at`
* 状态用 `String(32)` + comment，**禁用 SAEnum**（PG ENUM 后期变更困难）
* 表名单数、`__table_args__` 具名索引/约束、字段中文 comment
* 所有 BigInteger 主键 `autoincrement`

### 租户隔离决策（重要）

六表**不继承 `TenantMixin`**（spec §5.2 的字段清单里没有 `tenant_id`，全部经
`ontology_id` 归属到本体）。代价是「伪造 `ontology_id` 跨租户读写」的风险，
因此 **service 层的每一个方法都必须先按 `tenant_id` 解析出合法的 `ontology` 行，
再操作子表**——绝不允许接收裸 `ontology_id` 直查子表。必须有测试证明：
租户 A 的 service 访问租户 B 的本体时，行为等同「不存在」（抛 `ValueError`/返回空，
与 P4.1 仓储的租户链路风格一致）。

### 六张表（spec §5.2 字段为权威，可补充 nullable/长度等实现细节）

```
ontology_object_type   ontology_id(FK→ontology.id, CASCADE)
                       · code(String128) · name(String200) · description(Text)
                       · parent_id(FK→ontology_object_type.id, nullable, 自引用)
                       · status(suggested|accepted|rejected, 默认 suggested)
                       · source(rule|human|llm, 默认 human)   ← llm 保留取值，本任务不产生
                       · confidence(Float, nullable, 0~1) · evidence_json(JSONB, nullable)
                       唯一 uq_ontology_object_type (ontology_id, code)
                       索引 idx_object_type_ontology (ontology_id)、idx_object_type_parent (parent_id)

ontology_property      object_type_id(FK→ontology_object_type.id, CASCADE)
                       · code(String128) · name(String200) · data_type(String64)
                       · required(Boolean, 默认 False) · semantic_type(String128, nullable)
                       · status(suggested|accepted|rejected) · source(rule|human|llm) · confidence
                       唯一 uq_ontology_property (object_type_id, code)

ontology_link_type     ontology_id(FK, CASCADE)
                       · code(String128) · name(String200)
                       · source_type_id / target_type_id（都 FK→ontology_object_type.id）
                       · cardinality(String32, 如 1:1|1:N|N:M)
                       · status · source · confidence · evidence_json(JSONB)
                       唯一 uq_ontology_link_type (ontology_id, code)

ontology_mapping       ontology_id(FK, CASCADE)
                       · object_type_id(FK→ontology_object_type.id)
                       · target_type(table|column) · source_id(String128, P2 侧物理对象 ID)
                       · database(String128) · table_name(String200) · column_name(String200, nullable)
                       · status · source · confidence
                       索引 idx_mapping_ontology (ontology_id)、idx_mapping_object_type (object_type_id)

ontology_cq            ontology_id(FK, CASCADE)
                       · question(Text) · answer_hint(Text, nullable)
                       · status(active|archived, 默认 active)
                       · linked_object_types(JSONB, 对象类型 code 或 id 列表——实现者定并写清注释)
                       索引 idx_cq_ontology (ontology_id)

ontology_version       ontology_id(FK, CASCADE)
                       · version(String32) · snapshot_json(JSONB) · change_note(Text, nullable)
                       · author_user_id(BigInteger, nullable)
                       唯一 uq_ontology_version (ontology_id, version)
```

## 需要实现的 service 能力（`modeling_service.py`）

统一入口形如 `ModelingService(db, tenant_id, code="default")`——先解析本体，再操作。
解析不到本体时：读方法返回空/None；写方法按 P4.1 的约定幂等创建 `code='default'` 本体行
（savepoint + IntegrityError 兜底并发），或抛 ValueError——实现者选一种并保持一致。

| 方法 | 语义 |
|---|---|
| `add_object_type(code, name, ..., parent_code=None, status, source, confidence)` | 建对象类型；`parent_code` 存在时校验同本体；code 重复抛 ValueError |
| `list_object_types(status=None)` / `get_object_type(code)` / `update_object_type_status(code, status)` | 查询与评审状态流转（suggested→accepted/rejected 可逆） |
| `add_property(object_type_code, code, ...)` / `list_properties(object_type_code)` | 属性 CRUD，object_type 必须存在 |
| `add_link_type(code, name, source_type_code, target_type_code, cardinality, ...)` / `list_link_types()` | 关系类型；两端 object_type 必须存在 |
| `add_mapping(object_type_code, target_type, ...)` / `list_mappings()` | 映射 |
| `add_cq(question, answer_hint=None, linked_object_codes=None)` / `list_cqs()` | CQ CRUD；`linked_object_codes` 中不存在的 code 抛 ValueError |
| `cq_coverage() -> float` | **口径（计划示例为权威）**：`linked_object_types` 非空的 active CQ 数 ÷ 全部 active CQ 数。无 CQ 时返回 `0.0`（防除零）。示例：2 个 CQ、1 个关联了对象类型 → `0.5` |
| `list_object_types` 等 | 需支持层级语义（`parent_id`），但完整层级树不是本任务必须 |

状态流转：`suggested → accepted / rejected`（允许改回来），**必须**校验 status 取值，
非法值抛 ValueError。

## 附带输入：P4.1 复审遗留 Minor（用户已拍板挂本任务）

| # | 事项 | 本任务动作 |
|---|---|---|
| MI-04 | `ontology` 表 `tenant_id` 两个重复索引（`TenantMixin` 自动索引 + 手动 `idx_ontology_tenant`） | 删 `ontology.py` 的手动 `idx_ontology_tenant`；005 迁移里 `DROP INDEX IF EXISTS idx_ontology_tenant` |
| MI-01 | TTL label/comment 语言标记在**索引**中丢失 | **评估决策**：`ttl_content` 原文已保真（Literal lang 保留），导出路径不受影响；只有索引丢 lang。推荐**不加列**并记录决策；若实施中发现前端/检索确需语言信息再加列。在报告中说明决策依据 |
| — | `append_ttl_content()` 已无调用方（单一真相源后死代码） | 从 `ontology_repository.py`（PG 版 + InMemory 版）删除 |
| — | 测试卫生：`pytest.importorskip` / `_tables()` try-except / `_reset_legacy_singleton` 空转 / 函数体内 `import pytest` | 清理（conftest 与各测试文件）；`_reset_legacy_singleton` 若已无作用则整体删除 |
| — | `uri String(1000)` 参与 btree 唯一索引的 PG 上限风险（多字节 URI ×3 可能超 2704 字节/条目） | **评估决策**：推荐把 `ontology_class.uri` 列宽与 `MAX_URI_LENGTH` 统一降到 **500**（超长 URI 罕见；500×3=1500 < 2704 安全）；迁移顺带 `ALTER COLUMN ... TYPE varchar(500)`。若选择维持 1000，报告中必须给出理由与残余风险 |
| MI-08 | `InMemoryOntologyStore` 与 `OntologyRepository` 无共享 Protocol | 抽取 `OntologyStoreProtocol`（runtime_checkable 或纯类型用均可），两个后端都挂上；`WikiOwlEngine` 类型注解改用它 |

## 必须通过的测试（TDD，先 RED 后 GREEN）

1. **CQ 覆盖度**：计划示例原样固化——2 个 CQ、1 个关联对象类型 → `cq_coverage() == 0.5`；0 个 CQ → `0.0`
2. **租户安全**：租户 A 的 service 无法读/写租户 B 的本体（伪造 ontology_id/code 不可达）
3. **对象类型**：code 重复抛 ValueError；`parent_code` 悬空抛 ValueError；状态流转含非法值抛 ValueError
4. **属性/关系**：object_type 不存在抛 ValueError；link_type 两端校验
5. **CQ 引用校验**：`linked_object_codes` 含不存在 code 抛 ValueError
6. **持久化**：重建 engine + 新会话（`engine_for()`，P4.1 的「重启」模拟）后数据仍在
7. **迁移幂等**：重复 upgrade 不炸（沿用 004 的「表已存在跳过」模式）；重复索引已清理
8. **回归**：P4.1 的 60 条测试全绿（删 `append_ttl_content`、测试卫生清理不得破坏任何现有用例）

## 验收标准

| 项 | 标准 |
|---|---|
| 六表 | 模型 + 迁移可在真实 PG 空库 upgrade；JSONB 列实为 jsonb；无 SAEnum |
| CQ | 覆盖度口径与计划示例一致，防除零 |
| 租户 | service 全部方法走租户链路，跨租户不可达（有测试） |
| Minor | 6 条全部处理或在报告给出决策依据 |
| 回归 | `tests/ontology` 全绿（60 + 新增） |

## 边界（本 Task 不做）

- 不做 REST 路由（`routers/ontology/`）——后续任务
- 不做 AgentScope Tool（`ontology_query` / `ontology_answer_cq` / `ontology_suggest`）——Task 9
- 不做从 P2 元数据生成候选、置信度阈值——Task 5（届时复用 `rule_engine.CONF_AUTO_ACCEPT` / `CONF_SUGGEST_MIN`）
- 不做版本快照生成/对比/回滚——Task 6（本任务只建 `ontology_version` 表）
- 不实现 LLM 抽取通道（`source='llm'` 仅保留取值）
- 不引入新依赖

## 工程纪律

- 真实 PostgreSQL 测试（`minworkbuddy_test`，复用 P4.1 conftest 的 schema-per-test）
- TDD：新用例先跑出 RED，贴失败输出
- 迁移需在 PG 空库实跑验证（临时库，用完删）
- **不执行任何 git 写操作**（不 commit / add / checkout / stash / worktree），改动保留在工作区
