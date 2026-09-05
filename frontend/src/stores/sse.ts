/**
 * SSE Event Store (Pinia)
 * 
 * Centralized state management for SSE event streams
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SSEEvent, TeamStartEvent, TeamDoneEvent } from '@/types/sse'

export const useSSEStore = defineStore('sse', () => {
  // State
  const rawEvents = ref<SSEEvent[]>([])
  const teamEvent = ref<TeamStartEvent | null>(null)
  const doneEvent = ref<TeamDoneEvent | null>(null)
  const isConnected = ref(false)
  const error = ref<string | null>(null)
  
  // Computed properties
  const agents = computed(() => {
    const agentMap = new Map<string, string>()
    
    rawEvents.value.forEach((event: any) => {
      if (event.agent_id && event.agent_id !== '_system') {
        agentMap.set(event.agent_id, event.agent_name || event.agent_id)
      }
    })
    
    return Array.from(agentMap.entries())
  })
  
  const hasTeamContext = computed(() => !!teamEvent.value)
  const isTeamCompleted = computed(() => !!doneEvent.value)
  const completionRate = computed(() => {
    if (!doneEvent.value?.total_agents) return 0
    return Math.round((doneEvent.value.completed_agents / doneEvent.value.total_agents) * 100)
  })
  
  // Actions
  function addEvent(event: SSEEvent): void {
    rawEvents.value.push(event)
    
    // Extract team context
    if (event.type === 'team_start') {
      teamEvent.value = event as TeamStartEvent
    } else if (event.type === 'team_done') {
      doneEvent.value = event as TeamDoneEvent
    }
  }
  
  function clearEvents(): void {
    rawEvents.value = []
    teamEvent.value = null
    doneEvent.value = null
    isConnected.value = false
    error.value = null
  }
  
  function setError(message: string): void {
    error.value = message
  }
  
  function setConnected(status: boolean): void {
    isConnected.value = status
  }
  
  // Parse raw SSE stream line
  function parseLine(line: string): SSEEvent | null {
    try {
      if (!line.startsWith('data:')) return null
      
      const dataStr = line.slice(5).trim()
      if (!dataStr) return null
      
      return JSON.parse(dataStr)
    } catch (e) {
      console.error('Failed to parse SSE line:', e)
      return null
    }
  }
  
  return {
    // State
    rawEvents,
    teamEvent,
    doneEvent,
    isConnected,
    error,
    
    // Computed
    agents,
    hasTeamContext,
    isTeamCompleted,
    completionRate,
    
    // Actions
    addEvent,
    clearEvents,
    setError,
    setConnected,
    parseLine,
  }
})
