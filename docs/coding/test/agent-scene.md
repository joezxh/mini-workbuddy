# Agent 服务 — 端到端浏览器自动化测试 Skill

> 本文档为 AI 浏览器测试 Agent 提供完整的 Agent/Agent-Team(智能体/智能体团队)服务测试提示词。
> 使用 `/browser` 启动浏览器自动化测试,或使用 MCP Playwright 执行测试。
> 适用于 gstack `/qa` 和 `/qa-only` Skill,通过 `/open-gstack-browser` 导入认证 Cookie 后执行端到端测试。
> 文档同时包含问题自动定位与修复建议机制,支持端到端回归测试。

---

## 目录

- [1.测试前置条件](#测试前置条件)
- [2.全局测试策略](#全局测试策略)
- [3.Skill 调用方式](#skill-调用方式)
- [4.问题发现与自动修复流程](#问题发现与自动修复流程)
- [5.Agent 服务测试模块](#agent-服务测试模块)
  - [AGT-01 Agent 配置列表](#agt-01-agent-配置列表)
  - [AGT-02 Agent 创建/编辑](#agt-02-agent-创建编辑)
  - [AGT-03 Agent 详情抽屉](#agt-03-agent-详情抽屉)
  - [AGT-04 Agent 技能规则](#agt-04-agent-技能规则)
  - [AGT-05 Agent 执行记录](#agt-05-agent-执行记录)
  - [AGT-06 Agent 执行详情](#agt-06-agent-执行详情)
  - [AGT-07 团队列表](#agt-07-团队列表)
  - [AGT-08 团队编排器](#agt-08-团队编排器)
  - [AGT-09 团队对话与回放](#agt-09-团队对话与回放)
  - [AGT-10 定时调度管理](#agt-10-定时调度管理)
- [6.测试结果报告模板](#测试结果报告模板)
- [7.模块开发对照与补全清单](#模块开发对照与补全清单)
- [8.文档版本](#文档版本)

---

## 1.测试前置条件

### 1.1 环境要求

| 项目 | 值 |
|------|------|
| 前端地址 | `http://localhost:5173` |
| 后端 API 地址 | `http://localhost:8000` |
| Agent 服务路由前缀 | `/api/v1/agent-config`, `/api/v1/agent-execution`, `/api/v1/ai-team` |
| 管理员账号 | `admin` |
| 管理员密码 | `admin123` |

### 1.2 服务依赖检查

测试前需确认以下服务已启动:

1. **FastAPI 后端**(:8000) — 核心 API 服务
2. **Vue 前端**(:5173) — Vite 开发服务器
3. **PostgreSQL** — 数据库
4. **Redis** — 缓存（MCP 服务安装、异步任务依赖）

### 1.3 浏览器环境要求

- 浏览器:Chromium / Chrome(headless 模式或带 UI 模式均可)
- Cookie 导入:通过 `/open-gstack-browser` 导入已登录 Cookie,避免重复登录
- 如需手动登录:账号 `admin`,密码 `admin123`

---

## 2.全局测试策略

### 2.1 模块列表:

| 模块 ID | 模块名称 | 测试场景数 | 说明 |
|---------|---------|-----------|------|
| AGT-01 | Agent 配置列表 | 10 | 列表加载 + 监控统计 + 筛选 + 启禁用 + 删除 |
| AGT-02 | Agent 创建/编辑 | 8 | 表单校验 + 模型配置 + 工具/技能/MCP 绑定 + ReAct 配置 |
| AGT-03 | Agent 详情抽屉 | 6 | 基本信息 + 可视化配置 + 监控统计 + 链路追踪 |
| AGT-04 | Agent 技能规则 | 6 | 规则 CRUD + 启禁用 + 优先级 |
| AGT-05 | Agent 执行记录 | 8 | 列表 + 多条件筛选 + 统计 + 跳转过滤 |
| AGT-06 | Agent 执行详情 | 5 | DAG 拓扑 + 时间线 + 人工介入 + 输入输出 |
| AGT-07 | 团队列表 | 7 | 卡片网格 + 创建/编辑 + 启禁用 + 删除 |
| AGT-08 | 团队编排器 | 7 | 成员管理 + 节点属性 + 拓扑验证 + 保存 |
| AGT-09 | 团队对话与回放 | 10 | SSE 流式对话 + 干预 + 回放控制 + 分支重跑 |
| AGT-10 | 定时调度管理 | 10 | 调度 CRUD + 多模式 + 暂停/恢复/立即执行 |
| **合计** | **10 个模块** | **77 个场景** | **~6h 测试时间** |

### 2.2 每个测试用例的验证清单

1. **页面加载**:页面是否正常渲染,无白屏、无 JS 错误
2. **数据加载**:表格数据是否成功加载,loading 状态是否正确消失
3. **交互响应**:按钮点击是否有响应,弹窗是否正常弹出
4. **表单验证**:必填字段校验是否生效,错误提示是否显示
5. **数据回填**:编辑时已有数据是否正确回填到表单
6. **操作反馈**:成功/失败是否有 message 提示
7. **状态更新**:操作后列表数据是否自动刷新
8. **字典标签**:DictTag/Tag 颜色是否正确显示
9. **控制台检查**:浏览器控制台是否有报错或警告

### 2.3 通用测试模式

每个模块遵循 **CRUD 测试循环**:

```
1. 打开页面 → 验证列表加载
2. 搜索/筛选 → 验证条件过滤
3. 点击「新增」→ 验证弹窗/表单初始化 → 填写并提交 → 验证列表刷新
4. 点击「编辑」→ 验证数据回填 → 修改并提交 → 验证更新生效
5. 点击「删除」→ 验证确认弹窗 → 确认删除 → 验证列表更新
6. 边界测试 → 空数据、超长文本、特殊字符、并发操作
```

---

## 3.Skill 调用方式

### 3.1 方式一:使用 gstack /qa Skill(推荐)

```bash
/qa --tier standard --url http://localhost:5173
```

### 3.2 方式二:使用 gstack /open-gstack-browser

```
/open-gstack-browser
启动 GStack 浏览器后,执行以下测试流程...

# 或导入 Cookie 跳过登录
/setup-browser-cookies
选择已登录的会话
执行测试...
```

### 3.3 方式三:直接使用 MCP Playwright

```bash
# 启动浏览器
$B goto http://localhost:5173/login
$B screenshot "login-page.png"

# 登录
$B fill "#username" "admin"
$B fill "#password" "admin123"
$B click "button[type=submit]"

# 验证跳转
$B wait-for-url "**/dashboard"
$B screenshot "after-login.png"

# 继续测试各模块...
```

### 3.4 方式四:使用 /qa-only(仅发现问题不修复)

```
/qa-only --tier exhaustive --scope "Agent服务-Agent配置管理"
```

---

## 4.问题发现与自动修复流程

### 4.1 三阶段闭环

```
阶段 1:问题发现(Detect)
  → 浏览器测试发现异常
  → 截图记录当前状态
  → 记录控制台错误日志
  → 标记失败测试用例

阶段 2:问题定位(Diagnose)
  → 根据错误信息判断问题层级:
    - 前端渲染问题 → 检查 Vue 组件
    - API 请求失败 → 检查 Network 面板(状态码、响应体)
    - 后端逻辑错误 → 检查后端日志
    - 数据问题 → 检查数据库状态
  → 定位到具体文件和行号

阶段 3:自动修复建议(Fix)
  → 输出修复方案(代码 diff)
  → 常见修复模式:
    - 组件未导入 → 补充 import
    - API 路径错误 → 对齐后端路由
    - v-model 绑定问题 → 检查响应式
    - 表单初始值缺失 → 补充默认值
    - 字典类型未注册 → 补充 DictType
    - SSE 连接中断 → 检查 EventSource/fetch 流式解析
    - ECharts 渲染失败 → 检查拓扑图数据格式
    - MCP 安装失败 → 检查内置模板自动安装逻辑
  → 修复后自动重新执行失败的测试用例
```

### 4.2 常见错误自动匹配表

| 浏览器现象 | 可能原因 | 检查文件 |
|-----------|---------|---------|
| 白屏 | 路由组件未注册 / import 路径错误 | `router/`, `views/admin/agent/` |
| 表格无数据 | API 返回错误 / 后端未启动 | `request.ts`, Network 面板 |
| 弹窗打不开 | `v-model:open` / `v-model:visible` 绑定问题 | 对应 FormModal.vue |
| 表单不回填 | watch 未监听 / props 延迟 | FormModal.vue 的 watch |
| Tag 不显示 | 字典类型未注册 / 值为空 | `useAdminDict.ts`, 后端字典表 |
| 401 错误 | Token 过期 / 刷新 Token 逻辑失败 | `request.ts`, `auth.ts` |
| 删除失败 | 外键约束 / 关联数据未清理 | 后端 Service |
| Switch 不切换 | API 调用失败 / 状态未同步 | `toggleAgent()`, `updateTeam()` |
| SSE 流中断 | 网络连接断开 / 后端未返回 SSE 格式 | `TeamConversation.vue` fetch 解析 |
| ECharts 不渲染 | 拓扑数据格式错误 / 缺少 node_key/layer | `AgentExecutionManagement.vue` renderTopo() |
| MCP 安装失败 | 内置模板 ID 解析错误 / API 调用失败 | `AgentFormModal.vue` installMcpSquare() |
| 分页异常 | page/page_size 参数不对 | API 请求参数 |
| 监控统计不显示 | API 返回空 / 统计接口失败 | `getAgentStats()`, `AgentManagement.vue` |

---

## 5.Agent 服务测试模块

---

### 5.1 AGT-01 Agent 配置列表

**页面路径**: 左侧菜单「Agent 管理」→「Agent 配置」  
**源码文件**: `src/views/admin/agent/AgentManagement.vue`  
**API 文件**: `src/api/agentConfig.ts`  
**权限标识**: `agent:config:create`, `agent:config:update`, `agent:config:delete`

#### 5.1.1 测试场景

#### 5.1.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 配置列表页面,执行完整的 Agent 配置列表测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在左侧菜单点击「Agent 管理」→「Agent 配置」
3. 等待页面加载完成

---

【测试场景 1:列表加载与基础显示】
1. 验证 Agent 列表正常加载
2. 检查列:ID/agent_code/名称/实现类型/分类/模型配置/状态/调用次数/平均耗时/排序/操作
3. 验证分页功能正常
4. 验证实现类型列使用 Tag 标签(字典驱动)
5. 验证分类列使用 Tag 标签(字典驱动)
6. 验证模型配置列显示 provider/model/系统密钥标签

预期结果:
✅ 表格 11 列完整
✅ Tag 颜色正确
✅ 分页正常

---

【测试场景 2:监控统计卡片】
1. 验证 4 个统计卡片正常显示:
   - 总 Agent 数(启用/禁用)
   - 活跃会话(总会话)
   - 今日调用(成功/失败)
   - 平均耗时(链路数)
2. 点击「刷新监控」按钮
3. 验证统计数据更新

预期结果:
✅ 4 个统计卡片完整
✅ 刷新按钮响应正常

---

【测试场景 3:筛选功能】
1. 在「实现类型」下拉选择类型,验证列表过滤
2. 在「分类」下拉选择分类,验证列表过滤
3. 在「状态」下拉选择启用/禁用,验证列表过滤
4. 在关键词搜索框输入关键词,点击搜索,验证列表过滤
5. 点击「重置」按钮,验证条件清空,列表恢复

预期结果:
✅ 实现类型筛选正常
✅ 分类筛选正常
✅ 状态筛选正常
✅ 关键词搜索正常
✅ 重置清空条件

---

【测试场景 4:分页功能】
1. 验证分页显示总数
2. 切换页码,验证列表刷新
3. 修改每页条数,验证列表刷新

预期结果:
✅ 分页切换正常
✅ 每页条数切换正常

---

【测试场景 5:启禁用切换】
1. 点击某 Agent 的状态 Switch
2. 验证 API 调用 POST /api/v1/agent-config/{id}/toggle
3. 验证状态更新成功提示
4. 验证监控统计同步刷新

预期结果:
✅ Switch 切换正常
✅ 状态更新成功
✅ 统计同步刷新

---

【测试场景 6:删除 Agent】
1. 点击某 Agent 的「删除」按钮
2. 验证确认弹窗显示
3. 点击确认,验证删除成功
4. 验证列表刷新,Agent 消失

预期结果:
✅ 删除确认正常
✅ 删除成功后列表刷新

---

【测试场景 7:查看详情】
1. 点击某 Agent 的「详情」按钮
2. 验证 AgentDetailDrawer 抽屉打开
3. 验证详情数据正确加载

预期结果:
✅ 详情抽屉打开正常
✅ 详情数据完整

---

【测试场景 8:编辑 Agent】
1. 点击某 Agent 的「编辑」按钮
2. 验证 AgentFormModal 弹窗打开
3. 验证数据正确回填

预期结果:
✅ 编辑弹窗打开
✅ 数据回填正确

---

【测试场景 9:链路追踪跳转】
1. 点击某 Agent 的「链路」按钮
2. 验证跳转到「调用记录」Tab
3. 验证按该 Agent 精确过滤调用链路
4. 验证显示过滤提示标签
5. 点击「查看全部」按钮,验证清除过滤条件

预期结果:
✅ 链路跳转正常
✅ 过滤条件生效
✅ 清除过滤正常

---

【测试场景 10:创建 Agent 入口】
1. 点击顶部「创建 Agent」按钮
2. 验证 AgentFormModal 弹窗打开
3. 验证弹窗标题为「创建 Agent」

预期结果:
✅ 创建弹窗打开
✅ 标题正确

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 列表分页 | GET | /api/v1/agent-config |
| 统计概览 | GET | /api/v1/agent-config/stats/overview |
| 启禁用 | POST | /api/v1/agent-config/{id}/toggle |
| 删除 | DELETE | /api/v1/agent-config/{id} |

---

【问题诊断】
- 列表不加载 → 检查 getAgentList() 是否成功
- 统计卡片不显示 → 检查 getAgentStats() 是否成功
- Switch 切换失败 → 检查 toggleAgent() API 调用
- 删除失败 → 检查后端是否有依赖数据(执行记录等)
```

---

### 5.2 AGT-02 Agent 创建/编辑

**页面路径**: Agent 配置列表 → 创建/编辑弹窗  
**源码文件**: `src/views/admin/agent/components/AgentFormModal.vue`  
**API 文件**: `src/api/agentConfig.ts`  
**权限标识**: `agent:config:create`, `agent:config:update`

#### 5.2.1 测试场景

#### 5.2.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 创建/编辑弹窗,执行完整的 Agent 表单测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在 Agent 配置列表点击「创建 Agent」按钮
3. 等待弹窗加载完成

---

【测试场景 1:表单字段完整性】
1. 验证表单字段完整:
   - agent_code(必填,正则校验 ^[a-z][a-z0-9_-]*$)
   - name(必填)
   - agent_type(Radio Group,字典驱动,编辑时禁用)
   - category(Select,可搜索)
   - description(Textarea)
   - system_prompt(Textarea,可视化配置区域)
   - 模型源切换:系统模型 vs 自定义
   - temperature(InputNumber 0-2)
   - max_tokens(InputNumber 512-32768)
   - execution_mode(Select: llm/harness/react/plan)
   - tools(多选 Select)
   - skills(多选 Select)
   - mcp_servers(多选 Select)
   - is_active(Switch)
   - sort_order(InputNumber)
2. 验证必填字段校验:
   - agent_code 为空时提交,显示错误提示
   - name 为空时提交,显示错误提示
   - agent_type 未选择时提交,显示错误提示

预期结果:
✅ 表单字段完整
✅ 必填校验生效

---

【测试场景 2:agent_code 正则校验】
1. 输入 agent_code 为 "ABC"(大写),验证校验失败
2. 输入 agent_code 为 "123abc"(数字开头),验证校验失败
3. 输入 agent_code 为 "test-agent_01"(合法),验证校验通过

预期结果:
✅ 正则校验生效
✅ 错误提示正确

---

【测试场景 3:系统模型 vs 自定义模型切换】
1. 默认进入系统模型模式
2. 验证系统模型下拉列表加载(从已集成模型)
3. 选择系统模型,验证自动填充 provider/model/model_code/key_name
4. 切换到自定义模型模式
5. 验证显示 Provider Select + Model Input
6. 选择 Provider(OpenAI/Dashscope/DeepSeek/Anthropic/Azure/Ollama)
7. 输入 Model 名称

预期结果:
✅ 系统模型选择正常
✅ 自定义模型切换正常
✅ Provider 列表完整

---

【测试场景 4:ReAct 计划执行配置】
1. 将 execution_mode 切换为 "plan"
2. 验证 ReAct 配置区域显示:
   - interaction_mode(auto/approve/confirm_steps)
   - reflection_mode(lightweight/deep)
   - max_iters(InputNumber 1-50)
   - timeout_seconds(InputNumber 30-3600)
3. 切换 execution_mode 为其他值,验证 ReAct 配置区域隐藏

预期结果:
✅ ReAct 配置区域显示/隐藏正常
✅ 字段完整

---

【测试场景 5:工具/技能/MCP 多选绑定】
1. 在 tools 下拉选择多个工具,验证选中状态
2. 在 skills 下拉选择多个技能包,验证选中状态
3. 在 mcp_servers 下拉选择多个 MCP 服务
4. 验证 MCP 服务显示 builtin/installed 标签
5. 选择内置 MCP 服务(以 't' 开头),提交时验证自动安装逻辑

预期结果:
✅ 多选绑定正常
✅ MCP 内置服务自动安装

---

【测试场景 6:提交创建】
1. 填写完整表单:
   - agent_code: "test-agent-001"
   - name: "测试 Agent"
   - agent_type: "CHAT"
   - category: 选择分类
   - description: "自动化测试创建"
   - system_prompt: "你是一个测试助手"
   - 选择系统模型
   - temperature: 0.7
   - max_tokens: 4096
   - execution_mode: "llm"
2. 点击「保存」按钮
3. 验证 API POST /api/v1/agent-config 调用成功
4. 验证显示「创建成功」提示
5. 验证弹窗关闭,列表刷新

预期结果:
✅ 提交成功
✅ 列表刷新

---

【测试场景 7:编辑回填】
1. 在列表点击刚创建的 Agent 的「编辑」按钮
2. 验证弹窗打开,数据正确回填:
   - agent_code(禁用状态)
   - name
   - agent_type(禁用状态)
   - category
   - description
   - system_prompt
   - 模型配置(系统模型/自定义)
   - temperature/max_tokens/execution_mode
   - tools/skills/mcp_servers 选中状态
   - is_active/sort_order
3. 修改 name 为 "测试 Agent 修改版"
4. 提交验证更新成功

预期结果:
✅ 编辑回填正确
✅ 更新成功

---

【测试场景 8:agent_code 唯一性校验】
1. 创建新 Agent,agent_code 输入已存在的值
2. 提交验证后端返回 409 重复错误
3. 验证弹窗不关闭,显示错误提示

预期结果:
✅ 唯一性校验生效

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 创建 | POST | /api/v1/agent-config |
| 更新 | PUT | /api/v1/agent-config/{id} |
| 注册表 | GET | /api/v1/agent-config/registry |
| MCP 安装 | POST | /api/v1/admin/ai/mcp/square/install |

---

【问题诊断】
- 弹窗打不开 → 检查 v-model:visible 绑定
- 编辑不回填 → 检查 watch(props.agentData) 逻辑
- 模型列表不加载 → 检查 getAvailableModels() API
- MCP 安装失败 → 检查 installMcpSquare() 调用
- 提交失败 → 检查 buildPayload() 数据格式
```

---

### 5.3 AGT-03 Agent 详情抽屉

**页面路径**: Agent 配置列表 → 详情抽屉  
**源码文件**: `src/views/admin/agent/components/AgentDetailDrawer.vue`  
**API 文件**: `src/api/agentConfig.ts`  
**权限标识**: `agent:config:query`

#### 5.3.1 测试场景

#### 5.3.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 详情抽屉,执行完整的详情展示测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在 Agent 配置列表点击某 Agent 的「详情」按钮
3. 等待抽屉加载完成

---

【测试场景 1:基本信息卡片】
1. 验证基本信息卡片显示:
   - ID
   - agent_code(代码格式)
   - name
   - agent_type(Tag 标签,颜色区分)
   - 状态(Tag 标签,启用=绿色/禁用=灰色)
   - sort_order
   - created_at(格式化时间)
   - description(无描述显示"暂无描述")

预期结果:
✅ 基本信息完整
✅ Tag 颜色正确

---

【测试场景 2:可视化配置卡片】
1. 验证可视化配置卡片显示:
   - system_prompt(代码格式,无配置显示"未配置")
   - 模型配置(provider/model/temperature)
   - execution_mode
   - tools(Tag 列表,无工具显示"无")
   - skills(Tag 列表,无技能显示"无")
   - mcp_servers(Tag 列表,无 MCP 显示"无")

预期结果:
✅ 可视化配置完整
✅ 空值显示正确

---

【测试场景 3:原始配置 JSON】
1. 验证原始配置卡片显示
2. 验证 JSON 格式化显示(美化格式)

预期结果:
✅ JSON 显示正常

---

【测试场景 4:监控统计卡片】
1. 验证监控统计卡片显示:
   - 调用次数
   - 成功率(百分比)
   - 平均耗时(ms)

预期结果:
✅ 监控统计完整

---

【测试场景 5:最近链路列表】
1. 验证最近链路列表显示(最多 10 条)
2. 验证链路项显示:
   - status(Tag 标签,ERROR=红色/其他=绿色)
   - trace_id(截断显示)
   - agent_id/duration_ms/start_time
3. 点击「查看」链接,验证 AgentTraceDrawer 链路追踪抽屉打开
4. 点击刷新按钮,验证链路列表重新加载

预期结果:
✅ 链路列表正常
✅ 链路追踪抽屉打开

---

【测试场景 6:无链路空状态】
1. 选择无链路记录的 Agent
2. 验证显示空状态提示

预期结果:
✅ 空状态显示正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 详情 | GET | /api/v1/agent-config/{id} |
| 链路列表 | GET | /api/v1/agent/traces |

---

【问题诊断】
- 详情不加载 → 检查 getAgentDetail() API
- 链路不显示 → 检查 getTraceList() API
- JSON 格式化失败 → 检查 formatConfig() 函数
```

---

### 5.4 AGT-04 Agent 技能规则

**页面路径**: Agent 配置列表 → 技能规则抽屉  
**源码文件**: `src/views/admin/agent/AgentManagement.vue` (技能规则抽屉部分)  
**API 文件**: `src/api/skillRule.ts`  
**权限标识**: `agent:rule:create`, `agent:rule:update`, `agent:rule:delete`

#### 5.4.1 测试场景

#### 5.4.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 技能规则抽屉,执行完整的技能规则管理测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在 Agent 配置列表点击某 Agent 的「规则」按钮
3. 等待抽屉加载完成

---

【测试场景 1:规则抽屉打开】
1. 验证技能规则抽屉打开(宽度 720px)
2. 验证抽屉标题显示"技能规则 - {Agent 名称}"
3. 验证规则列表加载

预期结果:
✅ 抽屉打开正常
✅ 标题正确

---

【测试场景 2:规则列表显示】
1. 验证规则表格列:
   - 规则名称
   - 目标技能(package_id)
   - 优先级(Tag 标签,颜色区分:≤10=红色,≤50=橙色,≤100=蓝色,其他=默认)
   - 状态(Switch)
   - 操作(编辑/删除)
2. 验证无规则时显示空状态

预期结果:
✅ 规则列表完整
✅ 优先级颜色正确

---

【测试场景 3:创建规则】
1. 点击「创建规则」按钮
2. 验证 SkillRuleFormModal 弹窗打开
3. 填写规则表单:
   - 规则名称
   - 目标技能
   - 优先级
   - 状态
4. 提交验证创建成功
5. 验证规则列表刷新

预期结果:
✅ 创建规则成功
✅ 列表刷新

---

【测试场景 4:编辑规则】
1. 点击某规则的「编辑」按钮
2. 验证弹窗打开,数据正确回填
3. 修改优先级
4. 提交验证更新成功

预期结果:
✅ 编辑回填正确
✅ 更新成功

---

【测试场景 5:规则启禁用】
1. 点击某规则的状态 Switch
2. 验证 API 调用 updateSkillRule()
3. 验证状态更新成功提示

预期结果:
✅ Switch 切换正常

---

【测试场景 6:删除规则】
1. 点击某规则的「删除」按钮
2. 验证确认弹窗显示
3. 点击确认,验证删除成功
4. 验证规则列表刷新

预期结果:
✅ 删除确认正常
✅ 删除成功

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 规则列表 | GET | /api/v1/skill-rules |
| 创建规则 | POST | /api/v1/skill-rules |
| 更新规则 | PUT | /api/v1/skill-rules/{id} |
| 删除规则 | DELETE | /api/v1/skill-rules/{id} |

---

【问题诊断】
- 规则列表不加载 → 检查 getSkillRules() API
- 创建失败 → 检查 SkillRuleFormModal 表单校验
- Switch 切换失败 → 检查 updateSkillRule() API
```

---

### 5.5 AGT-05 Agent 执行记录

**页面路径**: 左侧菜单「Agent 管理」→「调用记录」  
**源码文件**: `src/views/admin/agent/AgentExecutionManagement.vue`  
**API 文件**: `src/api/agentExecution.ts`  
**权限标识**: `agent:execution:query`

#### 5.5.1 测试场景

#### 5.5.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 执行记录列表页面,执行完整的执行记录查询测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在左侧菜单点击「Agent 管理」→「调用记录」
3. 等待页面加载完成

---

【测试场景 1:列表加载与基础显示】
1. 验证执行记录列表正常加载
2. 检查列:时间/模式/目标/会话/输入/输出/状态/延迟
3. 验证分页功能正常
4. 验证模式列使用 Tag 标签(dify=极客蓝/skill=绿/agent=紫/agent_team=洋红/sqlbot=橙)
5. 验证状态列使用 Tag 标签(字典驱动颜色)

预期结果:
✅ 表格 8 列完整
✅ Tag 颜色正确
✅ 分页正常

---

【测试场景 2:关键词搜索】
1. 在关键词搜索框输入关键词
2. 按回车或清空时自动触发搜索
3. 验证列表过滤出匹配结果

预期结果:
✅ 关键词搜索正常

---

【测试场景 3:会话 ID 筛选】
1. 在会话 ID 输入框输入 ID
2. 按回车触发搜索
3. 验证列表过滤出该会话的记录

预期结果:
✅ 会话 ID 筛选正常

---

【测试场景 4:执行模式筛选】
1. 在「调用模式」下拉选择模式(字典驱动)
2. 验证列表过滤出该模式的记录

预期结果:
✅ 模式筛选正常

---

【测试场景 5:状态筛选】
1. 在「状态」下拉选择状态(字典驱动)
2. 验证列表过滤出该状态的记录

预期结果:
✅ 状态筛选正常

---

【测试场景 6:日期范围筛选】
1. 在日期范围选择器选择起止时间
2. 验证列表过滤出该时间范围内的记录

预期结果:
✅ 日期范围筛选正常

---

【测试场景 7:统计弹窗】
1. 点击「统计」按钮
2. 验证统计弹窗打开
3. 验证显示:
   - 总调用次数
   - 平均延迟(ms)
   - 按模式分布(Tag 标签)
   - 按状态分布(Tag 标签)

预期结果:
✅ 统计弹窗正常
✅ 统计数据完整

---

【测试场景 8:从 Agent 管理链路跳转过滤】
1. 在 Agent 配置列表点击某 Agent 的「链路」按钮
2. 验证跳转到调用记录 Tab
3. 验证自动按该 Agent 过滤(显示过滤提示标签)
4. 点击「查看全部」按钮
5. 验证清除过滤条件,显示全部记录

预期结果:
✅ 跳转过滤正常
✅ 清除过滤正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 列表分页 | GET | /api/v1/agent-execution |
| 统计聚合 | GET | /api/v1/agent-execution/stats |
| 按会话查询 | GET | /api/v1/agent-execution/session/{session_id} |
| 单条详情 | GET | /api/v1/agent-execution/{execution_id} |

---

【问题诊断】
- 列表不加载 → 检查 listAgentExecutions() API
- 筛选不生效 → 检查参数传递(page/session_id/execution_mode/status/start_time/end_time)
- 统计不显示 → 检查 getAgentExecutionStats() API
- 链路跳转不生效 → 检查 inject('executionFilter') 注入
```

---

### 5.6 AGT-06 Agent 执行详情

**页面路径**: 调用记录列表 → 行点击打开详情抽屉  
**源码文件**: `src/views/admin/agent/AgentExecutionManagement.vue` (详情抽屉部分)  
**API 文件**: `src/api/agentExecution.ts`  
**权限标识**: `agent:execution:query`

#### 5.6.1 测试场景

#### 5.6.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 执行详情抽屉,执行完整的执行详情展示测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在调用记录列表点击某行记录
3. 等待详情抽屉加载完成

---

【测试场景 1:详情基本信息】
1. 验证详情描述列表显示:
   - execution_id(等宽字体)
   - 会话(#session_id + title)
   - 模式(Tag 标签)
   - Target(Tag 标签,目标类型+ID)
   - 状态(Tag 标签)
   - 开始时间
   - 完成时间
   - 延迟(ms)
   - 用户 ID

预期结果:
✅ 基本信息完整
✅ 格式化正确

---

【测试场景 2:DAG 拓扑图】
1. 验证拓扑图区域显示
2. 验证 ECharts 渲染正常(节点+边)
3. 验证节点颜色区分状态:
   - failed/error=红色
   - completed/success=绿色
   - running/pending=蓝色
   - TEAM_START=紫色
   - AGENT_START=青色
   - SYNTHESIS/NODE_END=橙色
4. 验证 DAG/Flow 切换按钮:
   - DAG 模式:按 layer 分层
   - Flow 模式:按时间顺序横向排布
5. 验证无拓扑时显示空状态

预期结果:
✅ ECharts 渲染正常
✅ 节点颜色正确
✅ DAG/Flow 切换正常

---

【测试场景 3:事件时间线】
1. 验证时间线显示(按时间排序)
2. 验证事件项显示:
   - event_type(Tag 标签,颜色区分)
   - role_name/agent_code/node_key/source
   - created_at(时间格式)
   - content(截断显示)
3. 验证事件颜色:
   - node_start=蓝色
   - node_end=绿色
   - node_error=红色
   - team_layer_start/done=紫色
   - agent_start/done=青色
   - hitl_request/resume=橙色
4. 验证无事件时显示空状态

预期结果:
✅ 时间线正常
✅ 事件颜色正确

---

【测试场景 4:人工介入 pauses 列表】
1. 验证人工介入区域显示(仅当有 pauses 时)
2. 验证介入项显示:
   - pause_type(Tag 标签,resolved=绿色/其他=橙色)
   - status
   - comment(审批意见)
   - payload(JSON 截断)
   - created_at/resolved_at
3. 验证无介入记录时不显示该区域

预期结果:
✅ 介入列表正常
✅ 条件显示正确

---

【测试场景 5:输入/输出/错误/Metadata/Trace 代码块】
1. 验证输入代码块显示(user_input)
2. 验证输出代码块显示(output)
3. 验证错误代码块显示(仅当有 error 时,红色背景)
4. 验证 Metadata 代码块显示(仅当有 metadata_json 时,JSON 格式化)
5. 验证 Trace 代码块显示(仅当有 trace 时,JSON 格式化)

预期结果:
✅ 代码块显示正常
✅ 条件显示正确

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 单条详情 | GET | /api/v1/agent-execution/{execution_id} |
| 调用链事件 | GET | /api/v1/agent-execution/{execution_id}/events |
| 归一化事件 | GET | /api/v1/agent-execution/{execution_id}/unified-events |

---

【问题诊断】
- 详情不加载 → 检查 getAgentExecutionDetail() API
- DAG 不渲染 → 检查 renderTopo() 函数/ECharts 初始化
- 时间线不显示 → 检查 sortedEvents 计算属性
- 介入列表不显示 → 检查 detail.hitl_pauses 数据
- 代码块为空 → 检查 detail 字段是否存在
```

---

### 5.7 AGT-07 团队列表

**页面路径**: 左侧菜单「Agent 管理」→「Agent 团队」  
**源码文件**: `src/views/admin/agent-team/TeamList.vue`  
**API 文件**: `src/api/agentTeam.ts`  
**权限标识**: `agent:team:create`, `agent:team:update`, `agent:team:delete`

#### 5.7.1 测试场景

#### 5.7.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开 Agent 团队列表页面,执行完整的团队管理测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在左侧菜单点击「Agent 管理」→「Agent 团队」
3. 等待页面加载完成

---

【测试场景 1:卡片网格加载】
1. 验证团队卡片网格正常加载
2. 验证卡片显示:
   - 团队名称(ApartmentOutlined 图标)
   - team_code(等宽字体)
   - description(截断 2 行)
   - category(Tag 标签)
   - member_count(TeamOutlined 图标)
3. 验证无团队时显示空状态

预期结果:
✅ 卡片网格完整
✅ 信息显示正确

---

【测试场景 2:创建团队】
1. 点击「创建团队」按钮
2. 验证创建弹窗打开
3. 填写表单:
   - team_code(可选,留空自动生成)
   - team_name(必填)
   - category(可选)
   - description(可选)
4. 提交验证创建成功
5. 验证卡片列表刷新

预期结果:
✅ 创建成功
✅ 列表刷新

---

【测试场景 3:编辑团队】
1. 点击某卡片的「编排」按钮进入编辑器
2. 返回后点击卡片进入编辑(或通过其他方式触发编辑)
3. 验证弹窗打开,数据正确回填
4. 修改 team_name
5. 提交验证更新成功

预期结果:
✅ 编辑回填正确
✅ 更新成功

---

【测试场景 4:启禁用 Switch】
1. 点击某卡片的 Switch
2. 验证 API 调用 updateTeam()
3. 验证状态更新成功提示
4. 验证失败时回滚 UI 状态

预期结果:
✅ Switch 切换正常
✅ 失败回滚正常

---

【测试场景 5:删除团队】
1. 点击某卡片的「删除」按钮
2. 验证浏览器 confirm 弹窗显示
3. 点击确认,验证删除成功
4. 验证卡片列表刷新

预期结果:
✅ 删除确认正常
✅ 删除成功

---

【测试场景 6:点击卡片进入编排】
1. 点击某团队卡片
2. 验证触发自定义事件 'open-agent-team-editor'
3. 验证进入团队编排器页面

预期结果:
✅ 卡片点击正常
✅ 进入编排器正常

---

【测试场景 7:team_name 必填校验】
1. 创建团队,team_name 留空
2. 提交验证显示警告提示

预期结果:
✅ 必填校验生效

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 列表 | GET | /api/v1/ai-team |
| 创建 | POST | /api/v1/ai-team |
| 更新 | PUT | /api/v1/ai-team/{team_id} |
| 删除 | DELETE | /api/v1/ai-team/{team_id} |

---

【问题诊断】
- 卡片不加载 → 检查 listTeams() API
- 创建失败 → 检查 team_name 必填校验
- Switch 切换失败 → 检查 updateTeam() API
- 删除失败 → 检查后端是否有依赖数据(成员/边/运行记录)
```

---

### 5.8 AGT-08 团队编排器

**页面路径**: Agent 团队列表 → 点击卡片进入编排  
**源码文件**: `src/views/admin/agent-team/TeamEditor.vue`  
**API 文件**: `src/api/agentTeam.ts`  
**权限标识**: `agent:team:update`

#### 5.8.1 测试场景

#### 5.8.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开团队编排器页面,执行完整的团队编排测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在团队列表点击某团队卡片进入编排器
3. 等待页面加载完成

---

【测试场景 1:团队详情加载】
1. 验证顶部条显示:
   - 返回按钮
   - 团队名称
   - team_code(Tag 标签)
   - 验证拓扑按钮
   - 保存编排按钮
2. 验证左侧成员面板加载成员列表
3. 验证右侧节点属性面板显示(未选择时显示空状态提示)

预期结果:
✅ 详情加载正常
✅ 面板显示正确

---

【测试场景 2:左侧成员面板】
1. 验证成员列表显示:
   - role_name(leader 显示 CrownOutlined 图标)
   - agent_code(Tag 标签)
   - node_key/model(副标题)
2. 验证搜索框过滤成员(按 role_name/agent_code)
3. 验证点击成员项选中(高亮显示)

预期结果:
✅ 成员列表正常
✅ 搜索过滤正常
✅ 选中高亮正常

---

【测试场景 3:添加成员弹窗】
1. 点击「添加成员」按钮
2. 验证添加成员弹窗打开
3. 填写表单:
   - node_key(必填)
   - role_name(必填)
   - agent_code(可选)
   - model(可选,字典驱动)
   - is_leader(Switch)
4. 提交验证:
   - node_key/role_name 为空时显示警告
   - node_key 重复时显示警告
   - 正常提交后成员列表刷新

预期结果:
✅ 弹窗打开正常
✅ 必填校验生效
✅ 重复校验生效

---

【测试场景 4:节点属性面板】
1. 点击左侧某成员项
2. 验证右侧属性面板显示:
   - node_key(禁用状态)
   - role_name(可编辑)
   - agent_code(可编辑)
   - model(Select,字典驱动)
   - is_leader(Switch)
   - system_prompt(Textarea)
3. 修改属性值

预期结果:
✅ 属性面板正常
✅ 字段可编辑

---

【测试场景 5:删除节点】
1. 选中某成员
2. 点击「删除节点」按钮
3. 验证成员从列表移除
4. 验证相关边也移除
5. 验证显示成功提示

预期结果:
✅ 删除正常
✅ 关联边移除

---

【测试场景 6:验证拓扑】
1. 点击「验证拓扑」按钮
2. 验证 API 调用 POST /api/v1/ai-team/{team_id}/validate
3. 验证显示成功/失败提示

预期结果:
✅ 验证正常

---

【测试场景 7:保存编排】
1. 添加/修改成员和属性
2. 点击「保存编排」按钮
3. 验证 API 调用 PUT /api/v1/ai-team/{team_id}/graph
4. 验证保存载荷包含 members + edges + layout
5. 验证节点必须绑定 agent_config_id,否则报错
6. 验证显示成功/失败提示

预期结果:
✅ 保存正常
✅ 载荷格式正确

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 团队详情 | GET | /api/v1/ai-team/{team_id} |
| 成员列表 | GET | /api/v1/ai-team/{team_id}/members |
| 边列表 | GET | /api/v1/ai-team/{team_id}/edges |
| 保存拓扑 | PUT | /api/v1/ai-team/{team_id}/graph |
| 验证拓扑 | POST | /api/v1/ai-team/{team_id}/validate |

---

【问题诊断】
- 详情不加载 → 检查 getTeam() API
- 成员不显示 → 检查 members 数据
- 保存失败 → 检查 agent_config_id 是否绑定
- 验证失败 → 检查 validate API 返回
```

---

### 5.9 AGT-09 团队对话与回放

**页面路径**: Agent 团队 → 对话/回放  
**源码文件**: `src/views/admin/agent-team/TeamConversation.vue`, `src/views/admin/agent-team/TeamReplay.vue`  
**API 文件**: `src/api/agentTeam.ts`  
**权限标识**: `agent:team:chat`, `agent:team:intervene`

#### 5.9.1 测试场景

#### 5.9.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开团队对话页面,执行完整的团队对话与回放测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 进入某团队的对话页面
3. 等待页面加载完成

---

【测试场景 1:对话页加载】
1. 验证顶栏显示:
   - 返回按钮
   - 团队名称
   - 运行状态 Tag(idle/running/done/error)
   - 回放按钮(仅当有 runId 时)
   - 清空按钮
2. 验证左侧拓扑面板显示
3. 验证右侧对话面板显示

预期结果:
✅ 页面加载正常

---

【测试场景 2:SSE 流式对话】
1. 在输入区输入消息
2. 点击「发送」按钮
3. 验证:
   - 用户消息气泡显示(右侧)
   - 流式文本累积显示(左侧)
   - 事件日志更新
   - 拓扑节点状态更新(idle/running/done)
   - 运行状态 Tag 变为 running
4. 等待流结束
5. 验证运行状态变为 done
6. 验证累积文本推为消息气泡

预期结果:
✅ SSE 流式正常
✅ 文本累积正常
✅ 状态更新正常

---

【测试场景 3:模型选择】
1. 验证模型选择下拉列表加载(从可用模型)
2. 选择模型
3. 发送消息验证模型透传给后端

预期结果:
✅ 模型选择正常

---

【测试场景 4:@提及提示】
1. 在输入框输入 "@"
2. 验证显示提及提示(成员列表)

预期结果:
✅ 提及提示正常

---

【测试场景 5:干预下拉菜单】
1. 点击「干预」按钮
2. 验证下拉菜单显示:
   - 暂停
   - 恢复
   - 取消
   - 注入消息
   - 跳过节点
3. 选择干预类型,验证干预弹窗打开

预期结果:
✅ 下拉菜单正常

---

【测试场景 6:干预弹窗】
1. 选择「跳过节点」
2. 验证弹窗显示目标节点选择(成员列表)
3. 选择节点,提交验证
4. 选择「注入消息」
5. 验证弹窗显示内容输入框
6. 输入内容,提交验证
7. 验证无 runId 时提交显示警告

预期结果:
✅ 干预弹窗正常
✅ 校验生效

---

【测试场景 7:清空对话】
1. 点击「清空」按钮
2. 验证消息列表清空
3. 验证流式文本清空
4. 验证事件日志清空
5. 验证拓扑节点清空
6. 验证运行状态变为 idle

预期结果:
✅ 清空正常

---

【测试场景 8:历史恢复】
1. 带 runId 进入对话页(刷新/从回放进入)
2. 验证调用 getRunMessages() 恢复历史消息
3. 验证消息列表正确显示
4. 验证运行状态变为 done

预期结果:
✅ 历史恢复正常

---

【测试场景 9:回放页】
1. 点击「回放」按钮
2. 验证进入回放页面
3. 验证时间线加载
4. 验证播放控制条:
   - 播放/暂停按钮
   - 进度条(Slider)
   - 步数显示
   - 上一步/下一步/重新开始按钮
5. 点击播放,验证自动播放(700ms 间隔)
6. 拖动进度条,验证跳转
7. 点击时间线项,验证跳转

预期结果:
✅ 回放页正常
✅ 播放控制正常

---

【测试场景 10:分支重跑】
1. 在回放页点击「分支重跑」按钮
2. 验证弹窗显示:
   - 起始节点选择(从时间线节点提取)
   - 覆盖输入(Textarea)
3. 选择节点,输入内容
4. 提交验证创建新 run
5. 验证跳转到新 run 的对话页

预期结果:
✅ 分支重跑正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 团队对话 | POST | /api/v1/ai-team/{team_id}/chat (SSE) |
| 提交干预 | POST | /api/v1/ai-team/{team_id}/runs/{run_id}/interventions |
| 列出干预 | GET | /api/v1/ai-team/{team_id}/runs/{run_id}/interventions |
| 重建消息 | GET | /api/v1/ai-team/{team_id}/runs/{run_id}/messages |
| 回放时间线 | GET | /api/v1/ai-team/run/{run_id}/timeline |
| 分支重跑 | POST | /api/v1/ai-team/run/{run_id}/rerun |

---

【问题诊断】
- SSE 不流式 → 检查 fetch POST /api/v1/ai-team/{team_id}/chat
- 消息不显示 → 检查 pushMessage() 去重逻辑
- 拓扑不更新 → 检查 upsertNode() 函数
- 干预提交失败 → 检查 createIntervention() API
- 回放不播放 → 检查 timer 定时器逻辑
- 分支重跑失败 → 检查 rerunBranch() API
```

---

### 5.10 AGT-10 定时调度管理

**页面路径**: 智能助手 → 异步任务 → 「调度任务」Tab  
**源码文件**: `src/views/assistant/ScheduledTaskManage.vue`  
**API 文件**: `src/api/aiAgent.ts`  
**权限标识**: `agent:scheduled:create`, `agent:scheduled:update`, `agent:scheduled:delete`

#### 5.10.1 测试场景

#### 5.10.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8000

打开定时调度管理页面,执行完整的调度任务 CRUD 测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 进入「智能助手」→「异步任务」→ 切换到「调度任务」Tab
3. 等待页面加载完成

---

【测试场景 1:调度列表加载与基础显示】
1. 验证调度任务列表正常加载
2. 检查列:任务名称/执行类型/调度规则/状态/下次执行/最近执行/触发失败/操作
3. 验证分页功能正常
4. 验证执行类型列使用 Tag 标签(deep_research/agent/team/skill 颜色区分)
5. 验证状态列使用 Badge 标签(enabled=蓝色/paused=灰色)

预期结果:
✅ 表格 8 列完整
✅ Tag/Badge 颜色正确
✅ 分页正常

---

【测试场景 2:状态筛选】
1. 在「全部状态」下拉选择状态(enabled/paused)
2. 验证列表过滤出该状态的记录
3. 清空筛选,验证列表恢复

预期结果:
✅ 状态筛选正常
✅ 清空筛选正常

---

【测试场景 3:新建调度任务 — deep_research 模式】
1. 点击「新建调度任务」按钮
2. 验证弹窗打开,标题为「新建调度任务」
3. 填写表单:
   - 任务名称: "每日深度研究"
   - 执行类型: deep_research
   - 研究主题: "分析近期低空经济政策动向"
   - 调度类型: cron
   - Cron 表达式: "0 9 * * *"
4. 验证表单校验:
   - 任务名称为空时显示警告
   - 研究主题为空时显示警告
   - Cron 表达式为空时显示警告
5. 提交验证创建成功
6. 验证列表刷新

预期结果:
✅ 弹窗打开正常
✅ 表单校验生效
✅ 创建成功

---

【测试场景 4:新建调度任务 — agent 模式】
1. 点击「新建调度任务」按钮
2. 填写表单:
   - 任务名称: "Agent 定时任务"
   - 执行类型: agent
   - 选择智能体(从下拉列表搜索选择)
   - 执行指令: "总结昨日风险事件"
   - 调度类型: interval
   - 间隔: 3600 秒
3. 验证:
   - 选择 agent 模式后显示「选择智能体」下拉
   - 智能体列表加载正常
   - 未选择智能体时提交显示警告
4. 提交验证创建成功

预期结果:
✅ agent 模式正常
✅ 智能体选择正常
✅ 创建成功

---

【测试场景 5:新建调度任务 — skill 模式】
1. 点击「新建调度任务」按钮
2. 填写表单:
   - 任务名称: "技能定时任务"
   - 执行类型: skill
   - 选择技能包(从下拉列表搜索选择)
   - 选择技能脚本(级联选择)
   - 执行指令: "执行数据同步"
   - 调度类型: once
   - 执行时间: 选择未来某个时间点
3. 验证:
   - 选择 skill 模式后显示「技能包」和「技能脚本」级联选择
   - 技能包列表加载正常
   - 选择技能包后脚本列表刷新
   - 未选择技能包/脚本时提交显示警告
   - once 模式显示「执行时间」日期选择器
4. 提交验证创建成功

预期结果:
✅ skill 模式正常
✅ 级联选择正常
✅ 创建成功

---

【测试场景 6:编辑调度任务】
1. 点击某调度任务的「编辑」按钮
2. 验证弹窗打开,数据正确回填:
   - 任务名称
   - 执行类型(禁用状态,不可切换)
   - 研究主题/执行指令
   - 调度类型
   - Cron 表达式/间隔/执行时间
3. 修改任务名称
4. 提交验证更新成功
5. 验证列表刷新

预期结果:
✅ 编辑回填正确
✅ 执行类型禁用
✅ 更新成功

---

【测试场景 7:暂停/恢复调度】
1. 点击某启用中调度的「暂停」按钮
2. 验证 API 调用 POST /api/v1/ai-agent/agent-scheduled-tasks/{id}/pause
3. 验证状态变为「已暂停」
4. 验证显示「已暂停调度」成功提示
5. 点击某已暂停调度的「恢复」按钮
6. 验证 API 调用 POST /api/v1/ai-agent/agent-scheduled-tasks/{id}/resume
7. 验证状态变为「启用中」
8. 验证显示「已恢复调度」成功提示

预期结果:
✅ 暂停成功
✅ 恢复成功
✅ 状态更新正确

---

【测试场景 8:立即执行】
1. 点击某调度任务的「执行」按钮
2. 验证 API 调用 POST /api/v1/ai-agent/agent-scheduled-tasks/{id}/run-now
3. 验证显示「已触发执行,请在异步任务 Tab 查看进度」成功提示
4. 验证调度状态不变(仍为启用中)

预期结果:
✅ 立即执行触发成功
✅ 提示信息正确

---

【测试场景 9:删除调度任务】
1. 点击某调度任务的「删除」按钮
2. 验证 Popconfirm 确认弹窗显示
3. 点击确认,验证 API 调用 DELETE /api/v1/ai-agent/agent-scheduled-tasks/{id}
4. 验证显示「已删除」成功提示
5. 验证列表刷新,调度任务消失

预期结果:
✅ 删除确认正常
✅ 删除成功后列表刷新

---

【测试场景 10:调度类型切换验证】
1. 新建调度任务,选择 cron 调度类型
2. 验证显示「Cron 表达式」输入框
3. 切换为 interval 调度类型
4. 验证显示「间隔(秒)」输入框(最小 60)
5. 切换为 once 调度类型
6. 验证显示「执行时间」日期选择器
7. 验证不同调度类型的表单字段正确切换

预期结果:
✅ 调度类型切换正常
✅ 表单字段正确显示

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 调度列表 | GET | /api/v1/ai-agent/agent-scheduled-tasks |
| 调度详情 | GET | /api/v1/ai-agent/agent-scheduled-tasks/{id} |
| 创建调度 | POST | /api/v1/ai-agent/agent-scheduled-tasks |
| 更新调度 | PUT | /api/v1/ai-agent/agent-scheduled-tasks/{id} |
| 暂停调度 | POST | /api/v1/ai-agent/agent-scheduled-tasks/{id}/pause |
| 恢复调度 | POST | /api/v1/ai-agent/agent-scheduled-tasks/{id}/resume |
| 立即执行 | POST | /api/v1/ai-agent/agent-scheduled-tasks/{id}/run-now |
| 删除调度 | DELETE | /api/v1/ai-agent/agent-scheduled-tasks/{id} |

---

【问题诊断】
- 列表不加载 → 检查 listScheduledTasks() API
- 创建失败 → 检查表单校验(task_name/prompt/schedule_type)
- 智能体列表不显示 → 检查 getAgentRegistry() API
- 技能包列表不显示 → 检查 getSkills() API
- Cron 表达式错误 → 检查后端 cron 校验逻辑
- 暂停/恢复失败 → 检查 pauseScheduledTask()/resumeScheduledTask() API
```

---

## 6.测试结果报告模板

```markdown
# Agent 服务测试报告

**测试日期**: YYYY-MM-DD  
**测试人员**: AI Agent (gstack /qa)  
**测试环境**: http://localhost:5173  
**Agent 服务**: http://localhost:8000

## 测试摘要

| 指标 | 值 |
|------|------|
| 总用例数 | N |
| 通过 | X |
| 失败 | Y |
| 跳过 | Z |
| 通过率 | X/N% |
| 执行时长 | M 分钟 |

## 结果汇总

| 模块 | 用例数 | 通过 | 失败 | 跳过 | 通过率 |
|------|--------|------|------|------|--------|
| AGT-01 Agent 配置列表 | 10 | 10 | 0 | 0 | 100% |
| AGT-02 Agent 创建/编辑 | 8 | 8 | 0 | 0 | 100% |
| AGT-03 Agent 详情抽屉 | 6 | 6 | 0 | 0 | 100% |
| AGT-04 Agent 技能规则 | 6 | 6 | 0 | 0 | 100% |
| AGT-05 Agent 执行记录 | 8 | 8 | 0 | 0 | 100% |
| AGT-06 Agent 执行详情 | 5 | 5 | 0 | 0 | 100% |
| AGT-07 团队列表 | 7 | 7 | 0 | 0 | 100% |
| AGT-08 团队编排器 | 7 | 7 | 0 | 0 | 100% |
| AGT-09 团队对话与回放 | 10 | 9 | 1 | 0 | 90% |
| AGT-10 定时调度管理 | 10 | 10 | 0 | 0 | 100% |
| **合计** | **N** | **X** | **Y** | **Z** | **X/N%** |

## 失败用例详情

### AGT-09 团队对话与回放 — 测试场景 2:SSE 流式对话

- **现象**: 发送消息后无流式文本显示
- **控制台错误**: `Failed to fetch`
- **截图**: [.gstack/qa-reports/screenshots/issue-001.png](.gstack/qa-reports/screenshots/issue-001.png)
- **定位**: `TeamConversation.vue` fetch POST /api/v1/ai-team/{team_id}/chat 连接失败
- **修复建议**: 检查后端 SSE 接口是否正常,验证 Authorization header
- **修复文件**: `src/views/admin/agent-team/TeamConversation.vue`
- **状态**: 已修复

## 建议

1. **高优先级**:确保 SSE 流式对话稳定性,影响核心功能
2. **中优先级**:增强 DAG 拓扑图的交互体验(缩放/拖拽)
3. **低优先级**:优化团队编排器的用户体验
4. **测试补充**:建议增加并发对话、长时间运行等边界测试
```

---

## 7.模块开发对照与补全清单

本章节对照 Agent/Agent-Team 模块的实现状态与补全建议。

### Agent 模块补全对照表

| 模块 | 前端路径 | 后端路由 | 前端状态 | 后端状态 | 补全建议 |
|------|---------|---------|---------|---------|---------|
| Agent 配置列表 | `views/admin/agent/AgentManagement.vue` | `routers/agent/agent_config.py` | ✅ 完整 | ✅ | 对齐:无明显差距 |
| Agent 创建/编辑 | `views/admin/agent/components/AgentFormModal.vue` | `routers/agent/agent_config.py` | ✅ 完整 | ✅ | 已完成:系统模型/自定义切换 + MCP 自动安装 |
| Agent 详情抽屉 | `views/admin/agent/components/AgentDetailDrawer.vue` | `routers/agent/agent_config.py` | ✅ 完整 | ✅ | 已完成:基本信息 + 可视化配置 + 监控统计 + 链路追踪 |
| Agent 技能规则 | `views/admin/agent/AgentManagement.vue` (规则抽屉) | `routers/agent/agent_config.py` + `skillRule.ts` | ✅ 完整 | ✅ | 已完成:规则 CRUD + 启禁用 + 优先级 |
| Agent 执行记录 | `views/admin/agent/AgentExecutionManagement.vue` | `routers/agent/agent_execution.py` | ✅ 完整 | ✅ | 已完成:多条件筛选 + 统计 + 链路跳转 |
| Agent 执行详情 | `views/admin/agent/AgentExecutionManagement.vue` (详情抽屉) | `routers/agent/agent_execution.py` | ✅ 完整 | ✅ | 已完成:DAG 拓扑 + 时间线 + 人工介入 |
| 团队列表 | `views/admin/agent-team/TeamList.vue` | `routers/agent/agent_team.py` | ✅ 完整 | ✅ | 已完成:卡片网格 + 创建/编辑 + 启禁用 |
| 团队编排器 | `views/admin/agent-team/TeamEditor.vue` | `routers/agent/agent_team.py` | ✅ 完整 | ✅ | 已完成:成员管理 + 节点属性 + 拓扑保存 |
| 团队对话 | `views/admin/agent-team/TeamConversation.vue` | `routers/agent/agent_team.py` | ✅ 完整 | ✅ | 已完成:SSE 流式 + 干预 + 历史恢复 |
| 团队回放 | `views/admin/agent-team/TeamReplay.vue` | `routers/agent/agent_team.py` | ✅ 完整 | ✅ | 已完成:时间线 + 播放控制 + 分支重跑 |
| 统一聊天流 | `api/aiAgent.ts` | `routers/agent/agent.py` | ✅ 完整 | ⚠️ TODO | 后端旧版接口需重构 |
| 异步任务 | `api/aiAgent.ts` | `routers/agent/agent.py` | ✅ 完整 | ⚠️ TODO | 后端异步任务接口需完善 |
| 定时调度 | `api/aiAgent.ts` | `routers/agent/agent_scheduled_task.py` | ✅ 完整 | ✅ | 已完成:CRUD + 暂停/恢复/立即执行 |
| 定时调度管理 | `views/assistant/ScheduledTaskManage.vue` | `routers/agent/agent_scheduled_task.py` | ✅ 完整 | ✅ | 已完成:多模式调度 + 级联选择 + 状态管理 |

---

## 8.文档版本

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| 1.0.0 | 2026-06-14 | 初始版本,覆盖 Agent/Agent-Team 全部 10 个模块 77 个测试场景 | AI Agent |

| 项目 | 值 |
|------|------|
| 适用服务 | Agent/Agent-Team(:8000) |
| 前端入口 | http://localhost:5173 |
| 默认账号 | admin / admin123 |
| 测试 Skill | `/qa`, `/qa-only`, `/open-gstack-browser`, MCP Playwright |
