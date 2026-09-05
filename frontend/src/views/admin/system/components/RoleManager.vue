<template>
  <div class="role-manager">
    <div class="toolbar">
      <a-button type="primary" v-permission="'admin:roles:create'" @click="openModal()">新增角色</a-button>
      <a-button v-permission="'admin:roles:read'" @click="fetchRoles">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="roles"
      :loading="loading"
      row-key="roleId"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-button type="link" v-permission="'admin:roles:update'" @click="openModal(record)">编辑</a-button>
          <a-button type="link" v-permission="'admin:roles:assign-permission'" @click="openPermModal(record)">分配权限</a-button>
        </template>
      </template>
    </a-table>

    <!-- 角色编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingRole ? '编辑角色' : '新增角色'"
      @ok="handleSave"
      :confirmLoading="saving"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.roleName" />
        </a-form-item>
        <a-form-item label="代码" required>
          <a-input v-model:value="form.roleCode" :disabled="!!editingRole" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分配权限弹窗 -->
    <a-modal
      v-model:open="permModalVisible"
      :title="`分配权限 — ${permEditingRole?.roleName || ''}`"
      @ok="handleSavePerms"
      :confirm-loading="permSaving"
      width="600px"
      ok-text="保存"
      cancel-text="取消"
    >
      <a-spin :spinning="permLoading">
        <div class="perm-filter">
          <a-radio-group v-model:value="permTypeFilter" button-style="solid" size="small">
            <a-radio-button value="">全部</a-radio-button>
            <a-radio-button value="directory">目录</a-radio-button>
            <a-radio-button value="menu">菜单</a-radio-button>
            <a-radio-button value="button">按钮</a-radio-button>
          </a-radio-group>
        </div>
        <a-checkbox
          :checked="isAllChecked"
          :indeterminate="isIndeterminate"
          @change="toggleAll"
          style="margin:8px 0 12px;font-weight:600"
        >全选</a-checkbox>
        <a-checkbox-group v-model:value="selectedPermIds" style="display:flex;flex-direction:column;gap:6px">
          <a-checkbox
            v-for="p in filteredPerms"
            :key="p.id"
            :value="p.id"
          >
            <span>{{ p.name }}</span>
            <a-tag size="small" :color="permTypeColor(p.type)" style="margin-left:6px">{{ permTypeName(p.type) }}</a-tag>
            <span class="perm-code">{{ p.permission || '' }}</span>
          </a-checkbox>
        </a-checkbox-group>
        <a-empty v-if="!permLoading && filteredPerms.length === 0" description="暂无权限数据" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getRoleList, createRole, updateRole, getMenuFlatList, getRolePermissions, assignRolePermissions } from '@/api/admin'

const roles = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '角色名', dataIndex: 'roleName', key: 'roleName' },
  { title: '代码', dataIndex: 'roleCode', key: 'roleCode' },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '操作', key: 'action', width: 160 }
]

const modalVisible = ref(false)
const saving = ref(false)
const editingRole = ref<any>(null)
const form = reactive({
  roleName: '',
  roleCode: '',
  description: ''
})

const fetchRoles = async () => {
  loading.value = true
  try {
    const res = await getRoleList()
    if (res.code === 0) {
      roles.value = res.data
    }
  } catch (error) {
    message.error('获取角色列表失败')
  } finally {
    loading.value = false
  }
}

const openModal = (record?: any) => {
  editingRole.value = record || null
  if (record) {
    form.roleName = record.roleName
    form.roleCode = record.roleCode
    form.description = record.description || ''
  } else {
    form.roleName = ''
    form.roleCode = ''
    form.description = ''
  }
  modalVisible.value = true
}

const handleSave = async () => {
  if (!form.roleName || !form.roleCode) {
    message.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (editingRole.value) {
      const res = await updateRole(editingRole.value.roleId, form)
      if (res.code === 0) {
        message.success('更新成功')
        modalVisible.value = false
        fetchRoles()
      } else {
        message.error(res.message || '更新失败')
      }
    } else {
      const res = await createRole(form)
      if (res.code === 0) {
        message.success('创建成功')
        modalVisible.value = false
        fetchRoles()
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

// ── 分配权限 ─────────────────────────────────────────────────
const permModalVisible = ref(false)
const permLoading = ref(false)
const permSaving = ref(false)
const permEditingRole = ref<any>(null)
const allPerms = ref<any[]>([])
const selectedPermIds = ref<number[]>([])
const permTypeFilter = ref('')

const filteredPerms = computed(() => {
  if (!permTypeFilter.value) return allPerms.value
  return allPerms.value.filter(p => p.type === (permTypeFilter.value === 'menu' ? 2 : permTypeFilter.value === 'button' ? 3 : 1))
})

const isAllChecked = computed(() =>
  filteredPerms.value.length > 0 &&
  filteredPerms.value.every(p => selectedPermIds.value.includes(p.id))
)

const isIndeterminate = computed(() => {
  const count = filteredPerms.value.filter(p => selectedPermIds.value.includes(p.id)).length
  return count > 0 && count < filteredPerms.value.length
})

function toggleAll(e: any) {
  const filtered = filteredPerms.value.map(p => p.id)
  if (e.target.checked) {
    const merged = Array.from(new Set([...selectedPermIds.value, ...filtered]))
    selectedPermIds.value = merged
  } else {
    selectedPermIds.value = selectedPermIds.value.filter(id => !filtered.includes(id))
  }
}

function permTypeColor(type: number) {
  return type === 1 ? 'blue' : type === 2 ? 'green' : 'orange'
}

function permTypeName(type: number) {
  return type === 1 ? '目录' : type === 2 ? '菜单' : '按钮'
}

const openPermModal = async (record: any) => {
  permEditingRole.value = record
  permModalVisible.value = true
  permLoading.value = true
  try {
    const [permsRes, rolePermsRes] = await Promise.all([
      getMenuFlatList(),
      getRolePermissions(record.roleId)
    ])
    allPerms.value = permsRes.data || []
    selectedPermIds.value = rolePermsRes.data || []
  } catch (e: any) {
    message.error('加载权限数据失败')
  } finally {
    permLoading.value = false
  }
}

const handleSavePerms = async () => {
  if (!permEditingRole.value) return
  permSaving.value = true
  try {
    const res = await assignRolePermissions(permEditingRole.value.roleId, selectedPermIds.value)
    if (res.code === 0) {
      message.success('权限分配成功')
      permModalVisible.value = false
    } else {
      message.error(res.message || '分配失败')
    }
  } catch (e: any) {
    message.error(e?.message || '操作失败')
  } finally {
    permSaving.value = false
  }
}

onMounted(() => {
  fetchRoles()
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
}
.perm-filter {
  margin-bottom: 10px;
}
.perm-code {
  font-size: 11px;
  color: #999;
  margin-left: 6px;
}
</style>
