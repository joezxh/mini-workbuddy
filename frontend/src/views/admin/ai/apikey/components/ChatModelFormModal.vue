<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('apiKeyMgmt.editModelTitle') : t('apiKeyMgmt.createModelTitle')"
    width="700px"
    :confirm-loading="saving"
    @ok="handleSubmit"
    @cancel="visible = false"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :label-col="{ span: 6 }"
      :wrapper-col="{ span: 16 }"
      style="margin-top: 20px"
    >
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item
            :label="t('apiKeyMgmt.labelModelName')"
            name="name"
            :rules="[{ required: true, message: t('apiKeyMgmt.modelNameRule') }]"
          >
            <a-input v-model:value="formData.name" :placeholder="t('apiKeyMgmt.modelNamePlaceholder')" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            :label="t('apiKeyMgmt.labelModelId')"
            name="model"
            :rules="[{ required: true, message: t('apiKeyMgmt.modelIdRule') }]"
          >
            <a-input v-model:value="formData.model" :placeholder="t('apiKeyMgmt.modelIdPlaceholder')" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelModelCode')" name="code">
            <a-input v-model:value="formData.code" :placeholder="t('apiKeyMgmt.codePlaceholder')" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelType')" name="type">
            <a-select v-model:value="formData.type" :placeholder="t('apiKeyMgmt.typePlaceholder')" allowClear>
              <a-select-option
                v-for="tp in modelTypes"
                :key="tp.item_code"
                :value="Number(tp.item_value || tp.item_code)"
              >
                {{ tp.item_name }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-divider orientation="left">{{ t('apiKeyMgmt.sectionGenParams') }}</a-divider>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelTemperature')" name="temperature">
            <a-input-number
              v-model:value="formData.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              :precision="2"
              style="width: 100%"
              placeholder="0.0-2.0"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelMaxTokens')" name="max_tokens">
            <a-input-number
              v-model:value="formData.max_tokens"
              :min="1"
              :max="128000"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.maxTokensPlaceholder')"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="Top P" name="top_p">
            <a-input-number
              v-model:value="formData.top_p"
              :min="0"
              :max="1"
              :step="0.05"
              :precision="2"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.topPPlaceholder')"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="Top K" name="top_k">
            <a-input-number
              v-model:value="formData.top_k"
              :min="1"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.topKPlaceholder')"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelSeed')" name="seed">
            <a-input-number
              v-model:value="formData.seed"
              :min="0"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.seedPlaceholder')"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelMaxContexts')" name="max_contexts">
            <a-input-number
              v-model:value="formData.max_contexts"
              :min="1"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.contextsPlaceholder')"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelMaxTurns')" name="max_turns">
            <a-input-number
              v-model:value="formData.max_turns"
              :min="1"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.labelMaxTurns')"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelDimensions')" name="dimensions">
            <a-input-number
              v-model:value="formData.dimensions"
              :min="1"
              style="width: 100%"
              :placeholder="t('apiKeyMgmt.dimPlaceholder')"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-divider orientation="left">{{ t('apiKeyMgmt.sectionAdvanced') }}</a-divider>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelRetry')" name="retry">
            <a-input-number
              v-model:value="formData.retry"
              :min="0"
              :max="10"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelTimeout')" name="timeout">
            <a-input-number
              v-model:value="formData.timeout"
              :min="1"
              :max="300"
              style="width: 100%"
              :addon-after="t('apiKeyMgmt.seconds')"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelStreamTimeout')" name="stream_timeout">
            <a-input-number
              v-model:value="formData.stream_timeout"
              :min="1"
              :max="120"
              style="width: 100%"
              :addon-after="t('apiKeyMgmt.seconds')"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelSort')" name="sort">
            <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelThinking')" name="enable_thinking">
            <a-switch v-model:checked="formData.enable_thinking" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelSearch')" name="enable_search">
            <a-switch v-model:checked="formData.enable_search" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item :label="t('apiKeyMgmt.labelStatus')" name="status">
            <a-switch
              v-model:checked="formData.status"
              :checked-children="t('apiKeyMgmt.enabled')"
              :un-checked-children="t('apiKeyMgmt.disabled')"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { createChatModel, updateChatModel, type AiChatModel } from '@/api/ai-apikey'
import { useDictionary } from '@/composables/useDictionary'

const { t } = useI18n()

const props = defineProps<{
  open: boolean
  model?: AiChatModel | null
  keyId: number
  platform?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const isEdit = computed(() => !!props.model?.id)

const formRef = ref()
const saving = ref(false)

// 模型类型由数据字典（model_type）动态维护，避免硬编码
const { modelTypes, loadModelTypes } = useDictionary()
onMounted(() => {
  loadModelTypes()
})

const formData = reactive({
  name: '',
  model: '',
  code: '',
  type: undefined as number | undefined,
  temperature: undefined as number | undefined,
  max_tokens: undefined as number | undefined,
  top_p: undefined as number | undefined,
  top_k: undefined as number | undefined,
  seed: undefined as number | undefined,
  max_contexts: undefined as number | undefined,
  max_turns: undefined as number | undefined,
  dimensions: undefined as number | undefined,
  retry: undefined as number | undefined,
  timeout: undefined as number | undefined,
  stream_timeout: undefined as number | undefined,
  enable_thinking: false,
  enable_search: false,
  sort: 0,
  status: true
})

// 监听 props.model 变化，用于编辑回填
watch(
  () => props.model,
  (val) => {
    if (val?.id) {
      formData.name = val.name || ''
      formData.model = val.model || ''
      formData.code = val.code || ''
      formData.type = val.type
      formData.temperature = val.temperature
      formData.max_tokens = val.max_tokens
      formData.top_p = val.top_p
      formData.top_k = val.top_k
      formData.seed = val.seed
      formData.max_contexts = val.max_contexts
      formData.max_turns = val.max_turns
      formData.dimensions = val.dimensions
      formData.retry = val.retry
      formData.timeout = val.timeout
      formData.stream_timeout = val.stream_timeout
      formData.enable_thinking = val.enable_thinking || false
      formData.enable_search = val.enable_search || false
      formData.sort = val.sort || 0
      formData.status = val.status === 1
    } else {
      // 重置表单
      formData.name = ''
      formData.model = ''
      formData.code = ''
      formData.type = undefined
      formData.temperature = undefined
      formData.max_tokens = undefined
      formData.top_p = undefined
      formData.top_k = undefined
      formData.seed = undefined
      formData.max_contexts = undefined
      formData.max_turns = undefined
      formData.dimensions = undefined
      formData.retry = undefined
      formData.timeout = undefined
      formData.stream_timeout = undefined
      formData.enable_thinking = false
      formData.enable_search = false
      formData.sort = 0
      formData.status = true
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

  saving.value = true
  try {
    const payload: any = {
      key_id: props.keyId,
      name: formData.name,
      model: formData.model,
      code: formData.code || undefined,
      type: formData.type,
      temperature: formData.temperature,
      max_tokens: formData.max_tokens,
      top_p: formData.top_p,
      top_k: formData.top_k,
      seed: formData.seed,
      max_contexts: formData.max_contexts,
      max_turns: formData.max_turns,
      dimensions: formData.dimensions,
      retry: formData.retry,
      timeout: formData.timeout,
      stream_timeout: formData.stream_timeout,
      enable_thinking: formData.enable_thinking,
      enable_search: formData.enable_search,
      sort: formData.sort,
      status: formData.status ? 1 : 0
    }

    if (isEdit.value && props.model?.id) {
      payload.id = props.model.id
      await updateChatModel(payload)
      message.success(t('apiKeyMgmt.updateSuccess'))
    } else {
      await createChatModel(payload)
      message.success(t('apiKeyMgmt.createSuccess'))
    }
    emit('success')
    visible.value = false
  } catch (e: any) {
    message.error(e.message || t('apiKeyMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>
