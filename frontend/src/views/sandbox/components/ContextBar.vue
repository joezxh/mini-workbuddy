<template>
  <div class="ctxbar">
    <div class="atabs">
      <div class="atab on"><span>推演沙盘</span></div>
    </div>
    <div class="ctx-sep"></div>
    <div class="srcchip">世界来源 · <b>{{ sourceLabel }}</b>
      <span class="tag g" v-if="hasScene">已发布</span>
    </div>
    <div class="kv-inline" v-if="hasScene">克隆范围：<b>{{ cloneScopeLabel }}</b></div>
    <div class="spacer"></div>
    <div class="kv-inline">可达运行 <b>{{ tick }}/{{ maxTick }}</b></div>
    <select class="msel" :value="execMode" title="执行模式"
      @change="emit('exec-mode', ($event.target as HTMLSelectElement).value)">
      <option value="auto">自动执行</option>
      <option value="stepwise">逐步确认</option>
      <option value="replay">只读回放</option>
    </select>
    <button class="btn sm" :disabled="!hasScene" @click="emit('save-checkpoint')">💾 保存检查点</button>
    <span class="pill warn">检查点 {{ checkpointCount }}/5</span>
    <button class="btn sm" :disabled="!hasScene" @click="emit('refresh')">↻ 刷新状态</button>
    <button class="btn sm" :disabled="!hasScene" @click="emit('open-kpi')">场景 KPI</button>
    <button class="btn sm" @click="emit('open-create')">＋ 新建场景</button>
    <button class="btn sm danger" :disabled="!hasScene" @click="emit('open-delete')">🗑 删除沙盘</button>
  </div>
</template>

<script setup lang="ts">
// 上下文栏（沙盘实例 + 运行控制）：纯展示 + 事件上抛，业务由编排壳处理。
defineProps<{
  sourceLabel: string
  cloneScopeLabel: string
  tick: number
  maxTick: number
  execMode: string
  checkpointCount: number
  hasScene: boolean
}>()

const emit = defineEmits<{
  (e: 'save-checkpoint'): void
  (e: 'refresh'): void
  (e: 'open-kpi'): void
  (e: 'open-create'): void
  (e: 'open-delete'): void
  (e: 'exec-mode', mode: string): void
}>()
</script>
