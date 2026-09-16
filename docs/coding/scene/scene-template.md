# System 服务 — 端到端浏览器自动化测试 Skill

> 本文档为 AI 浏览器测试 Agent 提供完整的 System(系统管理)服务测试提示词。
> 使用 `/browser` 启动浏览器自动化测试,或使用 MCP Playwright 执行测试。
> 适用于 gstack `/qa` 和 `/qa-only` Skill,通过 `/open-gstack-browser` 导入认证 Cookie 后执行端到端测试。
> 文档同时包含问题自动定位与修复建议机制,支持端到端回归测试。

---

## 目录

- [1.测试前置条件](#测试前置条件)
- [2.全局测试策略](#全局测试策略)
- [3.Skill 调用方式](#skill-调用方式)
- [4.问题发现与自动修复流程](#问题发现与自动修复流程)
- [5.System 服务测试模块](#system-服务测试模块)
  - [SYS-01 参数配置](#sys-01-参数配置)
  - [SYS-02 字典管理](#sys-02-字典管理)
  - [SYS-03 通知公告](#sys-03-通知公告)
  - [SYS-04 站内信管理](#sys-04-站内信管理)
  - [SYS-05 文件管理](#sys-05-文件管理)
  - [SYS-06 文件配置管理](#sys-06-文件配置管理)
  - [SYS-07 邮件管理](#sys-07-邮件管理)
  - [SYS-08 短信管理](#sys-08-短信管理)
  - [SYS-09 操作日志](#sys-09-操作日志)
  - [SYS-10 我的站内信](#sys-10-我的站内信)
  - [SYS-11 站内信详情](#sys-11-站内信详情消息模板发送后详情)
  - [SYS-12 短信渠道管理(增强)](#sys-12-短信渠道管理增强)
  - [SYS-13 短信模板管理](#sys-13-短信模板管理)
  - [SYS-14 短信日志管理](#sys-14-短信日志管理)
  - [SYS-15 邮件账号管理](#sys-15-邮件账号管理)
  - [SYS-16 邮件模板管理](#sys-16-邮件模板管理)
  - [SYS-17 邮件日志管理](#sys-17-邮件日志管理)
  - [SYS-18 API 访问日志](#sys-18-api-访问日志)
  - [SYS-19 API 错误日志](#sys-19-api-错误日志)
  - [SYS-20 Redis 缓存监控](#sys-20-redis-缓存监控)
  - [SYS-21 数据源配置](#sys-21-数据源配置)
  - [SYS-22 Druid SQL 监控](#sys-22-druid-sql-监控)
  - [SYS-23 服务节点监控](#sys-23-服务节点监控)
  - [SYS-24 Swagger/API 文档](#sys-24-swaggerapi-文档)
- [6.测试结果报告模板](#测试结果报告模板)
- [7.模块开发对照与补全清单](#模块开发对照与补全清单)
- [8.文档版本]
  

---

## 1.测试前置条件

### 1.1 环境要求

| 项目 | 值 |
|------|------|
| 前端地址 | `http://localhost:5173` |
| 网关地址 | `http://localhost:8080` |
| System 服务 | `http://localhost:8082` |
| 超级管理员账号 | `admin` |
| 超级管理员密码 | `admin123` |
| 默认租户 ID | `1` |

### 1.2 服务依赖检查

测试前需确认以下服务已启动:

1. **Gateway**(:8080) — API 网关
2. **System**(:8082) — 系统公共服务
3. **MySQL/PostgreSQL** — 数据库
4. **Redis** — 缓存
5. **Nacos** — 服务注册中心

### 1.3 浏览器环境要求

- 浏览器:Chromium / Chrome(headless 模式或带 UI 模式均可)
- Cookie 导入:通过 `/open-gstack-browser` 导入已登录 Cookie,避免重复登录
- 如需手动登录:账号 `admin`,密码 `admin123`,租户 ID `1`

---

## 2.全局测试策略

### 2.1 模块列表:

| 模块 ID | 模块名称 | 测试场景数 | 说明 |
|---------|---------|-----------|------|
| SYS-01 | 参数配置 | 6 | CRUD + 唯一性校验 |
| SYS-02 | 字典管理 | 10 | 类型+数据双表 CRUD |
| SYS-03 | 通知公告 | 6 | CRUD + 富文本 |
| SYS-04 | 站内信管理 | 7 | 模板+消息+标记已读 |
| SYS-05 | 文件管理 | 11 | 列表/网格/预览/拖拽 |
| SYS-06 | 文件配置管理 | 8 | 配置 CRUD + 测试连接 |
| SYS-07 | 邮件管理 | 6 | 账号/模板/日志 Tab |
| SYS-08 | 短信管理 | 5 | 渠道/模板/日志 Tab |
| SYS-09 | 操作日志 | 5 | 查看 + 详情 |
| SYS-10 | 我的站内信 | 4 | 查看 + 标记已读 |
| SYS-11 | 站内信详情 | 3 | 详情弹窗 |
| SYS-12 | 短信渠道管理(增强) | 8 | 完整 CRUD |
| SYS-13 | 短信模板管理 | 9 | 完整 CRUD |
| SYS-14 | 短信日志管理 | 7 | 查看 + 详情 |
| SYS-15 | 邮件账号管理 | 8 | 完整 CRUD |
| SYS-16 | 邮件模板管理 | 9 | 完整 CRUD |
| SYS-17 | 邮件日志管理 | 7 | 查看 + 详情 |
| SYS-18 | API 访问日志 | 4 | 查看 + 导出 |
| SYS-19 | API 错误日志 | 7 | 查看 + 处理状态流转 |
| SYS-20 | Redis 缓存监控 | 4 | 仪表盘 + 图表 |
| SYS-21 | 数据源配置 | 6 | CRUD + 批量删除 |
| SYS-22 | Druid SQL 监控 | 1 | iframe 内嵌 |
| SYS-23 | 服务节点监控 | 1 | iframe 内嵌 |
| SYS-24 | Swagger/API 文档 | 1 | iframe 内嵌 |
| **合计** | **24 个模块** | **135 个场景** | **~8h 测试时间** |

### 2.2 每个测试用例的验证清单

1. **页面加载**:页面是否正常渲染,无白屏、无 JS 错误
2. **数据加载**:表格数据是否成功加载,loading 状态是否正确消失
3. **交互响应**:按钮点击是否有响应,弹窗是否正常弹出
4. **表单验证**:必填字段校验是否生效,错误提示是否显示
5. **数据回填**:编辑时已有数据是否正确回填到表单
6. **操作反馈**:成功/失败是否有 message 提示
7. **状态更新**:操作后列表数据是否自动刷新
8. **权限控制**:`v-has-permi` 指令是否正确控制按钮显隐
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
选择已登录的 mediation_platform 会话
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
/qa-only --tier exhaustive --scope "System服务-字典管理"
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
    - 权限码不匹配 → 对齐前后端权限标识
    - 表单初始值缺失 → 补充默认值
  → 修复后自动重新执行失败的测试用例
```

### 4.2 常见错误自动匹配表

| 浏览器现象 | 可能原因 | 检查文件 |
|-----------|---------|---------|
| 白屏 | 路由组件未注册 / import 路径错误 | `route-helper.ts`, `views/` |
| 表格无数据 | API 返回 code≠0 / 后端未启动 | `request.ts`, Network 面板 |
| 弹窗打不开 | `v-model:open` / `v-model:visible` 绑定问题 | 对应 FormModal.vue |
| 表单不回填 | watch 未监听 / props 延迟 | FormModal.vue 的 watch |
| 按钮不显示 | 权限码不匹配 | `access.ts`, 后端权限配置 |
| 401 错误 | Token 过期 / 刷新 Token 逻辑失败 | `request.ts`, `auth.ts` |
| 删除失败 | 外键约束 / 关联数据未清理 | 后端 Service |
| 分页异常 | pageNo/pageSize 参数不对 | API 请求参数 |
| 树形不展开 | `handleTree` 函数异常 | `menuTreeUtils.ts` |
| 表格列错位 | columns 定义顺序与数据不匹配 | index.vue 的 columns 定义 |
| DictTag 不显示 | 字典类型未注册 / 值为空 | `DictTag.vue`, 后端字典表 |

---

## 5.System 服务测试模块

---

### 5.1 SYS-01 参数配置

**页面路径**: 左侧菜单「系统管理」→「参数配置」  
**源码文件**: `src/views/system/config/index.vue`, `src/views/system/config/ConfigFormModal.vue`  
**API 文件**: `src/api/system/config.ts`  
**权限标识**: `system:config:create`, `system:config:update`, `system:config:delete`

#### 5.1.1 测试场景

#### 5.1.2 测试提示词

```
/qa 

前端：http://localhost:5173/  后端： http://localhost:8080

打开参数配置页面,执行完整的参数配置 CRUD 测试。

【前置操作】
1. 使用 admin/admin123 登录系统
2. 在左侧菜单点击「系统管理」→「参数配置」
3. 等待页面加载完成

---

【测试场景 1:列表加载与基础显示】
1. 验证参数列表正常加载
2. 检查列:参数名称、参数键名、参数键值、内置、参数类型、备注、创建时间、操作
3. 验证分页功能正常
4. 验证内置列使用 DictTag 标签(是=绿色/否=灰色)
5. 验证参数类型列显示(系统内置/自定义)

预期结果:
✅ 表格8列完整
✅ 内置 DictTag 正确
✅ 分页正常

---

【测试场景 2:搜索功能】
1. 在「参数名称」输入框输入关键词,点击「搜索」
2. 验证列表过滤出匹配参数名称的结果
3. 在「参数键名」输入框输入关键词,点击「搜索」
4. 验证列表过滤出匹配参数键名的结果
5. 点击「重置」,验证条件清空,列表恢复

预期结果:
✅ 参数名称搜索过滤正确
✅ 参数键名搜索过滤正确
✅ 重置清空条件

---

【测试场景 3:新增参数】
1. 点击顶部「新增」按钮
2. 验证 ConfigFormModal 弹窗弹出,标题为「新增参数」
3. 验证表单字段:
   - 参数名称(必填)
   - 参数键名(必填,唯一)
   - 参数键值(必填)
   - 参数类型(单选:系统内置/自定义)
   - 备注(可选)
4. 填写:
   - 参数名称:测试参数
   - 参数键名:test.param.key
   - 参数键值:test_value_001
   - 参数类型:自定义
   - 备注:自动化测试创建
5. 提交并验证:
   - API POST /admin-api/system/config/create
   - 显示「新增成功」
   - 弹窗关闭,列表刷新

预期结果:
✅ 新增弹窗表单字段完整
✅ 提交成功,列表刷新

---

【测试场景 4:编辑参数】
1. 点击刚创建参数的「编辑」按钮
2. 验证弹窗弹出,数据正确回填
3. 修改参数键值为 test_value_001_modified
4. 提交并验证更新

预期结果:
✅ 编辑弹窗正确回填
✅ 修改提交后数据更新

---

【测试场景 5:参数键名唯一性校验】
1. 新增参数,键名设为已存在的键名
2. 提交验证:后端返回重复错误
3. 弹窗不关闭

预期结果:
✅ 后端唯一性校验生效

---

【测试场景 6:删除参数】
1. 点击参数的「删除」按钮
2. 验证确认弹窗
3. 点击确认,验证删除成功
4. 验证列表刷新,参数消失

预期结果:
✅ 删除确认正常
✅ 删除成功后列表刷新

---

【API 端点对照】

| 操作 | API 方法 | 路径 |
|------|---------|------|
| 列表分页 | GET | /admin-api/system/config/page |
| 参数详情 | GET | /admin-api/system/config/get?id=X |
| 创建参数 | POST | /admin-api/system/config/create |
| 更新参数 | PUT | /admin-api/system/config/update |
| 删除参数 | DELETE | /admin-api/system/config/delete?id=X |

---

【问题诊断】
- 列表不加载 → 检查 configApi.page() 是否成功
- 编辑时数据不回填 → 检查 ConfigFormModal watch 逻辑
- 删除失败 → 检查参数是否被系统引用(后端保护)
```

#### 5.1.3 开发提示词



```
请基于以下信息,在 mediation-platform 仓库中实现【案件登记】模块。

【模块信息】
- 服务: Case(:8084)
- 页面路径: 左侧菜单「案件管理」→「案件登记」
- 路由: /case/register
- 权限前缀: case:
- 涉及权限码:
  - case:manage:create(新增案件)
  - case:manage:update(编辑案件)
  - case:manage:delete(删除案件)
  - case:manage:query(查询案件)

【前端文件清单】
- 主页面: mediation-web/src/views/case/register.vue
- API 封装: mediation-web/src/api/case/index.ts

【后端文件清单】
- Controller: mediation-platform-biz/mediation-module-case/mediation-module-case-server/src/main/java/com/tianque/module/medcase/controller/CaseController.java
- Service 接口: .../service/CaseService.java
- DTO/Request: .../dto/CaseRegisterRequest.java
- DO: .../dal/dataobject/CaseInfoDO.java
- Mapper: .../dal/mapper/CaseInfoMapper.java

【API 端点】
| 操作 | 方法 | 路径 |
|------|------|------|
| 提交案件 | POST | /admin-api/case/register |
| 获取详情 | GET | /admin-api/case/{id} |
| 列表分页 | GET | /admin-api/case/page |
| 编辑案件 | PUT | /admin-api/case/update |
| 删除案件 | DELETE | /admin-api/case/delete |
| 更新状态 | PUT | /admin-api/case/update-status |

【功能需求】
1. 支持案件登记表单,字段:案件标题、案件类型、申请人姓名/电话、被申请人姓名/电话、纠纷描述
2. 表单验证:案件标题必填、电话格式校验
3. 提交后调用 POST /admin-api/case/register,成功后跳转列表页
4. 案件类型使用 DictSelect(case_type 字典)
5. 提交失败时显示错误提示

【UI 规范】
- UI 库: ant-design-vue
- 表单字段:案件标题、案件类型、申请人姓名、申请人电话、被申请人姓名、被申请人电话、纠纷描述
- 字典类型: case_type(案件类型)
- 业务组件复用: DictSelect(来自 mediation-web/src/components/business)
- 操作按钮:提交案件、取消

【参考实现】
请参考以下已实现模块:
- mediation-web/src/views/system/dict/index.vue(字典管理,适合作为表单+下拉选择参考)
- mediation-web/src/views/system/notice/index.vue(通知公告,适合作为含富文本/多字段表单参考)
- 复用 mediation-web/src/components/business 中的 DictSelect 组件
- 字典数据从 case_type 字典类型读取

【测试验证】
实现完成后,使用 5.1.2 测试提示词中的测试场景验证,重点验证:
1. 表单 7 个字段完整渲染
2. 案件标题必填校验生效
3. DictSelect 案件类型下拉正常
4. 提交成功跳转列表页
5. 提交失败显示错误提示

【交付物清单】
- [ ] 前端主页面 .vue(register.vue)
- [ ] 前端 API 封装 .ts(含 TypeScript 类型)
- [ ] 后端 Controller(含 Swagger @Operation 注解)
- [ ] 后端 Service 接口 + 实现
- [ ] 后端 DTO / DO / Mapper
- [ ] 路由注册(/case/register)
- [ ] 菜单注册(左侧菜单「案件管理」→「案件登记」)
- [ ] 权限码注册(case:manage:create)
- [ ] 字典数据初始化 SQL(case_type)
- [ ] 通过 5.1.2 所有测试场景
```

---

*(注:SYS-02 到 SYS-24 的完整测试场景与 system-uaa-test.md 中一致,此处为保持文档精简省略重复内容。实际使用时可参考原文档或按需扩展)*

---


## 6.测试结果报告模板

```markdown
# System 服务测试报告

**测试日期**: YYYY-MM-DD  
**测试人员**: AI Agent (gstack /qa)  
**测试环境**: http://localhost:5173  
**System 服务**: http://localhost:8082

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
| SYS-01 参数配置 | 6 | 6 | 0 | 0 | 100% |
| SYS-02 字典管理 | 10 | 10 | 0 | 0 | 100% |
| SYS-03 通知公告 | 6 | 6 | 0 | 0 | 100% |
| SYS-04 站内信管理 | 7 | 7 | 0 | 0 | 100% |
| SYS-05 文件管理 | 11 | 10 | 1 | 0 | 90.9% |
| SYS-06 文件配置管理 | 8 | 8 | 0 | 0 | 100% |
| SYS-07 邮件管理 | 6 | 6 | 0 | 0 | 100% |
| SYS-08 短信管理 | 5 | 5 | 0 | 0 | 100% |
| SYS-09 操作日志 | 5 | 5 | 0 | 0 | 100% |
| **合计** | **N** | **X** | **Y** | **Z** | **X/N%** |

## 失败用例详情

### SYS-05 文件管理 — 测试场景 8:文件预览

- **现象**: 点击预览按钮后弹窗未显示
- **控制台错误**: `Component not found: FilePreviewModal`
- **截图**: [.gstack/qa-reports/screenshots/issue-003.png](.gstack/qa-reports/screenshots/issue-003.png)
- **定位**: `file/index.vue` 未正确导入 FilePreviewModal 组件
- **修复建议**: 在 components 中注册 FilePreviewModal
- **修复文件**: `src/views/system/file/index.vue`
- **状态**: 已修复

## 建议

1. **高优先级**:修复文件预览功能,影响用户体验
2. **中优先级**:增强邮件/短信管理的功能完整性
3. **低优先级**:引入 Infra 模块(API 日志、Redis 监控等)
4. **测试补充**:建议增加文件上传的边界测试(超大文件、非法类型)
```

---

## 7.模块开发对照与补全清单

本章节对照 tianque-ui(参考项目)与 mediation-platform(当前项目),梳理 System 模块的实现状态与补全建议。

### System 模块补全对照表

| 模块 | tianque-ui 路径 | mediation-platform 路径 | 前端状态 | 后端状态 | 补全建议 |
|------|-----------------|----------------------|---------|---------|---------|
| 参数配置 | system/config/index.vue | system/config/index.vue | ✅ 完整 | ✅ | 对齐:无明显差距 |
| 字典管理 | system/dict/index.vue + dict/data/ | system/dict/index.vue | ✅ 完整(子组件化) | ✅ | 已完成:DictTypeFormModal + DictDataFormModal 子组件 |
| 通知公告 | system/notice/index.vue | system/notice/index.vue | ✅ 完整(富文本) | ✅ | 已完成:NoticeFormModal 使用 wangeditor 富文本编辑器 |
| 站内信(消息模板) | system/notify/template/index.vue | system/notify/index.vue | ✅ 完整(Tab结构) | ✅ | 已完成:Tab 切换(模板/站内信) + NotifyTemplateFormModal |
| 站内信(消息列表) | system/notify/message/index.vue | system/notify/index.vue | ✅ 完整(详情弹窗) | ✅ | 已完成:NotifyMessageDetailModal + 标记已读 |
| 站内信(我的消息) | system/notify/my/index.vue | system/notify/my/index.vue | ✅ **已创建** | ✅ | 已完成:我的消息独立页面 + 铃铛入口 |
| 操作日志 | system/operatelog/index.vue | system/operatelog/index.vue | ✅ 完整(含详情弹窗) | ✅ | 已完成:详情弹窗集成在列表页内 |
| 登录日志 | system/loginlog/index.vue | uaa/loginLog/index.vue | ✅ 完整(含详情弹窗) | ✅ | 已完成:LoginLogDetailModal.vue |
| 邮件账号 | system/mail/account/index.vue | system/mail/index.vue | ✅ 完整(Tab结构) | ✅ | 当前已是完整 Tab 结构(账号/模板/日志) |
| 邮件模板 | system/mail/template/index.vue | system/mail/index.vue | ✅ 完整(Tab结构) | ✅ | 当前已是完整 Tab 结构 |
| 邮件日志 | system/mail/log/index.vue | system/mail/index.vue | ✅ 完整(Tab结构) | ✅ | 当前已是完整 Tab 结构 |
| 短信渠道 | system/sms/channel/index.vue | system/sms/index.vue | ✅ 完整(Tab结构) | ✅ | 当前已是完整 Tab 结构(渠道/模板/日志) |
| 短信模板 | system/sms/template/index.vue | system/sms/index.vue | ✅ 完整(Tab结构) | ✅ | 当前已是完整 Tab 结构 |
| 短信日志 | system/sms/log/index.vue | system/sms/index.vue | ✅ 完整(Tab结构) | ✅ | 当前已是完整 Tab 结构 |
| 文件管理 | infra/file/index.vue | system/file/index.vue | ✅ 完整(列表+网格+预览+拖拽上传) | ✅ | 当前文件管理较 tianque-ui 更完善 |
| 文件配置 | infra/file/FileForm.vue | system/file/FileConfigFormModal.vue | ✅ 完整(测试连接+主配置+复制) | ✅ | 当前文件配置较 tianque-ui 更完善 |


## 8.文档版本

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| 1.0.0 | 2026-06-14 | 从 system-uaa-test.md 拆分,仅保留 System 服务测试模块 | AI Agent |

| 项目 | 值 |
|------|------|
| 适用服务 | System(:8082) |
| 前端入口 | http://localhost:5173 |
| 默认账号 | admin / admin123 |
| 默认租户 ID | 1 |
| 测试 Skill | `/qa`, `/qa-only`, `/open-gstack-browser`, MCP Playwright |
