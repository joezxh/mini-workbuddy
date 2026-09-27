/**
 * PR-3 Task 12: useCrossModeCompaction — 9 模式跨模式上下文压缩 composable
 *
 * 基于 axios 实例(utils/request)封装 triggerCompaction,维护 isCompacting /
 * lastResult / lastError / history 状态。
 *
 * 设计要点:
 * - 沿用 aiContext.ts.triggerCompaction 已有的 CompactionRequest 接口。
 * - 复用 Pinia 不直接涉及(压缩动作无状态共享),仅维护本 composable 内部状态。
 * - 不引入新依赖(原文件使用 @tanstack/react-query 是占位符且无法加载)。
 * - history 默认保留最近 10 条记录,LRU(头部最新)。
 */
import { ref } from 'vue'
import api from '@/utils/request'
import type {
  CompactionRequest,
  CompactionResponse,
} from '@/api/aiContext.types'

const MAX_HISTORY = 10

export function useCrossModeCompaction() {
  const isCompacting = ref(false)
  const lastResult = ref<CompactionResponse | null>(null)
  const lastError = ref<string | null>(null)
  const history = ref<CompactionResponse[]>([])

  async function triggerCompaction(req: CompactionRequest): Promise<CompactionResponse> {
    isCompacting.value = true
    lastError.value = null
    try {
      const res = await api.post<{ data: CompactionResponse }>(
        '/api/v1/ai/context/compaction',
        req,
      )
      const payload = (res as { data: CompactionResponse }).data
      lastResult.value = payload
      // newest-first
      history.value = [payload, ...history.value].slice(0, MAX_HISTORY)
      return payload
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      lastError.value = msg
      throw err
    } finally {
      isCompacting.value = false
    }
  }

  function clearHistory(): void {
    history.value = []
    lastResult.value = null
    lastError.value = null
  }

  return {
    isCompacting,
    lastResult,
    lastError,
    history,
    triggerCompaction,
    clearHistory,
  }
}