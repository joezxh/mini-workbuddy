<template>
  <div class="mask" v-if="show">
    <div class="modal">
      <div class="mh">📊 场景 KPI · {{ sceneName }}<div class="spacer"></div><span class="pill">Tick {{ tick }}</span></div>
      <div class="mb">
        <div class="impact-cnt" style="margin-bottom:12px">
          <div class="icbox"><div class="k">需求态势</div><div class="v" :style="{ color: health.color }">{{ health.label }}</div></div>
          <div class="icbox"><div class="k">可控性</div><div class="v" :style="{ color: controllability.color }">{{ controllability.label }}</div></div>
          <div class="icbox"><div class="k">实体数</div><div class="v" style="color:var(--accent)">{{ entityCount }}</div></div>
        </div>
        <div class="sub" style="margin-top:0">关键指标</div>
        <div class="kv"><span class="k">当前分支</span><span class="v">{{ branchName || '—' }}</span></div>
        <div class="kv"><span class="k">Tick / 上限</span><span class="v">{{ tick }} / {{ maxTick }}</span></div>
        <div class="kv"><span class="k">已触发观察</span><span class="v">{{ observationCount }}</span></div>
        <div class="kv"><span class="k">行动窗口</span><span class="v" style="color:var(--accent)">#0–#{{ maxTick }}</span></div>
      </div>
      <div class="mf"><button class="btn" @click="emit('close')">关闭</button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 场景 KPI 模态：数值与配色由壳经 derive* 计算后注入。
defineProps<{
  show: boolean
  sceneName: string
  tick: number
  health: { label: string; color: string }
  controllability: { label: string; color: string }
  entityCount: number
  branchName: string
  observationCount: number
  maxTick: number
}>()

const emit = defineEmits<{ (e: 'close'): void }>()
</script>
