/**
 * AI助理状态管理
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatSession, ChatMessage } from '@/types/ai'
import { getChatSessions, getChatSession, createChatSession, deleteChatSession } from '@/api/ai'

export const useAIStore = defineStore('ai', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSession = ref<ChatSession | null>(null)
  const loading = ref(false)

  /**
   * 获取会话列表
   */
  async function fetchSessions() {
    loading.value = true
    try {
      const res = await getChatSessions()
      sessions.value = res.data
      return res
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取会话详情
   */
  async function fetchSession(sessionId: string) {
    loading.value = true
    try {
      const res = await getChatSession(sessionId)
      currentSession.value = res.data
      return res
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建会话
   */
  async function createSession(title?: string) {
    loading.value = true
    try {
      const res = await createChatSession(title)
      currentSession.value = res.data
      sessions.value.unshift(res.data)
      return res
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除会话
   */
  async function deleteSession(sessionId: string) {
    loading.value = true
    try {
      await deleteChatSession(sessionId)
      sessions.value = sessions.value.filter(s => s.sessionId !== sessionId)
      if (currentSession.value?.sessionId === sessionId) {
        currentSession.value = null
      }
    } finally {
      loading.value = false
    }
  }

  /**
   * 添加消息到当前会话
   */
  function addMessage(message: ChatMessage) {
    if (currentSession.value) {
      currentSession.value.messages.push(message)
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    sessions.value = []
    currentSession.value = null
    loading.value = false
  }

  return {
    sessions,
    currentSession,
    loading,
    fetchSessions,
    fetchSession,
    createSession,
    deleteSession,
    addMessage,
    reset
  }
})

