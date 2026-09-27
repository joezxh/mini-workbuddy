/**
 * PR-3 Task 11: useCrossModeStats — 9 模式跨模式上下文 composable
 *
 * 基于 Pinia contexts store 暴露的策略/聚合/条目状态,
 * 供 CrossModeStatsPage 与 ModeContextCard 共用。
 *
 * 设计要点:
 * - 状态由 Pinia store 持有,Composable 仅暴露反应式引用 + 调用入口。
 * - 既有 4 模式 `useContextStats` (useContextStats.ts) 保留,避免破坏
 *   CompactButton / ContextStatsDisplay 等已有组件。
 * - 不引入新依赖。
 */
import { useContextsStore } from '@/stores/contexts'

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