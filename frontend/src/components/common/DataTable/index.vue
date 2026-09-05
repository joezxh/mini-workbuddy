<template>
  <div ref="dtWrapper" class="d-table">
    <!-- 顶部 header 插槽 -->
    <div v-if="headerVisible" class="header-bar">
      <slot name="header" />
    </div>

    <!-- 表格区域 -->
    <div class="d-table__list-content">
      <slot name="list-left" />

      <div class="table-area">
        <a-table
          :columns="tableColumns"
          :data-source="dataSource"
          :loading="loading"
          :row-key="rowKey"
          :size="size"
          :scroll="computedScroll"
          :pagination="false"
          :show-header="showHeader"
          :custom-row="buildCustomRow"
        >
          <template #bodyCell="{ column, record, index }">
            <slot name="bodyCell" :column="column" :record="record" :index="index">
              <template v-if="column.key === 'no'">
                {{ index + 1 + (innerPage - 1) * innerPageSize }}
              </template>
              <template v-else>
                {{ record[column.dataIndex] }}
              </template>
            </slot>
          </template>
        </a-table>
      </div>

      <slot name="list-right" />
    </div>

    <!-- 底部分页 -->
    <div v-if="pageVisible" class="page-info">
      <!-- 自定义列 -->
      <CustomTableColumn
        v-if="showColumn"
        :fields="columnListWithIds"
        class="table-column-btn"
        @changeColumns="applyColumns"
      />

      <div v-if="showPageSize" class="s-table__page">
        <a-pagination
          v-model:current="innerPage"
          v-model:page-size="innerPageSize"
          :total="total"
          :show-size-changer="showSizeChanger"
          :page-size-options="pageSizeOptions"
          :show-quick-jumper="showPagelevator"
          @change="onPageChange"
          @show-size-change="onPageSizeChange"
        />
        <span class="all-last-page">
          共 <span class="num-size">{{ sizeTotals }}</span> 页
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import CustomTableColumn from './cell/customTableColumn.vue'

// ─── 接口定义 ───────────────────────────────────────
interface ColumnItem {
  id?: string
  title: string
  dataIndex?: string
  key?: string
  width?: number | string
  align?: 'left' | 'center' | 'right'
  ellipsis?: boolean
  checked?: boolean
  [key: string]: any
}

interface PaginationConfig {
  current: number
  pageSize: number
  total: number
  showSizeChanger?: boolean
  showTotal?: (total: number) => string
}

// ─── Props ───────────────────────────────────────────
interface Props {
  // 数据
  columns?: ColumnItem[]        // Ant Design 风格列配置
  column?: ColumnItem[]         // iView 风格列配置（兼容）
  dataSource?: any[]            // Ant Design 风格数据
  list?: any[]                  // iView 风格数据（兼容）

  // 分页
  pagination?: PaginationConfig // Ant Design 风格分页（兼容旧版）
  total?: number                // 总条数
  currentPage?: number          // 当前页
  pageSize?: number             // 每页条数
  pageVisible?: boolean         // 是否显示分页
  showPageSize?: boolean        // 是否显示页码选择
  showPagelevator?: boolean     // 是否显示跳页
  showSizeChanger?: boolean     // 是否显示每页条数切换

  // 状态
  loading?: boolean
  isLoading?: boolean           // 兼容 iView 版本

  // 布局
  size?: 'small' | 'middle' | 'large'
  scroll?: { x?: number | string; y?: number | string }
  rowKey?: string | ((record: any) => string)
  headerVisible?: boolean       // 是否显示顶部 header 插槽
  showHeader?: boolean          // 是否显示表头
  showColumn?: boolean          // 是否显示自定义列
  customHeight?: number | string
  customMaxHeight?: number | string
  emptySpace?: number           // 底部留白
}

const props = withDefaults(defineProps<Props>(), {
  columns: () => [],
  column: () => [],
  dataSource: () => [],
  list: () => [],
  total: 0,
  currentPage: 1,
  pageSize: 10,
  pageVisible: true,
  showPageSize: true,
  showPagelevator: true,
  showSizeChanger: true,
  loading: false,
  isLoading: false,
  size: 'small',
  rowKey: 'id',
  headerVisible: false,
  showHeader: true,
  showColumn: false,
  emptySpace: 0,
})

const emit = defineEmits<{
  'change': [pagination: PaginationConfig]
  'on-page-change': [page: number]
  'on-page-size-change': [size: number]
  'row-click': [record: any, index: number]
  'on-row-click': [record: any]
  'row-dblclick': [record: any, index: number]
  'on-row-dblclick': [record: any]
}>()

// ─── 分页状态 ─────────────────────────────────────────
const innerPage = ref(props.pagination?.current ?? props.currentPage)
const innerPageSize = ref(props.pagination?.pageSize ?? props.pageSize)
const pageSizeOptions = ['10', '20', '30', '50']

// 同步外部分页变化
watch(() => props.pagination, (val) => {
  if (val) {
    innerPage.value = val.current
    innerPageSize.value = val.pageSize
  }
}, { immediate: true })

watch(() => props.currentPage, (val) => { innerPage.value = val })
watch(() => props.pageSize,    (val) => { innerPageSize.value = val })

// 总条数（兼容两种传入方式）
const total = computed(() => props.pagination?.total ?? props.total)

// 总页数
const sizeTotals = computed(() => {
  if (!total.value || !innerPageSize.value) return 0
  return Math.ceil(total.value / innerPageSize.value)
})

// ─── 列配置 ───────────────────────────────────────────
// 优先使用 columns（Ant Design 风格），兼容 column（iView 风格）
const rawColumns = computed<ColumnItem[]>(() =>
  (props.columns?.length ? props.columns : props.column) ?? []
)

const columnList = ref<ColumnItem[]>([])
const tableColumns = ref<ColumnItem[]>([])

watch(rawColumns, (cols) => {
  columnList.value = cols.map((item) => ({
    ...item,
    id: item.id ?? `col_${item.key ?? item.dataIndex ?? Math.random()}`,
    checked: item.checked !== false,
  })) as ColumnItem[]
  applyColumns()
}, { immediate: true, deep: true })

function applyColumns() {
  tableColumns.value = columnList.value.filter(c => c.checked !== false)
}

// 确保 id 和 checked 字段总是有值的计算属性
const columnListWithIds = computed(() =>
  columnList.value.map(item => ({
    ...item,
    id: item.id || `col_${item.key || item.dataIndex || Math.random()}`,
    checked: item.checked !== false
  }))
)

// ─── 数据源（兼容 list / dataSource）─────────────────
const dataSource = computed<any[]>(() =>
  props.dataSource?.length ? props.dataSource : (props.list ?? [])
)

// ─── 高度自适应 ────────────────────────────────────────
const dtWrapper = ref<HTMLElement>()
const tableBodyHeight = ref<number>(400)
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let ro: ResizeObserver | null = null

const computedScroll = computed(() => {
  if (props.customHeight || props.customMaxHeight) {
    return props.scroll ?? {}
  }
  return {
    ...(props.scroll ?? {}),
    y: tableBodyHeight.value,
  }
})

function calcHeight() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    nextTick(() => {
      if (!dtWrapper.value) return
      const rect = dtWrapper.value.getBoundingClientRect()
      const headerH = props.headerVisible
        ? (dtWrapper.value.querySelector('.header-bar')?.getBoundingClientRect().height ?? 0)
        : 0
      const pageH = props.pageVisible ? 56 : 0
      const h = window.innerHeight - rect.top - pageH - headerH - (+props.emptySpace) - 2
      tableBodyHeight.value = Math.max(120, h)
    })
  }, 100)
}

onMounted(() => {
  if (!props.customHeight && !props.customMaxHeight) {
    calcHeight()
    window.addEventListener('resize', calcHeight)
    if (dtWrapper.value) {
      ro = new ResizeObserver(calcHeight)
      ro.observe(dtWrapper.value)
    }
  } else {
    // 固定高度模式
    const y = props.customHeight ?? props.customMaxHeight
    tableBodyHeight.value = Number(y) || 400
  }
})

onBeforeUnmount(() => {
  if (resizeTimer) clearTimeout(resizeTimer)
  window.removeEventListener('resize', calcHeight)
  ro?.disconnect()
})

// ─── 行事件 ────────────────────────────────────────────
const buildCustomRow = (record: any, index: number) => ({
  onClick: () => {
    emit('row-click', record, index)
    emit('on-row-click', record)
  },
  onDblclick: () => {
    emit('row-dblclick', record, index)
    emit('on-row-dblclick', record)
  },
})

// ─── 分页事件 ──────────────────────────────────────────
function onPageChange(page: number, pageSize: number) {
  innerPage.value = page
  innerPageSize.value = pageSize
  emit('change', { current: page, pageSize, total: total.value })
  emit('on-page-change', page)
}

function onPageSizeChange(_current: number, size: number) {
  innerPage.value = 1
  innerPageSize.value = size
  emit('change', { current: 1, pageSize: size, total: total.value })
  emit('on-page-size-change', size)
}
</script>

<style lang="less" scoped>
.d-table {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .header-bar {
    flex-shrink: 0;
    padding: 0 0 6px;
  }

  // 表格主体区域
  .d-table__list-content {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;

    .table-area {
      flex: 1;
      min-height: 0;
      overflow: hidden;
      display: flex;
      flex-direction: column;

      :deep(.ant-table-wrapper),
      :deep(.ant-spin-nested-loading),
      :deep(.ant-spin-container) {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
      }

      :deep(.ant-table) {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: transparent;
      }

      :deep(.ant-table-container) {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      :deep(.ant-table-header) {
        flex-shrink: 0;
      }

      :deep(.ant-table-body) {
        flex: 1;
        min-height: 0;
        max-height: none !important;
        overflow-y: auto !important;
        overflow-x: auto;
      }

      :deep(.ant-table-thead > tr > th) {
        background: transparent;
        font-weight: 600;
        color: #333;
      }

      :deep(.ant-table:not(.ant-table-bordered) .ant-table-tbody > tr > td) {
        border-top: 1px solid #c8dfff;
      }

      :deep(.ant-table-tbody > tr:hover > td) {
        background: rgba(24, 144, 255, 0.05) !important;
      }

      :deep(.ant-table-wrapper .ant-table-cell-fix-left),
      :deep(.ant-table-wrapper .ant-table-cell-fix-right) {
        background: transparent;
      }
    }
  }

  // 分页区域
  .page-info {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 10px 10px 0 10px;
    border-top: 1px solid var(--border-glow) !important;

    .table-column-btn {
      position: absolute;
      left: 0;
    }

    .s-table__page {
      display: flex;
      align-items: center;

      :deep(.ant-pagination) {
        display: flex;
        align-items: center;
        margin: 0;
      }

      :deep(.ant-pagination-item-active) {
        background: #d2e5ff !important;
        border-color: #a0bbe1 !important;

        a {
          color: #333 !important;
        }
      }

      .all-last-page {
        font-size: 14px;
        color: rgba(0, 0, 0, 0.65);
        white-space: nowrap;
        padding-right: 5px;
        .num-size {
          margin: 0 2px;
        }
      }
    }
  }

  // ====== ant-table 主题（仅当前组件） ======
  :deep(.ant-table) {
    background: transparent !important;
    color: var(--text-primary) !important;
    border-radius: 0px !important;
    overflow: hidden;
    border: 0px solid var(--border-glow);
  }

  :deep(.ant-table-thead > tr > th) {
    background: rgba(24, 144, 255, 0.10) !important;
    color: #333 !important;
    border-bottom: 1px solid var(--border-glow) !important;
    font-weight: 600;
  }

  :deep(.ant-table-tbody > tr) {
    background: transparent !important;
    transition: all 0.3s;
    border-bottom: 1px solid rgba(0, 100, 200, 0.08) !important;
  }

  :deep(.ant-table-tbody > tr:hover > td) {
    background: transparent !important;
  }

  :deep(.ant-table-tbody > tr > td) {
    border-bottom: 1px solid rgba(0, 100, 200, 0.08) !important;
    color: var(--text-primary) !important;
  }

  :deep(.ant-table-wrapper .ant-table-tbody > tr > td.ant-table-cell-row-hover) {
    background: transparent !important;
  }

  :deep(.ant-table-wrapper .ant-table-thead > tr > th:not(:last-child):not(.ant-table-selection-column):not(.ant-table-row-expand-icon-cell):not([colspan])::before),
  :deep(.ant-table-wrapper .ant-table-thead > tr > td:not(:last-child):not(.ant-table-selection-column):not(.ant-table-row-expand-icon-cell):not([colspan])::before) {
    width: 0;
  }

  :deep(.ant-table-wrapper .ant-table-cell-scrollbar:not([rowspan])) {
    box-shadow: 0 0px 0 0px #a8ceec !important;
  }

  :deep(.ant-table-empty .ant-table-tbody > tr > td) {
    border-bottom: 1px solid transparent !important;
  }

  // ====== ant-pagination 主题（仅当前组件） ======
  :deep(.ant-pagination) {
    color: var(--text-primary) !important;
  }

  :deep(.ant-pagination-item) {
    border-radius: 4px !important;
    border-color: rgba(0, 0, 0, 0.15) !important;
  }

  :deep(.ant-pagination-item a) {
    color: var(--text-primary) !important;
  }

  :deep(.ant-pagination-item-active) {
    background: var(--accent-cyan) !important;
    border-color: var(--accent-cyan) !important;
  }

  :deep(.ant-pagination-item-active a) {
    color: white !important;
  }

  :deep(.ant-pagination .ant-pagination-options) {
    display: flex !important;
    align-items: center !important;
  }

  :deep(.ant-pagination .ant-pagination-options-quick-jumper input) {
    background: transparent !important;
    height: 28px !important;
    border: 1px solid #a4cdf8 !important;
  }
}

// 滚动条
:deep(::-webkit-scrollbar) {
  width: 6px;
  height: 6px;
}
:deep(::-webkit-scrollbar-thumb) {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}
</style>
