<template>
  <a-modal
    v-model:open="visible"
    :title="t('toolMgmt.testTitle')"
    width="640px"
    :confirm-loading="testing"
    :ok-text="t('toolMgmt.runTest')"
    :cancel-text="t('common.close')"
    @ok="handleTest"
    @cancel="visible = false"
  >
    <a-alert
      v-if="tool"
      type="info"
      show-icon
      style="margin-bottom: 16px"
      :message="`${tool.displayName}（${tool.toolKey}）`"
      :description="tool.description || t('toolMgmt.noDescription')"
    />

    <a-empty v-if="!hasInputs" :description="t('toolMgmt.emptyInputs')" style="margin: 24px 0" />

    <a-form v-else :model="formData" layout="vertical" style="margin-top: 12px">
      <a-form-item
        v-for="(field, key) in inputFields"
        :key="key as string"
        :label="field.title || (key as string)"
      >
        <!-- 字符串 -->
        <a-input
          v-if="field.type === 'string' && !field.enum"
          v-model:value="(formData as any)[key as string]"
          :placeholder="field.description || t('toolMgmt.inputTextPh')"
        />
        <!-- 枚举 -->
        <a-select
          v-else-if="field.enum"
          v-model:value="(formData as any)[key as string]"
          :placeholder="field.description || t('toolMgmt.selectOption')"
          allow-clear
        >
          <a-select-option v-for="opt in field.enum" :key="String(opt)" :value="opt">{{ opt }}</a-select-option>
        </a-select>
        <!-- 数字 -->
        <a-input-number
          v-else-if="field.type === 'number' || field.type === 'integer'"
          v-model:value="(formData as any)[key as string]"
          style="width: 100%"
          :placeholder="field.description || t('toolMgmt.inputNumberPh')"
        />
        <!-- 布尔 -->
        <a-switch
          v-else-if="field.type === 'boolean'"
          v-model:checked="(formData as any)[key as string]"
        />
        <!-- 对象/数组 -->
        <a-textarea
          v-else
          v-model:value="jsonText[key as string]"
          :rows="3"
          :placeholder="field.description || t('toolMgmt.inputJsonPh')"
        />
      </a-form-item>
    </a-form>

    <!-- 测试结果 -->
    <a-divider v-if="result" orientation="left">{{ t('toolMgmt.resultTitle') }}</a-divider>
    <div v-if="result">
      <a-alert
        :type="result.success ? 'success' : 'error'"
        show-icon
        :message="result.success ? t('toolMgmt.execSuccess') : t('toolMgmt.execFailed')"
        :description="result.error || ''"
      />
      <pre v-if="result.success" class="test-output">{{ formatOutput(result.output) }}</pre>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { testTool, type AiTool } from '@/api/ai-tool'

const props = defineProps<{
  open: boolean
  tool?: AiTool | null
}>()

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const formData = reactive<Record<string, any>>({})
const jsonText = reactive<Record<string, string>>({})
const testing = ref(false)
const result = ref<{
  success: boolean
  output: any
  error: string | null
  target: string
} | null>(null)

interface SchemaField {
  type?: string
  title?: string
  description?: string
  enum?: any[]
}

const inputFields = computed<Record<string, SchemaField>>(() => {
  const schema = props.tool?.inputSchema
  if (!schema || !schema.properties) return {}
  return schema.properties as Record<string, SchemaField>
})

const hasInputs = computed(() => Object.keys(inputFields.value).length > 0)

watch(
  () => props.tool,
  (val) => {
    // 重置表单，按 schema 初始化默认值
    Object.keys(formData).forEach((k) => delete formData[k])
    Object.keys(jsonText).forEach((k) => delete jsonText[k])
    result.value = null
    const propsSchema = val?.inputSchema?.properties || {}
    for (const [k, field] of Object.entries(propsSchema)) {
      const f = field as SchemaField
      if (f.type === 'boolean') formData[k] = false
      else if (f.type === 'number' || f.type === 'integer') formData[k] = undefined
      else if (f.enum) formData[k] = undefined
      else if (f.type === 'string') formData[k] = ''
      else jsonText[k] = ''
    }
  },
  { immediate: true }
)

function formatOutput(output: any): string {
  if (output === null || output === undefined) return ''
  if (typeof output === 'string') return output
  try {
    return JSON.stringify(output, null, 2)
  } catch {
    return String(output)
  }
}

const handleTest = async () => {
  if (!props.tool) return
  testing.value = true
  result.value = null
  try {
    const inputs: Record<string, any> = {}
    for (const key of Object.keys(inputFields.value)) {
      const f = inputFields.value[key]
      if (f.type === 'object' || f.type === 'array') {
        const raw = jsonText[key]
        inputs[key] = raw && raw.trim() ? JSON.parse(raw) : (f.type === 'array' ? [] : {})
      } else {
        inputs[key] = (formData as any)[key]
      }
    }
    const res = await testTool({
      toolKey: props.tool.toolKey,
      inputs
    })
    result.value = res
  } catch (e: any) {
    message.error(e.message || t('toolMgmt.testRequestFailed'))
  } finally {
    testing.value = false
  }
}
</script>

<style lang="less" scoped>
.test-output {
  margin-top: 12px;
  background: #0d1117;
  color: #c9d1d9;
  padding: 12px 16px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
