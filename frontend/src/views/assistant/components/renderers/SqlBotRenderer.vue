<template>
  <div class="sqlbot-renderer">
    <!-- 进度状态 -->
    <div v-if="stage && stage !== 'done'" class="sqlbot-progress">
      <a-spin size="small" />
      <span class="progress-msg">{{ progressMessage }}</span>
    </div>

    <!-- SQL 展示 -->
    <div v-if="sql" class="sql-block">
      <div class="sql-header">
        <span class="sql-label">📝 生成 SQL</span>
        <a-button size="small" type="text" @click="copySql">复制</a-button>
      </div>
      <pre class="sql-code"><code>{{ sql }}</code></pre>
    </div>

    <!-- 数据表格（AntV S2 或 a-table fallback） -->
    <div v-if="records?.length" class="data-table-wrap">
      <div class="table-header">
        <span class="table-label">📊 查询结果（共 {{ total }} 条）</span>
        <a-button size="small" type="text" @click="toggleTableView">
          {{ useS2 ? '切换简易表格' : '切换高级表格' }}
        </a-button>
      </div>
      <div v-if="useS2" ref="s2Container" class="s2-container"></div>
      <a-table
        v-else
        :columns="tableColumns"
        :data-source="tableData"
        :pagination="{ pageSize: 10, size: 'small', showTotal: (t: number) => `共 ${t} 条` }"
        size="small"
        :scroll="{ x: 'max-content' }"
        bordered
      />
    </div>

    <!-- G2 图表区域 -->
    <div v-if="chartConfig" class="chart-area">
      <div class="chart-header">
        <span>📈 {{ chartConfig.title || '数据可视化' }}</span>
        <a-button size="small" type="text" @click="exportChart">导出图片</a-button>
      </div>
      <div ref="chartRef" class="chart-container"></div>
    </div>

    <!-- 错误 -->
    <div v-if="error" class="sqlbot-error">
      <a-alert :message="error" type="error" show-icon />
    </div>

    <!-- Markdown 摘要（无表格时展示） -->
    <div v-if="answer && !records?.length" class="msg-bubble ai-bubble">
      <div class="msg-markdown" v-html="renderMarkdown(answer)"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { message as antMsg } from 'ant-design-vue'
import { renderMarkdown } from '../markdown'

interface ChartAxis {
  name: string
  value: string
}

interface ChartConfig {
  type: 'column' | 'bar' | 'line' | 'pie' | 'table'
  title?: string
  axis?: {
    x?: ChartAxis
    y?: ChartAxis
    series?: ChartAxis
  }
  columns?: Array<{ name: string; value: string }>
}

const props = defineProps<{
  answer?: string
  sql?: string
  records?: Record<string, any>[]
  total?: number
  stage?: string
  progressMessage?: string
  chartConfig?: ChartConfig
  error?: string
}>()

const chartRef = ref<HTMLElement>()
const s2Container = ref<HTMLElement>()
const useS2 = ref(false)
let g2Chart: any = null
let s2Table: any = null

// ── 表格列（a-table fallback） ──────────────────────────────────────────────
const tableColumns = computed(() => {
  if (!props.records?.length) return []
  const keys = Object.keys(props.records[0])
  return keys.map(k => ({
    title: k,
    dataIndex: k,
    key: k,
    ellipsis: true,
    width: 120,
  }))
})

const tableData = computed(() => {
  return (props.records || []).map((r, i) => ({ ...r, _rowKey: i }))
})

// ── AntV G2 图表渲染 ────────────────────────────────────────────────────────
async function renderG2Chart() {
  if (!chartRef.value || !props.chartConfig || !props.records?.length) return

  try {
    const { Chart } = await import('@antv/g2')

    // 销毁旧图表
    if (g2Chart) { g2Chart.destroy(); g2Chart = null }

    const cfg = props.chartConfig
    const data = props.records

    g2Chart = new Chart({
      container: chartRef.value,
      autoFit: true,
      padding: 'auto',
    })

    g2Chart.data(data)

    const xField = cfg.axis?.x?.value
    const yField = cfg.axis?.y?.value
    const seriesField = cfg.axis?.series?.value

    switch (cfg.type) {
      case 'column':
        g2Chart
          .interval()
          .position(`${xField}*${yField}`)
        if (seriesField) {
          g2Chart.color(seriesField).adjust('dodge')
        }
        break

      case 'bar':
        g2Chart.coordinate().transpose()
        g2Chart
          .interval()
          .position(`${xField}*${yField}`)
        if (seriesField) {
          g2Chart.color(seriesField).adjust('dodge')
        }
        break

      case 'line':
        g2Chart
          .line()
          .position(`${xField}*${yField}`)
        if (seriesField) {
          g2Chart.color(seriesField)
        }
        g2Chart.point().position(`${xField}*${yField}`).shape('circle')
        break

      case 'pie':
        g2Chart.coordinate('theta', { radius: 0.75 })
        g2Chart
          .interval()
          .position(`${yField}`)
          .color(xField || 'type')
          .adjust('stack')
          .label(xField || 'type', { layout: { type: 'limit-in-plot', cfg: { action: 'ellipsis' } } })
        g2Chart.legend({ position: 'right' })
        break

      default:
        // fallback: column
        g2Chart.interval().position(`${xField}*${yField}`)
    }

    if (cfg.title) {
      g2Chart.annotation().text({
        position: ['50%', '0%'],
        content: cfg.title,
        style: { fontSize: 14, fontWeight: 600, fill: '#1a1a1a', textAlign: 'center' },
        offsetY: -8,
      })
    }

    g2Chart.interaction('active-region')
    g2Chart.render()
  } catch (e) {
    console.error('G2 图表渲染失败:', e)
  }
}

// ── AntV S2 表格渲染 ────────────────────────────────────────────────────────
async function renderS2Table() {
  if (!s2Container.value || !props.records?.length) return

  try {
    const { TableSheet } = await import('@antv/s2')

    if (s2Table) { s2Table.destroy(); s2Table = null }

    const columns = Object.keys(props.records[0])
    const s2DataConfig = {
      fields: { columns },
      meta: columns.map(col => ({ field: col, name: col })),
      data: props.records,
    }
    const s2Options = {
      width: s2Container.value.clientWidth || 600,
      height: Math.min(400, 32 * props.records.length + 60),
      style: {
        cellCfg: { height: 28 },
        colCfg: { height: 32 },
      },
      interaction: {
        enableCopy: true,
      },
    } as any

    s2Table = new TableSheet(s2Container.value, s2DataConfig, s2Options)
    s2Table.render()
  } catch (e) {
    console.error('S2 表格渲染失败:', e)
    useS2.value = false
  }
}

function toggleTableView() {
  useS2.value = !useS2.value
}

function exportChart() {
  if (g2Chart) {
    try {
      g2Chart.downloadImage('chart', 'image/png')
      antMsg.success('图表已导出')
    } catch {
      antMsg.error('导出失败')
    }
  }
}

async function copySql() {
  if (props.sql) {
    await navigator.clipboard.writeText(props.sql)
    antMsg.success('SQL 已复制')
  }
}

// 监听数据和配置变化重新渲染
watch(() => [props.chartConfig, props.records], () => {
  nextTick(() => {
    if (props.chartConfig) renderG2Chart()
  })
}, { deep: true })

watch(useS2, (val) => {
  if (val) nextTick(() => renderS2Table())
})

onMounted(() => {
  if (props.chartConfig && props.records?.length) {
    nextTick(() => renderG2Chart())
  }
})

onBeforeUnmount(() => {
  if (g2Chart) { g2Chart.destroy(); g2Chart = null }
  if (s2Table) { s2Table.destroy(); s2Table = null }
})
</script>

<style scoped lang="less">
.sqlbot-renderer { display: flex; flex-direction: column; gap: 12px; }
.sqlbot-progress { display: flex; align-items: center; gap: 8px; padding: 8px 0; color: #666; font-size: 13px; }
.sql-block { border: 1px solid #e8e8e8; border-radius: 6px; overflow: hidden; }
.sql-header { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; background: #fafafa; border-bottom: 1px solid #f0f0f0; }
.sql-label { font-size: 12px; font-weight: 600; color: #555; }
.sql-code { margin: 0; padding: 12px; font-size: 12px; background: #f8f9fa; overflow-x: auto; code { font-family: 'Fira Code', monospace; } }
.data-table-wrap { border: 1px solid #e8e8e8; border-radius: 6px; overflow: hidden; }
.table-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #fafafa; border-bottom: 1px solid #f0f0f0; }
.table-label { font-size: 12px; font-weight: 600; color: #555; }
.s2-container { min-height: 200px; max-height: 400px; overflow: auto; padding: 4px; }
.chart-area { border: 1px solid #e8e8e8; border-radius: 6px; padding: 12px; }
.chart-header { display: flex; align-items: center; justify-content: space-between; font-size: 12px; font-weight: 600; color: #555; margin-bottom: 8px; }
.chart-container { min-height: 280px; }
.sqlbot-error { margin-top: 8px; }
</style>
