<template>
  <div class="menu-manager">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="queryParams">
        <a-form-item label="菜单名称">
          <a-input
            v-model:value="queryParams.name"
            placeholder="请输入菜单名称"
            allow-clear
            style="width: 200px"
            @press-enter="handleQuery"
          />
        </a-form-item>
        <a-form-item label="状态">
          <a-select
            v-model:value="queryParams.status"
            placeholder="请选择状态"
            allow-clear
            style="width: 150px"
          >
            <a-select-option :value="0">开启</a-select-option>
            <a-select-option :value="1">关闭</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleQuery">
              <template #icon><SearchOutlined /></template>
              搜索
            </a-button>
            <a-button @click="handleReset">
              <template #icon><ReloadOutlined /></template>
              重置
            </a-button>
            <a-button type="primary" @click="openForm('create')">
              <template #icon><PlusOutlined /></template>
              新增
            </a-button>
            <a-button @click="toggleExpandAll">
              <template #icon><SwapOutlined /></template>
              {{ isExpandAll ? '折叠' : '展开' }}
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </div>

    <!-- 树形表格 -->
    <a-table
      :columns="columns"
      :data-source="dataSource"
      :loading="loading"
      :pagination="false"
      :default-expand-all-rows="isExpandAll"
      :indent-size="20"
      row-key="id"
      size="middle"
      children-column-name="children"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div style="display: flex; align-items: center">
            <component
              :is="getIconComponent(record.icon)"
              v-if="record.icon"
              style="margin-right: 6px; font-size: 14px; color: var(--accent-cyan)"
            />
            <component
              :is="record.type === 1 ? FolderOutlined : FileOutlined"
              v-else
              style="margin-right: 6px; font-size: 14px; color: var(--accent-cyan)"
            />
            <span>{{ record.name }}</span>
            <a-tag :color="typeColor(record.type)" style="margin-left: 8px">{{ typeName(record.type) }}</a-tag>
          </div>
        </template>
        <template v-else-if="column.key === 'icon'">
          <span>{{ record.icon || '-' }}</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-switch
            :checked="record.status === 0"
            :loading="statusUpdating[record.id]"
            checked-children="开"
            un-checked-children="关"
            @change="(val: any) => handleStatusChange(record, val)"
          />
        </template>
        <template v-else-if="column.key === 'visible'">
          <a-tag :color="record.visible === 1 ? 'blue' : 'default'">
            {{ record.visible === 1 ? '显示' : '隐藏' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space :size="4">
            <a-button type="link" size="small" @click="openForm('update', record.id)">修改</a-button>
            <a-button type="link" size="small" @click="openForm('create', undefined, record.id)">新增</a-button>
            <a-popconfirm title="确认删除该菜单？子菜单也将一并删除。" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑菜单弹窗 -->
    <a-modal
      v-model:open="formVisible"
      :title="formType === 'update' ? '修改菜单' : '新增菜单'"
      :width="640"
      :confirm-loading="formLoading"
      :mask-closable="false"
      :destroy-on-close="true"
      @ok="submitForm"
      @cancel="formVisible = false"
      ok-text="确定"
      cancel-text="取消"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        :label-col="{ style: { width: '100px' } }"
        layout="horizontal"
      >
        <a-form-item label="上级菜单" name="parentId">
          <a-tree-select
            v-model:value="formData.parentId"
            :tree-data="menuTree"
            :field-names="{ children: 'children', label: 'name', value: 'id' }"
            tree-default-expand-all
            placeholder="请选择上级菜单"
            allow-clear
          />
        </a-form-item>

        <a-form-item label="菜单类型" name="type">
          <a-radio-group v-model:value="formData.type">
            <a-radio-button :value="1">目录</a-radio-button>
            <a-radio-button :value="2">菜单</a-radio-button>
            <a-radio-button :value="3">按钮</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="菜单名称" name="name">
          <a-input v-model:value="formData.name" placeholder="请输入菜单名称" allow-clear />
        </a-form-item>

        <a-form-item v-show="formData.type !== 3" label="菜单图标" name="icon">
          <a-select
            v-model:value="formData.icon"
            placeholder="请选择菜单图标"
            allow-clear
            show-search
            :filter-option="filterIcon"
            :dropdown-match-select-width="false"
            :dropdown-style="{ width: '420px', padding: '12px' }"
            :trigger-action="['click']"
          >
            <template #dropdownRender="{ menuNode: menu }">
              <component :is="menu" />
              <a-divider style="margin: 8px 0" />
              <div class="icon-grid">
                <div
                  v-for="icon in availableIcons"
                  :key="icon.name"
                  class="icon-item"
                  :class="{ selected: formData.icon === icon.name }"
                  :title="icon.name"
                  @click="selectIcon(icon.name)"
                >
                  <component :is="icon.component" />
                </div>
              </div>
            </template>
            <a-select-option :value="formData.icon" :disabled="true">
              <span style="display: flex; align-items: center">
                <component :is="getIconComponent(formData.icon)" v-if="formData.icon" style="margin-right: 6px" />
                {{ formData.icon || '请选择图标' }}
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item v-show="formData.type !== 3" label="路由地址" name="path">
          <a-input v-model:value="formData.path" placeholder="访问的路由地址，如 system/user" allow-clear />
        </a-form-item>

        <a-form-item v-show="formData.type === 2" label="组件路径" name="component">
          <a-input v-model:value="formData.component" placeholder="例如：system/user/index" allow-clear />
        </a-form-item>

        <a-form-item v-show="formData.type === 2" label="组件名称" name="componentName">
          <a-input v-model:value="formData.componentName" placeholder="例如：SystemUser" allow-clear />
        </a-form-item>

        <a-form-item v-show="formData.type === 3" label="权限标识" name="permission">
          <a-input v-model:value="formData.permission" placeholder="如：system:user:delete" allow-clear />
        </a-form-item>

        <a-form-item label="显示排序" name="sort">
          <a-input-number v-model:value="formData.sort" :min="0" :max="9999" style="width: 100%" />
        </a-form-item>

        <a-form-item label="菜单状态" name="status">
          <a-radio-group v-model:value="formData.status">
            <a-radio :value="0">开启</a-radio>
            <a-radio :value="1">关闭</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item v-show="formData.type !== 3" label="显示状态" name="visible">
          <a-radio-group v-model:value="formData.visible">
            <a-radio :value="1">显示</a-radio>
            <a-radio :value="0">隐藏</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item v-show="formData.type !== 3" label="总是显示" name="alwaysShow">
          <a-radio-group v-model:value="formData.alwaysShow">
            <a-radio :value="1">总是</a-radio>
            <a-radio :value="0">不是</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item v-show="formData.type === 2" label="缓存状态" name="keepAlive">
          <a-radio-group v-model:value="formData.keepAlive">
            <a-radio :value="1">缓存</a-radio>
            <a-radio :value="0">不缓存</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, computed, markRaw, type Component } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  ReloadOutlined,
  PlusOutlined,
  SwapOutlined,
  FolderOutlined,
  FileOutlined,
  SettingOutlined,
  DashboardOutlined,
  UserOutlined,
  DatabaseOutlined,
  RobotOutlined,
  ApiOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  CloudUploadOutlined,
  ApartmentOutlined,
  OrderedListOutlined,
  AlertOutlined,
  BankOutlined,
  EnvironmentOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  MessageOutlined,
  BulbOutlined,
  CommentOutlined,
  TagsOutlined,
  SafetyCertificateOutlined,
  MergeCellsOutlined,
  ReadOutlined,
  ToolOutlined,
  LinkOutlined,
  HomeOutlined,
  TeamOutlined,
  KeyOutlined,
  LockOutlined,
  BellOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  QuestionCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusSquareOutlined,
  MinusSquareOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  FilterOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
  DownloadOutlined,
  UploadOutlined,
  SaveOutlined,
  SyncOutlined,
  UndoOutlined,
  RedoOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CaretUpOutlined,
  CaretDownOutlined,
  CaretLeftOutlined,
  CaretRightOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
  MoreOutlined,
  LeftOutlined,
  RightOutlined,
  UpOutlined,
  DownOutlined,
  StepForwardOutlined,
  StepBackwardOutlined,
  FastForwardOutlined,
  FastBackwardOutlined,
  ShrinkOutlined,
  ArrowsAltOutlined,
  UpCircleOutlined,
  DownCircleOutlined,
  LeftCircleOutlined,
  RightCircleOutlined,
  PlaySquareOutlined,
  PauseCircleOutlined,
  ProfileOutlined,
  AccountBookOutlined,
  ContactsOutlined,
  CarryOutOutlined,
  CalendarOutlined,
  CloudOutlined,
  RocketOutlined,
  ShopOutlined,
  WalletOutlined,
  GiftOutlined,
  TrophyOutlined,
  BuildOutlined,
  ExperimentOutlined,
  BugOutlined,
  CrownOutlined,
  FlagOutlined,
  HeatMapOutlined,
  InteractionOutlined,
  FundOutlined,
  DollarOutlined,
  EuroOutlined,
  PoundOutlined,
  YuqueOutlined,
  CodeOutlined,
  CodepenOutlined,
  RedditOutlined,
  AlipayOutlined,
  DingdingOutlined,
  WeiboOutlined,
  GitlabOutlined,
  GithubOutlined,
  GoogleOutlined,
  FacebookOutlined,
  LinkedinOutlined,
  SkypeOutlined,
  DropboxOutlined,
  DribbbleOutlined,
  BehanceOutlined,
  MediumOutlined,
  AmazonOutlined,
  AntCloudOutlined,
  ZhihuOutlined,
} from '@ant-design/icons-vue'
import { getMenuList, getMenuSimpleList, getMenuDetail, createMenu, updateMenu, deleteMenu } from '@/api/admin'
import type { MenuItem, MenuForm } from '@/api/admin'

// ── 图标映射 ──────────────────────────────────────────────
const allIconComponents = [
  SettingOutlined, DashboardOutlined, UserOutlined, DatabaseOutlined,
  RobotOutlined, ApiOutlined, ClockCircleOutlined, GlobalOutlined,
  ThunderboltOutlined, PlayCircleOutlined, BarChartOutlined, CloudUploadOutlined,
  ApartmentOutlined, OrderedListOutlined, AlertOutlined, BankOutlined,
  EnvironmentOutlined, CloudServerOutlined, FileTextOutlined, FolderOpenOutlined,
  MessageOutlined, BulbOutlined, CommentOutlined, TagsOutlined,
  SafetyCertificateOutlined, MergeCellsOutlined, ReadOutlined, ToolOutlined,
  LinkOutlined, HomeOutlined, TeamOutlined, KeyOutlined, LockOutlined,
  BellOutlined, CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined,
  InfoCircleOutlined, QuestionCircleOutlined, StopOutlined, DeleteOutlined,
  EditOutlined, PlusSquareOutlined, MinusSquareOutlined, EyeOutlined, EyeInvisibleOutlined,
  FilterOutlined, SortAscendingOutlined, SortDescendingOutlined, DownloadOutlined,
  UploadOutlined, SaveOutlined, SyncOutlined, UndoOutlined, RedoOutlined,
  ArrowUpOutlined, ArrowDownOutlined, ArrowLeftOutlined, ArrowRightOutlined,
  CaretUpOutlined, CaretDownOutlined, CaretLeftOutlined, CaretRightOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, MenuOutlined, MoreOutlined,
  LeftOutlined, RightOutlined,
  UpOutlined, DownOutlined, StepForwardOutlined, StepBackwardOutlined,
  FastForwardOutlined, FastBackwardOutlined, ShrinkOutlined, ArrowsAltOutlined,
  UpCircleOutlined, DownCircleOutlined, LeftCircleOutlined, RightCircleOutlined,
  PlaySquareOutlined, PauseCircleOutlined, ProfileOutlined,
  AccountBookOutlined, ContactsOutlined, CarryOutOutlined, CalendarOutlined,
  CloudOutlined, RocketOutlined, ShopOutlined, WalletOutlined, GiftOutlined,
  TrophyOutlined, BuildOutlined, ExperimentOutlined, BugOutlined, CrownOutlined,
  FlagOutlined, HeatMapOutlined, InteractionOutlined, FundOutlined,
  DollarOutlined, EuroOutlined, PoundOutlined, YuqueOutlined, CodeOutlined,
  CodepenOutlined, RedditOutlined, WeiboOutlined, GitlabOutlined, GithubOutlined,
  GoogleOutlined, FacebookOutlined, LinkedinOutlined, SkypeOutlined, DropboxOutlined,
  DribbbleOutlined, BehanceOutlined, MediumOutlined, AmazonOutlined,
  AntCloudOutlined, ZhihuOutlined, AlipayOutlined, DingdingOutlined,
]

const iconMap: Record<string, Component> = {}
const availableIcons: { name: string; component: Component }[] = []

allIconComponents.forEach(icon => {
  const name = icon.displayName || icon.name
  iconMap[name] = markRaw(icon)
  availableIcons.push({ name, component: markRaw(icon) })
})

function getIconComponent(iconName?: string): Component {
  if (!iconName) return markRaw(FolderOutlined)
  return iconMap[iconName] || markRaw(FileOutlined)
}

function selectIcon(iconName: string) {
  formData.value.icon = iconName
}

function filterIcon(input: string, option: any) {
  return option.value?.toLowerCase().includes(input.toLowerCase())
}

function typeColor(type: number) {
  return type === 1 ? 'blue' : type === 2 ? 'green' : 'orange'
}
function typeName(type: number) {
  return type === 1 ? '目录' : type === 2 ? '菜单' : '按钮'
}

// ── 查询 ──────────────────────────────────────────────
const loading = ref(false)
const dataSource = ref<MenuItem[]>([])
const isExpandAll = ref(true)
const statusUpdating = reactive<Record<number, boolean>>({})

const queryParams = reactive<{ name?: string; status?: number }>({
  name: undefined,
  status: undefined,
})

const columns = [
  { title: '菜单名称', dataIndex: 'name', key: 'name', width: 260, fixed: 'left' as const },
  { title: '图标', dataIndex: 'icon', key: 'icon', width: 180, ellipsis: true },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 70 },
  { title: '权限标识', dataIndex: 'permission', key: 'permission', width: 200, ellipsis: true },
  { title: '组件路径', dataIndex: 'component', key: 'component', width: 200, ellipsis: true },
  { title: '显示', key: 'visible', width: 80 },
  { title: '状态', key: 'status', width: 90 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' as const },
]

async function loadData() {
  loading.value = true
  try {
    const res = await getMenuList({
      name: queryParams.name || undefined,
      status: queryParams.status,
    })
    if (res.code === 0) {
      dataSource.value = res.data || []
    }
  } catch (e: any) {
    message.error(`加载菜单失败：${e?.message || '未知错误'}`)
    dataSource.value = []
  } finally {
    loading.value = false
  }
}

function handleQuery() {
  loadData()
}

function handleReset() {
  queryParams.name = undefined
  queryParams.status = undefined
  loadData()
}

function toggleExpandAll() {
  isExpandAll.value = !isExpandAll.value
  // 重新加载数据以触发展开/折叠
  loadData()
}

async function handleStatusChange(record: MenuItem, val: boolean | string | number) {
  const newStatus = val === true || val === 'true' || val === 1 ? 0 : 1
  statusUpdating[record.id] = true
  try {
    const res = await updateMenu(record.id, { status: newStatus })
    if (res.code === 0) {
      record.status = newStatus
      message.success('状态已更新')
    } else {
      message.error(res.message || '状态更新失败')
    }
  } catch (e: any) {
    message.error(`状态更新失败：${e?.message || '未知错误'}`)
  } finally {
    statusUpdating[record.id] = false
  }
}

async function handleDelete(id: number) {
  try {
    const res = await deleteMenu(id)
    if (res.code === 0) {
      message.success('删除成功')
      loadData()
    } else {
      message.error(res.message || '删除失败')
    }
  } catch (e: any) {
    message.error(`删除失败：${e?.message || '未知错误'}`)
  }
}

// ── 表单弹窗 ──────────────────────────────────────────────
const formVisible = ref(false)
const formType = ref<'create' | 'update'>('create')
const formLoading = ref(false)
const formRef = ref()
const menuTree = ref<any[]>([])

function createDefaultForm(): MenuForm {
  return {
    name: '',
    permission: '',
    path: '',
    type: 2,
    sort: 0,
    parentId: 0,
    icon: '',
    component: '',
    componentName: '',
    status: 0,
    visible: 1,
    keepAlive: 0,
    alwaysShow: 0,
  }
}

const formData = ref<MenuForm>(createDefaultForm())

const formRules = computed(() => ({
  name: [{ required: true, message: '菜单名称不能为空', trigger: 'blur' }],
  type: [{ required: true, message: '菜单类型不能为空', trigger: 'change' }],
  sort: [{ required: true, message: '排序不能为空', trigger: 'blur' }],
}))

async function loadMenuTree() {
  try {
    const res = await getMenuSimpleList()
    if (res.code === 0) {
      const list = res.data || []
      // 构建树形结构供 TreeSelect 使用
      menuTree.value = buildTreeSelect(list)
    }
  } catch {
    menuTree.value = [{ id: 0, name: '主类目', children: [] }]
  }
}

function buildTreeSelect(list: { id: number; parentId: number | null; name: string }[]): any[] {
  const map: Record<number, any> = {}
  const roots: any[] = []
  for (const item of list) {
    map[item.id] = { id: item.id, name: item.name, children: [] }
  }
  for (const item of list) {
    const pid = item.parentId || 0
    if (pid === 0 || !map[pid]) {
      roots.push(map[item.id])
    } else {
      map[pid].children.push(map[item.id])
    }
  }
  return [{ id: 0, name: '主类目', children: roots }]
}

async function openForm(type: 'create' | 'update', id?: number, parentId?: number) {
  formType.value = type
  formData.value = createDefaultForm()

  await loadMenuTree()

  if (parentId !== undefined) {
    formData.value.parentId = parentId
  }

  if (type === 'update' && id !== undefined) {
    formLoading.value = true
    try {
      const res = await getMenuDetail(id)
      if (res.code === 0) {
        const d = res.data
        formData.value = {
          id: d.id,
          name: d.name || '',
          permission: d.permission || '',
          path: d.path || '',
          type: d.type || 2,
          sort: d.sort || 0,
          parentId: d.parentId || 0,
          icon: d.icon || '',
          component: d.component || '',
          componentName: d.componentName || '',
          status: d.status ?? 0,
          visible: d.visible ?? 1,
          keepAlive: d.keepAlive ?? 0,
          alwaysShow: d.alwaysShow ?? 0,
        }
      }
    } catch (e: any) {
      message.error(`加载菜单详情失败：${e?.message || '未知错误'}`)
    } finally {
      formLoading.value = false
    }
  }

  await nextTick()
  formVisible.value = true
}

// 将前端 camelCase 字段转为后端 snake_case
function toApiData(data: MenuForm): any {
  return {
    name: data.name,
    permission: data.permission,
    path: data.path,
    type: data.type,
    sort: data.sort,
    parent_id: data.parentId,
    icon: data.icon,
    component: data.component,
    component_name: data.componentName,
    status: data.status,
    visible: data.visible,
    keep_alive: data.keepAlive,
    always_show: data.alwaysShow,
  }
}

async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch (e: any) {
    const errorFields = e?.errorFields || []
    if (errorFields.length > 0) {
      const firstError = errorFields[0]
      const errorMsg = firstError.errors?.[0] || '表单验证失败'
      message.error(`验证失败：${errorMsg}`)
    } else {
      message.error('表单验证失败，请检查输入')
    }
    return
  }

  // 路径校验（不再校验 /）
  if (formData.value.type !== 3 && formData.value.path) {
    const isExternal = /^(https?:|mailto:|tel:)/.test(formData.value.path)
    if (!isExternal && formData.value.path.includes(' ')) {
      message.error('路径不能包含空格')
      return
    }
  }

  formLoading.value = true
  try {
    if (formType.value === 'create') {
      const res = await createMenu(toApiData(formData.value) as MenuForm)
      if (res.code === 0) {
        message.success('新增成功')
        formVisible.value = false
        loadData()
      } else {
        message.error(res.message || '新增失败')
      }
    } else {
      const res = await updateMenu(formData.value.id!, toApiData(formData.value))
      if (res.code === 0) {
        message.success('修改成功')
        formVisible.value = false
        loadData()
      } else {
        message.error(res.message || '修改失败')
      }
    }
  } catch (e: any) {
    const respData = e?.response?.data || {}
    const detail = respData.detail || respData.message || respData.msg
    const text = typeof detail === 'string' ? detail : (detail && detail.msg) || e?.message || '未知错误'
    message.error(`${formType.value === 'create' ? '新增' : '修改'}失败：${text}`)
  } finally {
    formLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.menu-manager {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.search-bar {
  padding: 16px 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 4px;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}

.icon-grid::-webkit-scrollbar {
  width: 6px;
}

.icon-grid::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 3px;
}

.icon-grid::-webkit-scrollbar-track {
  background: var(--bg-page);
}

.icon-item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
  color: var(--fg-secondary);
}

.icon-item:hover {
  background: var(--accent-soft);
  color: var(--accent);
}

.icon-item.selected {
  background: var(--accent);
  color: var(--fg-inverse);
}
</style>
