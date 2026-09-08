import path from 'node:path'
import { app, BrowserWindow, Menu, shell, ipcMain, screen } from 'electron'
import type { AppConfig } from '../shared/ipc'
import { IPC } from '../shared/ipc'
import { getConfig, setConfig } from './config'
import { startStaticServer } from './server'
import type { StaticServer } from './server'

/**
 * MiniWorkBuddy 桌面端主进程。
 *
 * 开发态：加载 scripts/electron.cjs 传入的 VITE_DEV_SERVER_URL（Vite dev server）。
 * 生产态：内置静态服务器承载 dist/，通过 http://127.0.0.1:<随机端口> 加载。
 */

const isDev = !app.isPackaged
const APP_ID = 'com.miniworkbuddy.desktop'

let mainWindow: BrowserWindow | null = null
let staticServer: StaticServer | null = null

/** 渲染层根路径：dist-electron/main/index.js -> ../../dist */
function rendererRoot(): string {
  return path.join(__dirname, '..', '..', 'dist')
}

function preloadPath(): string {
  return path.join(__dirname, '..', 'preload', 'index.js')
}

function registerIpc(getOrigin: () => string) {
  ipcMain.handle(IPC.APP_VERSION, () => app.getVersion())
  ipcMain.handle(IPC.SERVER_ORIGIN, () => getOrigin())

  ipcMain.handle(IPC.CONFIG_GET, (): AppConfig => getConfig())
  ipcMain.handle(IPC.CONFIG_SET, (_evt, patch: Partial<AppConfig>): AppConfig => setConfig(patch))

  ipcMain.handle(IPC.WIN_MINIMIZE, () => mainWindow?.minimize())
  ipcMain.handle(IPC.WIN_TOGGLE_MAXIMIZE, () => {
    if (!mainWindow) return
    if (mainWindow.isMaximized()) mainWindow.unmaximize()
    else mainWindow.maximize()
  })
  ipcMain.handle(IPC.WIN_CLOSE, () => mainWindow?.close())
  ipcMain.handle(IPC.WIN_IS_MAXIMIZED, () => mainWindow?.isMaximized() ?? false)

  ipcMain.handle(IPC.SHELL_OPEN_EXTERNAL, async (_evt, url: string) => {
    if (typeof url === 'string' && /^https?:\/\//i.test(url)) {
      await shell.openExternal(url)
    }
  })

  ipcMain.on(IPC.APP_QUIT, () => app.quit())
}

async function createWindow() {
  const devServerUrl = process.env.VITE_DEV_SERVER_URL

  let origin = ''
  if (isDev && devServerUrl) {
    origin = devServerUrl.replace(/\/+$/, '')
  } else {
    staticServer = await startStaticServer(rendererRoot())
    origin = staticServer.origin
  }

  const workArea = screen.getPrimaryDisplay().workAreaSize
  const win = new BrowserWindow({
    width: Math.min(1440, Math.max(1100, workArea.width - 120)),
    height: Math.min(900, Math.max(720, workArea.height - 100)),
    minWidth: 1024,
    minHeight: 680,
    show: false,
    title: 'MiniWorkBuddy',
    autoHideMenuBar: true,
    backgroundColor: '#0d1117',
    webPreferences: {
      preload: preloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      spellcheck: false,
      devTools: isDev || process.env.ELECTRON_ENABLE_DEVTOOLS === '1',
    },
  })

  mainWindow = win

  win.once('ready-to-show', () => {
    win.show()
    if (isDev) win.focus()
  })

  const notifyMaximized = (maximized: boolean) => {
    if (!win.isDestroyed()) win.webContents.send(IPC.WIN_MAXIMIZE_CHANGED, maximized)
  }
  win.on('maximize', () => notifyMaximized(true))
  win.on('unmaximize', () => notifyMaximized(false))

  // 外链一律交给系统浏览器
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })
  win.webContents.on('will-navigate', (event, url) => {
    if (url.startsWith(origin) || url.startsWith('devtools://')) return
    event.preventDefault()
    if (/^https?:\/\//i.test(url)) void shell.openExternal(url)
  })

  // 桌面端快捷键：F12 / Ctrl+Shift+I 打开 DevTools
  win.webContents.on('before-input-event', (_event, input) => {
    if (input.type !== 'keyDown') return
    const isF12 = input.key === 'F12'
    const isInspect = input.control && input.shift && input.key.toLowerCase() === 'i'
    if (isF12 || isInspect) win.webContents.toggleDevTools()
  })

  await win.loadURL(`${origin}/`)
}

function bootstrap() {
  // 单实例：再次启动时聚焦已有窗口
  if (!app.requestSingleInstanceLock()) {
    app.quit()
    return
  }
  app.on('second-instance', () => {
    if (!mainWindow) return
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  })

  if (process.platform === 'win32') app.setAppUserModelId(APP_ID)

  // 桌面端不需要默认菜单栏（Alt 仍可呼出）
  Menu.setApplicationMenu(null)

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow()
  })

  app.on('before-quit', () => {
    void staticServer?.close()
    staticServer = null
  })

  void app.whenReady().then(createWindow)
}

registerIpc(() => staticServer?.origin ?? process.env.VITE_DEV_SERVER_URL ?? '')
bootstrap()
