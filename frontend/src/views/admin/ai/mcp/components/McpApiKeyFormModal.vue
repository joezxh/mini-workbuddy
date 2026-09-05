<template>
  <a-modal
    :open="visible"
    :title="isEdit ? '编辑 API Key' : '新增 API Key'"
    width="680px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
      <a-tabs v-model:activeKey="formTab">
        <!-- Tab 1: 基础信息 -->
        <a-tab-pane key="basic" tab="基础信息">
          <a-form-item label="名称" required>
            <a-input v-model:value="form.name" placeholder="请输入名称" />
          </a-form-item>
          <a-form-item label="服务类型" required>
            <a-select v-model:value="form.service_type" placeholder="选择服务类型">
              <a-select-option value="nacos2">Nacos 2.x</a-select-option>
              <a-select-option value="nacos3">Nacos 3.x</a-select-option>
              <a-select-option value="http">HTTP</a-select-option>
              <a-select-option value="sse">SSE</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="平台">
            <a-input v-model:value="form.platform" placeholder="local / remote" />
          </a-form-item>
          <a-form-item label="版本">
            <a-input v-model:value="form.version" placeholder="MCP协议版本" />
          </a-form-item>
          <a-form-item label="描述">
            <a-textarea v-model:value="form.description" :rows="3" placeholder="描述信息" />
          </a-form-item>
        </a-tab-pane>

        <!-- Tab 2: 连接配置 -->
        <a-tab-pane key="connection" tab="连接配置">
          <a-form-item label="服务地址">
            <a-input v-model:value="form.service_url" placeholder="http://..." />
          </a-form-item>
          <!-- Nacos 特有字段 -->
          <template v-if="isNacos">
            <a-form-item label="服务名">
              <a-input v-model:value="form.service_name" placeholder="Nacos 服务名" />
            </a-form-item>
            <a-form-item label="命名空间">
              <a-input v-model:value="form.namespace" placeholder="Nacos namespace" />
            </a-form-item>
            <a-form-item label="分组">
              <a-input v-model:value="form.group_key" placeholder="Nacos group" />
            </a-form-item>
          </template>
          <!-- HTTP/SSE 特有字段 -->
          <template v-if="isHttpOrSse">
            <a-form-item label="访问路径">
              <a-input v-model:value="form.access_path" placeholder="/mcp/v1" />
            </a-form-item>
          </template>
          <a-form-item label="API Key">
            <a-input-password v-model:value="form.api_key" placeholder="鉴权密钥" />
          </a-form-item>
        </a-tab-pane>

        <!-- Tab 3: 高级配置 -->
        <a-tab-pane key="advanced" tab="高级配置">
          <a-form-item label="能力列表">
            <a-select v-model:value="form.capabilities" mode="multiple" placeholder="选择能力">
              <a-select-option value="tools">Tools</a-select-option>
              <a-select-option value="resources">Resources</a-select-option>
              <a-select-option value="prompts">Prompts</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="备注">
            <a-textarea v-model:value="form.remark" :rows="3" placeholder="备注" />
          </a-form-item>
        </a-tab-pane>
      </a-tabs>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { createMcpApiKey, updateMcpApiKey, type McpApiKey } from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  record: McpApiKey | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isEdit = computed(() => !!props.record)
const formTab = ref('basic')
const submitting = ref(false)

// 表单字段全部使用 snake_case（与服务端 McpApiKeyCreate / McpApiKeyUpdate 一致）
const defaultForm = () => ({
  name: '',
  service_type: 'http' as 'nacos2' | 'nacos3' | 'http' | 'sse',
  platform: '',
  version: '',
  description: '',
  service_url: '',
  service_name: '',
  api_key: '',
  namespace: '',
  group_key: '',
  access_path: '',
  capabilities: [] as string[],
  remark: '',
})

const form = reactive(defaultForm())

const isNacos = computed(() => form.service_type === 'nacos2' || form.service_type === 'nacos3')
const isHttpOrSse = computed(() => form.service_type === 'http' || form.service_type === 'sse')

watch(() => props.visible, (val) => {
  if (val && props.record) {
    Object.assign(form, {
      name: props.record.name || '',
      service_type: (props.record.service_type as 'nacos2' | 'nacos3' | 'http' | 'sse') || 'http',
      platform: props.record.platform || '',
      version: props.record.version || '',
      description: props.record.description || '',
      service_url: props.record.service_url || '',
      service_name: props.record.service_name || '',
      api_key: props.record.api_key || '',
      namespace: props.record.namespace || '',
      group_key: props.record.group_key || '',
      access_path: props.record.access_path || '',
      capabilities: props.record.capabilities || [],
      remark: props.record.remark || '',
    })
  } else if (val) {
    Object.assign(form, defaultForm())
  }
  formTab.value = 'basic'
})

function buildPayload(): Record<string, any> {
  // 仅提交有值/显式启用的字段，避免空字符串覆盖后端数据
  return {
    name: form.name,
    service_type: form.service_type,
    platform: form.platform || undefined,
    version: form.version || undefined,
    description: form.description || undefined,
    service_url: form.service_url || undefined,
    service_name: form.service_name || undefined,
    api_key: form.api_key || undefined,
    namespace: form.namespace || undefined,
    group_key: form.group_key || undefined,
    access_path: form.access_path || undefined,
    capabilities: form.capabilities && form.capabilities.length ? form.capabilities : undefined,
    remark: form.remark || undefined,
  }
}

async function handleSubmit() {
  if (!form.name || !form.service_type) {
    message.warning('请填写必填字段')
    return
  }
  submitting.value = true
  try {
    const data = buildPayload()
    if (isEdit.value && props.record) {
      await updateMcpApiKey({ id: props.record.id, ...data })
      message.success('更新成功')
    } else {
      await createMcpApiKey(data)
      message.success('创建成功')
    }
    emit('update:visible', false)
    emit('success')
  } catch (e: any) {
    const detail = e?.response?.data?.detail || '操作失败'
    message.error(detail)
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  emit('update:visible', false)
}
</script>
