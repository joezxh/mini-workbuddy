<template>
  <div class="role-manager">
    <div class="toolbar">
      <a-button type="primary" v-permission="'admin:roles:create'" @click="openModal()">{{ t('sys.role.addRole') }}</a-button>
      <a-button v-permission="'admin:roles:read'" @click="fetchRoles">{{ t('sys.role.refresh') }}</a-button>
      <span v-if="showTenant" class="filter-label">{{ t('sys.role.tenantFilter') }}</span>
      <TenantFilterSelect v-if="showTenant" v-model="selectedTenantId" />
    </div>

    <a-table
      :columns="columns"
      :data-source="roles"
      :loading="loading"
      row-key="roleId"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-button type="link" v-permission="'admin:roles:update'" @click="openModal(record)">{{ t('sys.role.editRole') }}</a-button>
          <a-button type="link" v-permission="'admin:roles:assign-permission'" @click="openPermModal(record)">{{ t('sys.role.assignPerm') }}</a-button>
        </template>
      </template>
    </a-table>

    <!-- 角色编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingRole ? t('sys.role.editRole') : t('sys.role.addRoleTitle')"
      @ok="handleSave"
      :confirmLoading="saving"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('sys.role.labelName')" required>
          <a-input v-model:value="form.roleName" />
        </a-form-item>
        <a-form-item :label="t('sys.role.labelCode')" required>
          <a-input v-model:value="form.roleCode" :disabled="!!editingRole" />
        </a-form-item>
        <a-form-item :label="t('sys.role.labelDescription')">
          <a-textarea v-model:value="form.description" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分配权限弹窗（父子关系树） -->
    <a-modal
      v-model:open="permModalVisible"
      :title="t('sys.role.assignPermTitle', { name: permEditingRole?.roleName || '' })"
      @ok="handleSavePerms"
      :confirm-loading="permSaving"
      width="640px"
      :ok-text="t('sys.role.save')"
      :cancel-text="t('sys.role.cancel')"
    >
      <a-spin :spinning="permLoading">
        <div class="perm-toolbar">
          <a-radio-group v-model:value="permTypeFilter" button-style="solid" size="small">
            <a-radio-button value="">{{ t('sys.role.all') }}</a-radio-button>
            <a-radio-button value="directory">{{ t('sys.role.directory') }}</a-radio-button>
            <a-radio-button value="menu">{{ t('sys.role.menu') }}</a-radio-button>
            <a-radio-button value="button">{{ t('sys.role.button') }}</a-radio-button>
          </a-radio-group>
          <a-button size="small" @click="checkAllPerms">{{ t('sys.role.selectAll') }}</a-button>
          <a-button size="small" @click="clearPerms">{{ t('sys.role.clearAll') }}</a-button>
        </div>
        <a-tree
          v-if="!permLoading"
          class="perm-tree"
          checkable
          :tree-data="treeData"
          :checked-keys="selectedPermIds"
          :default-expand-all="true"
          @check="onTreeCheck"
        >
          <template #title="{ data }">
            <span class="tree-node">
              <span class="node-title">{{ data.title }}</span>
              <a-tag size="small" :color="permTypeColor(data.type)" style="margin-left:6px">{{ permTypeName(data.type) }}</a-tag>
              <span class="perm-code" v-if="data.permission">{{ data.permission }}</span>
            </span>
          </template>
        </a-tree>
        <a-empty v-if="!permLoading && treeData.length === 0" :description="t('sys.role.noData')" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { getRoleList, createRole, updateRole, getMenuFlatList, getRolePermissions, assignRolePermissions } from '@/api/admin'
import TenantFilterSelect from './TenantFilterSelect.vue'

const { t } = useI18n()

const props = defineProps<{
  /** 是否显示租户筛选下拉与所属租户列（仅超级管理员可见） */
  showTenant?: boolean
}>()

// 租户筛选由本组件内部持有：超管可切换具体租户，清空=全部
const selectedTenantId = ref<number | undefined>(undefined)
const tenantParam = () => (props.showTenant && selectedTenantId.value != null ? selectedTenantId.value : null)

const roles = ref<any[]>([])
const loading = ref(false)

const columns = computed(() => {
  const base: any[] = [
    { title: t('sys.role.colRoleName'), dataIndex: 'roleName', key: 'roleName' },
    { title: t('sys.role.colRoleCode'), dataIndex: 'roleCode', key: 'roleCode' },
    { title: t('sys.role.colDescription'), dataIndex: 'description', key: 'description' },
  ]
  if (props.showTenant) {
    base.push({ title: t('sys.role.colTenant'), dataIndex: 'tenantName', key: 'tenantName', width: 140 })
  }
  base.push({ title: t('sys.role.colAction'), key: 'action', width: 160, fixed: 'right' as const })
  return base
})

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
    const tid = tenantParam()
    const res = await getRoleList(tid != null ? { tenant_id: tid } : undefined)
    if (res.code === 0) {
      roles.value = res.data
    }
  } catch (error) {
    message.error(t('sys.role.fetchFail'))
  } finally {
    loading.value = false
  }
}

// 切换租户筛选时重新拉取
watch(selectedTenantId, () => {
  fetchRoles()
})

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
    message.warning(t('sys.role.fillRequired'))
    return
  }
  saving.value = true
  try {
    if (editingRole.value) {
      const res = await updateRole(editingRole.value.roleId, form)
      if (res.code === 0) {
        message.success(t('sys.role.updateSuccess'))
        modalVisible.value = false
        fetchRoles()
      } else {
        message.error(res.message || t('sys.role.updateFail'))
      }
    } else {
      const res = await createRole(form)
      if (res.code === 0) {
        message.success(t('sys.role.createSuccess'))
        modalVisible.value = false
        fetchRoles()
      } else {
        message.error(res.message || t('sys.role.createFail'))
      }
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || t('sys.role.saveFail'))
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

// 根据类型过滤（保留匹配节点及其祖先以维持树结构）后构建父子树
const treeData = computed(() => {
  let list: any[] = allPerms.value || []
  if (permTypeFilter.value) {
    const typeVal = permTypeFilter.value === 'menu' ? 2 : permTypeFilter.value === 'button' ? 3 : 1
    const byId = new Map(list.map((p: any) => [p.id, p]))
    const keep = new Set<number>()
    for (const p of list) {
      if (p.type === typeVal) {
        keep.add(p.id)
        let pid = p.parentId
        while (pid) {
          if (keep.has(pid)) break
          keep.add(pid)
          pid = byId.get(pid)?.parentId ?? null
        }
      }
    }
    list = list.filter(p => keep.has(p.id))
  }

  const nodes = new Map<number, any>()
  for (const p of list) {
    nodes.set(p.id, {
      key: p.id,
      title: p.name,
      type: p.type,
      permission: p.permission,
      children: [] as any[],
    })
  }
  const roots: any[] = []
  for (const p of list) {
    const node = nodes.get(p.id)!
    if (p.parentId && nodes.has(p.parentId)) {
      nodes.get(p.parentId)!.children.push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
})

function onTreeCheck(checkedKeys: any) {
  // 非严格模式下 checkedKeys 为数组；严格模式则为 { checked, halfChecked }
  selectedPermIds.value = Array.isArray(checkedKeys) ? checkedKeys : checkedKeys.checked
}

// 全选：勾选当前过滤下所有可见节点（含父子）
function checkAllPerms() {
  const collect = (arr: any[]): number[] => {
    let ids: number[] = []
    for (const n of arr) {
      ids.push(n.key)
      if (n.children?.length) ids = ids.concat(collect(n.children))
    }
    return ids
  }
  selectedPermIds.value = collect(treeData.value)
}

function clearPerms() {
  selectedPermIds.value = []
}

function permTypeColor(type: number) {
  return type === 1 ? 'blue' : type === 2 ? 'green' : 'orange'
}

function permTypeName(type: number) {
  return type === 1 ? t('sys.role.directory') : type === 2 ? t('sys.role.menu') : t('sys.role.button')
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
    message.error(t('sys.role.loadPermFail'))
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
      message.success(t('sys.role.permAssignSuccess'))
      permModalVisible.value = false
    } else {
      message.error(res.message || t('sys.role.permAssignFail'))
    }
  } catch (e: any) {
    message.error(e?.message || t('common.error'))
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
  align-items: center;
  flex-wrap: wrap;
}
.filter-label {
  font-size: 14px;
  color: var(--fg-secondary);
  white-space: nowrap;
}
/* 表格行不换行；操作按钮单行不换行 */
:deep(.ant-table-cell) {
  white-space: nowrap;
}
.perm-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.perm-tree {
  max-height: 460px;
  overflow: auto;
}
.tree-node {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.node-title {
  font-weight: 500;
}
.perm-code {
  font-size: 11px;
  color: var(--fg-muted);
  margin-left: 6px;
}
</style>
