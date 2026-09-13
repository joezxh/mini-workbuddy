<template>
  <a-drawer
    v-model:open="visible"
    :title="t('agentMgmt.detailTitle', { name: agentData?.name || '' })"
    placement="right"
    :width="640"
    :body-style="{ padding: '16px' }"
  >
    <a-spin :spinning="loading">
      <template v-if="agentData">
        <!-- 基本信息 -->
        <a-card size="small" :title="t('agentMgmt.basicInfo')" class="detail-card">
          <a-descriptions :column="2" size="small">
            <a-descriptions-item label="ID">{{ agentData.id }}</a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.labelCode')">
              <code>{{ agentData.agent_code }}</code>
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.colName')">{{ agentData.name }}</a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.labelType')">
              <a-tag :color="typeColor(agentData.agent_type)">
                {{ typeLabel(agentData.agent_type) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item :label="t('skillHub.status')">
              <a-tag :color="agentData.is_active ? 'green' : 'default'">
                {{ agentData.is_active ? t('agentMgmt.enabledMsg') : t('agentMgmt.disabledMsg') }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.colSort')">{{ agentData.sort_order }}</a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.createdAt')" :span="2">
              {{ formatDate(agentData.created_at) }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('skillHub.description')" :span="2">
              {{ agentData.description || t('agentMgmt.noDescription') }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 可视化配置 -->
        <a-card size="small" :title="t('agentMgmt.visConfig')" class="detail-card">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item :label="t('agentMgmt.systemPrompt')">
              <pre class="config-json">{{ agentData.system_prompt || t('agentMgmt.notConfigured') }}</pre>
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.labelModel')">
              {{ agentData.model_config?.provider || '-' }} / {{ agentData.model_config?.model || '-' }}
              <span v-if="agentData.model_config?.temperature !== undefined">
                · temp {{ agentData.model_config.temperature }}
              </span>
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.executionMode')">
              {{ agentData.execution_mode || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.bindTools')">
              <a-tag v-for="t in (agentData.tools || [])" :key="t" color="blue">{{ t }}</a-tag>
              <span v-if="!(agentData.tools || []).length">{{ t('agentMgmt.none') }}</span>
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.bindSkills')">
              <a-tag v-for="s in (agentData.skills || [])" :key="s" color="green">{{ s }}</a-tag>
              <span v-if="!(agentData.skills || []).length">{{ t('agentMgmt.none') }}</span>
            </a-descriptions-item>
            <a-descriptions-item :label="t('agentMgmt.labelMcpServices')">
              <a-tag v-for="m in (agentData.mcp_servers || [])" :key="m.name || JSON.stringify(m)" color="orange">
                {{ m.name || m }}
              </a-tag>
              <span v-if="!(agentData.mcp_servers || []).length">{{ t('agentMgmt.none') }}</span>
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 类型配置 -->
        <a-card size="small" :title="t('agentMgmt.rawConfig')" class="detail-card">
          <pre class="config-json">{{ formatConfig(agentData.config) }}</pre>
        </a-card>

        <!-- 监控统计 -->
        <a-card size="small" :title="t('agentMgmt.runStats')" class="detail-card">
          <a-row :gutter="16">
            <a-col :span="8">
              <div class="metric">
                <div class="metric-label">{{ t('agentMgmt.colInvocationCount') }}</div>
                <div class="metric-value">{{ metrics.invocation_count || 0 }}</div>
              </div>
            </a-col>
            <a-col :span="8">
              <div class="metric">
                <div class="metric-label">{{ t('agentMgmt.successRate') }}</div>
                <div class="metric-value">{{ metrics.success_rate || '0' }}%</div>
              </div>
            </a-col>
            <a-col :span="8">
              <div class="metric">
                <div class="metric-label">{{ t('agentMgmt.avgDuration') }}</div>
                <div class="metric-value">{{ metrics.avg_duration || 0 }}ms</div>
              </div>
            </a-col>
          </a-row>
        </a-card>

        <!-- 最近链路 -->
        <a-card size="small" :title="t('agentMgmt.recentTraces')" class="detail-card">
          <template #extra>
            <a-button size="small" type="link" @click="loadTraces">
              <ReloadOutlined :spin="loadingTraces" />
            </a-button>
          </template>
          <a-empty v-if="recentTraces.length === 0" :description="t('agentMgmt.noTraces')" :image-size="60" />
          <a-list v-else size="small" :data-source="recentTraces">
            <template #renderItem="{ item }">
              <a-list-item class="trace-item">
                <a-list-item-meta>
                  <template #title>
                    <a-space>
                      <a-tag :color="item.status === 'ERROR' ? 'red' : 'green'">
                        {{ item.status }}
                      </a-tag>
                      <span class="trace-id">{{ truncateId(item.trace_id) }}</span>
                    </a-space>
                  </template>
                  <template #description>
                    <span class="trace-meta">
                      {{ item.agent_id }} · {{ item.duration_ms }}ms · {{ formatDate(item.start_time) }}
                    </span>
                  </template>
                </a-list-item-meta>
                <template #actions>
                  <a @click="openTrace(item.trace_id)">{{ t('agentMgmt.view') }}</a>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </template>
    </a-spin>
  </a-drawer>

  <!-- 链路追踪抽屉 -->
  <AgentTraceDrawer
    v-model:visible="traceDrawerVisible"
    :trace-id="viewingTraceId"
    :agent-id="agentData?.agent_code"
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getAgentDetail, type AgentConfig } from '@/api/agentConfig'
import { getTraceList } from '@/api/agent'
import AgentTraceDrawer from '@/views/assistant/components/AgentTraceDrawer.vue'

const props = defineProps<{
  agentId?: number
}>()

const visible = defineModel<boolean>('visible', { default: false })
const { t } = useI18n()

const loading = ref(false)
const agentData = ref<AgentConfig | null>(null)
const metrics = ref<any>({})
const recentTraces = ref<any[]>([])
const loadingTraces = ref(false)

const traceDrawerVisible = ref(false)
const viewingTraceId = ref<string>('')

watch(() => props.agentId, (val) => {
  if (val && visible.value) {
    loadAgent()
  }
})

watch(visible, (val) => {
  if (val && props.agentId) {
    loadAgent()
  }
})

async function loadAgent() {
  if (!props.agentId) return
  loading.value = true
  try {
    agentData.value = await getAgentDetail(props.agentId)
    await loadTraces()
  } catch (e: any) {
    message.error(t('agentMgmt.loadDetailFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  } finally {
    loading.value = false
  }
}

async function loadTraces() {
  if (!agentData.value) return
  loadingTraces.value = true
  try {
    const res = await getTraceList({
      agent_id: agentData.value.agent_code,
      limit: 10,
    }) as any
    recentTraces.value = res.traces || []

    // 简单的指标计算
    const total = recentTraces.value.length
    const success = recentTraces.value.filter((t: any) => t.status !== 'ERROR').length
    const avgDuration = total > 0
      ? Math.round(recentTraces.value.reduce((sum: number, t: any) => sum + (t.duration_ms || 0), 0) / total)
      : 0

    metrics.value = {
      invocation_count: total,
      success_rate: total > 0 ? ((success / total) * 100).toFixed(1) : '0',
      avg_duration: avgDuration,
    }
  } catch (e) {
    recentTraces.value = []
  } finally {
    loadingTraces.value = false
  }
}

function openTrace(traceId: string) {
  viewingTraceId.value = traceId
  traceDrawerVisible.value = true
}

function typeLabel(type: string) {
  return ({
    CHAT: t('agentMgmt.typeChat'),
    WORKFLOW: t('agentMgmt.typeWorkflow'),
    SKILL: t('agentMgmt.typeSkill'),
  } as Record<string, string>)[type] ?? type
}

function typeColor(type: string) {
  return ({
    CHAT: 'blue',
    WORKFLOW: 'purple',
    SKILL: 'green',
  } as Record<string, string>)[type] ?? 'default'
}

function formatConfig(config: any): string {
  if (!config) return '{}'
  return JSON.stringify(config, null, 2)
}

function formatDate(d?: string): string {
  if (!d) return '-'
  try {
    return new Date(d).toLocaleString('zh-CN')
  } catch {
    return d
  }
}

function truncateId(id: string): string {
  if (!id) return ''
  return id.length > 16 ? id.slice(0, 8) + '...' + id.slice(-8) : id
}
</script>

<style scoped lang="less">
.detail-card {
  margin-bottom: 12px;

  :deep(.ant-card-head) {
    min-height: 36px;
    padding: 0 12px;
  }
  :deep(.ant-card-head-title) {
    font-size: 14px;
    font-weight: 600;
  }
  :deep(.ant-card-body) {
    padding: 12px;
  }
}

.config-json {
  background: var(--bg-input);
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 12px;
  font-family: monospace;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  color: var(--fg);
}

.metric {
  text-align: center;
  padding: 8px;
}

.metric-label {
  font-size: 12px;
  color: var(--fg-secondary);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--fg);
}

.trace-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--divider);

  &:last-child { border-bottom: none; }
}

.trace-id {
  font-family: monospace;
  font-size: 12px;
  background: var(--bg-input);
  padding: 1px 6px;
  border-radius: 3px;
}

.trace-meta {
  font-size: 11px;
  color: var(--fg-muted);
}
</style>