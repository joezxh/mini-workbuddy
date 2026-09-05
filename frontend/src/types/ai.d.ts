/**
 * AI助理类型定义
 */

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

