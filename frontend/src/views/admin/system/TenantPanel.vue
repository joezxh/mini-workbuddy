<template>
  <div class="tenant-panel">
    <div class="panel-header">
      <h2>{{ t('sys.tenant.title') }}</h2>
      <p class="description">{{ t('sys.tenant.subtitle') }}</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline">
        <a-form-item :label="t('sys.tenant.labelName')">
          <a-input v-model:value="queryParams.name" :placeholder="t('sys.tenant.placeholderName')" allow-clear style="width: 160px" />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelContact')">
          <a-input v-model:value="queryParams.contact_name" :placeholder="t('sys.tenant.placeholderContact')" allow-clear style="width: 140px" />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelStatus')">
          <a-select v-model:value="queryParams.status" :placeholder="t('sys.tenant.placeholderStatus')" allow-clear style="width: 120px">
            <a-select-option value="active">{{ t('sys.tenant.statusActive') }}</a-select-option>
            <a-select-option value="disabled">{{ t('sys.tenant.statusDisabled') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleQuery">
            <template #icon><SearchOutlined /></template>
            {{ t('sys.tenant.search') }}
          </a-button>
          <a-button style="margin-left: 8px" @click="resetQuery">{{ t('sys.tenant.reset') }}</a-button>
          <a-button type="primary" style="margin-left: 8px" @click="openForm('create')">
            <template #icon><PlusOutlined /></template>
            {{ t('sys.tenant.add') }}
          </a-button>
          <a-popconfirm :title="t('sys.tenant.batchDeleteConfirm')" @confirm="handleBatchDelete" :disabled="selectedRowKeys.length === 0">
            <a-button type="primary" danger style="margin-left: 8px" :disabled="selectedRowKeys.length === 0">
              <template #icon><DeleteOutlined /></template>
              {{ t('sys.tenant.batchDelete') }}
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
            <a-tag color="blue">{{ t('sys.tenant.systemTenant') }}</a-tag> {{ record.name }}
          </template>
          <span v-else>{{ record.name }}</span>
        </template>
        <template v-if="column.key === 'package_id'">
          <a-tag v-if="isSystemTenant(record)" color="blue">{{ t('sys.tenant.systemPackage') }}</a-tag>
          <template v-else>
            <a-tag v-if="record.package_id === 0 || record.package_id === null" color="red">{{ t('sys.tenant.unassigned') }}</a-tag>
            <a-tag v-else color="green">{{ getPackageName(record.package_id) }}</a-tag>
          </template>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'red'">
            {{ record.status === 'active' ? t('sys.tenant.statusActive') : t('sys.tenant.statusDisabled') }}
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
            <a @click="openForm('update', record)">{{ t('sys.tenant.edit') }}</a>
            <a-popconfirm :title="t('sys.tenant.deleteConfirm')" @confirm="handleDelete(record.tenant_id)">
              <a style="color: var(--err)">{{ t('sys.tenant.delete') }}</a>
            </a-popconfirm>
          </a-space>
          <span v-else style="color: var(--fg-muted)">{{ t('sys.tenant.readOnly') }}</span>
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
        <a-form-item :label="t('sys.tenant.labelName')" required>
          <a-input v-model:value="formData.name" :placeholder="t('sys.tenant.inputName')" />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelPackage')">
          <a-select v-model:value="formData.package_id" :placeholder="t('sys.tenant.placeholderPackage')" allow-clear>
            <a-select-option v-for="p in packageList" :key="p.package_id" :value="p.package_id">
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelContact')">
          <a-input v-model:value="formData.contact_name" :placeholder="t('sys.tenant.placeholderContact')" />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelContactMobile')">
          <a-input v-model:value="formData.contact_mobile" :placeholder="t('sys.tenant.placeholderContactMobile')" />
        </a-form-item>
        <template v-if="formType === 'create'">
          <a-form-item :label="t('sys.tenant.labelAdminUsername')" required>
            <a-input v-model:value="formData.username" :placeholder="t('sys.tenant.placeholderAdminUsername')" />
          </a-form-item>
          <a-form-item :label="t('sys.tenant.labelAdminPassword')" required>
            <a-input-password v-model:value="formData.password" :placeholder="t('sys.tenant.placeholderAdminPassword')" />
          </a-form-item>
        </template>
        <a-form-item :label="t('sys.tenant.labelAccountCount')">
          <a-input-number v-model:value="formData.account_count" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelExpireTime')">
          <a-date-picker
            v-model:value="formData.expire_time"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelWebsites')">
          <a-select
            v-model:value="formData.websites"
            mode="tags"
            :placeholder="t('sys.tenant.placeholderWebsites')"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item :label="t('sys.tenant.labelFormStatus')">
          <a-radio-group v-model:value="formData.status">
            <a-radio value="active">{{ t('sys.tenant.statusActive') }}</a-radio>
            <a-radio value="disabled">{{ t('sys.tenant.statusDisabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import {
  getTenantPage, createTenant, updateTenant, deleteTenant, deleteTenantList,
  getPackageSimpleList,
  type TenantVO, type TenantPackageSimpleVO,
} from '@/api/tenant'

const { t } = useI18n()

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
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})
const tablePagination = computed(() => ({
  ...pagination,
  showTotal: (total: number) => t('common.total', { total })
}))
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

const columns = computed(() => [
  { title: t('sys.tenant.colId'), dataIndex: 'tenant_id', key: 'tenant_id', width: 80 },
  { title: t('sys.tenant.colName'), dataIndex: 'name', key: 'name', width: 140 },
  { title: t('sys.tenant.colPackage'), key: 'package_id', width: 120 },
  { title: t('sys.tenant.colContact'), dataIndex: 'contact_name', key: 'contact_name', width: 100 },
  { title: t('sys.tenant.colMobile'), dataIndex: 'contact_mobile', key: 'contact_mobile', width: 120 },
  { title: t('sys.tenant.colAccountQuota'), dataIndex: 'account_count', key: 'account_count', width: 80 },
  { title: t('sys.tenant.colExpireTime'), dataIndex: 'expire_time', key: 'expire_time', width: 170 },
  { title: t('sys.tenant.colWebsites'), key: 'websites', width: 160 },
  { title: t('sys.tenant.colStatus'), key: 'status', width: 80 },
  { title: t('sys.tenant.colCreatedAt'), dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: t('sys.tenant.colAction'), key: 'action', width: 120, fixed: 'right' as const },
])

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
    message.error(t('sys.tenant.loadFail'))
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
    message.warning(t('sys.tenant.systemTenantNoEdit'))
    return
  }
  formType.value = type
  modalTitle.value = type === 'create' ? t('sys.tenant.addTitle') : t('sys.tenant.editTitle')
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
    message.warning(t('sys.tenant.inputName'))
    return
  }
  if (formType.value === 'create' && (!formData.username || !formData.password)) {
    message.warning(t('sys.tenant.needAdmin'))
    return
  }
  submitLoading.value = true
  try {
    if (formType.value === 'create') {
      await createTenant(formData)
      message.success(t('sys.tenant.createSuccess'))
    } else {
      await updateTenant(formData)
      message.success(t('sys.tenant.updateSuccess'))
    }
    modalVisible.value = false
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('sys.tenant.opFail'))
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(tenantId: number) {
  if (tenantId === SYSTEM_TENANT_ID) {
    message.warning(t('sys.tenant.systemTenantNoDelete'))
    return
  }
  try {
    await deleteTenant(tenantId)
    message.success(t('sys.tenant.deleteSuccess'))
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('sys.tenant.deleteFail'))
  }
}

async function handleBatchDelete() {
  // 过滤掉系统租户
  const idsToDelete = selectedRowKeys.value.filter((id) => id !== SYSTEM_TENANT_ID)
  if (idsToDelete.length === 0) {
    message.warning(t('sys.tenant.systemTenantNoDelete'))
    return
  }
  try {
    await deleteTenantList(idsToDelete)
    message.success(t('sys.tenant.batchDeleteSuccess'))
    selectedRowKeys.value = []
    loadData()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('sys.tenant.batchDeleteFail'))
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
</style>
