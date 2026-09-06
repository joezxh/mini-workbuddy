<template>
  <div class="dictionary-panel">
    <div class="panel-header">
      <h2>{{ t('sys.dictionary.title') }}</h2>
      <p class="description">{{ t('sys.dictionary.subtitle') }}</p>
    </div>

    <div class="dictionary-content">
      <!-- 左侧字典列表 -->
      <div class="dictionary-list">
        <div class="list-header">
          <span class="title">{{ t('sys.dictionary.listTitle') }}</span>
          <a-button type="primary" size="small" @click="showAddDictModal">
            <template #icon><PlusOutlined /></template>
            {{ t('sys.dictionary.addDict') }}
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
                  {{ dict.dict_type === 'system' ? t('sys.dictionary.systemType') : t('sys.dictionary.businessType') }}
                </a-tag>
                <a-badge :count="dict.items?.length || 0" :number-style="{ backgroundColor: 'var(--ok)' }" />
                <a-space size="small" @click.stop>
                  <a-button type="link" size="small" @click.stop="showEditDictModal(dict)">{{ t('sys.dictionary.edit') }}</a-button>
                  <a-popconfirm
                    :title="t('sys.dictionary.deleteDictConfirm')"
                    :ok-text="t('sys.dictionary.deleteDict')"
                    :cancel-text="t('common.cancel')"
                    @confirm="deleteDict(dict)"
                  >
                    <a-button
                      type="link"
                      danger
                      size="small"
                      :disabled="dict.dict_type === 'system'"
                    >{{ t('sys.dictionary.delete') }}</a-button>
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
              :show-total="(total: number) => t('common.total', { total })"
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
          <p>{{ t('sys.dictionary.selectHint') }}</p>
        </div>

        <div v-else class="items-container">
          <div class="items-header">
            <div class="header-info">
              <h3>{{ selectedDict.dict_name }}</h3>
              <p class="dict-description">{{ selectedDict.description || t('sys.dictionary.noDescription') }}</p>
            </div>
            <div class="header-actions">
              <a-button type="primary" @click="showAddItemModal">
                <template #icon><PlusOutlined /></template>
                {{ t('sys.dictionary.addItem') }}
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
            :pagination="itemTablePagination"
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
                  <a-button type="link" size="small" @click="editItem(record)">{{ t('sys.dictionary.edit') }}</a-button>
                  <a-popconfirm
                    :title="t('sys.dictionary.deleteItemConfirm')"
                    :ok-text="t('common.confirm')"
                    :cancel-text="t('common.cancel')"
                    @confirm="deleteItem(record)"
                  >
                    <a-button type="link" danger size="small">{{ t('sys.dictionary.delete') }}</a-button>
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
      :title="editingItem ? t('sys.dictionary.editDictItem') : t('sys.dictionary.addDictItem')"
      width="600px"
      @ok="saveItem"
    >
      <a-form :model="itemForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('sys.dictionary.labelItemCode')" required>
          <a-input v-model:value="itemForm.item_code" :disabled="!!editingItem" :placeholder="t('sys.dictionary.placeholderItemCode')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelItemName')" required>
          <a-input v-model:value="itemForm.item_name" :placeholder="t('sys.dictionary.placeholderItemName')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelItemValue')">
          <a-input v-model:value="itemForm.item_value" :placeholder="t('sys.dictionary.placeholderItemValue')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelColor')">
          <a-input v-model:value="itemForm.color" placeholder="#1890ff">
            <template #addonAfter>
              <input type="color" v-model="itemForm.color" style="border: none; cursor: pointer" />
            </template>
          </a-input>
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelIcon')">
          <a-input v-model:value="itemForm.icon" :placeholder="t('sys.dictionary.placeholderItemName')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelSort')">
          <a-input-number v-model:value="itemForm.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelIsActive')">
          <a-switch v-model:checked="itemForm.is_active" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelRemark')">
          <a-textarea v-model:value="itemForm.remark" :rows="3" :placeholder="t('sys.dictionary.placeholderRemark')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加字典弹窗 -->
    <a-modal
      v-model:open="dictModalVisible"
      :title="editingDict ? t('sys.dictionary.editDict') : t('sys.dictionary.addDictTitle')"
      width="600px"
      @ok="saveDict"
      :confirm-loading="dictSaving"
    >
      <a-form :model="dictForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('sys.dictionary.labelDictCode')" required>
          <a-input v-model:value="dictForm.dict_code" :placeholder="t('sys.dictionary.placeholderDictCode')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelDictName')" required>
          <a-input v-model:value="dictForm.dict_name" :placeholder="t('sys.dictionary.placeholderDictName')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelDictType')" required>
          <a-select v-model:value="dictForm.dict_type" :placeholder="t('sys.dictionary.placeholderDictType')">
            <a-select-option value="system">{{ t('sys.dictionary.systemDict') }}</a-select-option>
            <a-select-option value="business">{{ t('sys.dictionary.businessDict') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelDescription')">
          <a-textarea v-model:value="dictForm.description" :rows="3" :placeholder="t('sys.dictionary.placeholderDescription')" />
        </a-form-item>
        <a-form-item :label="t('sys.dictionary.labelSort')">
          <a-input-number v-model:value="dictForm.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

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
const itemTablePagination = computed(() => ({
  pageSize: 10,
  showTotal: (total: number) => t('common.total', { total })
}))

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
const itemColumns = computed(() => [
  { title: t('sys.dictionary.colItemName'), dataIndex: 'item_name', key: 'item_name', width: 200 },
  { title: t('sys.dictionary.colCode'), dataIndex: 'item_code', key: 'item_code', width: 150 },
  { title: t('sys.dictionary.colValue'), dataIndex: 'item_value', key: 'item_value', width: 150 },
  { title: t('sys.dictionary.colColor'), dataIndex: 'color', key: 'color', width: 120 },
  { title: t('sys.dictionary.colSort'), dataIndex: 'sort_order', key: 'sort_order', width: 80 },
  { title: t('sys.dictionary.colStatus'), dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: t('sys.dictionary.colAction'), key: 'actions', width: 150, fixed: 'right' }
])

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
    message.error(error.message || t('sys.dictionary.loadFail'))
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
    message.error(error.message || t('sys.dictionary.loadItemsFail'))
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
      message.success(t('sys.dictionary.saveSuccess'))
    } else {
      // 新增
      await createDictionaryItem(selectedDict.value.dict_code, {
        ...itemForm.value,
        dict_code: selectedDict.value.dict_code
      })
      message.success(t('sys.dictionary.addSuccess'))
    }
    itemModalVisible.value = false
    await loadDictItems(selectedDict.value.dict_code)
  } catch (error: any) {
    message.error(error.message || t('sys.dictionary.saveFail'))
  }
}

// 切换字典项状态
const toggleItemStatus = async (item: DictionaryItem) => {
  if (!selectedDict.value) return

  try {
    await updateDictionaryItem(selectedDict.value.dict_code, item.item_code, {
      is_active: item.is_active
    })
    message.success(t('sys.dictionary.statusUpdateSuccess'))
  } catch (error: any) {
    message.error(error.message || t('sys.dictionary.statusUpdateFail'))
    item.is_active = !item.is_active // 回滚
  }
}

// 删除字典项
const deleteItem = async (item: DictionaryItem) => {
  if (!selectedDict.value) return

  try {
    await deleteDictionaryItem(selectedDict.value.dict_code, item.item_code)
    message.success(t('sys.dictionary.deleteSuccess'))
    await loadDictItems(selectedDict.value.dict_code)
  } catch (error: any) {
    message.error(error.message || t('sys.dictionary.deleteFail'))
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
      message.success(t('sys.dictionary.dictUpdateSuccess'))
    } else {
      await createDictionary(dictForm.value)
      message.success(t('sys.dictionary.addSuccess'))
    }
    dictModalVisible.value = false
    await loadDictionaries()
  } catch (error: any) {
    message.error(error.message || t('sys.dictionary.addFail'))
  } finally {
    dictSaving.value = false
  }
}

const deleteDict = async (dict: Dictionary) => {
  if (dict.dict_type === 'system') {
    message.warning(t('sys.dictionary.systemNoDelete'))
    return
  }
  try {
    await deleteDictionary(dict.dict_code)
    message.success(t('sys.dictionary.dictDeleteSuccess'))
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
    message.error(error.message || t('sys.dictionary.dictDeleteFail'))
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
