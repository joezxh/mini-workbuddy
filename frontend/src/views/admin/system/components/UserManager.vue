<template>
  <div class="user-manager">
    <div class="toolbar">
      <a-button type="primary" v-permission="'admin:users:create'" @click="openModal()">{{ t('sys.user.addUser') }}</a-button>
      <a-button v-permission="'admin:users:read'" @click="fetchUsers">{{ t('sys.user.refresh') }}</a-button>
      <span v-if="showTenant" class="filter-label">{{ t('sys.user.tenantFilter') }}</span>
      <TenantFilterSelect v-if="showTenant" v-model="selectedTenantId" />
    </div>

    <a-table
      :columns="columns"
      :data-source="users"
      :loading="loading"
      :pagination="tablePagination"
      @change="handleTableChange"
      row-key="userId"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-switch
            :checked="record.status === 'active'"
            @change="(checked: boolean) => handleStatusChange(record.userId, checked)"
          />
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" v-permission="'admin:users:update'" @click="openModal(record)">{{ t('sys.user.editUser') }}</a-button>
          <a-button type="link" v-permission="'admin:users:assign-role'" @click="openRoleModal(record)">{{ t('sys.user.assignRole') }}</a-button>
          <a-button type="link" v-permission="'admin:audit-logs:read'" @click="$emit('view-logs', record.userId)">{{ t('sys.user.viewLogs') }}</a-button>
        </template>
      </template>
    </a-table>

    <!-- 用户模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingUser ? t('sys.user.editUser') : t('sys.user.addUserTitle')"
      @ok="handleSave"
      :confirmLoading="saving"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('sys.user.labelUsername')" required>
          <a-input v-model:value="form.username" :disabled="!!editingUser" />
        </a-form-item>
        <a-form-item v-if="!editingUser" :label="t('sys.user.labelPassword')" required>
          <a-input-password v-model:value="form.password" />
        </a-form-item>
        <a-form-item :label="t('sys.user.labelRealName')" required>
          <a-input v-model:value="form.realName" />
        </a-form-item>
        <a-form-item :label="t('sys.user.labelPhone')">
          <a-input v-model:value="form.phone" />
        </a-form-item>
        <a-form-item :label="t('sys.user.labelEmail')">
          <a-input v-model:value="form.email" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分配角色弹窗 -->
    <a-modal
      v-model:open="roleModalVisible"
      :title="t('sys.user.assignRoleTitle', { name: roleEditingUser?.realName || '' })"
      @ok="handleSaveRoles"
      :confirm-loading="roleSaving"
      :ok-text="t('sys.user.save')"
      :cancel-text="t('sys.user.cancel')"
    >
      <a-spin :spinning="roleLoading">
        <a-checkbox-group v-model:value="selectedRoleIds" style="display:flex;flex-direction:column;gap:8px">
          <a-checkbox v-for="r in allRoles" :key="r.roleId" :value="r.roleId">
            {{ r.roleName }}
            <a-tag size="small" color="blue" style="margin-left:4px">{{ r.roleCode }}</a-tag>
          </a-checkbox>
        </a-checkbox-group>
        <a-empty v-if="!roleLoading && allRoles.length === 0" :description="t('sys.user.noRoles')" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { getUserListBySkip, createUser, updateUser, updateUserStatus, getRoleList, getUserRoles, assignUserRole } from '@/api/admin'
import TenantFilterSelect from './TenantFilterSelect.vue'

const { t } = useI18n()

const props = defineProps<{
  /** 是否显示租户筛选下拉与所属租户列（仅超级管理员可见） */
  showTenant?: boolean
}>()

// 租户筛选由本组件内部持有：超管可切换具体租户，清空=全部
const selectedTenantId = ref<number | undefined>(undefined)
const tenantParam = () => (props.showTenant && selectedTenantId.value != null ? selectedTenantId.value : null)

defineEmits(['view-logs'])

const users = ref<any[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})
const tablePagination = computed(() => ({
  ...pagination,
  showTotal: (total: number) => t('common.total', { total })
}))

// 租户列为超级管理员专属；普通租户管理员不显示所属租户
const columns = computed(() => {
  const base: any[] = [
    { title: t('sys.user.colUsername'), dataIndex: 'username', key: 'username' },
    { title: t('sys.user.colRealName'), dataIndex: 'realName', key: 'realName' },
    { title: t('sys.user.colPhone'), dataIndex: 'phone', key: 'phone' },
    { title: t('sys.user.colEmail'), dataIndex: 'email', key: 'email' },
    { title: t('sys.user.colCreatedAt'), dataIndex: 'createdAt', key: 'createdAt' },
    { title: t('sys.user.colStatus'), key: 'status' },
  ]
  if (props.showTenant) {
    base.push({ title: t('sys.user.colTenant'), dataIndex: 'tenantName', key: 'tenantName', width: 140 })
  }
  base.push({ title: t('sys.user.colAction'), key: 'action', width: 200, fixed: 'right' as const })
  return base
})

const modalVisible = ref(false)
const saving = ref(false)
const editingUser = ref<any>(null)
const form = reactive({
  username: '',
  password: '',
  realName: '',
  phone: '',
  email: ''
})

const fetchUsers = async () => {
  loading.value = true
  try {
    const params: any = {
      skip: (pagination.current - 1) * pagination.pageSize,
      limit: pagination.pageSize
    }
    const tid = tenantParam()
    if (tid != null) params.tenant_id = tid
    const res = await getUserListBySkip(params)
    if (res.code === 0) {
      users.value = res.data
      pagination.total = res.total
    }
  } catch (error) {
    message.error(t('sys.user.fetchFail'))
  } finally {
    loading.value = false
  }
}

// 切换租户筛选时重新拉取
watch(selectedTenantId, () => {
  pagination.current = 1
  fetchUsers()
})

const handleTableChange = (pag: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  fetchUsers()
}

const openModal = (record?: any) => {
  editingUser.value = record || null
  if (record) {
    form.username = record.username
    form.realName = record.realName
    form.phone = record.phone
    form.email = record.email
  } else {
    form.username = ''
    form.password = ''
    form.realName = ''
    form.phone = ''
    form.email = ''
  }
  modalVisible.value = true
}

const handleSave = async () => {
  if (!form.username || (!editingUser.value && !form.password) || !form.realName) {
    message.warning(t('sys.user.fillRequired'))
    return
  }
  saving.value = true
  try {
    if (editingUser.value) {
      const res = await updateUser(editingUser.value.userId, form)
      if (res.code === 0) {
        message.success(t('sys.user.updateSuccess'))
        modalVisible.value = false
        fetchUsers()
      } else {
        message.error(res.message || t('sys.user.updateFail'))
      }
    } else {
      const res = await createUser(form)
      if (res.code === 0) {
        message.success(t('sys.user.createSuccess'))
        modalVisible.value = false
        fetchUsers()
      } else {
        message.error(res.message || t('sys.user.createFail'))
      }
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || t('sys.user.saveFail'))
  } finally {
    saving.value = false
  }
}

const handleStatusChange = async (userId: number, checked: boolean) => {
  const status = checked ? 'active' : 'inactive'
  try {
    const res = await updateUserStatus(userId, status)
    if (res.code === 0) {
      message.success(t('sys.user.statusUpdated'))
      fetchUsers()
    } else {
      message.error(res.message || t('sys.user.statusUpdateFail'))
    }
  } catch (error) {
    message.error(t('sys.user.statusUpdateFail'))
  }
}

// ── 分配角色 ────────────────────────────────────────────────
const roleModalVisible = ref(false)
const roleLoading = ref(false)
const roleSaving = ref(false)
const roleEditingUser = ref<any>(null)
const allRoles = ref<any[]>([])
const selectedRoleIds = ref<number[]>([])

const openRoleModal = async (record: any) => {
  roleEditingUser.value = record
  roleModalVisible.value = true
  roleLoading.value = true
  try {
    const [rolesRes, userRolesRes] = await Promise.all([
      getRoleList(tenantParam() != null ? { tenant_id: tenantParam()! } : undefined),
      getUserRoles(record.userId)
    ])
    allRoles.value = rolesRes.data || []
    selectedRoleIds.value = userRolesRes.data || []
  } catch (e: any) {
    message.error(t('sys.user.loadRoleFail'))
  } finally {
    roleLoading.value = false
  }
}

const handleSaveRoles = async () => {
  if (!roleEditingUser.value) return
  roleSaving.value = true
  try {
    const res = await assignUserRole(roleEditingUser.value.userId, selectedRoleIds.value)
    if (res.code === 0) {
      message.success(t('sys.user.roleAssignSuccess'))
      roleModalVisible.value = false
    } else {
      message.error(res.message || t('sys.user.roleAssignFail'))
    }
  } catch (e: any) {
    message.error(e?.message || t('common.error'))
  } finally {
    roleSaving.value = false
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.filter-label {
  font-size: 14px;
  color: var(--fg-secondary);
  white-space: nowrap;
}

/* 表格行不换行；操作按钮保持单行不换行 */
:deep(.ant-table-cell) {
  white-space: nowrap;
}
.action-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
</style>
