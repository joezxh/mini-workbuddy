/**
 * 加载动画组件
 */
<template>
  <div class="loading-spinner" :class="{ 'loading-spinner--fullscreen': fullscreen }">
    <div class="loading-spinner__content">
      <div class="loading-spinner__icon">
        <div class="spinner"></div>
      </div>
      <div v-if="text" class="loading-spinner__text">{{ text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  text?: string
  fullscreen?: boolean
}

withDefaults(defineProps<Props>(), {
  fullscreen: false
})
</script>

<style lang="less" scoped>
.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;

  &--fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--bg-base);
    z-index: 9999;
  }

  &__content {
    text-align: center;
  }

  &__icon {
    margin-bottom: 16px;
  }

  &__text {
    color: var(--fg-secondary);
    font-size: 14px;
  }
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 2s;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

