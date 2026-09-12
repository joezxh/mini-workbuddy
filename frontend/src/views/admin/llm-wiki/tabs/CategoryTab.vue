<template>
  <div>
    <a-button type="primary" @click="openCreate">新建分类</a-button>
    <a-tree
      :tree-data="treeData"
      :field-names="{ title: 'name', key: 'id', children: 'children' }"
      default-expand-all
      style="margin-top: 12px; background: #fff; padding: 12px; border-radius: 6px"
    >
      <template #title="{ name, id }">
        <span>{{ name }}</span>
        <a style="margin-left: 12px" @click.stop="openEdit(id)">编辑</a>
        <a-popconfirm title="确认删除?" @confirm="remove(id)">
          <a danger style="margin-left: 8px" @click.stop>删除</a>
        </a-popconfirm>
      </template>
    </a-tree>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? '编辑分类' : '新建分类'"
      @ok="save"
      :confirm-loading="saving"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="分类名称" />
        </a-form-item>
        <a-form-item label="父级分类">
          <a-tree-select
            v-model:value="form.parent_id"
            :tree-data="treeData"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="顶级分类"
            allow-clear
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getCategoryTree, createCategory, updateCategory, deleteCategory } from '@/api/wiki.ts'

const treeData = ref<any[]>([])
const modalOpen = ref(false)
const saving = ref(false)
const editing = ref<number | null>(null)
const form = ref({ name: '', parent_id: null as number | null })

async function reload() {
  try {
    const res = await getCategoryTree()
    treeData.value = res || []
  } catch (e) {
    message.error('加载分类失败')
  }
}
function openCreate() {
  editing.value = null
  form.value = { name: '', parent_id: null }
  modalOpen.value = true
}
function openEdit(id: number) {
  editing.value = id
  const node = findNode(treeData.value, id)
  form.value = { name: node?.name || '', parent_id: node?.parent_id || null }
  modalOpen.value = true
}
function findNode(list: any[], id: number): any {
  for (const n of list) {
    if (n.id === id) return n
    if (n.children) {
      const f = findNode(n.children, id)
      if (f) return f
    }
  }
  return null
}
async function save() {
  if (!form.value.name.trim()) {
    message.warning('请输入名称')
    return
  }
  saving.value = true
  try {
    const payload = { name: form.value.name, parent_id: form.value.parent_id || undefined }
    if (editing.value) await updateCategory(editing.value, payload)
    else await createCategory(payload)
    message.success('已保存')
    modalOpen.value = false
    reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
async function remove(id: number) {
  try {
    await deleteCategory(id)
    message.success('已删除')
    reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败（请先移除子分类/文章）')
  }
}
onMounted(reload)
</script>
