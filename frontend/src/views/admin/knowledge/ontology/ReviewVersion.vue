<template>
  <div class="onto-review">
    <div class="onto-review__bar">
      <a-select v-model:value="ontoId" placeholder="选择本体" style="width: 240px" @change="refresh">
        <a-select-option v-for="o in ontos" :key="o.id" :value="o.id">{{ o.name }}</a-select-option>
      </a-select>
      <a-button @click="refresh"><ReloadOutlined /> {{ t('knowledge.common.refresh') }}</a-button>
    </div>

    <a-divider>待评审项（status=suggested）</a-divider>
    <a-table :columns="reviewCols" :data-source="reviews" size="small" :pagination="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-button size="small" type="primary" @click="decide(record, 'accepted')">接受</a-button>
          <a-button size="small" danger @click="decide(record, 'rejected')">拒绝</a-button>
        </template>
        <template v-else-if="column.key === 'evidence'">
          <JsonViewer :value="record.evidence_json" :copyable="false" :compact="true" />
        </template>
      </template>
    </a-table>

    <a-divider>版本历史（快照对比）</a-divider>
    <div class="onto-review__versions">
      <a-select v-model:value="leftV" placeholder="左版本" style="width: 200px" @change="diff">
        <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.label }}</a-select-option>
      </a-select>
      <a-select v-model:value="rightV" placeholder="右版本" style="width: 200px" @change="diff">
        <a-select-option v-for="v in versions" :key="v.id" :value="v.id">{{ v.label }}</a-select-option>
      </a-select>
    </div>
    <DiffView v-if="leftV && rightV" :left="leftSnap" :right="rightSnap" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import JsonViewer from '@/components/common/JsonViewer.vue'
import DiffView from '@/components/common/DiffView.vue'
import * as api from '@/api/ontology'

const { t } = useI18n()
const ontos = ref<any[]>([])
const ontoId = ref<number>()
const reviews = ref<any[]>([])
const versions = ref<any[]>([])
const leftV = ref<number>()
const rightV = ref<number>()
const leftSnap = ref<any>(null)
const rightSnap = ref<any>(null)

const reviewCols = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: t('knowledge.common.name'), dataIndex: 'name', key: 'name' },
  { title: '置信度', dataIndex: 'confidence', key: 'confidence', width: 90 },
  { title: '证据', key: 'evidence' },
  { title: t('knowledge.common.actions'), key: 'action', width: 150 },
]

async function loadOntos() {
  try {
    const r: any = await api.listOntologies()
    ontos.value = r.data || r || []
  } catch { /* ignore */ }
}
async function refresh() {
  if (!ontoId.value) return
  try {
    const [rv, vs] = await Promise.all([
      api.listReviewItems(ontoId.value),
      api.listVersions(ontoId.value),
    ])
    reviews.value = rv.data || rv || []
    versions.value = (vs.data || vs || []).map((v: any) => ({ id: v.id, label: v.label || `v${v.id}`, snap: v.snapshot }))
  } catch {
    message.warning('评审/版本需后端 router')
  }
}
async function decide(row: any, decision: 'accepted' | 'rejected') {
  if (!ontoId.value) return
  try {
    await api.reviewItem(ontoId.value, row.id, decision)
    message.success(decision === 'accepted' ? '已接受' : '已拒绝')
    refresh()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '评审失败（需后端 router）')
  }
}
function diff() {
  leftSnap.value = versions.value.find((v) => v.id === leftV.value)?.snap || null
  rightSnap.value = versions.value.find((v) => v.id === rightV.value)?.snap || null
}
onMounted(loadOntos)
</script>

<style scoped>
.onto-review__bar { display: flex; gap: 8px; margin-bottom: 8px; }
.onto-review__versions { display: flex; gap: 12px; margin: 12px 0; }
</style>
