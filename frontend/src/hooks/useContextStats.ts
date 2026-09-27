import apiClient from '../apiClient';

export interface Stats {
  session_id: number;
  total_tokens: number;
  message_counts: {
    local: number;
    vector_store: number;
    shared_context: number;
  };
  vector_store_messages: number;
  shared_context_count: number;
  last_compaction_time: string | null;
  computed_at: string;
}

export interface StatsBatchRequest {
  session_ids: (string | number)[];
}

export function useContextStats() {
  async function getBatchStats(sessionIds: (string | number)[]) {
    const response = await apiClient.post('/ai/context/stats/batch', {
      session_ids: sessionIds,
    });
    return response.data.items as Record<number, Stats>;
  }

  async function getUserStats() {
    // Get all user sessions first
    const response = await apiClient.post('/ai/context/stats', {});
    return response.data as Stats[];
  }

  return { getBatchStats, getUserStats };
}

import { useContextsStore } from '@/stores/contexts'

// ─────────────────────────────────────────────────────────────
// PR-3 Task 11: useCrossModeStats — 9 模式跨模式上下文 composable
// 基于 Pinia contexts store 暴露的策略/聚合/条目状态,
// 供 CrossModeStatsPage 与 ModeContextCard 共用。
// 既有 4 模式 useContextStats 保留(避免破坏 CompactButton / ContextStatsDisplay)。
// ─────────────────────────────────────────────────────────────

/** 9 模式跨模式统计 composable(基于 Pinia store) */
export function useCrossModeStats() {
  const store = useContextsStore()
  return {
    strategies: store.strategies,
    breakdown: store.breakdown,
    entriesByMode: store.entriesByMode,
    loading: store.loading,
    lastError: store.lastError,
    loadStrategies: store.loadStrategies,
    loadBreakdown: store.loadBreakdown,
    loadEntriesByMode: store.loadEntriesByMode,
    loadAll: store.loadAll,
    findBucket: store.findBucket,
    reset: store.reset,
  }
}
