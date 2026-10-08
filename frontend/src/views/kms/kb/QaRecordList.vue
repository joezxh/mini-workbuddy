<template>
  <a-card :title="t('kbMgmt.qaRecords')" size="small">
    <a-space class="qrl__bar" wrap>
      <a-upload :before-upload="handleFile" :show-upload-list="false" accept=".csv,.xlsx,.xls">
        <a-button :loading="importing">{{ t('kbMgmt.qaBatchImport') }}</a-button>
      </a-upload>
      <a-button @click="handleExport">{{ t('kbMgmt.qaExport') }}</a-button>
      <a-button :loading="loading" @click="load">{{ t('common.refresh') }}</a-button>
    </a-space>
    <a-alert class="qrl__hint" type="info" :message="t('kbMgmt.qaFileHint')" show-icon />

    <a-table
      size="small"
      :data-source="rows"
      :columns="columns"
      :pagination="{ pageSize: 10, size: 'small' }"
      :loading="loading"
      row-key="document_id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tags'">
          <a-tag v-for="tg in record.tags" :key="tg">{{ tg }}</a-tag>
        </template>
        <template v-else-if="column.key === 'enabled'">
          <a-switch
            size="small"
            :checked="record.enabled !== false"
            :loading="record.__busy"
            @change="(v: boolean) => toggle(record, v)"
          />
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { exportQaRecords, importQaFile, listQaRecords, updateSegment } from '@/api/kb'

const props = defineProps<{ collection: string }>()
const { t } = useI18n()

interface QaRow {
  segment_id?: number
  document_id: string
  chunk_index: number
  question: string
  answer: string | null
  tags: string[]
  enabled: boolean
  __busy?: boolean
}

const loading = ref(false)
const importing = ref(false)
const rows = ref<QaRow[]>([])

const columns = [
  { title: t('kbMgmt.question'), dataIndex: 'question', key: 'question' },
  { title: t('kbMgmt.answer'), dataIndex: 'answer', key: 'answer' },
  { title: t('kbMgmt.tags'), key: 'tags', width: 160 },
  { title: t('kbMgmt.enabled'), key: 'enabled', width: 90 },
]

async function load() {
  loading.value = true
  try {
    const res: any = await listQaRecords(props.collection)
    rows.value = (res.records || res.items || res || []).map((r: any) => ({ ...r, __busy: false }))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function handleFile(file: File) {
  importing.value = true
  try {
    const res: any = await importQaFile(props.collection, file)
    message.success(`${t('kbMgmt.qaBatchImport')} ✓ ${res.imported ?? 0}`)
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.importFailed'))
  } finally {
    importing.value = false
  }
  return false
}

async function handleExport() {
  try {
    const res: any = await exportQaRecords(props.collection)
    const url = URL.createObjectURL(new Blob([res.data ?? res]))
    const a = document.createElement('a')
    a.href = url
    a.download = `qa-${props.collection}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.exportFailed'))
  }
}

/** 启停（D15）：enabled 存于 segment metadata，检索按 metadata_filter 过滤 */
async function toggle(row: QaRow, enabled: boolean) {
  if (row.segment_id == null) {
    message.warning(t('kbMgmt.qaToggleUnsupported'))
    return
  }
  row.__busy = true
  try {
    await updateSegment(row.segment_id, { metadata: { chunk_type: 'qa', enabled } })
    row.enabled = enabled
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.saveFailed'))
  } finally {
    row.__busy = false
  }
}

onMounted(load)
watch(() => props.collection, load)
</script>

<style scoped>
.qrl__bar {
  margin-bottom: 12px;
}
.qrl__hint {
  margin-bottom: 12px;
}
</style>
