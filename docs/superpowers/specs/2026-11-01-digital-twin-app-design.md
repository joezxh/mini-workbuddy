# MinWorkBuddy 孪生应用设计方案

> 日期：2026-11-01 · 状态：**待评审**
> 基准原型：`docs/prototypes/ontology-digital-twin-preview.html`（690 行，零外部依赖）
> 上游规格：`docs/superpowers/specs/2026-10-31-ontology-capability-design.md`（决策 D2、AF-22、§1.2 能力边界）
> 姊妹规格：`2026-10-28-standard-cdm-graph-ui-design.md`、`2026-11-01-asset-catalog-alignment-design.md`
>
> **阅读约定**：全文对现状的描述一律标注依据（文件:行号）；凡属推断、假设、未实测的内容集中在 §8，正文不做无据断言。

---

## 0. 已定调的六个决策

以下六项于 2026-11-01 由用户逐项裁决（每项给出被放弃的备选），是本方案全部设计的承重前提。

| # | 决策点 | ✅ 裁决 | 放弃的备选 | 直接后果 |
|---|---|---|---|---|
| **T1** | 组件取数基座 | **查询期直连**：绑定项编译为受 `SqlGuard` 约束的只读 SQL，经既有 `ReadonlyQueryService` 执行，轮询即"实时" | B 实例物化（孪生态快照）/ C 复用 SQLBot 声明式工具 / D 先 Mock 后接真 | **不破上游 D2**（实例不落库）；代价是大扇出与高频刷新的负载风险，以及无历史序列（见 R4） |
| **T2** | 绑定契约所在层 | 新增 **`onto_ontology_query` 一等公民**（钉版本 + 结果形状 + 参数声明） | B 组件内联 `bind_json` / C 只绑对象+属性原语 | AF-22「一次查询多端消费」首次真正落地；脱敏与权限裁定收敛到查询定义层 |
| **T3** | 3D 场景层分期 | **P0 只做 2D 与组件**，3D 进 P1（P0 场景 = 内置模板只读展示） | B P0 含 3D 渲染 / C 引入 three.js 真 3D / D 永久取消 3D | 成本从"渲染"转移到"场景配置编辑器"；等距 SVG 引擎零新依赖移植 |
| **T4** | 发布与嵌入边界 | **P0 登录态只读页 + RBAC 权限码**，同域 iframe；分享票据/公开链接进 P1 | B P0 含公开链接 / C 只做嵌入入口 / D 不做发布 | 不新增未鉴权攻击面；`/twin-p/:slug` 必须走顶层路由 |
| **T5** | AI 助手能力边界 | **双通道**：布局类指令走确定性解析；LLM 只产出「候选组件 + 绑定已有查询 + 栅格位」，服务端校验不过即丢弃并回执 | B LLM 自由生成整页 / C P0 不做 AI | AI 无法凭空造 SQL；权限与脱敏不被 AI 绕过；形态与 `ontology_semantic_service` 的 `suggest → hallucination_dropped → adopt` 同构 |
| **T6** | 受限/脱敏深度 | **列级脱敏（编译期闸 + 出口 `apply_masking`）+ 查询级过滤实现实体限制 + 卡片三态 + 申请单** | B 独立行列视野引擎 / C 仅列脱敏与卡片级可见 / D 不脱敏仅水印 | 与上游 §1.2「本期不做行列级视野引擎」保持一致；原型园区单实体 🔒 态仍可复现（行不返回即得） |

### 0.1 与上游/姊妹规格的冲突关账（**验收阻断项**）

上游规格现把孪生应用判为"不做/维持非目标"，本方案使其落地，因此**必须在同一 PR 内回改以下 5 处**，否则文档与实现背离（本项目已有过此类教训）。下表的「现文本」列**逐字摘自当前文件**（已复核，非记忆转述）：

| # | 位置 | 现文本（逐字） | 应改为 |
|---|---|---|---|
| 1 | 上游 §1.2 能力边界（`ontology-capability-design.md:64`） | 「**孪生应用** \| 依赖推演物化与实时回显；维持 P3 观察项」 | 孪生应用 → 本期 P0/P1 落地（依 T1 **查询期直连**，**不依赖物化**）；同行的推演沙盘拆分说明保留 |
| 2 | 上游 §1.3 对标表（同文件 `:77`） | 「七、孪生应用 \| 拖拽指标/告警/图表、绑定本体查询 \| **不做** \| 依赖推演与实时物化」 | 「七、孪生应用 \| 同上 \| **P0 部分做**：组件栅格 + 绑定本体查询 + 发布只读页；3D 场景编辑 P1；因果传导不做」 |
| 3 | 上游 §1.5 对照矩阵 AF-22（同文件 `:148`） | 「\*\*部分具备\*\*：`query_service` + `sql_guard` + Agent 工具注册可复用；推演/孪生端不存在」 | 孪生端经 `onto_ontology_query` 消费，AF-22 消费端由「图/问数/Agent/导出」扩为含**应用端**；沙盘端按姊妹规格 V1 裁决单独表述 |
| 4 | 上游 §7.1 分期图（同文件 `:1066`） | `P1C --> P2B["P2-2 多本体合并 / 推演孪生（观察项）"]` | 拆为两条：推演沙盘已在 P1 立项；孪生应用单列 P0/P1 节点（本文档 §7），P2-2 仅留多本体合并 |
| 5 | 姊妹沙盘规格 §关账表（`2026-11-01-simulation-sandbox-design.md:364`） | 「§1.2 非目标表 \| …推演沙盘已单独立项（沙箱域物化裁决）；**孪生应用维持非目标**」 | 「孪生应用已单独立项（见 `2026-11-01-digital-twin-app-design.md`）」 |

> 第 5 处是本方案自审时新发现的：沙盘规格的关账表在**它自己那一版里**把孪生写成了"维持非目标"。漏改它会让两份规格互相打脸，而前 4 处改完仍不足以消除矛盾。

### 0.2 与沙盘「沙箱域例外物化」裁决的关系（**不冲突，且必须说清**）

姊妹规格裁决 **V1**：D2「实例不落库」维持为**生产域红线**，仅在沙箱域开例外物化（克隆世界态）。本方案的 T1 选直连，理由正是**孪生属生产域**——看板展示的是源库当前事实，不是克隆态，因此受 D2 红线约束，不得复用沙箱的物化通道。两个域的唯一合法交点是单向消费：沙盘 P2「推演结果发布」（沙盘规格 `:327`）产出的结论可回链到孪生页作为**静态标注组件**，但孪生不写沙盘、不共享 `onto_sandbox_*` 表。

### 0.3 术语撞车预警：「场景」

本方案的 `scene` 指**等距视觉场景模板**（`twin_card.scene_key`），而沙盘规格的 `onto_sandbox_scene` 指**推演世界实例**。两者不是一个东西。落地要求：孪生侧字段与组件命名一律用 `scene_key` / `SceneWidget`，并在 `types/twin.d.ts` 顶部注释写明此区别；禁止孪生代码引用 `sandbox` 域的 `scene` 类型。

---

## 1. 目标与范围

### 1.1 目标

把本体「模式层」的产出（已发布版本 + 对象/属性/关系 + 脱敏标记）包装成**可搭建、可发布、可嵌入的实时孪生看板**，并让查询定义成为跨端复用资产。

一句话验收标准：**给定一个已发布 v1 的本体，可在孪生应用内建卡片、绑查询、看四态、切运行、发布为登录态只读页，且敏感列在非豁免用户处显示为 🔒 而非真值。**

### 1.2 能力边界

| 做（P0） | 不做（明确排除） | 原因 |
|---|---|---|
| 卡片 / 页面 / 组件三层编排 | **自由拖拽与缩放栅格** | `frontend/package.json` 对 `grid-layout`/`gridstack`/`vuedraggable` **零命中**；原型全文件仅 1 处 drag 相关代码（左栏 palette 渲染 `prototype:432`），画布组件本身从未实现拖拽。P0 用跨度 3/6/12 + 上下左右移 + 自动布局（原型 `:315` 同有该按钮）等价覆盖 |
| `onto_ontology_query` 声明 + 编译 + preview | 可视化 SQL 编辑器 / 任意手写 SQL | 手写 SQL 会绕开映射与脱敏闸，破"单一取数口" |
| KPI / 趋势 / 柱状 / 环形 / 告警表 / 图谱组件（图谱 P1） | 报表式分页、导出 Excel、订阅邮件 | 属 BI 通用能力，与孪生定位无关，YAGNI |
| 2D 内置场景模板只读展示 | **3D 等距引擎移植 + 场景配置编辑器 + 实体标记/弹窗/下钻** | T3：进 P1 |
| 页面级 10s/30s/关闭 轮询 | SSE / WebSocket 推送、告警规则引擎与历史去重 | 直连路线下"实时"= 最短 10s 轮询，语义已在 §4.3 说白 |
| 发布登录态只读页 + `role_codes` 授权 | 公开链接、分享票据、水印、限流 | T4：进 P1，须与攻击面防护同批 |
| 列级脱敏 + 卡片三态 + 权限申请单 | 行列级视野策略引擎 | T6 + 上游 §1.2 口径一致 |
| AI 双通道（确定性指令 + 受限生成） | LLM 直出整页布局、LLM 生成查询表达式 | T5 |
| 多人**串行**编辑（后写覆盖 + 更新时间提示） | 协同编辑与冲突合并（OT/CRDT） | 单租户低并发假设（§8.2 A3） |
| 卡片钉住本体版本 + `stale` 提示 | **自动跟随本体新版本** | 结构漂移会静默打穿画面（R5） |

### 1.3 术语表（**严格对齐原型，前后端共用同一套词**）

| 术语 | 对应原型元素 | 实现实体 | 说明 |
|---|---|---|---|
| 孪生卡片 | 左栏 `#myCards` + 面包屑「孪生卡片：智慧工厂产线 · FAC007」（`prototype:266`） | `twin_card` | 顶层容器，钉一个「本体 + 版本」，状态三值：运行中 / 草稿 / 受限 |
| 页面 | 顶部 Tab `#ptabs`（首页/设备健康/能耗管理/生产分析/告警中心 + 「＋」） | `twin_page` | 编辑态才可见「＋」 |
| **模块** | 左栏「本页面模块」`#modList`（`prototype:303`） | palette 类型目录 | **可添加的类型**，非实例。内置：场景视图/设备状态监控/产能统计/能耗分析/告警列表/设备关系图谱 |
| **组件** | 画布 `.widget` `#grid` | `twin_widget` | **已放置的实例**，携带 `query_id`、栅格位、刷新覆盖 |
| 本体查询 | 组件把手上的 `⛓ FAC007.设备OEE`（`prototype:473`） | `onto_ontology_query` | 一等公民，跨端复用 |

> 模块 vs 组件的混用是本模块最容易埋进代码里的语义 bug（一个词两个实体）。落地时后端一律用 `widget_key`（类型）与 `widget_id`（实例）两名，不得都叫 `module`。

### 1.4 相邻模块边界

- **本体建模工作台**（`/admin/kg-ontology`，`componentMap.ts:71`）：查询定义在**本体侧**创建与校验，孪生侧只做"挑选 + 绑定 + 预览"。不复制第二套查询编辑器。
- **推演沙盘**（板块六，**已于 2026-11-01 单独立项**，见 §0.2）：原型「在推演沙盘中推演」与「推演缓解方案」按钮在 mock 中**仅弹 toast 占位**（`prototype:655,:656`），本方案将其定义为**跳转 + 传参**（`scene_key` + `entity_id`）；不共享执行引擎，不读写 `onto_sandbox_*`。
- **图可视化 / 探索 / 智能体**：`onto_ontology_query` 的兄弟消费端；孪生图谱组件复用 `common/graph/GraphCanvas.vue`。
- **门户 / OA 嵌入**：P0 仅同域 iframe（token 走 `Authorization: Bearer`，`utils/request.ts:33`），跨域嵌入随 P1 分享票据一并解决。
- **本体应用发布登记**（`onto_ontology_publish`，`target_type ∈ skill|http|mcp`，`ontology.py:277`）：**刻意不复用**。那张登记「本体→对外契约」，本方案的 `twin_publish` 登记「孪生页→只读路由」，混用将逼 `ck_onto_publish_target` 加 `page` 值并污染其语义。

---

## 2. 总体架构

### 2.1 四层职责

| 层 | 归属 | 职责 | 明确不做 |
|---|---|---|---|
| 语义层 | `onto_ontology_query`（新增，`onto_` 域） | 声明"查什么" | 不存数据、不存结果 |
| 编排层 | `twin_*`（新增 6 张） | 卡片/页面/组件/发布/授权 | 不生成 SQL、不出现物理表名 |
| 执行层 | `ReadonlyQueryService` + `SqlGuard`（复用，微扩） | 唯一取数口：租户隔离 + 只读校验 + 行数上限 | 不开第二条 SQL 通道 |
| 出口层 | `masking.apply_masking`（复用纯函数） | 列级脱敏 + 角色豁免 | 不做行列视野引擎 |

### 2.2 数据流（一次页面刷新）

```
浏览器（twin store，页面级 10s 调度）
  → POST /api/v1/twins/pages/{id}/data        {params}
     ├─ 权限校验：twin_card_share / sys_role → 卡片可读？
     ├─ 逐组件：query_id → onto_ontology_query(version 钉版, compiled_sql, sql_sha256)
     │    ├─ 缓存键 (tenant, query_id, sha1(param_values), principal_role_hash) 命中？→ 直接返回
     │    └─ 未命中 → ReadonlyQueryService.run(source_id, sql, limit, params)
     │                   └─ SqlGuard.is_readonly → 源库执行 → 行结果
     │         → apply_masking(rows, rules, user)   ← 出口脱敏（内部走 user.has_any_role(rule.exempt_roles)）
     │         → 按 result_shape 归一（kpi/trend/bar/donut/table/entity_set/graph）
     └─ 组装 per-widget {state: ok|empty|error|masked, columns, rows, updated_at, masked_fields[]}
  → WidgetGrid 按 state 分派四态（loading 由前端本地态驱动）
```

### 2.3 挂载点（沿用既有机制，共 3 处）

| 挂载 | 做法 | 依据 |
|---|---|---|
| 菜单 | `sys_menu` 新增一行：`id 2406`、parent `2401`、path `/admin/kg-twin`、permission `kg:twin:read`、i18n `knowledge.menu.twin`、icon `DeploymentUnitOutlined`，`INSERT … WHERE NOT EXISTS` 幂等 | 照抄 `docs/sql/menu_knowledge_governance.sql:42`（2405 本体） |
| 组件 | `componentMap.ts` 增 `'kg-twin': markRaw(TwinWorkspace)` | 与 `'kg-ontology'` 同机制（`componentMap.ts:71`） |
| 只读运行态路由 | `/twin-p/:slug` 挂 `router/index.ts` **顶层**（不进 `AppLayout` 子树），`meta:{requiresAuth:true, hideHeader:true}` | `/login` 已证明顶层 + `hideHeader` 可行（`router/index.ts:7-10`） |

新增文件：`api/twin.ts`、`stores/twin.ts`（pinia）、`types/twin.d.ts`、`views/twin/**`。

---

## 3. 数据模型

沿用现库规范：`Base, TenantMixin`、`BigInteger` 主键、显式 `CheckConstraint` / `UniqueConstraint`、JSONB 配置列、中文 comment。**7 张新表，零既有表扩列，1 个 Alembic 迁移。**

### 3.1 `onto_ontology_query`（本体查询定义，T2 一等公民）

```
id, tenant_id
ontology_id      → onto_ontology.id (FK, ondelete=CASCADE)
version          Integer, server_default '0'   -- 钉住的发布版本；0=草稿态，禁止编译
code             String(64)   -- 本体 + 版本内唯一
name             String(200), description Text
result_shape     String(16)   -- kpi|trend|bar|donut|table|entity_set|graph  ← 组件配对校验锚点
spec_json        JSONB        -- {objects[], attributes[], agg, group_by[], filters[], time_window, limit}
params_json      JSONB        -- [{name,type,default,control}]
compiled_sql     Text         -- 无注释单语句模板，含 :p_xxx 占位符
sql_sha256       String(64)   -- 审批/执行一致性锚点（形态抄 meta_data_write_request.sql_sha256）
mask_rules_json  JSONB        -- 出口脱敏所需：[{field, strategy, keep_prefix, keep_suffix, exempt_roles[]}]
verify_status    String(16)   -- pending|verified|failed
verify_detail_json JSONB      -- {columns[], row_count, elapsed_ms, blocked_columns[]}
status           String(16)   -- enabled|disabled（version=0 时强制 disabled，同 MetaOntologyPublish）
creator_id, created_at, updated_at
uq_onto_query_code       (tenant_id, ontology_id, version, code)
idx_onto_query_ontology  (ontology_id, version, status)
ck_onto_query_shape      result_shape IN (...)
ck_onto_query_status     status IN ('enabled','disabled')
```

### 3.2 `twin_card`

```
id, tenant_id, name String(200), icon String(32), description Text, source_template_key String(64) NULL
ontology_id → onto_ontology.id (CASCADE), ontology_version Integer
scene_key     String(64) NULL      -- 内置场景模板；P0 只读展示
scene_config_json JSONB NULL       -- P1 场景编辑器写入
runtime_state String(16)           -- draft|live|paused（对齐原型"运行中/草稿"）
owner_id, created_at, updated_at
uq_twin_card_name (tenant_id, owner_id, name)
```

### 3.3 `twin_page`

```
id, tenant_id, card_id → twin_card.id (CASCADE), name String(200), sort_order Integer
refresh_json JSONB     -- {mode:'interval'|'manual'|'off', interval_seconds: 10|30|0}
created_at, updated_at
uq_twin_page_name (card_id, name)
```

### 3.4 `twin_widget`

```
id, tenant_id, page_id → twin_page.id (CASCADE)
widget_key  String(32)              -- scene2d|kpi|trend|bar|donut|alert_table|graph …
title       String(200)
query_id    → onto_ontology_query.id (ondelete=SET NULL) NULL  -- 为空即原型"待绑定"空态
param_values_json JSONB, display_json JSONB  -- display_json {series_map, thresholds, columns, span}
grid_json  JSONB                    -- {x,y,w,h}，12 列；原型 span2→w=6、span4→w=12
refresh_json JSONB NULL             -- 覆盖页面级
sort_order, created_at, updated_at
ck_twin_widget_key (widget_key IN (...))
```

> `query_id` 用 **SET NULL**：删除查询定义不删组件，而是把组件打回"待绑定"空态——与原型 `.wempty` 语义一致，且天然形成反向引用保护（删除前可查 `bindings` 列出受影响组件）。

### 3.5 `twin_publish`（页面发布登记）

```
id, tenant_id, card_id, page_id, slug String(32) UNIQUE(tenant_id, slug)  -- 随机不可猜串，非自增 id
access String(16)          -- org|role（public 留 P1）
role_codes_json JSONB      -- access=role 时生效
version Integer            -- 发布时冻结的页面快照版本
status enabled|disabled, published_by, published_at
```

### 3.6 `twin_card_share`

```
id, tenant_id, card_id, grantee_type user|role, grantee_id, grantee_code String(64)
perm read|edit, source manual|request, expires_at TIMESTAMP, granted_by, created_at
uq_twin_share (tenant_id, card_id, grantee_type, grantee_id|grantee_code)
```

驱动原型「我的卡片 / 共享给我的（只读）」两组（`prototype:295-299`）。

### 3.7 `twin_access_request`

```
id, tenant_id, card_id, applicant_id, reason Text, required_role_code String(64)
status pending|approved|rejected|expired, approver_id, reviewed_at, expires_at, created_at
```

形态取自 `DataWriteRequest`（表 `meta_data_write_request`，`write_request.py:17`）的申请/审批/过期三段；**不发一次性令牌**——批准的产物是写入 `twin_card_share`，而非 token 消费。

### 3.8 状态机

```
卡片   draft ──发布任一页──> live ──手动──> paused ──手动──> live
查询   pending ─compile成功─> verified ─绑组件─> enabled
          └─compile失败(缺映射/敏感未覆盖/JOIN 不唯一)─> failed ──修 spec──> pending
组件   未绑定(query_id=NULL) ─绑定─> 已绑定 ─shape 不符─> 拒绝(不落库)
发布   enabled ─停用─> disabled；本体发新版 → stale=true 提示（不自动跟随）
申请   pending ─approve─> approved(+写 share) │ reject │ expires_at 到期─> expired
```

### 3.9 迁移策略

单个 Alembic revision，按仓库 `backend/MIGRATIONS.md` 约定：`upgrade` 建 7 表 + 约束 + 索引；`downgrade` 逆序 drop（`onto_ontology_query` 最后 drop，因其被 `twin_widget` 引用）。菜单 SQL 同步补入 `docs/sql/init.sql` 与 `docs/sql/menu_knowledge_governance.sql` 两处，保持幂等写法一致。

---

## 4. 关键业务闭环

### 4.1 查询编译：7 步，全程 fail-closed

| 步 | 动作 | 依据/约束 |
|---|---|---|
| 1 | **版本解析**：`version > 0` 才允许编译，输入取 `onto_ontology_version.snapshot_json`（发布时冻结的对象/属性/关系/映射全量，`ontology.py:69`）；`version=0` 直接拒绝 | 与 `MetaOntologyPublish`「草稿态仅 disabled」同律；保证本体发新版打不穿已上线看板 |
| 2 | **元素解析**：`spec_json` 的 object/attribute code 在快照内解析，仅接受 `review_status=='accepted'` | 口径复用 `OntologyAgentService._accepted()`（`ontology_agent_service.py:47-53`），不另写筛选 |
| 3 | **物理绑定解析**：对象→`meta_table_standard`→`MetaTable`（`source_id` 在此刻确定）；属性→`meta_column_standard`→`MetaColumn.column_name`；跨对象 JOIN 走 `MetaObjectRelation` | 表名实存：`meta_table_standard`（`standard_cdm.py:140`）、`meta_column_standard`（`standard.py:83`）、`meta_object_relation`（`standard_cdm.py:102`） |
| 3′ | **P0 硬限制**：最多 2 个对象、1 跳 JOIN、路径唯一；不唯一则失败并回传候选路径 | 砍掉编译正确性里最贵的不确定性（R1） |
| 4 | **敏感闸（编译期）**：引用列 `pii_level ∈ {L2,L3}` 时须满足「标准 `mask_rule` 非空」或「`security_level_override` 降级至 L1 以下」或「登记豁免」，否则失败并返回 `blocked_columns[]` | **与发布门禁 5 同源**：复用常量 `_SENSITIVE_PII`（`ontology_publish_service.py:54`）与 `_gate5_mask_coverage` 的覆盖判定体（`:348` 定义，判定逻辑 `:370-383`），从中抽出 `_sensitive_covered(pii, mask, override)` 共用；**严禁复制第二份**（两处口径必然漂移） |
| 5 | **SQL 生成**：sqlglot 构造表达式树 → 按方言渲染（复用 `query_service._dialect_of`）。产出必须是**无注释单语句** | `SqlGuard` 对 `--`、`/* */` 零容忍（`sql_guard.py:25,102`）；禁写节点/危险函数见 `sql_guard.py:32-82`；解析失败 fail-closed（`:11`） |
| 6 | **参数化**：过滤值与时间窗编译为 `:p_xxx` 绑定参数，绝不字面量拼接；模板存 `compiled_sql` + `sql_sha256` | 注入面关闭，且"审批的 SQL == 执行的 SQL"可验证 |
| 7 | **预览（dry-run）**：`preview` → `SqlGuard.is_readonly` → `run(limit ≤ 200)` → 回写 `verify_status` + `verify_detail_json` | 把运行期失败前移到设计期；前端绑定抽屉的"预览"即此项 |

### 4.2 唯一一处改动既有公共代码

```python
# backend/app/services/dataops/query_service.py
def run(self, source_id: int, sql: str, limit: int = 100, params: dict | None = None) -> dict
```

- 内部 `text(sql).bindparams(**(params or {}))`；`params=None` 时行为与现状**逐字节一致**。
- 全库调用方共 3 处，均可零改动：`routers/dataops/dataops.py:594`、`ai/tools/dataops_tools.py:183`、`services/kb/table_sync_service.py:68`。
- 新增校验：未知参数名拒绝、参数个数 > 20 拒绝、值类型与 `params_json` 声明不符拒绝。
- `SqlGuard` 继续校验含占位符的模板文本，不校验绑定值。

### 4.3 扇出、超时与"实时"的真实含义

- **页面级批量端点** `POST /twins/pages/{id}/data`：整页刷新只发 1 个请求。8 组件 × 每 10s = 48 req/min，逐组件发请求在直连路线下不可接受。
- 服务端闸门：每请求 `asyncio.Semaphore(4)`、单查询 timeout **5s**（对齐原型 `getSensorStream 超时（5s）` 文案，`prototype:460`）、整页 deadline 8s；**超时组件各自回 error 态，绝不让整页失败**。
- 结果缓存：进程内 TTL，键 = `(tenant_id, query_id, sha1(param_values), principal_role_hash)`，TTL = `min(页面刷新周期, 30s)`。
  > **安全不变量（写进码注释 + 回归测试）：角色签名必须进缓存键。** 否则"有豁免权的用户"未脱敏结果会被"无豁免权用户"命中，等于脱敏形同虚设。
  > 实现：把 `audit_logger` 私有的 `_TTLCache`（`audit_logger.py:107,135`）上提至 `app/core/cache.py` 共用，避免出现第三份内存缓存（`kb_cache` 那套含 Redis 回退，语义更重，P0 不引）。
- 前端节流：`visibilitychange` 隐藏即暂停轮询、回前台立刻刷一次；档位 10秒/30秒/关闭 落 `twin_page.refresh_json`（`prototype:360`），组件可覆盖。
- **"实时"定义说白**：本设计下的实时 = 最短 10 秒轮询 + 查询期直连，**不是推送**。原型顶栏「运行中 · 数据刷新 10s」（`prototype:259`）正是此语义，无需 SSE/WebSocket，亦不因此修订 D2。

### 4.4 发布与只读运行

发布 = 冻结当前页面配置为 `twin_publish` 一行（含 `version` 与组件/绑定的快照），生成随机 `slug`。`/twin-p/:slug` 渲染同一套 `WidgetGrid`，`mode='run'`。

取数走 `POST /twin-p/{slug}/data`，校验链：`slug → twin_publish.status=enabled → card 可读（org 或 role_codes 命中）→ 出口脱敏`。审计日志覆盖每次访问（含 slug 与访问者），**失败即 403，不降级返回空数据**（避免"猜 slug"得到不同反馈信号）。

### 4.5 受限与权限申请闭环

| 场景 | 原型锚点 | 实现 |
|---|---|---|
| 受限卡片（整卡） | 「园区安防孪生 🔒 受限」`prototype:299` + 自动弹权限说明 `pickCard→showPerm` (`:433,:657`) | `twin_card_share` 无记录且 `runtime_state=live` → 列表标 🔒 受限；进入自动开 PermDrawer（受限内容 / 所需角色 / 申请按钮） |
| 申请 → 审批 → 可见 | 「申请访问权限」按钮 `prototype:657` | `twin_access_request` pending → owner 审批 approved → 写 `twin_card_share(read, expires_at)` → 卡片转入「共享给我的（只读）」 |
| 卡片内单列脱敏 | 能耗组件 `masked:true`（`prototype:452`）渲染为「电费成本 🔒 脱敏」（`prototype:464`） | 出口 `apply_masking`（`masking.py:97`，豁免判定 `:112-115`）+ `exempt_roles` 字段（`sqlbot_tool_config.py:152`）；非豁免用户值位显示 🔒 |
| 卡片内单实体限制 | park 场景摄像头/闸机 `masked:true`、周界红外可查 `prototype:581-593` | 靠**查询级过滤**：无权限时该行根本不返回；前端对已知实体渲染 🔒 占位（T6，不建策略引擎） |

### 4.6 错误处理

- 后端错误码统一走 `app/core/api_error.py` 的 `ApiError` 形态（现有惯例），新增：`QUERY_SHAPE_MISMATCH`、`QUERY_SENSITIVE_UNCOVERED`、`QUERY_JOIN_AMBIGUOUS`、`QUERY_MAPPING_MISSING`、`QUERY_DRAFT_FORBIDDEN`、`TWIN_PUBLISH_FORBIDDEN`、`TWIN_ACCESS_REQUIRED`。
- 前端 error 态**必须回显错误码 + 人话原因**，不得只显示"接口异常"（对齐 W6，直接决定这功能能不能自助排障）。
- 取数失败不清空上一次成功结果，改为叠加"数据已过期"提示（孪生看板最忌闪白）。

---

## 5. LLM 使用边界（T5 双通道）

### 5.1 通道划分

| 通道 | 指令样例 | 实现 | 是否经 LLM |
|---|---|---|---|
| **确定性指令** | 「把设备状态监控移到左上」「删除告警列表」「告警列表改表格样式」「自动布局」 | 意图正则 + 组件名匹配 → 直接产出 `grid_json` / `widget_key` 补丁 | ❌ 不经 LLM（零幻觉、零成本、可即时回退） |
| **受限生成** | 「增加设备 OEE 分析模块」「加一个能耗环比图」 | LLM 只能从**该卡片已 verified 的查询**中挑选 `query_id`、指定 `widget_key`、指定栅格位 | ✅ 经服务端校验 |
| **智能问数** | 运行态自由提问 | 复用既有 Agent 会话（已注册 SQLBot 只读工具 + 本体 `browse/resolve/manifest` 导航） | ✅ 已有能力，不新建 |

### 5.2 受限生成的校验三闸（复用 `ontology_semantic_service` 形态）

1. **schema 校验**：产出必须是 `{ops:[{op, widget_key?, query_id?, grid?, title?}]}`，字段白名单外一律丢弃 → `dropped[]` 计数与原因（同 `hallucination_dropped` 形态，`ontology_semantic_service.py:104-128`）。
2. **引用校验**：`query_id` 必须属于本卡片钉住的本体+版本且 `verify_status=verified`；不存在的 code/id 一律丢弃并回执说明。
3. **形状配对校验**：`result_shape` 与 `widget_key` 不匹配即拒绝（kpi 组件绑 `entity_set` 查询 → 拒绝并给出可选查询清单）。

**AI 永不直接落库**：产出先存 draft（会话内存态），前端渲染候选卡（原型 `.embedcard`，`prototype:200-201`），用户点「应用到页面」才走 `POST /twins/pages/{id}/widgets/batch`（确定性写入，可整体回滚）。

### 5.3 禁止项

- 禁止 LLM 产出 SQL、`spec_json`、表达式或任何物理表名。
- 禁止 LLM 触发删除组件以外的破坏性写（删卡片/取消发布/改权限）。
- 提示词只投喂：本体 manifest + verified 查询清单（code/name/result_shape）+ 当前页面组件摘要，**不投喂业务行数据**。

---

## 6. 接口与前端

### 6.1 REST 清单（前缀 `/api/v1/twins`，新 router `routers/twin/twin.py`；查询定义并入 ontology router）

| ID | 端点 | 用途 | 期次 |
|---|---|---|---|
| Q1 | `POST /ontologies/{id}/queries` | 建查询（触发编译） | P0 |
| Q2 | `GET /ontologies/{id}/queries?shape=&kw=` | 列表（供绑定抽屉挑选） | P0 |
| Q3 | `POST /queries/{qid}/preview` | dry-run，回写 verify | P0 |
| Q4 | `PATCH /queries/{qid}` / `DELETE /queries/{qid}` | 改/删（删前查 bindings） | P0 |
| Q5 | `GET /queries/{qid}/bindings` | 反向引用：哪些组件在用 | P0 |
| T1 | `GET /twins/cards` | 我的 / 共享给我的 / 受限（三组） | P0 |
| T2 | `POST /twins/cards`、`PATCH/DELETE /twins/cards/{id}` | 卡片 CRUD（选本体+钉版） | P0 |
| T3 | `POST /twins/cards/from-template` | 模板中心 | P0（2 个内置模板） |
| T4 | `POST/GET /twins/cards/{id}/pages`、`PATCH/DELETE /twins/pages/{id}`、`POST /twins/cards/{id}/pages/reorder` | 页面管理 | P0 |
| T5 | `GET/POST /twins/pages/{id}/widgets` | 组件列表 / 添加（含 shape 校验） | P0 |
| T6 | `PATCH/DELETE /twins/widgets/{id}` | 改标题/绑定/刷新覆盖 / 删 | P0 |
| T7 | `POST /twins/pages/{id}/widgets/layout` | 批量写布局（拖拽、自动布局、AI 应用共用同口） | P0 |
| T8 | `POST /twins/pages/{id}/data` | **页面级批量取数**（四态 + 脱敏） | P0 |
| T9 | `GET /twins/widgets/{id}/data` | 单组件刷新/重试 | P0 |
| T10 | `POST /twins/pages/{id}/publish`、`DELETE /twins/publish/{id}` | 发布 / 停用 | P0 |
| T11 | `GET /twin-p/{slug}`、`POST /twin-p/{slug}/data` | 只读页元数据与取数 | P0 |
| T12 | `POST /twins/cards/{id}/access-request`、`POST /twins/access-requests/{id}/approve\|reject`、`GET /twins/access-requests` | 权限申请闭环 | P0 |
| T13 | `POST /twins/pages/{id}/ai/commands` | 确定性指令通道 | P0 |
| T14 | `POST /twins/pages/{id}/ai/suggest`、`POST /twins/pages/{id}/ai/apply` | 受限生成 + 应用 | P0 |
| T15 | `GET /twins/scenes/templates`、`PATCH /twins/cards/{id}/scene` | 场景模板 / 场景配置 | P1 |
| T16 | `GET /twins/cards/{id}/scene/entities` | 查询行 → 实体标记 | P1 |
| T17 | `POST /twins/publish/{id}/share-token` | 分享票据（含水印/限流） | P1 |

### 6.2 前端组件树（✅ 复用 / 🆕 新增）

```
TwinWorkspace.vue            🆕 壳：ctxbar + grid(238/1fr/336) + statusbar
├─ TwinCardList.vue          🆕 我的 / 共享给我的 / 模板中心（三态徽标）
├─ PageModuleList.vue        🆕 本页面模块 palette（类型目录，非实例）
├─ TwinCanvas.vue            🆕
│  ├─ CanvasToolbar.vue      🆕 标题 + 场景 tag + 2D/3D 段控件 + 自动布局 + 添加模块
│  ├─ WidgetGrid.vue         🆕 12 列栅格（唯一画布实现，只接 mode prop）
│  │  └─ WidgetShell.vue     🆕 把手 + 四态容器（✅ StateWrapper）
│  │     ├─ KpiWidget ✅ StatsCard │ TrendWidget ✅ MultiLineChart │ BarWidget ✅ BarChart
│  │     ├─ GaugeWidget 🆕(需 use([GaugeChart]) 注册) │ AlertTableWidget ✅ a-table + StatusTag
│  │     ├─ GraphWidget ✅ GraphCanvas (P1) │ SceneWidget 🆕 (P1 等距 SVG 移植)
│  └─ overlays               🆕 SceneTag / EntityPopover(P1)
├─ TwinAiDock.vue            🆕 镜像 OntAssistantDock.vue 形态
└─ 浮层                       🆕 PublishModal / AddModuleModal / BindDrawer / DrillDrawer / PermDrawer
```

图表数据契约复用 `types/chart.d.ts`（`LineChartData` / `BarChartData` / `PieChartData`），`result_shape` 归一化在**后端完成**，前端 renderer 不做二次整形——避免两处形状推断。

### 6.3 模式差异契约（从原型 CSS 抽出的唯一实现方式）

原型用两条规则表达全部差异：`body.run .edit-only{display:none}`（`:125`）、`body.edit .wops{display:flex}`（`:163`）。落地为一张矩阵，且**只允许这一种实现**：

| 能力 | 编辑 | 运行 |
|---|---|---|
| 新建卡片/页面、添加/删除/复制模块、布局与跨度、绑定查询、组件把手 ✎ 🗑、保存草稿、发布、AI「编辑/重做/应用到页面」 | ✅ | ❌ |
| 数据轮询、2D/3D 切换、告警行下钻、实体点击弹窗、下钻抽屉、智能问数、全屏 | ✅ | ✅ |
| 权限申请 | ✅ | ✅ |

> **承重原则**：运行态 = 同一套 `WidgetGrid` 关掉把手的结果，**不是第二套组件**。代码中出现 `RunCanvas.vue` 之类文件即视为架构违规。此条防住孪生模块最常见的腐化路径（两份画布实现各自漂移）。

### 6.4 四态实现（全部收在 `WidgetShell`，业务 renderer 不得各自实现）

| 态 | 触发 | 实现 | 原型锚点 |
|---|---|---|---|
| loading | 请求 in-flight | StateWrapper loading slot + 骨架微光；图表与 KPI 降 `opacity .25` | `.skel` `:185-188`（含 `body.loading` 降透明度 `:188`） |
| empty-未绑定 | `query_id == NULL` | 空态卡 + 「绑定本体查询」CTA → BindDrawer | `.wempty` `:461` |
| empty-零行 | `row_count == 0` | 文案区分：「查询返回 0 行，检查时间窗/过滤条件」 | 原型未区分 → 本设计补齐 |
| error | 超时 / SqlGuard 拒 / 编译失败 | `.werr` + 错误码 + ↻ 重试（走 T9） | `:455,:460` |
| masked | 列脱敏 / 受限卡片 / 实体无权限 | 值位 🔒；进受限卡片自动弹 PermDrawer；实体级渲染 🔒 占位 | `:452,:464`、`pickCard:433`、`showPerm:657` |

### 6.5 视觉规则与 token 缺口

- 尺寸基线照抄原型：top 52 / ctxbar 42 / 三栏 238-1fr-336 / statusbar 30；圆角 14/10；过渡 `200ms cubic-bezier(.4,0,.2,1)`。
- 主色族**已实存且逐值相同**（`tokens.css:81-92`：`--accent #4aa3ff`、`--accent-hover #7fd0ff`、`--accent-soft rgba(74,163,255,.12)`、`--ok #4cc38a`、`--warn #f2b66d`、`--err #ff7b72`）→ 业务组件一律 `var(--token)`，**禁止裸 hex**。
- **两个 token 缺口（新增工作项，非假设）**：原型的 `--cyan:#39d3c4`（AI 组件描边、`tag.c`、冷却水/实时曲线）与 `--purple:#b48ef0`（图谱节点、`tag.p`、保养态）在 `tokens.css` 未定义。需在 dark skin 补 2 组 token（含 `*-soft` 变体）并在 light skin 同步补对应值；**只新增变量、不改既有值**（R9）。
- 暗色为默认，主题由既有 `data-theme` 机制驱动；原型状态栏的「主题：深色 ▾」接全局主题，不做模块内主题开关。
- 3D 移植的既有工程约束（P1 直接沿用）：投影 `iso(x,y,z) = [450+(x-y), 250+(x+y)*0.5 - z]`、viewBox `900×460`、复杂场景必须 `depth:true` + `centerDepth()` 按 `x+y` 升序绘制（画家算法）消穿模；浮层定位分母须同步为 460。

---

## 7. 实施路线图

### 7.1 需求 10 项 → 分期归位

| # | 需求项 | 期次 | 理由 |
|---|---|---|---|
| 1 | 卡片 + 多页面 Tab | **P0** | 数据模型骨架 |
| 2 | 编辑/运行模式差异 | **P0** | 一条 CSS 级契约（§6.3），必须一次定对 |
| 3 | 三栏工作台 | **P0** | 238/1fr/336 + AI 栏最小版 |
| 4 | 组件增删/布局/绑定/刷新/四态 | **P0**（真拖拽 → **P1**） | 离散栅格已覆盖原型全部实际交互 |
| 5a | KPI/趋势/柱/环形/告警表 | **P0** | ✅ 已有 5 个 echarts 组件，成本最低 |
| 5b | 2D 内置场景模板只读 | **P0** | 只渲染不编辑 |
| 5c | 3D 引擎 + 场景编辑器 + 实体标记/弹窗/下钻 | **P1** | T3 |
| 5d | 图谱组件接查询 | **P1** | 需新增 `result_shape='graph'` 的节点/边契约，与查询编译同批做才不返工 |
| 6 | 智能问数 + 确定性指令 + LLM 受限生成 | **P0** | T5 已把 LLM 权限收到"只选不造"，成本在 schema 校验与提示词 |
| 7a | 发布登录态只读页 + RBAC | **P0** | T4 |
| 7b | 分享票据 / 公开链接 / 跨域嵌入 | **P1** | 新攻击面须与水印/限流同批 |
| 8 | 列脱敏 + 卡片三态 + 权限申请 + 实体 🔒 | **P0** | T6，实体限制近零成本 |
| 9 | 与本体/资产/图谱/智能体边界 | **P0**；MCP 发布目标 **P2**（沿用上游对 `target_type='mcp'` 的 P2 安排，见上游 `:65`） | 本期只存不执行 |
| 10 | 输出物 | 本文档 | |

### 7.2 MVP（P0）可演示闭环

```
登录 → 新建卡片（选本体 + 钉版本）→ 建 2 条查询并 preview 通过
→ 添加 3 个组件（kpi/trend/alert_table）绑定查询 → 编辑态看得到 数据/零行/错误/脱敏 四态
→ 切「运行」→ 发布 → 打开 /twin-p/:slug 只读页（10s 轮询）
→ 切受限卡片 → 自动弹权限说明 → 提交申请 → owner 审批 → 可见
```

**P0 明确不做**：自由拖拽、3D 编辑与实体交互、告警规则引擎与历史去重、公开链接与水印、行列视野引擎、实例物化与任意时间回溯、MCP/HTTP 发布目标、协同编辑。

### 7.3 P0 任务拆分（可直接转开发任务）

| ID | 任务 | 关键产出 | 依赖 |
|---|---|---|---|
| P0-1 | Alembic 迁移 7 表 + 菜单/权限 SQL | 迁移可 upgrade/downgrade | — |
| P0-2 | `onto_ontology_query` 服务：编译 7 步 + preview + 反向引用；抽 `_sensitive_covered()` | 单测覆盖 6 类失败路径 | P0-1 |
| P0-3 | `ReadonlyQueryService.run` 扩 `params` + 等价回归（3 调用方） | `params=None` 行为不变 | — |
| P0-4 | 批量取数服务：扇出闸门 + TTL 缓存（键含角色签名）+ 出口脱敏 | W8 / W11 通过 | P0-2, P0-3 |
| P0-5 | 前端三栏壳 + `WidgetGrid/WidgetShell` 四态 + 5 类 renderer + 绑定抽屉 | W1-W7, W9 | P0-2 |
| P0-6 | 卡片/页面/组件 CRUD UI + 离散栅格 + 模式切换 | W3, W4 | P0-5 |
| P0-7 | 发布 + `/twin-p/:slug` 只读路由 + 访问校验与审计 | W12 | P0-4 |
| P0-8 | 受限三态 + 权限申请审批闭环 | W5, W13 | P0-6 |
| P0-9 | AI 双通道（确定性指令 + 受限生成 + 应用到页面） | W14 | P0-5 |
| P0-10 | tokens 补 `--cyan`/`--purple` + 全站回归 | W2, R9 | — |
| P0-11 | **规格关账（上游 4 处 + 姊妹 1 处）** | W16 | — |

### 7.4 测试策略

- **单元**：编译 7 步各失败路径（缺映射 / suggested 未采纳 / 敏感未覆盖 / JOIN 不歧 / 草稿态 / shape 不配对 / 参数越界）；`_sensitive_covered()` 与发布门禁 5 的**同源一致性**用例（同一列集，两处结论必须相同）。
- **安全回归（最高优先）**：W11 双角色交替命中缓存；W10 L2 列编译拒绝；越权 slug → 403。
- **等价回归**：`params=None` 对 3 个既有调用方逐字节等价（对比响应体快照）。
- **前端**：`WidgetShell` 四态组件测试（✅ 已有 vitest 基建）；栅格 span↔w 映射纯函数测试。
- **不做**：真实外部数据源的性能压测（列入待核实 U3，不在 CI 内依赖外网）。

### 7.5 风险登记（严重性 × 概率）

| ID | 风险 | 触发信号 | 缓解 | 兜底 |
|---|---|---|---|---|
| R3 | **缓存键漏角色签名 → 脱敏绕过**（安全事故） | 双人交替测试命中错值 | 不变量入码注释 + W11 回归 + review 清单 | 键结构固化，任何改动必须过 W11 |
| R1 | 映射缺失致编译失败率高 | preview 通过率 < 60% | 精确报错 + 回传"缺失映射清单" + 一键跳本体侧修复 | P0 只对 demo 本体（已完成映射）承诺可用 |
| R2 | 直连打库负载/延迟 | 单页刷新 p95 > 3s、源库告警 | 批量端点 + Semaphore(4) + TTL 缓存 + 隐藏暂停 + 档位下限 10s | 默认档位降为「关闭」，由用户显式开启 |
| R4 | 无实例物化 → 趋势/同比环比/告警历史受限 | 产品要求"任意时间回溯"或"告警去重与历史" | 时间窗交库端 SQL（窗口函数）；同比环比用双查询拼装 | **触发即重开 T1 的 B 方案并显式修订上游 D2**，不得偷偷加物化 |
| R6 | 扩公共取数口引入回归 | 既有链路报错 | `params=None` 等价测试覆盖 3 调用方 | 回退为孪生专用 service（会破"单一取数口"，须评审） |
| R5 | 钉版与本体新版本静默漂移 | 本体发新版后画面仍用旧结构且无提示 | 卡片/查询显示 `stale`（抄 `ontology_apppublish_service.py:52`）+ 手动升级向导 | 禁止自动跟随——结构漂移打穿画面不可接受 |
| R7 | **规格未关账 → 文档与实现背离** | 上游规格仍写「孪生 不做/P3」，沙盘规格关账表仍写「维持非目标」 | 同 PR 回改 5 处（§0.1） | 未关账即 W16 不通过，阻断验收 |
| R10 | 发布 slug 可枚举 → IDOR | 遍历 slug 成功 | 随机不可猜串 + 每次访问校验 `role_codes` + 审计留痕 | 加限流与短时效（随 P1 分享票据） |
| R8 | 编辑/运行两套画布漂移 | 出现 `RunCanvas.vue` 类文件 | §6.3 承重原则：`WidgetGrid` 只接 `mode` | 写入非目标，review 拦截 |
| R9 | 补全局 token 引发全站视觉回归 | 其他模块配色异常 | 只新增变量、不改既有值；light skin 同步 | 先在孪生模块局部定义，验证后上提 |

---

## 8. 事实与推断分离

### 8.1 事实清单（均可核查）

| 事实 | 依据 |
|---|---|
| 原型三栏 `238px 1fr 336px`，顶栏 52 / 上下文栏 42 / 状态栏 30 | `ontology-digital-twin-preview.html:93,52,77,211` |
| 原型 6 个等距场景（factory / energy / warehouse / transit / park / lineA），含 `restricted`/`depth` 标志 | `prototype:501`（`const SCENES={`）、park `:539`、lineA `:595` |
| 投影与 viewBox 参数 | `prototype:489`（`iso`）、`322`（`viewBox 900 460`）、`622/629`（`centerDepth`） |
| 8 个组件模型与 `span/err/empty/masked/ai` 标志 | `prototype:449`（`let WIDGETS=[`）至 `:458`；`sensor` err `:455`、`ratio` empty `:456`、`energy` masked `:452`、`graph` span4 `:457` |
| 四态样式与骨架动画均已存在 | `prototype:182-188` |
| 上游规格现文本（**已逐字复核**） | `2026-10-31-ontology-capability-design.md:64`「维持 P3 观察项」、`:77`「**不做**」、`:148`「推演/孪生端不存在」、`:1066` 分期图「推演孪生（观察项）」 |
| 不存在任何"已保存查询/指标"一等公民；CQ 只存自然语言 + 校验结论 | `ontology.py:165-191`（无表达式列） |
| `ReadonlyQueryService.run` 签名与全库 3 个调用方 | `query_service.py:41`；`dataops.py:594`、`dataops_tools.py:183`、`table_sync_service.py:68` |
| SqlGuard：解析失败 fail-closed / 拒注释 / allow roots / 禁写 `Set` / sleep 族黑名单 | `sql_guard.py:11`、`:25`+`:102`、`:28`、`:45`、`:62-64` |
| 发布门禁 5 已按 `pii_level≥L2 → mask_rule/降级/豁免` 校验（本方案抽共用函数的源） | `ontology_publish_service.py:24`（文档）、`:54`（`_SENSITIVE_PII`）、`:348`（`_gate5_mask_coverage`）、`:370-383`（判定体）；错误码 `PUBLISH_BLOCKED_MASK_COVERAGE` 在 `api_error.py:56` |
| 版本快照 `snapshot_json` 冻结对象/属性/关系/映射/CQ 全量 | `ontology.py:69` |
| `onto_ontology_publish.target_type` CHECK 仅 `skill|http|mcp`；`version=0` 强制 disabled；`stale` = 登记版本落后 `current_version` | `ontology.py:256`（表名）、`:277`（CHECK）；`ontology_apppublish_service.py:8`、`:52`（stale）、`:81`（草稿强制 disabled） |
| 申请→审批→过期的单据形态已存在（表名 `meta_data_write_request`） | `write_request.py:17` |
| 列级脱敏为纯函数，豁免靠 `user.has_any_role(rule.exempt_roles)` | `masking.py:97`（`def apply_masking`）、`:112-115`（豁免判定）；`sqlbot_tool_config.py:152`（`exempt_roles`） |
| 可复用图表组件**实测 5 个**：`BarChart` `LineChart` `MultiLineChart` `PieChart` `StackedBarChart`；通用件 `StateWrapper` `StatsCard` `StatusTag` 均在 | `frontend/src/components/charts/`、`components/common/`；数据类型 `types/chart.d.ts:19,26,34` |
| 暗色 token 主色族与原型逐值一致 | `styles/tokens.css:81-92` |
| `--cyan:#39d3c4` 与 `--purple:#b48ef0` 在 `tokens.css` **未定义** | grep 无命中（仅 `prototype:21,26` 定义） |
| 前端**无任何**网格/拖拽类依赖（查询词 `grid-layout`/`gridstack`/`vuedraggable`/`drag` 全部零命中） | `frontend/package.json` |
| 菜单挂载机制与 2405 本体行样例 | `docs/sql/menu_knowledge_governance.sql:42`；`componentMap.ts:71` |
| 顶层路由 + `hideHeader` 先例 | `router/index.ts:7`（`/login`）、`:10`（`requiresAuth:false, hideHeader:true`） |
| 进入受限场景**自动**弹权限抽屉（本方案 W5 的行为依据，非推测） | `prototype:433` 末尾 `if(S&&S.restricted)showPerm()`；抽屉内容三段 + 申请按钮 `:657` |
| 模式切换仅靠 `body.edit/body.run` 类 + toast，**无第二套画布** | `prototype:660`（`setMode`） |
| 顶栏「运行中 · 数据刷新 10s」/ 页面级刷新档位下拉 / 自动布局按钮 | `prototype:259`、`:360`、`:315` |
| 沙盘裁决 **V1**：D2 仍为**生产域红线**，仅沙箱域开例外物化 | `2026-11-01-simulation-sandbox-design.md:17` |
| 沙盘 P2 将推演结果回链孪生应用；且其关账表已将孪生写作「维持非目标」 | 同文件 `:327`、`:364` |
| 新建**平级服务/路由目录**已有先例（本方案 `services/twin/`+`routers/twin/` 沿用此形态） | 同文件 `:203`、`:215` |
| 上游规格正文写作 `meta_ontology_publish` / `meta_ontology_version`，**代码实际表名为 `onto_ontology_*`** | 规格 `:423` vs `ontology.py:256`（实施时以代码为准） |
| 错误码集中在 `app/core/api_error.py`（新增错误码沿用该模块） | `api_error.py:56` |

### 8.2 假设（未验证，不作为验收依据）

| ID | 假设 | 风险 |
|---|---|---|
| A1 | demo 本体的对象/属性映射已完成到足以支撑 ≥ 2 条 verified 查询 | 若否，P0-2 无法演示；须先造 seed 本体——**已证实为否**（见 §8.3 U1），已由迁移 `2026_11_01_0012_seed_twin_demo_mapping.py` 补齐 |
| A2 | 单租户低并发下 `Semaphore(4)` + 30s TTL 足以护住源库 | 沿用上游 A3 的同类假设，未实测 |
| A3 | 10s 轮询的"实时"语义被业务方接受 | 若要求秒级推送，须重开 T1/新增 SSE |
| A4 | 2 对象 / 1 跳 JOIN 覆盖 P0 全部演示组件 | 若产品要"多表关联口径"，须提前进 P1 编译增强 |
| A5 | 确定性指令的正则意图能覆盖原型示例的三类指令 | 概率高，但边界外表述会落到"未识别"回执 |

### 8.3 待核实（明确未读到 / 未实测）

| ID | 待核实项 | 谁在何时核实 |
|---|---|---|
| U1 | ~~默认 demo 本体与数据源选哪个（是否需新建 seed 数据）~~ **已核实（2026-11-01，Plan 1 Task 0 探测 + Task 0b）**：`scripts/twin_mapping_probe.py` 实测 14 条 `(租户, 本体, 版本)` 组合的 `mapping_rate` **全为 0.0**；根因是 0009 的版本快照硬编码 `"properties": []` / `"mappings": {"table": [], "column": []}`，且库内无任何 `meta_table_standard` / `meta_column_standard` 的 accepted 行——**无现成可演示本体**。处置：迁移 0012 为 `sales_ontology` 建 `twin_demo` schema（客户/订单/产品三表 + 含手机号的样例行）、登记 `twin-demo` 数据源（凭据取 `DB_*` 环境变量、Fernet 落库）、补 11 条 accepted 属性引用与 3+11 条表/列绑定、回写 JOIN 连接键，并**追加**（不改写历史）`current_version + 1` 快照。验收：探测复跑 `sales_ontology` v4 = `obj 3/3`、`attr 11/11`、`rate 1.0`；`downgrade -1` 后残留十项均为空 | 已关（Plan 1 Task 0b） |
| U2 | `result_shape='graph'` 的节点/边归一契约（P1 图谱组件前置） | P1 启动时 |
| U3 | 真实源库上批量取数的 p95 延迟 | 首次接入真数据源后压测（不进 CI） |
| U4 | 审计中间件是否覆盖 `/twin-p/*`（`audit_logger` 的 `required_permissions` 组合） | P0-7 |
| U5 | Electron 桌面端下 `/twin-p/:slug` 的可访问性（base 与 API 地址注入） | P0-7 一并验证 |
| U6 | 同比/环比是否必须库端窗口函数（方言差异：postgres vs mysql/doris） | P0-2 |

---

## 9. 原型对齐验收清单（浏览器 / Network 可判定）

| ID | 检查项 | 通过判据 |
|---|---|---|
| W1 | 三栏与条带尺寸 | top 52 / ctxbar 42 / 左 238 / 右 336 / statusbar 30；1280×800 无横向滚动 |
| W2 | token 一致性 | 主色 `#4aa3ff`、成功 `#4cc38a`、错误 `#ff7b72`、青 `#39d3c4`、紫 `#b48ef0` 均来源 `var(--*)`；业务样式表内无裸 hex |
| W3 | 模式差异 | 切「运行」后 `.edit-only` 与组件把手全隐，轮询/下钻/问数仍可用；编辑态把手齐全 |
| W4 | 页面 Tab | 5 个页面 + 「＋」仅编辑态可见；切换触发一次加载骨架 |
| W5 | 卡片三态 | 运行中/草稿/受限徽标正确；进受限卡片自动弹 PermDrawer |
| W6 | 四态渲染 | 构造 4 类查询（正常/0 行/未绑定/权限外敏感列）分别命中 数据、零行空态、绑定 CTA、🔒；错误态回显错误码 |
| W7 | 刷新档位 | 10秒/30秒/关闭 生效；隐藏标签页暂停轮询、回前台立即刷一次（Network 可证） |
| W8 | 批量取数 | 整页刷新只发 **1 个** `pages/{id}/data` |
| W9 | 形状配对 | kpi 绑 `entity_set` 被服务端拒绝且原因可读 |
| W10 | 敏感闸 | 引用未覆盖 L2 列编译失败，`blocked_columns` 明细可见 |
| W11 | **缓存安全不变量** | 角色 A（豁免）与 B（不豁免）交替请求同一查询，B 不得命中 A 的未脱敏结果 |
| W12 | 发布与只读 | `/twin-p/:slug` 无左导航与把手；越权角色 403 且审计留痕 |
| W13 | 权限申请闭环 | 申请 → owner 审批 → 转入「共享给我的（只读）」并含过期时间 |
| W14 | AI 双通道 | 「移到左上」不请求 LLM；「加 OEE 环形」产候选组件且非法项被丢弃并回执 |
| W15 | 公共代码回归 | `params=None` 时 3 个既有调用方行为逐字节不变 |
| W16 | 规格关账 | §0.1 的 **5 处**已改（上游 4 + 姊妹沙盘 1），AF-22 应用端一行可追溯 |

---

## 10. 需用户决策项（本方案未自决的三处）

### Q1 权限申请的审批人范围（驱动：§4.5）

- **A（本方案默认）**：仅卡片 `owner` 可批 —— 最小授权面，但 owner 不在岗即卡死。
- **B**：owner 或持 `kg:twin:publish` 者可批 —— 团队可用性更好，代价是发布权变相成为授权权。

### Q2 P0 演示本体来源（驱动：假设 A1 / 待核实 U1）

- **A（本方案默认）**：复用现有已完成映射的本体，若不足则补一份 seed 迁移造 demo 本体。
  - **裁决（2026-11-01，已执行）**：选 A 的后半枝——探测证实无现成可演示本体，故新增迁移
    `2026_11_01_0012_seed_twin_demo_mapping.py` 只补 `sales_ontology`（三对象 / 11 属性，落在
    A4 的 2 对象 1 跳限制内）；`supply_chain_ontology` 维持 0.0、不属 P0 演示范围。
    代价已知：生产库升级也会多出 `twin_demo` 的三张假表与一份重发布版本（行上有稳定标记可清）。
- **B**：P0 交付不以真实数据为验收条件，改为"preview 通过"即可（会把 R1 风险推到上线后）。

### Q3 卡片是否需要 `paused` 运行态控制（§3.2 已留状态位）

- **A（本方案默认）**：P0 提供「暂停/恢复」，语义 = 停轮询但页面仍可访问（零成本，运维价值高）。
- **B**：P0 隐藏该按钮，P1 再开（`runtime_state` 仍预留，不影响迁移）。

> 三处均已在正文标注默认选择；不回复即按 A 执行。
