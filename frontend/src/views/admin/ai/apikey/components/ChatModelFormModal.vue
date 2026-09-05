<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑模型' : '新增模型'"
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
            label="模型名称"
            name="name"
            :rules="[{ required: true, message: '请输入模型名称' }]"
          >
            <a-input v-model:value="formData.name" placeholder="如：GPT-4" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            label="模型 ID"
            name="model"
            :rules="[{ required: true, message: '请输入模型 ID' }]"
          >
            <a-input v-model:value="formData.model" placeholder="如：gpt-4" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="模型编码" name="code">
            <a-input v-model:value="formData.code" placeholder="编码（可选）" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="类型" name="type">
            <a-select v-model:value="formData.type" placeholder="请选择类型" allowClear>
              <a-select-option
                v-for="t in modelTypes"
                :key="t.item_code"
                :value="Number(t.item_value || t.item_code)"
              >
                {{ t.item_name }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-divider orientation="left">生成参数</a-divider>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="温度" name="temperature">
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
          <a-form-item label="最大 Token" name="max_tokens">
            <a-input-number
              v-model:value="formData.max_tokens"
              :min="1"
              :max="128000"
              style="width: 100%"
              placeholder="最大回复长度"
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
              placeholder="累积概率阈值"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="Top K" name="top_k">
            <a-input-number
              v-model:value="formData.top_k"
              :min="1"
              style="width: 100%"
              placeholder="保留词数"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="随机种子" name="seed">
            <a-input-number
              v-model:value="formData.seed"
              :min="0"
              style="width: 100%"
              placeholder="固定种子可复现"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="上下文数" name="max_contexts">
            <a-input-number
              v-model:value="formData.max_contexts"
              :min="1"
              style="width: 100%"
              placeholder="最大对话轮次"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="最大轮次" name="max_turns">
            <a-input-number
              v-model:value="formData.max_turns"
              :min="1"
              style="width: 100%"
              placeholder="最大轮次"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="维度" name="dimensions">
            <a-input-number
              v-model:value="formData.dimensions"
              :min="1"
              style="width: 100%"
              placeholder="向量维度"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-divider orientation="left">高级配置</a-divider>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="重试次数" name="retry">
            <a-input-number
              v-model:value="formData.retry"
              :min="0"
              :max="10"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="超时时间" name="timeout">
            <a-input-number
              v-model:value="formData.timeout"
              :min="1"
              :max="300"
              style="width: 100%"
              addon-after="秒"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="流式超时" name="stream_timeout">
            <a-input-number
              v-model:value="formData.stream_timeout"
              :min="1"
              :max="120"
              style="width: 100%"
              addon-after="秒"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="排序" name="sort">
            <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="支持思考" name="enable_thinking">
            <a-switch v-model:checked="formData.enable_thinking" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="支持搜索" name="enable_search">
            <a-switch v-model:checked="formData.enable_search" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="状态" name="status">
            <a-switch
              v-model:checked="formData.status"
              checked-children="启用"
              un-checked-children="禁用"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { createChatModel, updateChatModel, type AiChatModel } from '@/api/ai-apikey'
import { useDictionary } from '@/composables/useDictionary'

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
      message.success('更新成功')
    } else {
      await createChatModel(payload)
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
