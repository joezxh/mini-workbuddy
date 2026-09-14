/**
 * 轮次状态机 Composable（对应后端 turn_state.TurnState）
 *
 * 维护代际(generation)与语音状态，提供 is_stale 供客户端在「用户打断助理」时
 * 丢弃旧代际的迟到音频/文本帧。
 */
import { ref, computed } from 'vue'
import type { VoiceState } from '@/types/voice'

export function useTurnState() {
  const turnId = ref('')
  const generation = ref(0)
  const voiceState = ref<VoiceState>('idle')

  function markSpeaking() {
    generation.value += 1
    voiceState.value = 'speaking'
  }
  function onSpeechStarted() {
    generation.value += 1
    voiceState.value = 'listening'
  }
  function onSpeechStopped() {
    voiceState.value = 'idle'
  }
  function onAudioDone() {
    voiceState.value = 'idle'
  }
  function onAssistantStart() {
    voiceState.value = 'processing'
  }
  function onInterrupt() {
    voiceState.value = 'idle'
  }

  const isPlaying = computed(() => voiceState.value === 'speaking')
  /** 传入事件所属代际 < 当前代际 → 已过期，应丢弃 */
  function isStale(g: number): boolean {
    return generation.value > g
  }

  return {
    turnId,
    generation,
    voiceState,
    markSpeaking,
    onSpeechStarted,
    onSpeechStopped,
    onAudioDone,
    onAssistantStart,
    onInterrupt,
    isPlaying,
    isStale,
  }
}
