<!-- Source 配置页（Task 8.5 / 6.6 API）—— GitHub + Feishu Source 配置管理 -->
<template>
  <div class="sa-src">
    <div class="sa-src__intro">🐙 GitHub / 💬 飞书触发源 · Thread / Subscription / Mandate 预览</div>

    <a-spin :spinning="loading">
      <div class="sa-src__grid">
        <a-card v-for="s in sources" :key="s.kind" size="small" class="mb12">
          <template #title>
            <span class="sa-src__badge">{{ s.kind === 'github' ? '🐙' : '💬' }} {{ s.kind }}</span>
            <a-tag :color="s.configured ? 'green' : 'default'" style="margin-left: 8px">
              {{ s.configured ? '已配置' : '未配置' }}
            </a-tag>
          </template>

          <!-- GitHub 配置 -->
          <a-form v-if="s.kind === 'github'" layout="vertical" style="max-width: 520px">
            <a-form-item label="仓库（owner/name）">
              <a-input v-model:value="ghCfg.repository" placeholder="my-org/my-repo" />
            </a-form-item>
            <a-form-item label="gh CLI 路径">
              <a-input v-model:value="ghCfg.gh_cli" />
            </a-form-item>
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="轮询间隔（秒，≥60）">
                  <a-input-number v-model:value="ghCfg.poll_seconds" :min="60" :max="3600" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="失败阈值">
                  <a-input-number v-model:value="ghCfg.failures_before_error" :min="1" :max="20" style="width: 100%" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="观察范围">
              <a-space wrap>
                <a-checkbox v-model:checked="ghCfg.observe_issues">Issues</a-checkbox>
                <a-checkbox v-model:checked="ghCfg.observe_pulls">Pulls</a-checkbox>
                <a-checkbox v-model:checked="ghCfg.observe_comments">Comments</a-checkbox>
                <a-checkbox v-model:checked="ghCfg.observe_ci">CI</a-checkbox>
              </a-space>
            </a-form-item>
            <a-form-item label="CI 分支">
              <a-input v-model:value="ghCfg.ci_branch" style="max-width: 200px" />
            </a-form-item>
            <a-button type="primary" :loading="saving === 'github'" @click="save('github', ghCfg)">保存 GitHub 配置</a-button>
          </a-form>

          <!-- Feishu 配置 -->
          <a-form v-else layout="vertical" style="max-width: 520px">
            <a-form-item label="lark-cli 路径">
              <a-input v-model:value="fsCfg.lark_cli" />
            </a-form-item>
            <a-form-item label="监听群组">
              <div v-for="(c, i) in fsCfg.chats" :key="i" style="display: flex; gap: 8px; margin-bottom: 8px">
                <a-input v-model:value="c.chat_id" placeholder="oc_xxx" style="flex: 1" />
                <a-input v-model:value="c.name" placeholder="群名" style="width: 140px" />
                <a-select v-model:value="c.listen" style="width: 120px">
                  <a-select-option value="mentions">仅@我</a-select-option>
                  <a-select-option value="all">全部消息</a-select-option>
                </a-select>
                <a-button danger @click="fsCfg.chats.splice(i, 1)">删</a-button>
              </div>
              <a-button size="small" @click="fsCfg.chats.push({ chat_id: '', name: '', listen: 'mentions' })">+ 添加群组</a-button>
            </a-form-item>
            <a-form-item label="私聊消息">
              <a-switch v-model:checked="fsCfg.direct_messages" />
            </a-form-item>
            <a-form-item label="其他群">
              <a-radio-group v-model:value="fsCfg.other_chats">
                <a-radio value="none">不监听</a-radio>
                <a-radio value="mentions">仅@我</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-button type="primary" :loading="saving === 'feishu'" @click="save('feishu', fsCfg)">保存 Feishu 配置</a-button>
          </a-form>
        </a-card>
      </div>
    </a-spin>

    <!-- Thread / Subscription / Mandate 预览（TR-8.6）—— GET /threads + GET /tickets/{id}/subscriptions -->
    <a-card title="Thread / Subscription / Mandate 预览" size="small" class="mb12">
      <a-tabs>
        <a-tab-pane key="threads" tab="Thread 列表">
          <a-table :data-source="threads" :columns="threadCols" size="small" row-key="id"
                   :loading="previewLoading" :pagination="{ pageSize: 8 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a :href="record.url" target="_blank" rel="noopener">{{ record.title || record.id }}</a>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'closed' ? 'default' : 'green'">{{ record.status }}</a-tag>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="subs" tab="Subscription 列表">
          <a-table :data-source="subs" :columns="subCols" size="small" row-key="id"
                   :loading="previewLoading" :pagination="{ pageSize: 8 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'thread'">
                {{ record.thread?.title || record.thread_id }}
              </template>
              <template v-else-if="column.key === 'kind'">
                <a-tag :color="record.kind === 'following' ? 'blue' : 'default'">{{ record.kind }}</a-tag>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="mandates" tab="Mandate 列表">
          <a-table :data-source="mandates" :columns="mandateCols" size="small" row-key="ticket_id"
                   :loading="previewLoading" :pagination="{ pageSize: 8 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'strength'">
                <a-tag :color="record.strength === 'explicit' ? 'green' : 'blue'">{{ record.strength }}</a-tag>
              </template>
              <template v-else-if="column.key === 'rules'">
                <a-tag v-for="(r, i) in record.matched_rules" :key="i" style="margin-right: 4px">
                  {{ r.rule_id || r }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { listSources, getSourceConfig, updateSourceConfig, listThreads, listTickets, getTicket, listTicketSubscriptions } from '@/api/super-agent'

const loading = ref(false)
const saving = ref('')
const sources = ref<any[]>([])

// ===== Thread / Subscription / Mandate 预览（TR-8.6）=====
const WORKSPACE_ID = 1
const previewLoading = ref(false)
const threads = ref<any[]>([])
const subs = ref<any[]>([])
const mandates = ref<any[]>([])
const threadCols = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 200, ellipsis: true },
  { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '来源', dataIndex: 'source', key: 'source', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180 },
]
const subCols = [
  { title: 'Ticket', dataIndex: 'ticket_id', key: 'ticket_id', width: 200, ellipsis: true },
  { title: 'Thread', key: 'thread', ellipsis: true },
  { title: '类型', dataIndex: 'kind', key: 'kind', width: 120 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
]
const mandateCols = [
  { title: 'Ticket', dataIndex: 'ticket_id', key: 'ticket_id', width: 200, ellipsis: true },
  { title: 'Policy 版本', dataIndex: 'policy_version', key: 'policy_version', width: 160, ellipsis: true },
  { title: 'Strength', dataIndex: 'strength', key: 'strength', width: 100 },
  { title: '规则', key: 'rules' },
]

async function loadPreviews() {
  previewLoading.value = true
  try {
    threads.value = (await listThreads(WORKSPACE_ID)) as any[] || []
    const tickets = (await listTickets(WORKSPACE_ID)) as any[] || []
    const ticketIds = tickets.slice(0, 10).map((t: any) => t.id)
    // Subscription 预览 —— GET /tickets/{id}/subscriptions（近 10 个 Ticket）
    const subResults = await Promise.allSettled(ticketIds.map(id => listTicketSubscriptions(id)))
    subs.value = subResults.flatMap(r => (r.status === 'fulfilled' ? (r.value as any[]) : []))
    // Mandate 预览 —— TicketDetail.mandate
    const detailResults = await Promise.allSettled(ticketIds.map(id => getTicket(id)))
    mandates.value = detailResults.flatMap(r => {
      if (r.status !== 'fulfilled') return []
      const t: any = r.value
      return t?.mandate ? [{ ticket_id: t.id, ...t.mandate }] : []
    })
  } catch {
    /* request 拦截器已提示 */
  } finally {
    previewLoading.value = false
  }
}

const ghCfg = reactive({
  repository: '', gh_cli: 'gh', poll_seconds: 60, failures_before_error: 3,
  observe_issues: false, observe_pulls: false, observe_comments: false, observe_ci: false,
  ci_branch: 'main',
})
const fsCfg = reactive<{ lark_cli: string; chats: { chat_id: string; name: string; listen: 'mentions' | 'all' }[]; direct_messages: boolean; other_chats: 'none' | 'mentions' }>({
  lark_cli: 'lark-cli', chats: [], direct_messages: true, other_chats: 'none',
})

onMounted(async () => {
  loading.value = true
  try {
    sources.value = await listSources() as any || []
    for (const s of sources.value) {
      const cfg = await getSourceConfig(s.kind) as any
      const value = cfg?.current || {}
      if (s.kind === 'github') Object.assign(ghCfg, value)
      else if (s.kind === 'feishu') Object.assign(fsCfg, value)
    }
  } catch {
    /* request 拦截器已提示 */
  } finally {
    loading.value = false
  }
  void loadPreviews()
})

async function save(kind: string, value: any) {
  saving.value = kind
  try {
    await updateSourceConfig(kind, value)
    message.success(`${kind} 配置已保存`)
  } catch {
    /* request 拦截器已提示 */
  } finally {
    saving.value = ''
  }
}
</script>

<style scoped lang="less">
.sa-src {
  &__intro {
    font-size: 13px;
    color: var(--sa-text-3);
    margin-bottom: 14px;
  }

  &__grid {
    display: grid;
    grid-template-columns: 1fr;
  }

  &__badge {
    font-size: 14px;
    font-weight: 600;
  }
}

.mb12 {
  margin-bottom: 12px;
}
</style>
