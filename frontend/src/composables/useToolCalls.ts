/**
 * 工具调用 Composable（AgentScope 原生 Toolkit 语义）
 *
 * 维护会话级工具调用列表与状态：tool_call 结果展示 + 待确认（pending）
 * 卡片驱动。addConfirm 由 tool.confirm_required 帧触发，结果经 update 落位。
 */
import { ref, computed } from 'vue'
import type { ToolCall } from '@/types/voice'

export function useToolCalls() {
  const calls = ref<ToolCall[]>([])

  function add(call: ToolCall) {
    calls.value.push(call)
  }

  /** tool.confirm_required 帧到达：登记待确认调用 */
  function addConfirm(p: {
    confirmId: string
    name: string
    arguments: Record<string, unknown>
    timeoutMs: number
  }) {
    calls.value.push({
      id: p.confirmId,
      name: p.name,
      arguments: p.arguments,
      status: 'pending',
    })
  }

  function update(id: string, patch: Partial<ToolCall>) {
    const idx = calls.value.findIndex((c) => c.id === id)
    if (idx >= 0) {
      calls.value[idx] = { ...calls.value[idx], ...patch }
      if (patch.ok !== undefined) {
        calls.value[idx].status = patch.ok ? 'executed' : 'rejected'
      }
    }
  }

  /** 打断 / playback_cancelled 时清空待确认（服务端同步放弃） */
  function clearPending() {
    calls.value = calls.value.filter((c) => c.status !== 'pending')
  }

  function clear() {
    calls.value = []
  }

  const pending = computed(() =>
    calls.value.filter((c) => c.status === 'pending'),
  )
  const failed = computed(() => calls.value.filter((c) => c.ok === false))

  return { calls, add, addConfirm, update, clearPending, clear, pending, failed }
}
