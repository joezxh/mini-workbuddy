/**
 * 桌面端环境探测与能力访问。
 *
 * 渲染层所有对 Electron 的依赖都必须走这里，保证：
 *   - 浏览器 / Docker 部署时零副作用（isElectron 为 false，函数安全返回 undefined）
 *   - 只有 window.electronAPI 存在时才调用 IPC
 */
import type { ElectronAPI } from '@/types/electron'

/** 是否运行在 Electron 桌面端中。 */
export const isElectron: boolean = (() => {
  if (typeof window === 'undefined') return false
  if (window.electronAPI?.isElectron) return true
  return typeof navigator !== 'undefined' && /electron/i.test(navigator.userAgent)
})()

/** 取得桌面端 API；非桌面端返回 undefined。 */
export function getElectronAPI(): ElectronAPI | undefined {
  if (typeof window === 'undefined') return undefined
  return window.electronAPI
}

/** 桌面端才执行的调用，非桌面端返回 fallback。 */
export async function withElectron<T>(fn: (api: ElectronAPI) => Promise<T> | T, fallback: T): Promise<T> {
  const api = getElectronAPI()
  if (!api) return fallback
  try {
    return await fn(api)
  } catch (err) {
    console.error('[electron] IPC 调用失败:', err)
    return fallback
  }
}
