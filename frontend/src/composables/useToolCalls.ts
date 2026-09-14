/**
 * 工具调用 Composable（对应后端 tool_call_handler.ToolCallHandler）
 *
 * 维护会话级工具调用的列表与状态，供 UI 展示「AI 调用了哪些工具」。
 */
import { ref, computed } from 'vue'
import type { ToolCall } from '@/types/voice'

export function useToolCalls() {
  const calls = ref<ToolCall[]>([])

  function add(call: ToolCall) {
    calls.value.push(call)
  }

  function update(id: string, patch: Partial<ToolCall>) {
    const idx = calls.value.findIndex((c) => c.id === id)
    if (idx >= 0) calls.value[idx] = { ...calls.value[idx], ...patch }
  }

  function clear() {
    calls.value = []
  }

  const pending = computed(() => calls.value.filter((c) => c.result === undefined))
  const failed = computed(() => calls.value.filter((c) => c.ok === false))

  return { calls, add, update, clear, pending, failed }
}
