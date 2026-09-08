/**
 * 渲染层使用的桌面端类型契约。
 *
 * 接口本体定义在 electron/shared/ipc.ts（主进程与预加载脚本共用），
 * 这里只做再导出 + 挂到 window，避免两边定义漂移。
 */
import type { ElectronAPI } from '../../electron/shared/ipc'

export type { AppConfig, ElectronAPI } from '../../electron/shared/ipc'

declare global {
  interface Window {
    /** 仅桌面端存在；浏览器环境为 undefined */
    electronAPI?: ElectronAPI
  }
}
