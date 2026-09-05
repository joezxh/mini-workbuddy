<template>
  <div class="tool-management">
    <a-tabs v-model:activeKey="activeTab" class="tool-tabs">
      <!-- ============ 工具列表 ============ -->
      <a-tab-pane key="tools" tab="工具列表">
        <!-- 头部 -->
        <div class="panel-header">
          <div class="header-left">
            <h2>工具管理</h2>
            <p class="sub">管理系统内置与自定义工具，支持分类筛选、状态切换、测试与缓存刷新</p>
          </div>
          <div class="header-actions">
            <a-button @click="handleRefreshCache">
              <template #icon><ReloadOutlined /></template>
              刷新缓存
            </a-button>
            <a-button type="primary" @click="showCreateModal">
              <template #icon><PlusOutlined /></template>
              新增工具
            </a-button>
          </div>
        </div>

        <!-- 搜索栏 -->
        <div class="search-bar">
          <a-input-search
            v-model:value="filters.toolKey"
            placeholder="搜索工具标识"
            allow-clear
            style="width:200px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-input-search
            v-model:value="filters.displayName"
            placeholder="搜索显示名称"
            allow-clear
            style="width:200px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-select
            v-model:value="filters.category"
            placeholder="分类筛选"
            allow-clear
            style="width:160px"
            @change="handleSearch"
          >
            <a-select-option v-for="c in categories" :key="c" :value="c">{{ c }}</a-select-option>
          </a-select>
          <a-select
            v-model:value="filters.type"
            placeholder="类型筛选"
            allow-clear
            style="width:160px"
            @change="handleSearch"
          >
            <a-select-option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</a-select-option>
          </a-select>
          <a-select
            v-model:value="filters.status"
            placeholder="状态筛选"
            allow-clear
            style="width:120px"
            @change="handleSearch"
          >
            <a-select-option value="enabled">启用</a-select-option>
            <a-select-option value="disabled">禁用</a-select-option>
          </a-select>
          <a-button @click="handleReset"><ReloadOutlined /> 重置</a-button>
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
              {{ record.isSystem ? '系统' : '自定义' }}
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
                <PlayCircleOutlined /> 测试
              </a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">
                <EditOutlined /> 编辑
              </a-button>
              <a-popconfirm
                :title="record.isSystem ? '系统内置工具不允许删除' : '确定删除该工具？'"
                ok-text="确定"
                cancel-text="取消"
                :disabled="record.isSystem"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" size="small" danger :disabled="record.isSystem">
                  <DeleteOutlined /> 删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </BackTable>
        </div>
      </a-tab-pane>

      <!-- ============ 工具分组 ============ -->
      <a-tab-pane key="groups" tab="工具分组">
        <div class="panel-header">
          <div class="header-left">
            <h2>工具分组</h2>
            <p class="sub">将多个工具组成协作组，供多 Agent 编排复用</p>
          </div>
          <a-button type="primary" @click="showGroupModal()">
            <template #icon><PlusOutlined /></template>
            新增分组
          </a-button>
        </div>

        <div class="search-bar">
          <a-input-search
            v-model:value="groupFilters.name"
            placeholder="搜索分组名称"
            allow-clear
            style="width:220px"
            @search="loadGroups"
            @clear="loadGroups"
          />
          <a-button @click="loadGroups"><ReloadOutlined /> 刷新</a-button>
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
              {{ record.isActive ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template #actions="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openMembers(record)">
                <ApartmentOutlined /> 成员
              </a-button>
              <a-button type="link" size="small" @click="showGroupModal(record)">
                <EditOutlined /> 编辑
              </a-button>
              <a-popconfirm
                title="确定删除该分组？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="deleteGroup(record)"
              >
                <a-button type="link" size="small" danger>
                  <DeleteOutlined /> 删除
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
      :title="editingGroup ? '编辑分组' : '新增分组'"
      width="560px"
      :confirm-loading="groupSaving"
      @ok="submitGroup"
      @cancel="groupVisible = false"
    >
      <a-form :model="groupForm" layout="vertical" style="margin-top:16px">
        <a-form-item label="分组标识" required>
          <a-input v-model:value="groupForm.name" placeholder="如：risk_intel_group" :disabled="!!editingGroup" />
        </a-form-item>
        <a-form-item label="显示名称">
          <a-input v-model:value="groupForm.displayName" placeholder="如：风险情报采集组" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="groupForm.description" :rows="2" />
        </a-form-item>
        <a-form-item label="协作指令">
          <a-textarea v-model:value="groupForm.instructions" :rows="2" placeholder="多 Agent 协作时的共享指令" />
        </a-form-item>
        <a-form-item label="是否启用">
          <a-switch v-model:checked="groupForm.isActive" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="groupForm.sort" :min="0" style="width:100%" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分组成员管理弹窗 -->
    <a-modal
      v-model:open="memberVisible"
      title="分组成员管理"
      width="720px"
      @cancel="memberVisible = false"
      @ok="memberVisible = false"
    >
      <template v-if="currentGroup">
        <a-alert :message="`当前分组：${currentGroup.displayName || currentGroup.name}`" style="margin-bottom:12px" />
        <div class="member-toolbar">
          <a-select
            v-model:value="addMemberKeys"
            mode="multiple"
            placeholder="选择工具加入分组"
            style="width:100%"
            :options="selectableTools"
            show-search
            option-filter-prop="label"
          />
          <a-button type="primary" @click="addMembers"><PlusOutlined /> 添加</a-button>
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
                <DeleteOutlined /> 移除
              </a-button>
            </template>
          </template>
        </a-table>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
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

const columns: any[] = [
  { title: '工具标识', dataIndex: 'toolKey', key: 'toolKey', width: 160, align: 'center' as const },
  { title: '显示名称', dataIndex: 'displayName', key: 'displayName', width: 160, align: 'center' as const },
  { title: '分类', dataIndex: 'category', key: 'category', width: 120, align: 'center' as const },
  { title: '系统标记', dataIndex: 'isSystem', key: 'isSystem', width: 100, align: 'center' as const },
  { title: '描述', dataIndex: 'description', key: 'description', width: 220, align: 'center' as const },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90, align: 'center' as const },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 70, align: 'center' as const },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 170, align: 'center' as const },
  { title: '操作', key: 'actions', width: 220, fixed: 'right', align: 'center' as const }
]

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
      { value: 'custom', label: '自定义' },
      { value: 'agentscope_builtin', label: 'AgentScope内置' },
      { value: 'custom_dev', label: '自定义开发' }
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
    message.error(e.message || '加载失败')
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
    message.success(record.status === 'enabled' ? '已禁用' : '已启用')
    loadData()
  } catch (e: any) {
    message.error(e.message || '状态切换失败')
  }
}

const handleDelete = async (record: AiTool) => {
  try {
    await deleteTool(record.id)
    message.success('删除成功')
    loadData()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

const handleRefreshCache = async () => {
  try {
    const res = await refreshToolCache()
    message.success(`缓存刷新成功，已加载 ${res.count} 个工具`)
    loadData()
  } catch (e: any) {
    message.error(e.message || '缓存刷新失败')
  }
}

// ============ 工具分组 ============
const groupLoading = ref(false)
const groupList = ref<ToolGroup[]>([])
const groupPagination = reactive({ current: 1, pageSize: 15, total: 0 })
const groupFilters = reactive({ name: '' })

const groupColumns: any[] = [
  { title: '分组标识', dataIndex: 'name', key: 'name', width: 200, align: 'center' as const },
  { title: '显示名称', dataIndex: 'displayName', key: 'displayName', width: 180, align: 'center' as const },
  { title: '描述', dataIndex: 'description', key: 'description', width: 240, align: 'center' as const },
  { title: '工具数', dataIndex: 'toolCount', key: 'toolCount', width: 80, align: 'center' as const },
  { title: '状态', dataIndex: 'isActive', key: 'isActive', width: 90, align: 'center' as const },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 70, align: 'center' as const },
  { title: '操作', key: 'actions', width: 200, fixed: 'right', align: 'center' as const }
]

const groupVisible = ref(false)
const groupSaving = ref(false)
const editingGroup = ref<ToolGroup | null>(null)
const groupForm = reactive({
  name: '', displayName: '', description: '', instructions: '', isActive: true, sort: 0
})

const memberVisible = ref(false)
const currentGroup = ref<ToolGroup | null>(null)
const memberList = ref<AiTool[]>([])
const memberColumns: any[] = [
  { title: '工具标识', dataIndex: 'toolKey', key: 'toolKey' },
  { title: '显示名称', dataIndex: 'displayName', key: 'displayName' },
  { title: '分类', dataIndex: 'category', key: 'category' },
  { title: '操作', key: 'actions', width: 100 }
]
const addMemberKeys = ref<string[]>([])
const selectableTools = ref<{ value: string; label: string }[]>([])

const loadGroups = async () => {
  groupLoading.value = true
  try {
    const res = await getToolGroupPage({ name: groupFilters.name || undefined, page: groupPagination.current, pageSize: groupPagination.pageSize })
    groupList.value = res.data
    groupPagination.total = res.total
  } catch (e: any) {
    message.error(e.message || '加载分组失败')
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
  if (!groupForm.name.trim()) { message.warning('请输入分组标识'); return }
  groupSaving.value = true
  try {
    if (editingGroup.value) {
      await updateToolGroup({ id: editingGroup.value.id, ...groupForm })
      message.success('更新成功')
    } else {
      await createToolGroup({ ...groupForm })
      message.success('创建成功')
    }
    groupVisible.value = false
    loadGroups()
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    groupSaving.value = false
  }
}

const deleteGroup = async (record: ToolGroup) => {
  try {
    await deleteToolGroup(record.id)
    message.success('删除成功')
    loadGroups()
  } catch (e: any) {
    message.error(e.message || '删除失败')
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
      .filter((t) => !memberKeys.has(t.toolKey))
      .map((t) => ({ value: t.toolKey, label: `${t.displayName}（${t.toolKey}）` }))
  } catch (e: any) {
    message.error(e.message || '加载成员失败')
  }
}

const addMembers = async () => {
  if (!currentGroup.value || addMemberKeys.value.length === 0) return
  try {
    await addGroupMembers(currentGroup.value.id, addMemberKeys.value)
    message.success('添加成功')
    addMemberKeys.value = []
    await openMembers(currentGroup.value)
  } catch (e: any) {
    message.error(e.message || '添加失败')
  }
}

const removeMember = async (record: AiTool) => {
  if (!currentGroup.value) return
  try {
    await removeGroupMember(currentGroup.value.id, record.toolKey)
    message.success('移除成功')
    await openMembers(currentGroup.value)
  } catch (e: any) {
    message.error(e.message || '移除失败')
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

  h2 { font-size: 20px; font-weight: 700; color: #1a1a1a; margin: 0 0 4px 0; }
  .sub { font-size: 13px; color: #8c8c8c; margin: 0; }
  .header-actions { display: flex; gap: 10px; }
}

.search-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  background: #fff;
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

.muted { color: #bfbfbf; }

.member-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}
</style>
