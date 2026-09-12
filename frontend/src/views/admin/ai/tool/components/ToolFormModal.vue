<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('toolMgmt.editTitle') : t('toolMgmt.addTool')"
    width="680px"
    :confirm-loading="saving"
    @ok="handleSubmit"
    @cancel="visible = false"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :label-col="{ span: 5 }"
      :wrapper-col="{ span: 18 }"
      style="margin-top: 20px"
    >
      <a-form-item
        :label="t('toolMgmt.colToolKey')"
        name="toolKey"
        :rules="[
          { required: true, message: t('toolMgmt.toolKeyRequired') },
          { pattern: /^[A-Za-z][A-Za-z0-9_]*$/, message: t('toolMgmt.toolKeyPattern') }
        ]"
      >
        <a-input
          v-model:value="formData.toolKey"
          :placeholder="t('toolMgmt.toolKeyPh')"
          :disabled="isEdit"
        />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.colDisplayName')" name="displayName" :rules="[{ required: true, message: t('toolMgmt.displayNameRequired') }]">
        <a-input v-model:value="formData.displayName" :placeholder="t('toolMgmt.displayNamePh')" />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.colCategory')" name="category" :rules="[{ required: true, message: t('toolMgmt.categoryRequired') }]">
        <a-select
          v-model:value="formData.category"
          :placeholder="t('toolMgmt.categoryPh')"
          allow-clear
          show-search
          :loading="loadingCategories"
          :options="categoryOptions"
        />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.typeLabel')" name="type">
        <a-select
          v-model:value="formData.type"
          :placeholder="t('toolMgmt.typePh')"
          :loading="loadingTypes"
          :options="typeOptions"
        />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.classNameLabel')" name="className" :rules="[{ required: true, message: t('toolMgmt.classNameRequired') }]">
        <a-input v-model:value="formData.className" placeholder="如：com.tianque.module.ai.service.model.tool.TestToolFunction" />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.methodNameLabel')" name="methodName" :rules="[{ required: true, message: t('toolMgmt.methodNameRequired') }]">
        <a-input v-model:value="formData.methodName" :placeholder="t('toolMgmt.methodNamePh')" />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.colDescription')" name="description">
        <a-textarea v-model:value="formData.description" :placeholder="t('toolMgmt.descriptionPh')" :rows="2" />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.configSchemaLabel')" name="configSchema">
        <a-textarea
          v-model:value="formData.configSchemaText"
          placeholder='JSON 格式，如：{"type":"object","properties":{}}'
          :rows="3"
        />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.configValueLabel')" name="configValue">
        <a-textarea
          v-model:value="formData.configValueText"
          placeholder='JSON 格式，如：{"key":"value"}'
          :rows="3"
        />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.inputSchemaLabel')" name="inputSchema">
        <a-textarea
          v-model:value="formData.inputSchemaText"
          :placeholder="t('toolMgmt.inputSchemaPh')"
          :rows="3"
        />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.colSort')" name="sort">
        <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
      </a-form-item>

      <a-form-item :label="t('toolMgmt.isSystemLabel')" name="isSystem">
        <a-switch v-model:checked="formData.isSystem" :disabled="isEdit && props.tool?.isSystem" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { createTool, updateTool, getToolGroupPage, type AiTool } from '@/api/ai-tool'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'

const props = defineProps<{
  open: boolean
  tool?: AiTool | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const isEdit = computed(() => !!props.tool?.id)

const { t } = useI18n()

const formRef = ref()
const saving = ref(false)

// 从数据字典加载工具类型
const typeOptions = ref<{ value: string; label: string }[]>([])
const loadingTypes = ref(false)

// 从工具分组加载分类
const categoryOptions = ref<{ value: string; label: string }[]>([])
const loadingCategories = ref(false)

const loadToolTypes = async () => {
  loadingTypes.value = true
  try {
    const items = await getDictionaryItems('tool_type')
    typeOptions.value = (items || [])
      .filter((item: DictionaryItem) => item.is_active)
      .map((item: DictionaryItem) => ({ value: item.item_code, label: item.item_name }))
  } catch {
    // 兜底：如果字典加载失败，使用基本类型
    typeOptions.value = [
      { value: 'custom', label: t('toolMgmt.typeCustom') },
      { value: 'agentscope_builtin', label: t('toolMgmt.typeBuiltin') },
      { value: 'custom_dev', label: t('toolMgmt.typeCustomDev') }
    ]
  } finally {
    loadingTypes.value = false
  }
}

const loadCategories = async () => {
  loadingCategories.value = true
  try {
    const res = await getToolGroupPage({ page: 1, pageSize: 100 })
    categoryOptions.value = (res.data || [])
      .filter((g) => g.isActive)
      .map((g) => ({ value: g.displayName || g.name, label: g.displayName || g.name }))
  } catch {
    categoryOptions.value = []
  } finally {
    loadingCategories.value = false
  }
}

onMounted(() => {
  loadToolTypes()
  loadCategories()
})

const formData = reactive({
  toolKey: '',
  displayName: '',
  category: undefined as string | undefined,
  type: 'custom',
  className: '',
  methodName: '',
  description: '',
  configSchemaText: '',
  configValueText: '',
  inputSchemaText: '',
  sort: 0,
  isSystem: false
})

function parseJson(text: string, field: string): Record<string, any> | null {
  if (!text || !text.trim()) return null
  try {
    return JSON.parse(text)
  } catch (e) {
    throw new Error(t('toolMgmt.invalidJson', { field, msg: (e as Error).message }))
  }
}

watch(
  () => props.tool,
  (val) => {
    if (val?.id) {
      formData.toolKey = val.toolKey || ''
      formData.displayName = val.displayName || ''
      formData.category = val.category || undefined
      formData.type = val.type || 'custom'
      formData.className = val.className || ''
      formData.methodName = val.methodName || ''
      formData.description = val.description || ''
      formData.configSchemaText = val.configSchema ? JSON.stringify(val.configSchema, null, 2) : ''
      formData.configValueText = val.configValue ? JSON.stringify(val.configValue, null, 2) : ''
      formData.inputSchemaText = val.inputSchema ? JSON.stringify(val.inputSchema, null, 2) : ''
      formData.sort = val.sort || 0
      formData.isSystem = val.isSystem || false
    } else {
      Object.assign(formData, {
        toolKey: '', displayName: '', category: undefined, type: 'custom',
        className: '', methodName: '', description: '',
        configSchemaText: '', configValueText: '', inputSchemaText: '',
        sort: 0, isSystem: false
      })
    }
  },
  { immediate: true }
)

const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  let configSchema: Record<string, any> | null = null
  let configValue: Record<string, any> | null = null
  let inputSchema: Record<string, any> | null = null
  try {
    configSchema = parseJson(formData.configSchemaText, t('toolMgmt.fieldConfigSchema'))
    configValue = parseJson(formData.configValueText, t('toolMgmt.fieldConfigValue'))
    inputSchema = parseJson(formData.inputSchemaText, t('toolMgmt.fieldInputSchema'))
  } catch (e: any) {
    message.error(e.message)
    return
  }

  saving.value = true
  try {
    const payload: Record<string, any> = {
      toolKey: formData.toolKey,
      displayName: formData.displayName,
      category: formData.category,
      type: formData.type,
      className: formData.className,
      methodName: formData.methodName,
      description: formData.description,
      configSchema,
      configValue,
      inputSchema,
      sort: formData.sort,
      isSystem: formData.isSystem
    }
    if (isEdit.value && props.tool?.id) {
      await updateTool({ id: props.tool.id, ...payload })
      message.success(t('toolMgmt.updated'))
    } else {
      await createTool(payload)
      message.success(t('toolMgmt.created'))
    }
    emit('success')
    visible.value = false
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>
