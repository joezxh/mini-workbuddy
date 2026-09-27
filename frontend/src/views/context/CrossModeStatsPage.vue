<!--
  CrossModeStatsPage.vue
  PR-3 Task 17: 9 模式跨模式上下文统计页(数据驱动)

  Props:
    - sessionId: number              当前会话 ID

  数据流(useCrossModeStats + Pinia contexts store):
    - strategies: FinalizeStrategy[]
    - breakdown:  ContextBreakdownBucket[]
    - entriesByMode: Record<string, ContextEntry[]>
    - loading, lastError

  行为:
    - mount 时 loadAll(sessionId)
    - 点击 ModeContextCard 的"查看历史" → 打开 a-drawer + loadEntriesByMode
    - 优雅降级:strategies 为空时使用本地 DEFAULT_STRATEGIES(9 模式)

  设计要点:
  - 单一可复用 ModeContextCard + ContextHistoryList,数据驱动
  - 不引入新依赖
  - 9 模式全部从 props.strategies 或 DEFAULT_STRATEGIES 加载,严禁硬编码 9 张独立卡
-->
<template>
  <div class="cross-mode-stats-page">
    <a-page-header
      title="跨模式上下文记忆"
      sub-title="9 种会话模式 × L2 短期记忆 + 本地私有化 Mem0 永久记忆"
    >
      <template #extra>
        <a-button :loading="loading" @click="refresh">刷新</a-button>
      </template>
    </a-page-header>

    <a-empty
      v-if="!displayStrategies.length"
      description="暂无 9 模式策略数据"
    />

    <a-row v-else :gutter="[16, 16]">
      <a-col
        v-for="s in displayStrategies"
        :key="s.source_mode"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <ModeContextCard
          :strategy="s"
          :bucket="findBucket(s.source_mode)"
          @view-history="openHistoryDrawer"
        />
      </a-col>
    </a-row>

    <a-drawer
      v-model:open="historyDrawerVisible"
      :title="`历史:${activeStrategy?.display_label ?? ''}`"
      width="640"
    >
      <ContextHistoryList
        :entries="activeStrategy ? entriesByMode[activeStrategy.source_mode] || [] : []"
      />
    </a-drawer>

    <div v-if="hasError" class="error-banner">
      <a-alert :message="errorMessage" type="error" show-icon />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import ModeContextCard from '@/components/context/ModeContextCard.vue'
import ContextHistoryList from '@/components/context/ContextHistoryList.vue'
import type { FinalizeStrategy } from '@/api/aiContext.types'
import { useCrossModeStats } from '@/hooks/useCrossModeStats'

const props = defineProps<{ sessionId: number }>()

const {
  strategies,
  breakdown,
  entriesByMode,
  loading,
  lastError,
  loadAll,
  loadEntriesByMode,
  findBucket,
} = useCrossModeStats()

const errorMessage = computed(() => {
  const err = lastError as unknown as { value: string | null }
  return `加载失败: ${err?.value ?? ''}`
})
const hasError = computed(() => {
  const err = lastError as unknown as { value: string | null }
  return Boolean(err?.value)
})

/** 9 模式本地 fallback — 当 /strategies 接口失败时优雅降级 */
const DEFAULT_STRATEGIES: FinalizeStrategy[] = [
  { session_type: 'general',       source_mode: 'general',       priority: 3, ttl_hours: 168, write_mem0: true,  is_cross_mode_accessible: false, display_label: '通用对话',     display_color: 'blue' },
  { session_type: 'react',         source_mode: 'react',         priority: 3, ttl_hours: 168, write_mem0: true,  is_cross_mode_accessible: false, display_label: 'ReAct 计划',  display_color: 'cyan' },
  { session_type: 'thinking',      source_mode: 'thinking',      priority: 4, ttl_hours: 168, write_mem0: true,  is_cross_mode_accessible: false, display_label: '深度思考',     display_color: 'purple' },
  { session_type: 'deep_research', source_mode: 'deep_research', priority: 4, ttl_hours: 336, write_mem0: true,  is_cross_mode_accessible: true,  display_label: '深度研究',     display_color: 'magenta' },
  { session_type: 'skill',         source_mode: 'skill',         priority: 2, ttl_hours: 168, write_mem0: true,  is_cross_mode_accessible: false, display_label: '技能执行',     display_color: 'green' },
  { session_type: 'agent',         source_mode: 'agent',         priority: 2, ttl_hours: 720, write_mem0: true,  is_cross_mode_accessible: true,  display_label: '智能体',       display_color: 'gold' },
  { session_type: 'team',          source_mode: 'team',          priority: 2, ttl_hours: 168, write_mem0: true,  is_cross_mode_accessible: true,  display_label: '智能体团队',   display_color: 'orange' },
  { session_type: 'scheduled',     source_mode: 'scheduled',     priority: 4, ttl_hours: 720, write_mem0: false, is_cross_mode_accessible: false, display_label: '云端调度',     display_color: 'default' },
  { session_type: 'shared',        source_mode: 'shared',        priority: 5, ttl_hours: 168, write_mem0: false, is_cross_mode_accessible: false, display_label: '共享层',       display_color: 'default' },
]

const displayStrategies = computed<FinalizeStrategy[]>(() => {
  if (strategies.value && strategies.value.length > 0) return strategies.value
  return DEFAULT_STRATEGIES
})

const historyDrawerVisible = ref(false)
const activeStrategy = ref<FinalizeStrategy | null>(null)

function openHistoryDrawer(s: FinalizeStrategy) {
  activeStrategy.value = s
  loadEntriesByMode(s.source_mode, true)
  historyDrawerVisible.value = true
}

async function refresh() {
  await loadAll(props.sessionId)
}

watch(
  () => props.sessionId,
  (v) => {
    if (v) loadAll(v)
  },
  { immediate: true },
)

onMounted(() => {
  if (props.sessionId) loadAll(props.sessionId)
})
</script>

<style scoped>
.cross-mode-stats-page {
  padding: 16px;
  min-height: 200px;
}
.error-banner {
  margin-top: 12px;
}
</style>
