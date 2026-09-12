<template>
  <div class="tool-management">
    <a-tabs v-model:activeKey="activeTab" class="tool-tabs">
      <!-- ============ 工具列表 ============ -->
      <a-tab-pane key="tools" :tab="t('toolMgmt.tabTools')">
        <!-- 头部 -->
        <div class="panel-header">
          <div class="header-left">
            <h2>{{ t('toolMgmt.pageTitle') }}</h2>
            <p class="sub">{{ t('toolMgmt.pageDesc') }}</p>
          </div>
          <div class="header-actions">
            <a-button @click="handleRefreshCache">
              <template #icon><ReloadOutlined /></template>
              {{ t('toolMgmt.refreshCache') }}
            </a-button>
            <a-button type="primary" @click="showCreateModal">
              <template #icon><PlusOutlined /></template>
              {{ t('toolMgmt.addTool') }}
            </a-button>
          </div>
        </div>

        <!-- 搜索栏 -->
        <div class="search-bar">
          <a-input-search
            v-model:value="filters.toolKey"
            :placeholder="t('toolMgmt.searchToolKey')"
            allow-clear
            style="width:200px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-input-search
            v-model:value="filters.displayName"
            :placeholder="t('toolMgmt.searchDisplayName')"
            allow-clear
            style="width:200px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-select
            v-model:value="filters.category"
            :placeholder="t('toolMgmt.filterCategory')"
            allow-clear
            style="width:160px"
            @change="handleSearch"
          >
            <a-select-option v-for="c in categories" :key="c" :value="c">{{ c }}</a-select-option>
          </a-select>
          <a-select
            v-model:value="filters.type"
            :placeholder="t('toolMgmt.filterType')"
            allow-clear
            style="width:160px"
            @change="handleSearch"
          >
            <a-select-option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</a-select-option>
          </a-select>
          <a-select
            v-model:value="filters.status"
            :placeholder="t('toolMgmt.filterStatus')"
            allow-clear
            style="width:120px"
            @change="handleSearch"
          >
            <a-select-option value="enabled">{{ t('toolMgmt.enabled') }}</a-select-option>
            <a-select-option value="disabled">{{ t('toolMgmt.disabled') }}</a-select-option>
          </a-select>
          <a-button @click="handleReset"><ReloadOutlined /> {{ t('common.reset') }}</a-button>
        </div>

        <!-- 表格 -->
        <div class="table-wrapper">
        <BackTable
          row-key="id"
          size="small"
          :column="columns"
          :list="dataList"
          :is-loading="loading"
          :total="pagination.total"
          :page-size="pagination.pageSize"
          :current-page="pagination.current"
          :show-column="false"
          :border="false"
          @on-page-change="handlePageChange"
          @on-page-size-change="handlePageSizeChange"
        >
          <template #toolKey="{ record }">
            <a-tag color="geekblue">{{ record.toolKey }}</a-tag>
          </template>
          <template #category="{ record }">
            <span v-if="record.category">{{ record.category }}</span>
            <span v-else class="muted">-</span>
          </template>
          <template #isSystem="{ record }">
            <a-tag :color="record.isSystem ? 'blue' : 'default'">
              {{ record.isSystem ? t('toolMgmt.system') : t('toolMgmt.custom') }}
            </a-tag>
          </template>
          <template #description="{ record }">
            <a-tooltip :title="record.description">
              <span class="ellipsis">{{ record.description || '-' }}</span>
            </a-tooltip>
          </template>
          <template #status="{ record }">
            <a-switch
              :checked="record.status === 'enabled'"
              :disabled="record.isSystem"
              @change="() => toggleStatus(record)"
            />
          </template>
          <template #createdAt="{ record }">
            <span class="muted">{{ record.createdAt || '-' }}</span>
          </template>
          <template #actions="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="handleTest(record)">
                <PlayCircleOutlined /> {{ t('toolMgmt.test') }}
              </a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">
                <EditOutlined /> {{ t('common.edit') }}
              </a-button>
              <a-popconfirm
                :title="record.isSystem ? t('toolMgmt.deleteSystemForbidden') : t('toolMgmt.deleteToolConfirm')"
                :ok-text="t('common.confirm')"
                :cancel-text="t('common.cancel')"
                :disabled="record.isSystem"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" size="small" danger :disabled="record.isSystem">
                  <DeleteOutlined /> {{ t('common.delete') }}
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </BackTable>
        </div>
      </a-tab-pane>

      <!-- ============ 工具分组 ============ -->
      <a-tab-pane key="groups" :tab="t('toolMgmt.tabGroups')">
        <div class="panel-header">
          <div class="header-left">
            <h2>{{ t('toolMgmt.tabGroups') }}</h2>
            <p class="sub">{{ t('toolMgmt.groupsDesc') }}</p>
          </div>
          <a-button type="primary" @click="showGroupModal()">
            <template #icon><PlusOutlined /></template>
            {{ t('toolMgmt.addGroup') }}
          </a-button>
        </div>

        <div class="search-bar">
          <a-input-search
            v-model:value="groupFilters.name"
            :placeholder="t('toolMgmt.searchGroupName')"
            allow-clear
            style="width:220px"
            @search="loadGroups"
            @clear="loadGroups"
          />
          <a-button @click="loadGroups"><ReloadOutlined /> {{ t('toolMgmt.refresh') }}</a-button>
        </div>

        <div class="table-wrapper">
        <BackTable
          row-key="id"
          size="small"
          :column="groupColumns"
          :list="groupList"
          :is-loading="groupLoading"
          :total="groupPagination.total"
          :page-size="groupPagination.pageSize"
          :current-page="groupPagination.current"
          :show-column="false"
          :border="false"
          @on-page-change="handleGroupPageChange"
        >
          <template #isActive="{ record }">
            <a-tag :color="record.isActive ? 'success' : 'default'">
              {{ record.isActive ? t('toolMgmt.enabled') : t('toolMgmt.inactive') }}
            </a-tag>
          </template>
          <template #actions="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openMembers(record)">
                <ApartmentOutlined /> {{ t('toolMgmt.members') }}
              </a-button>
              <a-button type="link" size="small" @click="showGroupModal(record)">
                <EditOutlined /> {{ t('common.edit') }}
              </a-button>
              <a-popconfirm
                :title="t('toolMgmt.deleteGroupConfirm')"
                :ok-text="t('common.confirm')"
                :cancel-text="t('common.cancel')"
                @confirm="deleteGroup(record)"
              >
                <a-button type="link" size="small" danger>
                  <DeleteOutlined /> {{ t('common.delete') }}
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </BackTable>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- 工具新增/编辑弹窗 -->
    <ToolFormModal
      v-model:open="formVisible"
      :tool="editingTool"
      @success="onFormSuccess"
    />

    <!-- 工具测试弹窗 -->
    <ToolTestModal v-model:open="testVisible" :tool="testingTool" />

    <!-- 分组新增/编辑弹窗 -->
    <a-modal
      v-model:open="groupVisible"
      :title="editingGroup ? t('toolMgmt.editGroup') : t('toolMgmt.addGroup')"
      width="560px"
      :confirm-loading="groupSaving"
      @ok="submitGroup"
      @cancel="groupVisible = false"
    >
      <a-form :model="groupForm" layout="vertical" style="margin-top:16px">
        <a-form-item :label="t('toolMgmt.groupKeyLabel')" required>
          <a-input v-model:value="groupForm.name" placeholder="如：risk_intel_group" :disabled="!!editingGroup" />
        </a-form-item>
        <a-form-item :label="t('toolMgmt.colDisplayName')">
          <a-input v-model:value="groupForm.displayName" :placeholder="t('toolMgmt.displayNamePh')" />
        </a-form-item>
        <a-form-item :label="t('toolMgmt.colDescription')">
          <a-textarea v-model:value="groupForm.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('toolMgmt.instructionsLabel')">
          <a-textarea v-model:value="groupForm.instructions" :rows="2" :placeholder="t('toolMgmt.instructionsPlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('toolMgmt.enabledLabel')">
          <a-switch v-model:checked="groupForm.isActive" />
        </a-form-item>
        <a-form-item :label="t('toolMgmt.colSort')">
          <a-input-number v-model:value="groupForm.sort" :min="0" style="width:100%" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分组成员管理弹窗 -->
    <a-modal
      v-model:open="memberVisible"
      :title="t('toolMgmt.memberMgmtTitle')"
      width="720px"
      @cancel="memberVisible = false"
      @ok="memberVisible = false"
    >
      <template v-if="currentGroup">
        <a-alert :message="t('toolMgmt.currentGroup', { name: currentGroup.displayName || currentGroup.name })" style="margin-bottom:12px" />
        <div class="member-toolbar">
          <a-select
            v-model:value="addMemberKeys"
            mode="multiple"
            :placeholder="t('toolMgmt.selectToolsToAdd')"
            style="width:100%"
            :options="selectableTools"
            show-search
            option-filter-prop="label"
          />
          <a-button type="primary" @click="addMembers"><PlusOutlined /> {{ t('toolMgmt.add') }}</a-button>
        </div>
        <a-table
          row-key="id"
          size="small"
          :columns="memberColumns"
          :data-source="memberList"
          :pagination="false"
          style="margin-top:12px"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'actions'">
              <a-button type="link" size="small" danger @click="removeMember(record)">
                <DeleteOutlined /> {{ t('toolMgmt.remove') }}
              </a-button>
            </template>
          </template>
        </a-table>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined,
  PlayCircleOutlined, ApartmentOutlined
} from '@ant-design/icons-vue'
import BackTable from '@/components/common/BackTable/index.vue'
import ToolFormModal from './components/ToolFormModal.vue'
import ToolTestModal from './components/ToolTestModal.vue'
import {
  getToolPage, updateTool, deleteTool, refreshToolCache,
  getToolGroupPage, createToolGroup, updateToolGroup, deleteToolGroup,
  addGroupMembers, removeGroupMember, getGroupMembers,
  getToolSimpleList, type AiTool, type ToolGroup, type ToolSimpleItem
} from '@/api/ai-tool'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'

// ============ 工具列表 ============
const { t } = useI18n()
const activeTab = ref('tools')
const loading = ref(false)
const dataList = ref<AiTool[]>([])
const categories = ref<string[]>([])
const typeOptions = ref<{ value: string; label: string }[]>([])
const pagination = reactive({ current: 1, pageSize: 15, total: 0 })

const filters = reactive({
  toolKey: '',
  displayName: '',
  category: undefined as string | undefined,
  type: undefined as string | undefined,
  status: undefined as string | undefined
})

const columns = computed<any[]>(() => [
  { title: t('toolMgmt.colToolKey'), dataIndex: 'toolKey', key: 'toolKey', width: 160, align: 'center' as const },
  { title: t('toolMgmt.colDisplayName'), dataIndex: 'displayName', key: 'displayName', width: 160, align: 'center' as const },
  { title: t('toolMgmt.colCategory'), dataIndex: 'category', key: 'category', width: 120, align: 'center' as const },
  { title: t('toolMgmt.colIsSystem'), dataIndex: 'isSystem', key: 'isSystem', width: 100, align: 'center' as const },
  { title: t('toolMgmt.colDescription'), dataIndex: 'description', key: 'description', width: 220, align: 'center' as const },
  { title: t('toolMgmt.colStatus'), dataIndex: 'status', key: 'status', width: 90, align: 'center' as const },
  { title: t('toolMgmt.colSort'), dataIndex: 'sort', key: 'sort', width: 70, align: 'center' as const },
  { title: t('toolMgmt.colCreatedAt'), dataIndex: 'createdAt', key: 'createdAt', width: 170, align: 'center' as const },
  { title: t('toolMgmt.colActions'), key: 'actions', width: 220, fixed: 'right', align: 'center' as const }
])

const formVisible = ref(false)
const editingTool = ref<AiTool | null>(null)
const testVisible = ref(false)
const testingTool = ref<AiTool | null>(null)

onMounted(() => {
  loadCategories()
  loadToolTypes()
  loadData()
})

// 从工具分组加载分类（用于筛选下拉）
const loadCategories = async () => {
  try {
    const res = await getToolGroupPage({ page: 1, pageSize: 100 })
    categories.value = (res.data || [])
      .filter((g) => g.isActive)
      .map((g) => g.displayName || g.name)
  } catch { /* 使用空数组 */ }
}

// 从数据字典加载工具类型（用于筛选下拉）
const loadToolTypes = async () => {
  try {
    const items = await getDictionaryItems('tool_type')
    typeOptions.value = (items || [])
      .filter((item: DictionaryItem) => item.is_active)
      .map((item: DictionaryItem) => ({ value: item.item_code, label: item.item_name }))
  } catch {
    // 兜底
    typeOptions.value = [
      { value: 'custom', label: t('toolMgmt.typeCustom') },
      { value: 'agentscope_builtin', label: t('toolMgmt.typeBuiltin') },
      { value: 'custom_dev', label: t('toolMgmt.typeCustomDev') }
    ]
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getToolPage({
      toolKey: filters.toolKey || undefined,
      displayName: filters.displayName || undefined,
      category: filters.category,
      type: filters.type,
      status: filters.status,
      page: pagination.current,
      pageSize: pagination.pageSize
    })
    dataList.value = res.data
    pagination.total = res.total
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.loadFailed'))
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.current = 1; loadData() }
const handleReset = () => {
  filters.toolKey = ''
  filters.displayName = ''
  filters.category = undefined
  filters.type = undefined
  filters.status = undefined
  pagination.current = 1
  loadData()
}
const handlePageChange = (page: number) => { pagination.current = page; loadData() }
const handlePageSizeChange = (size: number) => { pagination.current = 1; pagination.pageSize = size; loadData() }

const showCreateModal = () => { editingTool.value = null; formVisible.value = true }
const handleEdit = (record: AiTool) => {
  editingTool.value = record
  formVisible.value = true
}
const handleTest = (record: AiTool) => { testingTool.value = record; testVisible.value = true }
const onFormSuccess = () => { loadData() }

const toggleStatus = async (record: AiTool) => {
  try {
    await updateTool({ id: record.id, status: record.status === 'enabled' ? 'disabled' : 'enabled' })
    message.success(record.status === 'enabled' ? t('toolMgmt.disabledMsg') : t('toolMgmt.enabledMsg'))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.statusToggleFailed'))
  }
}

const handleDelete = async (record: AiTool) => {
  try {
    await deleteTool(record.id)
    message.success(t('toolMgmt.deleteSuccess'))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.deleteFailed'))
  }
}

const handleRefreshCache = async () => {
  try {
    const res = await refreshToolCache()
    message.success(t('toolMgmt.cacheRefreshed', { count: res.count }))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.cacheRefreshFailed'))
  }
}

// ============ 工具分组 ============
const groupLoading = ref(false)
const groupList = ref<ToolGroup[]>([])
const groupPagination = reactive({ current: 1, pageSize: 15, total: 0 })
const groupFilters = reactive({ name: '' })

const groupColumns = computed<any[]>(() => [
  { title: t('toolMgmt.groupKeyLabel'), dataIndex: 'name', key: 'name', width: 200, align: 'center' as const },
  { title: t('toolMgmt.colDisplayName'), dataIndex: 'displayName', key: 'displayName', width: 180, align: 'center' as const },
  { title: t('toolMgmt.colDescription'), dataIndex: 'description', key: 'description', width: 240, align: 'center' as const },
  { title: t('toolMgmt.toolCount'), dataIndex: 'toolCount', key: 'toolCount', width: 80, align: 'center' as const },
  { title: t('toolMgmt.colStatus'), dataIndex: 'isActive', key: 'isActive', width: 90, align: 'center' as const },
  { title: t('toolMgmt.colSort'), dataIndex: 'sort', key: 'sort', width: 70, align: 'center' as const },
  { title: t('toolMgmt.colActions'), key: 'actions', width: 200, fixed: 'right', align: 'center' as const }
])

const groupVisible = ref(false)
const groupSaving = ref(false)
const editingGroup = ref<ToolGroup | null>(null)
const groupForm = reactive({
  name: '', displayName: '', description: '', instructions: '', isActive: true, sort: 0
})

const memberVisible = ref(false)
const currentGroup = ref<ToolGroup | null>(null)
const memberList = ref<AiTool[]>([])
const memberColumns = computed<any[]>(() => [
  { title: t('toolMgmt.colToolKey'), dataIndex: 'toolKey', key: 'toolKey' },
  { title: t('toolMgmt.colDisplayName'), dataIndex: 'displayName', key: 'displayName' },
  { title: t('toolMgmt.colCategory'), dataIndex: 'category', key: 'category' },
  { title: t('toolMgmt.colActions'), key: 'actions', width: 100 }
])
const addMemberKeys = ref<string[]>([])
const selectableTools = ref<{ value: string; label: string }[]>([])

const loadGroups = async () => {
  groupLoading.value = true
  try {
    const res = await getToolGroupPage({ name: groupFilters.name || undefined, page: groupPagination.current, pageSize: groupPagination.pageSize })
    groupList.value = res.data
    groupPagination.total = res.total
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.loadGroupsFailed'))
  } finally {
    groupLoading.value = false
  }
}

const handleGroupPageChange = (page: number) => { groupPagination.current = page; loadGroups() }

const showGroupModal = (group?: ToolGroup) => {
  editingGroup.value = group || null
  if (group) {
    groupForm.name = group.name
    groupForm.displayName = group.displayName || ''
    groupForm.description = group.description || ''
    groupForm.instructions = group.instructions || ''
    groupForm.isActive = group.isActive
    groupForm.sort = group.sort
  } else {
    Object.assign(groupForm, { name: '', displayName: '', description: '', instructions: '', isActive: true, sort: 0 })
  }
  groupVisible.value = true
}

const submitGroup = async () => {
  if (!groupForm.name.trim()) { message.warning(t('toolMgmt.nameRequired')); return }
  groupSaving.value = true
  try {
    if (editingGroup.value) {
      await updateToolGroup({ id: editingGroup.value.id, ...groupForm })
      message.success(t('toolMgmt.updated'))
    } else {
      await createToolGroup({ ...groupForm })
      message.success(t('toolMgmt.created'))
    }
    groupVisible.value = false
    loadGroups()
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.saveFailed'))
  } finally {
    groupSaving.value = false
  }
}

const deleteGroup = async (record: ToolGroup) => {
  try {
    await deleteToolGroup(record.id)
    message.success(t('toolMgmt.deleteSuccess'))
    loadGroups()
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.deleteFailed'))
  }
}

const openMembers = async (group: ToolGroup) => {
  currentGroup.value = group
  memberVisible.value = true
  addMemberKeys.value = []
  try {
    const [members, simple] = await Promise.all([getGroupMembers(group.id), getToolSimpleList()])
    memberList.value = members
    const memberKeys = new Set(members.map((m) => m.toolKey))
    selectableTools.value = (simple as ToolSimpleItem[])
      .filter((tool) => !memberKeys.has(tool.toolKey))
      .map((tool) => ({ value: tool.toolKey, label: `${tool.displayName}（${tool.toolKey}）` }))
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.loadMembersFailed'))
  }
}

const addMembers = async () => {
  if (!currentGroup.value || addMemberKeys.value.length === 0) return
  try {
    await addGroupMembers(currentGroup.value.id, addMemberKeys.value)
    message.success(t('toolMgmt.addSuccess'))
    addMemberKeys.value = []
    await openMembers(currentGroup.value)
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.addFailed'))
  }
}

const removeMember = async (record: AiTool) => {
  if (!currentGroup.value) return
  try {
    await removeGroupMember(currentGroup.value.id, record.toolKey)
    message.success(t('toolMgmt.removeSuccess'))
    await openMembers(currentGroup.value)
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.removeFailed'))
  }
}
</script>

<style lang="less" scoped>
.tool-management {
  height: 100%;
  display: flex;
  flex-direction: column;
}

// 让 tabs 填满剩余高度，内部 flex 布局使 BackTable 分页栏可见
.tool-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;

  :deep(.ant-tabs-content-holder) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  :deep(.ant-tabs-content) {
    height: 100%;
  }

  :deep(.ant-tabs-tabpane) {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 4px 0 12px;
  flex-shrink: 0;

  h2 { font-size: 20px; font-weight: 700; color: var(--fg); margin: 0 0 4px 0; }
  .sub { font-size: 13px; color: var(--fg-secondary); margin: 0; }
  .header-actions { display: flex; gap: 10px; }
}

.search-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  background: var(--bg-surface);
  padding: 16px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 12px;
  flex-shrink: 0;
}

.ellipsis {
  display: inline-block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

// BackTable 容器：填满 tab-pane 剩余高度，使分页栏可见
.table-wrapper {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.muted { color: var(--fg-muted); }

.member-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}
</style>
