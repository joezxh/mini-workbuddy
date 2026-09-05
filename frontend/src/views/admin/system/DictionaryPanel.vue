<template>
  <div class="dictionary-panel">
    <div class="panel-header">
      <h2>系统字典管理</h2>
      <p class="description">管理系统中的字典数据，包括风险等级、处置状态、事件类型等</p>
    </div>

    <div class="dictionary-content">
      <!-- 左侧字典列表 -->
      <div class="dictionary-list">
        <div class="list-header">
          <span class="title">字典列表</span>
          <a-button type="primary" size="small" @click="showAddDictModal">
            <template #icon><PlusOutlined /></template>
            新增字典
          </a-button>
        </div>
        <a-spin :spinning="loading">
          <div class="dict-items">
            <div
              v-for="dict in dictionaries"
              :key="dict.dict_code"
              class="dict-item"
              :class="{ active: selectedDict?.dict_code === dict.dict_code }"
              @click="selectDictionary(dict)"
            >
              <div class="dict-info">
                <div class="dict-name">{{ dict.dict_name }}</div>
              </div>
              <div class="dict-meta">
                <a-tag :color="dict.dict_type === 'system' ? 'blue' : 'green'" size="small">
                  {{ dict.dict_type === 'system' ? '系统' : '业务' }}
                </a-tag>
                <a-badge :count="dict.items?.length || 0" :number-style="{ backgroundColor: 'var(--ok)' }" />
                <a-space size="small" @click.stop>
                  <a-button type="link" size="small" @click.stop="showEditDictModal(dict)">编辑</a-button>
                  <a-popconfirm
                    title="确认删除该字典吗？删除后对应字典项也将删除"
                    ok-text="删除"
                    cancel-text="取消"
                    @confirm="deleteDict(dict)"
                  >
                    <a-button
                      type="link"
                      danger
                      size="small"
                      :disabled="dict.dict_type === 'system'"
                    >删除</a-button>
                  </a-popconfirm>
                </a-space>
              </div>
            </div>
          </div>
          <div class="dict-pagination">
            <a-pagination
              v-model:current="dictPagination.current"
              v-model:page-size="dictPagination.pageSize"
              :total="dictPagination.total"
              :show-size-changer="true"
              :page-size-options="['5','10', '15', '20', '30']"
              :show-total="(total: number, range: [number, number]) => `${range[0]}-${range[1]} / 共 ${total} 条`"
              size="small"
              @change="loadDictionaries"
              @showSizeChange="onDictPageSizeChange"
            />
          </div>
        </a-spin>
      </div>

      <!-- 右侧字典项管理 -->
      <div class="dictionary-items">
        <div v-if="!selectedDict" class="empty-state">
          <DatabaseOutlined style="font-size: 48px; color: var(--fg-muted)" />
          <p>请选择左侧字典查看详情</p>
        </div>

        <div v-else class="items-container">
          <div class="items-header">
            <div class="header-info">
              <h3>{{ selectedDict.dict_name }}</h3>
              <p class="dict-description">{{ selectedDict.description || '暂无描述' }}</p>
            </div>
            <div class="header-actions">
              <a-button type="primary" @click="showAddItemModal">
                <template #icon><PlusOutlined /></template>
                添加字典项
              </a-button>
              <a-button @click="refreshDictItems">
                <template #icon><ReloadOutlined /></template>
              </a-button>
            </div>
          </div>

          <a-table
            :columns="itemColumns"
            :data-source="dictItems"
            :loading="itemsLoading"
            :pagination="{ pageSize: 10 }"
            row-key="item_id"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'item_name'">
                <div class="item-name-cell">
                  <span v-if="record.color" class="color-dot" :style="{ backgroundColor: record.color }"></span>
                  <span v-if="record.icon" class="item-icon">{{ record.icon }}</span>
                  <span>{{ record.item_name }}</span>
                </div>
              </template>

              <template v-if="column.key === 'color'">
                <a-tag v-if="record.color" :color="record.color">
                  {{ record.color }}
                </a-tag>
                <span v-else class="text-muted">-</span>
              </template>

              <template v-if="column.key === 'is_active'">
                <a-switch
                  v-model:checked="record.is_active"
                  size="small"
                  @change="toggleItemStatus(record)"
                />
              </template>

              <template v-if="column.key === 'actions'">
                <a-space>
                  <a-button type="link" size="small" @click="editItem(record)">编辑</a-button>
                  <a-popconfirm
                    title="确定删除此字典项吗？"
                    ok-text="确定"
                    cancel-text="取消"
                    @confirm="deleteItem(record)"
                  >
                    <a-button type="link" danger size="small">删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </div>

    <!-- 添加/编辑字典项弹窗 -->
    <a-modal
      v-model:open="itemModalVisible"
      :title="editingItem ? '编辑字典项' : '添加字典项'"
      width="600px"
      @ok="saveItem"
    >
      <a-form :model="itemForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="字典项编码" required>
          <a-input v-model:value="itemForm.item_code" :disabled="!!editingItem" placeholder="请输入字典项编码" />
        </a-form-item>
        <a-form-item label="字典项名称" required>
          <a-input v-model:value="itemForm.item_name" placeholder="请输入字典项名称" />
        </a-form-item>
        <a-form-item label="字典项值">
          <a-input v-model:value="itemForm.item_value" placeholder="请输入字典项值" />
        </a-form-item>
        <a-form-item label="颜色">
          <a-input v-model:value="itemForm.color" placeholder="#1890ff">
            <template #addonAfter>
              <input type="color" v-model="itemForm.color" style="border: none; cursor: pointer" />
            </template>
          </a-input>
        </a-form-item>
        <a-form-item label="图标">
          <a-input v-model:value="itemForm.icon" placeholder="请输入图标" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="itemForm.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item label="是否启用">
          <a-switch v-model:checked="itemForm.is_active" />
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="itemForm.remark" :rows="3" placeholder="请输入备注" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加字典弹窗 -->
    <a-modal
      v-model:open="dictModalVisible"
      :title="editingDict ? '编辑字典' : '添加字典'"
      width="600px"
      @ok="saveDict"
      :confirm-loading="dictSaving"
    >
      <a-form :model="dictForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="字典编码" required>
          <a-input v-model:value="dictForm.dict_code" placeholder="请输入字典编码" />
        </a-form-item>
        <a-form-item label="字典名称" required>
          <a-input v-model:value="dictForm.dict_name" placeholder="请输入字典名称" />
        </a-form-item>
        <a-form-item label="字典类型" required>
          <a-select v-model:value="dictForm.dict_type" placeholder="请选择字典类型">
            <a-select-option value="system">系统字典</a-select-option>
            <a-select-option value="business">业务字典</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="dictForm.description" :rows="3" placeholder="请输入描述" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="dictForm.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
  DatabaseOutlined
} from '@ant-design/icons-vue'
import {
  getDictionaries,
  getDictionary,
  createDictionary,
  updateDictionary,
  deleteDictionary,
  createDictionaryItem,
  updateDictionaryItem,
  deleteDictionaryItem,
  type Dictionary,
  type DictionaryItem
} from '@/api/dictionary'

// 数据
const loading = ref(false)
const itemsLoading = ref(false)
const dictionaries = ref<(Dictionary & { items?: DictionaryItem[] })[]>([])
const selectedDict = ref<Dictionary | null>(null)
const dictItems = ref<DictionaryItem[]>([])
const dictPagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
})

// 弹窗
const itemModalVisible = ref(false)
const dictModalVisible = ref(false)
const editingItem = ref<DictionaryItem | null>(null)
const editingDict = ref<Dictionary | null>(null)
const dictSaving = ref(false)

// 表单
const itemForm = ref({
  item_code: '',
  item_name: '',
  item_value: '',
  color: '',
  icon: '',
  sort_order: 0,
  is_active: true,
  remark: ''
})

const dictForm = ref({
  dict_code: '',
  dict_name: '',
  dict_type: 'business',
  description: '',
  sort_order: 0
})

// 表格列
const itemColumns = [
  { title: '字典项名称', dataIndex: 'item_name', key: 'item_name', width: 200 },
  { title: '编码', dataIndex: 'item_code', key: 'item_code', width: 150 },
  { title: '值', dataIndex: 'item_value', key: 'item_value', width: 150 },
  { title: '颜色', dataIndex: 'color', key: 'color', width: 120 },
  { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right' }
]

// 加载字典列表
const loadDictionaries = async () => {
  try {
    loading.value = true
    const res = await getDictionaries({
      page: dictPagination.value.current,
      pageSize: dictPagination.value.pageSize
    })
    dictionaries.value = res.data
    dictPagination.value.total = res.total
    if (selectedDict.value) {
      const matched = res.data.find(d => d.dict_code === selectedDict.value?.dict_code)
      if (matched) selectedDict.value = matched
    }
  } catch (error: any) {
    message.error(error.message || '加载字典列表失败')
  } finally {
    loading.value = false
  }
}

const onDictPageSizeChange = (_page: number, pageSize: number) => {
  dictPagination.value.current = 1
  dictPagination.value.pageSize = pageSize
  loadDictionaries()
}

// 选择字典
const selectDictionary = async (dict: Dictionary) => {
  selectedDict.value = dict
  await loadDictItems(dict.dict_code)
}

// 加载字典项
const loadDictItems = async (dictCode: string) => {
  try {
    itemsLoading.value = true
    const data = await getDictionary(dictCode, true)
    dictItems.value = data.items || []
  } catch (error: any) {
    message.error(error.message || '加载字典项失败')
  } finally {
    itemsLoading.value = false
  }
}

// 刷新字典项
const refreshDictItems = () => {
  if (selectedDict.value) {
    loadDictItems(selectedDict.value.dict_code)
  }
}

// 显示添加字典项弹窗
const showAddItemModal = () => {
  editingItem.value = null
  itemForm.value = {
    item_code: '',
    item_name: '',
    item_value: '',
    color: '',
    icon: '',
    sort_order: 0,
    is_active: true,
    remark: ''
  }
  itemModalVisible.value = true
}

// 编辑字典项
const editItem = (item: DictionaryItem) => {
  editingItem.value = item
  itemForm.value = {
    item_code: item.item_code,
    item_name: item.item_name,
    item_value: item.item_value || '',
    color: item.color || '',
    icon: item.icon || '',
    sort_order: item.sort_order,
    is_active: item.is_active,
    remark: item.remark || ''
  }
  itemModalVisible.value = true
}

// 保存字典项
const saveItem = async () => {
  if (!selectedDict.value) return

  try {
    if (editingItem.value) {
      // 更新
      await updateDictionaryItem(
        selectedDict.value.dict_code,
        editingItem.value.item_code,
        itemForm.value
      )
      message.success('更新成功')
    } else {
      // 新增
      await createDictionaryItem(selectedDict.value.dict_code, {
        ...itemForm.value,
        dict_code: selectedDict.value.dict_code
      })
      message.success('添加成功')
    }
    itemModalVisible.value = false
    await loadDictItems(selectedDict.value.dict_code)
  } catch (error: any) {
    message.error(error.message || '保存失败')
  }
}

// 切换字典项状态
const toggleItemStatus = async (item: DictionaryItem) => {
  if (!selectedDict.value) return

  try {
    await updateDictionaryItem(selectedDict.value.dict_code, item.item_code, {
      is_active: item.is_active
    })
    message.success('状态更新成功')
  } catch (error: any) {
    message.error(error.message || '状态更新失败')
    item.is_active = !item.is_active // 回滚
  }
}

// 删除字典项
const deleteItem = async (item: DictionaryItem) => {
  if (!selectedDict.value) return

  try {
    await deleteDictionaryItem(selectedDict.value.dict_code, item.item_code)
    message.success('删除成功')
    await loadDictItems(selectedDict.value.dict_code)
  } catch (error: any) {
    message.error(error.message || '删除失败')
  }
}

// 显示添加字典弹窗
const showAddDictModal = () => {
  editingDict.value = null
  dictForm.value = {
    dict_code: '',
    dict_name: '',
    dict_type: 'business',
    description: '',
    sort_order: 0
  }
  dictModalVisible.value = true
}

const showEditDictModal = (dict: Dictionary) => {
  editingDict.value = dict
  dictForm.value = {
    dict_code: dict.dict_code,
    dict_name: dict.dict_name,
    dict_type: dict.dict_type,
    description: dict.description || '',
    sort_order: dict.sort_order || 0
  }
  dictModalVisible.value = true
}

// 保存字典
const saveDict = async () => {
  try {
    dictSaving.value = true
    if (editingDict.value) {
      await updateDictionary(editingDict.value.dict_code, {
        dict_name: dictForm.value.dict_name,
        dict_type: dictForm.value.dict_type,
        description: dictForm.value.description,
        sort_order: dictForm.value.sort_order
      })
      message.success('字典更新成功')
    } else {
      await createDictionary(dictForm.value)
      message.success('添加成功')
    }
    dictModalVisible.value = false
    await loadDictionaries()
  } catch (error: any) {
    message.error(error.message || '添加失败')
  } finally {
    dictSaving.value = false
  }
}

const deleteDict = async (dict: Dictionary) => {
  if (dict.dict_type === 'system') {
    message.warning('系统字典不允许删除')
    return
  }
  try {
    await deleteDictionary(dict.dict_code)
    message.success('字典删除成功')
    if (selectedDict.value?.dict_code === dict.dict_code) {
      selectedDict.value = null
      dictItems.value = []
    }
    // 当前页删空时回退一页
    if (dictionaries.value.length <= 1 && dictPagination.value.current > 1) {
      dictPagination.value.current -= 1
    }
    await loadDictionaries()
  } catch (error: any) {
    message.error(error.message || '字典删除失败')
  }
}

onMounted(() => {
  loadDictionaries()
})
</script>

<style lang="less" scoped>
.dictionary-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  margin-bottom: 20px;

  h2 {
    font-size: 20px;
    font-weight: 600;
    color: var(--fg);
    margin: 0 0 8px 0;
  }

  .description {
    color: var(--fg-secondary);
    margin: 0;
  }
}

.dictionary-content {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
  min-height: 0;
}

.dictionary-list {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.list-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-glow);
  display: flex;
  justify-content: space-between;
  align-items: center;

  .title {
    font-size: 16px;
    font-weight: 600;
    color: var(--fg);
  }
}

.dict-items {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: auto;
  padding: 8px;
}

.dict-pagination {
  padding: 8px 12px 12px;
  border-top: 1px solid var(--border-glow);
  display: flex;
  justify-content: flex-end;
}

.dict-item {
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  justify-content: space-between;
  align-items: center;

  &:hover {
    border-color: var(--accent-cyan);
    background: rgba(24, 144, 255, 0.05);
  }

  &.active {
    border-color: var(--accent-cyan);
    background: rgba(24, 144, 255, 0.1);
  }
}

.dict-info {
  flex: 1;
  min-width: 0;

  .dict-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--fg);
    margin-bottom: 4px;
  }

  .dict-code {
    font-size: 12px;
    color: var(--fg-secondary);
    font-family: 'Courier New', monospace;
  }
}

.dict-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dictionary-items {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--fg-secondary);

  p {
    margin-top: 16px;
    font-size: 14px;
  }
}

.items-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.items-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-glow);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;

  .header-info {
    h3 {
      font-size: 18px;
      font-weight: 600;
      color: var(--fg);
      margin: 0 0 4px 0;
    }

    .dict-description {
      font-size: 13px;
      color: var(--fg-secondary);
      margin: 0;
    }
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.item-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;

  .color-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .item-icon {
    font-size: 16px;
  }
}

.text-muted {
  color: var(--fg-muted);
}

:deep(.ant-table-wrapper) {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

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

