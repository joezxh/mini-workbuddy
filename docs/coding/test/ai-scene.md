# AI 服务 — 端到端浏览器自动化测试 Skill

> 本文档为 AI 浏览器测试 Agent 提供完整的 AI(智能服务)管理模块测试提示词。
> 使用 `/browser` 启动浏览器自动化测试,或使用 MCP Playwright 执行测试。
> 适用于 gstack `/qa` 和 `/qa-only` Skill,通过 `/open-gstack-browser` 导入认证 Cookie 后执行端到端测试。
> 文档同时包含问题自动定位与修复建议机制,支持端到端回归测试。

---

## 目录

- [1.测试前置条件](#测试前置条件)
- [2.全局测试策略](#全局测试策略)
- [3.Skill 调用方式](#skill-调用方式)
- [4.问题发现与自动修复流程](#问题发现与自动修复流程)
- [5.AI 服务测试模块](#ai-服务测试模块)
  - [AI-01 API Key 管理](#ai-01-api-key-管理)
  - [AI-02 关联模型管理（ChatModel）](#ai-02-关联模型管理chatmodel)
  - [AI-03 模型测试](#ai-03-模型测试)
  - [AI-04 MCP 服务管理 — 我的 MCP](#ai-04-mcp-服务管理--我的-mcp)
  - [AI-05 MCP 服务管理 — MCP 广场](#ai-05-mcp-服务管理--mcp-广场)
  - [AI-06 技能管理 — 技能包](#ai-06-技能管理--技能包)
  - [AI-07 技能管理 — 脚本与规则](#ai-07-技能管理--脚本与规则)
  - [AI-08 技能管理 — SKILL.md 与进化配置](#ai-08-技能管理--skillmd-与进化配置)
  - [AI-09 技能管理 — 技能仓库](#ai-09-技能管理--技能仓库)
  - [AI-10 工具管理 — 工具列表](#ai-10-工具管理--工具列表)
  - [AI-11 工具管理 — 工具分组与成员](#ai-11-工具管理--工具分组与成员)
  - [AI-12 联网搜索管理 — 配置管理](#ai-12-联网搜索管理--配置管理)
  - [AI-13 联网搜索管理 — 配额/健康/日志](#ai-13-联网搜索管理--配额健康日志)
  - [AI-14 工具调用策略管理](#ai-14-工具调用策略管理)
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
| AI 服务路由前缀 | `/api/v1/admin/ai` |
| 管理员账号 | `admin` |
| 管理员密码 | `admin123` |

### 1.2 服务依赖检查

测试前需确认以下服务已启动:

1. **FastAPI 后端**(:8000) — 核心 API 服务
2. **Vue 前端**(:5173) — Vite 开发服务器
3. **PostgreSQL** — 数据库
4. **Redis** — 缓存（工具缓存刷新依赖）

### 1.3 浏览器环境要求

- 浏览器:Chromium / Chrome(headless 模式或带 UI 模式均可)
- Cookie 导入:通过 `/open-gstack-browser` 导入已登录 Cookie,避免重复登录
- 如需手动登录:账号 `admin`,密码 `admin123`

---

## 2.全局测试策略

### 2.1 模块列表:

| 模块 ID | 模块名称 | 测试场景数 | 说明 |
|---------|---------|-----------|------|
| AI-01 | API Key 管理 | 8 | CRUD + 搜索 + 状态切换 |
| AI-02 | 关联模型管理（ChatModel） | 8 | 子表 CRUD + 设为默认 |
| AI-03 | 模型测试 | 5 | 流式测试 + 多模型对比 |
| AI-04 | MCP 服务管理 — 我的 MCP | 7 | API Key CRUD + 连接测试 + Client 管理 |
| AI-05 | MCP 服务管理 — MCP 广场 | 8 | 模板 CRUD + 安装/卸载 + 软删除/强制删除 |
| AI-06 | 技能管理 — 技能包 | 8 | 包 CRUD + 导入/导出 + 启用/禁用 |
| AI-07 | 技能管理 — 脚本与规则 | 8 | 脚本 CRUD + 规则 CRUD + Switch 切换 |
| AI-08 | 技能管理 — SKILL.md 与进化 | 5 | Markdown 编辑保存 + 进化配置 |
| AI-09 | 技能管理 — 技能仓库 | 4 | 仓库浏览 + 添加 Repo + 安装 |
| AI-10 | 工具管理 — 工具列表 | 8 | CRUD + 搜索 + 状态 Switch + 缓存刷新 + 测试 |
| AI-11 | 工具管理 — 工具分组与成员 | 7 | 分组 CRUD + 成员添加/移除 |
| AI-12 | 联网搜索管理 — 配置管理 | 7 | CRUD + 搜索 + 状态切换 + 测试搜索 |
| AI-13 | 联网搜索管理 — 配额/健康/日志 | 5 | 配额用量 + 健康检查 + 搜索日志 |
| AI-14 | 工具调用策略管理 | 11 | 策略 CRUD + 表单验证 + 数值边界 |
| **合计** | **14 个模块** | **99 个场景** | **~7h 测试时间** |

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
/qa-only --tier exhaustive --scope "AI服务-API Key管理"
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
  → 修复后自动重新执行失败的测试用例
```

### 4.2 常见错误自动匹配表

| 浏览器现象 | 可能原因 | 检查文件 |
|-----------|---------|---------|
| 白屏 | 路由组件未注册 / import 路径错误 | `router/`, `views/admin/ai/` |
| 表格无数据 | API 返回错误 / 后端未启动 | `request.ts`, Network 面板 |
| 弹窗打不开 | `v-model:open` / `v-model:visible` 绑定问题 | 对应 FormModal.vue |
| 表单不回填 | watch 未监听 / props 延迟 | FormModal.vue 的 watch |
| Tag 不显示 | 字典类型未注册 / 值为空 | `useAdminDict.ts`, 后端字典表 |
| 401 错误 | Token 过期 / 刷新 Token 逻辑失败 | `request.ts`, `auth.ts` |
| 删除失败 | 外键约束 / 关联数据未清理 | 后端 Service |
| 分页异常 | page/pageSize 参数不对 | API 请求参数 |
| 流式输出中断 | SSE 连接被代理截断 | nginx 配置, `fetchModelTestStream` |
| Switch 不生效 | API 字段名不匹配(status vs is_active) | 前端 API 调用参数 |

---

## 5.AI 服务测试模块

---

### 5.1 AI-01 API Key 管理

**页面路径**: 管理后台 → AI 管理 → API Key 管理  
**源码文件**: `frontend/src/views/admin/ai/apikey/ApiKeyManagement.vue`  
**API 文件**: `frontend/src/api/ai-apikey.ts`  
**后端路由**: `backend/app/routers/ai/ai_api_key.py`  
**基础路径**: `/api/v1/admin/ai/api-key`

#### 5.1.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-01-01 | 列表加载与基础显示 | 打开页面,验证表格列完整 | 7 列完整渲染:名称、平台、API Key、URL、状态、创建时间、操作 |
| AI-01-02 | 搜索 — 名称搜索 | 输入关键词搜索 | 列表过滤出匹配名称的结果 |
| AI-01-03 | 搜索 — 平台筛选 | 选择平台下拉项 | 列表按平台过滤 |
| AI-01-04 | 搜索 — 状态筛选 | 选择启用/禁用 | 列表按状态过滤 |
| AI-01-05 | 搜索 — 重置 | 点击重置按钮 | 条件清空,列表恢复 |
| AI-01-06 | 新增 API Key | 点击新增 → 填写表单 → 提交 | 弹窗表单完整,提交成功列表刷新 |
| AI-01-07 | 编辑 API Key | 点击编辑 → 验证回填 → 修改 → 提交 | 数据正确回填,更新生效 |
| AI-01-08 | 状态切换 | 点击启用/禁用按钮 | 状态切换成功,message 提示正确 |
| AI-01-09 | 删除 API Key | 点击删除 → 确认弹窗 → 确认 | 删除成功,列表刷新 |
| AI-01-10 | 打开关联模型 | 点击「模型」按钮 | ChatModelList 弹窗正确打开 |
| AI-01-11 | 分页切换 | 切换页码/每页条数 | 数据正确翻页 |

#### 5.1.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端：http://localhost:8000

打开 API Key 管理页面,执行完整的 CRUD 测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 导航到 AI 管理 → API Key 管理
3. 等待页面加载完成

---

【测试场景 1:列表加载与基础显示】
1. 验证表格正常加载,loading 消失
2. 检查列:名称、平台、API Key、URL、状态、创建时间、操作
3. 验证 API Key 列脱敏显示(前12位 + ***)
4. 验证平台列使用 DictTag 标签(字典:AI_PLATFORM)
5. 验证状态列使用 Tag(启用=绿色,禁用=红色)

预期结果:
✅ 表格7列完整
✅ API Key 脱敏显示
✅ 平台/状态 Tag 颜色正确

---

【测试场景 2:搜索功能】
1. 在名称搜索框输入关键词,触发搜索
2. 验证列表过滤出匹配名称的结果
3. 选择平台下拉筛选,验证列表按平台过滤
4. 选择状态筛选(启用/禁用),验证列表过滤
5. 点击「重置」按钮,验证所有条件清空,列表恢复

预期结果:
✅ 名称搜索过滤正确
✅ 平台筛选正确
✅ 状态筛选正确
✅ 重置清空所有条件

---

【测试场景 3:新增 API Key】
1. 点击顶部「新增 API Key」按钮
2. 验证 ApiKeyFormModal 弹窗弹出,标题为新增
3. 验证表单字段:
   - 名称(必填)
   - 平台(必填,下拉选择,字典驱动)
   - API Key(必填,密码输入框)
   - URL(可选)
   - AppId(可选)
   - 排序(数字,默认0)
   - 状态(Switch,默认启用)
4. 不填写名称直接提交,验证必填校验提示
5. 填写完整信息后提交:
   - API POST /api/v1/admin/ai/api-key/create
   - 显示「创建成功」
   - 弹窗关闭,列表刷新

预期结果:
✅ 新增弹窗表单字段完整
✅ 必填校验生效
✅ 提交成功,列表刷新

---

【测试场景 4:编辑 API Key】
1. 点击刚创建的 API Key 的「编辑」按钮
2. 验证弹窗弹出,标题为编辑
3. 验证所有字段正确回填(名称、平台、URL、AppId、排序、状态)
4. 修改名称,提交
5. 验证列表中名称已更新

预期结果:
✅ 编辑弹窗正确回填
✅ 修改提交后数据更新

---

【测试场景 5:状态切换】
1. 找到一个启用状态的 API Key
2. 点击「禁用」按钮
3. 验证 API 调用 PUT /api/v1/admin/ai/api-key/update
4. 验证 message 提示「已禁用」
5. 验证列表刷新,状态 Tag 变为红色
6. 再次点击「启用」,验证状态恢复

预期结果:
✅ 状态切换成功
✅ Tag 颜色正确变化
✅ message 提示正确

---

【测试场景 6:删除 API Key】
1. 点击 API Key 的「删除」按钮
2. 验证 Popconfirm 确认弹窗出现
3. 点击取消,验证不执行删除
4. 再次点击删除,点击确认
5. 验证 API DELETE /api/v1/admin/ai/api-key/delete
6. 验证删除成功 message,列表刷新

预期结果:
✅ 确认弹窗正常
✅ 取消不执行删除
✅ 确认删除成功

---

【测试场景 7:打开关联模型子表】
1. 点击某条 API Key 操作列的「模型」按钮(RobotOutlined)
2. 验证 ChatModelList 弹窗打开
3. 验证弹窗标题包含 API Key 名称
4. 验证模型列表加载

预期结果:
✅ 模型子表弹窗正确打开
✅ 标题显示关联名称

---

【测试场景 8:分页功能】
1. 验证分页组件显示(总条数、当前页、每页条数)
2. 切换每页条数(15→30),验证列表刷新
3. 切换到第2页,验证数据正确

预期结果:
✅ 分页功能正常
✅ 每页条数切换正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 分页列表 | GET | /api/v1/admin/ai/api-key/page |
| 详情 | GET | /api/v1/admin/ai/api-key/{id} |
| 创建 | POST | /api/v1/admin/ai/api-key/create |
| 更新 | POST | /api/v1/admin/ai/api-key/update |
| 删除 | DELETE | /api/v1/admin/ai/api-key/delete |
| 简易列表 | GET | /api/v1/admin/ai/api-key/simple-list |

---

【问题诊断】
- 列表不加载 → 检查 getApiKeyPage() 是否成功
- 编辑时数据不回填 → 检查 ApiKeyFormModal watch 逻辑
- 平台 Tag 不显示 → 检查 DictType.AI_PLATFORM 字典是否注册
- 删除失败 → 检查是否有关联 ChatModel 未清理
```

---

### 5.2 AI-02 关联模型管理（ChatModel）

**页面路径**: API Key 管理 → 点击「模型」按钮打开子表  
**源码文件**: `frontend/src/views/admin/ai/apikey/components/ChatModelList.vue`, `ChatModelFormModal.vue`  
**API 文件**: `frontend/src/api/ai-apikey.ts`  
**后端路由**: `backend/app/routers/ai/ai_api_key.py`  
**基础路径**: `/api/v1/admin/ai/api-key/chat-model`

#### 5.2.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-02-01 | 模型列表加载 | 打开模型子表,验证表格列 | 8 列完整:名称、模型ID、类型、默认、温度、最大Token、状态、操作 |
| AI-02-02 | 模型搜索 | 输入模型名称搜索 | 列表过滤 |
| AI-02-03 | 新增模型 | 点击新增 → 填写表单 → 提交 | 表单字段完整,提交成功 |
| AI-02-04 | 编辑模型 | 点击编辑 → 验证回填 → 修改 → 提交 | 数据正确回填,更新生效 |
| AI-02-05 | 设为默认模型 | 点击星标/设为默认按钮 | 设为成功,星标高亮 |
| AI-02-06 | 模型状态切换 | 点击启用/禁用 | 状态切换成功 |
| AI-02-07 | 删除模型 | 点击删除 → 确认 | 删除成功 |
| AI-02-08 | 模型测试入口 | 点击「测试模型」按钮 | ModelTestModal 弹窗打开 |

#### 5.2.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在 API Key 管理页面,点击某条 API Key 的「模型」按钮,执行关联模型的完整测试。

【前置操作】
1. 登录系统,进入 API Key 管理
2. 点击一条已有 API Key 的「模型」按钮
3. 等待 ChatModelList 弹窗加载

---

【测试场景 1:模型列表加载与显示】
1. 验证模型表格正常加载,loading 消失
2. 检查列:名称、模型ID、类型、默认、温度、最大Token、状态、操作
3. 验证默认模型使用星标图标(StarFilled=金色,StarOutlined=灰色)
4. 验证状态 Tag 颜色(启用=绿色,禁用=红色)

预期结果:
✅ 表格8列完整
✅ 星标图标正确
✅ 状态 Tag 颜色正确

---

【测试场景 2:新增模型】
1. 点击「新增模型」按钮
2. 验证 ChatModelFormModal 弹窗弹出
3. 验证表单字段:
   - 模型名称(必填) + 模型ID(必填) — 同一行
   - 模型代码 + 模型类型(字典下拉) — 同一行
   - ── 生成参数 ──
   - Temperature(0-2,步长0.1) + MaxTokens(1-128000)
   - TopP(0-1) + TopK(≥1)
   - Seed + MaxContexts
   - MaxTurns + Dimensions
   - ── 高级 ──
   - Retry(0-10) + Timeout(1-300秒)
   - StreamTimeout(1-120秒) + 排序
   - 启用思考(Switch) + 启用搜索(Switch)
   - 状态(Switch,默认启用)
4. 不填写必填项直接提交,验证校验提示
5. 填写完整信息提交:
   - API POST /api/v1/admin/ai/api-key/chat-model/create
   - 成功提示,弹窗关闭,列表刷新

预期结果:
✅ 表单字段完整(含分区标题)
✅ 必填校验生效
✅ 提交成功

---

【测试场景 3:编辑模型 — 数据回填】
1. 点击模型的「编辑」按钮
2. 验证弹窗标题变为「编辑模型」
3. 验证所有字段正确回填:
   - 名称、模型ID、代码、类型
   - Temperature、MaxTokens、TopP、TopK
   - Seed、MaxContexts、MaxTurns、Dimensions
   - Retry、Timeout、StreamTimeout、排序
   - 启用思考、启用搜索、状态
4. 修改 Temperature 值,提交
5. 验证更新成功

预期结果:
✅ 所有字段正确回填
✅ 修改后更新生效

---

【测试场景 4:设为默认模型】
1. 找到一个非默认模型
2. 点击操作列的「设为默认」按钮(或点击灰色星标)
3. 验证 API POST /api/v1/admin/ai/api-key/chat-model/set-default
4. 验证成功提示
5. 验证该模型星标变为金色(StarFilled)
6. 验证原默认模型星标变为灰色

预期结果:
✅ 设为默认成功
✅ 星标状态正确切换

---

【测试场景 5:模型状态切换】
1. 点击模型的「启用/禁用」按钮
2. 验证 API 调用成功
3. 验证列表刷新,状态 Tag 变化

预期结果:
✅ 状态切换成功

---

【测试场景 6:删除模型】
1. 点击模型的「删除」按钮
2. 验证 Popconfirm 确认弹窗
3. 确认删除,验证成功提示
4. 验证列表刷新

预期结果:
✅ 删除确认正常
✅ 删除成功

---

【测试场景 7:打开模型测试弹窗】
1. 点击顶部「测试模型」按钮
2. 验证 ModelTestModal 弹窗打开
3. 验证所有模型默认勾选

预期结果:
✅ 测试弹窗正确打开

---

【测试场景 8:模型搜索】
1. 在搜索框输入模型名称关键词
2. 验证列表过滤
3. 清空搜索,验证列表恢复

预期结果:
✅ 搜索过滤正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 模型分页 | GET | /api/v1/admin/ai/api-key/chat-model/page |
| 模型详情 | GET | /api/v1/admin/ai/api-key/chat-model/{id} |
| 创建模型 | POST | /api/v1/admin/ai/api-key/chat-model/create |
| 更新模型 | POST | /api/v1/admin/ai/api-key/chat-model/update |
| 删除模型 | DELETE | /api/v1/admin/ai/api-key/chat-model/delete |
| 设为默认 | POST | /api/v1/admin/ai/api-key/chat-model/set-default |

---

【问题诊断】
- 模型列表不加载 → 检查 getChatModelPage() 参数 keyId 是否正确
- 编辑回填缺失字段 → 检查 ChatModelFormModal watch 中字段映射
- 设为默认不生效 → 检查 setChatModelDefault API 参数
- 模型类型下拉为空 → 检查 useDictionary().loadModelTypes() 字典加载
```

---

### 5.3 AI-03 模型测试

**页面路径**: ChatModelList 弹窗 → 点击「测试模型」按钮  
**源码文件**: `frontend/src/views/admin/ai/apikey/components/ModelTestModal.vue`  
**API 文件**: `frontend/src/api/ai-apikey.ts`（fetchModelTestStream）  
**后端路由**: `backend/app/routers/ai/ai_api_key.py`  
**测试端点**: `POST /api/v1/admin/ai/api-key/chat-model/test`（SSE 流式）

#### 5.3.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-03-01 | 测试弹窗初始化 | 打开测试弹窗 | 模型全选,prompt 为空,按钮禁用 |
| AI-03-02 | 单模型文本测试 | 选1个模型,输入 prompt,开始测试 | 流式输出结果,显示耗时和 token |
| AI-03-03 | 多模型对比测试 | 选2+模型,输入 prompt | 多列并排显示结果 |
| AI-03-04 | 停止测试 | 测试运行中点击停止 | 流中断,显示已接收内容 |
| AI-03-05 | 清除结果 | 点击清除结果按钮 | 结果区域清空 |

#### 5.3.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在模型列表中打开测试弹窗,执行模型测试功能验证。

【前置操作】
1. 进入 API Key → 模型列表 → 点击「测试模型」
2. 等待 ModelTestModal 弹窗加载

---

【测试场景 1:测试弹窗初始化】
1. 验证弹窗标题「模型测试」
2. 验证模型选择区:所有模型默认勾选(CheckboxGroup)
3. 验证每个模型显示:名称 + 模型ID + 类型Tag
4. 验证已选数量 Tag 显示正确
5. 验证 prompt 输入框为空
6. 验证「开始测试」按钮禁用状态(因为 prompt 为空)

预期结果:
✅ 弹窗初始化正确
✅ 模型全选
✅ 按钮状态正确

---

【测试场景 2:单模型文本测试】
1. 取消部分模型勾选,只保留1个 Chat 模型
2. 在 prompt 输入框输入:"你好,请用一句话介绍自己"
3. 验证「开始测试」按钮变为可用
4. 点击「开始测试」
5. 验证:
   - 按钮显示 loading 状态
   - 结果区出现卡片,状态为"运行中"
   - 文字流式输出(光标闪烁 ▌)
6. 等待完成:
   - 状态变为"已完成"(绿色 Tag)
   - 显示耗时(ms)和 token 数
7. 如果有 reasoning(思考过程),验证思考区块显示

预期结果:
✅ 流式输出正常
✅ 完成后状态/耗时/token 正确

---

【测试场景 3:多模型对比测试】
1. 勾选2个或以上模型
2. 输入 prompt
3. 点击开始测试
4. 验证结果区使用网格布局多列并排显示
5. 验证每个模型独立显示结果卡片
6. 验证各模型独立计算耗时和 token

预期结果:
✅ 多模型并排显示
✅ 各自独立统计

---

【测试场景 4:高级选项 — System Prompt】
1. 展开「高级选项」折叠面板
2. 输入 System Prompt:"你是一个专业的助手"
3. 执行测试
4. 验证请求包含 system_prompt 参数

预期结果:
✅ 高级选项可展开
✅ System Prompt 生效

---

【测试场景 5:停止测试】
1. 选择模型,输入 prompt,开始测试
2. 在流式输出过程中,点击「停止」按钮(红色)
3. 验证:
   - 所有 AbortController 被 abort
   - 已接收内容保留
   - 状态变为"已完成"
   - 显示 info message "测试已停止"

预期结果:
✅ 停止功能正常
✅ 已接收内容不丢失

---

【测试场景 6:清除结果】
1. 测试完成后,点击「清除结果」按钮
2. 验证结果区域完全隐藏

预期结果:
✅ 结果清除正常

---

【测试场景 7:Embedding 模型测试】
1. 如果有 Embedding 类型的模型,勾选它
2. 输入 prompt
3. 执行测试
4. 验证结果卡片显示:
   - 维度(descriptions)
   - Token 计数
   - 向量预览(前N个值)

预期结果:
✅ Embedding 结果正确展示

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 模型测试(SSE) | POST(fetch) | /api/v1/admin/ai/api-key/chat-model/test |

---

【问题诊断】
- 流式输出无内容 → 检查 API Key 是否有效,Network 面板 SSE 数据
- 多模型只显示一个 → 检查 grid 布局 CSS
- 停止后页面卡住 → 检查 AbortController 清理逻辑
- Embedding 结果不显示 → 检查 data.type === 'embedding' 分支
```

---

### 5.4 AI-04 MCP 服务管理 — 我的 MCP

**页面路径**: 管理后台 → AI 管理 → MCP 服务 → 「我的 MCP」Tab  
**源码文件**: `frontend/src/views/admin/ai/mcp/McpServiceManagement.vue`  
**API 文件**: `frontend/src/api/ai-mcp.ts`  
**后端路由**: `backend/app/routers/ai/ai_mcp.py`  
**基础路径**: `/api/v1/admin/ai/mcp-api-key`

#### 5.4.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-04-01 | Tab 切换 | 切换到「我的 MCP」Tab | 表格正确加载 |
| AI-04-02 | 列表加载与显示 | 验证表格列 | 8 列:名称、服务类型、协议类型、状态、健康、创建者、创建时间、操作 |
| AI-04-03 | 搜索功能 | 名称搜索 + 服务类型筛选 + 状态筛选 | 过滤正确 |
| AI-04-04 | 新增 API Key | 点击新增 → 填写 → 提交 | McpApiKeyFormModal 弹窗,提交成功 |
| AI-04-05 | 编辑 API Key | 点击编辑 → 回填 → 修改 → 提交 | 数据正确回填 |
| AI-04-06 | 连接测试 | 点击「测试」按钮 | 显示 loading,返回健康状态 |
| AI-04-07 | Client 管理 | 点击「Client」按钮 | McpClientList 弹窗打开 |
| AI-04-08 | 删除 API Key | 点击删除 → 确认 | 删除成功 |

#### 5.4.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

打开 MCP 服务管理页面,执行「我的 MCP」Tab 的完整测试。

【前置操作】
1. 登录系统,导航到 AI 管理 → MCP 服务
2. 默认应在「我的 MCP」Tab
3. 等待页面加载

---

【测试场景 1:Tab 切换与列表加载】
1. 验证页面有两个 Tab:「我的 MCP」和「MCP 广场」
2. 如果不在「我的 MCP」Tab,点击切换
3. 验证表格正常加载
4. 检查列:名称、服务类型、协议类型、状态、健康、创建者、创建时间、操作
5. 验证服务类型使用字典 Tag(MCP_SERVICE_TYPE)
6. 验证状态使用 Badge(成功=绿点,禁用=灰点)
7. 验证健康状态使用 Badge + Tooltip(显示最后检查时间)

预期结果:
✅ Tab 切换正常
✅ 表格8列完整
✅ Tag/Badge 显示正确

---

【测试场景 2:搜索功能】
1. 在名称搜索框输入关键词,搜索
2. 选择服务类型下拉筛选
3. 选择状态下拉筛选
4. 点击重置按钮
5. 验证各筛选条件生效/清空

预期结果:
✅ 搜索/筛选/重置正常

---

【测试场景 3:新增 MCP API Key】
1. 点击「新增 API Key」按钮
2. 验证 McpApiKeyFormModal 弹窗弹出
3. 填写表单字段(名称、服务类型、URL、API Key 等)
4. 提交:
   - API POST /api/v1/admin/ai/mcp-api-key/create
   - 成功提示,弹窗关闭,列表刷新

预期结果:
✅ 新增弹窗正常
✅ 提交成功

---

【测试场景 4:编辑 MCP API Key】
1. 点击「编辑」按钮
2. 验证弹窗回填正确
3. 修改字段,提交
4. 验证更新成功

预期结果:
✅ 回填正确
✅ 更新生效

---

【测试场景 5:连接测试】
1. 找到一条 MCP 记录
2. 点击「测试」按钮
3. 验证按钮显示 loading 状态
4. 等待响应:
   - 成功:绿色 Badge + "健康" message
   - 失败:红色 Badge + "异常" warning message
5. 验证健康状态列实时更新
6. 验证 Tooltip 显示最后检查时间

预期结果:
✅ 连接测试正常
✅ 健康状态实时更新

---

【测试场景 6:Client 管理】
1. 点击「Client」按钮
2. 验证 McpClientList 弹窗打开
3. 验证弹窗标题包含 API Key 名称
4. 验证 Client 列表加载

预期结果:
✅ Client 弹窗正常

---

【测试场景 7:删除 MCP API Key】
1. 点击「删除」按钮
2. 验证 Popconfirm 确认弹窗
3. 确认删除
4. 验证成功提示,列表刷新

预期结果:
✅ 删除正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 分页列表 | GET | /api/v1/admin/ai/mcp-api-key/page |
| 详情 | GET | /api/v1/admin/ai/mcp-api-key/get |
| 创建 | POST | /api/v1/admin/ai/mcp-api-key/create |
| 更新 | POST | /api/v1/admin/ai/mcp-api-key/update |
| 删除 | DELETE | /api/v1/admin/ai/mcp-api-key/delete |
| 连接测试 | POST | /api/v1/admin/ai/mcp-square/test/{id} |

---

【问题诊断】
- 列表不加载 → 检查 getMcpApiKeyPage() API
- 服务类型 Tag 不显示 → 检查 DictType.MCP_SERVICE_TYPE 字典
- 连接测试超时 → 检查 MCP 服务 URL 是否可达
- 健康 Badge 不更新 → 检查 handleTestConnection 返回值赋值
```

---

### 5.5 AI-05 MCP 服务管理 — MCP 广场

**页面路径**: MCP 服务 → 「MCP 广场」Tab  
**源码文件**: `frontend/src/views/admin/ai/mcp/McpServiceManagement.vue`, `McpSquareTemplateFormModal.vue`, `McpInstallModal.vue`, `McpSquareDetailModal.vue`  
**API 文件**: `frontend/src/api/ai-mcp.ts`  
**基础路径**: `/api/v1/admin/ai/mcp-square`

#### 5.5.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-05-01 | 广场卡片列表 | 切换到广场 Tab,验证卡片网格 | 卡片显示:名称、描述、类型Tag、分类Tag |
| AI-05-02 | 广场搜索 | 名称搜索 + 分类筛选 + 状态筛选 | 过滤正确 |
| AI-05-03 | 新增模板 | 点击新增 → 填写 → 提交 | 模板创建成功 |
| AI-05-04 | 编辑模板 | 点击编辑 → 回填 → 修改 | 更新成功 |
| AI-05-05 | 查看详情 | 点击「详情」按钮 | McpSquareDetailModal 弹窗 |
| AI-05-06 | 安装模板 | 点击「安装」按钮 → McpInstallModal | 安装成功,卡片显示「已安装」Tag |
| AI-05-07 | 卸载模板 | 点击「卸载」按钮 → 确认 | 卸载成功 |
| AI-05-08 | 删除模板 — 软删除 | 点击删除 → 确认(取消删除) | 软删除成功 |
| AI-05-09 | 删除模板 — 强制删除 | 软删除失败 → 级联确认 → 强制删除 | 强制删除成功 |
| AI-05-10 | 广场分页 | 切换页码/每页条数 | 分页正常 |

#### 5.5.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在 MCP 服务管理页面,切换到「MCP 广场」Tab,执行完整测试。

【前置操作】
1. 进入 MCP 服务管理页面
2. 点击「MCP 广场」Tab
3. 等待卡片网格加载

---

【测试场景 1:广场卡片列表】
1. 验证卡片使用 a-card 网格布局(xs=24, sm=12, md=8, lg=6)
2. 验证每张卡片显示:
   - 标题区:名称 + 已安装Tag(绿色,如果已安装)
   - 描述(最多2行,溢出省略)
   - 底部:服务类型Tag + 分类Tag + 禁用Tag
3. 验证卡片操作按钮:详情、编辑、安装/卸载、删除
4. 验证空状态:a-empty 组件

预期结果:
✅ 卡片网格布局正确
✅ 信息展示完整

---

【测试场景 2:广场搜索】
1. 在搜索框输入关键词
2. 选择分类下拉筛选(字典:MCP_CATEGORY)
3. 选择状态筛选
4. 点击重置
5. 验证各条件生效

预期结果:
✅ 搜索/筛选/重置正常

---

【测试场景 3:新增模板】
1. 点击「新增模板」按钮
2. 验证 McpSquareTemplateFormModal 弹窗
3. 填写模板信息(名称、服务类型、URL、描述等)
4. 提交,验证创建成功

预期结果:
✅ 新增模板成功

---

【测试场景 4:编辑模板】
1. 点击卡片「编辑」按钮
2. 验证弹窗回填正确
3. 修改,提交,验证更新

预期结果:
✅ 编辑回填正确

---

【测试场景 5:查看详情】
1. 点击卡片「详情」按钮
2. 验证 McpSquareDetailModal 弹窗打开
3. 验证详情信息完整

预期结果:
✅ 详情弹窗正常

---

【测试场景 6:安装模板】
1. 找到未安装的模板(无「已安装」Tag)
2. 点击「安装」按钮
3. 验证 McpInstallModal 弹窗打开
4. 填写安装配置(URL、API Key 等)
5. 提交安装:
   - API POST /api/v1/admin/ai/mcp-square/install
   - 成功提示
6. 验证卡片出现「已安装」绿色 Tag
7. 验证「安装」按钮变为「卸载」按钮

预期结果:
✅ 安装成功
✅ 卡片状态更新

---

【测试场景 7:卸载模板】
1. 找到已安装的模板
2. 点击「卸载」按钮
3. 验证 Popconfirm 确认弹窗
4. 确认卸载
5. 验证成功提示
6. 验证卡片「已安装」Tag 消失

预期结果:
✅ 卸载成功

---

【测试场景 8:删除模板 — 软删除】
1. 点击卡片「删除」按钮
2. 验证 Popconfirm 确认弹窗
   - 确认按钮文字:「取消删除」
   - 取消按钮文字:「强制删除」
3. 点击确认(执行软删除)
4. 验证删除成功,卡片消失

预期结果:
✅ 软删除成功

---

【测试场景 9:删除模板 — 强制删除】
1. 点击删除,如果软删除失败(有关联数据):
   - 后端返回 400
   - 弹出 Modal.confirm 级联删除确认
2. 点击「强制删除」
3. 验证 API DELETE /api/v1/admin/ai/mcp-square/delete?force=true
4. 验证强制删除成功

预期结果:
✅ 强制删除成功

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 广场分页 | GET | /api/v1/admin/ai/mcp-square/page |
| 详情 | GET | /api/v1/admin/ai/mcp-square/get |
| 创建 | POST | /api/v1/admin/ai/mcp-square/create |
| 更新 | POST | /api/v1/admin/ai/mcp-square/update |
| 删除(软) | DELETE | /api/v1/admin/ai/mcp-square/delete?id=X |
| 删除(强制) | DELETE | /api/v1/admin/ai/mcp-square/delete?id=X&force=true |
| 安装 | POST | /api/v1/admin/ai/mcp-square/install |
| 卸载 | DELETE | /api/v1/admin/ai/mcp-square/uninstall |

---

【问题诊断】
- 卡片不显示 → 检查 getMcpSquarePage() API
- 安装弹窗不打开 → 检查 McpInstallModal v-model:visible
- 软删除后弹级联确认 → 检查后端 400 响应 + Modal.confirm 逻辑
- 分类 Tag 不显示 → 检查 DictType.MCP_CATEGORY 字典
```

---

### 5.6 AI-06 技能管理 — 技能包

**页面路径**: 管理后台 → AI 管理 → 技能管理 → 「技能包管理」Tab  
**源码文件**: `frontend/src/views/admin/ai/skill/SkillManagement.vue`, `SkillPackageForm.vue`  
**API 文件**: `frontend/src/api/skill.ts`（getSkills, deleteSkillPackage, updateSkillPackage, importSkillPackage, exportSkillPackage）  
**后端路由**: `backend/app/routers/ai/ai_skill.py`

#### 5.6.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-06-01 | 主 Tab 切换 | 切换「技能包管理」/「技能仓库」 | 内容区正确切换 |
| AI-06-02 | 左侧包列表加载 | 验证分类分组 + 包列表 | 分组折叠/展开正常,包列表渲染 |
| AI-06-03 | 搜索技能包 | 输入关键词搜索 | 包列表过滤 |
| AI-06-04 | 选中技能包 | 点击左侧包项 | 右侧显示详情,自动加载规则/Markdown |
| AI-06-05 | 新增技能包 | 点击「新增技能包」→ 填写 → 提交 | SkillPackageForm 弹窗,创建成功 |
| AI-06-06 | 编辑技能包 | 点击「编辑」按钮 | 弹窗回填,更新成功 |
| AI-06-07 | 启用/禁用技能包 | 点击启用/禁用按钮 | 状态切换,Tag 变化 |
| AI-06-08 | 删除技能包 | 点击删除 → 确认 | 删除成功,右侧清空 |
| AI-06-09 | 导入 ZIP | 点击「导入 ZIP」→ 选择文件 → 确认 | 导入成功,自动选中 |
| AI-06-10 | 导出 ZIP | 点击「导出」按钮 | 下载 .zip 文件 |

#### 5.6.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

打开技能管理页面,执行技能包管理功能的完整测试。

【前置操作】
1. 登录系统,导航到 AI 管理 → 技能管理
2. 默认在「技能仓库」Tab,点击切换到「技能包管理」
3. 等待左侧包列表加载

---

【测试场景 1:主 Tab 切换】
1. 验证标题栏有两个 Tab:「技能包管理」和「技能仓库」
2. 默认激活「技能仓库」
3. 点击「技能包管理」Tab
4. 验证内容区切换为左右布局(左侧包列表 + 右侧详情)
5. 验证操作按钮变为「导入 ZIP」+「新增技能包」

预期结果:
✅ Tab 切换正常
✅ 按钮组正确变化

---

【测试场景 2:左侧包列表加载】
1. 验证左侧面板显示分类分组(字典:skill_category)
2. 验证每个分组标题:分类名 + 数量(如"信息查询 (3)")
3. 验证每个包项:图标 emoji + 名称 + 禁用Tag(如果禁用)
4. 验证分组可折叠(点击标题,DownOutlined/UpOutlined 切换)

预期结果:
✅ 分组显示正确
✅ 折叠/展开正常

---

【测试场景 3:搜索技能包】
1. 在搜索框输入关键词
2. 验证包列表过滤(名称或 package_id 匹配)
3. 清空搜索,验证列表恢复

预期结果:
✅ 搜索过滤正常

---

【测试场景 4:选中技能包 — 右侧详情】
1. 点击左侧某个包项
2. 验证包项高亮(active 样式 + 右侧边框)
3. 验证右侧显示:
   - 头部:图标 + 名称 + 操作按钮(编辑、启用/禁用、导出、删除)
   - Tabs:包详情 / 触发规则 / SKILL.md / 进化配置 / 对话记录
   - 包详情 Tab:a-descriptions 显示(package_id、分类、版本、状态、路径、创建时间、描述)
   - 脚本列表:每个脚本显示名称、命令、描述、Switch、编辑、删除

预期结果:
✅ 右侧详情完整
✅ 5 个 Tab 显示

---

【测试场景 5:新增技能包】
1. 点击「新增技能包」按钮
2. 验证 SkillPackageForm 弹窗打开
3. 填写包信息(名称、分类、描述、图标等)
4. 提交,验证创建成功
5. 验证左侧列表刷新,新包出现

预期结果:
✅ 新增成功

---

【测试场景 6:编辑技能包】
1. 选中一个包,点击「编辑」按钮
2. 验证弹窗回填正确
3. 修改名称,提交
4. 验证更新成功

预期结果:
✅ 编辑回填正确

---

【测试场景 7:启用/禁用技能包】
1. 选中一个启用的包
2. 点击「禁用」按钮
3. 验证 API PUT 调用
4. 验证 Tag 变为「禁用」(灰色)
5. 再次点击「启用」,验证恢复

预期结果:
✅ 启用/禁用切换正常

---

【测试场景 8:删除技能包】
1. 选中一个包
2. 点击「删除」按钮
3. 验证 Popconfirm 确认弹窗
4. 确认删除
5. 验证:
   - 右侧详情清空(显示提示文字)
   - 左侧列表刷新
   - 成功 message

预期结果:
✅ 删除成功
✅ 右侧清空

---

【测试场景 9:导入 ZIP 包】
1. 点击「导入 ZIP」按钮
2. 验证隐藏的文件 input 触发(accept=".zip")
3. 选择一个 .zip 文件
4. 验证 Modal.confirm 确认弹窗(显示文件名)
5. 确认导入:
   - API POST (multipart/form-data)
   - 成功 message(显示包名和脚本数)
   - 列表刷新,自动选中新导入的包

预期结果:
✅ 导入成功
✅ 自动选中新包

---

【测试场景 10:导出 ZIP 包】
1. 选中一个包
2. 点击「导出」按钮
3. 验证浏览器下载 {package_id}.zip 文件
4. 验证成功 message

预期结果:
✅ 导出下载正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 技能包列表 | GET | /api/v1/admin/ai/skill |
| 删除包 | DELETE | /api/v1/admin/ai/skill/{package_id} |
| 更新包 | PUT | /api/v1/admin/ai/skill/{package_id} |
| 导入 | POST | /api/v1/admin/ai/skill/import |
| 导出 | GET | /api/v1/admin/ai/skill/{package_id}/export |

---

【问题诊断】
- 包列表不加载 → 检查 getSkills() API
- 分组不显示 → 检查 skill_category 字典加载
- 导入失败 → 检查文件格式和后端解析
- 导出不下载 → 检查 Blob 下载逻辑
```

---

### 5.7 AI-07 技能管理 — 脚本与规则

**页面路径**: 技能管理 → 选中包 → 「包详情」Tab(脚本) / 「触发规则」Tab  
**源码文件**: `SkillManagement.vue`, `SkillScriptForm.vue`, `SkillRuleFormModal.vue`  
**API 文件**: `frontend/src/api/skill.ts`, `frontend/src/api/skillRule.ts`  
**后端路由**: `backend/app/routers/ai/ai_skill.py`, `ai_skill_rule.py`

#### 5.7.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-07-01 | 脚本列表显示 | 验证脚本项渲染 | 名称、命令、描述、Switch、编辑、删除 |
| AI-07-02 | 新增脚本 | 点击「新增脚本」→ 填写 → 提交 | 脚本创建成功 |
| AI-07-03 | 编辑脚本 | 点击脚本编辑按钮 → 回填 → 修改 | 更新成功 |
| AI-07-04 | 脚本 Switch 切换 | 切换脚本启用/禁用 | 状态更新,Switch 变化 |
| AI-07-05 | 删除脚本 | 点击脚本删除 → 确认 | 脚本消失 |
| AI-07-06 | 规则列表加载 | 切换到「触发规则」Tab | 规则表格加载:名称、Agent、优先级、条件、状态、操作 |
| AI-07-07 | 新增规则 | 点击「新增规则」→ 填写 → 提交 | SkillRuleFormModal 弹窗,创建成功 |
| AI-07-08 | 编辑规则 | 点击规则编辑 → 回填 → 修改 | 更新成功 |
| AI-07-09 | 规则 Switch 切换 | 切换规则 is_active | 状态更新成功 |
| AI-07-10 | 删除规则 | 点击规则删除 → 确认 | 规则消失 |

#### 5.7.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在技能管理页面,选中一个技能包,执行脚本和触发规则的完整测试。

【前置操作】
1. 进入技能管理,切换到「技能包管理」Tab
2. 选中一个技能包
3. 等待右侧详情加载

---

【测试场景 1:脚本列表显示】
1. 在「包详情」Tab 下,验证脚本列表区域
2. 验证每个脚本项显示:
   - 名称(禁用时灰色+删除线)
   - 禁用Tag(如果禁用)
   - 命令(等宽字体)
   - 描述(可选)
   - Switch(启用/禁用)
   - 编辑按钮
   - 删除按钮
3. 验证底部「新增脚本」虚线按钮

预期结果:
✅ 脚本列表渲染正确

---

【测试场景 2:新增脚本】
1. 点击「新增脚本」按钮
2. 验证 SkillScriptForm 弹窗/区域出现
3. 填写脚本信息(名称、命令、描述等)
4. 提交,验证创建成功
5. 验证脚本列表刷新

预期结果:
✅ 新增脚本成功

---

【测试场景 3:编辑脚本】
1. 点击脚本的编辑按钮
2. 验证表单回填正确
3. 修改命令,提交
4. 验证更新成功

预期结果:
✅ 编辑回填正确

---

【测试场景 4:脚本 Switch 切换】
1. 找到一个启用的脚本
2. 点击 Switch 切换为禁用
3. 验证 API 调用 updateScript
4. 验证脚本名称变灰+删除线
5. 验证禁用Tag出现

预期结果:
✅ Switch 切换正常
✅ 视觉反馈正确

---

【测试场景 5:删除脚本】
1. 点击脚本的删除按钮
2. 验证 Popconfirm 确认
3. 确认删除
4. 验证脚本从列表消失

预期结果:
✅ 删除成功

---

【测试场景 6:触发规则 Tab】
1. 切换到「触发规则」Tab
2. 验证工具栏:「新增规则」+「刷新」按钮
3. 验证规则表格列:名称、Agent、优先级、条件预览、状态(Switch)、操作
4. 验证优先级使用颜色 Tag(≤10=红,≤50=橙,≤100=蓝,其他=默认)
5. 验证条件列:等宽字体预览,Tooltip 显示完整 JSON

预期结果:
✅ 规则表格渲染正确

---

【测试场景 7:新增规则】
1. 点击「新增规则」按钮
2. 验证 SkillRuleFormModal 弹窗
3. 填写规则信息(名称、Agent、优先级、条件等)
4. 提交,验证创建成功
5. 验证规则列表刷新

预期结果:
✅ 新增规则成功

---

【测试场景 8:编辑规则】
1. 点击规则的「编辑」按钮
2. 验证弹窗回填正确
3. 修改,提交,验证更新

预期结果:
✅ 编辑回填正确

---

【测试场景 9:规则 Switch 切换】
1. 点击规则的 Switch
2. 验证 API 调用 updateSkillRule
3. 验证状态更新,message 提示

预期结果:
✅ 规则状态切换正常

---

【测试场景 10:删除规则】
1. 点击规则的「删除」按钮
2. 验证 Popconfirm 确认
3. 确认删除
4. 验证规则列表刷新

预期结果:
✅ 删除成功

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 脚本更新 | PUT | /api/v1/admin/ai/skill/{package_id}/script/{script_id} |
| 脚本删除 | DELETE | /api/v1/admin/ai/skill/{package_id}/script/{script_id} |
| 规则列表 | GET | /api/v1/admin/ai/skill-rule |
| 规则更新 | PUT | /api/v1/admin/ai/skill-rule/{id} |
| 规则删除 | DELETE | /api/v1/admin/ai/skill-rule/{id} |

---

【问题诊断】
- 脚本列表不显示 → 检查 selected.scripts 数据
- 规则列表不加载 → 检查 getSkillRules({ package_id }) 参数
- Switch 切换不生效 → 检查 updateSkillRule API 参数 is_active
- 条件预览为空 → 检查 formatConditions JSON 序列化
```

---

### 5.8 AI-08 技能管理 — SKILL.md 与进化配置

**页面路径**: 技能管理 → 选中包 → 「SKILL.md」Tab / 「进化配置」Tab  
**源码文件**: `SkillManagement.vue`, `SkillEvolutionPanel.vue`  
**API 文件**: `frontend/src/api/skill.ts`（getSkillMarkdown, saveSkillMarkdown）

#### 5.8.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-08-01 | SKILL.md 加载 | 切换到 SKILL.md Tab | Markdown 内容渲染或空状态 |
| AI-08-02 | SKILL.md 编辑 | 点击编辑 → 修改内容 → 保存 | 保存成功,来源标记更新 |
| AI-08-03 | SKILL.md 取消编辑 | 编辑中点击取消 | 回到预览模式 |
| AI-08-04 | SKILL.md 来源标记 | 验证来源标签 | 显示来源:数据库/工作区/文件系统 |
| AI-08-05 | 进化配置面板 | 切换到进化配置 Tab | SkillEvolutionPanel 加载 |

#### 5.8.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在技能管理页面,选中一个技能包,测试 SKILL.md 和进化配置功能。

【前置操作】
1. 选中一个技能包
2. 等待详情加载

---

【测试场景 1:SKILL.md 加载】
1. 切换到「SKILL.md」Tab
2. 验证工具栏:编辑按钮 + 刷新按钮
3. 验证内容区:
   - 如果有内容:pre 标签等宽字体显示
   - 如果无内容:a-empty 显示"暂无 SKILL.md"
   - 如果加载失败:a-empty 显示错误信息
4. 验证来源标记(如"来源:数据库")

预期结果:
✅ Markdown 内容正确加载
✅ 来源标记显示

---

【测试场景 2:SKILL.md 编辑与保存】
1. 点击「编辑」按钮
2. 验证工具栏变为:保存 + 取消按钮
3. 验证内容区变为 textarea 编辑器
4. 修改内容
5. 点击「保存」
6. 验证:
   - API 调用 saveSkillMarkdown
   - 成功 message
   - 回到预览模式
   - 来源标记更新为"数据库"

预期结果:
✅ 编辑/保存流程正常

---

【测试场景 3:SKILL.md 取消编辑】
1. 进入编辑模式
2. 修改内容
3. 点击「取消」
4. 验证回到预览模式,内容未变化

预期结果:
✅ 取消编辑正常

---

【测试场景 4:进化配置面板】
1. 切换到「进化配置」Tab
2. 验证 SkillEvolutionPanel 组件加载
3. 验证面板内容渲染

预期结果:
✅ 进化配置面板正常

---

【测试场景 5:对话记录面板】
1. 切换到「对话记录」Tab
2. 验证 SkillConversationsPanel 组件加载
3. 验证对话列表渲染

预期结果:
✅ 对话记录面板正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 获取 Markdown | GET | /api/v1/admin/ai/skill/{package_id}/markdown |
| 保存 Markdown | PUT | /api/v1/admin/ai/skill/{package_id}/markdown |

---

【问题诊断】
- Markdown 不显示 → 检查 getSkillMarkdown API
- 保存失败 → 检查 saveSkillMarkdown 请求体
- 来源标记不显示 → 检查 markdownSource 赋值逻辑
```

---

### 5.9 AI-09 技能管理 — 技能仓库

**页面路径**: 技能管理 → 「技能仓库」Tab  
**源码文件**: `frontend/src/views/admin/ai/skill/components/SkillHubBrowser.vue`  
**API 文件**: `frontend/src/api/skill.ts`  
**后端路由**: `backend/app/routers/ai/ai_skill_hub.py`

#### 5.9.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-09-01 | 仓库浏览 | 切换到技能仓库 Tab | 仓库列表加载 |
| AI-09-02 | 添加 Repo | 点击「添加仓库」按钮 | 弹窗打开,填写 Repo URL |
| AI-09-03 | 安装技能 | 在仓库中点击安装 | 安装到本地技能包 |
| AI-09-04 | 仓库搜索 | 搜索仓库中的技能 | 过滤结果 |

#### 5.9.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在技能管理页面,切换到「技能仓库」Tab,执行仓库浏览功能测试。

【前置操作】
1. 进入技能管理页面
2. 点击「技能仓库」Tab(默认激活)
3. 等待 SkillHubBrowser 加载

---

【测试场景 1:仓库浏览】
1. 验证 SkillHubBrowser 组件渲染
2. 验证仓库列表/卡片显示
3. 验证操作按钮「添加仓库」

预期结果:
✅ 仓库浏览正常

---

【测试场景 2:添加仓库】
1. 点击「添加仓库」按钮
2. 验证弹窗打开
3. 填写仓库 URL
4. 提交,验证添加成功

预期结果:
✅ 添加仓库成功

---

【测试场景 3:安装技能】
1. 在仓库中浏览可用技能
2. 点击某个技能的「安装」按钮
3. 验证安装流程
4. 验证安装成功后跳转到技能包管理

预期结果:
✅ 安装成功

---

【测试场景 4:仓库搜索】
1. 在搜索框输入关键词
2. 验证搜索结果过滤

预期结果:
✅ 搜索正常

---

【问题诊断】
- 仓库不加载 → 检查 SkillHubBrowser API 调用
- 安装失败 → 检查后端 ai_skill_hub 路由
```

---

### 5.10 AI-10 工具管理 — 工具列表

**页面路径**: 管理后台 → AI 管理 → 工具管理 → 「工具列表」Tab  
**源码文件**: `frontend/src/views/admin/ai/tool/ToolManagement.vue`, `ToolFormModal.vue`, `ToolTestModal.vue`  
**API 文件**: `frontend/src/api/ai-tool.ts`  
**后端路由**: `backend/app/routers/ai/ai_tool.py`  
**基础路径**: `/api/v1/admin/ai/tool`

#### 5.10.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-10-01 | Tab 切换 | 切换到「工具列表」Tab | 表格加载 |
| AI-10-02 | 列表加载与显示 | 验证表格列 | 9 列完整:toolKey、显示名、分类、系统/自定义、描述、状态(Switch)、排序、创建时间、操作 |
| AI-10-03 | 搜索功能 | toolKey + 显示名 + 分类 + 类型 + 状态 | 多条件过滤 |
| AI-10-04 | 新增工具 | 点击新增 → ToolFormModal → 提交 | 创建成功 |
| AI-10-05 | 编辑工具 | 点击编辑 → 回填 → 修改 | 更新成功 |
| AI-10-06 | 状态 Switch | 切换工具启用/禁用 | 状态更新(Switch 禁用系统工具) |
| AI-10-07 | 删除工具 | 点击删除 → 确认(系统工具禁用删除) | 删除成功 |
| AI-10-08 | 测试工具 | 点击「测试」按钮 → ToolTestModal | 测试弹窗打开 |
| AI-10-09 | 刷新缓存 | 点击「刷新缓存」按钮 | 缓存刷新成功,显示数量 |

#### 5.10.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

打开工具管理页面,执行「工具列表」Tab 的完整测试。

【前置操作】
1. 登录系统,导航到 AI 管理 → 工具管理
2. 默认在「工具列表」Tab
3. 等待页面加载

---

【测试场景 1:列表加载与显示】
1. 验证表格正常加载
2. 检查列:toolKey、显示名、分类、系统/自定义、描述、状态、排序、创建时间、操作
3. 验证 toolKey 列使用 geekblue Tag
4. 验证系统/自定义列使用 Tag(系统=蓝色,自定义=灰色)
5. 验证状态列使用 Switch 组件
6. 验证系统工具的 Switch 为 disabled 状态
7. 验证系统工具的删除按钮为 disabled 状态

预期结果:
✅ 表格9列完整
✅ 系统工具有保护(不可删除/禁用)

---

【测试场景 2:搜索功能】
1. 在 toolKey 搜索框输入关键词
2. 在显示名搜索框输入关键词
3. 选择分类下拉筛选(从工具分组动态加载)
4. 选择类型下拉筛选(字典:tool_type)
5. 选择状态筛选(enabled/disabled)
6. 点击重置按钮
7. 验证各条件生效/清空

预期结果:
✅ 多条件搜索正常
✅ 重置清空所有条件

---

【测试场景 3:新增工具】
1. 点击「新增工具」按钮
2. 验证 ToolFormModal 弹窗
3. 填写工具信息(toolKey、显示名、分类、类型、描述、配置等)
4. 提交:
   - API POST /api/v1/admin/ai/tool/create
   - 成功提示,列表刷新

预期结果:
✅ 新增成功

---

【测试场景 4:编辑工具】
1. 点击工具的「编辑」按钮
2. 验证弹窗回填正确
3. 修改显示名,提交
4. 验证更新成功

预期结果:
✅ 编辑回填正确

---

【测试场景 5:状态 Switch】
1. 找到一个自定义工具(非系统工具)
2. 点击 Switch 切换状态
3. 验证 API 调用 updateTool
4. 验证 message 提示
5. 验证列表刷新
6. 注意:系统工具的 Switch 不可点击

预期结果:
✅ 状态切换正常
✅ 系统工具 Switch 禁用

---

【测试场景 6:删除工具】
1. 验证系统工具删除按钮禁用
2. 点击自定义工具的「删除」按钮
3. 验证 Popconfirm 确认弹窗
4. 确认删除
5. 验证成功提示,列表刷新

预期结果:
✅ 系统工具不可删除
✅ 自定义工具删除正常

---

【测试场景 7:测试工具】
1. 点击工具的「测试」按钮(PlayCircleOutlined)
2. 验证 ToolTestModal 弹窗打开
3. 验证弹窗内容(工具信息、输入参数、测试按钮)

预期结果:
✅ 测试弹窗正常

---

【测试场景 8:刷新缓存】
1. 点击「刷新缓存」按钮
2. 验证 API POST /api/v1/admin/ai/tool/refresh-cache
3. 验证成功 message(显示缓存数量)
4. 验证列表刷新

预期结果:
✅ 缓存刷新成功

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 分页列表 | GET | /api/v1/admin/ai/tool/page |
| 详情 | GET | /api/v1/admin/ai/tool/get |
| 创建 | POST | /api/v1/admin/ai/tool/create |
| 更新 | POST | /api/v1/admin/ai/tool/update |
| 删除 | DELETE | /api/v1/admin/ai/tool/delete |
| 刷新缓存 | POST | /api/v1/admin/ai/tool/refresh-cache |
| 测试 | POST | /api/v1/admin/ai/tool/test |
| 简易列表 | GET | /api/v1/admin/ai/tool/simple-list |

---

【问题诊断】
- 列表不加载 → 检查 getToolPage() API
- 分类下拉为空 → 检查 getToolGroupPage 动态加载
- 类型下拉为空 → 检查 tool_type 字典
- 系统工具可删除 → 检查 isSystem 条件判断
- 缓存刷新失败 → 检查 Redis 连接
```

---

### 5.11 AI-11 工具管理 — 工具分组与成员

**页面路径**: 工具管理 → 「工具分组」Tab  
**源码文件**: `frontend/src/views/admin/ai/tool/ToolManagement.vue`  
**API 文件**: `frontend/src/api/ai-tool.ts`  
**基础路径**: `/api/v1/admin/ai/tool/group`

#### 5.11.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-11-01 | 分组 Tab 切换 | 切换到「工具分组」Tab | 分组表格加载 |
| AI-11-02 | 分组列表 | 验证表格列 | 7 列:分组Key、显示名、描述、工具数、状态、排序、操作 |
| AI-11-03 | 分组搜索 | 输入分组名搜索 | 过滤正确 |
| AI-11-04 | 新增分组 | 点击新增 → 填写表单 → 提交 | 分组创建成功 |
| AI-11-05 | 编辑分组 | 点击编辑 → 回填 → 修改 | 更新成功(Key 不可编辑) |
| AI-11-06 | 删除分组 | 点击删除 → 确认 | 删除成功 |
| AI-11-07 | 成员管理 — 打开 | 点击「成员」按钮 | 成员弹窗打开,加载成员和可选工具 |
| AI-11-08 | 成员管理 — 添加 | 选择工具 → 点击添加 | 成员添加成功 |
| AI-11-09 | 成员管理 — 移除 | 点击成员「移除」按钮 | 成员移除成功 |

#### 5.11.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在工具管理页面,切换到「工具分组」Tab,执行分组和成员管理的完整测试。

【前置操作】
1. 进入工具管理页面
2. 点击「工具分组」Tab
3. 等待分组表格加载

---

【测试场景 1:分组 Tab 与列表】
1. 验证 Tab 切换正常
2. 验证头部:标题 + 描述 + 「新增分组」按钮
3. 验证搜索栏:分组名搜索 + 刷新按钮
4. 验证表格列:分组Key、显示名、描述、工具数、状态、排序、操作

预期结果:
✅ 分组列表正常

---

【测试场景 2:新增分组】
1. 点击「新增分组」按钮
2. 验证 Modal 弹窗(560px 宽)
3. 验证表单字段:
   - 分组Key(必填,如 risk_intel_group)
   - 显示名(可选)
   - 描述(textarea)
   - 指令(textarea)
   - 启用(Switch)
   - 排序(数字)
4. 不填写 Key 直接提交,验证提示"名称必填"
5. 填写完整信息提交
6. 验证创建成功,列表刷新

预期结果:
✅ 新增分组成功
✅ 必填校验生效

---

【测试场景 3:编辑分组】
1. 点击分组的「编辑」按钮
2. 验证弹窗回填正确
3. 验证分组Key 输入框 disabled(不可修改)
4. 修改显示名,提交
5. 验证更新成功

预期结果:
✅ 编辑回填正确
✅ Key 不可修改

---

【测试场景 4:删除分组】
1. 点击分组的「删除」按钮
2. 验证 Popconfirm 确认
3. 确认删除
4. 验证成功提示,列表刷新

预期结果:
✅ 删除成功

---

【测试场景 5:成员管理 — 打开弹窗】
1. 点击分组的「成员」按钮(ApartmentOutlined)
2. 验证成员管理 Modal 弹窗(720px 宽)
3. 验证弹窗内容:
   - Alert 提示:当前分组名称
   - 工具选择器(多选 Select,show-search)
   - 「添加」按钮
   - 成员表格(toolKey、显示名、分类、操作)
4. 验证成员列表和可选工具列表加载

预期结果:
✅ 成员弹窗正常

---

【测试场景 6:成员管理 — 添加工具】
1. 在工具选择器中搜索并选择工具
2. 点击「添加」按钮
3. 验证 API POST /api/v1/admin/ai/tool/group/members/add
4. 验证成功提示
5. 验证成员表格刷新,新成员出现
6. 验证选择器中已移除刚添加的工具

预期结果:
✅ 添加成员成功

---

【测试场景 7:成员管理 — 移除成员】
1. 点击成员的「移除」按钮
2. 验证 API 调用 removeGroupMember
3. 验证成功提示
4. 验证成员表格刷新

预期结果:
✅ 移除成员成功

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 分组分页 | GET | /api/v1/admin/ai/tool/group/page |
| 创建分组 | POST | /api/v1/admin/ai/tool/group/create |
| 更新分组 | POST | /api/v1/admin/ai/tool/group/update |
| 删除分组 | DELETE | /api/v1/admin/ai/tool/group/delete |
| 获取成员 | GET | /api/v1/admin/ai/tool/group/members |
| 添加成员 | POST | /api/v1/admin/ai/tool/group/members/add |
| 移除成员 | POST | /api/v1/admin/ai/tool/group/members/remove |

---

【问题诊断】
- 分组列表不加载 → 检查 getToolGroupPage() API
- 编辑时 Key 可修改 → 检查 !!editingGroup 条件
- 成员弹窗不打开 → 检查 openMembers 函数
- 添加成员后选择器未更新 → 检查 openMembers 重新加载
```

---

### 5.12 AI-12 联网搜索管理 — 配置管理

**页面路径**: 管理后台 → AI 管理 → 联网搜索 → 「配置管理」Tab  
**源码文件**: `frontend/src/views/admin/ai/websearch/WebSearchManagement.vue`, `WebSearchFormModal.vue`, `SearchTestModal.vue`  
**API 文件**: `frontend/src/api/ai-web-search.ts`  
**后端路由**: `backend/app/routers/ai/ai_web_search.py`  
**基础路径**: `/api/v1/admin/ai/web-search`

#### 5.12.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-12-01 | 页面加载与 Tab 显示 | 打开页面,验证 4 个 Tab | 配置管理/配额用量/健康检查/搜索日志 |
| AI-12-02 | 配置列表加载 | 验证表格列 | 11 列:名称、API Key、平台、超时、最大结果数、配额、优先级、URL、状态、创建时间、操作 |
| AI-12-03 | 搜索功能 | 名称 + 平台 + 状态 | 过滤正确 |
| AI-12-04 | 新增搜索供应商 | 点击新增 → 填写 → 提交 | 创建成功 |
| AI-12-05 | 编辑搜索供应商 | 点击编辑 → 回填 → 修改 | 更新成功 |
| AI-12-06 | 状态切换 | 点击启用/禁用 | 状态切换成功 |
| AI-12-07 | 删除搜索供应商 | 点击删除 → 确认 | 删除成功 |
| AI-12-08 | 测试搜索 | 点击「测试」→ SearchTestModal | 测试弹窗打开 |

#### 5.12.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

打开联网搜索管理页面,执行配置管理的完整测试。

【前置操作】
1. 登录系统,导航到 AI 管理 → 联网搜索
2. 等待页面加载

---

【测试场景 1:页面加载与 Tab 显示】
1. 验证头部:标题 + 副标题 + 「新增搜索供应商」按钮
2. 验证 4 个 Tab:配置管理、配额用量、健康检查、搜索日志
3. 验证搜索栏在 Tab 栏右侧(tabBarExtraContent):
   - 名称搜索
   - 平台筛选(字典:WEB_SEARCH_PLATFORM)
   - 状态筛选
   - 重置按钮
4. 验证默认在「配置管理」Tab

预期结果:
✅ 4 个 Tab 完整
✅ 搜索栏位置正确

---

【测试场景 2:配置列表加载】
1. 验证表格正常加载
2. 检查列:名称、API Key、平台、超时、最大结果数、配额、优先级、URL、状态、创建时间、操作
3. 验证 API Key 脱敏显示(前12位+***)
4. 验证平台列使用蓝色 Tag
5. 验证状态列使用 Tag(启用=绿色,禁用=红色)
6. 验证配额列:大于0显示数字,0显示"不限"

预期结果:
✅ 表格11列完整
✅ API Key 脱敏
✅ Tag 颜色正确

---

【测试场景 3:搜索功能】
1. 在名称搜索框输入关键词
2. 选择平台下拉筛选
3. 选择状态筛选
4. 点击重置按钮
5. 验证各条件生效/清空

预期结果:
✅ 搜索/筛选/重置正常

---

【测试场景 4:新增搜索供应商】
1. 点击「新增搜索供应商」按钮
2. 验证 WebSearchFormModal 弹窗
3. 填写表单(名称、API Key、平台、URL、超时、最大结果数、配额、优先级等)
4. 提交:
   - API POST /api/v1/admin/ai/web-search/create
   - 成功提示,列表刷新

预期结果:
✅ 新增成功

---

【测试场景 5:编辑搜索供应商】
1. 点击「编辑」按钮
2. 验证弹窗回填正确
3. 修改名称,提交
4. 验证更新成功

预期结果:
✅ 编辑回填正确

---

【测试场景 6:状态切换】
1. 点击启用/禁用按钮
2. 验证 API 调用
3. 验证 message 提示
4. 验证列表刷新

预期结果:
✅ 状态切换正常

---

【测试场景 7:删除搜索供应商】
1. 点击「删除」按钮
2. 验证 Popconfirm 确认
3. 确认删除
4. 验证成功提示,列表刷新

预期结果:
✅ 删除成功

---

【测试场景 8:测试搜索】
1. 点击「测试」按钮(ExperimentOutlined)
2. 验证 SearchTestModal 弹窗打开
3. 验证弹窗内容(供应商信息、搜索输入框、测试按钮)

预期结果:
✅ 测试弹窗正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 分页列表 | GET | /api/v1/admin/ai/web-search/page |
| 详情 | GET | /api/v1/admin/ai/web-search/{id} |
| 创建 | POST | /api/v1/admin/ai/web-search/create |
| 更新 | POST | /api/v1/admin/ai/web-search/update |
| 删除 | DELETE | /api/v1/admin/ai/web-search/delete |
| 测试搜索 | POST | /api/v1/admin/ai/web-search/test |

---

【问题诊断】
- 列表不加载 → 检查 getWebSearchPage() API
- 平台 Tag 不显示 → 检查 DictType.WEB_SEARCH_PLATFORM 字典
- 测试弹窗不打开 → 检查 SearchTestModal v-model:open
```

---

### 5.13 AI-13 联网搜索管理 — 配额/健康/日志

**页面路径**: 联网搜索 → 「配额用量」/「健康检查」/「搜索日志」Tab  
**源码文件**: `frontend/src/views/admin/ai/websearch/WebSearchManagement.vue`  
**API 文件**: `frontend/src/api/ai-web-search.ts`

#### 5.13.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|---------|
| AI-13-01 | 配额用量 Tab | 切换到配额 Tab | 表格显示:供应商、平台、配额、已用、剩余、进度条 |
| AI-13-02 | 配额进度条 | 验证进度条颜色 | ≥90% 红色(exception),其他绿色(active) |
| AI-13-03 | 健康检查 Tab | 切换到健康 Tab | 表格显示:供应商、平台、状态、响应时间、消息 |
| AI-13-04 | 健康状态 Tag | 验证状态颜色 | normal=绿色,warning=橙色,error=红色 |
| AI-13-05 | 健康刷新 | 点击刷新按钮 | 数据重新加载 |
| AI-13-06 | 搜索日志 Tab | 切换到日志 Tab | 表格显示:供应商、平台、关键词、响应时间、结果数、成功/失败、时间 |
| AI-13-07 | 日志分页 | 切换日志页码 | 分页正常 |
| AI-13-08 | 日志成功/失败 Tag | 验证 Tag 颜色 | 成功=绿色,失败=红色 |

#### 5.13.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

在联网搜索管理页面,测试配额用量、健康检查和搜索日志三个 Tab。

【前置操作】
1. 进入联网搜索管理页面

---

【测试场景 1:配额用量 Tab】
1. 点击「配额用量」Tab
2. 验证 a-card 加载(quotaLoading)
3. 验证表格列:供应商、平台、配额、已用、剩余、进度
4. 验证进度条:
   - daily_quota > 0:显示 a-progress + "已用/配额" 文字
   - daily_quota = 0:显示"不限配额"
   - 使用率 ≥ 90%:进度条为红色(exception)
   - 使用率 < 90%:进度条为绿色(active)

预期结果:
✅ 配额数据正确
✅ 进度条颜色正确

---

【测试场景 2:健康检查 Tab】
1. 点击「健康检查」Tab
2. 验证 a-card 加载(healthLoading)
3. 验证右上角刷新按钮
4. 验证表格列:供应商、平台、状态、响应时间、消息
5. 验证状态 Tag:
   - normal:绿色"正常"
   - warning:橙色"警告"
   - error:红色"异常"

预期结果:
✅ 健康数据正确
✅ 状态 Tag 颜色正确

---

【测试场景 3:健康刷新】
1. 点击健康检查 Tab 右上角的刷新按钮
2. 验证 API GET /api/v1/admin/ai/web-search/health
3. 验证数据重新加载

预期结果:
✅ 刷新正常

---

【测试场景 4:搜索日志 Tab】
1. 点击「搜索日志」Tab
2. 验证 a-card 加载(logLoading)
3. 验证表格列:供应商、平台、关键词、响应时间、结果数、成功/失败、时间
4. 验证成功/失败 Tag:
   - success=true:绿色"成功"
   - success=false:红色"失败"
   - 如果有 error,显示错误信息
5. 验证分页功能

预期结果:
✅ 日志数据正确
✅ 分页正常

---

【测试场景 5:Tab 切换数据懒加载】
1. 从配置管理 Tab 切换到配额用量
2. 验证触发 loadQuota() API
3. 切换到健康检查
4. 验证触发 loadHealth() API
5. 切换到搜索日志
6. 验证触发 loadLogs() API

预期结果:
✅ Tab 切换触发对应数据加载

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 配额统计 | GET | /api/v1/admin/ai/web-search/quota |
| 健康检查 | GET | /api/v1/admin/ai/web-search/health |
| 搜索日志 | GET | /api/v1/admin/ai/web-search/logs |

---

【问题诊断】
- 配额数据为空 → 检查 getWebSearchQuota() API
- 健康检查超时 → 检查后端健康检查逻辑
- 日志不显示 → 检查 getWebSearchLogs() 参数
- 进度条颜色不对 → 检查 usage_percent >= 90 条件
```

### 5.14 AI-14 工具调用策略管理

**页面路径**: 管理后台 → 语音管理 → 工具调用策略（动态组件 `voice-tool-policy`）  
**源码文件**: `frontend/src/views/admin/ai/components/ToolPolicyEditor.vue`  
**API 文件**: `frontend/src/api/voice.ts`（listToolPolicies, upsertToolPolicy）  
**后端路由**: `backend/app/routers/ai/` (duplex config 路由)  
**基础路径**: `/api/v1/admin/duplex/config/tool-policy`

#### 5.14.1 测试场景

| 场景 ID | 场景名称 | 操作描述 | 预期结果 |
|---------|---------|---------|----------|
| AI-14-01 | 策略列表加载 | 进入工具调用策略页面 | a-card 标题"工具调用策略",表格加载策略列表 |
| AI-14-02 | 表格列验证 | 验证表格列 | 6 列:工具名、状态(Tag)、超时(ms)、每轮上限、结果上限(B)、操作 |
| AI-14-03 | 状态 Tag 颜色 | 验证启用/停用 Tag | 启用=绿色 Tag,停用=红色 Tag |
| AI-14-04 | 新增策略 — 表单填写 | 在表单中填写工具名 + 参数 | 表单字段:工具名(input)、启用(Switch)、超时(ms)(InputNumber)、每轮最大调用次数(InputNumber)、结果体积上限(InputNumber) |
| AI-14-05 | 新增策略 — 保存 | 填写工具名后点击「保存」 | API POST upsertToolPolicy,成功提示"已保存",列表刷新 |
| AI-14-06 | 新增策略 — 工具名为空 | 不填工具名直接保存 | message.warning "请填写工具名" |
| AI-14-07 | 表单数值边界 | 验证 InputNumber 边界 | 超时:min=500,max=60000,step=500; 每轮上限:min=1,max=10; 结果上限:min=1024,step=1024 |
| AI-14-08 | 编辑策略 | 点击表格行「编辑」链接 | 表单回填该行数据(form = record) |
| AI-14-09 | 修改后保存 | 编辑后点击保存 | upsert 更新成功,列表刷新 |
| AI-14-10 | 重置表单 | 点击「重置」按钮 | 表单恢复默认值(工具名空,启用=true,超时=8000,每轮=2,结果=32768) |
| AI-14-11 | 启用 Switch | 切换表单中「启用」Switch | form.enabled 值切换,true/false |

#### 5.14.2 测试提示词

```
/qa

前端：http://localhost:5173/  后端：http://localhost:8000

测试工具调用策略管理页面（动态组件 voice-tool-policy）。

【前置操作】
1. 登录系统,导航到包含「工具调用策略」Tab 的页面
2. 等待 ToolPolicyEditor 组件加载
3. 验证 a-card 标题为"工具调用策略"

---

【测试场景 1:策略列表加载】
1. 验证组件 onMounted 时自动调用 listToolPolicies()
2. 验证 API GET /api/v1/admin/duplex/config/tool-policy
3. 验证表格渲染,列:工具名、状态(Tag)、超时(ms)、每轮上限、结果上限(B)、操作
4. 验证状态列:
   - enabled=true: 绿色 a-tag 显示"启用"
   - enabled=false: 红色 a-tag 显示"停用"
5. 验证表格 pagination=false(不分页)

预期结果:
✅ 策略列表正常加载
✅ 表格列完整
✅ 状态 Tag 颜色正确

---

【测试场景 2:新增策略】
1. 在表单中填写:
   - 工具名: 输入 "search_law"
   - 启用: Switch 默认 true
   - 超时(ms): 默认 8000
   - 每轮最大调用次数: 默认 2
   - 结果体积上限: 默认 32768
2. 点击「保存」按钮
3. 验证:
   - API POST /api/v1/admin/duplex/config/tool-policy
   - 成功 message "已保存"
   - 列表自动刷新(load())

预期结果:
✅ 新增策略成功
✅ 列表刷新显示新策略

---

【测试场景 3:工具名为空验证】
1. 清空工具名输入框
2. 点击「保存」按钮
3. 验证 message.warning "请填写工具名"
4. 验证不会发送 API 请求

预期结果:
✅ 空工具名拦截

---

【测试场景 4:表单数值边界】
1. 验证超时(ms) InputNumber:
   - 最小值 500,最大值 60000,步长 500
   - 输入 100 → 自动修正为 500
   - 输入 100000 → 自动修正为 60000
2. 验证每轮最大调用次数:
   - 最小值 1,最大值 10
3. 验证结果体积上限:
   - 最小值 1024,步长 1024

预期结果:
✅ 数值边界正确

---

【测试场景 5:编辑策略】
1. 点击表格某行的「编辑」链接
2. 验证表单回填:
   - form.tool_name = record.tool_name
   - form.enabled = record.enabled
   - form.timeout_ms = record.timeout_ms
   - form.max_calls_per_turn = record.max_calls_per_turn
   - form.max_result_bytes = record.max_result_bytes
3. 修改超时为 10000
4. 点击「保存」
5. 验证 upsert 更新成功

预期结果:
✅ 编辑回填正确
✅ 更新保存成功

---

【测试场景 6:重置表单】
1. 在表单中填写任意值
2. 点击「重置」按钮
3. 验证表单恢复默认:
   - 工具名: 空
   - 启用: true
   - 超时: 8000
   - 每轮上限: 2
   - 结果上限: 32768

预期结果:
✅ 重置正常

---

【测试场景 7:启用 Switch】
1. 在表单中找到「启用」Switch
2. 切换 Switch (true → false)
3. 验证 form.enabled 值变化
4. 再切换回来 (false → true)

预期结果:
✅ Switch 切换正常

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 策略列表 | GET | /api/v1/admin/duplex/config/tool-policy |
| 保存/更新 | POST | /api/v1/admin/duplex/config/tool-policy |

---

【问题诊断】
- 策略列表不加载 → 检查 listToolPolicies() API
- 保存失败 → 检查 upsertToolPolicy() 请求体
- 工具名验证不生效 → 检查 form.tool_name 空值判断
- 数值输入异常 → 检查 a-input-number min/max/step 属性
- 编辑回填不正确 → 检查 onEdit(record) Object.assign 逻辑
```

---

## 6.测试结果报告模板

```markdown
# AI 服务测试报告

**测试日期**: YYYY-MM-DD  
**测试人员**: AI Agent (gstack /qa)  
**测试环境**: http://localhost:5173  
**后端 API**: http://localhost:8000

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
| AI-01 API Key 管理 | 11 | | | | |
| AI-02 关联模型管理 | 8 | | | | |
| AI-03 模型测试 | 7 | | | | |
| AI-04 MCP 我的 MCP | 8 | | | | |
| AI-05 MCP 广场 | 10 | | | | |
| AI-06 技能包管理 | 10 | | | | |
| AI-07 脚本与规则 | 10 | | | | |
| AI-08 SKILL.md 与进化 | 5 | | | | |
| AI-09 技能仓库 | 4 | | | | |
| AI-10 工具列表 | 9 | | | | |
| AI-14 工具调用策略 | 11 | | | | |
| AI-11 工具分组与成员 | 9 | | | | |
| AI-12 联网搜索配置 | 8 | | | | |
| AI-13 配额/健康/日志 | 8 | | | | |
| **合计** | **N** | **X** | **Y** | **Z** | **X/N%** |

## 失败用例详情

### AI-XX 模块名 — 测试场景 N:场景名

- **现象**: 
- **控制台错误**: 
- **截图**: 
- **定位**: 
- **修复建议**: 
- **修复文件**: 
- **状态**: 待修复

## 建议

1. **高优先级**:
2. **中优先级**:
3. **低优先级**:
```

---

## 7.模块开发对照与补全清单

| 模块 | 前端路径 | API 文件 | 后端路由 | 前端状态 | 后端状态 | 补全建议 |
|------|---------|---------|---------|---------|---------|---------|
| API Key 管理 | views/admin/ai/apikey/ | api/ai-apikey.ts | routers/ai/ai_api_key.py | ✅ 完整 | ✅ | 含 ChatModel 子表 + 模型测试 |
| MCP 服务 | views/admin/ai/mcp/ | api/ai-mcp.ts | routers/ai/ai_mcp.py | ✅ 完整(Tab) | ✅ | 我的 MCP + 广场 + 安装/卸载 |
| 技能管理 | views/admin/ai/skill/ | api/skill.ts + skillRule.ts | routers/ai/ai_skill*.py | ✅ 完整(Tab) | ✅ | 包+脚本+规则+Markdown+进化+仓库 |
| 工具管理 | views/admin/ai/tool/ | api/ai-tool.ts | routers/ai/ai_tool.py | ✅ 完整(Tab) | ✅ | 工具列表 + 分组 + 成员管理 |
| 工具调用策略 | views/admin/ai/components/ | api/voice.ts | routers/ai/(duplex) | ✅ 完整 | ✅ | 动态组件 voice-tool-policy |
| 联网搜索 | views/admin/ai/websearch/ | api/ai-web-search.ts | routers/ai/ai_web_search.py | ✅ 完整(Tab) | ✅ | 配置 + 配额 + 健康 + 日志 |

---

## 8.文档版本

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| 1.0.1 | 2026-09-16 | 补充 AI-14 工具调用策略管理模块(ToolPolicyEditor) | AI Agent |
| 1.0.0 | 2026-09-16 | 初始版本,覆盖 AI 服务全部 13 个模块 88 个测试场景 | AI Agent |

| 项目 | 值 |
|------|------|
| 适用服务 | AI 管理模块 |
| 前端入口 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| 默认账号 | admin / admin123 |
| 测试 Skill | `/qa`, `/qa-only`, `/open-gstack-browser`, MCP Playwright |
