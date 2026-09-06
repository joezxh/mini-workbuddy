<template>
  <div class="package-panel">
    <div class="panel-header">
      <h2>{{ t('sys.package.title') }}</h2>
      <p class="description">{{ t('sys.package.subtitle') }}</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline">
        <a-form-item :label="t('sys.package.labelName')">
          <a-input v-model:value="queryParams.name" :placeholder="t('sys.package.placeholderName')" allow-clear style="width: 160px" />
        </a-form-item>
        <a-form-item :label="t('sys.package.labelStatus')">
          <a-select v-model:value="queryParams.status" :placeholder="t('sys.package.placeholderStatus')" allow-clear style="width: 120px">
            <a-select-option value="active">{{ t('sys.package.statusActive') }}</a-select-option>
            <a-select-option value="disabled">{{ t('sys.package.statusDisabled') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleQuery">
            <template #icon><SearchOutlined /></template>
            {{ t('sys.package.search') }}
          </a-button>
          <a-button style="margin-left: 8px" @click="resetQuery">{{ t('sys.package.reset') }}</a-button>
          <a-button type="primary" style="margin-left: 8px" @click="openForm('create')">
            <template #icon><PlusOutlined /></template>
            {{ t('sys.package.add') }}
          </a-button>
          <a-popconfirm :title="t('sys.package.batchDeleteConfirm')" @confirm="handleBatchDelete" :disabled="selectedRowKeys.length === 0">
            <a-button type="primary" danger style="margin-left: 8px" :disabled="selectedRowKeys.length === 0">
              <template #icon><DeleteOutlined /></template>
              {{ t('sys.package.batchDelete') }}
            </a-button>
          </a-popconfirm>
        </a-form-item>
      </a-form>
    </div>

    <!-- 数据表格 -->
    <a-table
      :columns="columns"
      :data-source="tableData"
      :loading="loading"
      :pagination="tablePagination"
      :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
      row-key="package_id"
      size="middle"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'red'">
            {{ record.status === 'active' ? t('sys.package.statusActive') : t('sys.package.statusDisabled') }}
          </a-tag>
        </template>
        <template v-if="column.key === 'menu_ids'">
          <a-tag v-if="record.menu_ids && record.menu_ids.length" color="blue">
            {{ t('sys.package.menuCount', { count: record.menu_ids.length }) }}
          </a-tag>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openForm('view', record)">{{ t('sys.package.view') }}</a>
            <a @click="openForm('update', record)">{{ t('sys.package.edit') }}</a>
            <a-popconfirm :title="t('sys.package.deleteConfirm')" @confirm="handleDelete(record.package_id)">
              <a style="color: var(--err)">{{ t('sys.package.delete') }}</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑/查看弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      :confirm-loading="submitLoading"
      @ok="handleSubmit"
      :ok-text="formMode === 'view' ? undefined : t('sys.package.confirm')"
      :cancel-text="t('sys.package.close')"
      :footer="formMode === 'view' ? undefined : undefined"
      width="640px"
    >
      <!-- 查看模式：隐藏确定按钮 -->
      <template v-if="formMode === 'view'" #footer>
        <a-button @click="modalVisible = false">{{ t('sys.package.close') }}</a-button>
      </template>
      <a-spin :spinning="menuLoading">
      <a-form :model="formData" :label-col="{ span: 5 }" :wrapper-col="{ span: 17 }">
        <a-form-item :label="t('sys.package.labelName')" required>
          <a-input v-model:value="formData.name" :placeholder="t('sys.package.inputName')" :disabled="formMode === 'view'" />
        </a-form-item>
        <a-form-item :label="t('sys.package.labelFormStatus')">
          <a-radio-group v-model:value="formData.status" :disabled="formMode === 'view'">
            <a-radio value="active">{{ t('sys.package.statusActive') }}</a-radio>
            <a-radio value="disabled">{{ t('sys.package.statusDisabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('sys.package.labelRemark')">
          <a-textarea v-model:value="formData.remark" :placeholder="t('sys.package.placeholderRemark')" :rows="2" :disabled="formMode === 'view'" />
        </a-form-item>
        <a-form-item :label="t('sys.package.labelMenuPerm')">
          <div class="menu-tree-container">
            <div v-if="formMode !== 'view'" class="tree-toolbar">
              <span>{{ t('sys.package.selectAllLabel') }}</span>
              <a-switch v-model:checked="treeNodeAll" :checked-children="t('sys.package.yes')" :un-checked-children="t('sys.package.no')" size="small" @change="handleCheckAll" />
              <span style="margin-left: 12px">{{ t('sys.package.expandLabel') }}</span>
              <a-switch v-model:checked="treeExpandAll" :checked-children="t('sys.package.expand')" :un-checked-children="t('sys.package.collapse')" size="small" @change="handleExpandAll" />
            </div>
            <a-tree
              v-model:checkedKeys="checkedMenuIds"
              v-model:expandedKeys="expandedMenuIds"
              :tree-data="menuTreeData"
              checkable
              :disabled="formMode === 'view'"
              :field-names="{ key: 'id', title: 'name', children: 'children' }"
              :default-expand-all="formMode === 'view'"
              class="perm-tree"
              @check="onTreeCheck"
            >
              <template #title="{ name, type }">
                <span class="tree-node">
                  <span class="node-title">{{ name }}</span>
                  <a-tag v-if="type" size="small" :color="permTypeColor(type)" style="margin-left:6px">{{ permTypeName(type) }}</a-tag>
                </span>
              </template>
            </a-tree>
            <a-empty v-if="menuTreeData.length === 0" :description="t('sys.package.noMenuData')" />
          </div>
        </a-form-item>
      </a-form>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import {
  getPackagePage, getPackage, createPackage, updatePackage, deletePackage, deletePackageList,
  type TenantPackageVO,
} from '@/api/tenant'
import { getMenuFlatList } from '@/api/admin'

const { t } = useI18n()

defineOptions({ name: 'TenantPackagePanel' })

// ── 查询参数 ──────────────────────────────────────────────────────
const queryParams = reactive({
  name: '',
  status: undefined as string | undefined,
})

const loading = ref(false)
const tableData = ref<any[]>([])
const selectedRowKeys = ref<number[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})
const tablePagination = computed(() => ({
  ...pagination,
  showTotal: (total: number) => t('common.total', { total })
}))

const columns = computed(() => [
  { title: t('sys.package.colId'), dataIndex: 'package_id', key: 'package_id', width: 80 },
  { title: t('sys.package.colName'), dataIndex: 'name', key: 'name', width: 160 },
  { title: t('sys.package.colStatus'), key: 'status', width: 80 },
  { title: t('sys.package.colMenuPerm'), key: 'menu_ids', width: 120 },
  { title: t('sys.package.colRemark'), dataIndex: 'remark', key: 'remark', ellipsis: true },
  { title: t('sys.package.colCreatedAt'), dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: t('sys.package.colAction'), key: 'action', width: 150, fixed: 'right' as const },
])

// ── 弹窗 ──────────────────────────────────────────────────────────
const modalVisible = ref(false)
const modalTitle = ref('')
const formMode = ref<'create' | 'update' | 'view'>('create')
const submitLoading = ref(false)

const formData = reactive<TenantPackageVO>({
  name: '',
  status: 'active',
  remark: '',
  menu_ids: [],
})

// ── 菜单树 ────────────────────────────────────────────────────────
const menuTreeData = ref<any[]>([])
const checkedMenuIds = ref<number[]>([])
const expandedMenuIds = ref<number[]>([])
const treeNodeAll = ref(false)
const treeExpandAll = ref(false)
const menuLoading = ref(false)

/** 从后端加载全量菜单（扁平列表）并构建父子树 */
async function loadMenuTree() {
  menuLoading.value = true
  try {
    const res = await getMenuFlatList() as any
    const data = res?.data || res || []
    menuTreeData.value = buildTree(data)
  } catch { /* ignore */ }
  finally { menuLoading.value = false }
}

function buildTree(items: any[], parentId: number | null = null): any[] {
  const tree: any[] = []
  for (const item of items) {
    const rawPid = item.parentId ?? item.parent_id
    // 兼容顶级菜单 parent_id 为 0 或 null 的情况
    const isRoot = rawPid === null || rawPid === undefined || rawPid === 0
    const targetIsRoot = parentId === null || parentId === undefined || parentId === 0
    const pidMatch = rawPid === parentId || (isRoot && targetIsRoot)
    if (pidMatch) {
      const children = buildTree(items, item.id)
      const node: any = {
        id: item.id,
        name: item.name,
        type: item.type,
      }
      if (children.length) node.children = children
      tree.push(node)
    }
  }
  return tree
}

function handleCheckAll(checked: boolean) {
  if (checked) {
    // checkedKeys 只需叶子节点，父节点由树级联自动勾选
    checkedMenuIds.value = getLeafMenuIds(menuTreeData.value)
  } else {
    checkedMenuIds.value = []
  }
  // 同步到 formData.menu_ids（保存时需要完整 ID 列表）
  formData.menu_ids = checked ? getAllMenuIds(menuTreeData.value) : []
}

/** 树勾选变化回调：同步 checkedMenuIds（叶子）和 formData.menu_ids（全部） */
function onTreeCheck(checkedKeys: any) {
  const keys: number[] = Array.isArray(checkedKeys) ? checkedKeys : checkedKeys.checked
  // checkedKeys 保持为当前树返回的值（ant-design-vue 自行管理）
  checkedMenuIds.value = keys
  // formData.menu_ids 保存所有勾选的节点（含父+叶）
  formData.menu_ids = [...keys]
}

function getAllMenuIds(nodes: any[]): number[] {
  const ids: number[] = []
  for (const node of nodes) {
    ids.push(node.id)
    if (node.children) {
      ids.push(...getAllMenuIds(node.children))
    }
  }
  return ids
}

/** 获取树中所有叶子节点的 ID */
function getLeafMenuIds(nodes: any[]): number[] {
  const ids: number[] = []
  for (const node of nodes) {
    if (node.children && node.children.length > 0) {
      ids.push(...getLeafMenuIds(node.children))
    } else {
      ids.push(node.id)
    }
  }
  return ids
}

/** 收集树中所有节点 ID（用于构建 Set 做存在性校验） */
function collectAllIds(nodes: any[]): Set<number> {
  const ids = new Set<number>()
  for (const node of nodes) {
    ids.add(node.id)
    if (node.children) {
      for (const cid of collectAllIds(node.children)) ids.add(cid)
    }
  }
  return ids
}

/** 从给定 ID 列表中过滤出仅属于叶子节点的 ID（父节点由树级联自动勾选） */
function filterToLeafIds(ids: number[]): number[] {
  const leafSet = new Set(getLeafMenuIds(menuTreeData.value))
  return ids.filter(id => leafSet.has(id))
}

function handleExpandAll(expanded: boolean) {
  if (expanded) {
    expandedMenuIds.value = getAllMenuIds(menuTreeData.value)
  } else {
    expandedMenuIds.value = []
  }
}

function permTypeColor(type: number) {
  return type === 1 ? 'blue' : type === 2 ? 'green' : 'orange'
}

function permTypeName(type: number) {
  return type === 1 ? t('sys.package.typeDir') : type === 2 ? t('sys.package.typeMenu') : t('sys.package.typeBtn')
}

// ── 数据加载 ──────────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const res = await getPackagePage({
      ...queryParams,
      page_no: pagination.current,
      page_size: pagination.pageSize,
    }) as any
    const data = res?.data || res || {}
    tableData.value = data.list || []
    pagination.total = data.total || 0
  } catch {
    message.error(t('sys.package.loadFail'))
  } finally {
    loading.value = false
  }
}

function handleQuery() {
  pagination.current = 1
  loadData()
}

function resetQuery() {
  queryParams.name = ''
  queryParams.status = undefined
  handleQuery()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

function onSelectChange(keys: number[]) {
  selectedRowKeys.value = keys
}

// ── 表单操作 ──────────────────────────────────────────────────────
async function openForm(mode: 'create' | 'update' | 'view', record?: any) {
  formMode.value = mode
  modalTitle.value = mode === 'create' ? t('sys.package.addTitle') : mode === 'update' ? t('sys.package.editTitle') : t('sys.package.viewTitle')

  // 重置表单
  formData.name = ''
  formData.status = 'active'
  formData.remark = ''
  formData.menu_ids = []
  checkedMenuIds.value = []
  expandedMenuIds.value = []
  treeNodeAll.value = false
  treeExpandAll.value = false

  // 确保菜单树已加载
  if (menuTreeData.value.length === 0) {
    await loadMenuTree()
  }

  if ((mode === 'update' || mode === 'view') && record) {
    // 从后端获取套餐最新数据（含 menu_ids）
    try {
      const res = await getPackage(record.package_id) as any
      const pkg = res?.data || res || record
      formData.package_id = pkg.package_id
      formData.name = pkg.name
      formData.status = pkg.status
      formData.remark = pkg.remark || ''
      formData.menu_ids = pkg.menu_ids || []
      // checkedKeys 只需设置叶子节点 ID，父节点由树组件级联自动勾选
      checkedMenuIds.value = filterToLeafIds(pkg.menu_ids || [])
    } catch {
      message.error(t('sys.package.loadDetailFail'))
      // 回退使用列表行数据
      formData.package_id = record.package_id
      formData.name = record.name
      formData.status = record.status
      formData.remark = record.remark || ''
      checkedMenuIds.value = filterToLeafIds(record.menu_ids || [])
    }
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formData.name) {
    message.warning(t('sys.package.inputName'))
    return
  }
  submitLoading.value = true
  try {
    const data = { ...formData }
    if (formMode.value === 'create') {
      await createPackage(data)
      message.success(t('sys.package.createSuccess'))
    } else {
      await updatePackage(data)
      message.success(t('sys.package.updateSuccess'))
    }
    modalVisible.value = false
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('sys.package.opFail'))
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(packageId: number) {
  try {
    await deletePackage(packageId)
    message.success(t('sys.package.deleteSuccess'))
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('sys.package.deleteFail'))
  }
}

async function handleBatchDelete() {
  try {
    await deletePackageList(selectedRowKeys.value)
    message.success(t('sys.package.batchDeleteSuccess'))
    selectedRowKeys.value = []
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('sys.package.batchDeleteFail'))
  }
}

onMounted(() => {
  loadData()
  loadMenuTree()
})
</script>

<style scoped>
.package-panel {
  padding: 0;
}
.panel-header {
  margin-bottom: 16px;
}
.panel-header h2 {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
}
.panel-header .description {
  color: var(--fg-secondary);
  font-size: 13px;
  margin: 0;
}
.search-bar {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--bg-page);
  border-radius: 6px;
}
.menu-tree-container {
  width: 100%;
}
.tree-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

/* 菜单权限树样式 —— 复选框前置（左侧），与角色赋权保持一致 */
.perm-tree {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px;
}

/* 确保复选框在文字左侧（Ant Design 默认行为，此处显式加固） */
.perm-tree :deep(.ant-tree-checkbox) {
  order: -1;
  margin-inline-end: 4px;
  margin-inline-start: 0;
}

.perm-tree :deep(.ant-tree-node-content-wrapper) {
  display: inline-flex;
  align-items: center;
}

.tree-node {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.node-title {
  font-weight: 500;
}

/* 查看模式下禁用态样式 */
.perm-tree :deep(.ant-tree-disabled .ant-tree-checkbox-disabled) {
  opacity: 0.8;
}
</style>
