<!-- frontend/src/views/twin/TwinWorkspace.vue —— 工作区壳：ctxbar(42) + 左238/中1fr/右336 + statusbar(30) -->
<template>
  <div class="twin-workspace">
    <header class="tw-ctxbar">
      <span class="tw-brand">孪生应用</span>
      <span class="tw-sep"></span>
      <span class="tw-card">{{ store.cardDetail?.name ?? '未选择卡片' }}</span>
      <span v-if="store.cardDetail?.stale" class="tw-stale">本体版本落后</span>
    </header>

    <div class="tw-body">
      <aside class="tw-left">
        <TwinCardList @perm-request="onPermRequest" />
        <PageModuleList @add="onAddModule" />
      </aside>

      <main class="tw-mid">
        <CanvasToolbar @add-module="onAddModule()" />
        <TwinCanvas />
      </main>

      <aside class="tw-right">
        <div class="tw-ai-dock" aria-disabled="true">
          <div class="aid-title">AI 助手</div>
          <div class="aid-hint">P0 暂不可用（骨架占位，Task 8 接 TwinAiDock）</div>
        </div>
      </aside>
    </div>

    <footer class="tw-statusbar">
      <label class="sb-item">刷新
        <select class="sb-select" :value="store.intervalMs" @change="onRefreshChange">
          <option :value="10000">10 秒</option>
          <option :value="30000">30 秒</option>
          <option :value="0">关闭</option>
        </select>
      </label>
      <span class="sb-item">组件 {{ store.widgets.length }}</span>
      <span class="sb-item">{{ collectedText }}</span>
    </footer>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useTwinStore } from '@/stores/twin'
import TwinCardList from './TwinCardList.vue'
import PageModuleList from './PageModuleList.vue'
import CanvasToolbar from './CanvasToolbar.vue'
import TwinCanvas from './TwinCanvas.vue'
import type { ResultShape, TwinCard } from '@/types/twin'

const store = useTwinStore()

const collectedText = computed(() =>
  store.collectedAt ? '采集于 ' + new Date(store.collectedAt).toLocaleTimeString() : '尚未采集')

function onRefreshChange(e: Event) {
  const ms = Number((e.target as HTMLSelectElement).value)
  store.applyRefreshCfg({ interval: ms })   // 归一 10000/30000/0
  store.stopScheduler()
  store.startScheduler()
}

// 占位事件：Task 8 分别接 PermDrawer / AddModuleModal
function onPermRequest(card: TwinCard) { console.log('[twin] perm-request →', card.id) }
function onAddModule(shape?: ResultShape) { console.log('[twin] add-module →', shape ?? '(toolbar)') }

// 注：计划示例把 onBeforeUnmount 嵌在 onMounted 回调内（无效注册）；Vue 钩子须在 setup 同步顶层登记（D-13）
const onVis = () => store.onVisibility(document.hidden)
onMounted(async () => {
  await store.loadCards()
  const first = store.cards.mine[0] ?? store.cards.shared[0]
  if (first) await store.openCard(first.id)
  document.addEventListener('visibilitychange', onVis)
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', onVis)
  store.stopScheduler()
})
</script>
<style scoped>
.twin-workspace {
  --twin-top: 100%;
  --twin-ctxbar: 42px;
  --twin-statusbar: 30px;
  display: flex; flex-direction: column; height: var(--twin-top); min-height: 0; overflow: hidden;
  background: var(--bg-base); color: var(--fg);
}
.tw-ctxbar { display: flex; align-items: center; gap: 10px; height: var(--twin-ctxbar); padding: 0 14px; background: var(--bg-page); border-bottom: 1px solid var(--border); flex: none; }
.tw-brand { font-size: 13px; font-weight: 600; color: var(--fg); }
.tw-sep { width: 1px; height: 18px; background: var(--divider); }
.tw-card { font-size: 12px; color: var(--fg-secondary); }
.tw-stale { font-size: 11px; color: var(--warn); padding: 2px 8px; border-radius: 8px; background: var(--warn-soft); }
.tw-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 238px 1fr 336px; }
.tw-left { display: flex; flex-direction: column; min-height: 0; overflow: hidden; border-right: 1px solid var(--border); background: var(--bg-page); }
.tw-mid { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.tw-right { border-left: 1px solid var(--border); background: var(--bg-page); }
.tw-ai-dock { display: flex; flex-direction: column; gap: 8px; padding: 12px; opacity: .55; }
.aid-title { font-size: 12px; font-weight: 600; color: var(--fg-secondary); }
.aid-hint { font-size: 11px; color: var(--fg-muted); }
.tw-statusbar { display: flex; align-items: center; gap: 16px; height: var(--twin-statusbar); padding: 0 12px; background: var(--bg-page); border-top: 1px solid var(--border); flex: none; }
.sb-item { font-size: 11px; color: var(--fg-muted); display: inline-flex; align-items: center; gap: 6px; }
.sb-select { font-size: 11px; color: var(--fg); background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px; padding: 1px 6px; }
</style>
