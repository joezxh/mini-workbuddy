<template>
  <div class="data-analysis-card">
    <!-- 头部 -->
    <div class="analysis-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <span class="header-title">{{ title }}</span>
      </div>
      <div class="header-right">
        <a-tag v-if="dataSource" color="purple" size="small">
          <DatabaseOutlined /> {{ dataSource }}
        </a-tag>
        <a-tag v-if="rowCount !== undefined" color="blue" size="small">
          {{ rowCount.toLocaleString() }} 行
        </a-tag>
        <a-button v-if="expandable" type="link" size="small" @click="expanded = !expanded">
          {{ expanded ? '收起' : '展开' }}
          <UpOutlined v-if="expanded" />
          <DownOutlined v-else />
        </a-button>
      </div>
    </div>

    <!-- 摘要文本（始终显示） -->
    <div v-if="summary" class="analysis-summary">
      {{ summary }}
    </div>

    <!-- KPI 卡片 -->
    <div v-if="metrics && metrics.length" class="metric-grid">
      <div v-for="(m, idx) in metrics" :key="idx" class="metric-card" :style="{ borderLeftColor: m.color || 'var(--accent)' }">
        <div class="metric-label">{{ m.label }}</div>
        <div class="metric-value">{{ m.value }}</div>
        <div v-if="m.delta !== undefined" class="metric-delta" :class="m.delta >= 0 ? 'up' : 'down'">
          <CaretUpOutlined v-if="m.delta >= 0" />
          <CaretDownOutlined v-else />
          {{ Math.abs(m.delta).toFixed(1) }}%
        </div>
      </div>
    </div>

    <!-- 折叠区：图表 / 表格 -->
    <div v-show="expanded || !expandable" v-if="hasDetail" class="analysis-detail">
      <!-- 节点输出（Dify Code/Tool 节点结果） -->
      <div v-if="nodeOutputs && nodeOutputs.length" class="detail-section">
        <div class="detail-label">节点执行结果（{{ nodeOutputs.length }}）</div>
        <a-collapse size="small" :bordered="false">
          <a-collapse-panel
            v-for="(node, idx) in nodeOutputs"
            :key="idx"
            :header="`${node.title || '节点'} (${node.node_type})`"
          >
            <pre class="node-outputs">{{ formatJson(node.outputs) }}</pre>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <!-- 表格数据 -->
      <div v-if="tableData && tableData.length" class="detail-section">
        <div class="detail-label">数据预览（前 {{ Math.min(tableData.length, 10) }} 行）</div>
        <a-table
          :columns="tableColumns"
          :data-source="tableData.slice(0, 10)"
          :pagination="false"
          size="small"
          bordered
        />
      </div>

      <!-- 知识库检索资源 -->
      <div v-if="retrieverResources && retrieverResources.length" class="detail-section">
        <div class="detail-label">知识库引用（{{ retrieverResources.length }} 条）</div>
        <div class="resource-list">
          <a-tag
            v-for="(r, idx) in retrieverResources"
            :key="idx"
            color="cyan"
            class="resource-tag"
          >
            <ReadOutlined /> {{ r.title || r.dataset_name || `资源 ${idx + 1}` }}
          </a-tag>
        </div>
      </div>

      <!-- 工具调用记录 -->
      <div v-if="toolCalls && toolCalls.length" class="detail-section">
        <div class="detail-label">工具调用（{{ toolCalls.length }}）</div>
        <div class="tool-call-list">
          <div v-for="(tc, idx) in toolCalls" :key="idx" class="tool-call-item">
            <a-tag color="orange" size="small">{{ tc.event || 'tool' }}</a-tag>
            <span class="tool-call-name">{{ tc.data?.tool_name || tc.data?.name || `Call #${idx + 1}` }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  DatabaseOutlined,
  UpOutlined,
  DownOutlined,
  CaretUpOutlined,
  CaretDownOutlined,
  ReadOutlined,
} from '@ant-design/icons-vue'

// ── 类型 ─────────────────────────────────────────────────────────────────────

export interface MetricItem {
  label: string
  value: string | number
  delta?: number
  color?: string
}

export interface RetrieverResource {
  title?: string
  dataset_name?: string
  dataset_id?: string
  segment_id?: string
  score?: number
  content?: string
}

export interface ToolCallItem {
  event?: string
  data?: any
}

export interface NodeOutput {
  node_id?: string
  node_type?: string
  title?: string
  outputs?: any
}

export interface DataAnalysisPayload {
  title?: string
  /** 兼容字段：部分 Skill 返 'name' 作为标题 */
  name?: string
  dataSource?: string
  /** 兼容字段：部分 Skill 返 'source' 作为数据来源 */
  source?: string
  summary?: string
  /** 兼容字段：部分 Skill 返 'description' 作为摘要 */
  description?: string
  rowCount?: number
  /** 兼容字段：snake_case 后端字段 */
  row_count?: number
  metrics?: MetricItem[]
  tableData?: Array<Record<string, any>>
  /** 兼容字段：部分 Skill 返 'data' 作为表格数据 */
  data?: Array<Record<string, any>>
  /** 兼容字段：部分 Skill 返 'rows' 作为表格数据 */
  rows?: Array<Record<string, any>>
  retriever_resources?: RetrieverResource[]
  tool_calls?: ToolCallItem[]
  node_outputs?: NodeOutput[] | Record<string, NodeOutput>
  raw?: any  // 原始数据兜底
}

// ── Props ────────────────────────────────────────────────────────────────────

const props = withDefaults(defineProps<{
  /** 分析数据 payload */
  analysis: DataAnalysisPayload | any
  /** 是否支持展开/折叠 */
  expandable?: boolean
  /** 默认是否展开 */
  defaultExpanded?: boolean
}>(), {
  expandable: true,
  defaultExpanded: true,
})

const expanded = ref(props.defaultExpanded)

// ── 计算属性 ─────────────────────────────────────────────────────────────────

const payload = computed<DataAnalysisPayload>(() => {
  const a = props.analysis || {}
  // 兼容多种来源：
  //   1) 直接 DataAnalysisPayload
  //   2) 嵌套在 tool_results 下的对象
  //   3) extra_data.analysis 整体
  return a.tool_results || a
})

const title = computed(() => payload.value.title || payload.value.name || '数据分析结果')
const dataSource = computed(() => payload.value.dataSource || payload.value.source || '')
const summary = computed(() => payload.value.summary || payload.value.description || '')

const rowCount = computed(() => {
  const rc = payload.value.rowCount ?? payload.value.row_count
  if (typeof rc === 'number') return rc
  if (Array.isArray(payload.value.tableData)) return payload.value.tableData.length
  return undefined
})

const metrics = computed<MetricItem[]>(() => {
  const m = payload.value.metrics
  return Array.isArray(m) ? m : []
})

const tableData = computed(() => {
  // 兼容多种字段
  return payload.value.tableData || payload.value.data || payload.value.rows || []
})

const tableColumns = computed(() => {
  const data = tableData.value
  if (!data?.length) return []
  const first = data[0] || {}
  return Object.keys(first).map((key) => ({
    title: key,
    dataIndex: key,
    key,
    ellipsis: true,
    width: 140,
  }))
})

const retrieverResources = computed<RetrieverResource[]>(() => {
  const r = payload.value.retriever_resources
  return Array.isArray(r) ? r : []
})

const toolCalls = computed<ToolCallItem[]>(() => {
  const tc = payload.value.tool_calls
  return Array.isArray(tc) ? tc : []
})

const nodeOutputs = computed<NodeOutput[]>(() => {
  const n = payload.value.node_outputs
  if (Array.isArray(n)) return n
  if (n && typeof n === 'object') {
    return Object.values(n) as NodeOutput[]
  }
  return []
})

const hasDetail = computed(() =>
  (nodeOutputs.value?.length ?? 0) > 0
  || (tableData.value?.length ?? 0) > 0
  || (retrieverResources.value?.length ?? 0) > 0
  || (toolCalls.value?.length ?? 0) > 0,
)

// ── 方法 ─────────────────────────────────────────────────────────────────────

function formatJson(data: any): string {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}
</script>

<style scoped lang="less">
.data-analysis-card {
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  margin: 8px 0;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.analysis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: linear-gradient(135deg, var(--bg-input) 0%, var(--bg-input) 100%);
  border-bottom: 1px solid var(--border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 18px;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.analysis-summary {
  padding: 10px 14px;
  font-size: 13px;
  color: var(--fg);
  line-height: 1.6;
  background: var(--bg-input);
  border-bottom: 1px solid var(--border);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  padding: 12px 14px;
}

.metric-card {
  padding: 10px 12px;
  background: var(--bg-input);
  border-left: 3px solid var(--accent);
  border-radius: 4px;

  .metric-label {
    font-size: 11px;
    color: var(--fg-secondary);
    margin-bottom: 4px;
  }

  .metric-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--fg);
    line-height: 1.2;
  }

  .metric-delta {
    font-size: 11px;
    margin-top: 4px;
    font-weight: 500;

    &.up { color: var(--ok); }
    &.down { color: var(--err); }
  }
}

.analysis-detail {
  padding: 0 14px 12px;
}

.detail-section {
  margin-top: 10px;
}

.detail-label {
  font-size: 12px;
  color: var(--fg-secondary);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.node-outputs {
  font-size: 12px;
  background: var(--bg-input);
  padding: 8px 10px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  white-space: pre-wrap;
}

.resource-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.resource-tag {
  cursor: default;
}

.tool-call-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-call-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: var(--bg-input);
  border-radius: 4px;
}

.tool-call-name {
  font-size: 12px;
  color: var(--fg-secondary);
}

:deep(.ant-collapse-header) {
  padding: 6px 10px !important;
  font-size: 12px;
  background: var(--bg-input);
}
</style>