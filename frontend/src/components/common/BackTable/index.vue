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
          :loading="isTableLoading"
          :row-key="rowKey"
          :size="size"
          :scroll="computedScroll"
          :pagination="false"
          :bordered="border"
          :show-header="header"
          :custom-row="buildCustomRow"
        >
          <template #bodyCell="slotProps">
            <!-- 单选框列 -->
            <template v-if="slotProps.column.key === '__radio__'">
              <a-radio
                :checked="radioKey === slotProps.record[rowKey as string]"
                @change="radioHandle(slotProps.record)"
              />
            </template>

            <!-- 复选框列 -->
            <template v-else-if="slotProps.column.key === '__selectionD__'">
              <a-checkbox
                :checked="checkKeys.includes(slotProps.record[rowKey as string])"
                @change="(e: any) => checkHandle(slotProps.record, e.target.checked)"
              />
            </template>

            <!-- 自定义列插槽透传 -->
            <template v-else>
              <slot
                :name="slotProps.column.key || slotProps.column.dataIndex"
                :row="slotProps.record"
                :record="slotProps.record"
                :column="slotProps.column"
                :index="slotProps.index"
                :text="slotProps.text"
              >
                {{ slotProps.text }}
              </slot>
            </template>
          </template>
        </a-table>
      </div>

      <slot name="list-right" />
    </div>

    <!-- 底部分页 -->
    <div v-if="pageVisible" class="page-info">
      <!-- 自定义列筛选 -->
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
          :total="totalCount"
          :show-size-changer="showPageSize"
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
  title?: string
  dataIndex?: string
  key?: string
  width?: number | string
  align?: 'left' | 'center' | 'right'
  ellipsis?: boolean
  checked?: boolean
  fixed?: string | boolean
  slot?: string
  type?: string
  [k: string]: any
}

// ─── Props ───────────────────────────────────────────
interface Props {
  rowKey?: string
  column?: ColumnItem[]
  list?: any[]
  isLoading?: boolean
  total?: number
  pageSize?: number
  currentPage?: number
  pageVisible?: boolean
  showColumn?: boolean
  border?: boolean
  isMultiple?: boolean
  checkBox?: boolean
  checkKeys?: Array<string | number>
  radioKey?: string | number
  emptySpace?: number | string
  customHeight?: string | number
  customMaxHeight?: string | number
  headerVisible?: boolean
  header?: boolean
  showPageSize?: boolean
  showPagelevator?: boolean
  size?: 'small' | 'middle' | 'large'
  spanMethod?: Function | null
}

const props = withDefaults(defineProps<Props>(), {
  rowKey: 'id',
  column: () => [],
  list: () => [],
  isLoading: false,
  total: 0,
  pageSize: 10,
  currentPage: 1,
  pageVisible: true,
  showColumn: true,
  border: false,
  isMultiple: true,
  checkBox: false,
  checkKeys: () => [],
  radioKey: '',
  emptySpace: 0,
  customHeight: '',
  customMaxHeight: '',
  headerVisible: false,
  header: true,
  showPageSize: true,
  showPagelevator: true,
  size: 'small',
  spanMethod: null,
})

const emit = defineEmits<{
  'on-page-change': [page: number]
  'on-page-size-change': [size: number]
  'on-row-click': [record: any]
  'on-row-dblclick': [record: any]
  'on-selection-change': [rows: any[]]
  'on-selection-current': [row: any]
  'on-expand-tree': [row: any, status: boolean]
  'on-filter-change': [cell: any]
  'on-sort-change': [columns: any, key: string, order: string]
  'radioSelect': [key: string | number, row: any]
  'selectChange': [keys: Array<string | number>, rows: any[], row?: any, added?: boolean]
}>()

// ─── 加载状态 ────────────────────────────────────────
const isTableLoading = computed(() => props.isLoading)

// ─── 分页 ────────────────────────────────────────────
const innerPage = ref(props.currentPage)
const innerPageSize = ref(props.pageSize)
const pageSizeOptions = ['10', '20', '30', '50', '100']

watch(() => props.currentPage, (val) => { innerPage.value = val })
watch(() => props.pageSize, (val) => { innerPageSize.value = val })

const totalCount = computed(() => props.total)
const sizeTotals = computed(() => {
  if (!totalCount.value || !innerPageSize.value) return 0
  return Math.ceil(totalCount.value / innerPageSize.value)
})

function onPageChange(page: number, _pageSize: number) {
  innerPage.value = page
  emit('on-page-change', page)
}

function onPageSizeChange(_current: number, size: number) {
  innerPage.value = 1
  innerPageSize.value = size
  emit('on-page-size-change', size)
}

// ─── 列配置 ──────────────────────────────────────────
const columnList = ref<ColumnItem[]>([])
const tableColumns = ref<ColumnItem[]>([])

const rawColumns = computed<ColumnItem[]>(() => {
  const cols: ColumnItem[] = [...(props.column ?? [])]
  // 如果开启了复选框，在最前面插入复选列
  if (props.checkBox) {
    cols.unshift({
      key: '__selectionD__',
      title: '',
      width: 50,
      align: 'center',
      checked: true,
    })
  }
  return cols
})

watch(rawColumns, (cols) => {
  columnList.value = cols.map((item) => ({
    ...item,
    id: item.id ?? `col_${item.key ?? item.dataIndex ?? Math.random()}`,
    checked: item.checked !== false,
  }))
  applyColumns()
}, { immediate: true, deep: true })

function applyColumns() {
  tableColumns.value = columnList.value.filter(c => c.checked !== false)
}

const columnListWithIds = computed(() =>
  columnList.value.map(item => ({
    ...item,
    id: item.id || `col_${item.key || item.dataIndex || Math.random()}`,
    title: item.title || '',
    checked: item.checked !== false,
  })) as Array<{ id: string; title: string; checked: boolean; type?: string; slot?: string }>
)

// ─── 数据源 ──────────────────────────────────────────
const dataSource = computed<any[]>(() => props.list ?? [])

// ─── 高度自适应 ──────────────────────────────────────
const dtWrapper = ref<HTMLElement>()
const tableBodyHeight = ref<number>(400)
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let ro: ResizeObserver | null = null

const computedScroll = computed(() => {
  if (props.customHeight || props.customMaxHeight) {
    const y = Number(props.customHeight) || Number(props.customMaxHeight) || undefined
    return y ? { y } : {}
  }
  return { y: tableBodyHeight.value }
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
      const h = window.innerHeight - rect.top - pageH - headerH - Number(props.emptySpace || 0) - 2
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
    const y = Number(props.customHeight) || Number(props.customMaxHeight) || 400
    tableBodyHeight.value = y
  }
})

onBeforeUnmount(() => {
  if (resizeTimer) clearTimeout(resizeTimer)
  window.removeEventListener('resize', calcHeight)
  ro?.disconnect()
})

// ─── 行事件 ──────────────────────────────────────────
const buildCustomRow = (record: any, _index: number) => ({
  onClick: () => {
    emit('on-row-click', record)
  },
  onDblclick: () => {
    emit('on-row-dblclick', record)
  },
})

// ─── 单选 ────────────────────────────────────────────
function radioHandle(row: any) {
  emit('radioSelect', row[props.rowKey as string], row)
}

// ─── 多选 ────────────────────────────────────────────
function checkHandle(row: any, checked: boolean) {
  if (checked) {
    const newKeys = [...props.checkKeys, row[props.rowKey as string]]
    emit('selectChange', newKeys, [], row, true)
  } else {
    const newKeys = props.checkKeys.filter(k => k !== row[props.rowKey as string])
    emit('selectChange', newKeys, [], row, false)
  }
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
        // background: transparent;
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
        // background: transparent;
        font-weight: 600;
        color: #333;
      }

      :deep(.ant-table:not(.ant-table-bordered) .ant-table-tbody > tr > td) {
        border-top: 1px solid #c8dfff;
      }

      :deep(.ant-table-tbody > tr:hover > td) {
        // background: rgba(24, 144, 255, 0.05) !important;
      }

      :deep(.ant-table-wrapper .ant-table-cell-fix-left),
      :deep(.ant-table-wrapper .ant-table-cell-fix-right) {
        // background: transparent;
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
