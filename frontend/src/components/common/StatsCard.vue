/**
 * AI Context Stats Card - 多模式会话上下文统计卡片
 * 
 * 展示 ContextManager 三层架构的关键指标：
 * - Shared Layer (共享层) 上下文数量
 * - Isolated Layer (隔离层) 各模式统计数据
 * - Mem0 Layer (长期记忆层) 集成状态
 */
<template>
  <div class="stats-card" :class="`stats-card--${mode}`">
    <!-- Header: Title + Last Updated -->
    <div class="stats-card__header">
      <div class="stats-card__title">
        <component :is="icon" class="stats-card__icon" />
        <span>{{ title }}</span>
      </div>
      <div v-if="lastUpdated" class="stats-card__timestamp">
        {{ lastUpdated }}
      </div>
    </div>

    <!-- Main Content: Layer Statistics -->
    <div class="stats-card__content">
      <!-- Shared Layer Stat -->
      <div class="stats-card__stat-item shared">
        <div class="stats-card__stat-icon">
          <ShareOutlined class="stats-card__stat-icon__svg" />
        </div>
        <div class="stats-card__stat-info">
          <div class="stats-card__stat-label">{{ t('context.stats.sharedLabel') }}</div>
          <div class="stats-card__stat-value">
            <span class="stats-card__stat-number">{{ props.stats.shared_context_count }}</span>
            <span class="stats-card__stat-unit">{{ t('common.entryCount') }}</span>
          </div>
        </div>
      </div>

      <!-- Mode-Specific Statistics Grid -->
      <div v-if="props.stats.modes && Object.keys(props.stats.modes).length > 0" class="stats-card__modes-grid">
        <div
          v-for="(modeData, modeName) in props.stats.modes"
          :key="modeName"
          class="stats-card__mode-item"
          :class="`stats-card__mode-item--${modeName}`"
        >
          <div class="stats-card__mode-header">
            <span class="stats-card__mode-name">
              {{ getModeDisplayName(modeName) }}
            </span>
            <span class="stats-card__mode-count">
              {{ modeData.entry_count }} entries
            </span>
          </div>
          
          <div class="stats-card__mode-stats">
            <div class="stats-card__mode-stat token">
              <span class="stats-card__mode-stat__label">{{ t('context.stats.tokenUsage') }}</span>
              <span class="stats-card__mode-stat__value">{{ formatTokens(modeData.total_tokens) }}</span>
            </div>
            <div class="stats-card__mode-stat priority">
              <span class="stats-card__mode-stat__label">{{ t('context.stats.avgPriority') }}</span>
              <span class="stats-card__mode-stat__value">{{ modeData.avg_priority }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Mem0 Long-Term Memory Status -->
      <div v-if="props.stats.mem0_enabled !== undefined" class="stats-card__mem0-status">
        <div class="stats-card__mem0-indicator" :class="{ 'stats-card__mem0-indicator--active': props.stats.mem0_enabled }">
          <div v-if="props.stats.mem0_enabled" class="status-dot"></div>
        </div>
        <div class="stats-card__mem0-text">
          <span>{{ props.stats.mem0_enabled ? t('context.stats.mem0Enabled') : t('context.stats.mem0Disabled') }}</span>
          <span v-if="props.stats.mem0_memory_count && props.stats.mem0_enabled" class="stats-card__mem0-extra">
            ({{ props.stats.mem0_memory_count }} memories)
          </span>
        </div>
      </div>
    </div>

    <!-- Footer: Total Count + Refresh Button -->
    <div class="stats-card__footer">
      <div class="stats-card__total">
        <span class="stats-card__total-label">{{ t('context.stats.totalEntries') }}:</span>
        <span class="stats-card__total-value">{{ props.stats.total_entries }}</span>
      </div>
      <button @click="onRefresh" class="stats-card__refresh-btn" :disabled="loading">
        <component :is="loading ? LoadingOutlined : ReloadOutlined" />
        <span>{{ loading ? t('common.refreshing') : t('common.refresh') }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ShareOutlined,
  ReloadOutlined,
  LoadingOutlined
} from '@ant-design/icons-vue'
import type { Component } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ContextStats } from '@/api/aiContext.types'

// Props definition
interface Props {
  title?: string
  icon?: Component
  stats: ContextStats
  lastUpdated?: string
  onRefresh: () => void
  mode?: 'default' | 'compact' | 'detailed'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: 'AI Context Stats',
  icon: ShareOutlined,
  mode: 'default',
  loading: false
})

const emit = defineEmits<{
  refresh: []
}>()

const { t } = useI18n()

// Formatted timestamp
const formattedTimestamp = computed(() => {
  if (!props.lastUpdated) return ''
  try {
    const date = new Date(props.lastUpdated)
    return date.toLocaleString(getLocale())
  } catch {
    return props.lastUpdated
  }
})

// Get locale from i18n
function getLocale(): string {
  const locale = t('locale')
  return locale === 'zh-CN' ? 'zh-CN' : 'en-US'
}

// Format token count to human readable
function formatTokens(tokens: number): string {
  if (tokens >= 1000000) {
    return (tokens / 1000000).toFixed(1) + 'M'
  } else if (tokens >= 1000) {
    return (tokens / 1000).toFixed(1) + 'K'
  }
  return tokens.toString()
}

// Get mode display name with i18n
function getModeDisplayName(mode: string): string {
  const names: Record<string, string> = {
    dify: t('context.modes.dify'),
    sqlbot: t('context.modes.sqlbot'),
    agentscope: t('context.modes.agentscope')
  }
  return names[mode] || mode
}

// Handle refresh click
function handleRefresh() {
  emit('refresh')
  props.onRefresh()
}

</script>

<style lang="less" scoped>
.stats-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition);

  &:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow);
  }

  &--default {
    // Default styling
  }

  &--compact {
    padding: 16px;
    
    .stats-card__title {
      font-size: 16px;
    }
    
    .stats-card__value {
      font-size: 24px;
    }
  }

  &--detailed {
    .stats-card__modes-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }
  }

  // Header
  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }

  &__title {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 18px;
    font-weight: 600;
    color: var(--fg);

    &__icon {
      font-size: 20px;
      color: var(--accent);
    }
  }

  &__timestamp {
    font-size: 12px;
    color: var(--fg-muted);
    font-family: var(--font-tech);
  }

  // Content
  &__content {
    margin-bottom: 20px;
  }

  &__stat-item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px;
    background: var(--bg-soft);
    border-radius: var(--radius-sm);
    margin-bottom: 12px;
    transition: background var(--transition);

    &:hover {
      background: var(--bg-hover);
    }

    &.shared {
      border-left: 3px solid var(--accent);
    }

    &__icon {
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--accent-soft);
      border-radius: var(--radius-sm);

      &__svg {
        font-size: 18px;
        color: var(--accent);
      }
    }

    &__info {
      flex: 1;
    }

    &__label {
      font-size: 12px;
      color: var(--fg-muted);
      margin-bottom: 4px;
    }

    &__value {
      display: flex;
      align-items: baseline;
      gap: 6px;
    }

    &__number {
      font-size: 24px;
      font-weight: 700;
      color: var(--fg);
      font-family: var(--font-display);
      font-variant-numeric: tabular-nums;
    }

    &__unit {
      font-size: 13px;
      color: var(--fg-muted);
    }
  }

  // Modes Grid
  &__modes-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 16px;
  }

  &__mode-item {
    padding: 16px;
    background: var(--bg-soft);
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--border);
    transition: all var(--transition);

    &:hover {
      transform: translateX(4px);
      border-left-color: var(--accent);
    }

    &--dify {
      border-left-color: #FF6A00;
    }

    &--sqlbot {
      border-left-color: #5C6BC0;
    }

    &--agentscope {
      border-left-color: #26A69A;
    }

    &__header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    &__name {
      font-size: 14px;
      font-weight: 600;
      color: var(--fg);
    }

    &__count {
      font-size: 12px;
      color: var(--fg-muted);
      background: var(--bg-surface);
      padding: 4px 8px;
      border-radius: var(--radius-sm);
    }

    &__stats {
      display: flex;
      gap: 20px;
    }

    &__stat {
      display: flex;
      flex-direction: column;
      gap: 4px;

      &__label {
        font-size: 11px;
        color: var(--fg-muted);
      }

      &__value {
        font-size: 16px;
        font-weight: 600;
        color: var(--fg);
        font-family: var(--font-display);
      }
    }
  }

  // Mem0 Status
  &__mem0-status {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 20px;
    padding: 12px;
    background: var(--bg-soft);
    border-radius: var(--radius-sm);
  }

  &__mem0-indicator {
    position: relative;
    width: 24px;
    height: 24px;

    &--active .status-dot {
      animation: pulse 2s infinite;
    }
  }

  .status-dot {
    width: 10px;
    height: 10px;
    background: var(--success);
    border-radius: 50%;
    position: absolute;
    top: 7px;
    left: 7px;
  }

  &__mem0-text {
    flex: 1;
    font-size: 13px;
    color: var(--fg);

    &-extra {
      font-size: 12px;
      color: var(--fg-muted);
      margin-left: 8px;
    }
  }

  // Footer
  &__footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 16px;
    border-top: 1px solid var(--border);
  }

  &__total {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;

    &-label {
      color: var(--fg-muted);
    }

    &-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--accent);
      font-family: var(--font-display);
    }
  }

  &__refresh-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition);

    &:hover:not(:disabled) {
      opacity: 0.9;
      transform: translateY(-1px);
    }

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
