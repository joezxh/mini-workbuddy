<template>
  <div class="binding-wb">
    <div class="binding-wb__filters">
      <a-select v-model:value="sourceId" :placeholder="t('kbMgmt.meta.selectSource')" style="width: 220px" @change="reset">
        <a-select-option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</a-select-option>
      </a-select>
      <a-select v-model:value="database" :placeholder="t('kbMgmt.meta.selectDatabase')" style="width: 200px">
        <a-select-option v-for="d in databases" :key="d" :value="d">{{ d }}</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!sourceId" @click="doBind"><LinkOutlined /> {{ t('kbMgmt.bind.run') }}</a-button>
      <a-button :disabled="!sourceId" @click="infer"><ApartmentOutlined /> {{ t('kbMgmt.bind.infer') }}</a-button>
    </div>

    <a-alert v-if="report" type="info" show-icon style="margin-bottom: 12px">
      <template #message>
        {{ t('kbMgmt.bind.report', { tables: report.tables, columns: report.columns, annotated: report.annotated, bound: report.bound, updated: report.updated, skipped: report.skipped_human }) }}
      </template>
    </a-alert>

    <div class="binding-wb__cols">
      <div class="binding-wb__col">
        <h4>{{ t('kbMgmt.bind.pendingCols') }}</h4>
        <a-empty v-if="!pending.length" :description="t('kbMgmt.common.empty')" />
        <a-list size="small" :data-source="pending" :locale="{ emptyText: t('kbMgmt.common.empty') }">
          <template #renderItem="{ item }">
            <a-list-item>
              <span>{{ item.column }}</span>
              <a-tag v-if="item.semantic_type" color="blue">{{ item.semantic_type }}</a-tag>
              <a-tag v-if="item.pii_level" color="red">{{ item.pii_level }}</a-tag>
            </a-list-item>
          </template>
        </a-list>
      </div>
      <div class="binding-wb__col">
        <h4>{{ t('kbMgmt.bind.standardItems') }}</h4>
        <a-list size="small" :data-source="standards" :locale="{ emptyText: t('kbMgmt.common.empty') }">
          <template #renderItem="{ item }">
            <a-list-item>
              <span>{{ item.name }}</span>
              <a-tag>{{ item.semantic_type || '—' }}</a-tag>
            </a-list-item>
          </template>
        </a-list>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { LinkOutlined, ApartmentOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/dataops'

const { t } = useI18n()
const sources = ref<any[]>([])
const sourceId = ref<number>()
const databases = ref<string[]>([])
const database = ref<string>()
const report = ref<any>(null)
const pending = ref<any[]>([])
const standards = ref<any[]>([])

async function loadSources() {
  const r: any = await api.listSources()
  sources.value = r.data || r || []
}
async function reset() {
  report.value = null
  pending.value = []
}
async function doBind() {
  if (!sourceId.value) return
  try {
    const r: any = await api.bindSource(sourceId.value, database.value)
    report.value = r.data || r
    message.success(t('kbMgmt.bind.done'))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.bind.failed'))
  }
}
async function infer() {
  if (!sourceId.value) return
  try {
    await api.inferRelations(sourceId.value, database.value, true)
    message.success(t('kbMgmt.bind.inferDone'))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.bind.inferFailed'))
  }
}
onMounted(async () => {
  await loadSources()
  const r: any = await api.listStandards()
  standards.value = r.data || r || []
})
</script>

<style scoped>
.binding-wb { display: flex; flex-direction: column; gap: 12px; }
.binding-wb__filters { display: flex; gap: 10px; flex-wrap: wrap; }
.binding-wb__cols { display: flex; gap: 16px; }
.binding-wb__col { flex: 1; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px; }
</style>
