<template>
  <a-modal
    :open="visible"
    :title="isEdit ? t('mcpSquare.editTemplate') : t('mcpSquare.addTemplate')"
    width="720px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :label-col="{ span: 5 }"
      :wrapper-col="{ span: 18 }"
    >
      <a-form-item :label="t('mcpSquare.templateName')" name="name">
        <a-input v-model:value="form.name" :placeholder="t('mcpSquare.templateNamePlaceholder')" :max-length="100" show-count />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.serviceType')" name="service_type">
        <a-select v-model:value="form.service_type" :placeholder="t('mcpSquare.selectServiceType')">
          <a-select-option value="nacos2">Nacos 2.x</a-select-option>
          <a-select-option value="nacos3">Nacos 3.x</a-select-option>
          <a-select-option value="http">HTTP</a-select-option>
          <a-select-option value="sse">SSE</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="t('mcpSquare.category')" name="category">
        <a-select v-model:value="form.category" :placeholder="t('mcpSquare.selectCategory')" allow-clear>
          <a-select-option value="finance">{{ t('mcpSquare.catFinance') }}</a-select-option>
          <a-select-option value="sales">{{ t('mcpSquare.catSales') }}</a-select-option>
          <a-select-option value="legal">{{ t('mcpSquare.catLegal') }}</a-select-option>
          <a-select-option value="office">{{ t('mcpSquare.catOffice') }}</a-select-option>
          <a-select-option value="education">{{ t('mcpSquare.catEducation') }}</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="t('mcpSquare.platform')" name="platform">
        <a-input v-model:value="form.platform" placeholder="local / remote" :max-length="50" />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.icon')" name="icon">
        <a-input v-model:value="form.icon" :placeholder="t('mcpSquare.iconPlaceholder')" :max-length="200" />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.protocolVersion')" name="version">
        <a-input v-model:value="form.version" :placeholder="t('mcpSquare.versionPlaceholder')" :max-length="20" />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.serviceUrl')" name="service_url">
        <a-input v-model:value="form.service_url" :placeholder="t('mcpSquare.serviceUrlPlaceholder')" :max-length="500" />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.accessPath')" name="access_path">
        <a-input v-model:value="form.access_path" :placeholder="t('mcpSquare.accessPathPlaceholder')" :max-length="500" />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.capabilities')" name="capabilities">
        <a-select
          v-model:value="form.capabilities"
          mode="multiple"
          :placeholder="t('mcpSquare.selectCapabilities')"
          allow-clear
        >
          <a-select-option value="tools">Tools</a-select-option>
          <a-select-option value="resources">Resources</a-select-option>
          <a-select-option value="prompts">Prompts</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="t('skillHub.description')" name="description">
        <a-textarea
          v-model:value="form.description"
          :rows="3"
          :placeholder="t('mcpSquare.templateDescPlaceholder')"
          :max-length="2000"
          show-count
        />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.defaultClient')" name="default_client_config">
        <a-textarea
          v-model:value="defaultClientConfigText"
          :rows="5"
          :placeholder="t('mcpSquare.defaultClientPlaceholder')"
        />
      </a-form-item>

      <a-form-item :label="t('mcpSquare.sort')" name="sort">
        <a-input-number v-model:value="form.sort" :min="0" :max="9999" style="width: 160px" />
      </a-form-item>

      <a-form-item :label="t('skillHub.status')" name="status">
        <a-radio-group v-model:value="form.status">
          <a-radio :value="1">{{ t('skillHub.enabled') }}</a-radio>
          <a-radio :value="0">{{ t('skillHub.disabled') }}</a-radio>
        </a-radio-group>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import type { Rule } from 'ant-design-vue/es/form'
import {
  createMcpSquare,
  updateMcpSquare,
  type McpSquareTemplate,
} from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  record: McpSquareTemplate | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isEdit = computed(() => !!props.record)
const submitting = ref(false)
const formRef = ref()

const { t } = useI18n()

const defaultForm = () => ({
  name: '',
  service_type: 'http' as 'nacos2' | 'nacos3' | 'http' | 'sse',
  platform: '',
  category: undefined as string | undefined,
  icon: '',
  version: '',
  service_url: '',
  access_path: '',
  capabilities: [] as string[],
  description: '',
  sort: 0,
  status: 1 as number,
})

const form = reactive(defaultForm())
const defaultClientConfigText = ref('')

const rules = computed<Record<string, Rule[]>>(() => ({
  name: [
    { required: true, message: t('mcpSquare.templateNamePlaceholder'), trigger: 'blur' },
    { max: 100, message: t('mcpSquare.nameTooLong'), trigger: 'blur' },
  ],
  service_type: [{ required: true, message: t('mcpSquare.serviceTypeRequired'), trigger: 'change' }],
  sort: [{ type: 'number', message: t('mcpSquare.sortNumber'), trigger: 'blur' }],
}))

watch(() => props.visible, (val) => {
  if (val && props.record) {
    Object.assign(form, {
      name: props.record.name || '',
      service_type: (props.record.service_type as 'nacos2' | 'nacos3' | 'http' | 'sse') || 'http',
      platform: props.record.platform || '',
      category: props.record.category || undefined,
      icon: props.record.icon || '',
      version: props.record.version || '',
      service_url: props.record.service_url || '',
      access_path: props.record.access_path || '',
      capabilities: props.record.capabilities || [],
      description: props.record.description || '',
      sort: props.record.sort ?? 0,
      status: props.record.status ?? 1,
    })
    defaultClientConfigText.value = props.record.default_client_config
      ? JSON.stringify(props.record.default_client_config, null, 2)
      : ''
  } else if (val) {
    Object.assign(form, defaultForm())
    defaultClientConfigText.value = ''
  }
})

function parseDefaultClientConfig(): Record<string, any> | null {
  const text = defaultClientConfigText.value.trim()
  if (!text) return null
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed
    }
    message.error(t('mcpSquare.cfgMustBeObject'))
    return undefined as any
  } catch {
    message.error(t('mcpSquare.cfgParseFailed'))
    return undefined as any
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate?.()
  } catch {
    return
  }
  const cfg = parseDefaultClientConfig()
  if (defaultClientConfigText.value.trim() && cfg === undefined) {
    // 解析失败，终止提交
    return
  }

  submitting.value = true
  try {
    const payload: any = {
      name: form.name,
      service_type: form.service_type,
      platform: form.platform || undefined,
      category: form.category || undefined,
      icon: form.icon || undefined,
      version: form.version || undefined,
      service_url: form.service_url || undefined,
      access_path: form.access_path || undefined,
      capabilities: form.capabilities && form.capabilities.length ? form.capabilities : undefined,
      description: form.description || undefined,
      default_client_config: cfg,
      sort: form.sort,
      status: form.status,
    }

    if (isEdit.value && props.record) {
      await updateMcpSquare({ id: props.record.id, ...payload })
      message.success(t('mcpSquare.updateSuccess'))
    } else {
      await createMcpSquare(payload)
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
