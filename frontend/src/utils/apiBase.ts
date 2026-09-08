/**
 * 后端 API 根地址解析。
 *
 * 浏览器部署：地址在构建期烘焙进 import.meta.env.VITE_API_BASE_URL（或留空走 Nginx 反代）。
 * 桌面端部署：地址不烘焙，运行时从主进程 userData/app-config.json 读取，可在客户端里随时改，
 *            改完无需重新打包。
 *
 * 桌面端加载页面时，页面同源是内置静态服务器（http://127.0.0.1:<随机端口>），
 * 而这里烘焙的 VITE_API_BASE_URL 为空，因此所有 /api 请求会被改写到真实后端地址。
 * 改写只作用于以 /api 开头的相对路径，静态资源请求不受影响。
 */
import { getElectronAPI, isElectron, withElectron } from './electron'

/** 需要改写为后端绝对地址的路径前缀。 */
const API_PREFIX = '/api'

function normalize(url: string): string {
  return (url || '').trim().replace(/\/+$/, '')
}

let apiBase: string = normalize(import.meta.env.VITE_API_BASE_URL || '')
const changeListeners = new Set<(base: string) => void>()
let patched = false

export function getApiBase(): string {
  return apiBase
}

export function setApiBase(url: string): string {
  apiBase = normalize(url)
  changeListeners.forEach((cb) => cb(apiBase))
  return apiBase
}

/** 订阅地址变化（axios 实例等需要同步 baseURL 的地方使用）。 */
export function onApiBaseChange(cb: (base: string) => void): () => void {
  changeListeners.add(cb)
  return () => changeListeners.delete(cb)
}

/**
 * 把相对 API 路径解析为绝对地址。
 * 已经是绝对地址（http/https/其他协议）时原样返回。
 */
export function resolveApiUrl(url: string): string {
  if (!url) return url
  if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return url
  return `${apiBase}${url.startsWith('/') ? '' : '/'}${url}`
}

function shouldRewrite(url: string): boolean {
  return url.startsWith(API_PREFIX)
}

/** fetch / XHR / EventSource 统一改写，覆盖 axios 与原生调用两种写法。 */
function installPatches() {
  if (patched || !isElectron || typeof window === 'undefined') return
  patched = true

  // fetch
  const nativeFetch = window.fetch.bind(window)
  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    if (typeof input === 'string' && shouldRewrite(input)) {
      return nativeFetch(resolveApiUrl(input), init)
    }
    if (typeof Request !== 'undefined' && input instanceof Request && shouldRewrite(input.url)) {
      return nativeFetch(new Request(resolveApiUrl(input.url), input), init)
    }
    return nativeFetch(input as RequestInfo, init)
  }

  // XMLHttpRequest（axios 底层）
  const nativeOpen = XMLHttpRequest.prototype.open
  XMLHttpRequest.prototype.open = function patchedOpen(this: XMLHttpRequest, ...args: any[]) {
    const url = args[1]
    if (typeof url === 'string' && shouldRewrite(url)) {
      args[1] = resolveApiUrl(url)
    } else if (url instanceof URL && shouldRewrite(url.href)) {
      args[1] = resolveApiUrl(url.href)
    }
    return (nativeOpen as unknown as (...a: any[]) => void).apply(this, args)
  } as unknown as typeof nativeOpen

  // EventSource（SSE）
  const NativeEventSource = window.EventSource
  class ResolvedEventSource extends NativeEventSource {
    constructor(url: string | URL, config?: EventSourceInit) {
      super(resolveApiUrl(String(url)), config)
    }
  }
  window.EventSource = ResolvedEventSource as unknown as typeof EventSource
}

/**
 * 应用启动前调用：读取桌面端配置并应用后端地址。
 * 非桌面端直接返回构建期地址。
 */
export async function initApiBase(): Promise<string> {
  installPatches()
  if (!isElectron) return apiBase

  const config = await withElectron<{ apiBaseUrl?: string } | undefined>(
    (api) => api.getConfig(),
    undefined,
  )
  if (config?.apiBaseUrl) setApiBase(config.apiBaseUrl)
  return apiBase
}

/** 在桌面端持久化后端地址，并立即生效。 */
export async function saveApiBase(url: string): Promise<string> {
  const next = normalize(url)
  const saved = await withElectron(
    (api) => api.setConfig({ apiBaseUrl: next }),
    { apiBaseUrl: next },
  )
  setApiBase(saved?.apiBaseUrl || next)
  return getApiBase()
}

/** 桌面端客户端信息（版本号等），非桌面端返回 null。 */
export async function getDesktopInfo(): Promise<{ version: string; platform: string } | null> {
  const api = getElectronAPI()
  if (!api) return null
  try {
    const [version] = await Promise.all([api.appVersion()])
    return { version, platform: api.platform }
  } catch {
    return null
  }
}
