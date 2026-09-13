<template>
  <div class="sql-wb">
    <a-alert type="warning" banner style="margin-bottom: 10px">
      <template #message>{{ t('kbMgmt.sql.isolationNotice') }}</template>
    </a-alert>
    <a-tabs v-model:activeKey="tab">
      <!-- 只读查询 -->
      <a-tab-pane key="ro" :tab="t('kbMgmt.sql.roTab')">
        <div class="sql-wb__bar">
          <a-select v-model:value="sourceId" :placeholder="t('kbMgmt.sql.source')" style="width: 220px">
            <a-select-option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</a-select-option>
          </a-select>
          <a-button type="primary" :disabled="!sourceId" @click="run"><PlayCircleOutlined /> {{ t('kbMgmt.sql.execute') }}</a-button>
        </div>
        <a-textarea v-model:value="roSql" :rows="5" :placeholder="t('kbMgmt.sql.roPlaceholder')" />
        <JsonViewer v-if="roResult" :value="roResult" :copyable="false" />
      </a-tab-pane>

      <!-- 写操作 -->
      <a-tab-pane key="wr" :tab="t('kbMgmt.sql.woTab')">
        <a-textarea v-model:value="wrSql" :rows="4" placeholder="INSERT / UPDATE / DELETE / DDL" />
        <div class="sql-wb__bar">
          <a-button @click="dryRun"><BugOutlined /> {{ t('kbMgmt.sql.dryRun') }}</a-button>
          <a-button type="primary" :disabled="!sourceId" @click="submitReq"><SendOutlined /> {{ t('kbMgmt.sql.submitReq') }}</a-button>
        </div>
        <a-card v-if="impact" size="small" :title="t('kbMgmt.sql.impactTitle')" style="margin-bottom: 12px">
          <JsonViewer :value="impact" />
        </a-card>

        <h4>{{ t('kbMgmt.sql.myRequests') }}</h4>
        <a-table :columns="reqCols" :data-source="requests" size="small" :pagination="false">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'action'">
              <a-button v-if="record.status === 'approved'" size="small" @click="exec(record)">{{ t('kbMgmt.sql.execToken') }}</a-button>
              <a-tag v-else>{{ record.status }}</a-tag>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined, BugOutlined, SendOutlined } from '@ant-design/icons-vue'
import JsonViewer from '@/components/common/JsonViewer.vue'
import * as api from '@/api/dataops'

const { t } = useI18n()
const sources = ref<any[]>([])
const sourceId = ref<number>()
const tab = ref('ro')
const roSql = ref('')
const roResult = ref<any>(null)
const wrSql = ref('')
const impact = ref<any>(null)
const requests = ref<any[]>([])

const reqCols = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: t('kbMgmt.common.status'), dataIndex: 'status', key: 'status', width: 110 },
  { title: t('kbMgmt.sql.sqlPreview'), dataIndex: 'sql_preview', key: 'sql_preview' },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 140 },
])

async function loadSources() {
  const r: any = await api.listSources()
  sources.value = r.data || r || []
}
async function run() {
  if (!sourceId.value) return
  try {
    const r: any = await api.runQuery(sourceId.value, roSql.value, 200)
    roResult.value = r.data || r
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.sql.queryFailed'))
  }
}
async function dryRun() {
  impact.value = { note: t('kbMgmt.sql.dryRunNote') }
}
async function submitReq() {
  if (!sourceId.value) return
  try {
    await api.createWriteRequest({ source_id: sourceId.value, sql_text: wrSql.value })
    message.success(t('kbMgmt.sql.reqSubmitted'))
    loadRequests()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.sql.submitFailed'))
  }
}
async function loadRequests() {
  const r: any = await api.listWriteRequests(sourceId.value)
  requests.value = r.data || r || []
}
async function exec(row: any) {
  const token = await new Promise<string>((resolve) => {
    const input = window.prompt(t('kbMgmt.sql.tokenPrompt'))
    resolve(input || '')
  })
  if (!token) return
  try {
    await api.executeWriteRequest(row.id, token)
    message.success(t('kbMgmt.sql.execOk'))
    loadRequests()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.sql.execFailed'))
  }
}
onMounted(loadSources)
</script>

<style scoped>
.sql-wb__bar { display: flex; gap: 8px; margin: 8px 0; }
</style>
