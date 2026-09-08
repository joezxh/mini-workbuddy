import { contextBridge, ipcRenderer } from 'electron'
import { IPC } from '../shared/ipc'
import type { AppConfig, ElectronAPI } from '../shared/ipc'

/**
 * 预加载脚本：只通过 contextBridge 暴露白名单能力，
 * 渲染进程保持 nodeIntegration=false，避免把 Node 全量能力暴露给页面。
 */

const api: ElectronAPI = {
  isElectron: true,
  platform: process.platform,

  appVersion: () => ipcRenderer.invoke(IPC.APP_VERSION),
  serverOrigin: () => ipcRenderer.invoke(IPC.SERVER_ORIGIN),

  getConfig: () => ipcRenderer.invoke(IPC.CONFIG_GET),
  setConfig: (patch: Partial<AppConfig>) => ipcRenderer.invoke(IPC.CONFIG_SET, patch),

  windowMinimize: () => ipcRenderer.invoke(IPC.WIN_MINIMIZE),
  windowToggleMaximize: () => ipcRenderer.invoke(IPC.WIN_TOGGLE_MAXIMIZE),
  windowClose: () => ipcRenderer.invoke(IPC.WIN_CLOSE),
  isWindowMaximized: () => ipcRenderer.invoke(IPC.WIN_IS_MAXIMIZED),

  onWindowMaximizeChanged: (cb) => {
    const listener = (_evt: unknown, maximized: boolean) => cb(maximized)
    ipcRenderer.on(IPC.WIN_MAXIMIZE_CHANGED, listener)
    return () => {
      ipcRenderer.removeListener(IPC.WIN_MAXIMIZE_CHANGED, listener)
    }
  },

  openExternal: (url: string) => ipcRenderer.invoke(IPC.SHELL_OPEN_EXTERNAL, url),
  quit: () => ipcRenderer.send(IPC.APP_QUIT),
}

contextBridge.exposeInMainWorld('electronAPI', api)
