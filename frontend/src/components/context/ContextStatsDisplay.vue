<!--
  ContextStatsDisplay.vue
  PR-3 Task 15: 9 模式通用上下文统计展示组件

  Props:
    - breakdown:  ContextBreakdownBucket[]   必填,来自 POST /breakdown
    - strategies: FinalizeStrategy[]         可选,来自 GET /strategies
    - loading?:   boolean                    加载状态

  Emits:
    - refresh()                              触发刷新(由父组件 loadAll 处理)

  设计要点:
  - Ant Design Vue + a-table + a-statistic 渲染 9 模式 breakdown
  - 兼容已有 aiContext.ts / aiContext.types.ts 的现有公共导出
  - SSR-friendly,不直接调 axios
  - 不引入新依赖
-->
<template>
  <div class="context-stats-display">
    <a-card :body-style="{ padding: '16px' }">
      <template #title>
        <span>📊 上下文统计</span>
      </template>
      <template #extra>
        <a-button
          type="primary"
          size="small"
          :loading="loading"
          @click="emit('refresh')"
        >
          🔄 刷新
        </a-button>
      </template>

      <a-empty v-if="!breakdown.length" description="暂无数据" />

      <template v-else>
        <a-row :gutter="16" style="margin-bottom: 16px;">
          <a-col :span="6">
            <a-statistic title="模式数" :value="modeCount" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="总条目数" :value="totalEntries" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="跨模式可读桶数" :value="crossModeCount" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="Mem0 启用桶数" :value="mem0Count" />
          </a-col>
        </a-row>

        <a-table
          :data-source="breakdown"
          :columns="columns"
          row-key="source_mode"
          size="small"
          :pagination="false"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'source_mode'">
              <a-tag :color="getModeColor(record.source_mode)">
                {{ record.source_mode }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'mem0'">
              <a-tag v-if="hasMem0(record.source_mode)" color="green">Mem0</a-tag>
              <a-tag v-else color="default">L2 only</a-tag>
            </template>
            <template v-else-if="column.key === 'cross'">
              <a-tag v-if="isCrossModeAccessible(record.source_mode)" color="purple">
                可读
              </a-tag>
              <a-tag v-else color="default">隔离</a-tag>
            </template>
          </template>
        </a-table>
      </template>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  ContextBreakdownBucket,
  FinalizeStrategy,
} from '@/api/aiContext.types'

const props = withDefaults(
  defineProps<{
    breakdown: ContextBreakdownBucket[]
    strategies?: FinalizeStrategy[]
    loading?: boolean
  }>(),
  {
    strategies: () => [] as FinalizeStrategy[],
    loading: false,
  },
)

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const columns = [
  { title: '模式', key: 'source_mode', dataIndex: 'source_mode' },
  { title: '条目数', key: 'entry_count', dataIndex: 'entry_count' },
  { title: 'Mem0', key: 'mem0' },
  { title: '跨模式', key: 'cross' },
]

const modeCount = computed(() => props.breakdown.length)
const totalEntries = computed(() =>
  props.breakdown.reduce((sum, b) => sum + (b.entry_count ?? 0), 0),
)
const mem0Count = computed(
  () => props.strategies.filter((s) => s.write_mem0).length,
)
const crossModeCount = computed(
  () => props.strategies.filter((s) => s.is_cross_mode_accessible).length,
)

function hasMem0(mode: string): boolean {
  return props.strategies.find((s) => s.source_mode === mode)?.write_mem0 === true
}

function isCrossModeAccessible(mode: string): boolean {
  return props.strategies.find((s) => s.source_mode === mode)?.is_cross_mode_accessible === true
}

const MODE_COLOR_MAP: Record<string, string> = {
  general: 'blue',
  react: 'cyan',
  thinking: 'purple',
  deep_research: 'magenta',
  skill: 'green',
  agent: 'gold',
  team: 'orange',
  scheduled: 'default',
  shared: 'default',
}

function getModeColor(mode: string): string {
  return MODE_COLOR_MAP[mode] ?? 'default'
}
</script>

<style scoped>
.context-stats-display {
  width: 100%;
}
</style>
