/**
 * AI助理相关API
 */

import request from '@/utils/request'
import { resolveApiUrl } from '@/utils/apiBase'
import type { ApiResponse } from '@/types/api'

// 对话消息
export interface ChatMessage {
  messageId: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

// 对话会话
export interface ChatSession {
  sessionId: string
  title: string
  messages: ChatMessage[]
  createTime: string
  updateTime: string
}

// 获取会话列表
export function getChatSessions() {
  return request.get<ApiResponse<ChatSession[]>>('/api/ai/sessions')
}

// 获取会话详情
export function getChatSession(sessionId: string) {
  return request.get<ApiResponse<ChatSession>>(`/api/ai/sessions/${sessionId}`)
}

// 创建会话
export function createChatSession(title?: string) {
  return request.post<ApiResponse<ChatSession>>('/api/ai/sessions', { title })
}

// 删除会话
export function deleteChatSession(sessionId: string) {
  return request.delete<ApiResponse<void>>(`/api/ai/sessions/${sessionId}`)
}

// 发送消息（非流式）
export function sendMessage(sessionId: string, content: string) {
  return request.post<ApiResponse<ChatMessage>>(`/api/ai/sessions/${sessionId}/messages`, { content })
}

// 发送消息（流式）- 返回SSE连接URL
export function getStreamMessageUrl(sessionId: string) {
  return resolveApiUrl(`/api/ai/sessions/${sessionId}/stream`)
}

// 关键词溯源
export function traceKeyword(keyword: string) {
  return request.post<ApiResponse<any>>('/api/ai/trace-keyword', { keyword })
}

