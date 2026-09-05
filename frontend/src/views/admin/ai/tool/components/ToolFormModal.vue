<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑工具' : '新增工具'"
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
        label="工具标识"
        name="toolKey"
        :rules="[
          { required: true, message: '请输入工具标识' },
          { pattern: /^[A-Za-z][A-Za-z0-9_]*$/, message: '只能包含字母、数字、下划线，且以字母开头' }
        ]"
      >
        <a-input
          v-model:value="formData.toolKey"
          placeholder="如：test_tool"
          :disabled="isEdit"
        />
      </a-form-item>

      <a-form-item label="显示名称" name="displayName" :rules="[{ required: true, message: '请输入显示名称' }]">
        <a-input v-model:value="formData.displayName" placeholder="如：测试工具" />
      </a-form-item>

      <a-form-item label="分类" name="category" :rules="[{ required: true, message: '请选择分类' }]">
        <a-select
          v-model:value="formData.category"
          placeholder="请选择分类（来自工具分组）"
          allow-clear
          show-search
          :loading="loadingCategories"
          :options="categoryOptions"
        />
      </a-form-item>

      <a-form-item label="类型" name="type">
        <a-select
          v-model:value="formData.type"
          placeholder="请选择类型"
          :loading="loadingTypes"
          :options="typeOptions"
        />
      </a-form-item>

      <a-form-item label="类名" name="className" :rules="[{ required: true, message: '请输入类名' }]">
        <a-input v-model:value="formData.className" placeholder="如：com.tianque.module.ai.service.model.tool.TestToolFunction" />
      </a-form-item>

      <a-form-item label="方法名" name="methodName" :rules="[{ required: true, message: '请输入方法名' }]">
        <a-input v-model:value="formData.methodName" placeholder="如：execute" />
      </a-form-item>

      <a-form-item label="描述" name="description">
        <a-textarea v-model:value="formData.description" placeholder="工具描述" :rows="2" />
      </a-form-item>

      <a-form-item label="配置 Schema" name="configSchema">
        <a-textarea
          v-model:value="formData.configSchemaText"
          placeholder='JSON 格式，如：{"type":"object","properties":{}}'
          :rows="3"
        />
      </a-form-item>

      <a-form-item label="配置值" name="configValue">
        <a-textarea
          v-model:value="formData.configValueText"
          placeholder='JSON 格式，如：{"key":"value"}'
          :rows="3"
        />
      </a-form-item>

      <a-form-item label="输入 Schema" name="inputSchema">
        <a-textarea
          v-model:value="formData.inputSchemaText"
          placeholder='JSON Schema，用于测试表单动态渲染'
          :rows="3"
        />
      </a-form-item>

      <a-form-item label="排序" name="sort">
        <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
      </a-form-item>

      <a-form-item label="系统内置" name="isSystem">
        <a-switch v-model:checked="formData.isSystem" :disabled="isEdit && props.tool?.isSystem" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
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
      { value: 'custom', label: '自定义' },
      { value: 'agentscope_builtin', label: 'AgentScope内置' },
      { value: 'custom_dev', label: '自定义开发' }
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
    throw new Error(`${field} 不是合法 JSON: ${(e as Error).message}`)
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
    configSchema = parseJson(formData.configSchemaText, '配置 Schema')
    configValue = parseJson(formData.configValueText, '配置值')
    inputSchema = parseJson(formData.inputSchemaText, '输入 Schema')
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
      message.success('更新成功')
    } else {
      await createTool(payload)
      message.success('创建成功')
    }
    emit('success')
    visible.value = false
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
