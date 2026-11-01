<template>
  <div class="tickbar">
    <div class="tb-sec">
      <div class="tb-lbl">推演时钟 · TICK</div>
      <div class="playrow">
        <button class="btn sm" @click="emit('toggle-auto')" :disabled="!canAdvance">{{ autoOn ? '⏸ 暂停' : '▶ 自动推进' }}</button>
        <button class="btn sm" @click="emit('step', 1)" :disabled="!canAdvance">Step +1</button>
        <button class="btn sm" @click="emit('step', 10)" :disabled="!canAdvance">Step +10</button>
        <span class="ticknum">Tick <b>{{ tick }}</b>/{{ maxTick }}</span>
      </div>
    </div>
    <div class="scrub-wrap">
      <div class="tb-lbl" style="margin-bottom:2px">主时间线 · 点击 Tick 可跳转</div>
      <div class="scrub">
        <div v-for="i in scrubTicks" :key="i" class="sg" :class="{ done: i < tick, cur: i === tick }" @click="emit('jump', i)">
          <span v-if="cpTicks.has(i)" class="cp"></span>
          <div class="bar"></div><span class="n">{{ i }}</span>
        </div>
      </div>
    </div>
    <div class="kpi">
      <div class="box"><span class="k">需求态势</span><span class="v" :style="{ color: health.color }">{{ health.label }}</span></div>
      <div class="box"><span class="k">可控性</span><span class="v" :style="{ color: controllability.color }">{{ controllability.label }}</span></div>
      <div class="box"><span class="k">目标体系</span><span class="v" style="color:var(--fg2)">{{ goalCount }}</span></div>
      <div class="box"><span class="k">行动窗口</span><span class="v" style="font-size:11px;color:var(--accent)">#0–#{{ maxTick }}</span></div>
    </div>
    <div class="kpi" style="border-right:0">
      <div class="tb-lbl">风险 TOP 3</div>
      <div class="riskrow" v-for="r in riskTop3" :key="r.entity_code">
        <span>{{ r.name }}</span>
        <span class="sc" :style="riskChipStyle(r.score)">{{ r.score }}</span>
      </div>
      <div class="kv-inline" v-if="!riskTop3.length">推进 Tick 后生成</div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Tick 控制条 + 主时间线 + KPI 摘要：推进/跳转由壳执行，本组件只发意图。
defineProps<{
  tick: number
  maxTick: number
  scrubTicks: number[]
  cpTicks: Set<number>
  canAdvance: boolean
  autoOn: boolean
  health: { label: string; color: string }
  controllability: { label: string; color: string }
  goalCount: number
  riskTop3: { entity_code: string; score: number; name: string }[]
}>()

const emit = defineEmits<{
  (e: 'toggle-auto'): void
  (e: 'step', n: number): void
  (e: 'jump', tick: number): void
}>()

const riskChipStyle = (score: number) =>
  score >= 0.6
    ? { background: 'var(--err-soft)', color: 'var(--err)' }
    : { background: 'var(--warn-soft)', color: 'var(--warn)' }
</script>
