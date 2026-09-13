<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('apiKeyMgmt.editKeyTitle') : t('apiKeyMgmt.createKeyTitle')"
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
        :label="t('apiKeyMgmt.labelKeyName')"
        name="name"
        :rules="[{ required: true, message: t('apiKeyMgmt.keyNameRule') }]"
      >
        <a-input v-model:value="formData.name" :placeholder="t('apiKeyMgmt.keyNameRule')" />
      </a-form-item>

      <a-form-item
        :label="t('apiKeyMgmt.labelPlatform')"
        name="platform"
        :rules="[{ required: true, message: t('apiKeyMgmt.platformRule') }]"
      >
        <a-select v-model:value="formData.platform" :placeholder="t('apiKeyMgmt.platformRule')">
          <a-select-option v-for="p in AI_PLATFORMS" :key="p" :value="p">{{ p }}</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item
        label="API Key"
        name="api_key"
        :rules="[{ required: true, message: t('apiKeyMgmt.apiKeyRule') }]"
      >
        <a-input-password
          v-model:value="formData.api_key"
          :placeholder="t('apiKeyMgmt.apiKeyRule')"
          :visibility-toggle="true"
        />
      </a-form-item>

      <a-form-item label="URL" name="url">
        <a-input v-model:value="formData.url" :placeholder="t('apiKeyMgmt.urlPlaceholder')" />
      </a-form-item>

      <a-form-item label="AppId" name="app_id">
        <a-input v-model:value="formData.app_id" :placeholder="t('apiKeyMgmt.appIdPlaceholder')" />
      </a-form-item>

      <a-form-item :label="t('apiKeyMgmt.labelSort')" name="sort">
        <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
      </a-form-item>

      <a-form-item :label="t('apiKeyMgmt.labelStatus')" name="status">
        <a-switch
          v-model:checked="formData.status"
          :checked-children="t('apiKeyMgmt.enabled')"
          :un-checked-children="t('apiKeyMgmt.disabled')"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { createApiKey, updateApiKey, AI_PLATFORMS, type AiApiKey } from '@/api/ai-apikey'

const { t } = useI18n()

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
      message.success(t('apiKeyMgmt.updateSuccess'))
    } else {
      await createApiKey(payload)
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
