/**
 * 会话历史记录 API
 */
import request from '@/utils/request'
import type { AxiosRequestConfig } from 'axios'

interface GetSessionsRequest {
  skill_id: string
  page?: number
  page_size?: number
}

interface GetMessagesRequest {
  session_id: number
  limit?: number
  before_message_id?: number
}

/**
 * 获取技能的会话列表（分页）
 */
export async function postSessions(params: GetSessionsRequest) {
  const config: AxiosRequestConfig = {
    headers: {
      'Content-Type': 'application/json',
    },
  }
  return request.post(
    `/api/v1/ai-assistant/skills/${params.skill_id}/sessions`,
    params,
    config
  )
}

/**
 * 获取会话的消息记录（分页）
 */
export async function getMessages(skillId: string, params: GetMessagesRequest) {
  return request.post(`/api/v1/ai-assistant/skills/${skillId}/messages`, params)
}

/**
 * 获取会话详情
 */
export async function getSessionDetail(skillId: string, sessionId: number) {
  return request.get(`/api/v1/ai-assistant/skills/${skillId}/session/${sessionId}`)
}
