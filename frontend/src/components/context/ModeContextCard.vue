<!--
  ModeContextCard.vue
  PR-3 Task 13: 数据驱动单模式卡组件

  9 种会话模式(general/react/thinking/deep_research/skill/agent/team/scheduled/shared)
  全部通过 `strategy` prop 从 GET /strategies 加载渲染,严禁硬编码 9 个独立组件。

  Props:
    - strategy: FinalizeStrategy   必填,来自后端 GET /api/v1/ai/context/strategies
    - bucket?:  ContextBreakdownBucket  可选,来自 POST /breakdown 的桶

  Emits:
    - view-history(strategy)   点击查看历史
    - enable-cross(strategy)  点击跨模式读取按钮(仅 is_cross_mode_accessible=true)
-->
<template>
  <a-card class="mode-context-card" :body-style="{ padding: '14px' }">
    <template #title>
      <a-tag :color="strategy.display_color">{{ strategy.display_label }}</a-tag>
      <span class="mode-source">{{ strategy.source_mode }}</span>
    </template>
    <template #extra>
      <a-tooltip
        :title="strategy.write_mem0 ? 'Mem0 永久记忆已启用' : '仅 L2,不写 Mem0'"
      >
        <a-badge
          :status="strategy.write_mem0 ? 'success' : 'default'"
          :text="strategy.write_mem0 ? 'Mem0' : 'L2 only'"
        />
      </a-tooltip>
    </template>

    <a-row :gutter="8">
      <a-col :span="8">
        <a-statistic title="条目数" :value="bucket?.entry_count ?? 0" />
      </a-col>
      <a-col :span="8">
        <a-statistic title="TTL (h)" :value="strategy.ttl_hours" />
      </a-col>
      <a-col :span="8">
        <a-statistic title="优先级" :value="strategy.priority" />
      </a-col>
    </a-row>

    <div class="card-actions">
      <a-button size="small" @click="$emit('view-history', strategy)">
        查看历史
      </a-button>
      <a-button
        v-if="strategy.is_cross_mode_accessible"
        size="small"
        type="primary"
        ghost
        @click="$emit('enable-cross', strategy)"
      >
        跨模式读取:已启用
      </a-button>
      <a-tag v-else color="default">跨模式:隔离</a-tag>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type { FinalizeStrategy, ContextBreakdownBucket } from '@/api/aiContext.types'

defineProps<{
  strategy: FinalizeStrategy
  bucket?: ContextBreakdownBucket
}>()

defineEmits<{
  (e: 'view-history', s: FinalizeStrategy): void
  (e: 'enable-cross', s: FinalizeStrategy): void
}>()
</script>

<style scoped>
.mode-context-card {
  border-radius: 8px;
  transition: box-shadow 0.2s;
}
.mode-context-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.mode-source {
  margin-left: 8px;
  color: #888;
  font-family: monospace;
  font-size: 12px;
}
.card-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
