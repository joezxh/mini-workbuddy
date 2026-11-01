<!-- frontend/src/views/twin/CanvasToolbar.vue —— 画布顶部：页签 / scene_key tag / 编辑·运行段控件 / 添加模块入口 -->
<template>
  <div class="canvas-toolbar">
    <div class="page-tabs">
      <button v-for="p in store.pages" :key="p.id" class="ptab" :class="{ on: p.id === store.activePageId }"
        @click="store.selectPage(p.id)">{{ p.name }}</button>
      <span v-if="!store.pages.length" class="no-page">暂无页面</span>
    </div>
    <span v-if="store.cardDetail?.scene_key" class="scene-tag">{{ store.cardDetail.scene_key }}</span>
    <div class="spacer"></div>
    <div class="mode-seg">
      <button :class="{ on: store.mode === 'edit' }" @click="store.setMode('edit')">编辑</button>
      <button :class="{ on: store.mode === 'run' }" @click="store.setMode('run')">运行</button>
    </div>
    <button class="add-mod" :disabled="!store.activePageId" @click="$emit('add-module')">+ 模块</button>
  </div>
</template>
<script setup lang="ts">
import { useTwinStore } from '@/stores/twin'
defineEmits<{ 'add-module': [] }>()
const store = useTwinStore()
</script>
<style scoped>
.canvas-toolbar { display: flex; align-items: center; gap: 10px; height: var(--twin-ctxbar, 42px); padding: 0 12px; background: var(--bg-page); border-bottom: 1px solid var(--border); flex: none; }
.page-tabs { display: flex; gap: 4px; }
.ptab { padding: 4px 10px; border-radius: 8px; font-size: 12px; color: var(--fg-muted); background: transparent; border: 1px solid transparent; cursor: pointer; }
.ptab.on { color: var(--fg); background: var(--bg-surface); border-color: var(--border); }
.no-page { font-size: 12px; color: var(--fg-muted); }
.scene-tag { font-size: 11px; color: var(--accent); padding: 2px 8px; border-radius: 8px; background: var(--accent-soft); }
.spacer { flex: 1; }
.mode-seg { display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.mode-seg button { padding: 4px 12px; font-size: 12px; color: var(--fg-muted); background: transparent; border: none; cursor: pointer; }
.mode-seg button.on { color: var(--fg-inverse); background: var(--accent); }
.add-mod { padding: 4px 12px; font-size: 12px; color: var(--accent); background: var(--bg-surface); border: 1px solid var(--border-strong); border-radius: 8px; cursor: pointer; }
.add-mod:disabled { color: var(--fg-muted); cursor: not-allowed; opacity: .5; }
</style>
