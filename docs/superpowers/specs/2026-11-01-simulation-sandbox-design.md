# 推演沙盘（沙箱域）设计 · MinWorkBuddy

- **日期**：2026-11-01
- **状态**：✅ 设计已确认（brainstorming 两轮裁决 + 整体设计批准），待实施计划
- **原型基线**：`docs/prototypes/ontology-simulation-sandbox-preview.html`（暗色工作台，与本体建模工作台 token 同源）
- **上游规格**：`docs/superpowers/specs/2026-10-31-ontology-capability-design.md`（下称「主规格」；本文档对其 D2 决策做边界重划，见 §0 与 §11）
- **功能来源**：`docs/ontoflow/ontoflow.md` 六、推演沙盘——「以已经构建的本体应用作为依据，基于世界模型架构运行推演，理清因果影响，提供未来决策的真实反馈」

---

## 0. 裁决记录（本文档成立的四项前提）

四项裁决均在 2026-11-01 头脑风暴会话中由用户明确选定，作为全文不变前提；任何一节与本节冲突时以本节为准。

| # | 裁决 | 内容 | 被否备选 |
|---|---|---|---|
| **V1**<br>D2 边界重划 | **沙箱域例外物化** | 主规格决策 D2「实例不落库、映射下推源库」维持为**生产域红线**：生产本体、生产数据不落实例、永不回写。推演沙盘在**独立沙箱域**按场景物化有上限的克隆快照，检查点/分支只存沙箱域，随场景删除回收 | 重新开 D2 全案（推演改实时下推 + view-time overlay）；维持 P3 观察项仅做预研 |
| **V2**<br>传播引擎 | **确定性引擎 + LLM 辅助建模** | Tick 推进由确定性引擎计算：世界快照 + 因果配置（激活条件 / 效应公式 AST / 规则判据）按固定拓扑序逐 Tick 传播，结果可复现、可回放。因果边/规则配置可由 LLM 辅助生成，落 `origin='llm', status='suggested'`，人审采纳才生效——完整复用主规格 D3 rev.2 三层防线。AI 顾问**只读**沙箱世界做解释、归因、建议，零写权限，不参与数值计算 | 确定性引擎 + AI 只解释（不含 LLM 建模）；LLM 直接模拟推演（不可复现，否决） |
| **V3**<br>行动来源 | **平台内置行动模板库** | MVP 不在本体模式层新增「行动」元素；由平台内置通用行动模板（`supply_cut` 断供、`delay` 延迟交付、`price_up` 提价、`reroute` 切换替代源起步，带参数 schema 与效应映射），场景内选用。与主规格 §10 Q3「可执行行动永久不做」**兼容**：Q3 红线指生产域写回实例的行动，沙箱域场景级行动不构成违反（§11 回写澄清） | 本体侧行动元模型（触碰 Q3 边界、工期大）；自由参数行动（失去审计与门禁语义） |
| **V4**<br>权限口径 | **Q1 裁决不重开** | 行级视野引擎本期仍不做。脱敏在**克隆时**落盘：命中 `mask_rule` 的列按包裹规则写入沙箱（无 `mask_rule` 整列 `'***'`），沙箱内不存在明文敏感值；模块权限做**功能级**（建景/推进/施加行动/删除），沿用 `sys_*` 角色与租户隔离 | 接入行列级视野引擎（主规格 Q1 已裁决 A：本期不做） |

**产出定位**：设计文档 + 实施计划双产出（实施计划由 writing-plans 阶段承接，不在本文档范围）。

---

## 1. 基线与 mock 边界

原型为单文件静态演示，以下行为全部是**硬编码演示假数据**，不是产品事实；产品化的本质是把它们变成**引擎计算结果与配置数据**：

| 原型 mock | 位置（示意） | 产品化替身 |
|---|---|---|
| 因果边及其激活 Tick（`CAUSAL` 数组，`at:1..4`、`weak` 边） | JS 常量 | `onto_sandbox_element`（`kind=causal_edge`）配置数据，激活由引擎求值 |
| 传播观察文案（`OBS` 数组，含「错过 deadline」错误态） | JS 常量 | 引擎逐 Tick 落 `onto_sandbox_observation` |
| KPI 线性公式（健康度按 tick 阈值切换、风险 `0.64+tick*0.02`、产能 `100-tick*8`） | `updateKPI()` | 引擎每 Tick 采样 KPI/风险时序落 `observation`，前端只读展示 |
| 分支对比结果（`0.78 / 0.31` toast 硬编码） | `compareBranch()` | S11 对比端点返回逐 KPI 序列差异表（数据来自引擎） |
| AI 对话三段式 canned 回答 | `sendChat()` | S20 顾问对话（Agent 回合 + 只读工具调用留痕） |
| 检查点 ≤5、行动门禁拒绝 SUP018、执行模式仅 toast | `saveCheckpoint()` / `submitAction()` / `#autoMode` | S9 服务端上限校验；§5 门禁求值；场景 `exec_mode` 落库并约束全部写端点 |
| 世界实体/关系 7 节点手工字面量 | `ENT` 常量 | S1 克隆链路从源库下推 SQL 物化 |

原型中「未来事件」tab 仅按 `at > tick` 过滤 OBS——产品语义升级为**真前瞻预测**：引擎沿已采纳因果配置做有限深度（≤4）正向推演，列出尚未发生的效应与预计激活 Tick（§4 引擎 `preview_future`）。

原型顶栏「隔离沙箱世界 · 未写入生产」徽标在 MVP 必须是**可验证承诺**，证据链见 §5。

---

## 2. 功能拆解（F1–F8，对齐原型八域）

| # | 原型区域 | 产品能力 | 关键约束 |
|---|---|---|---|
| F1 | 场景探索列 | 场景 CRUD：从**已发布本体应用版本**按子图范围克隆世界建景；场景列表/切换；主时间线（由 observation 渲染）；分支列表与对比入口 | 克隆对象 = `onto_ontology_publish` 已登记且 `version=current_version` 的应用；草稿不可建景 |
| F2 | 推演画布（四视图） | ① 世界概览=克隆子图实例图；② 本体结构=只读 schema 图（复用 `GET /ontologies/{id}/graph`）；③ 因果传播=因果配置 + 随 Tick 点亮；④ 实例探索=实体列表+属性+来源回链 | 原型仅实做③；MVP 实做③+①，②④复用现有端点入口。节点详情「来源：数据资产 › dwd_supp_item」= `source_ref_json` 回链（只展示不回查）；「🔒 脱敏」节点 = 克隆时 `masked` 标记 |
| F3 | 传播过程列（四 tab） | 目标体系（声明 + 每 Tick 求值状态）；传播过程（观察流 + 实体/关系/规则计数）；未来事件（前瞻预测）；规则系统（命中/待命中/新触发） | 「Tick 推进后新发现失效规则」产品化解释 = 预配置规则首次被上游状态触发；引擎不自动发现新规则，新规则候选走 LLM→人审（V2） |
| F4 | AI 推演顾问台（三 tab） | 推演对话（只读工具 Agent 回合，工具调用留痕）；行动审计（`action` 全量留痕 + 隔离声明）；推荐问答（基于场景模板生成） | 顾问工具无写接口；模型选择复用现有 `qwen-plus`/`deepseek-r1` 配置链路 |
| F5 | 上下文栏 | 世界来源 chip（本体+版本+已发布态）、克隆范围统计、执行模式三档、检查点保存（≤5）、刷新状态、场景 KPI 模态、删除沙盘回收 | 执行模式为服务端状态（`scene.exec_mode`），非前端演示 |
| F6 | Tick 控制条 | Step +1/+10、自动推进、Tick 跳转（scrubber）、健康度、可控性、目标体系计数、行动窗口、风险 TOP3 | 跳转 = 检查点回放至目标 Tick（确定性保证 §4/§10-A1）；KPI 由引擎物化为时序 |
| F7 | 施加行动模态 | 选目标实体（含视野受限提示）→ 选内置行动模板（S16）→ 填参 → 服务端门禁校验 → 落行动日志 + 写沙箱世界 + 推进 1 Tick | denied 也留痕并返回审计 id；`stepwise` 模式需二次确认（§5） |
| F8 | 四态 | 加载（引擎任务 pending/running 轮询遮罩）、空态（无场景/无观察/无预测三处占位）、错误态（错过 deadline 观察）、权限态（脱敏 + 门禁） | 引擎任务状态口径沿用 `build_job` 的 `status/phase/progress` |

---

## 3. 数据模型

新增 **8 张沙箱域表 + 1 张平台级模板表**。全部与 `onto_ontology*` 生产域物理分表；沿用既有约定：`TenantMixin` 租户行级隔离、表名单数、状态用 `String` + comment 枚举、审计列 `creator_id/created_at/updated_at`、`JSONB` 载荷。

### 3.1 `onto_sandbox_scene` 推演场景（沙盘实例）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger PK | 主键 |
| `ontology_id` | BigInteger FK→`onto_ontology.id`，`ON DELETE CASCADE` | 世界来源本体 |
| `ontology_version` | Integer NOT NULL | 钉住的**已发布**版本号（建景时校验 `=current_version` 且 publish 登记 `enabled`；后续版本升级不影响已建场景） |
| `name` | String(200) NOT NULL | 场景名 |
| `clone_scope_json` | JSONB | `{object_codes[], relation_codes[], max_entities, max_relations}`（子图范围 + 上限） |
| `exec_mode` | String(16) default `auto` | `auto\|stepwise\|replay`（语义见 §5.4） |
| `tick_now` / `tick_max` | Integer | 当前场景默认分支推进位 / 推演窗口上限（原型叙事 0–12，实际由场景配置） |
| `status` | String(16) default `draft` | `draft\|cloning\|running\|completed\|failed\|archived` |
| `clone_stats_json` / `error_detail` | JSONB / Text | 克隆结果统计（实体/关系/masked_columns 计数）与失败摘要 |
| `creator_id` / `created_at` / `updated_at` | — | 审计 |

约束与索引：`ck_sandbox_scene_exec_mode`、`ck_sandbox_scene_status`；`idx (tenant_id, ontology_id, status)`。

### 3.2 `onto_sandbox_branch` 分支（平行世界线）

| 列 | 说明 |
|---|---|
| `id`, `scene_id`(FK CASCADE) | 归属场景 |
| `name`, `color` | 原型「基线分支/断供·未干预/断供·应急调拨」叙事 |
| `base_checkpoint_id` | 可空=基线分支；非空=从检查点派生 |
| `tick_now` | 分支推进位（真源；前端 Tick 只读游标） |
| `status` | `active\|sealed`（对比定稿后可封存） |

唯一约束 `uq (scene_id, name)`。

### 3.3 `onto_sandbox_checkpoint` 检查点（不可变世界快照）

| 列 | 说明 |
|---|---|
| `id`, `scene_id`, `branch_id`(FK CASCADE) | 归属 |
| `tick`, `seq` | 快照时点与场景内序号 |
| `label` | 「T5 快照」类展示名 |
| `stats_json` | 快照实体/关系计数与 KPI 摘要（对比表快速渲染用） |

**场景级合计上限 5 个**（跨全部分支共用，对齐原型「检查点 1/5」的场景级计数与拒绝 toast；服务端校验）；检查点创建 = 将该分支当前 entity/relation 行集复制为 `checkpoint_id` 归属的不可变行（见 3.4/3.5 的 `checkpoint_id` 列）。删除检查点级联回收其快照行；存在依赖该检查点派生的分支时拒绝删除并提示。

### 3.4 `onto_sandbox_entity` 世界实体行

| 列 | 说明 |
|---|---|
| `id`, `scene_id`, `branch_id`(FK CASCADE) | 当前态行 `checkpoint_id IS NULL`；检查点快照行非空 |
| `entity_code` | **沙箱代理键**（原型 `proxy_key` 语义，如 `SUP006`；分支内唯一，不暴露源库真实主键） |
| `object_code` | 本体对象类型 code（逻辑引用 `snapshot_json`，不建 FK 到模式层） |
| `props_json` | 属性载荷（克隆自映射列；效应公式改写对象） |
| `risk_score` | Float，可被引擎改写（原型节点右上角评分圆点） |
| `masked` | Boolean——该实体存在命中脱敏的列（克隆时置位；行动门禁求值输入） |
| `source_ref_json` | `{source_id, db, table, pk}` 来源回链——**仅展示**，任何代码路径不得据此回查或写回源库 |
| `origin` | `clone`（克隆行）\| `derived`（引擎派生行，如事件实体） |

索引：当前态行唯一约束用部分唯一索引 `(branch_id, entity_code) WHERE checkpoint_id IS NULL`；快照行唯一约束 `(checkpoint_id, entity_code)`；另建 `idx (scene_id, object_code)`。

### 3.5 `onto_sandbox_relation` 世界关系行

同 3.4 的归属与快照机制：`link_type_code`（本体关系 code）、`from_entity_code`/`to_entity_code`、`props_json`、`origin`（`clone|causal`——因果边实例化产生的关系行）。

### 3.6 `onto_sandbox_element` 统一配置元素（因果边/规则/目标/未来事件模板）

| 列 | 说明 |
|---|---|
| `id`, `scene_id`(FK CASCADE) | 场景级配置（不落本体模式层，V3） |
| `kind` | `causal_edge \| rule \| goal \| future_event` |
| `code` | 场景内唯一标识（如 `G-01`、`CE-003`） |
| `label` | 因果边语义：`PRODUCES \| MODIFIES \| CAUSES \| SUPPLIES \| FULFILLS`（其余 kind 为空） |
| `from_ref` / `to_ref` | 端点（实体 code / 对象 code / 事件 kind） |
| `condition_expr_json` | 触发条件 AST（受控文法，见 §4 引擎） |
| `effect_expr_json` | 效应公式 AST（属性算术/聚合/阈值；goal 为判据公式） |
| `activation_tick` | 可空——手工指定的期望激活位（引擎实际以状态求值为准；此列供「未来事件」前瞻排序参考） |
| `origin` | `rule \| llm \| human`（`llm` 只能 `status='suggested'`——D3 防线原样复用） |
| `status` | `suggested \| accepted \| rejected`；**仅 `accepted` 参与引擎求值** |
| `confidence` | LLM 自评分（仅排序展示） |

唯一约束 `uq (scene_id, kind, code)`；索引 `idx (scene_id, status)`、`idx (scene_id, origin, status)`。

### 3.7 `onto_sandbox_action` 行动审计日志

| 列 | 说明 |
|---|---|
| `id`, `scene_id`, `branch_id` | 归属（行动总是作用于具体分支） |
| `tick` | 施加时点 |
| `template_code` | 引用 `onto_action_template.code` |
| `target_entity_code` | 沙箱代理键 |
| `params_json` | 强度/参数（如「供料中断 100%，持续至窗口结束」） |
| `gate_result` / `gate_reason` | `allowed \| denied` / 原因码（`MASKED_TARGET`、`NO_ACTION_PERMISSION`、`MODE_READONLY`、`CONFIRM_EXPIRED`） |
| `confirm_token` | `stepwise` 模式待确认令牌（可空） |
| `operator_id`, `created_at` | 审计 |

**allowed 与 denied 都落痕**（F4 行动审计 tab 数据源）。

### 3.8 `onto_sandbox_observation` 引擎时序事实

| 列 | 说明 |
|---|---|
| `id`, `scene_id`, `branch_id`, `tick` | 定位 |
| `kind` | `observation \| kpi_point \| risk_point \| rule_fired \| goal_eval \| action_effect \| deadline_missed` |
| `severity` | `info \| warn \| err` |
| `title` / `detail_json` | 结构化观察载荷（KPI 点：`{health, controllability}`；风险点：`{entity_code, score}`；目标点：`{goal_code, status}`） |
| `source` | `engine`（确定性产出）\| `advisor`（AI 解释性附注，不参与求值只供展示） |

索引 `idx (branch_id, tick, kind)`。主时间线、传播过程四 tab、KPI 模态、风险 TOP3、分支对比序列**全部且仅**由本表渲染。

### 3.9 `onto_action_template` 平台内置行动模板库（平台级）

| 列 | 说明 |
|---|---|
| `code` | `supply_cut \| delay \| price_up \| reroute`（种子数据起步，演进期开放管理界面） |
| `name` / `description` / `domain_hint` | 展示与推荐（供应链/风险域） |
| `param_schema_json` | 参数表单 schema（F7 模态的「强度/参数」控件由它驱动渲染） |
| `effect_spec_json` | 效应映射声明：产 SimEvent（`origin='causal'` 派生实体）+ 挂接的默认因果边模板 + 目标属性改写式 |
| `status` | `enabled \| disabled` |

模板表**无 tenant 维度**（平台内置）；场景只能引用 `enabled` 模板，不能自定义模板（V3；P2 开放管理界面时再评估是否升为租户级）。

### 3.10 九类语义对象的联动闭环

```text
本体发布快照(snapshot_json) ──只读钉版──▶ 克隆链路 S1
      实体/关系（onto_sandbox_entity/relation，带 risk_score/props/masked/source_ref）
          ▲ 改写属性                              ▲ 派生
行动（onto_action 引用 action_template）──▶ 产出 SimEvent（derived 实体，PRODUCES 起点）
      SimEvent ──causal_edge(PRODUCES/MODIFIES/CAUSES)──▶ 下游实体属性改写 / 新事件
      规则（element.kind=rule）每 Tick 条件求值 ──命中──▶ observation.rule_fired
      目标（element.kind=goal）每 Tick 判据求值 ──▶ observation.goal_eval（达成/观察/受威胁）
      风险 = entity.risk_score 时序 ──▶ observation.risk_point（TOP3 排序查询）
      前瞻 = 已采纳 element 沿因果边正向推演（depth≤4）──▶「未来事件」tab
引擎每 Tick 采样 ──▶ observation.kpi_point ──▶ F6 KPI / KPI 模态 / 分支对比
检查点 = entity/relation 当前态行集复制；分支 = 检查点派生平行世界线
```

与主规格 D1（CDM 升格模式层）的关系：沙箱域**只读消费**发布快照的 `object/property/relation/mapping` 定义，绝不反向修改模式层；`object_code/link_type_code` 为逻辑引用不建 FK，发布版本升级不影响已建场景（钉版语义）。

---

## 4. 服务与 API

### 4.1 后端服务（`backend/app/services/sandbox/`，与 `services/ontology/` 平级）

| 服务 | 职责 | 边界要点 |
|---|---|---|
| `sandbox_scene_service` | 场景生命周期：校验本体 `status=published` 且存在 `enabled` publish 登记且 `version=current_version` → 生成克隆计划（含范围预检，见 §9-R1）→ 建基线分支 → 删除级联回收 | 只读 `onto_ontology*`；无任何生产写路径 |
| `sandbox_clone_service` | 世界克隆：按 `clone_scope_json` + 版本快照映射生成下推 SELECT（复用 `ReadonlyQueryService`+`SqlGuard`），脱敏列克隆时即按 `mask_rule` 包裹（无规则整列 `'***'` 并记 `masked_columns[]`），上限强制，落 entity/relation | 产出物只有沙箱行；克隆失败 → 场景 `failed`，可重试；克隆是一次性快照，推演期不回源 |
| `sandbox_engine_service` | `advance(branch, n)`：逐 Tick 执行「事件到期检查 → 因果边传播（受控 AST 效应，固定拓扑序）→ 规则求值 → 目标求值 → KPI/风险采样 → 观察落库」；`preview_future(branch, depth≤4)`；`save_checkpoint` / `restore`（回放）/ `derive_branch` / `compare` | 推进为幂等后台任务（沿用 `build_job` 模式：`idempotency_key` + `status/phase/progress`，进程内线程，与主规格 A3 假设一致）；**确定性**：同配置 + 同行动序列 → 逐 Tick 相同结果（固定拓扑序 + Decimal 定点求值，§9-R3） |
| `sandbox_action_service` | 行动执行：模板校验（S16 参数 schema）→ 门禁求值（§5）→ 落 `action` 日志 → 转引擎输入（产 SimEvent + 挂默认因果边实例）→ 推进 1 Tick；`stepwise` 两段式（待确认 token → 确认端点） | denied 也返回审计 id；行动只写沙箱 branch |
| `sandbox_advisor_service` | AI 顾问：注册**只读**工具 `query_sandbox_world` / `propagation_trace` / `read_observations`（复用 react/tool_manager 体系）+ 场景上下文摘要注入（当前 Tick/KPI/目标/风险 TOP3）；SSE 流式复用现有封装；LLM 辅助建模：按场景生成 `element` 候选落 `origin='llm', status='suggested'` | 顾问工具无写接口；LLM 候选未经采纳不参与引擎求值（D3 防线）；推荐问答由模板问题 + 场景数据拼装 |

受控 AST 文法（效应与条件共用，引擎内解释执行，**不 eval 任意代码**）：字面量、属性引用（`entity.props.<key>`）、四则运算、比较、`AND/OR/NOT`、`min/max/sum/avg/count` 聚合、`clip(x, lo, hi)`、`if(cond, a, b)`。表达力不足时给配置期 warn（§9-R2），不扩文法。

### 4.2 API（前缀 `/ontologies/sandbox`，挂载沿用 `routers/ontology` include 模式；全端点租户隔离）

| # | 端点 | 说明 |
|---|---|---|
| S1 | `POST /scenes` | 建景：`{ontology_id, name, clone_scope, tick_max, exec_mode}` → 异步克隆，返回场景 id 供轮询 |
| S2 | `GET /scenes?ontology_id&status` | 场景列表 |
| S3 | `GET /scenes/{id}` | 详情（含克隆统计、分支概览、检查点计数） |
| S4 | `DELETE /scenes/{id}` | 删除回收（级联全部沙箱行；不可撤销确认由前端模态承载） |
| S5 | `PATCH /scenes/{id}` | 改名 / 切执行模式（`replay` 切入后拒绝后续写） |
| S6 | `GET /scenes/{id}/world?branch&tick&view=` | 画布统一数据源（节点+边+激活态+来源回链+脱敏标记；`view=world|causal`） |
| S7 | `GET /scenes/{id}/entities/{code}?branch` | 节点详情（属性、风险、来源、本体映射、行动可用性标志） |
| S8 | `POST /scenes/{id}/branches/{bid}/advance` | 推进 `{n}`（1/10/自动逐 Tick 均由前端以 n=1 循环或后台任务驱动） |
| S9 | `POST /scenes/{id}/branches/{bid}/checkpoints` | 保存检查点 `{label}`；>5 拒绝 `CHECKPOINT_LIMIT` |
| S10 | `POST /scenes/{id}/branches` | 从检查点派生分支 `{name, checkpoint_id}` |
| S11 | `GET /scenes/{id}/compare?branches=a,b` | 分支对比：**逐 KPI 序列差异表**（observations 聚合） |
| S12 | `POST /scenes/{id}/branches/{bid}/replay` | 跳转回放 `{to_tick}`（确定性保证） |
| S13 | `GET/POST/PUT/DELETE /scenes/{id}/elements` | 因果边/规则/目标/未来事件配置 CRUD（仅 `accepted` 可被引擎加载） |
| S14 | `POST /scenes/{id}/elements/llm-draft` | LLM 辅助生成候选（异步，落 suggested） |
| S15 | `POST /elements/{eid}/review` | 采纳 / 驳回（D3 防线执行点） |
| S16 | `GET /action-templates` | 内置模板库（含 param_schema 驱动 F7 表单） |
| S17 | `POST /scenes/{id}/branches/{bid}/actions` | 施加行动；同步返回 `{gate_result, action_id, tick_after?}`；`stepwise` 返回待确认态 |
| S18 | `GET /scenes/{id}/actions?branch&result` | 行动审计流（F4 审计 tab；`replay` 模式也可读） |
| S19 | `GET /scenes/{id}/observations?branch&tick_from&tick_to&kind` | 传播过程 / 未来事件（`kind=future` 走 `preview_future`）/ 规则 / 目标四 tab 共用 |
| S20 | `POST /scenes/{id}/ask` | AI 顾问对话（SSE；上下文自动注入当前 scene/branch/tick） |
| S21 | `GET /scenes/{id}/kpis?branch&kind` | KPI/风险时序（F6 条与 KPI 模态） |

错误码沿用 `app/core/api_error` 模式新增：`SCENE_NOT_FOUND`、`ONTOLOGY_NOT_PUBLISHED`（钉版校验）、`CLONE_LIMIT_EXCEEDED`、`CHECKPOINT_LIMIT`、`GATE_DENIED_MASKED`、`GATE_DENIED_MODE`、`ELEMENT_NOT_ADOPTED`、`ACTION_TEMPLATE_DISABLED`、`CONFIRM_EXPIRED`。

### 4.3 前端（`frontend/src/views/sandbox/`）

- 组件按原型八域拆分：`ContextBar` / `TickBar` / `ScenePanel` / `CausalCanvas`（SVG，参照原型渲染逻辑改为消费 S6）/ `TracePanel`（四 tab）/ `AdvisorPanel`（三 tab）/ `ActionModal` / `CompareView`。
- 状态：Pinia store 仅持 `{sceneId, branchId, tick, execMode}` **游标**；世界状态真源恒在后端沙箱表——F6 跳转与 F5 刷新都是服务端重算。样式沿用本体工作台暗色 token 基线（`frontend/src/styles/tokens.css` dark skin）。
- 引擎任务进度：S8/S1 返回 task id，前端轮询（MVP），SSE 增强列 P1（受主规格 U8「三处 SSE 封装选型」收口约束）。

---

## 5. 隔离、权限、行动门禁与执行模式

### 5.1 隔离三层证据（「隔离沙箱世界 · 未写入生产」的可验证承诺）

| 层 | 机制 | 验收钩子 |
|---|---|---|
| 物理层 | `onto_sandbox_*` 独立表；sandbox 服务与引擎代码路径不存在对 `onto_ontology*`/`meta_*`/源库的写连接 | 代码评审 + 静态检查断言（A7 前置）；端到端前后快照 diff 为空（验收 A2） |
| 数据层 | 克隆唯一入口为只读下推 SQL；脱敏列**克隆时**落盘包裹，沙箱内不存在明文敏感值；`source_ref_json` 仅展示、禁止回查/回写 | 验收 A3 |
| 行为层 | 行动/推进/检查点全部以 `branch_id` 为作用域；`action` 表 allowed/denied 全留痕 | 验收 A3/A5/A6 |

### 5.2 权限（不重开主规格 Q1）

- 功能级权限点：`sandbox:scene:create` / `sandbox:run` / `sandbox:act` / `sandbox:delete`，挂现有 `sys_*` 角色体系与路由鉴权。
- 数据级：沿用本体已有 `security_level`/`pii_level`/`mask_rule` 标记做**克隆期脱敏**（V4）；行级视野引擎本期不做——「谁能看哪些行」仍非目标，口径与主规格 §10 Q1 裁决 A 一致。

### 5.3 行动门禁求值顺序（服务端，F7/S17）

```text
1. exec_mode == replay            → denied(MODE_READONLY)
2. 角色无 sandbox:act             → denied(NO_ACTION_PERMISSION)
3. 目标实体 masked                → denied(MASKED_TARGET)
4. 模板 disabled / 参数不合 schema → 400（不进门禁留痕，视为非法请求）
5. exec_mode == stepwise          → 落待确认(pending, confirm_token) → 确认端点执行 / 超时 CONFIRM_EXPIRED
6. exec_mode == auto              → allowed → 写世界 + 推进 1 Tick
```

denied/pending 均先落 `action` 日志再返回，保证审计闭环（两段式形态借鉴 `write_request_service` 的请求-确认先例）。

### 5.4 三执行模式语义

| 模式（原型下拉三档） | 语义 | 端点行为 |
|---|---|---|
| `auto` 自动执行 | 推进与行动即时生效 | S8/S17 直接执行 |
| `stepwise` 逐步确认 | 每个行动生效前需人二次确认 | S17 两段式；推进仍即时（Tick 推进无破坏性） |
| `replay` 只读回放 | 仅回放检查点/分支序列，禁止一切世界写 | 世界写类端点全部拒绝：S17 走门禁流程返回 `denied(MODE_READONLY)` 并留审计（保留原型拒绝 toast 形态）；其余写端点（S1/S4/S8/S9/S10/S13/S14/S15）403；S12 回放查看、S20 顾问问数及全部只读端点允许；S5 仅允许切出/切入模式 |

---

## 6. 关键用户旅程（对齐原型叙事，验收走查脚本）

1. **建景**：本体建模工作台已发布「汽车零部件供应链 v3」→ 沙盘 ＋场景（S1：选应用版本 + 勾子图范围 Supplier→Facility→Order→Warehouse）→ 克隆进度遮罩 → 基线分支 @Tick0 建成本体出图（S6 世界概览）。
2. **推演**：S16 拉模板 → 施加行动「断供 SUP006」（S17 门禁 allowed）→ SimEvent 供料中断 @T1 → S8 推进/自动 → 因果链逐级点亮（T2 缺料 MODIFIES FAC007 产能↓、T3 交付延迟、T4 CAUSES ORD012 违约风险↑）→ S19 观察流刷新、S21 健康度 A→C、风险 TOP3 重排、G-01 转受威胁。
3. **对比**：T5 S9 存检查点 → S10 派生「未干预」「应急调拨」两分支各自推满 → S11 逐 KPI 差异表（违约风险终值由引擎算出）→ 决策选优。
4. **问策**：S20 问「风险如何从 SUP006 传到 ORD012」→ 顾问调 `propagation_trace` 只读工具 → 因果链解释 + 建议行动窗口；S18 行动审计核对每步留痕与隔离声明。
5. **异常路径**：对 SUP018（masked）施加 → `GATE_DENIED_MASKED` toast + 审计；推进错过 deadline → `deadline_missed` 观察（错误态）；克隆失败 → 场景 `failed` 可重试；S4 删除 → 全量回收确认模态；检查点第 6 个 → `CHECKPOINT_LIMIT` 拒绝。

---

## 7. 能力差距分析（现有 → 增量）

| 能力 | 现状 | 差距（本文档解法） |
|---|---|---|
| 本体发布快照 / 应用登记 | ✅ `onto_ontology_version.snapshot_json` + `onto_ontology_publish`（P0 已落地） | 无——S1 直接钉版消费 |
| 实例物化 | ❌ D2 不落库；仅 `POST /ontologies/{id}/sample`（LIMIT≤100 采样） | **最大增量**：`sandbox_clone_service` 受控上限批量下推 + 脱敏落盘（§4.1） |
| 因果边/规则/目标语义 | ❌ 模式层无此概念（Q3 裁决行动不做） | 新建 `onto_sandbox_element` **场景级**配置，不触碰模式层（V3） |
| 推演引擎 | ❌ 无 | 新建确定性 Tick 引擎 + 受控 AST 解释器（§4.1） |
| 行动模板库 | ❌ 无（4 类行动仅原型硬编码） | 新建 `onto_action_template` 种子 |
| AI 工具底座 | ✅ react/tool_manager/SSE/审阅台模式齐备 | 增量：3 只读沙箱工具 + S14/S15 LLM 候选链路（复用 D3） |
| 图谱渲染 | ✅ schema 图 + `views/kms/kg` 实例图组件可借鉴 | 增量：因果传播视图（Tick 点亮态）新组件 |
| 权限 | ✅ `sys_*` + TenantMixin | 增量：4 个功能权限点；**不做**行级视野（V4） |
| 任务模式 | ✅ `build_job`（幂等/phase/progress/后台线程） | 复用为克隆与推进任务外壳 |

---

## 8. MVP（P0）范围与演进路线

**MVP 包含**：F1–F7 主路径 + 单本体钉版克隆（上限默认 **500 实体 / 2000 关系**，场景可配）+ 4 内置行动模板 + 手工配置因果边/规则/目标（S13）+ 检查点 ≤5 / 分支派生 / 逐 KPI 对比 + 三执行模式 + 门禁 + 顾问只读对话（S20 最小工具面）+ 行动审计 + 四态 + 8 条验收断言全绿。画布视图实做因果传播 + 世界概览（本体结构/实例探索复用现有端点入口）。

**MVP 不包含（明确排除，防止范围蠕变）**：
- LLM 辅助建模的可用率实测（S14/S15 交付链路但演示不依赖其质量——继承主规格 U12 教训）；
- 概率性推演 / 参数扫描；多本体合并世界；孪生应用（板块七）；
- 行动模板自定义与管理界面；行级视野引擎；
- 引擎任务队列化（维持进程内线程，主规格 A3 假设，超限再评估）。

**演进**：
- **P1**：LLM 辅助因果建模实测与采纳率优化；传播深度/环路策略；并行分支批量推进性能；SSE 进度流（U8 收口后）；克隆范围预检报告可视化。
- **P2**：推演结果发布（回链孪生应用/报告导出）；行动模板管理界面（评估升租户级）；检查点 diff 可视化；视野引擎接入（仅当主规格 Q1 重开）。
- **P3**：多本体克隆世界；概率性推演（蒙特卡洛参数扫描）；实时事件源驱动 Tick（数据新鲜度问题的终解，与 D2 生产域红线仍不冲突——事件源仍只进沙箱域）。

---

## 9. 风险与对策

| ID | 风险 | 对策 |
|---|---|---|
| R1 | 源库数据量/质量决定克隆可用性；上限截断可能切断因果链（下游实体未克隆） | S1 建景前范围预检：按对象行数出预算报告，超限要求收窄子图或显式确认截断；引擎对悬空因果边给 warn 观察 |
| R2 | 受控 AST 表达力不足，场景"推不动" | 配置期静态校验（孤立边/无锚点规则/未知属性引用 → warn）；文法保持封闭不扩（扩文法走 P1 评审） |
| R3 | 确定性被破坏：求值顺序、浮点误差致回放漂移 | 引擎内固定拓扑序 + 同层按 element.code 排序；Decimal 定点；验收 A1 逐值断言入 CI |
| R4 | 进程内后台线程并发不足（多场景同时推进） | 与主规格 A3 同假设（单租户低并发）；出现实证瓶颈再评估队列，不预建 |
| R5 | 与主规格「推演沙盘 = P3 观察项」表面矛盾 | 本文档即 D2 边界重划裁决载体；§11 回写主规格五处，消除口径冲突 |

---

## 10. 验收标准（硬断言）

| # | 断言 |
|---|---|
| A1 | 同场景同行动序列重放两次，逐 Tick 实体属性 / observations / KPI **完全一致**（确定性；CI 化） |
| A2 | 全程审计可证无生产写：推演会话前后对 `onto_ontology*`、`meta_*` 行集与源库做快照 diff **为空** |
| A3 | 脱敏实体在沙箱查询（S6/S7）、画布渲染、行动模态三处均无明文；对其施加行动返回 `GATE_DENIED_MASKED` 且落审计 |
| A4 | `replay` 模式下世界写类端点全部被拒（S17 返回 denied 且落审计，其余写端点 403）；`stepwise` 模式行动未经确认不改变世界状态 |
| A5 | 检查点上限 5 生效；从检查点派生分支后原分支状态不变；删除被派生分支依赖的检查点被拒绝 |
| A6 | 分支对比表数值与 observations 表一致（来自引擎），前端无任何 KPI 计算 |
| A7 | 静态检查/评审约束：sandbox 服务无 `onto_ontology*`、`meta_*` 写路径，无源库连接（除 clone 唯一入口） |
| A8 | LLM 生成的 element 候选未经 S15 采纳不参与引擎求值；顾问回答中的实体/数值可溯源到只读工具返回（提示词约束 + 抽样核验） |

---

## 11. 对主规格的回写项（本设计获批后执行）

| 位置 | 回写内容 |
|---|---|
| §0 决策表 D2 行 | 追加边界注记：生产域红线不变；沙箱域例外物化见本文档 §0-V1 |
| §1.2 非目标表 | 「推演沙盘、孪生应用」行拆分：**两者均已单独立项**——推演沙盘见本文档（沙箱域物化裁决），孪生应用见 `2026-11-01-digital-twin-app-design.md`（T1 查询期直连，不依赖物化，与本文 V1 裁决不冲突） |
| §1.3 对标矩阵「六、推演沙盘」行 | 「不做」→「已立项：沙箱域设计见 `2026-11-01-simulation-sandbox-design.md`」 |
| §8.2 假设 A2 | 补注：重开条件已触发并完成裁决（沙箱域例外，生产域仍不落库） |
| §10 Q3 落地约束第 2 条 | 边界澄清：红线指**生产域写回实例的行动**；沙箱域内置行动模板（场景级、不落模式层、永不回写）不构成违反 |

---

## 附：术语对照（原型字面 → 产品字段）

`proxy_key`→`entity_code` · `WorldChip 世界来源`→`scene.ontology_id+ontology_version` · `克隆范围 5实体/6关系`→`scene.clone_stats_json` · `可达运行 7/7`→引擎任务成功计数 · `行动窗口 #0–#12`→`scene.tick_max` · `检查点 1/5`→`checkpoint` 计数 · `失效规则`→`element.kind=rule` 触发观察 · `目标 G-01/G-02`→`element.kind=goal` · `qwen-plus/deepseek-r1`→现有模型配置。
