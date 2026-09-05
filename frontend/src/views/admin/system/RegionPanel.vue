<template>
  <div class="region-panel">
    <div class="panel-header">
      <h2>行政区域管理</h2>
      <p class="description">浙江省行政区划数据，来源于 sys_region 表，支持逐级懒加载展开</p>
    </div>

    <div class="region-content">
      <!-- 统计卡片 -->
      <div class="stats-row">
        <div class="stat-card" v-for="stat in levelStats" :key="stat.level">
          <div class="stat-value">{{ stat.count }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>

      <!-- 主体：左侧树 + 右侧详情 -->
      <div class="main-body">
        <!-- 左侧树形 -->
        <div class="tree-panel">
          <div class="tree-toolbar">
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="搜索区域名称"
              allow-clear
              size="small"
              style="flex:1"
              @search="handleSearch"
            />
            <a-button size="small" @click="resetTree">
              <template #icon><ReloadOutlined /></template>
            </a-button>
          </div>

          <a-spin :spinning="rootLoading">
            <a-tree
              v-if="treeData.length > 0"
              :tree-data="treeData"
              :field-names="{ title: 'region_name', key: 'region_code', children: 'children' }"
              :expanded-keys="expandedKeys"
              :selected-keys="selectedKeys"
              :load-data="loadChildren"
              show-line
              @expand="handleExpand"
              @select="handleSelect"
            >
              <template #title="nodeData">
                <div class="tree-node" :class="{ loading: loadingNodes.has(nodeData.region_code) }">
                  <component :is="levelIcon[nodeData.region_level]" class="node-icon" />
                  <span class="node-name">{{ nodeData.region_name }}</span>
                  <a-tag :color="levelColor[nodeData.region_level]" size="small" class="node-tag">
                    {{ RegionLevelLabel[nodeData.region_level] }}
                  </a-tag>
                </div>
              </template>
            </a-tree>
            <a-empty v-else description="暂无数据" />
          </a-spin>
        </div>

        <!-- 右侧详情 -->
        <div class="detail-panel">
          <div v-if="!selectedRegion" class="detail-empty">
            <ApartmentOutlined style="font-size:48px;color:var(--fg-muted)" />
            <p>点击左侧区域查看详情</p>
          </div>
          <div v-else class="detail-content">
            <div class="detail-header">
              <div class="detail-title">
                <component :is="levelIcon[selectedRegion.region_level]" class="detail-icon" />
                <h3>{{ selectedRegion.region_name }}</h3>
                <a-tag :color="levelColor[selectedRegion.region_level]">
                  {{ RegionLevelLabel[selectedRegion.region_level] }}
                </a-tag>
              </div>
              <div class="detail-actions">
                <a-button size="small" type="primary" ghost @click="showEditModal">
                  <template #icon><EditOutlined /></template>
                  编辑
                </a-button>
                <a-button size="small" @click="showAddChildModal" :disabled="selectedRegion.region_level === 'street'">
                  <template #icon><PlusOutlined /></template>
                  新增子区域
                </a-button>
                <a-popconfirm
                  title="确定删除该区域及其所有子区域吗？"
                  ok-text="确定删除"
                  cancel-text="取消"
                  ok-type="danger"
                  @confirm="handleDelete"
                >
                  <a-button size="small" danger>
                    <template #icon><DeleteOutlined /></template>
                    删除
                  </a-button>
                </a-popconfirm>
              </div>
            </div>
            <a-descriptions :column="2" bordered size="small" class="detail-desc">
              <a-descriptions-item label="区域编码">
                <code class="code-text">{{ selectedRegion.region_code }}</code>
              </a-descriptions-item>
              <a-descriptions-item label="上级编码">
                <code class="code-text">{{ selectedRegion.parent_code || '-' }}</code>
              </a-descriptions-item>
              <a-descriptions-item label="行政级别">
                {{ RegionLevelLabel[selectedRegion.region_level] || selectedRegion.region_level }}
              </a-descriptions-item>
              <a-descriptions-item label="排序">
                {{ selectedRegion.sort_order }}
              </a-descriptions-item>
              <a-descriptions-item label="完整路径" :span="2">
                {{ selectedRegion.full_path || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="经度">
                {{ selectedRegion.longitude || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="纬度">
                {{ selectedRegion.latitude || '-' }}
              </a-descriptions-item>
            </a-descriptions>

            <!-- 下级区域列表 -->
            <div class="children-section" v-if="selectedChildren.length > 0">
              <div class="children-title">下级区域（{{ selectedChildren.length }}个）</div>
              <div class="children-grid">
                <div
                  v-for="child in selectedChildren"
                  :key="child.region_code"
                  class="child-item"
                  @click="selectChildRegion(child)"
                >
                  <a-tag :color="levelColor[child.region_level]" size="small">{{ RegionLevelLabel[child.region_level] }}</a-tag>
                  <span class="child-name">{{ child.region_name }}</span>
                  <code class="child-code">{{ child.region_code }}</code>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 编辑/新增弹窗 -->
  <a-modal
    v-model:open="modalVisible"
    :title="modalTitle"
    width="520px"
    :confirm-loading="modalLoading"
    @ok="handleModalOk"
    @cancel="modalVisible = false"
  >
    <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }" autocomplete="off">
      <a-form-item label="区域编码" required>
        <a-input v-model:value="form.region_code" :disabled="modalMode === 'edit'" placeholder="如：330102001000" />
      </a-form-item>
      <a-form-item label="区域名称" required>
        <a-input v-model:value="form.region_name" placeholder="如：西湖街道" />
      </a-form-item>
      <a-form-item label="上级编码">
        <a-input v-model:value="form.parent_code" :disabled="modalMode === 'add-child'" placeholder="父级区域编码" />
      </a-form-item>
      <a-form-item label="行政级别" required>
        <a-select v-model:value="form.region_level">
          <a-select-option v-for="(label, val) in RegionLevelLabel" :key="val" :value="val">{{ label }}</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="完整路径">
        <a-input v-model:value="form.full_path" placeholder="如：浙江省/杭州市/西湖区/西湖街道" />
      </a-form-item>
      <a-form-item label="排序">
        <a-input-number v-model:value="form.sort_order" :min="0" style="width:100%" />
      </a-form-item>
      <a-form-item label="经度">
        <a-input v-model:value="form.longitude" placeholder="如：120.153576" />
      </a-form-item>
      <a-form-item label="纬度">
        <a-input v-model:value="form.latitude" placeholder="如：30.287459" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  ApartmentOutlined,
  GlobalOutlined,
  BankOutlined,
  HomeOutlined,
  EnvironmentOutlined,
  EditOutlined,
  PlusOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import {
  getRegions, getRegionStats, createRegion, updateRegion, deleteRegion,
  RegionLevelLabel, type RegionItem
} from '@/api/region'

// ─── 类型扩展：带懒加载标记 ───────────────────────────────────────
interface TreeNode extends RegionItem {
  children?: TreeNode[]
  isLeaf?: boolean
}

// ─── 状态 ────────────────────────────────────────────────────────
const rootLoading = ref(false)
const treeData = ref<TreeNode[]>([])
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])
const selectedRegion = ref<TreeNode | null>(null)
const selectedChildren = ref<TreeNode[]>([])
const loadingNodes = ref<Set<string>>(new Set())
const searchKeyword = ref('')
const statsData = ref<Record<string, number>>({})

// ─── 弹窗状态 ────────────────────────────────────────────────────
type ModalMode = 'edit' | 'add-child'
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalMode = ref<ModalMode>('edit')
const modalTitle = ref('')
const form = ref({
  region_code: '',
  region_name: '',
  parent_code: '',
  region_level: 'street',
  full_path: '',
  sort_order: 0,
  longitude: '',
  latitude: ''
})

// 级别颜色
const levelColor: Record<string, string> = {
  province: 'red',
  city: 'orange',
  district: 'blue',
  street: 'green',
  community: 'purple'
}

// 级别图标
const levelIcon: Record<string, any> = {
  province: GlobalOutlined,
  city: BankOutlined,
  district: HomeOutlined,
  street: EnvironmentOutlined,
  community: EnvironmentOutlined
}

// ─── 统计卡片数据 ─────────────────────────────────────────────────
const levelStats = computed(() => {
  return Object.entries(RegionLevelLabel)
    .map(([level, label]) => ({ level, label, count: statsData.value[level] || 0 }))
    .filter(s => s.count > 0)
})

// ─── 初始化：只加载地市级 ─────────────────────────────────────────
const initTree = async () => {
  rootLoading.value = true
  try {
    const provinces = await getRegions(undefined)
    const cities = await getRegions('330000')
    loadStats()

    const provinceNode: TreeNode = {
      ...(provinces.find(p => p.region_code === '330000') || {
        region_id: 0,
        region_code: '330000',
        region_name: '浙江省',
        region_level: 'province',
        sort_order: 1
      }),
      children: cities.map(city => ({
        ...city,
        children: [],
        isLeaf: false
      })),
      isLeaf: false
    }
    treeData.value = [provinceNode]
    expandedKeys.value = ['330000']
  } catch (e: any) {
    message.error(e.message || '加载区域数据失败')
  } finally {
    rootLoading.value = false
  }
}

const loadStats = async () => {
  try {
    const data = await getRegionStats()
    statsData.value = data
  } catch {}
}

// ─── 懒加载子节点 ─────────────────────────────────────────────────
const loadChildren = (node: any): Promise<void> => {
  return new Promise(async (resolve) => {
    const treeNode: TreeNode = node.dataRef
    const code = treeNode.region_code

    if (treeNode.region_level === 'street') {
      treeNode.isLeaf = true
      resolve()
      return
    }

    loadingNodes.value = new Set([...loadingNodes.value, code])
    try {
      const children = await getRegions(code)
      if (children.length === 0) {
        treeNode.isLeaf = true
        treeNode.children = undefined
      } else {
        treeNode.children = children.map(child => ({
          ...child,
          children: child.region_level === 'street' ? undefined : [],
          isLeaf: child.region_level === 'street'
        }))
      }
      treeData.value = [...treeData.value]
    } catch (e: any) {
      message.error(`加载 ${treeNode.region_name} 下级失败`)
    } finally {
      const next = new Set(loadingNodes.value)
      next.delete(code)
      loadingNodes.value = next
      resolve()
    }
  })
}

const handleExpand = (keys: string[]) => {
  expandedKeys.value = keys
}

const handleSelect = async (keys: string[], { node }: any) => {
  if (!keys.length) return
  selectedKeys.value = keys
  const region: TreeNode = node.dataRef || node
  selectedRegion.value = region
  selectedChildren.value = []
  if (region.region_level !== 'street') {
    try {
      const children = await getRegions(region.region_code)
      selectedChildren.value = children
    } catch {}
  }
}

const selectChildRegion = async (child: TreeNode) => {
  selectedKeys.value = [child.region_code]
  selectedRegion.value = child
  selectedChildren.value = []
  if (child.region_level !== 'street') {
    try {
      const children = await getRegions(child.region_code)
      selectedChildren.value = children
    } catch {}
  }
  if (child.parent_code && !expandedKeys.value.includes(child.parent_code)) {
    expandedKeys.value = [...expandedKeys.value, child.parent_code]
  }
}

const handleSearch = async (val: string) => {
  if (!val.trim()) {
    resetTree()
    return
  }
  rootLoading.value = true
  try {
    const all = await getRegions(undefined)
    const kw = val.toLowerCase()
    const matched = all.filter(r =>
      r.region_name.includes(kw) || r.region_code.includes(kw)
    )
    if (matched.length === 0) {
      message.info('未找到匹配的区域')
      return
    }
    treeData.value = matched.map(r => ({ ...r, isLeaf: r.region_level === 'street' }))
    expandedKeys.value = []
  } catch (e: any) {
    message.error(e.message || '搜索失败')
  } finally {
    rootLoading.value = false
  }
}

const resetTree = () => {
  searchKeyword.value = ''
  initTree()
}

// ─── CRUD 操作 ────────────────────────────────────────────────────
const showEditModal = () => {
  if (!selectedRegion.value) return
  modalMode.value = 'edit'
  modalTitle.value = `编辑区域 - ${selectedRegion.value.region_name}`
  const r = selectedRegion.value
  form.value = {
    region_code: r.region_code,
    region_name: r.region_name,
    parent_code: r.parent_code || '',
    region_level: r.region_level,
    full_path: r.full_path || '',
    sort_order: r.sort_order,
    longitude: r.longitude || '',
    latitude: r.latitude || ''
  }
  modalVisible.value = true
}

const showAddChildModal = () => {
  if (!selectedRegion.value) return
  modalMode.value = 'add-child'
  modalTitle.value = `新增子区域 - 上级：${selectedRegion.value.region_name}`
  const levelOrder = ['province', 'city', 'district', 'street']
  const currentIdx = levelOrder.indexOf(selectedRegion.value.region_level)
  const nextLevel = levelOrder[Math.min(currentIdx + 1, levelOrder.length - 1)]
  form.value = {
    region_code: '',
    region_name: '',
    parent_code: selectedRegion.value.region_code,
    region_level: nextLevel,
    full_path: (selectedRegion.value.full_path || selectedRegion.value.region_name) + '/',
    sort_order: 0,
    longitude: '',
    latitude: ''
  }
  modalVisible.value = true
}

const handleDelete = async () => {
  if (!selectedRegion.value) return
  try {
    await deleteRegion(selectedRegion.value.region_code)
    message.success('删除成功')
    selectedRegion.value = null
    selectedChildren.value = []
    selectedKeys.value = []
    await initTree()
    loadStats()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

const handleModalOk = async () => {
  if (!form.value.region_code.trim() || !form.value.region_name.trim()) {
    message.warning('区域编码和名称为必填项')
    return
  }
  modalLoading.value = true
  try {
    if (modalMode.value === 'edit') {
      const updated = await updateRegion(form.value.region_code, form.value)
      // 更新当前选中节点数据
      if (selectedRegion.value) {
        Object.assign(selectedRegion.value, updated)
      }
      message.success('更新成功')
    } else {
      await createRegion(form.value)
      message.success('新增成功')
      // 刷新当前选中节点的子级
      if (selectedRegion.value) {
        selectedChildren.value = await getRegions(selectedRegion.value.region_code)
      }
    }
    modalVisible.value = false
    // 刷新树和统计
    await initTree()
    loadStats()
  } catch (e: any) {
    message.error(e.message || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

onMounted(() => {
  initTree()
})
</script>

<style lang="less" scoped>
.region-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  margin-bottom: 16px;
  h2 { font-size: 20px; font-weight: 600; color: var(--fg); margin: 0 0 6px 0; }
  .description { color: var(--fg-secondary); margin: 0; font-size: 13px; }
}

.region-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: hidden;
  min-height: 0;
}

.stats-row {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.stat-card {
  flex: 1;
  min-width: 90px;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
  position: relative;
  overflow: hidden;
  &::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent-cyan);
  }
  .stat-value { font-size: 24px; font-weight: 700; color: var(--accent-cyan); line-height: 1.2; }
  .stat-label { font-size: 12px; color: var(--fg-secondary); margin-top: 2px; }
}

.main-body {
  flex: 1;
  display: flex;
  gap: 14px;
  overflow: hidden;
  min-height: 0;
}

.tree-panel {
  width: 300px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tree-toolbar {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-glow);
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

:deep(.ant-spin-nested-loading) { flex: 1; overflow-y: auto; padding: 8px; }
:deep(.ant-spin-container) { height: 100%; }

.tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  .node-icon { font-size: 13px; color: var(--fg-muted); }
  .node-name { font-size: 13px; color: var(--fg); }
  .node-tag { font-size: 10px; transform: scale(0.9); }
  &.loading .node-name { color: var(--fg-muted); }
}

.detail-panel {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 8px;
  overflow-y: auto;
  padding: 20px;
}

.detail-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--fg-secondary);
  gap: 12px;
  p { font-size: 14px; margin: 0; }
}

.detail-content { display: flex; flex-direction: column; gap: 16px; }

.detail-header {
  .detail-title {
    display: flex;
    align-items: center;
    gap: 10px;
    .detail-icon { font-size: 22px; color: var(--accent-cyan); }
    h3 { font-size: 20px; font-weight: 600; color: var(--fg); margin: 0; }
  }
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  .detail-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}

.detail-desc { margin-top: 4px; }

.code-text {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: var(--accent-2);
}

.children-section {
  .children-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--fg-secondary);
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--divider);
  }
}

.children-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}

.child-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  &:hover {
    border-color: var(--accent-cyan);
    background: rgba(24,144,255,0.05);
  }
  .child-name { font-size: 13px; color: var(--fg); flex: 1; }
  .child-code {
    font-size: 10px;
    color: var(--fg-muted);
    font-family: 'Courier New', monospace;
  }
}

:deep(.ant-tree-switcher) { color: var(--accent-cyan); }
:deep(.ant-tree-treenode) { padding: 2px 0; }
:deep(.ant-tree-node-content-wrapper:hover) { background: rgba(24,144,255,0.06); }
:deep(.ant-tree-node-selected) { background: rgba(24,144,255,0.12) !important; }

:deep(.ant-table) {
  background: var(--bg-surface);
  .ant-table-thead > tr > th {
    background: var(--bg-base);
  }
  .ant-table-tbody > tr > td {
    background: var(--bg-surface);
  }
  .ant-table-tbody > tr:hover > td {
    background: var(--bg-hover) !important;
  }
}
</style>
