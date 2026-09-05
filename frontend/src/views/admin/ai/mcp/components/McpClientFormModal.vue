<template>
  <a-modal
    :open="visible"
    :title="isEdit ? '编辑 Client' : '新增 Client'"
    width="560px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
      <a-form-item label="名称" required>
        <a-input v-model:value="form.name" placeholder="客户端名称" />
      </a-form-item>
      <a-form-item label="客户端类型" required>
        <a-select v-model:value="form.client_type" placeholder="选择类型">
          <a-select-option value="stdio">Stdio</a-select-option>
          <a-select-option value="http">HTTP</a-select-option>
          <a-select-option value="sse">SSE</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="应用类别" required>
        <a-select v-model:value="form.mcp_type" placeholder="选择类别">
          <a-select-option value="tool">Tool</a-select-option>
          <a-select-option value="resource">Resource</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="版本">
        <a-input v-model:value="form.version" placeholder="版本号" />
      </a-form-item>
      <a-form-item label="描述">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="描述" />
      </a-form-item>
      <a-form-item label="备注">
        <a-textarea v-model:value="form.remark" :rows="2" placeholder="备注" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { createMcpClient, updateMcpClient, type McpClient } from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  record: McpClient | null
  apiKeyId: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isEdit = computed(() => !!props.record)
const submitting = ref(false)

const defaultForm = () => ({
  name: '',
  client_type: 'http' as 'stdio' | 'http' | 'sse',
  mcp_type: 'tool' as 'tool' | 'resource',
  version: '',
  description: '',
  remark: '',
})

const form = reactive(defaultForm())

watch(() => props.visible, (val) => {
  if (val && props.record) {
    Object.assign(form, {
      name: props.record.name || '',
      client_type: (props.record.client_type as 'stdio' | 'http' | 'sse') || 'http',
      mcp_type: (props.record.mcp_type as 'tool' | 'resource') || 'tool',
      version: props.record.version || '',
      description: props.record.description || '',
      remark: props.record.remark || '',
    })
  } else if (val) {
    Object.assign(form, defaultForm())
  }
})

function buildPayload(): Record<string, any> {
  return {
    name: form.name,
    client_type: form.client_type,
    mcp_type: form.mcp_type,
    version: form.version || undefined,
    description: form.description || undefined,
    remark: form.remark || undefined,
  }
}

async function handleSubmit() {
  if (!form.name || !form.client_type || !form.mcp_type) {
    message.warning('请填写必填字段')
    return
  }
  submitting.value = true
  try {
    const data = buildPayload()
    if (isEdit.value && props.record) {
      await updateMcpClient({ id: props.record.id, ...data })
      message.success('更新成功')
    } else {
      await createMcpClient({ api_key_id: props.apiKeyId, ...data })
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
