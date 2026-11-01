<!-- frontend/src/views/twin/TwinCardList.vue —— 左上孪生卡片列表：三组 + 状态徽标 + 新建卡片最小表单 -->
<template>
  <div class="card-list">
    <div class="cl-head">
      <span class="cl-title">孪生卡片</span>
      <button class="cl-add" @click="openCreate">+ 新建</button>
    </div>
    <div class="cl-scroll">
      <section v-for="grp in groups" :key="grp.key" class="cl-group">
        <div class="cl-glabel">{{ grp.label }} <span class="cl-gcount">{{ grp.items.length }}</span></div>
        <div v-for="c in grp.items" :key="c.id" class="cl-card"
          :class="{ on: c.id === store.activeCardId, restricted: grp.key === 'restricted' }"
          @click="onPick(grp.key, c)">
          <span class="cl-name">{{ c.name }}</span>
          <span v-if="grp.key === 'shared' && daysLeft(c) != null" class="cl-days">剩 {{ daysLeft(c) }} 天</span>
          <span v-if="grp.key === 'restricted'" class="cl-lock">🔒</span>
          <span v-else class="cl-badge" :class="c.runtime_state">{{ stateText(c.runtime_state) }}</span>
        </div>
      </section>
    </div>
    <a-modal v-model:open="formOpen" title="新建卡片" :confirm-loading="creating" @ok="submitCreate">
      <a-form layout="vertical" size="small">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="卡片名称" />
        </a-form-item>
        <a-form-item label="本体 ID" required>
          <a-input-number v-model:value="form.ontology_id" :min="1" style="width:100%" placeholder="ontology_id" />
        </a-form-item>
        <a-form-item label="本体版本" required>
          <a-input-number v-model:value="form.ontology_version" :min="1" style="width:100%" />
        </a-form-item>
        <a-form-item label="场景 Key">
          <a-input v-model:value="form.scene_key" placeholder="可选 scene_key" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useTwinStore } from '@/stores/twin'
import * as api from '@/api/twin'
import type { TwinCard, RuntimeState } from '@/types/twin'

const emit = defineEmits<{ 'perm-request': [card: TwinCard] }>()
const store = useTwinStore()

const groups = computed(() => [
  { key: 'mine', label: '我的', items: store.cards.mine },
  { key: 'shared', label: '共享给我的', items: store.cards.shared },
  { key: 'restricted', label: '受限', items: store.cards.restricted },
] as { key: string; label: string; items: TwinCard[] }[])

function stateText(s: RuntimeState) { return { draft: '草稿', live: '运行中', paused: '已暂停' }[s] }

// 共享卡剩余天数：由 share_expires_at 换算（不足一天进一，过期为 0）
function daysLeft(c: TwinCard): number | null {
  if (!c.share_expires_at) return null
  const ms = new Date(c.share_expires_at).getTime() - Date.now()
  return ms > 0 ? Math.ceil(ms / 86400000) : 0
}

async function onPick(key: string, c: TwinCard) {
  // 受限卡不发取数（403 会被后端堵），直接 emit 占位；Task 8 开 PermDrawer
  if (key === 'restricted') { emit('perm-request', c); return }
  await store.openCard(c.id)
}

const formOpen = ref(false)
const creating = ref(false)
const form = reactive<{ name: string; ontology_id: number | null; ontology_version: number; scene_key: string }>(
  { name: '', ontology_id: null, ontology_version: 1, scene_key: '' })

function openCreate() {
  form.name = ''; form.ontology_id = null; form.ontology_version = 1; form.scene_key = ''
  formOpen.value = true
}

async function submitCreate() {
  if (!form.name.trim()) { message.warning('请填写名称'); return }
  if (!form.ontology_id || form.ontology_id < 1) { message.warning('请填写有效本体 ID'); return }
  if (!form.ontology_version || form.ontology_version < 1) { message.warning('本体版本需 ≥ 1'); return }
  creating.value = true
  try {
    const card = await api.createCard({
      name: form.name.trim(),
      ontology_id: form.ontology_id,
      ontology_version: form.ontology_version,
      scene_key: form.scene_key.trim() || undefined,
    })
    message.success('卡片已创建')
    formOpen.value = false
    await store.loadCards()
    await store.openCard(card.id)
  } finally { creating.value = false }
}
</script>
<style scoped>
.card-list { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.cl-head { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid var(--border); flex: none; }
.cl-title { font-size: 12px; font-weight: 600; color: var(--fg-secondary); }
.cl-add { font-size: 12px; color: var(--accent); background: transparent; border: 1px solid var(--border-strong); border-radius: 6px; padding: 2px 8px; cursor: pointer; }
.cl-scroll { flex: 1; overflow: auto; padding: 8px; }
.cl-group { margin-bottom: 12px; }
.cl-glabel { font-size: 11px; color: var(--fg-muted); margin-bottom: 4px; }
.cl-gcount { color: var(--fg-secondary); }
.cl-card { display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-surface); margin-bottom: 4px; cursor: pointer; font-size: 12px; color: var(--fg); }
.cl-card.on { border-color: var(--accent); background: var(--accent-soft); }
.cl-card.restricted { opacity: .7; }
.cl-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cl-badge { font-size: 10px; padding: 1px 6px; border-radius: 6px; }
.cl-badge.draft { color: var(--fg-muted); background: var(--bg-subtle); }
.cl-badge.live { color: var(--ok); background: var(--ok-soft); }
.cl-badge.paused { color: var(--warn); background: var(--warn-soft); }
.cl-days { font-size: 10px; color: var(--fg-muted); }
.cl-lock { font-size: 12px; }
</style>
