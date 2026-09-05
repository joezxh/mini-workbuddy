/**
 * 科技感卡片组件
 */
<template>
  <div class="tech-card" :class="{ 'tech-card--hover': hoverable }">
    <div v-if="title" class="tech-card__header">
      <div class="tech-card__title">{{ title }}</div>
      <div v-if="$slots.extra" class="tech-card__extra">
        <slot name="extra"></slot>
      </div>
    </div>
    <div class="tech-card__body">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title?: string
  hoverable?: boolean
}

withDefaults(defineProps<Props>(), {
  hoverable: false
})
</script>

<style lang="less" scoped>
.tech-card {
  background: var(--bg-surface);
  -webkit-backdrop-filter: var(--glass);
  backdrop-filter: var(--glass);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 18px 20px;
  position: relative;
  overflow: hidden;
  transition: border-color var(--transition), box-shadow var(--transition),
    transform var(--transition);

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
  }

  &--hover:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow-lg);
    transform: translateY(-2px);
  }

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--divider);
  }

  &__title {
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 600;
    color: var(--fg);
  }

  &__extra {
    color: var(--fg-secondary);
  }

  &__body {
    color: var(--fg);
  }
}
</style>

