<template>
  <div class="col">
    <div class="ph"><span>场景探索</span><div class="spacer"></div>
      <button class="mini" @click="emit('open-create')">＋ 场景</button></div>
    <div class="pb">
      <div class="sub">推演场景</div>
      <div v-if="!scenes.length" class="empty"><div class="ic">🗂</div>暂无推演场景<div style="margin-top:4px">点击右上角「＋ 新建场景」从已发布本体克隆世界</div></div>
      <div v-for="s in scenes" :key="s.scene_id" class="scard" :class="{ on: s.scene_id === currentSceneId }" @click="emit('select-scene', s.scene_id)">
        <div class="sh"><span class="tag" :class="sceneTagClass(s.status)">{{ sceneStatusLabel(s.status) }}</span><b>{{ s.name }}</b></div>
        <div class="sm">Tick {{ s.tick_now }}→{{ s.tick_max }} · {{ s.status }}</div>
      </div>

      <div class="sub">主时间线</div>
      <div class="tl">
        <div class="tli cur"><span class="mono" style="color:var(--fg3)">T0</span> · 克隆世界 · 基线快照<span class="cp"> ◆检查点</span></div>
        <div v-for="(o, idx) in timeline" :key="idx" class="tli" :class="{ done: (o.tick ?? 0) <= tick, cur: o.tick === tick }" @click="o.tick != null && emit('jump', o.tick)">
          <span class="mono" style="color:var(--fg3)">T{{ o.tick }}</span> · {{ truncate(o.title, 26) }}
        </div>
        <div v-if="!timeline.length" class="kv-inline" style="padding:4px 0">推进 Tick 后逐条展开</div>
      </div>

      <div class="sub">分支对比</div>
      <div v-for="b in branches" :key="b.id" class="brow" :class="{ sel: compareSet.has(b.id), on: b.id === selectedBranchId }" @click="emit('toggle-compare', b.id)">
        <span class="bd" :style="{ background: b.color || '#4aa3ff' }"></span>
        <span style="flex:1" @click.stop="emit('pick-branch', b.id)">{{ b.name }}</span>
        <span class="mono" style="font-size:10px;color:var(--fg3)">T{{ b.tick_now }}</span>
      </div>
      <button class="btn sm" style="width:100%;margin-top:4px" @click="emit('do-compare')">⇄ 对比所选分支</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Observation, SandboxBranch, SandboxScene } from '@/api/sandbox'
import { sceneStatusLabel, sceneTagClass, truncate } from '../sandboxFormat'

// 场景探索列（col ①）：场景卡 + 主时间线 + 分支对比，数据与游标由壳注入。
withDefaults(defineProps<{
  scenes: SandboxScene[]
  currentSceneId: number | null
  timeline: Observation[]
  branches: SandboxBranch[]
  selectedBranchId: number | null
  compareSet: Set<number>
  tick?: number
}>(), { tick: 0 })

const emit = defineEmits<{
  (e: 'select-scene', id: number): void
  (e: 'open-create'): void
  (e: 'jump', tick: number): void
  (e: 'pick-branch', id: number): void
  (e: 'toggle-compare', id: number): void
  (e: 'do-compare'): void
}>()
</script>
