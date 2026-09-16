# Matt Pocock Skills 使用手册与最佳实践指南

> 生成日期：2026-09-15 | 安装路径：`C:\Users\joezxh\.agents\skills\mp-*` | 共计 37 个 Skills

---

## 目录索引

- [一、Skills 分类总览](#一skills-分类总览)
- [二、核心流程：从想法到交付](#二核心流程从想法到交付)
- [三、各 Skill 完整说明](#三各-skill-完整说明)
  - [3.1 主流程 Skills（Idea → Ship）](#31-主流程-skillsidea--ship)
  - [3.2 入口 Skills（On-Ramps）](#32-入口-skillson-ramps)
  - [3.3 代码库健康 Skills](#33-代码库健康-skills)
  - [3.4 词汇层 Skills](#34-词汇层-skills)
  - [3.5 独立工具 Skills](#35-独立工具-skills)
  - [3.6 写作 Skills](#36-写作-skills)
  - [3.7 项目配置 Skills](#37-项目配置-skills)
- [四、实战用例集](#四实战用例集)
- [五、工程开发综合范例](#五工程开发综合范例)
- [六、最佳实践总结](#六最佳实践总结)

---

## 一、Skills 分类总览

| 分类 | Skills 数量 | 核心用途 | 包含 Skills |
|------|------------|---------|-------------|
| 主流程 | 11 | 从想法到代码交付的完整链路 | grill-with-docs, grill-me, grilling, handoff, claude-handoff, prototype, to-spec, to-tickets, implement, implement-spec, tdd |
| 入口 | 3 | 不同起点进入主流程 | triage, diagnosing-bugs, wayfinder |
| 代码健康 | 2 | 架构诊断与审查 | improve-codebase-architecture, code-review |
| 词汇层 | 2 | 统一设计语言 | codebase-design, domain-modeling |
| 独立工具 | 9 | 特定场景的独立能力 | research, resolving-merge-conflicts, retro, scaffold-exercises, teach, to-questionnaire, wait-what, wizard, migrate-to-shoehorn |
| 写作 | 4 | 文档与内容创作 | writing-beats, writing-for-agents, writing-fragments, writing-shape |
| 项目配置 | 3 | 项目初始化与工具链 | setup-matt-pocock-skills, setup-pre-commit, setup-ts-deep-modules |
| 路由 | 1 | 技能选择导航 | ask-matt |
| 工作流设计 | 2 | 工作流规范定义 | loop-me, git-guardrails-claude-code |

---

## 二、核心流程：从想法到交付

```
┌─────────────────────────────────────────────────────────────────┐
│                    主流程：Idea → Ship                           │
│                                                                 │
│  /grill-with-docs ──→ /to-spec ──→ /to-tickets ──→ /implement  │
│        │                   │             │              │       │
│        │                   └─────────────┤         /tdd (内部)  │
│        │                                 │              │       │
│   /prototype ◄───────────────────────────┘      /code-review   │
│                                                                 │
│  入口：                                                          │
│  /triage ──────────────────────────────→ /implement             │
│  /diagnosing-bugs ─────────────────────→ 回归修复               │
│  /wayfinder ──→ /to-spec ──────────────→ /to-tickets           │
└─────────────────────────────────────────────────────────────────┘
```

**关键原则**：
- 步骤 1-3 保持在**同一个上下文窗口**中，不要 compact 或 clear
- 每个 `/implement` 从新上下文启动，基于工单独立工作
- 上下文窗口约 150k tokens 为"smart zone"，接近时在阶段边界 compact

---

## 三、各 Skill 完整说明

### 3.1 主流程 Skills（Idea → Ship）

#### `/mp-ask-matt` — 技能路由器

| 项目 | 内容 |
|------|------|
| **核心功能** | 根据你的场景描述，推荐最合适的 Skill 或工作流路径 |
| **适用场景** | 不确定该用哪个 Skill 时；想了解整体工作流路径时 |
| **触发命令** | `/mp-ask-matt` |
| **输入** | 自然语言描述当前场景 |
| **输出** | 推荐的 Skill 路径及理由 |

#### `/mp-grilling` — 深度访谈原语

| 项目 | 内容 |
|------|------|
| **核心功能** | 通过多轮编号提问，系统性地挖掘设计决策树中所有未解决的问题 |
| **适用场景** | 需要压力测试一个想法/设计/决策时 |
| **触发命令** | `/mp-grilling` |
| **关键机制** | 设计树（Design Tree）+ 前沿（Frontier）逐轮推进 |
| **输入** | 一个待讨论的想法或计划 |
| **输出** | 格式化的编号问题集，每个附带推荐答案 |

```
❓ Q1 - 数据持久化方案：是否需要事件溯源？
➡️ 推荐：否，当前规模用 PostgreSQL 即可

❓ Q2 - 认证方式：JWT 还是 Session？
➡️ 推荐：JWT，因为需要跨服务验证
```

#### `/mp-grill-with-docs` — 带文档的访谈

| 项目 | 内容 |
|------|------|
| **核心功能** | 在代码仓库中进行有状态访谈，自动生成 CONTEXT.md 术语表和 ADR 文档 |
| **适用场景** | 在代码仓库中工作，需要留下文档痕迹时（首选） |
| **触发命令** | `/mp-grill-with-docs` |
| **内部调用** | grilling + domain-modeling |

#### `/mp-grill-me` — 无状态访谈

| 项目 | 内容 |
|------|------|
| **核心功能** | 无状态的深度访谈，不保存任何本地文件 |
| **适用场景** | 不在代码仓库中工作时（如纯设计讨论） |
| **触发命令** | `/mp-grill-me` |

#### `/mp-handoff` — 会话交接（文件）

| 项目 | 内容 |
|------|------|
| **核心功能** | 将当前对话压缩为交接文档，保存到临时目录供下一个 Agent 使用 |
| **适用场景** | 切换到新目录/新 Agent/新同事继续工作时 |
| **触发命令** | `/mp-handoff "下一步要做什么"` |

#### `/mp-claude-handoff` — 会话交接（后台 Agent）

| 项目 | 内容 |
|------|------|
| **核心功能** | 将当前对话交接给一个后台 Agent，通过 `claude --bg` 启动 |
| **适用场景** | 需要立即启动一个新的后台会话继续工作 |
| **触发命令** | `/mp-claude-handoff "焦点描述"` |

#### `/mp-prototype` — 一次性原型

| 项目 | 内容 |
|------|------|
| **核心功能** | 构建一次性原型来回答一个设计问题，支持逻辑原型和 UI 原型两条路径 |
| **适用场景** | 需要验证状态模型是否合理，或探索 UI 外观时 |
| **触发命令** | `/mp-prototype` |
| **两条路径** | Logic（单 HTML 文件）/ UI（多变体路由） |

#### `/mp-to-spec` — 对话转规格说明

| 项目 | 内容 |
|------|------|
| **核心功能** | 将当前对话综合为结构化的 Spec 文档，发布到 Issue Tracker |
| **适用场景** | 讨论已充分，需要固化为可执行规格时 |
| **触发命令** | `/mp-to-spec` |
| **输出格式** | Problem Statement → Solution → User Stories → Implementation Decisions → Testing Decisions → Out of Scope |

#### `/mp-to-tickets` — 规格转工单

| 项目 | 内容 |
|------|------|
| **核心功能** | 将 Spec 分解为垂直切片的 Tracer-Bullet 工单，声明阻塞关系 |
| **适用场景** | Spec 已就绪，需要拆分为可独立实现的工单时 |
| **触发命令** | `/mp-to-tickets` |
| **关键规则** | 每个工单是完整的垂直切片（schema+API+UI+tests），而非水平分层 |

#### `/mp-implement` — 实现工作

| 项目 | 内容 |
|------|------|
| **核心功能** | 基于 Spec 或工单实现代码，内部驱动 TDD，完成后执行 Code Review |
| **适用场景** | 工单已就绪，需要开始编码实现时 |
| **触发命令** | `/mp-implement` |
| **内部流程** | 读取工单 → /tdd 逐切片实现 → /code-review 审查 → 提交 |

#### `/mp-implement-spec` — 并行实现规格

| 项目 | 内容 |
|------|------|
| **核心功能** | 基于 Spec 的工单图，使用多个子 Agent 并行实现，最大化并发 |
| **适用场景** | 大型 Spec 有多个可并行的工单时 |
| **触发命令** | `/mp-implement-spec` |
| **关键机制** | 每个 Implementer 子 Agent 在独立 worktree 工作，完成后合并到 PR 分支 |

#### `/mp-tdd` — 测试驱动开发

| 项目 | 内容 |
|------|------|
| **核心功能** | Red → Green 循环的完整参考：好的测试标准、测试位置、反模式、循环规则 |
| **适用场景** | 需要 test-first 构建功能或修复 Bug 时 |
| **触发命令** | `/mp-tdd` |
| **核心规则** | ① Red before Green ② 一次一个切片 ③ 重构不属于循环 |
| **反模式** | 实现耦合测试、同义反复测试、水平切片测试 |

#### `/mp-code-review` — 双轴代码审查

| 项目 | 内容 |
|------|------|
| **核心功能** | 从 Standards（编码标准）和 Spec（需求规格）两个维度并行审查代码变更 |
| **适用场景** | 审查分支、PR、或自某个固定点以来的变更时 |
| **触发命令** | `/mp-code-review <fixed-point>` |
| **参数** | `fixed-point`：commit SHA / 分支名 / tag / `main` / `HEAD~5` |
| **输出** | `## Standards` 和 `## Spec` 两个独立报告 |

---

### 3.2 入口 Skills（On-Ramps）

#### `/mp-triage` — 问题分类

| 项目 | 内容 |
|------|------|
| **核心功能** | 将 Issue/PR 通过状态机流转：needs-triage → needs-info → ready-for-agent/ready-for-human/wontfix |
| **适用场景** | 有新的 Bug 报告或功能请求需要评估时 |
| **触发命令** | `/mp-triage "show me anything that needs attention"` |
| **角色** | 分类：bug/enhancement；状态：5 种流转状态 |

#### `/mp-diagnosing-bugs` — Bug 诊断

| 项目 | 内容 |
|------|------|
| **核心功能** | 6 阶段结构化调试：构建反馈循环 → 复现最小化 → 假设 → 探测 → 修复 → 清理 |
| **适用场景** | 遇到难以定位的 Bug、间歇性故障、性能回退时 |
| **触发命令** | `/mp-diagnosing-bugs` |
| **核心原则** | "没有 Red 命令就没有 Phase 2"——先建反馈循环，再谈假设 |

#### `/mp-wayfinder` — 大型规划

| 项目 | 内容 |
|------|------|
| **核心功能** | 将超大型模糊需求拆解为 Issue Tracker 上的决策地图，逐个解决直到路径清晰 |
| **适用场景** | 工作量大到超出单个 Agent 会话，且路径不明确时 |
| **触发命令** | `/mp-wayfinder` |
| **输出** | 地图 Issue（wayfinder:map）+ 子决策 Issues |
| **工单类型** | Research / Prototype / Grilling / Task |

---

### 3.3 代码健康 Skills

#### `/mp-improve-codebase-architecture` — 架构诊断

| 项目 | 内容 |
|------|------|
| **核心功能** | 扫描代码库发现"加深机会"，生成可视化 HTML 报告，然后对选定候选进行 Grilling |
| **适用场景** | 有空闲时间改善代码库可测试性和 AI 可导航性时 |
| **触发命令** | `/mp-improve-codebase-architecture` |
| **输出** | 交互式 HTML 报告（含 Before/After 图） |

#### `/mp-code-review` — （见 3.1 主流程）

---

### 3.4 词汇层 Skills

#### `/mp-codebase-design` — 深度模块设计词汇

| 项目 | 内容 |
|------|------|
| **核心功能** | 定义深度模块设计的共享词汇：Module、Interface、Depth、Seam、Adapter、Leverage、Locality |
| **适用场景** | 设计或改善模块接口、决定 Seam 位置、使代码更可测试时 |
| **触发命令** | `/mp-codebase-design` |
| **核心原则** | ① 删除测试 ② 接口是测试面 ③ 一个 Adapter = 假设 Seam，两个 = 真实 Seam |

#### `/mp-domain-modeling` — 领域建模

| 项目 | 内容 |
|------|------|
| **核心功能** | 主动构建和锐化项目的领域模型：挑战术语、发明边界场景、维护 CONTEXT.md |
| **适用场景** | 讨论代码库术语、编写/编辑 CONTEXT.md、记录 ADR 时 |
| **触发命令** | `/mp-domain-modeling` |
| **文件结构** | `CONTEXT.md`（术语表）+ `docs/adr/`（架构决策记录） |

---

### 3.5 独立工具 Skills

#### `/mp-research` — 后台调研

| 项目 | 内容 |
|------|------|
| **核心功能** | 启动后台 Agent 基于权威一手来源调研问题，输出带引用的 Markdown 文件 |
| **适用场景** | 需要调研某个技术/API/文档，同时继续其他工作 |
| **触发命令** | `/mp-research` |

#### `/mp-resolving-merge-conflicts` — 合并冲突解决

| 项目 | 内容 |
|------|------|
| **核心功能** | 按意图（而非按行）解决 Git 合并/变基冲突，追踪双方的原始意图 |
| **适用场景** | 正在进行 merge/rebase 且遇到冲突时 |
| **触发命令** | `/mp-resolving-merge-conflicts` |
| **关键规则** | 永不 `--abort`；保留双方意图；运行自动化检查后完成 |

#### `/mp-retro` — 会话回顾

| 项目 | 内容 |
|------|------|
| **核心功能** | 对编码会话进行回顾，提出环境改进建议（导航、自动化检查、编码标准等） |
| **适用场景** | 完成一段编码工作后，希望改善未来 Agent 运行环境 |
| **触发命令** | `/mp-retro` |

#### `/mp-scaffold-exercises` — 练习脚手架

| 项目 | 内容 |
|------|------|
| **核心功能** | 创建包含 section/exercise/problem/solution/explainer 的目录结构 |
| **适用场景** | 需要搭建课程练习结构时 |
| **触发命令** | `/mp-scaffold-exercises` |

#### `/mp-teach` — 教学系统

| 项目 | 内容 |
|------|------|
| **核心功能** | 跨多个会话的有状态教学：课程（HTML）、参考资料、学习记录、任务定义 |
| **适用场景** | 想系统学习一个新概念或技能时 |
| **触发命令** | `/mp-teach "想学什么"` |
| **工作区** | MISSION.md / lessons/ / reference/ / learning-records/ / RESOURCES.md |

#### `/mp-to-questionnaire` — 生成问卷

| 项目 | 内容 |
|------|------|
| **核心功能** | 将你无法独自回答的决策转化为给他人填写的问卷 |
| **适用场景** | 阻塞你的不是技术问题而是他人的信息时 |
| **触发命令** | `/mp-to-questionnaire` |

#### `/mp-wait-what` — 重新解释

| 项目 | 内容 |
|------|------|
| **核心功能** | 当上一条消息没理解时，要求用简化英语和 CONTEXT.md 词汇重新解释 |
| **适用场景** | 对话中 Agent 输出了难以理解的内容 |
| **触发命令** | `/mp-wait-what` |

#### `/mp-wizard` — 交互式向导

| 项目 | 内容 |
|------|------|
| **核心功能** | 生成交互式 Bash 脚本，引导人类完成只有他们能执行的手动步骤 |
| **适用场景** | 配置基础设施、设置凭据、点击第三方面板、执行一次性迁移 |
| **触发命令** | `/mp-wizard` |

#### `/mp-migrate-to-shoehorn` — 测试迁移

| 项目 | 内容 |
|------|------|
| **核心功能** | 将测试文件中的 `as` 类型断言迁移为 `@total-typescript/shoehorn` 的类型安全替代 |
| **适用场景** | 测试中有大量 `as` 断言导致类型安全问题时 |
| **触发命令** | `/mp-migrate-to-shoehorn` |

---

### 3.6 写作 Skills

#### `/mp-writing-for-agents` — 为 Agent 写作

| 项目 | 内容 |
|------|------|
| **核心功能** | 编写 Agent 消费文档的参考指南：上下文指针、信息层级、引导词、修剪规则 |
| **适用场景** | 创建/编辑 Skills、修改 AGENTS.md 或 CLAUDE.md 时 |
| **触发命令** | `/mp-writing-for-agents` |

#### `/mp-writing-fragments` — 碎片探索

| 项目 | 内容 |
|------|------|
| **核心功能** | 纯探索模式写作：通过访谈产出原始碎片，不承诺结构 |
| **适用场景** | 想围绕一个主题自由探索写作素材时 |
| **触发命令** | `/mp-writing-fragments` |

#### `/mp-writing-beats` — 节拍写作

| 项目 | 内容 |
|------|------|
| **核心功能** | 将原始素材组装为"选择你自己的冒险"式节拍旅程 |
| **适用场景** | 有素材，需要组装成文章时（exploit 阶段） |
| **触发命令** | `/mp-writing-beats` |

#### `/mp-writing-shape` — 段落塑形

| 项目 | 内容 |
|------|------|
| **核心功能** | 将原始素材逐段塑形为完整文章 |
| **适用场景** | 有素材，需要逐段构建结构化文章时 |
| **触发命令** | `/mp-writing-shape` |

---

### 3.7 项目配置 Skills

#### `/mp-setup-matt-pocock-skills` — 初始化配置

| 项目 | 内容 |
|------|------|
| **核心功能** | 配置仓库的 Issue Tracker、分类标签词汇、领域文档布局 |
| **适用场景** | 首次使用 Matt Pocock Skills 前必须运行一次 |
| **触发命令** | `/mp-setup-matt-pocock-skills` |
| **输出** | `docs/agents/issue-tracker.md`、`docs/agents/domain.md`、`docs/agents/triage-labels.md` |

#### `/mp-setup-pre-commit` — 预提交钩子

| 项目 | 内容 |
|------|------|
| **核心功能** | 配置 Husky + lint-staged + Prettier 的预提交钩子 |
| **适用场景** | 需要在提交时自动格式化、类型检查和运行测试 |
| **触发命令** | `/mp-setup-pre-commit` |

#### `/mp-setup-ts-deep-modules` — TypeScript 深度模块

| 项目 | 内容 |
|------|------|
| **核心功能** | 使用 dependency-cruiser 强制 TypeScript 包的入口点边界规则 |
| **适用场景** | 需要确保包只能通过入口点导入，内部实现隐藏 |
| **触发命令** | `/mp-setup-ts-deep-modules` |

#### `/mp-git-guardrails-claude-code` — Git 安全护栏

| 项目 | 内容 |
|------|------|
| **核心功能** | 设置 PreToolUse 钩子拦截危险 Git 命令（push、reset --hard、clean -fd 等） |
| **适用场景** | 需要防止 Agent 执行破坏性 Git 操作时 |
| **触发命令** | `/mp-git-guardrails-claude-code` |

#### `/mp-loop-me` — 工作流设计

| 项目 | 内容 |
|------|------|
| **核心功能** | 通过 Grilling 设计工作流规范，输出到 `workflows/*.md` |
| **适用场景** | 需要将重复性工作流程规范化和自动化时 |
| **触发命令** | `/mp-loop-me` |

---

## 四、实战用例集

### 4.1 `/mp-grill-with-docs` 实战

**用例 1：新功能设计**
- **需求**：为电商系统添加"购物车分享"功能
- **命令**：`/mp-grill-with-docs`
- **流程**：Agent 逐轮提问 → 分享链接格式？权限模型？过期策略？实时同步？
- **输出**：`CONTEXT.md` 更新术语 + `docs/adr/0003-cart-sharing.md`

**用例 2：技术选型**
- **需求**：选择实时通信方案
- **命令**：`/mp-grill-with-docs`
- **流程**：WebSocket vs SSE vs Long Polling → 连接数预估 → 消息格式 → 重连策略
- **输出**：ADR 记录选型决策及理由

**用例 3：API 设计**
- **需求**：设计 GraphQL vs REST API
- **命令**：`/mp-grill-with-docs`
- **流程**：查询复杂度 → 缓存需求 → 客户端多样性 → 团队经验
- **输出**：决策文档 + 更新的领域术语表

### 4.2 `/mp-diagnosing-bugs` 实战

**用例 1：间歇性 500 错误**
- **需求**：API 偶发 500 错误，无法稳定复现
- **命令**：`/mp-diagnosing-bugs`
- **流程**：
  1. 构建反馈循环 → 编写压测脚本循环 100 次提高复现率
  2. 复现+最小化 → 发现只在特定并发数下触发
  3. 假设 → 3 个假设：竞态条件/连接池耗尽/超时配置
  4. 探测 → 添加 `[DEBUG-a4f2]` 标记日志
  5. 修复 → 写回归测试 → 修复 → 清理
- **输出**：回归测试 + 修复 PR + 清理后的代码

**用例 2：性能回退**
- **需求**：页面加载从 200ms 退化到 2s
- **命令**：`/mp-diagnosing-bugs`
- **流程**：建立性能基线 → `performance.now()` 测量 → 二分法定位到特定 commit → 修复
- **输出**：性能基线测试 + 修复 + 性能验证

### 4.3 `/mp-tdd` 实战

**用例 1：实现折扣计算**
- **需求**：实现购物车折扣逻辑
- **命令**：`/mp-tdd`
- **流程**：
  1. 确认 Seam：`calculateDiscount(cart): Discount`
  2. Red：写失败测试 `expect(calculateDiscount(mockCart)).toEqual({ amount: 10 })`
  3. Green：写最小实现
  4. 下一个切片：满减折扣 → 重复 Red-Green
- **输出**：完整测试套件 + 实现代码

**用例 2：修复边界 Bug**
- **需求**：空购物车时折扣计算崩溃
- **命令**：`/mp-tdd`
- **流程**：Red → 写空购物车测试 → Green → 处理空值 → 验证所有测试通过
- **输出**：新增边界测试 + 修复代码

### 4.4 `/mp-code-review` 实战

**用例 1：PR 审查**
- **需求**：审查 feature/auth 分支的变更
- **命令**：`/mp-code-review main`
- **流程**：
  1. 固定点 = `main`，获取 diff
  2. 并行启动 Standards 子 Agent + Spec 子 Agent
  3. Standards 检查：Fowler 代码气味 + 仓库编码标准
  4. Spec 检查：需求覆盖度 + 范围蔓延
- **输出**：双轴报告

```markdown
## Standards
- Feature Envy: `UserService.processOrder()` 过多访问 `Order.items`
- Primitive Obsession: `userId: string` 应为 `UserId` 类型

## Spec
- ✅ 用户认证已实现
- ⚠️ 刷新令牌轮换部分缺失（Spec §3.2）
```

### 4.5 `/mp-wayfinder` 实战

**用例 1：微服务迁移**
- **需求**：将单体应用迁移为微服务架构（巨大且模糊）
- **命令**：`/mp-wayfinder`
- **流程**：
  1. 命名目的地："确定服务边界并输出迁移规格"
  2. 广度优先 Grilling → 发现数据迁移/服务发现/API 网关等决策
  3. 创建地图 Issue + 决策子 Issues
  4. 逐个解决决策工单，直到路径清晰
- **输出**：地图 Issue + 链接的决策记录

---

## 五、工程开发综合范例

### 范例 1：从需求分析到 TDD 实现的完整开发流程

**场景**：为 SaaS 平台添加"团队邀请"功能

```
步骤 1: /mp-setup-matt-pocock-skills    ← 首次配置（仅一次）
步骤 2: /mp-grill-with-docs              ← 深度访谈，产出 CONTEXT.md + ADR
         "邀请模型是什么？过期策略？权限？"
步骤 3: /mp-to-spec                       ← 综合为 Spec Issue
         输出：User Stories + Implementation Decisions + Testing Decisions
步骤 4: /mp-to-tickets                    ← 拆分为垂直切片的工单
         Ticket 01: 邀请数据模型 (无阻塞)
         Ticket 02: 邀请 API 端点 (阻塞: 01)
         Ticket 03: 邀请 UI 界面 (阻塞: 02)
步骤 5: /mp-implement (per ticket)        ← 每个工单独立实现
         内部驱动 /mp-tdd → Red-Green 循环
         完成后 /mp-code-review 审查
步骤 6: 提交到当前分支
```

**上下文管理**：步骤 2-4 在同一上下文窗口中完成。步骤 5 每个工单从新上下文启动。

### 范例 2：遗留代码重构的最佳实践路径

**场景**：一个 2000 行的 God Class 需要拆分

```
步骤 1: /mp-improve-codebase-architecture  ← 扫描代码库，生成 HTML 报告
         发现 God Class 是"浅模块"，接口复杂度≈实现复杂度
步骤 2: 选择候选 → 进入 Grilling
         /mp-grilling 讨论拆分策略
步骤 3: /mp-codebase-design               ← 用深度模块词汇设计新接口
         Module/Interface/Depth/Seam 分析
         应用"删除测试"：删除后复杂度消失 = 透传，不是深度模块
步骤 4: /mp-domain-modeling                ← 更新 CONTEXT.md 术语
         为新模块命名，记录 ADR
步骤 5: /mp-tdd                            ← 在新 Seam 处 test-first 重构
         一次一个垂直切片
步骤 6: /mp-code-review                    ← 审查重构变更
```

### 范例 3：多团队协作的代码审查流程

**场景**：团队有 3 个并行开发的 feature 分支需要审查

```
步骤 1: /mp-triage "show me anything that needs attention"
         发现 3 个 ready-for-agent 的 PR
步骤 2: 对每个 PR 执行 /mp-code-review main
         Standards 子 Agent：检查编码标准 + 代码气味
         Spec 子 Agent：检查需求覆盖度
步骤 3: 汇总发现
         PR-A: Standards pass, Spec pass → 可合并
         PR-B: Standards pass, Spec fail (缺少错误处理) → 需修改
         PR-C: Standards fail (Feature Envy), Spec pass → 需重构
步骤 4: /mp-retro                          ← 回顾本次审查
         发现审查反复发现同类问题 → 建议添加自动化检查规则
```

### 范例 4：大型项目的架构诊断与优化

**场景**：项目代码量增长，Agent 导航困难，测试覆盖低

```
步骤 1: /mp-improve-codebase-architecture
         扫描发现 5 个"加深机会"
         候选 A [Strong]: OrderService 可拆分为深度模块
         候选 B [Worth exploring]: 支付逻辑耦合过紧
         候选 C [Speculative]: 通知系统可提取
步骤 2: 选择候选 A → /mp-grilling 讨论设计
步骤 3: /mp-codebase-design 设计新接口
         小接口 + 深实现 = 深度模块
步骤 4: /mp-domain-modeling 更新术语表
步骤 5: /mp-to-spec → /mp-to-tickets → /mp-implement
         按工单逐步重构
步骤 6: /mp-setup-ts-deep-modules          ← 强制包边界规则
         dependency-cruiser 验证入口点约束
步骤 7: /mp-setup-pre-commit               ← 添加预提交检查
         确保每次提交都通过类型检查和测试
```

### 范例 5：Bug 排查与修复的标准操作流

**场景**：用户报告"结账时偶尔扣款成功但订单状态未更新"

```
步骤 1: /mp-triage "#42"                   ← 分类 Issue
         验证 Bug → 确认复现 → 标记为 bug + needs-triage
步骤 2: /mp-diagnosing-bugs                ← 结构化诊断
         Phase 1: 构建反馈循环
           → 编写集成测试模拟并发结账场景
           → 循环 100 次提高复现率到 50%+
         Phase 2: 复现+最小化
           → 发现只在支付回调和订单更新存在竞态时触发
         Phase 3: 假设（3 个）
           H1: 支付回调先于订单创建完成
           H2: 事务隔离级别不足
           H3: 消息队列消费顺序问题
         Phase 4: 探测 → [DEBUG-a4f2] 标记日志
           → 确认 H1
         Phase 5: 写回归测试 → 修复（添加幂等性检查）→ 验证
         Phase 6: 清理所有 DEBUG 日志
步骤 3: /mp-code-review                    ← 审查修复
步骤 4: 提交，commit message 包含正确的假设
```

---

## 六、最佳实践总结

### 6.1 上下文管理

| 原则 | 说明 |
|------|------|
| **同一窗口保持连贯** | grill → to-spec → to-tickets 保持在同一上下文中，不要 compact |
| **实现时开新窗口** | 每个 `/implement` 从新上下文启动，基于工单独立工作 |
| **Smart Zone 意识** | 约 150k tokens 为有效推理区间，接近时在阶段边界 compact |
| **阶段边界选择** | Continue > Handoff > Subagent > Compact，Continue 是默认首选 |

### 6.2 团队协作规范

| 实践 | 建议 |
|------|------|
| **首次配置** | 每个新仓库首先运行 `/mp-setup-matt-pocock-skills` |
| **统一词汇** | 维护 `CONTEXT.md` 作为领域术语唯一来源 |
| **ADR 纪律** | 仅当满足三条件时创建 ADR：难以反转 + 出乎意料 + 真实权衡 |
| **Git 安全** | 运行 `/mp-git-guardrails-claude-code` 防止 Agent 执行危险操作 |
| **预提交** | 运行 `/mp-setup-pre-commit` 确保每次提交经过检查 |
| **代码审查** | 所有变更必须经过 `/mp-code-review` 双轴审查 |
| **回顾改进** | 定期运行 `/mp-retro` 改善 Agent 运行环境 |

### 6.3 工具链配置建议

```
项目初始化清单：
□ /mp-setup-matt-pocock-skills    → Issue Tracker + 标签 + 领域文档
□ /mp-setup-pre-commit            → Husky + lint-staged + Prettier
□ /mp-git-guardrails-claude-code  → 拦截危险 Git 命令
□ /mp-setup-ts-deep-modules       → （TypeScript 项目）包边界强制
```

### 6.4 工作流选择速查

| 你的情况 | 使用的 Skill |
|---------|-------------|
| 有新功能想法，需要讨论清楚 | `/mp-grill-with-docs` |
| 讨论够了，需要固化规格 | `/mp-to-spec` |
| 规格有了，需要拆分任务 | `/mp-to-tickets` |
| 任务就绪，需要编码实现 | `/mp-implement`（内部用 `/mp-tdd`） |
| 代码写完了，需要审查 | `/mp-code-review` |
| 有 Bug 报告需要处理 | `/mp-triage` → `/mp-diagnosing-bugs` |
| 项目太大看不清路径 | `/mp-wayfinder` |
| 想改善代码库架构 | `/mp-improve-codebase-architecture` |
| 需要别人提供信息才能继续 | `/mp-to-questionnaire` |
| 遇到合并冲突 | `/mp-resolving-merge-conflicts` |
| 不确定该用哪个 Skill | `/mp-ask-matt` |

### 6.5 关键设计原则

1. **深度模块**：小接口 + 大实现 = 高杠杆。用"删除测试"判断模块是否有深度。
2. **垂直切片**：每个工单/测试切穿所有层（schema → API → UI → tests），不做水平分层。
3. **Tracer Bullet**：每个切片是一个完整的端到端验证，完成即可演示。
4. **Seam 优先**：先确认测试的 Seam，再写测试，再写实现。
5. **上下文指针**：文档间通过路径引用，不复制粘贴内容。
6. **Red before Green**：永远先看到测试失败，再写实现。
7. **双轴审查**：Standards 和 Spec 独立报告，防止一个掩盖另一个。

---

> **参考资源**：每个 Skill 的完整源码和附属文档位于 `C:\Users\joezxh\.agents\skills\mp-<name>\` 目录下，包含 SKILL.md 及其引用的模板文件和补充说明。
