<template>
  <div>
    <a-button type="primary" @click="openCreate">{{ t('wikiMgmt.cat.create') }}</a-button>
    <a-tree
      :tree-data="treeData"
      :field-names="{ title: 'name', key: 'id', children: 'children' }"
      default-expand-all
      style="margin-top: 12px; background: #fff; padding: 12px; border-radius: 6px"
    >
      <template #title="{ name, id }">
        <span>{{ name }}</span>
        <a style="margin-left: 12px" @click.stop="openEdit(id)">{{ t('common.edit') }}</a>
        <a-popconfirm :title="t('wikiMgmt.deleteConfirm')" @confirm="remove(id)">
          <a danger style="margin-left: 8px" @click.stop>{{ t('common.delete') }}</a>
        </a-popconfirm>
      </template>
    </a-tree>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? t('wikiMgmt.cat.edit') : t('wikiMgmt.cat.create')"
      @ok="save"
      :confirm-loading="saving"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.common.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('wikiMgmt.cat.namePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('wikiMgmt.cat.parent')">
          <a-tree-select
            v-model:value="form.parent_id"
            :tree-data="treeData"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            :placeholder="t('wikiMgmt.cat.topLevel')"
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
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { getCategoryTree, createCategory, updateCategory, deleteCategory } from '@/api/wiki.ts'

const { t } = useI18n()
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
    message.error(t('wikiMgmt.cat.loadFailed'))
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
    message.warning(t('wikiMgmt.nameRequired'))
    return
  }
  saving.value = true
  try {
    const payload = { name: form.value.name, parent_id: form.value.parent_id || undefined }
    if (editing.value) await updateCategory(editing.value, payload)
    else await createCategory(payload)
    message.success(t('wikiMgmt.saved'))
    modalOpen.value = false
    reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('wikiMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}
async function remove(id: number) {
  try {
    await deleteCategory(id)
    message.success(t('kbMgmt.common.deleted'))
    reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('wikiMgmt.cat.deleteFailed'))
  }
}
onMounted(reload)
</script>
