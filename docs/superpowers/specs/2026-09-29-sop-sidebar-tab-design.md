# 智能助手 · SOP 流程侧栏标签页设计

- 状态：设计已确认（待实施）
- 日期：2026-09-29
- 范围：`frontend/src/views/assistant` 为主，`backend/app/ai/sop` 与 `backend/app/ai/agent_factory.py` 仅做最小必要改动
- 关联：`docs/design/sop-assistant-mode-design.md`（SOP 编排引擎本体设计）

## 1. 背景与目标

智能助手左侧导航栏现有「技能 / 专家 / 专家团」三个资源选择标签页。后端已落地 SOP 编排引擎（14 个模板、模板 CRUD API、执行与 HITL 人工验收、运行状态快照），但前端缺少对应的入口：用户无法在侧栏选择/配置 SOP，也无法直观看到执行过程。

**目标**

1. 在左侧导航栏「专家团」之后新增「SOP流程」标签页，实现方式与现有三个模块保持一致。
2. 支持自定义 SOP 的**配置**（步骤增删改）、**调用**（选中生效）与**触发**（发消息执行）。
3. 在对话区清晰、实时地展示执行过程：各步骤状态、执行结果、异常信息。

**非目标**

- 不做独立路由级 SOP 管理页面。
- 不重写后端编排引擎；`SOPEngine` / `SOPAgent` / `GoalStep` 行为不变。
- 不把 `thinking` / `deep_research` 的默认链路切到 SOP（仍需先补齐联网检索执行器）。

## 2. 已确认决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 侧栏只做**选择器**（列表/选中/清除/新建入口）；执行与实时监控复用对话区 `SOPRenderer`；模板配置放独立抽屉 | 侧栏宽度有限，现有三个 tab 均为轻量选择器；复用已建好的渲染器避免重复实现时间线 |
| D2 | **选中即切 `sop` 会话模式**，随后在输入框发消息触发 | 与技能/专家/专家团既有行为完全一致，改动最小、无新增运行入口 |

## 3. 现状锚点（代码事实）

- `frontend/.../SessionSidebar.vue:54` — `<a-tabs v-model:activeKey="resourceTab">`，pane 依次为 `skill`(技能, :55)、`agent`(专家, :63)、`team`(专家团, :69)；`resourceTab` 类型定义在 `:107`。
- `frontend/.../AgentSelector.vue` — 可参照范式：折叠头部 + loading/错误/空三态 + 按类目分组 + `selectedId` 高亮 + `emit('agent-change', info | null)`（:120-132）；样式为 scoped less（因 scoped 无法跨组件复用，需整体复制以保持一致）。
- `frontend/.../AssistantPanel.vue:558/566/576` — `handleSkillChange` / `handleAgentChange` / `handleTeamChange` 的同一范式：`if (info) { sessionType.value = '<mode>'; 清理其它选择 }`。
- 已有可复用资产：`selectedSopTemplateKey` ref、请求体 `sop_template_id`、`api/sop.ts` 的 `listSopTemplates`、`SOPRenderer.vue`（里程碑/验收/交接）、后端 `sop_run` 事件与 `extra_data` 持久化。
- **待修缺陷**：`backend/app/ai/agent_factory.py:358` 的 `get_template()` 只查代码注册表（`app/ai/sop/templates/__init__.py:36` 的 `_BY_ID`），自定义（DB）模板在执行期解析不到，会静默回退到 `builtin:thinking`。

## 4. 设计

### 4.1 文件清单

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `components/SopSelector.vue` | 新增 | 侧栏选择器，结构与样式对齐 `AgentSelector.vue` |
| `components/SessionSidebar.vue` | 修改 | 新增 `sop` pane；`resourceTab` 联合类型扩 `'sop'`；props 增 `selectedSopKey?: string \| null`；emits 增 `sop-change` |
| `components/AssistantPanel.vue` | 修改 | 新增 `handleSopChange`；向侧栏透传 `selectedSopKey`；移除已冗余的 `SopTemplatePicker` 挂载（见 4.7） |
| `components/SopTemplateDrawer.vue` | 新增 | 模板配置抽屉（步骤增删改） |
| `api/sop.ts` | 修改 | 增加 `createSopTemplate` / `updateSopTemplate` / `deleteSopTemplate` |
| `renderers/sop/SOPRenderer.vue` | 修改 | 增加步骤输出、失败原因、异常信息展示 |
| `backend/app/ai/agent_factory.py` | 修改 | 模板解析增加 DB 回退 + 未命中告警 |
| `backend/app/ai/sop/runner.py` | 修改 | `sop_run` 快照改为逐步发送 |

### 4.2 数据流

```
侧栏选中模板
  → emit sop-change(info|null)
  → AssistantPanel: currentSop = info; sessionType = 'sop'; 清空技能/专家/专家团
  → 发消息 body: { session_type: 'sop', sop_template_id: <template_key> }
  → 后端 _create_sop_agent 解析定义（代码注册表 → DB 回退）
  → SOPAgent → runner 产出 step / engine_decision / hitl_pause / sop_run / completed / error
  → 前端: sop_run 覆盖 msg.sopRun；unifiedSteps 作为兜底
  → SOPRenderer 渲染里程碑、状态、反馈、异常
```

`handleSopChange` 与既有三个 handler 同构：选中时置 `sessionType='sop'`，并清空 `currentSkill` / `currentAgent` / `currentTeam`，避免多种资源同时生效。

### 4.3 前置修复：让自定义模板真正生效（必须）

`_create_sop_agent` 解析顺序调整为：

1. `sop_definition`（动态定义，优先级最高）
2. `sop_template_id` → 代码注册表 `get_template()`
3. **新增**：代码注册表未命中 → `SOPTemplateService(self._db).get_by_key(template_id)`，命中则 `SOPDefinition.model_validate(row.definition)`
4. `sop_source`
5. 兜底 `builtin:thinking`

**回退语义收紧（消除静默降级）**：

- 未提供 `sop_template_id`：回退 `builtin:thinking`，属合法默认，记 debug 日志。
- 提供了 `sop_template_id`，但代码注册表与 DB 均未命中：**显式抛 `ValueError`**，由 chat_stream 收敛为 `error` 事件返回前端，不再静默改用内置流程。

这样"选了 A 模板却执行了 B 流程"不可能发生——要么按所选模板正确执行，要么明确报错。

### 4.4 实时性：`sop_run` 事件粒度

**问题**：当前 `sop_run` 只在执行段末发送一次；而 `SOPRenderer` 优先使用 `sopRun` 渲染。若只在段末更新，执行过程中步骤状态会停留在旧值，与"实时查看进展"矛盾。

**改法**：`runner.py` 的 `_drive` 在转发每个 `step` / `engine_decision` / `hitl_pause` 事件后，追加发送一次 `sop_run` 快照（引擎状态序列化开销很小，步骤数量级为个位数）。段末快照保留，用于 `extra_data` 持久化与刷新恢复。

前端 `sop_run` 处理已实现（收到即覆盖 `msg.sopRun`），无需改动。

### 4.5 配置抽屉 `SopTemplateDrawer.vue`

- **列表与权限**：内置模板（`builtin=true`）只读，提供「另存为」转为自定义；自定义模板可编辑、可删除。
- **字段**：模板名称、描述、标签；步骤表支持增删改与排序，每步可配 `subject`、`description`、`verifier_type`(ai/human/none)、`max_attempts`、`loop`(none/goal)、`goal_max_iters`、`artifact_key`。
- **校验**：至少 1 步；`subject` 与 `description` 非空；`max_attempts >= 1`。校验不通过时阻止保存并给出字段级提示。
- **保存后**：写入 `POST/PUT /api/v1/sop/templates`，成功后刷新列表并自动选中该模板（便于立即验证）。

### 4.6 `SOPRenderer.vue` 增强

在现有里程碑（序号、状态、尝试次数、验收方式、迭代轮次）基础上补充：

- 步骤产出摘要（可折叠，避免长文本撑开卡片）
- 失败步骤：红色状态 + 驳回原因 / 失败原因
- 执行异常：顶部醒目错误条展示 `error` 事件内容
- 人工验收挂起：保留已实现的通过 / 驳回（驳回必填原因）面板

### 4.7 与已有 `SopTemplatePicker` 的关系

当前 `SopTemplatePicker.vue` 挂载在输入框上方（`sessionType === 'sop'` 时显示），与新的侧栏选择器功能重叠。本设计**移除该挂载**，统一由侧栏「SOP流程」标签页承担选择职责，避免同一信息两处入口、两处状态。`SopTemplatePicker.vue` 文件删除，`api/sop.ts` 的 `listSopTemplates` 由 `SopSelector` 复用。

## 5. 错误与边界

| 场景 | 处理 |
|---|---|
| 模板列表加载失败 | 侧栏显示错误态 + 「重试」按钮（同 `AgentSelector`） |
| 模板为空 | 显示空态 + 「新建模板」入口 |
| 选中的模板被删除 | `selectedKey` 回落到 null，提示"所选模板已不可用" |
| 提供了 `sop_template_id` 但解析未命中 | 显式 `ValueError` → `error` 事件；不静默降级为内置流程 |
| 步骤执行异常 | `error` 事件 → 渲染器错误条 |
| 步骤验收失败 | 步骤红色 + 原因；达 `max_attempts` 后整流程 FAILED |
| 人工验收挂起 | 渲染器内通过/驳回；驳回原因经 `/confirm` 的 `message` 回传 |

## 6. 测试与验证

**后端（pytest）**

- 新增：`sop_template_id` 命中 DB 自定义模板时解析成功（用 SQLite 内存库建 `sop_templates` 表并插入行）
- 新增：代码注册表与 DB 均未命中时产生告警而非静默降级
- 回归：既有 `tests/ai/sop` 36 项须全绿

**前端**

- `npx vue-tsc --noEmit` 对改动文件无新增错误
- `npm run build` 通过
- 手工冒烟：新建自定义模板 → 侧栏选中 → 确认模式切换为 sop → 发消息 → 观察步骤状态实时推进、人工验收挂起与恢复、失败与异常展示
- 说明：`vitest ^2.1.9` 在 devDependencies 但项目 `test` 脚本未接入、无 vitest 配置；本设计不引入 vitest 配置，组件逻辑以类型检查 + 构建 + 冒烟验证。如需补充组件单测，另开任务。

## 7. 风险与取舍

- **实时快照频率**：逐步发送 `sop_run` 会增加 SSE 事件量。步骤数为个位数，开销可接受；若后续模板步骤数量级增长，改为仅状态变化时发送。
- **侧栏信息密度**：严格保持选择器形态，配置能力下沉到抽屉，避免窄侧栏堆砌表单。
- **内置模板只读**：防止用户改坏系统内置骨架；需要定制走「另存为」。

## 8. 持久化规范：自定义模板的 PostgreSQL 存储

> 本节为存储层**规范说明**，不引入代码改动（已确认只补规范）。§4.1 中的代码改动清单不受本节影响。

### 8.1 存储定位（结论先行）

- 生产环境**已经是 PostgreSQL**：`app/config/_database.py:22` 的 `DATABASE_URL` 固定为 `postgresql://...`；`app/db/database.py` 的 `connect_args` 亦注明"仅对 psycopg2/PostgreSQL 生效"。
- `SOPTemplate`（`app/models/sop.py`）继承 `app.db.database.Base`，并在 `app/db/init_models.py` 登记，由 `main.py` 的 `Base.metadata.create_all(bind=engine, tables=non_kb)` 建表 —— 与项目其它非 `kb_*` 表**完全同一机制**（`kb_*` 三表由迁移 006 独占）。
- 出现的 SQLite 仅存在于离线单测 `tests/ai/sop/test_sop_service.py`（`sqlite:///:memory:`），是测试脚手架，不代表生产存储。
- 因此**不存在"从 SQLite 迁到 PostgreSQL"的数据迁移**。需要规定的是：首次建表的幂等性、种子数据的幂等写入、以及未来表结构演进的通道。

### 8.2 完整字段定义

表 `sop_templates`：

| 字段 | PostgreSQL 类型 | 空 | 默认 | 约束 | 用途 |
|---|---|---|---|---|---|
| `id` | BIGSERIAL | 否 | 自增 | 主键 | 代理主键 |
| `template_key` | VARCHAR(100) | 否 | — | 唯一 + 索引 | 模板稳定标识，对应代码注册表 id；种子幂等依据 |
| `name` | VARCHAR(200) | 否 | — | | 模板名称 |
| `description` | TEXT | 是 | NULL | | 模板描述 |
| `tags` | JSON | 是 | NULL | | 标签列表（字符串数组） |
| `definition` | JSON | 否 | — | | `SOPDefinition` 序列化结果 |
| `builtin` | BOOLEAN | 否 | false | | true=系统内置（种子可刷新）；false=预设/用户自建 |
| `enabled` | BOOLEAN | 否 | true | | 停用后从默认列表隐藏 |
| `created_by` | VARCHAR(100) | 是 | NULL | | 创建人；种子写入 `"system"` |
| `created_at` | TIMESTAMP | 否 | now() | | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | now() | 更新时 now() | 更新时间 |

`definition` 列以 `model_dump(mode="json")` 写入（枚举已转为字符串），结构为：
`SOPDefinition{name, description, steps[], source, template_id}`，其中每步
`SOPStepDef{subject, description, executor_agent, verifier_type(ai|human|none), verifier_agent, max_attempts, loop(none|goal), goal_max_iters, goal_max_retries, goal_verifier_reset_ctx, exec_mode(serial|parallel), group_id, artifact_key}`。

### 8.3 表结构 DDL（主键 / 索引 / 约束）

SQLAlchemy 在 PostgreSQL 上实际生成的等价 DDL：

```sql
CREATE TABLE sop_templates (
    id            BIGSERIAL     NOT NULL,
    template_key  VARCHAR(100)  NOT NULL,
    name          VARCHAR(200)  NOT NULL,
    description   TEXT,
    tags          JSON,
    definition    JSON          NOT NULL,
    builtin       BOOLEAN       NOT NULL DEFAULT false,
    enabled       BOOLEAN       NOT NULL DEFAULT true,
    created_by    VARCHAR(100),
    created_at    TIMESTAMP     NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP     NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT uq_sop_templates_template_key UNIQUE (template_key)
);
CREATE INDEX ix_sop_templates_template_key ON sop_templates (template_key);
-- 各列另有 COMMENT ON COLUMN（由模型 comment= 生成，与 kb_document 等表风格一致）
```

- **主键**：`id BIGSERIAL`。模型用 `BigInteger().with_variant(Integer, "sqlite")`，PostgreSQL 侧渲染为 BIGSERIAL；sqlite 变体仅供离线单测。
- **唯一约束**：`template_key` 唯一，同时承担两个职责 —— 种子幂等（不重复插入）与防止同名模板相互覆盖。
- **索引**：`unique=True` 已隐含唯一索引，`index=True` 额外生成 `ix_sop_templates_template_key`，属冗余但与项目其它表写法一致，保留。
- **时间列**：依赖数据库 `now()`；`updated_at` 由 SQLAlchemy `onupdate` 维护。

### 8.4 首次建表 / 已有数据兼容

- **首次建表**：`create_all` 默认 `checkfirst=True`，表已存在则跳过，已落库数据不会丢失。
- **种子幂等**（`SOPTemplateService.seed`）：按 `template_key` 判定 —— 不存在则插入；存在且 `builtin=true` 则刷新 `name/description/tags/definition`（系统拥有的骨架可随代码演进）；存在且非 builtin 则**跳过**，保留用户改动。
- **存量数据**：`sop_templates` 为本次新增表，无历史存量，无数据迁移工作量。
- **未来演进**：`create_all` **不会为已存在的表补列**。后续新增/修改列必须走 `alembic` 迁移（仓库已有 `alembic/` 与 001-006），不能依赖重启自动生效。
- **读取兼容**：`definition` 以 JSON 文本存储，读取侧统一经 `SOPDefinition.model_validate` 校验；今后为 `SOPDefinition` 增加字段必须是可选字段，否则既有行会校验失败。

### 8.5 读写接口与调用逻辑

分层与项目一致（`routers → services → models`）：

| 层 | 位置 | 职责 |
|---|---|---|
| Model | `app/models/sop.py` | 表定义；登记于 `app/db/init_models.py` |
| Service | `app/services/sop_service.py` | `list_templates` / `get` / `get_by_key` / `create` / `update` / `delete` / `seed` |
| Router | `app/routers/sop.py` | `GET`、`POST /api/v1/sop/templates`；`GET/PUT/DELETE /{id}`；`POST /seed` |
| 执行期解析 | `app/ai/agent_factory.py::_create_sop_agent` | 模板定义解析链（见 §4.3） |
| 前端 | `frontend/src/api/sop.ts` | 列表 / 新建 / 更新 / 删除 |

调用逻辑要点：

- **检索**：`list_templates` 先按 `enabled` 过滤，再在内存做关键词匹配（模板量级为十位数，无需全文索引）。
- **执行期解析顺序**：`sop_definition` → 代码注册表 `get_template()` → **DB `get_by_key()`** → `sop_source` → 仅在未提供 `template_key` 时才回退 `builtin:thinking`；给了 `template_key` 却查不到则显式报错（见 §4.3）。
- **种子触发**：`POST /api/v1/sop/seed`，可重复调用。

### 8.6 并发与事务一致性

- **事务规范**：service 只做 `flush` + `commit`，**禁止** `with self.db.begin()`（项目统一约束；`app/services/base_service.py` 含 `begin`，是历史反例，不得参照）。
- **会话**：经 `get_db` 依赖注入（`autocommit=False`、`expire_on_commit=False`），单请求一会话。
- **写冲突**：当前**无乐观锁**。同一模板被两个用户并发编辑时，后提交者整体覆盖先提交者（`update` 为全字段赋值）。缓解手段：唯一约束保证 `template_key` 不重复；`create` 前显式查重并返回 409。
- **删除**：内置模板（`builtin=true`）由应用层禁止删除并返回 400；表上无外键依赖，删除无级联风险。
- **批量**：`seed()` 在一次事务内完成全部 upsert 后 `commit`，中途异常由调用方回滚。

> 若后续需要真正的并发编辑保护，再引入 `version` 整数列做乐观锁（`UPDATE ... WHERE id=? AND version=?`，影响行数为 0 即判冲突）。本次不实现。

### 8.7 与项目其它表的一致性核对

| 项 | `sop_templates` | 项目其它表 |
|---|---|---|
| 主键 | BigInteger 自增 → BIGSERIAL | 一致（如 `ai_tool_definition`） |
| 列注释 | `comment=` → COMMENT ON COLUMN | 一致（如 `kb_document`） |
| 建表方式 | `create_all`（非 kb 表） | 一致；仅 `kb_*` 走迁移 006 |
| JSON 列 | 使用 `JSON` | 一致（如 `ai_tool_definition`、`ai_mcp_client`） |

### 8.8 未纳入本次的后续项

- `definition` 改 `JSONB` + GIN 索引以支持按内容检索
- `version` 乐观锁
- `sop_templates` 的显式 Alembic 迁移脚本（**新增列前必须**）
- 单测改用真实 PostgreSQL（当前为 SQLite 内存库）
