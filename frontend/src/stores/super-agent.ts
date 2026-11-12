/**
 * SuperAgent Pinia Store（Task 4.1 / 4.6）
 *
 * tickets / feed / ideas / goals / chat 状态 + SSE 订阅。
 * SSE 从 demo.html 迁入：EventSource('/api/v1/super-agent/events?workspace_id=1')。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  type ChatMessage, type ChatSession, type FeedPost, type Goal, type Idea, type TicketBrief,
  listChatSessions, listFeed, listGoals, listIdeas, listTickets, openEventsSSE, openFeedSSE,
} from '@/api/super-agent'

/** Prototype 固定 workspace（与 demo.html 一致）。 */
export const SA_WORKSPACE_ID = 1

/** 看板 8 stage 分组 —— ticket status → stage（tasks.md 4.2）。 */
export const STAGES = [
  'PENDING_ASSESS', 'ACCEPTED', 'WORKING', 'REFLECTING',
  'WAITING_PERSON', 'BLOCKED', 'COMPLETED', 'DROPPED',
] as const

function statusToStage(status: string): string {
  switch (status) {
    case 'open': return 'ACCEPTED' // Ticket 仅在 accept 后创建
    case 'working': return 'WORKING'
    case 'working.reflecting': return 'REFLECTING'
    case 'waiting_person':
    case 'waiting_hitl': return 'WAITING_PERSON'
    case 'waiting_input': return 'PENDING_ASSESS'
    case 'blocked':
    case 'failed': return 'BLOCKED'
    case 'completed': return 'COMPLETED'
    case 'dropped': return 'DROPPED'
    default: return 'PENDING_ASSESS'
  }
}

export const useSuperAgentStore = defineStore('super-agent', () => {
  // ============ state ============
  const tickets = ref<TicketBrief[]>([])
  const loadingTickets = ref(false)

  const feed = ref<FeedPost[]>([])
  const loadingFeed = ref(false)

  const ideas = ref<Idea[]>([])
  const loadingIdeas = ref(false)

  const goals = ref<Goal[]>([])
  const loadingGoals = ref(false)

  const chatSessions = ref<ChatSession[]>([])
  const activeSessionId = ref<string>('')
  const chatMessages = ref<ChatMessage[]>([])
  const chatStreaming = ref(false)

  const connected = ref(false)
  const lastEvent = ref<{ event: string; data: any; ts: number } | null>(null)

  let eventsES: EventSource | null = null
  let feedES: EventSource | null = null
  let pollTimer: number | null = null

  // ============ getters ============
  const stageGroups = computed(() => {
    const groups: Record<string, TicketBrief[]> = {}
    for (const s of STAGES) groups[s] = []
    for (const t of tickets.value) {
      groups[statusToStage(t.status)]?.push(t)
    }
    return groups
  })

  const unreadFeedCount = computed(() => feed.value.filter(p => !p.read).length)

  // ============ actions ============

  async function fetchTickets() {
    loadingTickets.value = true
    try {
      tickets.value = await listTickets(SA_WORKSPACE_ID, undefined) as any || []
    } finally {
      loadingTickets.value = false
    }
  }

  async function fetchFeed() {
    loadingFeed.value = true
    try {
      feed.value = await listFeed(SA_WORKSPACE_ID) as any || []
    } finally {
      loadingFeed.value = false
    }
  }

  async function fetchIdeas() {
    loadingIdeas.value = true
    try {
      ideas.value = await listIdeas(SA_WORKSPACE_ID) as any || []
    } finally {
      loadingIdeas.value = false
    }
  }

  async function fetchGoals() {
    loadingGoals.value = true
    try {
      goals.value = await listGoals(SA_WORKSPACE_ID) as any || []
    } finally {
      loadingGoals.value = false
    }
  }

  async function fetchChatSessions() {
    chatSessions.value = await listChatSessions(SA_WORKSPACE_ID) as any || []
  }

  // --- SSE 订阅（demo.html 迁移） ---

  /** 订阅引擎事件流 + 5s 轮询 fallback（看板用）。 */
  function connectEvents() {
    if (eventsES) return
    eventsES = openEventsSSE(SA_WORKSPACE_ID, {
      connected: () => { connected.value = true },
      ticket_created: (data) => {
        lastEvent.value = { event: 'ticket_created', data, ts: Date.now() }
        fetchTickets()
      },
      ticket_completed: (data) => {
        lastEvent.value = { event: 'ticket_completed', data, ts: Date.now() }
        fetchTickets()
      },
      effect_assess: (data) => { lastEvent.value = { event: 'effect_assess', data, ts: Date.now() } },
      effect_launch: (data) => { lastEvent.value = { event: 'effect_launch', data, ts: Date.now() } },
    })
    // 轮询 fallback
    pollTimer = window.setInterval(() => { fetchTickets() }, 5000)
  }

  function disconnectEvents() {
    eventsES?.close()
    eventsES = null
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
    connected.value = false
  }

  /** 订阅 Feed 流（workbench feed 页用）。 */
  function connectFeed(onGoalUpdated?: (data: any) => void) {
    if (feedES) return
    feedES = openFeedSSE(SA_WORKSPACE_ID, {
      connected: () => { connected.value = true },
      feed_post: (data) => {
        lastEvent.value = { event: 'feed_post', data, ts: Date.now() }
        if (!data.quiet) fetchFeed()
      },
      proposal_created: (data) => {
        lastEvent.value = { event: 'proposal_created', data, ts: Date.now() }
      },
      goal_updated: (data) => {
        lastEvent.value = { event: 'goal_updated', data, ts: Date.now() }
        onGoalUpdated?.(data)
      },
    })
  }

  function disconnectFeed() {
    feedES?.close()
    feedES = null
    connected.value = false
  }

  // --- Chat ---

  function openSession(sessionId: string, messages: ChatMessage[]) {
    activeSessionId.value = sessionId
    chatMessages.value = messages
  }

  function appendMessage(msg: ChatMessage) {
    chatMessages.value.push(msg)
  }

  return {
    tickets, loadingTickets, feed, loadingFeed, ideas, loadingIdeas, goals, loadingGoals,
    chatSessions, activeSessionId, chatMessages, chatStreaming,
    connected, lastEvent,
    stageGroups, unreadFeedCount,
    fetchTickets, fetchFeed, fetchIdeas, fetchGoals, fetchChatSessions,
    connectEvents, disconnectEvents, connectFeed, disconnectFeed,
    openSession, appendMessage,
  }
})
