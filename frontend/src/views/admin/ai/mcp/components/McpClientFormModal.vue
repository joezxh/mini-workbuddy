<template>
  <a-modal
    :open="visible"
    :title="isEdit ? t('mcpSquare.editClient') : t('mcpSquare.addClient')"
    width="560px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
      <a-form-item :label="t('mcpSquare.name')" required>
        <a-input v-model:value="form.name" :placeholder="t('mcpSquare.clientNamePlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('mcpSquare.clientType')" required>
        <a-select v-model:value="form.client_type" :placeholder="t('mcpSquare.selectType')">
          <a-select-option value="stdio">Stdio</a-select-option>
          <a-select-option value="http">HTTP</a-select-option>
          <a-select-option value="sse">SSE</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item :label="t('mcpSquare.mcpType')" required>
        <a-select v-model:value="form.mcp_type" :placeholder="t('mcpSquare.selectMcpType')">
          <a-select-option value="tool">Tool</a-select-option>
          <a-select-option value="resource">Resource</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item :label="t('skillHub.version')">
        <a-input v-model:value="form.version" :placeholder="t('mcpSquare.versionNumPlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('skillHub.description')">
        <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('mcpSquare.descPlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('mcpSquare.remark')">
        <a-textarea v-model:value="form.remark" :rows="2" :placeholder="t('mcpSquare.remark')" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

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
    message.warning(t('mcpSquare.fillRequired'))
    return
  }
  submitting.value = true
  try {
    const data = buildPayload()
    if (isEdit.value && props.record) {
      await updateMcpClient({ id: props.record.id, ...data })
      message.success(t('mcpSquare.updateSuccess'))
    } else {
      await createMcpClient({ api_key_id: props.apiKeyId, ...data })
      message.success(t('mcpSquare.createSuccess'))
    }
    emit('update:visible', false)
    emit('success')
  } catch (e: any) {
    const detail = e?.response?.data?.detail || t('common.error')
    message.error(detail)
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  emit('update:visible', false)
}
</script>
