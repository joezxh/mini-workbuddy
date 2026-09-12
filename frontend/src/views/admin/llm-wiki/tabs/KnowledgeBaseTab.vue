<template>
  <div>
    <a-button type="primary" @click="openCreate">新建知识库</a-button>
    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      style="margin-top: 12px"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 1 ? 'green' : 'default'">
            {{ record.status === 1 ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="openEdit(record)">编辑</a>
          <a-divider type="vertical" />
          <a-popconfirm title="确认删除?" @confirm="remove(record)">
            <a danger>删除</a>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? '编辑知识库' : '新建知识库'"
      @ok="save"
      :confirm-loading="saving"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="知识库名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="3" placeholder="描述" />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="form.status">
            <a-radio :value="1">启用</a-radio>
            <a-radio :value="0">停用</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { listKnowledge, createKnowledge, updateKnowledge, deleteKnowledge } from '@/api/wiki.ts'

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '状态', key: 'status' },
  { title: '操作', key: 'action' },
]
const rows = ref<any[]>([])
const loading = ref(false)
const modalOpen = ref(false)
const saving = ref(false)
const editing = ref<number | null>(null)
const form = ref({ name: '', description: '', status: 1 })

async function reload() {
  loading.value = true
  try {
    const res = await listKnowledge()
    rows.value = res.items || res || []
  } catch (e) {
    message.error('加载知识库失败')
  } finally {
    loading.value = false
  }
}
function openCreate() {
  editing.value = null
  form.value = { name: '', description: '', status: 1 }
  modalOpen.value = true
}
function openEdit(r: any) {
  editing.value = r.id
  form.value = { name: r.name, description: r.description || '', status: r.status }
  modalOpen.value = true
}
async function save() {
  if (!form.value.name.trim()) {
    message.warning('请输入名称')
    return
  }
  saving.value = true
  try {
    if (editing.value) await updateKnowledge(editing.value, form.value)
    else await createKnowledge(form.value)
    message.success('已保存')
    modalOpen.value = false
    reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
async function remove(r: any) {
  try {
    await deleteKnowledge(r.id)
    message.success('已删除')
    reload()
  } catch (e) {
    message.error('删除失败')
  }
}
onMounted(reload)
</script>
