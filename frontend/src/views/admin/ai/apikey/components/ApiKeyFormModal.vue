<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑 API 密钥' : '新增 API 密钥'"
    width="600px"
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
        label="密钥名称"
        name="name"
        :rules="[{ required: true, message: '请输入密钥名称' }]"
      >
        <a-input v-model:value="formData.name" placeholder="请输入密钥名称" />
      </a-form-item>

      <a-form-item
        label="平台"
        name="platform"
        :rules="[{ required: true, message: '请选择平台' }]"
      >
        <a-select v-model:value="formData.platform" placeholder="请选择平台">
          <a-select-option v-for="p in AI_PLATFORMS" :key="p" :value="p">{{ p }}</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item
        label="API Key"
        name="api_key"
        :rules="[{ required: true, message: '请输入 API Key' }]"
      >
        <a-input-password
          v-model:value="formData.api_key"
          placeholder="请输入 API Key"
          :visibility-toggle="true"
        />
      </a-form-item>

      <a-form-item label="URL" name="url">
        <a-input v-model:value="formData.url" placeholder="API 地址，如：https://api.openai.com/v1" />
      </a-form-item>

      <a-form-item label="AppId" name="app_id">
        <a-input v-model:value="formData.app_id" placeholder="AppId（可选）" />
      </a-form-item>

      <a-form-item label="排序" name="sort">
        <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
      </a-form-item>

      <a-form-item label="状态" name="status">
        <a-switch
          v-model:checked="formData.status"
          checked-children="启用"
          un-checked-children="禁用"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { createApiKey, updateApiKey, AI_PLATFORMS, type AiApiKey } from '@/api/ai-apikey'

const props = defineProps<{
  open: boolean
  apiKey?: AiApiKey | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const isEdit = computed(() => !!props.apiKey?.id)

const formRef = ref()
const saving = ref(false)

const formData = reactive({
  name: '',
  platform: 'OpenAI',
  api_key: '',
  url: '',
  app_id: '',
  sort: 0,
  status: true
})

// 监听 props.apiKey 变化，用于编辑回填
watch(
  () => props.apiKey,
  (val) => {
    if (val?.id) {
      formData.name = val.name || ''
      formData.platform = val.platform || 'OpenAI'
      formData.api_key = val.api_key || ''
      formData.url = val.url || ''
      formData.app_id = val.app_id || ''
      formData.sort = val.sort || 0
      formData.status = val.status === 1
    } else {
      // 重置表单
      formData.name = ''
      formData.platform = 'OpenAI'
      formData.api_key = ''
      formData.url = ''
      formData.app_id = ''
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
    const payload = {
      name: formData.name,
      platform: formData.platform,
      api_key: formData.api_key,
      url: formData.url,
      app_id: formData.app_id,
      sort: formData.sort,
      status: formData.status ? 1 : 0
    }

    if (isEdit.value && props.apiKey?.id) {
      await updateApiKey({ id: props.apiKey.id, ...payload })
      message.success('更新成功')
    } else {
      await createApiKey(payload)
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
