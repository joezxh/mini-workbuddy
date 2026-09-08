/**
 * 主进程 / 预加载脚本 / 渲染进程三方共享的 IPC 契约。
 *
 * 该目录同时被 tsc 编译进 dist-electron，供 main 与 preload 使用；
 * 渲染层通过 src/types/electron.ts 中同名接口获得类型提示。
 */

/** IPC 通道名常量，避免主进程与预加载脚本两边手写字符串出错。 */
export const IPC = {
  APP_VERSION: 'app:version',
  SERVER_ORIGIN: 'app:server-origin',
  CONFIG_GET: 'config:get',
  CONFIG_SET: 'config:set',
  WIN_MINIMIZE: 'window:minimize',
  WIN_TOGGLE_MAXIMIZE: 'window:toggle-maximize',
  WIN_CLOSE: 'window:close',
  WIN_IS_MAXIMIZED: 'window:is-maximized',
  WIN_MAXIMIZE_CHANGED: 'window:maximize-changed',
  SHELL_OPEN_EXTERNAL: 'shell:open-external',
  APP_QUIT: 'app:quit',
} as const

/** 持久化在 `userData/app-config.json` 中的客户端配置。 */
export interface AppConfig {
  /** 后端 API 根地址，例如 `http://192.168.1.10:8000`（不要以 / 结尾） */
  apiBaseUrl: string
}

/** 通过 contextBridge 暴露到渲染进程 `window.electronAPI` 的能力集合。 */
export interface ElectronAPI {
  /** 渲染层判断运行环境的可靠标记 */
  readonly isElectron: true
  /** win32 | darwin | linux */
  readonly platform: string

  appVersion(): Promise<string>
  /** 内置静态服务器的 origin（开发态为 Vite dev server） */
  serverOrigin(): Promise<string>

  getConfig(): Promise<AppConfig>
  setConfig(patch: Partial<AppConfig>): Promise<AppConfig>

  windowMinimize(): Promise<void>
  windowToggleMaximize(): Promise<void>
  windowClose(): Promise<void>
  isWindowMaximized(): Promise<boolean>
  onWindowMaximizeChanged(cb: (maximized: boolean) => void): () => void

  openExternal(url: string): Promise<void>
  quit(): void
}
