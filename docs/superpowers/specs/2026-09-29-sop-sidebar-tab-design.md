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
