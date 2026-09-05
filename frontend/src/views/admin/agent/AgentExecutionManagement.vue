<template>
  <div class="agent-execution-management">
    <div class="page-header">
      <h2 class="page-title">📋 会话调用记录</h2>
      <div class="header-actions">
        <a-button @click="loadStats">
          <BarChartOutlined /> 统计
        </a-button>
        <a-button @click="loadData">
          <ReloadOutlined :spin="loading" /> 刷新
        </a-button>
      </div>
    </div>

    <a-card size="small">
      <a-alert
        v-if="targetLabel"
        type="info"
        show-icon
        class="filter-hint"
        :message="targetLabel"
      >
        <template #action>
          <a-button size="small" @click="clearTargetFilter">查看全部</a-button>
        </template>
      </a-alert>
      <div class="list-toolbar">
        <a-space wrap>
          <a-input
            v-model:value="filterKeyword"
            placeholder="搜索 Target / 输入 / 输出"
            allow-clear
            style="width: 240px"
            @press-enter="onSearch"
            @change="onKeywordChange"
          >
            <template #prefix><SearchOutlined /></template>
          </a-input>
          <a-input
            v-model:value="filterSessionId"
            placeholder="会话 ID"
            allow-clear
            style="width: 150px"
            @press-enter="loadData"
          />
          <a-select
            v-model:value="filterMode"
            placeholder="调用模式"
            style="width: 160px"
            allow-clear
            @change="loadData"
          >
            <a-select-option v-for="m in modeOptions" :key="m.value" :value="m.value">
              {{ m.label }}
            </a-select-option>
          </a-select>
          <a-select
            v-model:value="filterStatus"
            placeholder="状态"
            style="width: 140px"
            allow-clear
            @change="loadData"
          >
            <a-select-option v-for="s in statusOptions" :key="s.value" :value="s.value">
              {{ s.label }}
            </a-select-option>
          </a-select>
          <a-range-picker
            v-model:value="filterDateRange"
            :show-time="true"
            format="YYYY-MM-DD HH:mm:ss"
            style="width: 380px"
            @change="loadData"
          />
        </a-space>
      </div>

      <a-spin :spinning="loading">
        <a-table
          :columns="columns"
          :data-source="records"
          :pagination="pagination"
          row-key="execution_id"
          :custom-row="customRow"
          @change="handleTableChange"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'started_at'">
              <span>{{ formatDate((record as AgentExecutionItem).started_at) }}</span>
            </template>
            <template v-else-if="column.key === 'execution_mode'">
              <a-tag :color="modeColor((record as AgentExecutionItem).execution_mode)">
                {{ (record as AgentExecutionItem).execution_mode }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'target_id'">
              <a-tag :color="modeColor((record as AgentExecutionItem).execution_mode)">
                {{ formatTarget(record as AgentExecutionItem) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'session'">
              <a-tag color="blue">#{{ (record as AgentExecutionItem).session_id }}</a-tag>
              <span class="session-title">{{ (record as AgentExecutionItem).session_title || '新对话' }}</span>
            </template>
            <template v-else-if="column.key === 'user_input'">
              <span :title="(record as AgentExecutionItem).user_input">{{ truncate((record as AgentExecutionItem).user_input) }}</span>
            </template>
            <template v-else-if="column.key === 'output'">
              <span :title="(record as AgentExecutionItem).output">{{ truncate((record as AgentExecutionItem).output) }}</span>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="statusColor((record as AgentExecutionItem).status)">
                {{ statusLabel((record as AgentExecutionItem).status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'latency_ms'">
              <span>{{ (record as AgentExecutionItem).latency_ms != null ? `${(record as AgentExecutionItem).latency_ms} ms` : '-' }}</span>
            </template>
          </template>
        </a-table>
        <a-empty v-if="!loading && records.length === 0" description="暂无调用记录" />
      </a-spin>
    </a-card>

    <!-- 详情抽屉 -->
    <a-drawer
      v-model:open="detailVisible"
      title="调用详情"
      width="860px"
      :footer="null"
      @close="detailVisible = false"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <a-descriptions bordered size="small" :column="2">
            <a-descriptions-item label="执行ID" :span="2">
              <span class="text-mono">{{ detail.execution_id }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="会话">
              #{{ detail.session_id }} {{ detail.session_title || '' }}
            </a-descriptions-item>
            <a-descriptions-item label="模式">
              <a-tag :color="modeColor(detail.execution_mode)">{{ detail.execution_mode }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="Target">
              <a-tag :color="modeColor(detail.execution_mode)">
                {{ formatTarget(detail) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ formatDate(detail.started_at) }}</a-descriptions-item>
            <a-descriptions-item label="完成时间">{{ formatDate(detail.completed_at) }}</a-descriptions-item>
            <a-descriptions-item label="耗时">
              {{ detail.latency_ms != null ? `${detail.latency_ms} ms` : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="用户">{{ detail.user_id ?? '-' }}</a-descriptions-item>
          </a-descriptions>

          <!-- 分层 DAG 拓扑 -->
          <a-divider orientation="left">
            调用链路拓扑
            <span class="divider-hint" v-if="detail.events && detail.events.length">
              （{{ detail.events.length }} 个节点）
            </span>
          </a-divider>
          <div v-if="hasTopology" class="topo-wrap">
            <div ref="topoChartRef" class="topo-chart"></div>
            <a-radio-group v-model:value="topoMode" size="small" class="topo-toggle">
              <a-radio-button value="dag">分层拓扑</a-radio-button>
              <a-radio-button value="flow">流程视图</a-radio-button>
            </a-radio-group>
          </div>
          <a-empty v-else description="该次调用无调用链拓扑数据" />

          <!-- 时间线 -->
          <a-divider orientation="left">执行时间线</a-divider>
          <a-timeline v-if="detail.events && detail.events.length" class="evt-timeline">
            <a-timeline-item
              v-for="ev in sortedEvents"
              :key="ev.id"
              :color="eventColor(ev)"
            >
              <div class="evt-head">
                <a-tag :color="eventTypeColor(ev.event_type)">{{ ev.event_type || 'event' }}</a-tag>
                <span class="evt-name">{{ ev.role_name || ev.agent_code || ev.node_key || ev.source || `#${ev.id}` }}</span>
                <span class="evt-time">{{ formatTime(ev.created_at) }}</span>
              </div>
              <div v-if="ev.content" class="evt-content">{{ truncate(String(ev.content), 160) }}</div>
            </a-timeline-item>
          </a-timeline>
          <a-empty v-else description="无节点事件" />

          <!-- 人工介入 -->
          <a-divider orientation="left" v-if="detail.hitl_pauses && detail.hitl_pauses.length">
            人工介入 (HITL)
          </a-divider>
          <a-list
            v-if="detail.hitl_pauses && detail.hitl_pauses.length"
            size="small"
            bordered
            :data-source="detail.hitl_pauses"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <a-tag :color="item.status === 'resolved' ? 'success' : 'warning'">
                      {{ item.pause_type || 'pause' }}
                    </a-tag>
                    <span class="hitl-stage">{{ item.status || '-' }}</span>
                  </template>
                  <template #description>
                    <div v-if="item.comment" class="hitl-reason">审批意见：{{ item.comment }}</div>
                    <div v-if="item.payload" class="hitl-row">
                      <span>请求负载：{{ truncate(formatJson(item.payload), 80) }}</span>
                    </div>
                    <div class="hitl-time">
                      请求：{{ formatDate(item.created_at) }}
                      <span v-if="item.resolved_at"> / 解决：{{ formatDate(item.resolved_at) }}</span>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>

          <a-divider orientation="left">输入</a-divider>
          <pre class="code-block">{{ detail.user_input || '-' }}</pre>

          <a-divider orientation="left">输出 (Output)</a-divider>
          <pre class="code-block">{{ detail.output || '-' }}</pre>

          <a-divider orientation="left" v-if="detail.error">错误 (Error)</a-divider>
          <pre class="code-block error-block" v-if="detail.error">{{ detail.error }}</pre>

          <a-divider orientation="left" v-if="detail.metadata_json">Metadata</a-divider>
          <pre class="code-block" v-if="detail.metadata_json">{{ formatJson(detail.metadata_json) }}</pre>

          <a-divider orientation="left" v-if="detail.trace">Trace</a-divider>
          <pre class="code-block" v-if="detail.trace">{{ formatJson(detail.trace) }}</pre>
        </template>
      </a-spin>
    </a-drawer>

    <!-- 统计弹窗 -->
    <a-modal
      v-model:open="statsVisible"
      title="调用统计"
      width="560px"
      :footer="null"
      @cancel="statsVisible = false"
    >
      <a-spin :spinning="statsLoading">
        <template v-if="stats">
          <a-descriptions bordered size="small" :column="1">
            <a-descriptions-item label="总调用数">{{ stats.total ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="平均耗时">
              {{ stats.avg_latency_ms != null ? `${stats.avg_latency_ms} ms` : '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="按模式">
              <a-tag v-for="(v, k) in stats.by_execution_mode" :key="`m-${k}`" :color="modeColor(k)">
                {{ targetTypeLabel(k) }}: {{ v }}
              </a-tag>
              <span v-if="!stats.by_execution_mode || !Object.keys(stats.by_execution_mode).length" class="text-muted">-</span>
            </a-descriptions-item>
            <a-descriptions-item label="按状态">
              <a-tag v-for="(v, k) in stats.by_status" :key="`s-${k}`" :color="statusColor(k)">
                {{ statusLabel(k) }}: {{ v }}
              </a-tag>
              <span v-if="!stats.by_status || !Object.keys(stats.by_status).length" class="text-muted">-</span>
            </a-descriptions-item>
          </a-descriptions>
        </template>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick, inject } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  BarChartOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import type { Dayjs } from 'dayjs'
import {
  listAgentExecutions,
  getAgentExecutionDetail,
  getAgentExecutionStats,
  type AgentExecutionItem,
  type AgentExecutionDetail,
  type AgentExecutionStats,
  type AgentExecutionEvent,
  type ExecutionMode,
  type ExecutionStatus,
} from '@/api/agentExecution'

const loading = ref(false)
const records = ref<AgentExecutionItem[]>([])

const filterKeyword = ref<string | undefined>()
const filterSessionId = ref<string | undefined>()
const filterMode = ref<ExecutionMode | undefined>()
const filterStatus = ref<ExecutionStatus | undefined>()
const filterDateRange = ref<[Dayjs, Dayjs] | null>(null)
const filterTargetId = ref<string | undefined>()
const targetLabel = ref<string | undefined>()

const modeOptions = [
  { value: 'dify', label: 'Dify' },
  { value: 'skill', label: 'Skill' },
  { value: 'agent', label: 'Agent' },
  { value: 'agent_team', label: 'Agent Team' },
  { value: 'sqlbot', label: 'SqlBot' },
]
const statusOptions = [
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
]

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
})

const columns = [
  { title: '时间', key: 'started_at', width: 170 },
  { title: '模式', key: 'execution_mode', width: 110 },
  { title: '目标(Target)', key: 'target_id', width: 160 },
  { title: '会话', key: 'session', width: 200 },
  { title: '参数摘要', key: 'user_input', width: 200, ellipsis: true },
  { title: '结果摘要', key: 'output', width: 200, ellipsis: true },
  { title: '状态', key: 'status', width: 100 },
  { title: '耗时', key: 'latency_ms', width: 110 },
]

// ---- 详情 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<AgentExecutionDetail | null>(null)

// ---- 拓扑图 ----
const topoChartRef = ref<HTMLDivElement | null>(null)
const topoMode = ref<'dag' | 'flow'>('dag')
let topoChart: echarts.ECharts | null = null

// ---- 统计 ----
const statsVisible = ref(false)
const statsLoading = ref(false)
const stats = ref<AgentExecutionStats | null>(null)

// 事件按时间排序
const sortedEvents = computed<AgentExecutionEvent[]>(() => {
  if (!detail.value?.events) return []
  return [...detail.value.events].sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0
    if (ta !== tb) return ta - tb
    return (a.id || 0) - (b.id || 0)
  })
})

// 是否存在可绘制拓扑的事件（含 node_key / layer / parent_keys）
const hasTopology = computed(() => {
  const evs = detail.value?.events || []
  return evs.some((e) => {
    const meta = e.metadata_json || {}
    return (
      e.node_key ||
      e.layer != null ||
      (e.parent_keys && e.parent_keys.length) ||
      meta.node_key ||
      meta.layer != null ||
      (meta.parent_keys && meta.parent_keys.length)
    )
  })
})

// 取事件的拓扑字段（优先顶层便捷字段，回退 metadata_json）
function evMeta(ev: AgentExecutionEvent) {
  return {
    node_key: ev.node_key || ev.metadata_json?.node_key || ev.metadata_json?.node_role,
    layer: ev.layer != null ? ev.layer : ev.metadata_json?.layer,
    parent_keys: ev.parent_keys?.length
      ? ev.parent_keys
      : ev.metadata_json?.parent_keys || [],
    node_type: ev.node_type || ev.metadata_json?.node_type,
    node_status: ev.node_status || ev.metadata_json?.node_status,
    role_name: ev.role_name || ev.metadata_json?.role_name,
    agent_code: ev.agent_code || ev.metadata_json?.agent_code,
  }
}

function onKeywordChange() {
  // 清空即触发搜索
  if (!filterKeyword.value) loadData()
}

function clearTargetFilter() {
  filterTargetId.value = undefined
  filterMode.value = undefined
  targetLabel.value = undefined
  pagination.current = 1
  loadData()
}

function onSearch() {
  pagination.current = 1
  loadData()
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterSessionId.value) params.session_id = Number(filterSessionId.value)
    if (filterMode.value) params.execution_mode = filterMode.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterTargetId.value) params.target_id = filterTargetId.value
    if (filterDateRange.value && filterDateRange.value.length === 2) {
      params.start_time = filterDateRange.value[0].format('YYYY-MM-DD HH:mm:ss')
      params.end_time = filterDateRange.value[1].format('YYYY-MM-DD HH:mm:ss')
    }
    const res = await listAgentExecutions(params)
    records.value = res.items || []
    pagination.total = res.total || 0
  } catch (e: any) {
    message.error('加载失败：' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsVisible.value = true
  statsLoading.value = true
  try {
    const res = await getAgentExecutionStats()
    stats.value = res
  } catch (e: any) {
    message.error('统计加载失败：' + (e.message || '未知错误'))
  } finally {
    statsLoading.value = false
  }
}

async function openDetail(record: AgentExecutionItem) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const res = await getAgentExecutionDetail(record.execution_id)
    detail.value = res
    await nextTick()
    renderTopo()
  } catch (e: any) {
    message.error('详情加载失败：' + (e.message || '未知错误'))
  } finally {
    detailLoading.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function customRow(record: AgentExecutionItem) {
  return {
    onClick: () => openDetail(record),
    style: 'cursor: pointer;',
  }
}

// ── 拓扑图渲染 ─────────────────────────────────────────────
function renderTopo() {
  if (!topoChartRef.value || !hasTopology.value) return
  if (!topoChart) {
    topoChart = echarts.init(topoChartRef.value)
  }
  const evs = detail.value?.events || []
  const nodes = new Map<string, any>()
  const edges: any[] = []

  evs.forEach((ev) => {
    const m = evMeta(ev)
    const key = m.node_key || ev.source_id || `e${ev.id}`
    const layer = m.layer != null ? Number(m.layer) : 0
    const parentKeys: string[] = m.parent_keys || []
    nodes.set(key, {
      id: key,
      name: m.role_name || m.agent_code || ev.event_type || key,
      value: ev.content,
      layer,
      nodeType: m.node_type || ev.event_type,
      status: m.node_status,
    })
    parentKeys.forEach((pk) => {
      if (pk && pk !== key) edges.push({ source: pk, target: key })
    })
  })

  const nodeList = Array.from(nodes.values())
  // 根据 layer 计算 x 坐标（分层）；无 layer 的退化为按事件序
  const maxLayer = nodeList.reduce((m, n) => Math.max(m, n.layer), 0)
  nodeList.forEach((n) => {
    const col = maxLayer > 0 ? n.layer / maxLayer : 0
    n.x = col * 600 + 60
  })

  if (topoMode.value === 'flow') {
    // 流程视图：按时间顺序横向排布
    sortedEvents.value.forEach((ev, i) => {
      const m = evMeta(ev)
      const key = m.node_key || ev.source_id || `e${ev.id}`
      const n = nodes.get(key)
      if (n) n.x = i * 120 + 60
    })
  }

  const option = {
    tooltip: {
      formatter: (p: any) => {
        if (p.dataType === 'edge') return `${p.data.source} → ${p.data.target}`
        const d = p.data
        return `<b>${d.name}</b><br/>类型：${d.nodeType || '-'}<br/>状态：${d.status || '-'}`
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        symbolSize: 46,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
        label: { show: true, position: 'bottom', fontSize: 11 },
        lineStyle: { color: '#bbb', curveness: 0.08 },
        data: nodeList.map((n) => ({
          id: n.id,
          name: n.name,
          x: n.x,
          y: n.layer * 90 + 40,
          itemStyle: { color: nodeColor(n.status, n.nodeType) },
          value: n.value,
          _meta: n,
        })),
        edges: edges.map((e) => ({ source: e.source, target: e.target })),
      },
    ],
  }
  topoChart.setOption(option, true)
}

function nodeColor(status?: string, nodeType?: string): string {
  if (status === 'failed' || nodeType === 'NODE_ERROR') return '#ff4d4f'
  if (status === 'completed' || status === 'success') return '#52c41a'
  if (status === 'running' || status === 'pending') return '#1677ff'
  if (nodeType === 'TEAM_START' || nodeType === 'team_layer_start') return '#722ed1'
  if (nodeType === 'AGENT_START' || nodeType === 'agent_start') return '#13c2c2'
  if (nodeType === 'SYNTHESIS' || nodeType === 'NODE_END') return '#fa8c16'
  return '#8c8c8c'
}

function eventColor(ev: AgentExecutionEvent): string {
  const s = ev.node_status
  if (s === 'failed') return 'red'
  if (s === 'completed' || s === 'success') return 'green'
  if (s === 'running') return 'blue'
  return 'gray'
}

function eventTypeColor(type?: string): string {
  switch (type) {
    case 'node_start': return 'blue'
    case 'node_end': return 'green'
    case 'node_error': return 'red'
    case 'team_layer_start': return 'purple'
    case 'team_layer_end': return 'purple'
    case 'agent_start': return 'cyan'
    case 'agent_end': return 'cyan'
    case 'hitl_request': return 'orange'
    case 'hitl_resume': return 'orange'
    default: return 'default'
  }
}

watch(topoMode, () => renderTopo())

function truncate(text?: string, len = 60): string {
  if (!text) return '-'
  return text.length > len ? text.slice(0, len) + '…' : text
}

function formatDate(d?: string): string {
  if (!d) return '-'
  try {
    return new Date(d).toLocaleString('zh-CN')
  } catch {
    return d
  }
}

function formatTime(d?: string): string {
  if (!d) return '-'
  try {
    return new Date(d).toLocaleTimeString('zh-CN')
  } catch {
    return d
  }
}

function formatJson(obj?: Record<string, any>): string {
  if (!obj) return '-'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function modeColor(mode?: string): string {
  switch (mode) {
    case 'dify': return 'geekblue'
    case 'skill': return 'green'
    case 'agent': return 'purple'
    case 'agent_team': return 'magenta'
    case 'sqlbot': return 'orange'
    default: return 'default'
  }
}

// target_id 的语义由 execution_mode 决定（skill_id 已由 target_id 取代）：
// dify→Dify流程 / skill→技能包 / agent→Agent配置 / agent_team→团队 / sqlbot 固定 "0"
function targetTypeLabel(mode?: string): string {
  switch (mode) {
    case 'dify': return 'Dify流程'
    case 'skill': return '技能包'
    case 'agent': return 'Agent配置'
    case 'agent_team': return '团队'
    case 'sqlbot': return 'SqlBot'
    default: return '目标'
  }
}

// 展示「目标类型 + ID」；sqlbot 的 target_id 固定为 "0"，仅显示类型
function formatTarget(record: AgentExecutionItem): string {
  const id = record.target_id
  if (!id || (record.execution_mode === 'sqlbot' && id === '0')) {
    return targetTypeLabel(record.execution_mode)
  }
  return `${targetTypeLabel(record.execution_mode)} · ${id}`
}

function statusColor(status?: string): string {
  switch (status) {
    case 'running': return 'processing'
    case 'completed': return 'success'
    case 'failed': return 'error'
    default: return 'default'
  }
}

function statusLabel(status?: string): string {
  switch (status) {
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    default: return status || '-'
  }
}

onMounted(() => {
  // 来自 AgentManagement「链路」按钮跳转：按 agent / skill 等精确过滤调用链路
  const execFilter = inject<{ mode?: string; targetId?: string; label?: string }>('executionFilter')
  if (execFilter?.targetId) {
    filterTargetId.value = execFilter.targetId
    targetLabel.value = execFilter.label || (execFilter.mode ? `当前过滤：${targetTypeLabel(execFilter.mode)} #${execFilter.targetId}` : `当前过滤：对象 #${execFilter.targetId}`)
    if (execFilter.mode) filterMode.value = execFilter.mode as ExecutionMode
  }
  loadData()
  window.addEventListener('resize', () => topoChart?.resize())
})
</script>

<style scoped lang="less">
.agent-execution-management {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 16px 0;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--fg);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.list-toolbar {
  margin-bottom: 12px;
}

.session-title {
  margin-left: 6px;
  font-size: 13px;
  color: var(--fg);
}

.text-mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}

.text-muted {
  color: var(--fg-muted);
}

.divider-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--fg-muted);
}

.topo-wrap {
  position: relative;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  background: var(--bg-input);
}

.topo-chart {
  width: 100%;
  height: 360px;
}

.topo-toggle {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
}

.evt-timeline {
  padding-left: 4px;
}

.evt-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.evt-name {
  font-weight: 600;
  color: var(--fg);
}

.evt-latency {
  font-size: 12px;
  color: var(--accent);
}

.evt-time {
  font-size: 12px;
  color: var(--fg-muted);
}

.evt-content {
  margin-top: 4px;
  font-size: 12px;
  color: var(--fg-secondary);
  background: var(--bg-input);
  border-radius: 4px;
  padding: 6px 8px;
  white-space: pre-wrap;
  word-break: break-all;
}

.hitl-stage {
  font-size: 13px;
  color: var(--fg);
}

.hitl-row {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--fg-secondary);
  margin-top: 2px;
}

.hitl-reason {
  font-size: 12px;
  color: var(--err);
  margin-top: 2px;
}

.hitl-time {
  font-size: 12px;
  color: var(--fg-muted);
  margin-top: 2px;
}

.code-block {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 280px;
  overflow: auto;
  margin: 0;
}

// 表格单元格：禁止换行 + 超出省略号截断
.agent-execution-management :deep(.ant-table-cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

// 带 title 提示的单元格（参数摘要 / 结果摘要 / 目标）确保截断生效
.agent-execution-management :deep(.ant-table-cell .ant-typography),
.agent-execution-management :deep(.ant-table-cell span[title]) {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
}

// 单元格内的标签（目标 / 模式 / 状态 / 会话）限制宽度并省略
.agent-execution-management :deep(.ant-table-cell .ant-tag) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.error-block {
  background: var(--err-soft);
  border-color: var(--err);
  color: var(--err);
}
</style>
