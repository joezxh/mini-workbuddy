<template>
  <div class="voice-model-config">
    <div class="page-header">
      <div>
        <h2>语音模型配置</h2>
        <p class="desc">
          管理用于实时语音（调解语音 RTC）的模型与密钥。默认模型会被语音演示页与网关自动选用。
        </p>
      </div>
      <a-button type="primary" @click="openCreate">新增语音模型</a-button>
    </div>

    <a-alert
      v-if="defaultInfo && defaultInfo.configured"
      type="success"
      show-icon
      class="default-tip"
    >
      <template #message>
        当前默认语音模型：<b>{{ defaultInfo.model }}</b>（密钥：{{ defaultInfo.key_name }}）
      </template>
    </a-alert>
    <a-alert
      v-else-if="defaultInfo"
      type="warning"
      show-icon
      class="default-tip"
    >
      <template #message>尚未配置默认语音模型，请在下方设置一项为默认。</template>
    </a-alert>

    <a-table
      :columns="columns"
      :data-source="models"
      :loading="loading"
      row-key="id"
      size="middle"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'is_default'">
          <a-tag v-if="record.is_default" color="green">默认</a-tag>
          <span v-else>—</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.status === 1 ? 'blue' : 'default'">
            {{ record.status === 1 ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button
              v-if="!record.is_default"
              type="link"
              @click="setDefault(record)"
            >
              设为默认
            </a-button>
            <a-button type="link" @click="openEdit(record)">编辑</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :title="editId ? '编辑语音模型' : '新增语音模型'"
      @ok="save"
      @cancel="closeModal"
      :confirm-loading="saving"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="如：通义千问 Realtime" />
        </a-form-item>
        <a-form-item label="模型标识" required>
          <a-input v-model:value="form.model" placeholder="如：qwen-realtime" />
        </a-form-item>
        <a-form-item label="所属密钥" required>
          <a-select
            v-model:value="form.key_id"
            placeholder="选择 API Key"
            :options="keyOptions"
            show-search
            option-filter-prop="label"
          />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="form.sort" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item label="设为默认">
          <a-switch v-model:checked="form.is_default" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { VoiceModel, VoiceModelDefault } from '@/types/voice'
import {
  listVoiceModels,
  getVoiceModelDefault,
  upsertVoiceModel,
  setDefaultVoiceModel,
} from '@/api/voice'
import { getApiKeySimpleList } from '@/api/ai-apikey'

const loading = ref(false)
const saving = ref(false)
const models = ref<VoiceModel[]>([])
const defaultInfo = ref<VoiceModelDefault | null>(null)
const keyOptions = ref<{ label: string; value: number }[]>([])

const modalOpen = ref(false)
const editId = ref<number | null>(null)
const form = ref({
  name: '',
  model: '',
  key_id: undefined as number | undefined,
  sort: 0,
  is_default: false,
})

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '模型', dataIndex: 'model', key: 'model' },
  { title: '平台/密钥', key: 'key_name', customRender: (r: any) => r.record.key_name || r.record.platform || '—' },
  { title: '默认', key: 'is_default', width: 80 },
  { title: '状态', key: 'status', width: 90 },
  { title: '操作', key: 'action', width: 160 },
]

async function load() {
  loading.value = true
  try {
    const [m, d, keys] = await Promise.all([
      listVoiceModels(),
      getVoiceModelDefault(),
      getApiKeySimpleList(),
    ])
    models.value = m
    defaultInfo.value = d
    keyOptions.value = (keys as any[]).map((k) => ({
      label: `${k.name}（${k.platform}）`,
      value: k.id,
    }))
  } catch (e: any) {
    message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editId.value = null
  form.value = { name: '', model: '', key_id: undefined, sort: 0, is_default: false }
  modalOpen.value = true
}

function openEdit(record: VoiceModel) {
  editId.value = record.id
  form.value = {
    name: record.name,
    model: record.model,
    key_id: record.key_id,
    sort: record.sort,
    is_default: record.is_default,
  }
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
}

async function save() {
  if (!form.value.name || !form.value.model || form.value.key_id == null) {
    message.warning('请填写名称、模型与所属密钥')
    return
  }
  saving.value = true
  try {
    await upsertVoiceModel({
      id: editId.value ?? undefined,
      name: form.value.name,
      model: form.value.model,
      key_id: form.value.key_id,
      sort: form.value.sort,
      is_default: form.value.is_default,
      status: 1,
    })
    message.success('已保存')
    modalOpen.value = false
    await load()
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function setDefault(record: VoiceModel) {
  try {
    await setDefaultVoiceModel(record.id)
    message.success(`已将「${record.name}」设为默认`)
    await load()
  } catch (e: any) {
    message.error(e?.message || '设置失败')
  }
}

onMounted(load)
</script>

<style scoped>
.voice-model-config {
  padding: 8px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0 0 4px;
}
.desc {
  color: rgba(0, 0, 0, 0.45);
  margin: 0;
  font-size: 13px;
}
.default-tip {
  margin-bottom: 16px;
}
</style>
