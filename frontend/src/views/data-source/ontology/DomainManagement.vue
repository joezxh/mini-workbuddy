<template>
  <div class="domain-mgmt">
    <div class="domain-mgmt__header">
      <h2 class="domain-mgmt__title">{{ t2('本体领域') }}</h2>
      <span class="domain-mgmt__hint">{{ t2('维护业务领域分组，本体与数据资产可按领域归类与筛选') }}</span>
      <a-button type="primary" class="domain-mgmt__new" @click="openCreate">{{ t2('新建领域') }}</a-button>
    </div>

    <a-table
      :data-source="rows"
      :columns="columns"
      :loading="loading"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">
            {{ record.status === 'active' ? t2('启用') : t2('停用') }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'reference_count'">
          {{ record.reference_count ?? 0 }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openEdit(record)">{{ t2('编辑') }}</a-button>
            <a-button
              type="link"
              size="small"
              @click="doToggle(record)"
            >{{ record.status === 'active' ? t2('停用') : t2('启用') }}</a-button>
            <a-popconfirm :title="t2('确认删除该领域？关联本体与表将变为未分类')" @confirm="doDelete(record)">
              <a-button type="link" size="small" danger>{{ t2('删除') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="formOpen"
      :title="editingId ? t2('编辑领域') : t2('新建领域')"
      :confirm-loading="saving"
      @ok="submit"
    >
      <a-form layout="vertical">
        <a-form-item :label="t2('编码 code')" required>
          <a-input v-model:value="form.code" :placeholder="t2('租户内唯一，如 hr / supply_chain')" />
        </a-form-item>
        <a-form-item :label="t2('名称')" required>
          <a-input v-model:value="form.name" :placeholder="t2('如 HR人力资源 / 供应链管理')" />
        </a-form-item>
        <a-form-item :label="t2('说明')">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t2('排序')">
          <a-input-number v-model:value="form.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t2('状态')">
          <a-select v-model:value="form.status">
            <a-select-option value="active">{{ t2('启用') }}</a-select-option>
            <a-select-option value="disabled">{{ t2('停用') }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/** 本体领域字典管理：列表 / 新建 / 编辑 / 启停 / 删除（后端 /api/v1/dataops/domains）。 */
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { createDomain, deleteDomain, listDomains, toggleDomain, updateDomain } from '@/api/dataops'
import { t2 } from './ontologyText'

const loading = ref(false)
const rows = ref<any[]>([])
const formOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ code: '', name: '', description: '', sort_order: 0, status: 'active' })

const columns = [
  { title: t2('编码'), key: 'code', dataIndex: 'code', width: 140 },
  { title: t2('名称'), key: 'name', dataIndex: 'name' },
  { title: t2('说明'), key: 'description', dataIndex: 'description' },
  { title: t2('排序'), key: 'sort_order', dataIndex: 'sort_order', width: 70 },
  { title: t2('状态'), key: 'status', width: 90 },
  { title: t2('引用数'), key: 'reference_count', width: 80 },
  { title: t2('操作'), key: 'action', width: 200 },
]

async function load() {
  loading.value = true
  try {
    const resp: any = await listDomains()
    rows.value = Array.isArray(resp) ? resp : (resp?.items || [])
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.code = ''
  form.name = ''
  form.description = ''
  form.sort_order = 0
  form.status = 'active'
  formOpen.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  form.code = row.code || ''
  form.name = row.name || ''
  form.description = row.description || ''
  form.sort_order = row.sort_order ?? 0
  form.status = row.status || 'active'
  formOpen.value = true
}

async function submit() {
  if (!form.code || !form.name) {
    message.warning(t2('编码与名称必填'))
    return
  }
  saving.value = true
  try {
    const body = {
      code: form.code.trim(), name: form.name.trim(), description: form.description || undefined,
      sort_order: Number(form.sort_order || 0), status: form.status,
    }
    if (editingId.value) await updateDomain(editingId.value, body)
    else await createDomain(body)
    message.success(t2('已保存'))
    formOpen.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function doToggle(row: any) {
  await toggleDomain(row.id, row.status === 'active' ? 'disabled' : 'active')
  message.success(t2('状态已更新'))
  await load()
}

async function doDelete(row: any) {
  await deleteDomain(row.id)
  message.success(t2('已删除'))
  await load()
}

onMounted(load)
</script>

<style lang="less" scoped>
.domain-mgmt {
  display: flex;
  flex-direction: column;
  gap: 12px;
  &__header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 12px 0;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }
  &__title { margin: 0; font-size: 20px; font-weight: 600; color: var(--fg); }
  &__hint { font-size: 12px; color: var(--fg-mute, #888); flex: 1; }
}
</style>
