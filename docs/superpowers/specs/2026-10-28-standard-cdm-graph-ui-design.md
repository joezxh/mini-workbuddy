# 标准三层语义模型（CDM）+ 目录/场景 + 图驱动标准中心 设计

> 日期：2026-10-28
> 状态：设计中（待用户 review）
> 影响范围：backend models/services/routers/alembic + frontend standard 页签（StandardManagement.vue 及其子组件）
> 核心原则：**纯增量**——现有 `meta_standard` / `meta_column_standard` / `meta_relation` 与 DataSourcePanel 页签结构全部保留、不破坏。

## 1. 背景与目标

当前「标准」在数据模型上只有**属性（字段）级**一层：`meta_standard` 一行 = 一个业务字段口径，通过 `meta_column_standard` 绑定到物理列。缺少业务语义治理所需的**对象（表）标准**与**关系标准**，且没有"应用场景/目录"分类维度。前端 `StandardManagement.vue` 只是一张扁平字段 CRUD 列表。

参考开源工程 `Ontology-Playground-zh-dev` 的组织方式：每个 catalogue 条目 = 一个应用场景（E-Commerce / Logistics / Healthcare…），其 OWL 本体用 `owl:Class`（对象）+ `owl:DatatypeProperty`（属性）+ `owl:ObjectProperty`（关系）描述，并用 `opl-meta:DataSource` 绑定物理表。本设计据此把「标准」升级为三层语义模型（CDM），并新增可导航的目录/场景层，前端做成图驱动的标准中心。

### 目标
1. 标准支持三层：**对象标准 + 属性标准 + 关系标准**，且驱动元数据绑定。
2. 属性标准保持**全局复用字典**，对象标准通过引用复用属性。
3. 新增**层级目录（应用场景）**，圈定对象标准与关系标准。
4. 关系标准为**人工基准**，绑定时与推断的 `meta_relation` 比对，产出命中/缺失/冲突。
5. 前端 standard 页签升级为**图 + 目录树 + 检视面板 + 总览 + NL 查询**的标准中心。

### 非目标（YAGNI 明确剔除）
- 不引入参考工程的 gamified 任务/徽章/答题系统（仅做轻量导览步骤条）。
- NL 查询不做 text-to-SQL、不改数据、不生成执行计划（仅"检索 + 高亮"）。
- 对象标准版本快照表本期不做（属性已有 `meta_standard_version`；对象版本留后续）。
- 不实现 `source=llm` 的自动标注（现有列绑定仍走 rule 通道）。

## 2. 领域概念与命名

| 概念 | 释义 | 物理落点 |
|------|------|---------|
| 属性标准 | 全局可复用的业务字段口径（现有 meta_standard 语义升格） | `meta_standard`（不变） |
| 对象标准 | 业务对象/实体模板（客户、订单…），引用一组属性标准 | `meta_object_standard`（新） |
| 对象-属性引用 | 对象与属性的多对多关联，承载"全局复用" | `meta_object_standard_attribute`（新） |
| 关系标准 | 对象→对象的人工定义关系（类型 + 连接键） | `meta_object_relation`（新） |
| 目录/场景 | 层级树，圈定对象标准与关系标准的应用场景 | `meta_standard_catalog`（新） |
| 表↔对象绑定 | 物理表匹配到对象标准（镜像列↔属性绑定） | `meta_table_standard`（新） |
| 关系校验结论 | 标准关系 vs 推断 `meta_relation` 的比对结果 | `meta_relation_check`（新） |

**维度正交说明**：`meta_standard.domain`（主题域，扁平字符串）与 `catalog`（应用场景层级）是两维——domain 表达业务主题分类，catalog 表达场景归属。catalog 只作用于对象标准与关系标准；属性标准保持全局、不进 catalog，仅保留 domain。两者互不替换。

## 3. 数据模型（新增 7 张表）

所有新表均 `Base, TenantMixin`，含 `tenant_id`；风格对齐 [standard.py](file:///D:/projects/MinWorkBuddy/backend/app/models/dataops/standard.py)（BigInteger 主键、JSONB、TIMESTAMP server_default、审计列）。

### 3.1 `meta_standard_catalog`（目录/场景树）
- `id` PK
- `parent_id` FK→self，nullable（null=根节点）
- `code` String(64) not null — 租户内唯一
- `name` String(200) not null
- `description` Text nullable
- `icon` String(32) nullable（展示用，emoji/图标 key）
- `sort_order` Integer not null default 0
- `status` String(32) not null default `draft`（`draft|published`）
- 审计：`creator_id / updater_id / created_at / updated_at`
- 约束：`UniqueConstraint(tenant_id, code)`；`Index(tenant_id, parent_id)`
- 删除保护：有子节点或被对象/关系引用时 `RESTRICT`（服务层校验，禁止悬空）

### 3.2 `meta_object_standard`（对象标准）
- `id` PK
- `catalog_id` FK→`meta_standard_catalog.id`，**nullable**（null=未归类，允许逐步归档）
- `code` String(64) not null；`name` String(200) not null
- `aliases_json` JSONB nullable（匹配物理表名/注释用）
- `description` Text nullable
- `domain` String(64) nullable
- `status` String(32) default `draft`；`current_version` Integer default 1
- 审计列同上
- 约束：`UniqueConstraint(tenant_id, code)`；`Index(tenant_id, catalog_id)`

### 3.3 `meta_object_standard_attribute`（对象↔属性 引用，M2M）
- `id` PK
- `object_id` FK→`meta_object_standard.id` ondelete=CASCADE
- `standard_id` FK→`meta_standard.id` ondelete=RESTRICT（被引用属性不可删）
- `required` Boolean not null default false
- `sort_order` Integer not null default 0
- `security_level_override` String(8) nullable（对象上下文覆盖属性等级）
- `note` String(500) nullable
- 约束：`UniqueConstraint(object_id, standard_id)`；`Index(object_id)`

### 3.4 `meta_object_relation`（关系标准）
- `id` PK
- `catalog_id` FK→`meta_standard_catalog.id`，nullable
- `code` String(64) not null；`name` String(200) not null
- `from_object_id` FK→`meta_object_standard.id` ondelete=RESTRICT
- `to_object_id` FK→`meta_object_standard.id` ondelete=RESTRICT
- `relation_type` String(16) not null（`1:1|1:N|N:1|N:N`）
- `via_attribute_ids` JSONB nullable（连接键引用哪些属性标准 id，有序）
- `description` Text nullable
- `status` String(32) default `draft`
- 审计列
- 约束：`UniqueConstraint(tenant_id, code)`；`Index(from_object_id)`；`Index(to_object_id)`；`Index(tenant_id, catalog_id)`

### 3.5 `meta_table_standard`（表↔对象 绑定，镜像列绑定）
字段语义完全对齐 [MetaColumnStandard](file:///D:/projects/MinWorkBuddy/backend/app/models/dataops/standard.py#L72-L110)：
- `id` PK；`table_id` FK→`meta_table.id` ondelete=CASCADE；`object_standard_id` FK→`meta_object_standard.id` ondelete=RESTRICT
- `standard_version` Integer nullable
- `status` String(32) default `suggested`（`suggested|accepted|rejected`）
- `source` String(32) default `human`（`rule|llm|human`）
- `confidence` Float nullable；`evidence_json` JSONB nullable
- `reviewed_by` BigInteger nullable；`reviewed_at` TIMESTAMP nullable
- 审计列
- 约束：`UniqueConstraint(table_id)`（表侧 1:1）

### 3.6 `meta_table_standard_history`（表绑定变更历史，对齐列绑定历史链路）
镜像 [MetaColumnStandardHistory](file:///D:/projects/MinWorkBuddy/backend/app/models/dataops/standard.py#L113-L131)：`id / table_id / object_standard_id / standard_version / action(bind|unbind|accept|reject|override) / snapshot_json / actor_user_id / created_at`；`Index(table_id)`。每次表→对象重绑写一条。绑定的留痕与列绑定对称，故本期**明确建此表**（非可选）。

### 3.7 `meta_relation_check`（关系校验结论）
- `id` PK
- `standard_relation_id` FK→`meta_object_relation.id` ondelete=CASCADE
- `source_id` FK→`meta_data_source.id` ondelete=CASCADE；`database` String(128) not null（库/schema 作用域，对齐 meta_relation）
- `inferred_relation_id` FK→`meta_relation.id` nullable（命中时回填推断关系 id）
- `verdict` String(16) not null（`hit|missing|conflict`）
- `confidence` Float nullable
- `evidence_json` JSONB nullable（比对依据：两端已绑定表名、方向、基数差异）
- `checked_at` TIMESTAMP not null server_default now
- 约束：`UniqueConstraint(standard_relation_id, source_id, database)`（幂等 upsert）

## 4. 服务层

### 4.1 CRUD 服务（新增，[services/dataops](file:///D:/projects/MinWorkBuddy/backend/app/services/dataops) 下）
- `MetaStandardCatalogService`：树构建、create/update/move(改 parent)/delete（RESTRICT 保护）、list。
- `MetaObjectStandardService`：对象 CRUD；`set_attributes(object_id, [ {standard_id, required, sort_order, security_level_override} ])` 全量替换引用；`serialize`（含引用的属性摘要）。
- `MetaObjectRelationService`：关系 CRUD；保存时做"跨场景软校验"——两端对象的 `catalog_id` 分属不同子树时返回提醒（不阻断）。

租户隔离与"无 tenant 拒绝构造"沿用现有 [MetaStandardService](file:///D:/projects/MinWorkBuddy/backend/app/services/dataops/standard_service.py#L17-L47) 模式。

### 4.2 绑定链路扩展（[standard_binding_service.py](file:///D:/projects/MinWorkBuddy/backend/app/services/dataops/standard_binding_service.py)）
`bind_table` / `bind_source` 现在只做"列→属性"。改为按序三步：
1. **列→属性**：保留现有 `_annotate` + `_bind_column`。
2. **表→对象**（新）：`RuleEngine.match_object(table_name, table_comment, object_standards)`（复用别名匹配打分），按 [tier](file:///D:/projects/MinWorkBuddy/backend/app/ai/dataops/rule_engine.py) 置信度分层落 `meta_table_standard` + 历史；**已 accepted 的人工绑定不覆盖**（同列绑定语义）。
3. **关系校验**（新）：对象绑定完成后，对每条 `published` 的 `meta_object_relation`：
   - 找到 from/to 对象在该 (source, database) 下已绑定的物理表 TA/TB；
   - 任一端未绑定 → 跳过该 (source,database) 的判定；
   - 查 `meta_relation` 中 TA↔TB（两向）：
     - 存在且置信度≥阈值、方向一致 → `verdict=hit`，回填 `inferred_relation_id`；
     - 存在但方向反/类型不符 → `conflict`；
     - 不存在 → `missing`；
   - upsert 到 `meta_relation_check`。
   - **conflict 判定收敛说明**：`meta_relation` 无显式基数，本期 conflict 仅在"存在推断关系但 left/right 方向与标准 from/to 相反"时判定；类型不符（relation_type vs 推断无类型）不作为 conflict，降级为 hit+evidence 备注，避免过度设计。
- `BindReport` 扩展计数字段：`objects_bound / objects_updated / relation_checked / hit / missing / conflict`，`details` 增加对象与关系校验条目。

### 4.3 NL 查询服务（新）
`StandardQueryService.nl_query(question, catalog_scope, model_id?)`：
- 取范围内对象/关系/属性摘要，压成紧凑 JSON 提示词；
- 复用 [llm_json(prompt, model_id)](file:///D:/projects/MinWorkBuddy/backend/app/ai/research/llm.py#L193-L200)；
- 约定模型返回结构化选择器：`{ "highlight_object_codes": [], "highlight_relation_codes": [], "focus_catalog_code": null, "summary": "" }`；
- `llm_json` 抛错时服务层捕获，返回带 `error` 字段的降级响应（HTTP 200 + `degraded=true`），不 500。
- 纯只读：不改数据、不生成 SQL。

## 5. 路由 / API（[routers/dataops/dataops.py](file:///D:/projects/MinWorkBuddy/backend/app/routers/dataops/dataops.py)，前缀 `/api/v1/dataops`）

沿用现有 dataops 路由与鉴权/租户注入模式。新增：

| Method | Path | 说明 |
|--------|------|------|
| GET/POST | `/standards/catalogs` | 目录列表(树)/新建 |
| PUT/DELETE | `/standards/catalogs/{id}` | 改名/移动(parent)/删除(RESTRICT) |
| GET/POST | `/standards/objects` | 对象标准列表(可按 catalog 过滤)/新建 |
| PUT/DELETE | `/standards/objects/{id}` | 更新/删除 |
| PUT | `/standards/objects/{id}/attributes` | 全量设置引用属性 |
| GET/POST | `/standards/relations` | 关系标准列表/新建 |
| PUT/DELETE | `/standards/relations/{id}` | 更新/删除 |
| GET | `/standards/graph` | 图数据：给定 catalog 范围返回 nodes(objects)+edges(relations) |
| GET | `/standards/stats` | 统计：按目录的对象/关系计数、校验 hit/missing/conflict 汇总 |
| POST | `/standards/nl-query` | 自然语言检索→结构化选择器 |
| POST | `/sources/{id}/bind`（扩展） | 现有绑定端点，返回体带新增计数 |

请求/响应体在 [schemas](file:///D:/projects/MinWorkBuddy/backend/app/schemas) dataops 子域定义 Pydantic 模型。

## 6. Alembic 迁移

- 新建 1 个 revision（依赖当前 head `2026_10_28_0002_add_meta_table_db_name`）：建 7 张新表 + 约束/索引。
- 全部 `create`（无历史数据迁移，属性字典不动）。
- **幂等**：建表前查 `information_schema.tables`；风格对齐 [0002 迁移](file:///D:/projects/MinWorkBuddy/backend/alembic/versions/2026_10_28_0002_add_meta_table_db_name.py)。
- `downgrade` 逆序 drop 7 表。
- **种子**：迁移内预置 2 个场景根目录（电商 / 物流），各带 1 个示例对象标准 + 1 条示例关系（供图与绑定演示）；幂等（存在即跳过）。测试库走 `create_all`，种子仅生产迁移需要。

## 7. 前端（standard 页签改造）

容器不变：[DataSourcePanel.vue](file:///D:/projects/MinWorkBuddy/frontend/src/views/data-source/DataSourcePanel.vue) 的 `a-tabs`（source/metadata/**standard**/binding/sql）。改造发生在 standard 页签内部，`StandardManagement.vue` 升级为「标准中心」，拆为子组件：

```
StandardManagement.vue（标准中心 shell：视图切换 + 布局）
├─ StdGuidTour.vue        轻量建模导览步骤条（静态步骤+高亮+下一步）
├─ StdCatalogTree.vue     左：catalog 层级树（a-tree，选中过滤；增删改/移动）
├─ StdGraphView.vue       中(图视图)：ECharts graph 力导向；节点=对象、边=关系
├─ StdOverviewView.vue    中(总览)：统计卡片 + ECharts + NL 查询框
├─ StdInspector.vue       右：详情检视（点对象→表定义含属性列表；点边→关系定义+校验结论；下钻数据源按钮）
└─ Std*FormModal          对象/属性引用/关系 录入编辑（模态，保留作者态）
```

要点：
- **图库**：ECharts 5 `graph` series（`vue-echarts` 已在依赖）。节点点击→设 selected→StdInspector；边点击→关系详情。`/standards/graph` 提供 nodes/edges。
- **视图切换**：中央窗体 `[图视图 | 总览视图]` 顶部 tab 切换（对齐参考"中间主窗体可切换"）。
- **目录树可选**：不选=全图；选中节点=只显示该子树下对象与关系。
- **下钻数据源**：StdInspector 中对象/表已绑定时，按钮**上抛 `@drill-down` 事件**给父 DataSourcePanel（父持有 `activeKey`），由父切到 metadata 页签并带 source/scope，复用 [MetadataExplorer](file:///D:/projects/MinWorkBuddy/frontend/src/views/data-source/MetadataExplorer.vue)。
- **NL 查询**：总览视图输入框→`/standards/nl-query`→拿选择器切回图视图高亮 + 右面板显示 summary。
- [api/dataops.ts](file:///D:/projects/MinWorkBuddy/frontend/src/api/dataops.ts) 增加对应函数（catalog/objects/relations/graph/stats/nl-query/objects-attributes）。
- i18n：新 key 落 `kbMgmt.std.*` 与新增 `kbMgmt.catalog.*` / `kbMgmt.graph.*` 命名空间。

## 8. 测试

- **服务层单测**：catalog 树增删改/move/RESTRICT；对象 CRUD + 引用属性全量替换；关系 CRUD + 跨场景提醒。
- **绑定回归**（[tests/dataops](file:///D:/projects/MinWorkBuddy/backend/tests/dataops)）：`match_object` 表→对象命中；人工 accepted 不覆盖；关系三态（构造命中的 `meta_relation`→hit；删掉→missing；反向→conflict）。
- **路由级**：各 CRUD 端点 + `/graph` + `/stats` + `/nl-query`（NL 用 mock 打桩 `llm_json`，断言降级路径不 500）。
- **迁移**：alembic upgrade/downgrade 往返（本地 PG）。
- **前端**：StdGraphView 渲染 nodes/edges 快照测试；StdCatalogTree 选中过滤；StdInspector 点选联动（沿用 vitest 约定）。

## 9. 分期（4 后端片 + 3 前端片，前端依赖后端对应片）

| 片 | 交付 | 依赖 |
|----|------|------|
| B1 | 7 表模型 + Alembic 迁移 + 种子 | — |
| B2 | 目录树 + 对象标准 + 引用属性 CRUD/API | B1 |
| B3 | 表→对象绑定（`match_object` + `meta_table_standard` + BindReport 扩展） | B1,B2 |
| B4 | 关系标准 CRUD + 校验链路 + `/graph` `/stats` + NL 查询端点 | B1,B2,B3 |
| F1 | 标准中心骨架：catalog 树 + 对象 CRUD + 引用属性（先 CRUD，无图） | B2 |
| F2 | 中央 ECharts 图 + 右检视 + 点选联动 + 下钻数据源 | B3,B4(graph) |
| F3 | 总览视图（统计+校验可视化）+ NL 查询联动高亮 + 导览步骤条 | B4(stats,nl-query) |

## 10. 错误处理 / 安全 / 兼容

- 租户隔离：所有服务要求 `tenant_id`，无租户拒绝构造（对齐现有）。
- 删除保护链：属性被对象引用→RESTRICT；对象被关系引用或表绑定→RESTRICT；目录有子/被引用→RESTRICT。
- 绑定幂等：`meta_table_standard` 按 `table_id` upsert；`meta_relation_check` 按 (standard_relation_id, source_id, database) upsert。
- 向后兼容：`meta_standard` / `meta_column_standard` / `meta_relation` 不改；旧列绑定/规则通道不受影响；现有 standard 页签的 CRUD 能力内联保留。
- NL 查询失败降级：`llm_json` 异常→200 + `degraded=true`，前端提示"AI 检索不可用"，不影响图浏览。

## 11. 已确认的决策（定稿要点）

1. 三层 CDM（对象+属性+关系），驱动绑定。
2. 属性=全局复用字典，对象引用属性（M2M）。
3. 关系=人工基准 + 与 `meta_relation` 比对校验（不自动改写标准）。
4. 目录=层级树，只圈对象与关系；属性保持全局。
5. `catalog_id` **可空**（允许未归类，逐步归档）。
6. 迁移**预置电商/物流 2 个种子场景**（各带示例对象+关系）。
7. 图库 = ECharts graph；导览 = 轻量步骤条；NL 查询本期落地（复用 `llm_json`）。
8. 冲突判定收敛为"方向反转"，类型不符降级为 hit+备注。
