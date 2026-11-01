# WorkBuddy RPA 改造方案：接管用户本地已授权浏览器

> 状态：方案设计稿（2026-11-01）
> 范围：将现有服务端 headless Playwright 浏览器工具，升级为「AI 对话授权后接管用户本地已登录浏览器」的 RPA 能力。
> 前置阅读：`backend/app/ai/tool_manager/browser_tools.py`、`backend/app/ai/events/hitl.py`、`frontend/src/views/assistant/components/HitlConfirmPanel.vue`

---

## 1. 现状与目标

### 1.1 现有实现链路

当前"AI 对话 → 授权 → 浏览器自动操作"的完整链路：

```
用户对话 → LLM 规划出 browser_automation 调用
  → 只读动作(navigate/extract/screenshot)? 直接执行(Playwright headless)
  → 写操作(click/fill)? PermissionBehavior.ASK
  → Agent 挂起 + agent_hitl_pause 落库 + SSE 推 hitl_pause
  → 前端 HitlConfirmPanel 确认面板 → 用户 approve/reject → /confirm API
  → 注入 UserConfirmResultEvent → Agent 续跑 → Playwright 执行/跳过
```

涉及的核心资产：

| 层 | 文件 | 职责 |
|---|---|---|
| 工具 | `backend/app/ai/tool_manager/browser_tools.py` | `BrowserAutomation(ToolBase)`，5 个原子动作，headless Chromium |
| 权限 | 同上 `check_permissions()` | 只读 ALLOW / 写操作 ASK |
| HITL | `backend/app/ai/events/hitl.py` | 暂停记录、`/confirm` 恢复（`UserConfirmResultEvent` / `UserInterruptEvent`）、30 分钟超时监控 |
| 事件 | `backend/app/ai/events/bus.py`（EventBus） | `EventEnvelope` SSE 推送，`ui_hint` 路由 |
| 前端 | `frontend/src/stores/agentEvents.ts`、`HitlConfirmPanel.vue`、`AgentEventStream.vue` | `hitl_pause` 事件 → 确认面板 → `/api/v1/agents/executions/{id}/confirm` |
| 注册 | `backend/app/ai/tool_manager/manager.py` + `AiToolDefinition` 表 | DB 驱动、`class_name` 动态导入装配 Toolkit |

### 1.2 现状局限

1. **无用户会话**：headless 每次 `browser.new_context()` 都是全新会话，无法操作需要登录态的第三方页面；
2. **选择器盲猜**：元素定位靠 LLM 直接猜 CSS 选择器，没有"页面快照回喂模型"的感知环，复杂动态页面（React 虚拟列表、iframe、验证码）成功率低；
3. **操作对象错位**：AI 操作的是服务端隐形浏览器，不是用户正在看的那个页面，无法做到"帮我在当前页面上填这个表"。

### 1.3 目标

让 AI 在用户明确授权后，**接管用户本地已登录的浏览器标签页**执行导航/读取/点击/填写/截图，并保留现有 HITL 人工确认、SSE 事件流、审计与紧急停止能力。

---

## 2. 核心架构问题与选型

后端服务器无法直接访问用户机器上的 Chrome：CDP 端口监听在用户的 `127.0.0.1`，远程暴露 9222 等于把浏览器裸奔权限交给全网。**必须由用户侧主动向外建立一条可信通道**。按部署场景分别选型：

| 场景 | 方案 | 通道 |
|---|---|---|
| **Web 端（主场景，推荐）** | Chrome 扩展 + `chrome.debugger`（官方扩展侧 CDP 封装） | 扩展**反向 WS** 连后端 `/api/v1/browser-bridge/ws`，一次性配对码授权绑定 |
| Electron 桌面端 | `webContents.debugger`（同属 CDP 协议域）直控内置浏览器，或 `connect_over_cdp` 外接用户 Chrome | 本机 IPC，免网络通道、免装扩展 |
| 单机/内网自托管 | 用户以 `--remote-debugging-port=9222` 启动 Chrome，后端 Playwright `connect_over_cdp("http://127.0.0.1:9222")` | 复用 Playwright 全部 API，改造量最小 |

三者共用同一套 **BrowserKernel 抽象 + 会话/权限/审计层**，差异仅在"命令如何送达浏览器"。

### 方案对比

| 维度 | 扩展 + WS Bridge（推荐主线） | connect_over_cdp 直连 |
|---|---|---|
| 跨网络（云端后端 ↔ 用户本机） | ✅ 出站 WS，天然穿透 NAT/防火墙 | ❌ 后端须与浏览器同机/同内网 |
| 安全边界 | ✅ 配对码 + token + origin 白名单 + 扩展策略层 | ⚠️ 9222 端口无鉴权，暴露即沦陷 |
| 感知能力 | ✅ 可扩展 `chrome.tabs`/`scripting` 补充 CDP | ✅ Playwright 完整 API |
| 用户成本 | 需安装扩展并配对 | 需带命令行参数重启 Chrome |
| 紧急停止 | ✅ 扩展注入悬浮条 + Esc | ❌ 仅能靠后端断开 |

结论：**主线走扩展 + WS Bridge**；`connect_over_cdp` 作为单机部署与 Electron 的轻量替代内核；headless 保留为无绑定设备时的回退路径。

---

## 3. 后端改造

### 3.1 抽出 BrowserKernel，工具签名不动

现在 `BrowserAutomation.call()` 把"启动 headless Chromium"写死。改造为内核选择：

```
backend/app/ai/tool_manager/browser_kernel/
├── __init__.py
├── base.py       # BrowserKernel Protocol：snapshot / navigate / click / fill / extract / screenshot
├── headless.py   # HeadlessPlaywrightKernel —— 迁移现有 Playwright 逻辑（保底路径，行为不变）
├── bridge.py     # BridgeKernel —— 命令以 JSON-RPC 消息经 WS 派发给用户浏览器扩展
└── cdp.py        # CdpKernel —— Playwright connect_over_cdp 直连（单机/Electron 场景）
```

`BrowserAutomation` 保留 `name / description / input_schema / check_permissions` 不变（HITL 全流程零改动），`call()` 内部改为：

1. 从执行上下文取 `user_id`（`RunHandle` 已携带，见 `backend/app/ai/events/registry.py`）；
2. 查该用户是否有**在线 bridge 会话**：
   - 有 → `BridgeKernel`（接管用户本地浏览器，天然继承其全部 Cookie/登录态）；
   - 无 → 回退 `HeadlessPlaywrightKernel`（保持现行为，向后兼容）；
3. 内核调用失败（设备中途离线、命令超时）→ 结果以结构化 error 返回，LLM 在 ReAct 循环内自行决定重试或改道。

### 3.2 新增桥接服务

参考 `backend/app/duplex/voice/websocket_gateway.py` 的既有 WS 网关经验：

```
backend/app/services/browser_bridge/
├── registry.py     # user_id -> WebSocket 连接池（在线设备表），心跳保活与掉线清理
├── dispatcher.py   # command_id ↔ asyncio.Future 关联、超时控制、结果回传
├── protocol.py     # 消息信封：cmd / req_id / payload / ok / error / event
└── pairing.py      # 配对码签发与消费（一次性、5 分钟过期、绑定用户与设备名）

backend/app/routers/agent/browser_bridge.py
# REST：申请配对码 / 设备列表 / 在线状态 / 解绑；WS：/ws 长连接端点（token 鉴权）
```

路由注册进 `backend/app/routers/agent/__init__.py`，鉴权复用 `app/deps.py` 现有 JWT 依赖。

### 3.3 桥接协议（命令集）

扩展侧基于 `chrome.debugger` 转发 CDP domain：

| 命令 | CDP 实现 | 权限级 | 说明 |
|---|---|---|---|
| `page.snapshot` | `DOM.getDocument` + `Accessibility.getFullAXTree`，裁剪为带 `ref` 编号的紧凑文本 | 只读 | **新增关键能力**：把"可交互元素列表 + 语义 ref"回喂 LLM，替代盲猜 CSS 选择器 |
| `page.navigate` | `Page.navigate` | 接管模式下建议 ASK（见 §3.4） | |
| `element.click` | 按 `ref` 解析 `backendNodeId` → `Input.dispatchMouseEvent`，`Runtime.callFunctionOn` 兜底 | ASK | 授权后执行 |
| `form.fill` | `Input.insertText` / `Runtime.callFunctionOn` | ASK | 授权后执行 |
| `page.extract` | `DOM.getOuterHTML` / `Runtime.evaluate` | 只读 | |
| `page.screenshot` | `Page.captureScreenshot` | 只读 | 结果推 SSE 供前端展示 + 落审计 |

推荐 LLM 工作流升级为闭环：`snapshot → 按 ref 操作 → screenshot 验证`（相应更新工具的 `input_schema`，新增 `mode` 与 `ref` 参数）。

### 3.4 权限与安全（在现有 HITL 之上加薄层）

- **绑定即第一道授权**：扩展用一次性配对码换取 scoped token；`BridgeKernel` 严格按 `执行归属 user_id → 该用户在线设备` 路由，杜绝跨用户操作他人浏览器。
- **HITL 分级升级**：保留现有"只读 ALLOW / click·fill ASK"基线；当目标落到用户真实浏览器（`mode=local`）时，风险等级整体上调——导航类动作也建议 ASK（操作的是用户本人账号会话），确认面板内容替换为：**目标 tab 标题 + URL + snapshot 摘要 + 即将执行的动作**。
- **紧急停止**：扩展向被控页面注入悬浮条「🤖 AI 正在控制此标签页 [Esc 停止]」（shadow-DOM 隔离，防被页面脚本摘除）；Esc 或面板"中断"按钮 → 前端调现有 `/confirm` 端点 `action=interrupt` → `resume_hitl()` 走 `UserInterruptEvent`，**零新增后端恢复代码**。
- **域白名单**：配对时用户勾选允许 AI 操作的 origin 列表，后端与扩展双侧校验（后端拦截为准，扩展校验为快），防止 prompt injection 把 AI 引到钓鱼站点。
- **审计落库**：每条实际执行的命令记录（execution_id、cmd、payload 摘要、screenshot_path、approve/reject 结果、耗时）。

### 3.5 数据模型（alembic 迁移）

新增两张表，模型放 `backend/app/models/agent/`，迁移脚本放 `backend/alembic/versions/`（遵循 `backend/MIGRATIONS.md` 流程）：

- `browser_bridge_device`：用户绑定的扩展设备（user_id、设备名、UA、配对时间、最后在线时间、origin 白名单 JSON、状态）；
- `browser_bridge_audit`：命令执行审计（见 §3.4）。

### 3.6 工具注册

`AiToolDefinition` 是 DB 驱动 + `class_name` 动态导入（`manager.py::_instantiate_tool`）。`BrowserAutomation` 类路径不变，仅需：

- 更新 DB 定义的 `description` / `config_value`（如 `{"fallback": "headless"}`）；
- `input_schema` 补 `mode`（`auto` / `headless` / `local`）与 `ref` 参数；
- 无需改动 `build_toolkit` 装配逻辑。

---

## 4. Chrome 扩展（新建 `browser-extension/`）

MV3 工程骨架：

```
browser-extension/
├── manifest.json               # permissions: debugger, tabs, scripting, storage, alarms
├── background/
│   ├── service-worker.js       # 生命周期、重连调度（alarms 保活）
│   ├── ws-client.js            # 反向连后端 WS，断线重连 + 心跳，配对 token 存 chrome.storage
│   ├── dispatcher.js           # 消息路由到 cdp-session / policy
│   ├── cdp-session.js          # chrome.debugger.attach/detach，按 tabId 管理 session，命令转发
│   ├── overlay.js              # 控制态悬浮条 + 动作目标高亮 + Esc 停止
│   └── policy.js               # origin 白名单 + target 过滤 +（可选）敏感站点转手动
├── popup/                      # 配对界面（输入配对码）、在线状态、白名单管理、本次会话命令流水
└── options/                    # 全量设置
```

要点：

1. `chrome.debugger` 即官方提供的"扩展内 CDP"，detach 后 Chrome 顶部调试横幅消失；接管期横幅本身是一层天然透明提示，需在用户文档说明属正常现象；
2. **禁止 attach** 扩展自身页面、`chrome://` 内部页与 Web Store——`policy.js` 做 target 过滤；
3. `page.snapshot` 的 DOM/AX 树裁剪在扩展内先做初筛（只留可交互节点），避免整棵 DOM 过 WS 撑爆消息体积；
4. 同一 tab 同时只允许一个调试 session；切换 tab 接管前先 `detach`。

---

## 5. 前端改造（Web 控制台）

| 文件 | 改动 |
|---|---|
| `frontend/src/api/browserBridge.ts`（新） | 配对码申请、设备列表、在线状态轮询、解绑 |
| 设置页新增「本地浏览器」卡片 | 展示配对码 + 扩展安装指引 + 已绑定设备与在线状态（复用现有 SSE 通道推送上下线事件） |
| `frontend/src/views/assistant/components/HitlConfirmPanel.vue` | confirm 事件 payload 增加 tab 标题、目标 URL、动作预览、snapshot 摘要；新增「中断控制」按钮（发 `interrupt`） |
| `frontend/src/stores/agentEvents.ts` / `AgentEventStream.vue` | 渲染 `browser_command_executed` / `browser_screenshot` 新事件类型（复用 `EventEnvelope` + `ui_hint` 路由机制，store 逻辑基本不动） |

---

## 6. Electron 桌面端（低成本增强，可后置）

`frontend/electron/main/` 增加 `browserControl` 模块：

- 路径 A：在本机拉起带 `--remote-debugging-port` 的 Chrome 并探测端口，向后端注册为 `CdpKernel` 设备；
- 路径 B：直接用 Electron 内置窗口 `webContents.debugger`（同 CDP 协议域）开一个「AI 操作视图」。

后端将 `CdpKernel` 的端点来源接入 `browser_bridge` 配对流程（Electron 启动时注册本机 CDP 端点），桌面端即可免装扩展获得同等能力。

---

## 7. 实施分期

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **P0 内核抽象 + CDP 直连** | 抽 `BrowserKernel`；现有 headless 逻辑迁移为 `HeadlessPlaywrightKernel`；实现 `CdpKernel`（`connect_over_cdp`） | 单机跑通接管本地已登录 Chrome；现有浏览器工具全部测试无回归（kernel 单测补齐） |
| **P1 扩展 + WS Bridge（读通道）** | 配对/注册/心跳/解绑；`navigate / screenshot / extract` 只读接管；审计落库 | Web 端用户配对后，AI 对话可截回用户真实页面并抓取内容 |
| **P2 写操作 + snapshot 闭环** | `page.snapshot` 回喂 LLM；`click / fill` 按 ref 执行；HITL 面板升级；Esc 中断；origin 白名单 | 授权流全链路走通；AI 能以 ref 精准操作真实页面表单 |
| **P3 Electron 免扩展直连 + 多实例** | 桌面端 browserControl；bridge 注册表跨实例化（Redis pub/sub） | 桌面端免装扩展可用；多后端副本下 WS 路由正确 |

P0 不依赖扩展与 WS，风险最小且是后续所有阶段的地基，建议优先开工。

---

## 8. 关键风险声明

1. **WS 连接粘性与进程内单例冲突**：`RunHandle` / HITL 暂停句柄本就是单进程内存态（`backend/app/ai/events/registry.py`），bridge 注册表同样受多副本部署限制。当前单后端部署无碍；要上多副本，需把"命令派发→结果回传"改走 Redis pub/sub——这与 HITL resume 的跨实例问题是同一个前置工程，应合并解决。
2. **prompt injection 风险放大**：接管真实登录浏览器意味着 AI 能以用户身份执行转账/发帖等不可逆操作。§3.4 的域白名单 + 全程 HITL + 审计**不是可选项，是上线门槛**。
3. **感知带宽仍然有限**：snapshot 文本 + 截图回传是当前方案的感知上限；验证码、强反自动化站点（指纹检测 `chrome.debugger`）不在射程内，需在产品预期中明确。
4. **扩展审核与分发**：企业内部署可走组策略/侧载（crx），公网分发需过 Chrome Web Store 审核，`debugger` 权限的审核描述需要提前准备。

---

## 9. 一句话总结

保留 `BrowserAutomation` 工具与 HITL 授权流不动，在其下抽出 `BrowserKernel` 三实现（headless 回退 / WS 扩展桥 / CDP 直连）；用户侧由 Chrome 扩展以配对码反向建立 WS 可信通道，AI 通过 `snapshot(ref) → 授权 → click/fill → screenshot 验证` 闭环接管用户本人已登录浏览器，配套 origin 白名单、悬浮条紧急停止与全量审计。
