<script setup lang="ts">
// MiniWorkBuddy 产品标志：渐变圆角方块 + 对话气泡 + 输入指示点，
// 呼应“智能工作助手 (WorkBuddy)”的产品定位。
const props = withDefaults(defineProps<{ size?: number }>(), { size: 28 })
// 每个实例使用唯一 id，避免多个 Logo 同处文档时 SVG 渐变 id 冲突
const gid = `mwg-${Math.random().toString(36).slice(2, 8)}`
</script>

<template>
  <svg
    class="app-logo"
    :width="props.size"
    :height="props.size"
    viewBox="0 0 32 32"
    role="img"
    aria-label="MiniWorkBuddy"
  >
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#22d3ee" />
        <stop offset="55%" stop-color="#3b82f6" />
        <stop offset="100%" stop-color="#6366f1" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="30" height="30" rx="9" :fill="`url(#${gid})`" />
    <path
      d="M9 10.5h14a2.5 2.5 0 0 1 2.5 2.5v4a2.5 2.5 0 0 1 -2.5 2.5h-8.5l-4 3v-3h-1.5a2.5 2.5 0 0 1 -2.5 -2.5v-4a2.5 2.5 0 0 1 2.5 -2.5z"
      fill="#ffffff"
      fill-opacity="0.96"
    />
    <circle cx="14.5" cy="15" r="1.5" fill="#22d3ee" />
    <circle cx="19" cy="15" r="1.5" fill="#6366f1" />
  </svg>
</template>

<style scoped>
.app-logo {
  display: block;
  flex-shrink: 0;
}
</style>
