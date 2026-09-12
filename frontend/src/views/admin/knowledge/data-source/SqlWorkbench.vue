<template>
  <div class="sql-wb">
    <a-alert type="warning" banner style="margin-bottom: 10px">
      <template #message>只读区与写区物理隔离：写语句粘贴到只读框将被后端拒绝；写操作需「申请 → 审批 → 令牌执行」。</template>
    </a-alert>
    <a-tabs v-model:activeKey="tab">
      <!-- 只读查询 -->
      <a-tab-pane key="ro" tab="只读查询">
        <div class="sql-wb__bar">
          <a-select v-model:value="sourceId" placeholder="数据源" style="width: 220px">
            <a-select-option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</a-select-option>
          </a-select>
          <a-button type="primary" :disabled="!sourceId" @click="run"><PlayCircleOutlined /> 执行</a-button>
        </div>
        <a-textarea v-model:value="roSql" :rows="5" placeholder="SELECT ... （只读）" />
        <JsonViewer v-if="roResult" :value="roResult" :copyable="false" />
      </a-tab-pane>

      <!-- 写操作 -->
      <a-tab-pane key="wr" tab="写操作">
        <a-textarea v-model:value="wrSql" :rows="4" placeholder="INSERT / UPDATE / DELETE / DDL" />
        <div class="sql-wb__bar">
          <a-button @click="dryRun"><BugOutlined /> Dry-run 影响预估</a-button>
          <a-button type="primary" :disabled="!sourceId" @click="submitReq"><SendOutlined /> 提交申请</a-button>
        </div>
        <a-card v-if="impact" size="small" title="影响预估" style="margin-bottom: 12px">
          <JsonViewer :value="impact" />
        </a-card>

        <h4>我的申请</h4>
        <a-table :columns="reqCols" :data-source="requests" size="small" :pagination="false">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'action'">
              <a-button v-if="record.status === 'approved'" size="small" @click="exec(record)">执行（令牌）</a-button>
              <a-tag v-else>{{ record.status }}</a-tag>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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

const reqCols = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
  { title: 'SQL 预览', dataIndex: 'sql_preview', key: 'sql_preview' },
  { title: t('knowledge.common.actions'), key: 'action', width: 140 },
]

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
    message.error(e?.response?.data?.detail || '查询失败')
  }
}
async function dryRun() {
  impact.value = { note: 'Dry-run 影响预估由后端 write-request 创建时返回 impact_json；此处展示占位。' }
}
async function submitReq() {
  if (!sourceId.value) return
  try {
    await api.createWriteRequest({ source_id: sourceId.value, sql_text: wrSql.value })
    message.success('已提交写申请')
    loadRequests()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '提交失败')
  }
}
async function loadRequests() {
  const r: any = await api.listWriteRequests(sourceId.value)
  requests.value = r.data || r || []
}
async function exec(row: any) {
  const token = await new Promise<string>((resolve) => {
    const input = window.prompt('输入一次性执行令牌')
    resolve(input || '')
  })
  if (!token) return
  try {
    await api.executeWriteRequest(row.id, token)
    message.success('执行成功')
    loadRequests()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '执行失败（令牌无效或已过期）')
  }
}
onMounted(loadSources)
</script>

<style scoped>
.sql-wb__bar { display: flex; gap: 8px; margin: 8px 0; }
</style>
