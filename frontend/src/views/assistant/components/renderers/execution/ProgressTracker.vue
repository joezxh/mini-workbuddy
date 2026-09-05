<template>
  <div class="progress-tracker">
    <div class="progress-info">
      <span class="progress-stage">{{ stage }}</span>
      <span class="progress-message">{{ message }}</span>
    </div>
    <a-progress :percent="progress" :show-info="false" size="small" :status="progress >= 100 ? 'success' : 'active'" />
  </div>
</template>

<script setup lang="ts">
defineProps<{ stage: string; progress: number; message: string }>()
</script>

<style scoped lang="less">
.progress-tracker { padding: 6px 10px; }
.progress-info { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 12px; }
.progress-stage { font-weight: 600; color: var(--accent); }
.progress-message { color: var(--fg-secondary); }
</style>
