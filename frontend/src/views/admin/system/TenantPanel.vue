<template>
  <div class="tenant-panel">
    <div class="panel-header">
      <h2>租户管理</h2>
      <p class="description">管理 SaaS 多租户，包括租户创建、套餐分配、状态控制</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline">
        <a-form-item label="租户名">
          <a-input v-model:value="queryParams.name" placeholder="请输入租户名" allow-clear style="width: 160px" />
        </a-form-item>
        <a-form-item label="联系人">
          <a-input v-model:value="queryParams.contact_name" placeholder="请输入联系人" allow-clear style="width: 140px" />
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
          <a-popconfirm title="确认批量删除选中的租户吗？" @confirm="handleBatchDelete" :disabled="selectedRowKeys.length === 0">
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
      :row-selection="rowSelection"
      row-key="tenant_id"
      size="middle"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tenant_id'">
          <span>{{ record.tenant_id }}</span>
        </template>
        <template v-if="column.key === 'name'">
          <template v-if="isSystemTenant(record)">
            <a-tag color="blue">系统租户</a-tag> {{ record.name }}
          </template>
          <span v-else>{{ record.name }}</span>
        </template>
        <template v-if="column.key === 'package_id'">
          <a-tag v-if="isSystemTenant(record)" color="blue">系统套餐</a-tag>
          <template v-else>
            <a-tag v-if="record.package_id === 0 || record.package_id === null" color="red">未分配</a-tag>
            <a-tag v-else color="green">{{ getPackageName(record.package_id) }}</a-tag>
          </template>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'red'">
            {{ record.status === 'active' ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'websites'">
          <template v-if="record.websites && record.websites.length">
            <a-tag v-for="w in record.websites" :key="w" size="small">{{ w }}</a-tag>
          </template>
          <span v-else>-</span>
        </template>
        <template v-if="column.key === 'action'">
          <a-space v-if="!isSystemTenant(record)">
            <a @click="openForm('update', record)">编辑</a>
            <a-popconfirm title="确认删除该租户吗？" @confirm="handleDelete(record.tenant_id)">
              <a style="color: #ff4d4f">删除</a>
            </a-popconfirm>
          </a-space>
          <span v-else style="color: #999">只读</span>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      :confirm-loading="submitLoading"
      @ok="handleSubmit"
      width="600px"
    >
      <a-form :model="formData" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="租户名" required>
          <a-input v-model:value="formData.name" placeholder="请输入租户名" />
        </a-form-item>
        <a-form-item label="租户套餐">
          <a-select v-model:value="formData.package_id" placeholder="请选择套餐" allow-clear>
            <a-select-option v-for="p in packageList" :key="p.package_id" :value="p.package_id">
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="联系人">
          <a-input v-model:value="formData.contact_name" placeholder="请输入联系人" />
        </a-form-item>
        <a-form-item label="联系手机">
          <a-input v-model:value="formData.contact_mobile" placeholder="请输入联系手机" />
        </a-form-item>
        <template v-if="formType === 'create'">
          <a-form-item label="管理员用户名" required>
            <a-input v-model:value="formData.username" placeholder="请输入管理员用户名" />
          </a-form-item>
          <a-form-item label="管理员密码" required>
            <a-input-password v-model:value="formData.password" placeholder="请输入管理员密码" />
          </a-form-item>
        </template>
        <a-form-item label="账号额度">
          <a-input-number v-model:value="formData.account_count" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item label="过期时间">
          <a-date-picker
            v-model:value="formData.expire_time"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="绑定域名">
          <a-select
            v-model:value="formData.websites"
            mode="tags"
            placeholder="输入域名后按回车添加"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="formData.status">
            <a-radio value="active">启用</a-radio>
            <a-radio value="disabled">禁用</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { SearchOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import {
  getTenantPage, createTenant, updateTenant, deleteTenant, deleteTenantList,
  getPackageSimpleList,
  type TenantVO, type TenantPackageSimpleVO,
} from '@/api/tenant'

defineOptions({ name: 'TenantPanel' })

/** 系统租户 ID（不可修改/删除） */
const SYSTEM_TENANT_ID = 0

/** 判断是否为系统租户 */
function isSystemTenant(record: any): boolean {
  return record.tenant_id === SYSTEM_TENANT_ID
}

// ── 查询参数 ──────────────────────────────────────────────────────
const queryParams = reactive({
  name: '',
  contact_name: '',
  status: undefined as string | undefined,
})

const loading = ref(false)
const tableData = ref<any[]>([])
const selectedRowKeys = ref<number[]>([])
const pagination = reactive({ current: 1, pageSize: 10, total: 0 })
const packageList = ref<TenantPackageSimpleVO[]>([])

/** 行选择配置：排除系统租户（id=0） */
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: number[]) => {
    selectedRowKeys.value = keys
  },
  getCheckboxProps: (record: any) => ({
    disabled: isSystemTenant(record),
  }),
}))

const columns = [
  { title: '租户编号', dataIndex: 'tenant_id', key: 'tenant_id', width: 80 },
  { title: '租户名', dataIndex: 'name', key: 'name', width: 140 },
  { title: '租户套餐', key: 'package_id', width: 120 },
  { title: '联系人', dataIndex: 'contact_name', key: 'contact_name', width: 100 },
  { title: '联系手机', dataIndex: 'contact_mobile', key: 'contact_mobile', width: 120 },
  { title: '账号额度', dataIndex: 'account_count', key: 'account_count', width: 80 },
  { title: '过期时间', dataIndex: 'expire_time', key: 'expire_time', width: 170 },
  { title: '绑定域名', key: 'websites', width: 160 },
  { title: '状态', key: 'status', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 120, fixed: 'right' as const },
]

// ── 弹窗 ──────────────────────────────────────────────────────────
const modalVisible = ref(false)
const modalTitle = ref('')
const formType = ref<'create' | 'update'>('create')
const submitLoading = ref(false)

const defaultForm = (): TenantVO => ({
  name: '',
  package_id: null,
  contact_name: '',
  contact_mobile: '',
  status: 'active',
  account_count: 0,
  expire_time: null,
  websites: [],
  username: '',
  password: '',
})

const formData = reactive<TenantVO>(defaultForm())

function getPackageName(packageId: number): string {
  return packageList.value.find((p: TenantPackageSimpleVO) => p.package_id === packageId)?.name || `#${packageId}`
}

// ── 数据加载 ──────────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const res = await getTenantPage({
      ...queryParams,
      page_no: pagination.current,
      page_size: pagination.pageSize,
    }) as any
    const data = res?.data || res || {}
    tableData.value = data.list || []
    pagination.total = data.total || 0
  } catch (e: any) {
    message.error('加载租户列表失败')
  } finally {
    loading.value = false
  }
}

async function loadPackages() {
  try {
    const res = await getPackageSimpleList() as any
    packageList.value = res?.data || res || []
  } catch { /* ignore */ }
}

function handleQuery() {
  pagination.current = 1
  loadData()
}

function resetQuery() {
  queryParams.name = ''
  queryParams.contact_name = ''
  queryParams.status = undefined
  handleQuery()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

// ── 表单操作 ──────────────────────────────────────────────────────
function openForm(type: 'create' | 'update', record?: any) {
  // 系统租户只读，禁止编辑
  if (type === 'update' && record && isSystemTenant(record)) {
    message.warning('系统租户不可编辑')
    return
  }
  formType.value = type
  modalTitle.value = type === 'create' ? '新增租户' : '编辑租户'
  Object.assign(formData, defaultForm())
  if (type === 'update' && record) {
    Object.assign(formData, {
      tenant_id: record.tenant_id,
      name: record.name,
      package_id: record.package_id,
      contact_name: record.contact_name,
      contact_mobile: record.contact_mobile,
      status: record.status,
      account_count: record.account_count,
      expire_time: record.expire_time,
      websites: record.websites || [],
    })
  }
  modalVisible.value = true
}

async function handleSubmit() {
  if (!formData.name) {
    message.warning('请输入租户名')
    return
  }
  if (formType.value === 'create' && (!formData.username || !formData.password)) {
    message.warning('新增租户需填写管理员用户名和密码')
    return
  }
  submitLoading.value = true
  try {
    if (formType.value === 'create') {
      await createTenant(formData)
      message.success('创建成功')
    } else {
      await updateTenant(formData)
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

async function handleDelete(tenantId: number) {
  if (tenantId === SYSTEM_TENANT_ID) {
    message.warning('系统租户不可删除')
    return
  }
  try {
    await deleteTenant(tenantId)
    message.success('删除成功')
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  }
}

async function handleBatchDelete() {
  // 过滤掉系统租户
  const idsToDelete = selectedRowKeys.value.filter((id) => id !== SYSTEM_TENANT_ID)
  if (idsToDelete.length === 0) {
    message.warning('系统租户不可删除')
    return
  }
  try {
    await deleteTenantList(idsToDelete)
    message.success('批量删除成功')
    selectedRowKeys.value = []
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '批量删除失败')
  }
}

onMounted(() => {
  loadData()
  loadPackages()
})
</script>

<style scoped>
.tenant-panel {
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
</style>
