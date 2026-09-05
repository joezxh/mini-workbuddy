/**
 * AI助理相关API
 */

import request from '@/utils/request'

const BASE_URL = '/api/v1'

/**
 * AI对话
 */
export interface ChatRequest {
  message: string
  session_id?: string
}

export interface ChatResponse {
  message: string
  session_id: string
  timestamp: string
}

export function sendChatMessage(data: ChatRequest) {
  return request.post<ChatResponse>(`${BASE_URL}/ai-assistant/chat`, data)
}

/**
 * 会话列表
 */
export interface ChatSession {
  session_id: string
  created_at: string
}

export function getChatSessions() {
  return request.get<{ data: ChatSession[] }>(`${BASE_URL}/ai-assistant/sessions`)
}

/**
 * 创建会话
 */
export function createChatSession() {
  return request.post<ChatSession>(`${BASE_URL}/ai-assistant/sessions`)
}

/**
 * 会话消息历史
 */
export interface ChatMessage {
  id: number
  role: string
  content: string
  created_at: string
}

export function getSessionMessages(sessionId: string) {
  return request.get<{ data: ChatMessage[] }>(`${BASE_URL}/ai-assistant/sessions/${sessionId}/messages`)
}

