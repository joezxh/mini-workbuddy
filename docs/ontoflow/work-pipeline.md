我先按 superpowers 的规则检查适用技能，再读取上下文。


已完成上下文收集：读取了 [ontoflow.md](file:///d:/projects/MinWorkBuddy/docs/prototypes/ontoflow.md)（154 行，11 个板块）、两份已完成原型的样式骨架（二者共享完全一致的 `:root` 设计令牌、`preview-header` 渐变页头、tab/badge/stat-card 组件语法），并核对了 Qoder 已注册技能清单。下面直接给出推荐报告。

> 过程技能说明：已调用 `ask-matt` 做路由核对——其主线（grill → spec → tickets → implement）面向生产代码，本任务是"一次性可演示静态 HTML"，属于 Matt 流中 `/prototype` 的独立场景，因此最终推荐以 Qoder 注册表中的 ECC 系技能为主。任务为纯咨询报告、目标明确无多方案分歧，无需切换 Plan 模式。

---

## 〇、先决结论：风格基线已经存在

两份已完成原型（`ontology-capability-preview.html` / `ontology-asset-catalog-preview.html`）已固化了一套完整设计语言：

- **Design tokens**：`--primary:#3371fc`、`--bg/--card/--subtle` 三级背景、`--success/--error/--warn/--purple` 语义色、`--r/--r-sm` 圆角、`--t` 过渡曲线、`--mono` 等宽字体——两文件逐字节一致
- **版式骨架**：深色渐变 `preview-header`（kicker + 决策标签 `dec` 胶囊）+ `.shell` 网格主框架（侧栏列表/树 + 主区 tabs + 右抽屉）
- **组件语法**：`.btn/.badge/.stat/.card/.tab` 及空态、加载态（pulse 动画）、权限态的写法

所以 11 个新原型的**设计方向技能只需用于第一页"定调"，后续 10 页的核心工作是"令牌级复用 + 板块特有 UI 构成"**。这直接决定了下面的矩阵。

---

## 一、板块 × 推荐 Skill 矩阵

| # | 板块 | 设计方向 | 构建 | 一致性 | 可视化 | 工程模式 |
|---|------|---------|------|--------|--------|----------|
| 1 | 探索（AI 工作台） | `make-interfaces-feel-better` | `prototype` | `design-system` | N/A | N/A |
| 2 | 智能体 | `make-interfaces-feel-better` | `prototype` | `design-system` | N/A | N/A |
| 3 | 数据摄取 | N/A | `prototype` | `design-system` | `archify`（连接器拓扑） | N/A |
| 4 | 数据资产 | N/A | `prototype`（**已完成**，补齐跨页跳转即可） | `design-debt-review` | N/A | N/A |
| 5 | 本体建模（五步链路） | `frontend-design-direction` | `prototype` | `design-system` | `archify` + `graphviz` | N/A |
| 6 | 推演沙盘 | `frontend-design-direction` | `prototype` | `design-system` | `graphviz`（因果传播） | N/A |
| 7 | 孪生应用 | `make-interfaces-feel-better` | `prototype` | `design-qa` | `archify`（数据流） | N/A |
| 8 | 知识库 | N/A | `prototype` | `design-system` | N/A | N/A |
| 9 | 图可视化 | N/A | `prototype` | `design-qa` | `graphviz` | N/A |
| 10 | 系统设置 | N/A | `prototype` | `design-system` | N/A | N/A |
| 11 | 平台架构 | `frontend-design-direction` | `prototype` | N/A | `archify`（主战场）+ `c4model` | N/A |

**列说明与约束处理：**

- **工程模式列全部 N/A**：原型是 vanilla HTML/JS 单文件，`vue-patterns`/`react-patterns`/`vite-patterns` 均针对框架工程，引入只会让原型变成需要构建的工程项目，违背"浏览器直接打开"的约束。真正可借鉴的是既有两页的**朴素组织法**（`const MOCK = {...}` 数据层 + 渲染函数 + 事件委托），这无需 Skill。
- **`ui-demo`/`browser-qa` 按你的约束排除在设计阶段之外**（属验证阶段）；`canvas` 是 slash-command 专用产物（`.canvas.tsx`），不适合交付给浏览器独立打开的文件；`frontend-slides` 是演示文稿而非产品界面原型，均不进入矩阵。
- 你提到的 `taste-skill`/`soft-skill`/`html-presentation` **不在 Qoder 注册表中**——最接近的替代是 `frontend-design-direction`（ECC 的设计方向技能）和 `taste`（但它限定音乐 MV/短视频审美方向，不适用）。

---

## 二、逐板块推荐理由

### 1. 探索（统一 AI 工作台）
UI 构成以**对话流**为主：多轮会话气泡、模型切换器、知识库/数据表/技能挂载面板。这是 11 页中"手感"要求最高的一页——打字机效果、发送中态、上下文引用条的 hover/聚焦细节，正是 `make-interfaces-feel-better` 的射程（间距、过渡、hit-area、focus 态）。与已有原型衔接：页头 `dec` 标签可直接标注"挂载来源：本体技能 #SK-07"，与板块五、八形成呼应。`prototype` 保证单文件 mock、不写请求层。

### 2. 智能体（可发布业务助手）
核心是**配置表单 + 挂载选择 + 发布生成链接**的状态流转（草稿→配置→测试→发布→嵌入）。`prototype` 的"回答一个设计问题"定位恰好匹配本页要验证的问题："配置项分区和发布门禁怎样组织才不吓人"。`design-system` 确保表单控件（input/select/switch/多选卡片）沿用两页已有的 focus-ring、disabled、错误提示写法，不重新发明。

### 3. 数据摄取（多源接入）
本页两大难点：连接器矩阵（关系库/时序/文件/接口/MQ/实时通道六类）的**图形化配置向导**，以及采集结果流入资产目录的**上下游示意**。前者靠 `prototype` + 复用 token；后者可在页面顶部放一张 `archify` 生成的轻量数据流图（源→采集→统一资产目录），静态内嵌 SVG 即可，与"无外部依赖"兼容。一致性仍由 `design-system` 兜底。

### 4. 数据资产（统一目录）
`ontology-asset-catalog-preview.html` **已完成本页主体**（树 + 检索 + 卡片列表 + 选择条），无需重新构建；剩余工作是补齐需求 2 中要求的"选表结果流入本体建模作用域"的**跨页跳转**（选择条"送入建模"按钮 → `ontology-modeling-workbench-preview.html`，该文件也已存在）。此阶段推荐 `design-debt-review`：审查两页里是否出现了硬编码色值、魔法 px 等偏离 token 的写法，防止后续 10 页把债务复制扩散。

### 5. 本体建模（五步链路，平台核心）
全平台信息密度最高的一页：五步 Stepper（数据源表→数据处理→子图建模→本体库→本体应用）、画布式子图编辑、AI 助手侧栏、发布门禁。注意 `ontology-modeling-workbench-preview.html` 已存在，建议先确认它是否已覆盖，缺什么补什么。设计上用 `frontend-design-direction` 先定"这一页的设计方向"（画布区与配置区的视觉权重、五步的进度隐喻），避免核心页落入模板感。可视化上 `graphviz` 适合把"对象-关系-规则"子图缩略图以 DOT 渲染为内嵌 SVG；`archify` 适合画五步链路全景。`design-system` 保证 stepper/门禁徽标与板块一的会话态同一语义色。

### 6. 推演沙盘（世界模型推演）
难点是**因果传导的可视化叙事**：克隆世界状态 → 施加行动 → 影响层层扩散 → 检查点分支对比。`frontend-design-direction` 帮这页找到区别于普通 dashboard 的视觉语言（如"隔离世界"的边框/底色隐喻、传播动画的节奏）。图形部分（传播 DAG、分支树）用 `graphviz` 出 DOT 再嵌 SVG；`prototype` 约束用 mock 时间轴驱动假推演，明确"这不是真引擎"。衔接点：入口卡片直接引用板块五"已发布的本体应用"列表。

### 7. 孪生应用（可交互大屏）
本页是**组件拖拽搭建 + 实时指标**，视觉完成度直接决定演示说服力，故用 `make-interfaces-feel-better`（图表 hover、下钻过渡、告警脉冲——既有原型的 `.badge .pulse` 已是现成词汇）。一致性检查升级为 `design-qa`：因为大屏组件最多、最容易偏离 DESIGN 契约，需要对照基准图逐组件核对。`archify` 可用于页头一张"本体查询 → 组件绑定"的数据流小图。

### 8. 知识库（文档知识底座）
UI 是标准 CRUD 组合：批量上传（拖拽区/解析进度）、切分策略配置、多层索引状态、检索测试面板。仓库里已有 `kb-manager-preview.html` 可作素材来源。无需专门设计方向技能——`prototype` + `design-system` 就够，重点是把 token 套用上去（旧 KB 原型的配色若不同，此处统一）。衔接点：挂载操作按钮文案与板块一、二的"挂载知识库"互为镜像。

### 9. 图可视化（图谱探索）
本质是一张力导向图 + 筛选面板 + 节点详情抽屉。`prototype` 用纯 SVG + 手写简单布局脚本（无外部依赖约束下不引 D3，预计算坐标写死在 mock 里即可）。`graphviz` 负责生成演示图的初始坐标/拓扑（DOT → 坐标 → 内嵌 SVG）。一致性用 `design-qa` 核对：节点/边的语义色必须与板块五子图建模的配色定义同源，否则"建模→验收"的叙事断裂。

### 10. 系统设置（模型/MCP/权限中枢）
多子页（100+ 模型厂商、MCP 与插件、角色、令牌、定时任务、日志）的**设置页阵列**，全是表格 + 表单 + 开关。这是最不需要创意、最需要纪律的一页：`prototype` 快速铺开，`design-system` 确保六个子 tab 的表格密度、分页、操作列与既有两页完全一致。"一次配置全局复用"的叙事可在每条模型行尾放"已被 3 个智能体引用"的关联徽标，回扣板块二。

### 11. 平台架构（OntioGraph 底座）
纯可视化页：分层架构（OntoGraph 底座 → OntoFlow 后端 → OntoOS/OntoX 前端）、能力标签云、极简部署拓扑。这是 `archify` 的主战场——直接产出"polished, validated architecture diagram as explorable standalone HTML with inline SVG, dark/light themes"，其内联 SVG + 无依赖的输出形态与本项目约束天然吻合。若团队需要**可维护的图源**（后续改架构不重画），补 `c4model` 出 Structurizr DSL 作为 source of truth，archify 图从它派生。`frontend-design-direction` 用于让架构页的两张深色渐变头图（img16/17 的意象）与产品页区分而不突兀。

---

## 三、推荐工作流（5 步）

```
Step 0  读 ontoflow.md + 两份原型           （已完成，本文即是产物）
   ↓
Step 1  定调（仅做一次）
   Skill: frontend-design-direction + design-system
   产物: 一份《原型设计契约》—— :root 令牌表、preview-header 规范、
         组件清单(btn/badge/stat/card/tab/tree/drawer/modal)、
         空态/加载/错误/权限四态模板、跨页跳转 URL 约定、mock 数据命名规范
   （建议落盘为 docs/prototypes/DESIGN-CONTRACT.md，后续每页冷启动只喂这一份）
   ↓
Step 2  逐板块产出（×10，按依赖顺序：三→四(补链)→五→八→十→一→二→九→六→七→十一）
   Skill: prototype（每页冷启动输入 = DESIGN-CONTRACT + 该板块 md 原文）
   特殊页叠加: 五/六/九 → graphviz 出拓扑;  十一/三/七 → archify 出架构图;
              一/七 → make-interfaces-feel-better 补交互细节
   ↓
Step 3  交叉一致性校验（全部页面完成后）
   Skill: design-qa（对照 DESIGN-CONTRACT 逐页核对组件/状态语义）
        + design-debt-review（扫硬编码色值/魔法值/重复组件）
        + component-library-alignment（可选：确认 11 页未各自发明同类组件）
   ↓
Step 4  汇总演示入口
   Skill: prototype 产出一份 index.html（11+2 卡片目录页，沿用同一 token，
          标注上下游数据流向箭头，点击即开对应页）
   ↓
Step 5（验收阶段，非设计阶段）
   此时才允许 browser-qa / ui-demo 做视觉走查 —— 按你的约束从设计流中剔除
```

**顺序要点：**
- Step 1 只跑一次是核心杠杆——11 页的风格一致性问题 90% 在定调阶段就已解决，后续每页 `design-system` 只是执行者而非决策者；
- Step 2 按**数据依赖序**而非文档序号构建（先做"数据摄取/资产/建模"主线，再做消费端"探索/智能体/孪生"），跨页引用（如"送入建模"）在依赖方已存在时才能一次接对；
- Step 3 放在全部完成之后集中跑，比每页跑一次便宜得多，且跨页漂移只有凑齐 11 页才看得见。