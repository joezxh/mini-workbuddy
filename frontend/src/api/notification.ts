/** 站内通知接口 */
import request from '@/utils/request'

export interface NotificationItem {
  id: number
  userId: number
  type: string
  title: string
  content?: string
  refId?: number
  refType?: string
  isRead: boolean
  expireAt?: string
  createdAt?: string
}

export async function getNotifications(params: { page?: number; size?: number; onlyUnread?: boolean }) {
  return request.get('/api/v1/ai/notifications', { params })
}

export async function markNotificationsRead(ids?: number[]) {
  return request.post('/api/v1/ai/notifications/read', { ids: ids || [] })
}

export async function cleanExpiredNotifications() {
  return request.post('/api/v1/ai/notifications/clean')
}
