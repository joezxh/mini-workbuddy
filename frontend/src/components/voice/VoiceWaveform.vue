<template>
  <div class="voice-waveform" :class="{ active: (level ?? 0) > 0.01 }">
    <span v-for="n in bars" :key="n" class="bar" :style="barStyle(n)" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ level?: number }>()
const bars = 28

function barStyle(n: number): Record<string, string> {
  const lvl = props.level ?? 0
  const phase = (n / bars) * Math.PI * 2
  const wave = (Math.sin(phase) + 1) / 2
  const h = Math.max(6, lvl * 100 * (0.35 + 0.65 * wave))
  return {
    height: `${h}%`,
    animationDelay: `${(n * 60) % 800}ms`,
  }
}
</script>

<style scoped>
.voice-waveform {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 56px;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 8px;
}
.bar {
  width: 4px;
  background: #c0c4cc;
  border-radius: 2px;
  transition: height 0.1s ease;
}
.voice-waveform.active .bar {
  background: linear-gradient(180deg, #4096ff, #1677ff);
  animation: voice-bounce 0.9s ease-in-out infinite;
}
@keyframes voice-bounce {
  0%,
  100% {
    transform: scaleY(0.5);
  }
  50% {
    transform: scaleY(1);
  }
}
</style>
