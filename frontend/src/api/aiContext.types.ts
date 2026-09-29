/**
 * AI Context Stats API - TypeScript 类型定义
 * Phase 2 增强版 - 支持详细指标和压缩功能
 */

/**
 * 单会话的上下文统计信息 (每个 session)
 */
export interface SessionStats {
  session_id: number  // 会话 ID
  total_tokens: number  // 总 token 使用量
  message_counts: {
    local: number  // 本地消息数
    vector_store: number  // 向量存储消息数
    shared_context: number  // 共享层上下文数（租户级别）
  }
  vector_store_messages: number  // Mem0 向量存储消息数
  shared_context_count: number  // 跨租户共享上下文条目总数
  last_compaction_time: string | null  // 最后压缩时间
  computed_at: string  // 统计计算时间
}

/**
 * 多模式会话上下文统计信息 (旧格式，向后兼容)
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
  mode: string  // 目标模式
  key: string  // 要压缩的上下文键
  strategy: 'sliding_window' | 'priority_eviction' | 'access_based' | 'summary_and_keep_latest'
  target_tokens?: number  // 目标 token 数（1000-32000）
}

/**
 * 上下文压缩响应
 */
export interface CompactionResponse {
  success: boolean  // 是否成功
  mode: string  // 受影响的模式
  key: string  // 受影响的上下文键
  strategy: string  // 使用的策略
  entries_before: number  // 压缩前条目数
  entries_after: number  // 压缩后条目数
  tokens_before: number  // 压缩前 token 数
  tokens_after: number  // 压缩后 token 数
  compaction_ratio: number  // 压缩比
  compacted_at: string  // 压缩时间戳
  error?: string | null  // 错误消息（如果失败）
}

/**
 * 审计日志项 - 压缩历史记录
 */
export interface CompactionHistoryItem {
  id: number
  timestamp: string
  action: 'compaction_triggered' | 'context_manual_override'
  target_type: 'context'
  target_id: string  // "mode:key" 格式
  details: {
    type: 'context_compaction' | 'manual_override'
    session_id: number
    tenant_id: string
    user_id?: number
    mode: string
    key: string
    strategy: string
    result: any
  }
}

// ─────────────────────────────────────────────────────────────
// PR-3 Task 10: 跨模式上下文 4 个类型（驱动 ModeContextCard 数据驱动）
// ─────────────────────────────────────────────────────────────

/** L2 短期记忆条目（来自 POST /entries） */
export interface ContextEntry {
  id: number
  session_id: number
  source_mode: string
  context_key: string
  context_data: Record<string, any>
  context_tags: string[]
  priority: number
  is_cross_mode_accessible: boolean
  case_number: string | null
  expires_at: string | null
  created_at: string
  last_accessed: string | null
}

/** POST /entries 请求体 */
export interface ContextEntriesRequest {
  session_id: number
  allow_cross_mode?: boolean
  include_tags?: string[]
  source_mode?: string
  limit?: number
}

/** POST /breakdown 单桶 */
export interface ContextBreakdownBucket {
  source_mode: string
  entry_count: number
}

/** GET /strategies 单策略（驱动 ModeContextCard 数据驱动） */
export interface FinalizeStrategy {
  session_type: string
  source_mode: string
  priority: number
  ttl_hours: number
  write_mem0: boolean
  is_cross_mode_accessible: boolean
  display_label: string
  display_color: string
}

// ─────────────────────────────────────────────────────────────
// 记忆子系统（spec 2026-09-29 §9.8 / §12.2）
// ─────────────────────────────────────────────────────────────

/** GET /memory/health — L3 provider 健康 + 记忆配置摘要 */
export interface MemoryHealth {
  ok: boolean
  provider: string
  ltm_enabled: boolean
  recall_enabled: boolean
  snapshot_enabled: boolean
  fail_open: boolean
  top_k: number
  max_chars: number
  history_limit: number
  detail: Record<string, unknown>
}

/** GET /memory/stats — 按 memory_kind 聚合的单桶 */
export interface MemoryKindBucket {
  memory_kind: string
  count: number
  tokens: number
}

/** GET /memory/stats — 按 source_mode 聚合的单桶 */
export interface MemorySourceModeBucket {
  source_mode: string
  count: number
}

/** GET /memory/stats — 会话记忆统计（已过滤过期条目） */
export interface MemoryStats {
  session_id: number
  total: number
  by_kind: MemoryKindBucket[]
  by_source_mode: MemorySourceModeBucket[]
}
