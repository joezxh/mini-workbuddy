/**
 * 视频会议 API —— LiveKit 入会 Token 签发
 *
 * 后端路由：backend/app/routers/meeting.py（POST /api/v1/meeting/tokens）
 * 前端拿到 { token, ws_url } 后用 livekit-client 直连自建 SFU，
 * 参见 docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md §6。
 */
import request from '@/utils/request'

/** 与后端 MeetingTokenOut 对齐 */
export interface MeetingToken {
  token: string
  ws_url: string
  room: string
  identity: string
  name: string
  ttl_seconds: number
}

/** 签发入会 token 的入参（与后端 MeetingTokenIn 对齐） */
export interface MeetingTokenRequest {
  /** 房间名：^[A-Za-z0-9][A-Za-z0-9_-]{1,62}[A-Za-z0-9]$ */
  room: string
  /** 参与者唯一 ID，缺省为当前用户 user_id；代签他人仅限管理员 */
  identity?: string
  /** 房间内展示名，缺省为当前用户 real_name */
  name?: string
  /** false 时为旁听席：只可订阅，不可推音视频 */
  can_publish?: boolean
}

/** 为当前用户签发指定房间的入会 token */
export function createMeetingToken(payload: MeetingTokenRequest) {
  return request.post<MeetingToken>('/api/v1/meeting/tokens', payload)
}
