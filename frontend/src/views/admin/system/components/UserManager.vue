<template>
  <div class="user-manager">
    <div class="toolbar">
      <a-button type="primary" v-permission="'admin:users:create'" @click="openModal()">新增用户</a-button>
      <a-button v-permission="'admin:users:read'" @click="fetchUsers">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="users"
      :loading="loading"
      :pagination="pagination"
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
          <a-button type="link" v-permission="'admin:users:update'" @click="openModal(record)">编辑</a-button>
          <a-button type="link" v-permission="'admin:users:assign-role'" @click="openRoleModal(record)">分配角色</a-button>
          <a-button type="link" v-permission="'admin:audit-logs:read'" @click="$emit('view-logs', record.userId)">查看日志</a-button>
        </template>
      </template>
    </a-table>

    <!-- 用户模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingUser ? '编辑用户' : '新增用户'"
      @ok="handleSave"
      :confirmLoading="saving"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="用户名" required>
          <a-input v-model:value="form.username" :disabled="!!editingUser" />
        </a-form-item>
        <a-form-item v-if="!editingUser" label="密码" required>
          <a-input-password v-model:value="form.password" />
        </a-form-item>
        <a-form-item label="真实姓名" required>
          <a-input v-model:value="form.realName" />
        </a-form-item>
        <a-form-item label="手机号">
          <a-input v-model:value="form.phone" />
        </a-form-item>
        <a-form-item label="邮箱">
          <a-input v-model:value="form.email" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分配角色弹窗 -->
    <a-modal
      v-model:open="roleModalVisible"
      :title="`分配角色 — ${roleEditingUser?.realName || ''}`"
      @ok="handleSaveRoles"
      :confirm-loading="roleSaving"
      ok-text="保存"
      cancel-text="取消"
    >
      <a-spin :spinning="roleLoading">
        <a-checkbox-group v-model:value="selectedRoleIds" style="display:flex;flex-direction:column;gap:8px">
          <a-checkbox v-for="r in allRoles" :key="r.roleId" :value="r.roleId">
            {{ r.roleName }}
            <a-tag size="small" color="blue" style="margin-left:4px">{{ r.roleCode }}</a-tag>
          </a-checkbox>
        </a-checkbox-group>
        <a-empty v-if="!roleLoading && allRoles.length === 0" description="暂无角色" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getUserListBySkip, createUser, updateUser, updateUserStatus, getRoleList, getUserRoles, assignUserRole } from '@/api/admin'

defineEmits(['view-logs'])

const users = ref<any[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '真实姓名', dataIndex: 'realName', key: 'realName' },
  { title: '手机号', dataIndex: 'phone', key: 'phone' },
  { title: '邮箱', dataIndex: 'email', key: 'email' },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt' },
  { title: '状态', key: 'status' },
  { title: '操作', key: 'action', width: 200 }
]

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
    const res = await getUserListBySkip({
      skip: (pagination.current - 1) * pagination.pageSize,
      limit: pagination.pageSize
    })
    if (res.code === 0) {
      users.value = res.data
      pagination.total = res.total
    }
  } catch (error) {
    message.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

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
    message.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (editingUser.value) {
      const res = await updateUser(editingUser.value.userId, form)
      if (res.code === 0) {
        message.success('更新成功')
        modalVisible.value = false
        fetchUsers()
      } else {
        message.error(res.message || '更新失败')
      }
    } else {
      const res = await createUser(form)
      if (res.code === 0) {
        message.success('创建成功')
        modalVisible.value = false
        fetchUsers()
      } else {
        message.error(res.message || '创建失败')
      }
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleStatusChange = async (userId: number, checked: boolean) => {
  const status = checked ? 'active' : 'inactive'
  try {
    const res = await updateUserStatus(userId, status)
    if (res.code === 0) {
      message.success('状态更新成功')
      fetchUsers()
    } else {
      message.error(res.message || '更新失败')
    }
  } catch (error) {
    message.error('更新失败')
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
      getRoleList(),
      getUserRoles(record.userId)
    ])
    allRoles.value = rolesRes.data || []
    selectedRoleIds.value = userRolesRes.data || []
  } catch (e: any) {
    message.error('加载角色数据失败')
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
      message.success('角色分配成功')
      roleModalVisible.value = false
    } else {
      message.error(res.message || '分配失败')
    }
  } catch (e: any) {
    message.error(e?.message || '操作失败')
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
}
</style>
