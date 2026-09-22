/**
 * AI Context Stats API - TypeScript 类型定义
 */

/**
 * 多模式会话上下文统计信息
 */
export interface ContextStats {
  shared_context_count: number  // 共享层上下文数量
  modes: Record<string, ModeStats>  // 各模式的统计数据
  mem0_enabled: boolean  // Mem0 长期记忆是否启用
  mem0_memory_count?: number  // Mem0 记忆总数
  total_entries: number  // 总条目数
  computed_at?: string  // 统计计算时间
}

/**
 * 孤立模式 (Isolated Mode) 的上下文统计
 */
export interface ModeStats {
  entry_count: number  // 该模式的上下文条目数
  total_tokens: number  // 总 token 使用量
  avg_priority: number  // 平均优先级
}

/**
 * 上下文压缩请求体
 */
export interface CompactionRequest {
  session_id?: string  // 会话 ID（可选）
  mode?: string  // 模式标识（dify/sqlbot/agentscope）
  min_priority_threshold?: number  // 最小优先级阈值（低于此值的可压缩）
  max_tokens?: number  // 最大保留 token 数
}
