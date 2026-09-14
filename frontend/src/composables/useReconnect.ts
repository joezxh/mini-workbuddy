/**
 * 重连退避 Composable（对应后端 reconnect_backoff.ReconnectBackoff）
 *
 * 指数退避（封顶）+ 最大重试次数，供 VoiceChannel 在连接断开后自动重连。
 */
import { ref } from 'vue'

export interface ReconnectOptions {
  base?: number
  factor?: number
  cap?: number
  maxAttempts?: number
}

export function useReconnect(opts: ReconnectOptions = {}) {
  const base = opts.base ?? 0.5
  const factor = opts.factor ?? 2.0
  const cap = opts.cap ?? 8.0
  const maxAttempts = opts.maxAttempts ?? 5

  const attempt = ref(0)
  const lastDelay = ref(0)

  function reset() {
    attempt.value = 0
    lastDelay.value = 0
  }

  /** 返回下一次重连延迟（秒）并推进计数 */
  function nextDelay(): number {
    const d = Math.min(base * Math.pow(factor, attempt.value), cap)
    attempt.value += 1
    lastDelay.value = d
    return d
  }

  function shouldRetry(): boolean {
    return attempt.value < maxAttempts
  }

  return { attempt, lastDelay, reset, nextDelay, shouldRetry }
}
