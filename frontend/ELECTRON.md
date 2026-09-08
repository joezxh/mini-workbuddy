# MiniWorkBuddy 桌面端（Electron）

前端在保留原有 Web / Docker 部署方式的前提下，新增了桌面端（Windows / macOS / Linux）构建能力。
新增内容全部位于 `electron/`、`scripts/electron.cjs`、`electron-builder.yml`，**不影响** `npm run dev` 与 `npm run build`。

## 快速开始

```bash
cd frontend

# 1. 安装依赖（会额外下载 Electron 运行时，约 150MB，仅首次）
npm install

# 2. 桌面端开发：Vite dev server + Electron，渲染层改动的 HMR 与 Web 端一致
npm run electron:dev

# 3. 构建当前平台安装包，产物在 release/<version>/
npm run electron:build

# 指定平台
npm run electron:build:win
npm run electron:build:mac     # 需在 macOS 上构建（或配置 CI）
npm run electron:build:linux

# 只产出未打包目录（排查文件遗漏时很有用）
node scripts/electron.cjs build --dir

# 用已有的 dist/ 直接启动桌面端，不打包（跳过构建，秒开）
npm run electron:preview
```

## 目录结构

```
frontend/
├── electron/                    # 桌面端源码（TypeScript，由 tsc 编译到 dist-electron/）
│   ├── main/
│   │   ├── index.ts             # 主进程：窗口、单实例、IPC、生命周期
│   │   ├── config.ts            # 后端地址等配置（持久化到 userData/app-config.json）
│   │   └── server.ts            # 承载 dist/ 的本地静态服务器（仅打包后使用）
│   ├── preload/index.ts         # contextBridge 白名单 API
│   ├── shared/ipc.ts            # 主进程 / 预加载 / 渲染层共享的 IPC 契约
│   ├── resources/               # 打包资源（图标）目录
│   └── tsconfig.json            # CommonJS 输出
├── electron-builder.yml         # 打包配置（nsis / portable / dmg / AppImage / deb）
├── scripts/electron.cjs         # dev / preview / build 统一入口
└── src/
    ├── types/electron.ts        # 复用 electron/shared/ipc.ts 的类型，挂载 window.electronAPI
    ├── utils/electron.ts        # 桌面端环境探测与能力访问
    ├── utils/apiBase.ts         # 后端地址解析 + fetch/XHR/EventSource 改写
    └── layouts/components/ElectronServerButton.vue   # 顶栏「后端服务地址」入口
```

## 运行机制

| 场景 | 渲染层来源 | 说明 |
|------|-----------|------|
| `npm run electron:dev` | Vite dev server（`VITE_DEV_SERVER_URL`） | 与浏览器开发体验一致，`/api` 由 Vite proxy 代理 |
| 打包后 / `electron:preview` | 内置静态服务器 `http://127.0.0.1:<随机端口>` | 主进程用 `node:http` 直接服务 `dist/`，带 SPA 回退与 Range 支持 |

### 为什么打包后不用 `file://` 直接打开 dist

- `file://` 页面无法 `pushState`，history 路由（当前项目用的就是 history 模式）会失效；
- `file://` 下 Web Worker / PDF 预览（`@file-viewer`）会被同源策略拦截；
- 走 `http://127.0.0.1` 后，渲染层与浏览器里运行的语义完全一致，无需为桌面端改造业务代码。

静态服务器只监听回环地址、端口由系统分配，不对外暴露。

## 后端地址配置

桌面端**不烘焙**后端地址（构建时 `VITE_API_BASE_URL` 置空），地址在运行时从主进程读取：

1. 首次启动默认 `http://localhost:8000`；
2. 可在顶栏「后端服务地址」按钮中修改，保存到 `%APPDATA%/MiniWorkBuddy/app-config.json`
   （macOS：`~/Library/Application Support/MiniWorkBuddy`，Linux：`~/.config/MiniWorkBuddy`）；
3. 保存后自动重载页面，无需重新打包；升级安装包也不会丢失。

构建时想改默认值：

```bash
ELECTRON_DEFAULT_API_BASE_URL=http://192.168.1.10:8000 npm run electron:build
```

渲染层的改写逻辑（`src/utils/apiBase.ts`）只作用于以 `/api` 开头的相对路径，
静态资源、第三方绝对地址请求不受影响；`axios` 实例的 `baseURL` 会随地址变化同步更新。

> 跨域：桌面端页面同源是 `http://127.0.0.1:<端口>`，请求会带 `Origin` 头发往后端的其他地址，
> 需要后端 CORS 放行。项目默认 `CORS_ORIGINS=*`（见 `backend/app/config.py`），
> 若改成白名单，请把 `http://127.0.0.1` 加进去。

## 安全约定

- 渲染进程 `nodeIntegration: false` + `contextIsolation: true`，只通过 `preload` 暴露白名单 IPC；
- 外链一律交给系统浏览器，禁止在应用窗口内导航到站外；
- 打包产物中不含 `node_modules`（主进程只依赖 Electron 内建模块与 Node 内建模块）。

## 自定义图标

把图标放到 `electron/resources/`，再取消 `electron-builder.yml` 中对应平台 `icon` 的注释：

| 平台 | 文件 | 要求 |
|------|------|------|
| Windows | `icon.ico` | ≥ 256x256，建议多尺寸 |
| macOS | `icon.icns` | 1024x1024 |
| Linux | `icon.png` | 512x512 |

未提供图标时使用 Electron 默认图标，打包不会失败。可由 `public/brand/logo-icon.svg` 导出。

## 常见问题

**1. `Electron failed to install correctly` / `ENOSPC`**
Electron 运行时没下载成功（多为磁盘空间不足或网络问题）。清理空间后执行：

```bash
rm -rf node_modules/electron
npm install electron --force
```

也可设置镜像：`ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm install`。

**2. 打开是白屏**
说明 `dist/index.html` 缺失。打包流程会自动构建渲染层；`npm run electron:preview` 需要你先跑一次
`npm run electron:build` 或 `npm run build`。

**3. 登录一直失败 / 网络错误**
先在顶栏（或登录页左下角悬浮按钮）确认「后端服务地址」，再确认后端已启动且 CORS 允许
`http://127.0.0.1` 来源。

**4. 主进程代码改了没生效**
`npm run electron:dev` 会用 `tsc --watch` 持续编译主进程，但 Electron 需要手动关掉重启。

**5. 打包体积**
`dist/` 含 PDF 预览等静态资源，安装包通常在 150MB 量级，属正常范围。
