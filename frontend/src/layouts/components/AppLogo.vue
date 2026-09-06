<script setup lang="ts">
// MiniWorkBuddy 产品标志（完整版）：六边形 Agent 网络图标 + 字标 + 标语。
// 仅当前应用内唯一渲染（侧栏展开态），故渐变/滤镜 id 使用命名空间前缀避免冲突。
const props = withDefaults(defineProps<{ size?: number }>(), { size: 28 })
</script>

<template>
  <svg
    class="app-logo"
    :style="{ height: props.size + 'px', width: 'auto' }"
    viewBox="0 0 320 64"
    role="img"
    aria-label="MiniWorkBuddy"
    xmlns="http://www.w3.org/2000/svg"
  >
    <defs>
      <linearGradient id="mwb-bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#4F6EF7" />
        <stop offset="100%" stop-color="#22D3AE" />
      </linearGradient>
      <linearGradient id="mwb-ag" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#22D3AE" />
        <stop offset="100%" stop-color="#4F6EF7" />
      </linearGradient>
      <filter id="mwb-gl">
        <feGaussianBlur stdDeviation="1.2" result="b" />
        <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>

    <!-- Icon Mark -->
    <polygon points="32,4 56,18 56,46 32,60 8,46 8,18" fill="none" stroke="url(#mwb-bg)" stroke-width="2" stroke-linejoin="round" opacity="0.6" />
    <line x1="32" y1="20" x2="22" y2="40" stroke="url(#mwb-bg)" stroke-width="1.2" opacity="0.4" />
    <line x1="32" y1="20" x2="42" y2="40" stroke="url(#mwb-bg)" stroke-width="1.2" opacity="0.4" />
    <line x1="22" y1="40" x2="42" y2="40" stroke="url(#mwb-bg)" stroke-width="1.2" opacity="0.4" />
    <circle cx="32" cy="33" r="3" fill="url(#mwb-bg)" filter="url(#mwb-gl)" opacity="0.5" />
    <circle cx="32" cy="20" r="4.5" fill="url(#mwb-bg)" filter="url(#mwb-gl)" />
    <circle cx="32" cy="20" r="2" fill="#fff" opacity="0.9" />
    <circle cx="22" cy="40" r="3.5" fill="url(#mwb-ag)" filter="url(#mwb-gl)" />
    <circle cx="22" cy="40" r="1.5" fill="#fff" opacity="0.9" />
    <circle cx="42" cy="40" r="3.5" fill="url(#mwb-ag)" filter="url(#mwb-gl)" />
    <circle cx="42" cy="40" r="1.5" fill="#fff" opacity="0.9" />

    <!-- Wordmark -->
    <text x="74" y="30" font-family="'Space Grotesk','IBM Plex Sans',system-ui,sans-serif" font-size="22" font-weight="700" fill="#E8ECF1" letter-spacing="-0.5">
      Mini<tspan fill="url(#mwb-bg)">Work</tspan>Buddy
    </text>

    <!-- Tagline -->
    <text x="74" y="48" font-family="'IBM Plex Sans','Space Grotesk',system-ui,sans-serif" font-size="10" fill="#8892A4" letter-spacing="2">
      AI WORKSTATION
    </text>
  </svg>
</template>

<style scoped>
.app-logo {
  display: block;
  width: 100%;
  height: 100%;
  flex-shrink: 0;
}
</style>
