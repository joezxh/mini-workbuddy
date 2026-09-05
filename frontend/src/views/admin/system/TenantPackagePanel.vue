<template>
  <div class="package-panel">
    <div class="panel-header">
      <h2>租户套餐管理</h2>
      <p class="description">管理租户可用的菜单权限套餐，每个租户关联一个套餐</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline">
        <a-form-item label="套餐名">
          <a-input v-model:value="queryParams.name" placeholder="请输入套餐名" allow-clear style="width: 160px" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="queryParams.status" placeholder="请选择状态" allow-clear style="width: 120px">
            <a-select-option value="active">启用</a-select-option>
            <a-select-option value="disabled">禁用</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleQuery">
            <template #icon><SearchOutlined /></template>
            搜索
          </a-button>
          <a-button style="margin-left: 8px" @click="resetQuery">重置</a-button>
          <a-button type="primary" style="margin-left: 8px" @click="openForm('create')">
            <template #icon><PlusOutlined /></template>
            新增
          </a-button>
          <a-popconfirm title="确认批量删除选中的套餐吗？" @confirm="handleBatchDelete" :disabled="selectedRowKeys.length === 0">
            <a-button type="primary" danger style="margin-left: 8px" :disabled="selectedRowKeys.length === 0">
              <template #icon><DeleteOutlined /></template>
              批量删除
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
      :pagination="pagination"
      :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
      row-key="package_id"
      size="middle"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'red'">
            {{ record.status === 'active' ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'menu_ids'">
          <a-tag v-if="record.menu_ids && record.menu_ids.length" color="blue">
            {{ record.menu_ids.length }} 个菜单
          </a-tag>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openForm('update', record)">编辑</a>
            <a-popconfirm title="确认删除该套餐吗？" @confirm="handleDelete(record.package_id)">
              <a style="color: #ff4d4f">删除</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      :confirm-loading="submitLoading"
      @ok="handleSubmit"
      width="640px"
    >
      <a-form :model="formData" :label-col="{ span: 5 }" :wrapper-col="{ span: 17 }">
        <a-form-item label="套餐名" required>
          <a-input v-model:value="formData.name" placeholder="请输入套餐名" />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="formData.status">
            <a-radio value="active">启用</a-radio>
            <a-radio value="disabled">禁用</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="formData.remark" placeholder="请输入备注" :rows="2" />
        </a-form-item>
        <a-form-item label="菜单权限">
          <div class="menu-tree-container">
            <div class="tree-toolbar">
              <span>全选/全不选：</span>
              <a-switch v-model:checked="treeNodeAll" checked-children="是" un-checked-children="否" size="small" @change="handleCheckAll" />
              <span style="margin-left: 12px">展开/折叠：</span>
              <a-switch v-model:checked="treeExpandAll" checked-children="展开" un-checked-children="折叠" size="small" @change="handleExpandAll" />
            </div>
            <a-tree
              v-model:checkedKeys="checkedMenuIds"
              v-model:expandedKeys="expandedMenuIds"
              :tree-data="menuTreeData"
              checkable
              :field-names="{ key: 'id', title: 'name', children: 'children' }"
              style="max-height: 300px; overflow-y: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 8px;"
            />
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { SearchOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import {
  getPackagePage, createPackage, updatePackage, deletePackage, deletePackageList,
  type TenantPackageVO,
} from '@/api/tenant'
import request from '@/utils/request'

defineOptions({ name: 'TenantPackagePanel' })

// ── 查询参数 ──────────────────────────────────────────────────────
const queryParams = reactive({
  name: '',
  status: undefined as string | undefined,
})

const loading = ref(false)
const tableData = ref<any[]>([])
const selectedRowKeys = ref<number[]>([])
const pagination = reactive({ current: 1, pageSize: 10, total: 0 })

const columns = [
  { title: '套餐编号', dataIndex: 'package_id', key: 'package_id', width: 80 },
  { title: '套餐名', dataIndex: 'name', key: 'name', width: 160 },
  { title: '状态', key: 'status', width: 80 },
  { title: '菜单权限', key: 'menu_ids', width: 120 },
  { title: '备注', dataIndex: 'remark', key: 'remark', ellipsis: true },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 120, fixed: 'right' as const },
]

// ── 弹窗 ──────────────────────────────────────────────────────────
const modalVisible = ref(false)
const modalTitle = ref('')
const formType = ref<'create' | 'update'>('create')
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

async function loadMenuTree() {
  try {
    const res = await request.get('/api/v1/admin/menus/simple') as any
    const data = res?.data || res || []
    menuTreeData.value = buildTree(data)
  } catch { /* ignore */ }
}

function buildTree(items: any[], parentId: number | null = null): any[] {
  const tree: any[] = []
  for (const item of items) {
    const pid = item.parentId ?? item.parent_id
    if (pid === parentId) {
      const children = buildTree(items, item.id)
      const node: any = { id: item.id, name: item.name }
      if (children.length) node.children = children
      tree.push(node)
    }
  }
  return tree
}

function handleCheckAll(checked: boolean) {
  if (checked) {
    checkedMenuIds.value = getAllMenuIds(menuTreeData.value)
  } else {
    checkedMenuIds.value = []
  }
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

function handleExpandAll(expanded: boolean) {
  if (expanded) {
    expandedMenuIds.value = getAllMenuIds(menuTreeData.value)
  } else {
    expandedMenuIds.value = []
  }
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
    message.error('加载套餐列表失败')
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
function openForm(type: 'create' | 'update', record?: any) {
  formType.value = type
  modalTitle.value = type === 'create' ? '新增套餐' : '编辑套餐'
  formData.name = ''
  formData.status = 'active'
  formData.remark = ''
  formData.menu_ids = []
  checkedMenuIds.value = []
  expandedMenuIds.value = []
  treeNodeAll.value = false
  treeExpandAll.value = false

  if (type === 'update' && record) {
    formData.package_id = record.package_id
    formData.name = record.name
    formData.status = record.status
    formData.remark = record.remark || ''
    formData.menu_ids = record.menu_ids || []
    checkedMenuIds.value = [...(record.menu_ids || [])]
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formData.name) {
    message.warning('请输入套餐名')
    return
  }
  submitLoading.value = true
  try {
    // 合并选中节点和半选节点
    const data = { ...formData }
    if (formType.value === 'create') {
      await createPackage(data)
      message.success('创建成功')
    } else {
      await updatePackage(data)
      message.success('更新成功')
    }
    modalVisible.value = false
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(packageId: number) {
  try {
    await deletePackage(packageId)
    message.success('删除成功')
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  }
}

async function handleBatchDelete() {
  try {
    await deletePackageList(selectedRowKeys.value)
    message.success('批量删除成功')
    selectedRowKeys.value = []
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '批量删除失败')
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
  color: #888;
  font-size: 13px;
  margin: 0;
}
.search-bar {
  margin-bottom: 16px;
  padding: 16px;
  background: #fafafa;
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
</style>
