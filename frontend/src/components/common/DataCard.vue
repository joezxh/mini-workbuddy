/**
 * 数据卡片组件
 */
<template>
  <div class="data-card" :class="`data-card--${type}`">
    <div class="data-card__icon">
      <component :is="icon" />
    </div>
    <div class="data-card__content">
      <div class="data-card__label">{{ label }}</div>
      <div class="data-card__value">
        <span class="data-card__number">{{ formattedValue }}</span>
        <span v-if="unit" class="data-card__unit">{{ unit }}</span>
      </div>
      <div v-if="trend !== undefined" class="data-card__trend" :class="trendClass">
        <component :is="trendIcon" />
        <span>{{ Math.abs(trend) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  DashboardOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined
} from '@ant-design/icons-vue'

interface Props {
  label: string
  value: number
  unit?: string
  icon?: any
  type?: 'primary' | 'success' | 'warning' | 'danger'
  trend?: number
}

const props = withDefaults(defineProps<Props>(), {
  icon: DashboardOutlined,
  type: 'primary'
})

const formattedValue = computed(() => {
  if (props.value >= 10000) {
    return (props.value / 10000).toFixed(1) + 'w'
  }
  return props.value.toLocaleString()
})

const trendClass = computed(() => {
  if (props.trend === undefined) return ''
  return props.trend >= 0 ? 'data-card__trend--up' : 'data-card__trend--down'
})

const trendIcon = computed(() => {
  if (props.trend === undefined) return null
  return props.trend >= 0 ? ArrowUpOutlined : ArrowDownOutlined
})
</script>

<style lang="less" scoped>
.data-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-surface);
  -webkit-backdrop-filter: var(--glass);
  backdrop-filter: var(--glass);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition), box-shadow var(--transition);

  &:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow);
  }

  &__icon {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    font-size: 24px;
    background: var(--bg-input);
  }

  &--primary &__icon {
    background: var(--accent-soft);
    color: var(--accent);
  }

  &--success &__icon {
    background: var(--ok-soft);
    color: var(--ok);
  }

  &--warning &__icon {
    background: var(--warn-soft);
    color: var(--warn);
  }

  &--danger &__icon {
    background: var(--err-soft);
    color: var(--err);
  }

  &__content {
    flex: 1;
  }

  &__label {
    font-family: var(--font-tech);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--fg-muted);
    margin-bottom: 8px;
  }

  &__value {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }

  &__number {
    font-family: var(--font-display);
    font-size: 28px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--fg);
    line-height: 1;
  }

  &__unit {
    font-size: 14px;
    color: var(--fg-muted);
  }

  &__trend {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 8px;
    font-size: 12px;

    &--up {
      color: var(--ok);
    }

    &--down {
      color: var(--err);
    }
  }
}
</style>

