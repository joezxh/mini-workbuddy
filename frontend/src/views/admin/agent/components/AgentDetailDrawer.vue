<template>
  <a-drawer
    v-model:open="visible"
    :title="`Agent 详情 - ${agentData?.name || ''}`"
    placement="right"
    :width="640"
    :body-style="{ padding: '16px' }"
  >
    <a-spin :spinning="loading">
      <template v-if="agentData">
        <!-- 基本信息 -->
        <a-card size="small" title="基本信息" class="detail-card">
          <a-descriptions :column="2" size="small">
            <a-descriptions-item label="ID">{{ agentData.id }}</a-descriptions-item>
            <a-descriptions-item label="编码">
              <code>{{ agentData.agent_code }}</code>
            </a-descriptions-item>
            <a-descriptions-item label="名称">{{ agentData.name }}</a-descriptions-item>
            <a-descriptions-item label="类型">
              <a-tag :color="typeColor(agentData.agent_type)">
                {{ typeLabel(agentData.agent_type) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="agentData.is_active ? 'green' : 'default'">
                {{ agentData.is_active ? '已启用' : '已禁用' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="排序">{{ agentData.sort_order }}</a-descriptions-item>
            <a-descriptions-item label="创建时间" :span="2">
              {{ formatDate(agentData.created_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="描述" :span="2">
              {{ agentData.description || '暂无描述' }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 可视化配置 -->
        <a-card size="small" title="可视化配置" class="detail-card">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item label="系统提示词">
              <pre class="config-json">{{ agentData.system_prompt || '（未配置）' }}</pre>
            </a-descriptions-item>
            <a-descriptions-item label="模型">
              {{ agentData.model_config?.provider || '-' }} / {{ agentData.model_config?.model || '-' }}
              <span v-if="agentData.model_config?.temperature !== undefined">
                · temp {{ agentData.model_config.temperature }}
              </span>
            </a-descriptions-item>
            <a-descriptions-item label="执行模式">
              {{ agentData.execution_mode || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="绑定工具">
              <a-tag v-for="t in (agentData.tools || [])" :key="t" color="blue">{{ t }}</a-tag>
              <span v-if="!(agentData.tools || []).length">无</span>
            </a-descriptions-item>
            <a-descriptions-item label="绑定技能">
              <a-tag v-for="s in (agentData.skills || [])" :key="s" color="green">{{ s }}</a-tag>
              <span v-if="!(agentData.skills || []).length">无</span>
            </a-descriptions-item>
            <a-descriptions-item label="MCP 服务">
              <a-tag v-for="m in (agentData.mcp_servers || [])" :key="m.name || JSON.stringify(m)" color="orange">
                {{ m.name || m }}
              </a-tag>
              <span v-if="!(agentData.mcp_servers || []).length">无</span>
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 类型配置 -->
        <a-card size="small" title="原始配置 (config)" class="detail-card">
          <pre class="config-json">{{ formatConfig(agentData.config) }}</pre>
        </a-card>

        <!-- 监控统计 -->
        <a-card size="small" title="运行统计" class="detail-card">
          <a-row :gutter="16">
            <a-col :span="8">
              <div class="metric">
                <div class="metric-label">调用次数</div>
                <div class="metric-value">{{ metrics.invocation_count || 0 }}</div>
              </div>
            </a-col>
            <a-col :span="8">
              <div class="metric">
                <div class="metric-label">成功率</div>
                <div class="metric-value">{{ metrics.success_rate || '0' }}%</div>
              </div>
            </a-col>
            <a-col :span="8">
              <div class="metric">
                <div class="metric-label">平均耗时</div>
                <div class="metric-value">{{ metrics.avg_duration || 0 }}ms</div>
              </div>
            </a-col>
          </a-row>
        </a-card>

        <!-- 最近链路 -->
        <a-card size="small" title="最近链路" class="detail-card">
          <template #extra>
            <a-button size="small" type="link" @click="loadTraces">
              <ReloadOutlined :spin="loadingTraces" />
            </a-button>
          </template>
          <a-empty v-if="recentTraces.length === 0" description="暂无链路" :image-size="60" />
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
                  <a @click="openTrace(item.trace_id)">查看</a>
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
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getAgentDetail, type AgentConfig } from '@/api/agentConfig'
import { getTraceList } from '@/api/agent'
import AgentTraceDrawer from '@/views/assistant/components/AgentTraceDrawer.vue'

const props = defineProps<{
  agentId?: number
}>()

const visible = defineModel<boolean>('visible', { default: false })

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
    message.error('加载 Agent 详情失败：' + (e.message || '未知错误'))
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
    CHAT: '💬 会话型',
    WORKFLOW: '⚡ 工作流型',
    SKILL: '🔧 技能型',
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
  background: #f5f5f5;
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 12px;
  font-family: monospace;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  color: #333;
}

.metric {
  text-align: center;
  padding: 8px;
}

.metric-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
}

.trace-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;

  &:last-child { border-bottom: none; }
}

.trace-id {
  font-family: monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 3px;
}

.trace-meta {
  font-size: 11px;
  color: #999;
}
</style>