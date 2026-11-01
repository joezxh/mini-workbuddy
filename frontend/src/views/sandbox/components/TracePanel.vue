<template>
  <div class="col">
    <div class="ptabs">
      <button v-for="t in traceTabs" :key="t.k" class="ptab" :class="{ on: tview === t.k }" @click="emit('set-view', t.k)">{{ t.label }}</button>
    </div>
    <div class="pb">
      <!-- goal -->
      <template v-if="tview === 'goal'">
        <div class="sub">已声明目标 · {{ goalElements.length }}</div>
        <div v-for="g in goalElements" :key="g.id" class="obs info" :style="{ borderLeftColor: 'var(--ok)' }">
          <div class="oh" style="color:inherit">🎯 {{ g.code }} <span class="pill ok" style="margin-left:auto">{{ g.status }}</span></div>{{ g.label }}
        </div>
        <div v-if="!goalElements.length" class="empty"><div class="ic">◎</div>尚未声明目标<div style="margin-top:4px">在配置元素中新增 goal 类型用于评估方案可信度</div></div>
      </template>
      <!-- trace -->
      <template v-else-if="tview === 'trace'">
        <div class="sub">传播过程 · Propagation Trace <span style="margin-left:auto;font-family:var(--mono);color:var(--fg3)">最近 Tick {{ tick }}</span></div>
        <div class="impact-cnt">
          <div class="icbox"><div class="k">实体</div><div class="v" style="color:var(--accent)">{{ entityCount }}</div></div>
          <div class="icbox"><div class="k">关系</div><div class="v" style="color:var(--purple)">{{ relationCount }}</div></div>
          <div class="icbox"><div class="k">规则</div><div class="v" style="color:var(--amber)">{{ ruleElements.length }}</div></div>
        </div>
        <div v-for="o in traceObs" :key="o.id" class="obs" :class="obsSevClass(o.severity)">
          <div class="oh">{{ sevIcon(o.severity) }} {{ o.kind }} · T{{ o.tick }}</div>{{ o.title }}
        </div>
        <div v-if="!traceObs.length" class="empty"><div class="ic">◷</div>尚无传播记录<div style="margin-top:4px">推进 Tick 或施加行动后，因果链影响将在此逐条展开</div></div>
      </template>
      <!-- future -->
      <template v-else-if="tview === 'future'">
        <div class="sub">未来事件预测 · 基于世界模型</div>
        <div v-for="(f, i) in futureItems" :key="i" class="obs info"><div class="oh">◷ {{ f.title }}</div>{{ formatFutureSummary(f) }}</div>
        <div v-if="!futureItems.length" class="empty"><div class="ic">🔮</div>无待发生的预测事件<div style="margin-top:4px">当前因果链已推进至末端，或尚未产生会作用于未来的边</div></div>
      </template>
      <!-- rule -->
      <template v-else>
        <div class="sub">规则系统 · 本体派生/失效规则</div>
        <div v-for="r in ruleElements" :key="r.id" style="display:flex;align-items:center;gap:6px;padding:6px 0;border-bottom:1px dashed var(--divider);font-size:11.5px">
          <span style="flex:1;color:var(--fg)">{{ r.label || r.code }}</span>
          <span class="pill ok">{{ r.status }}</span>
        </div>
        <div v-if="!ruleElements.length" class="empty"><div class="ic">⚖</div>暂无规则元素</div>
        <div class="obs info" style="margin-top:10px"><div class="oh">◷ 规则发现</div>Tick 推进后新发现失效规则会在「传播过程」与「观察」中提示，用于判断方案是否可信。</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Element, Observation } from '@/api/sandbox'
import { formatFutureSummary, obsSevClass, sevIcon } from '../sandboxFormat'

// 传播过程列（col ③）：目标 / 传播 / 未来 / 规则四视图，视图游标由壳持有。
type TraceView = 'goal' | 'trace' | 'future' | 'rule'

defineProps<{
  tview: TraceView
  goalElements: Element[]
  ruleElements: Element[]
  traceObs: Observation[]
  futureItems: Observation[]
  entityCount: number
  relationCount: number
  tick: number
}>()

const emit = defineEmits<{ (e: 'set-view', v: TraceView): void }>()

const traceTabs = [
  { k: 'goal', label: '目标体系' }, { k: 'trace', label: '传播过程' },
  { k: 'future', label: '未来事件' }, { k: 'rule', label: '规则系统' },
] as const
</script>
