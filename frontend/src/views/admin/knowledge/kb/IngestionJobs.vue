<template>
  <div class="kb-ing">
    <div class="kb-ing__toolbar">
      <a-select v-model:value="kbId" placeholder="选择数据集" style="width: 240px" @change="refresh">
        <a-select-option v-for="d in datasets" :key="d.kb_id" :value="d.kb_id">{{ d.name }}</a-select-option>
      </a-select>
      <a-button @click="refresh"><ReloadOutlined /> 刷新</a-button>
    </div>

    <a-row :gutter="12" class="kb-ing__stats">
      <a-col v-for="s in stats" :key="s.key" :span="6">
        <a-card size="small">
          <div class="kb-ing__stat-num" :style="{ color: s.color }">{{ s.count }}</div>
          <div class="kb-ing__stat-label">{{ s.label }}</div>
        </a-card>
      </a-col>
    </a-row>

    <a-empty v-if="!docs.length" :description="t('knowledge.common.empty')" />
    <a-table v-else :columns="columns" :data-source="docs" size="small" :pagination="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'ready' ? 'success' : record.status === 'error' ? 'error' : 'processing'">{{ record.status }}</a-tag>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ReloadOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/knowledgeBase'

const { t } = useI18n()
const datasets = ref<any[]>([])
const kbId = ref<string>()
const docs = ref<any[]>([])

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: t('knowledge.common.status'), key: 'status', width: 110 },
  { title: '切片数', dataIndex: 'chunk_count', key: 'chunk_count', width: 90 },
]

const stats = computed(() => {
  const c: Record<string, number> = { pending: 0, processing: 0, ready: 0, error: 0 }
  docs.value.forEach((d) => { c[d.status] = (c[d.status] || 0) + 1 })
  return [
    { key: 'pending', label: 'pending', count: c.pending, color: 'var(--fg-muted)' },
    { key: 'processing', label: 'processing', count: c.processing, color: 'var(--accent)' },
    { key: 'ready', label: 'ready', count: c.ready, color: '#52c41a' },
    { key: 'error', label: 'error', count: c.error, color: '#ff4d4f' },
  ]
})

async function loadDatasets() {
  const r: any = await api.listDatasets()
  datasets.value = r.data || r || []
}
async function refresh() {
  if (!kbId.value) return
  const r: any = await api.listDocuments(kbId.value)
  docs.value = r.data || r || []
}
onMounted(loadDatasets)
</script>

<style scoped>
.kb-ing__toolbar { margin-bottom: 12px; display: flex; gap: 8px; }
.kb-ing__stats { margin-bottom: 12px; }
.kb-ing__stat-num { font-size: 22px; font-weight: 700; }
.kb-ing__stat-label { color: var(--fg-muted); font-size: 12px; }
</style>
