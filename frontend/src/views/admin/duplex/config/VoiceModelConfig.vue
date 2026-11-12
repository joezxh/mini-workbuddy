<template>
  <div class="voice-model-config">
    <div class="page-header">
      <div>
        <h2>语音模型配置</h2>
        <p class="desc">
          管理用于实时语音（全双工语音 RTC）的模型与密钥。模型清单严格取自各厂商官方发布的全双工语音大模型目录，默认模型会被语音演示页与网关自动选用。
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
        <template v-if="column.key === 'model'">
          <div>{{ record.model }}</div>
          <a-tag v-if="record.usable === false" color="red">不可用</a-tag>
          <a-tag v-else-if="record.usable" color="green">可用</a-tag>
        </template>
        <template v-else-if="column.key === 'is_default'">
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
      :width="600"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="如：通义千问 Realtime" />
        </a-form-item>

        <a-form-item label="所属密钥（厂商）" required>
          <a-select
            v-model:value="form.key_id"
            placeholder="选择 API Key"
            :options="keyOptions"
            show-search
            option-filter-prop="label"
            @change="onKeyChange"
          />
          <div v-if="currentProvider" class="provider-hint">
            <a-space size="small">
              <a-tag color="blue">{{ currentProvider.label }}</a-tag>
              <a :href="currentProvider.docs_url" target="_blank">官方文档</a>
              <a :href="currentProvider.api_key_url" target="_blank">申请 Key</a>
            </a-space>
          </div>
        </a-form-item>

        <a-form-item label="模型标识" required>
          <a-select
            v-model:value="form.model"
            placeholder="选择该厂商的全双工语音模型"
            :options="modelOptions"
            :disabled="!currentProvider"
            show-search
            option-filter-prop="label"
          />
          <div v-if="currentProvider" class="model-hint">
            仅展示「{{ currentProvider.label }}」官方发布的全双工语音大模型，共 {{ currentProvider.models.length }} 个。
          </div>
          <div v-else class="model-hint text-muted">
            请先选择所属密钥，系统会按厂商自动过滤可用的全双工语音模型。
          </div>
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
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { VoiceModel, VoiceModelDefault, VoiceProviderCatalogItem } from '@/types/voice'
import {
  listVoiceModels,
  getVoiceModelDefault,
  upsertVoiceModel,
  setDefaultVoiceModel,
  getVoiceProviderCatalog,
} from '@/api/voice'
import { getApiKeySimpleList } from '@/api/ai-apikey'

const loading = ref(false)
const saving = ref(false)
const models = ref<VoiceModel[]>([])
const defaultInfo = ref<VoiceModelDefault | null>(null)

interface KeyOption {
  label: string
  value: number
  platform: string
}
const keyOptions = ref<KeyOption[]>([])
const providerCatalog = ref<Record<string, VoiceProviderCatalogItem>>({})

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

// 当前选中密钥对应的厂商目录条目
const currentProvider = computed<VoiceProviderCatalogItem | null>(() => {
  if (form.value.key_id == null) return null
  const key = keyOptions.value.find((k) => k.value === form.value.key_id)
  if (!key) return null
  const provKey = normalizeProvider(key.platform)
  return providerCatalog.value[provKey] || null
})

// 模型下拉：仅展示当前厂商官方全双工语音模型
const modelOptions = computed(() => {
  if (!currentProvider.value) return []
  return currentProvider.value.models.map((m) => ({
    label: m.is_default ? `${m.name}（推荐）` : m.name,
    value: m.code,
  }))
})

// 归一化平台名（与后端 normalize_provider_key 保持一致）
function normalizeProvider(platform: string): string {
  const p = (platform || '').trim().toLowerCase()
  const aliases: Record<string, string> = {
    dashscope: 'dashscope', '通义千问': 'dashscope', 'aliyun': 'dashscope', '阿里云': 'dashscope',
    openai: 'openai',
    google: 'google', 'gemini': 'google',
    volcengine: 'volcengine', 'bytedance': 'volcengine', '字节跳动': 'volcengine', 'doubao': 'volcengine', '豆包': 'volcengine',
    iflytek: 'iflytek', '讯飞': 'iflytek', 'xfyun': 'iflytek', 'spark': 'iflytek',
  }
  return aliases[p] || p
}

function onKeyChange() {
  // 切换密钥时，若当前模型不属于新厂商则清空
  if (currentProvider.value && form.value.model) {
    const codes = currentProvider.value.models.map((m) => m.code)
    if (!codes.includes(form.value.model)) {
      form.value.model = ''
    }
  } else {
    form.value.model = ''
  }
}

async function load() {
  loading.value = true
  try {
    const [m, d, keys, catalog] = await Promise.all([
      listVoiceModels(),
      getVoiceModelDefault(),
      getApiKeySimpleList(),
      getVoiceProviderCatalog(),
    ])
    models.value = m
    defaultInfo.value = d
    providerCatalog.value = catalog
    keyOptions.value = (keys as any[]).map((k) => ({
      label: `${k.name}（${k.platform}）`,
      value: k.id,
      platform: k.platform,
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
  if (record.usable === false) {
    message.warning('该模型不可用（模型不在官方全双工目录或缺少密钥），无法设为默认')
    return
  }
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
  max-width: 720px;
}
.default-tip {
  margin-bottom: 16px;
}
.provider-hint {
  margin-top: 8px;
  font-size: 12px;
}
.model-hint {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}
.text-muted {
  color: rgba(0, 0, 0, 0.25);
}
</style>
