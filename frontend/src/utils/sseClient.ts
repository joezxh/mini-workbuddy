/** 统一 SSE 客户端（P1.2：fetch 流式 + Last-Event-ID 断线重连 + after_seq 补拉）。

相比浏览器原生 EventSource，本实现：
- 允许携带 Authorization 头（EventSource 不支持自定义头）；
- 断线后用最后收到的 seq 作为 after_seq 自动补拉，保证 30s 内重连不丢事件；
- 解析 ``id:`` / ``event:`` / ``data:`` 帧，心跳 ``: keep-alive`` 忽略。
*/
import { getToken } from '@/utils/auth'

const baseUrl: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface SSEClientOptions {
  onEvent: (env: Record<string, any>) => void
  onOpen?: () => void
  onError?: (err: unknown) => void
  onClose?: () => void
  afterSeq?: number | null
  maxReconnectAttempts?: number
  reconnectDelayMs?: number
}

export interface SSEClient {
  close: () => void
  readonly lastEventId: number | null
}

export function connectEventStream(path: string, opts: SSEClientOptions): SSEClient {
  let lastEventId: number | null = opts.afterSeq ?? null
  let closedByUser = false
  let controller: AbortController | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let attempts = 0
  const maxAttempts = opts.maxReconnectAttempts ?? 10
  const delay = opts.reconnectDelayMs ?? 2000

  const scheduleReconnect = () => {
    if (closedByUser || attempts >= maxAttempts) return
    attempts += 1
    reconnectTimer = setTimeout(open, delay)
  }

  const handleFrame = (frame: string) => {
    let id: number | null = null
    let data = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('id:')) {
        const n = parseInt(line.slice(3).trim(), 10)
        if (!Number.isNaN(n)) id = n
      } else if (line.startsWith('data:')) {
        data += line.slice(5).trim()
      }
    }
    if (!data || data === ': keep-alive') return
    if (id != null) lastEventId = id
    try {
      opts.onEvent(JSON.parse(data))
    } catch (e) {
      console.error('[sseClient] parse error', e)
    }
  }

  const open = async () => {
    if (closedByUser) return
    controller = new AbortController()
    const url = new URL(baseUrl + path)
    if (lastEventId != null) url.searchParams.set('after_seq', String(lastEventId))
    const token = getToken()
    try {
      const res = await fetch(url.toString(), {
        headers: {
          Accept: 'text/event-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller!.signal,
      })
      if (!res.ok || !res.body) {
        scheduleReconnect()
        return
      }
      attempts = 0
      opts.onOpen?.()
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          handleFrame(frame)
        }
      }
      // 服务端正常结束 → 尝试重连以捕获可能的补发事件
      scheduleReconnect()
    } catch (e: any) {
      if (e?.name === 'AbortError') return
      opts.onError?.(e)
      scheduleReconnect()
    }
  }

  open()

  return {
    get lastEventId() {
      return lastEventId
    },
    close() {
      closedByUser = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      controller?.abort()
      opts.onClose?.()
    },
  }
}
