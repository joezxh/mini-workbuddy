<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑搜索供应商' : '新增搜索供应商'"
    width="880px"
    :confirm-loading="saving"
    @ok="handleSubmit"
    @cancel="visible = false"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :label-col="{ span: 8 }"
      :wrapper-col="{ span: 16 }"
      class="compact-form"
    >
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item
            label="名称"
            name="name"
            :rules="[{ required: true, message: '请输入供应商名称' }]"
          >
            <a-input v-model:value="formData.name" placeholder="如：博查搜索" />
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item
            label="平台"
            name="platform"
            :rules="[{ required: true, message: '请选择平台' }]"
          >
            <a-select v-model:value="formData.platform" placeholder="请选择平台">
              <a-select-option v-for="it in dictItems(DictType.WEB_SEARCH_PLATFORM)" :key="it.item_code" :value="it.item_code">
                {{ it.item_name }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="AppId" name="app_id">
            <a-input v-model:value="formData.app_id" placeholder="AppId（可选）" />
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="排序" name="sort">
            <a-input-number v-model:value="formData.sort" :min="0" style="width: 100%" />
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="超时(秒)" name="timeout">
            <a-input-number v-model:value="formData.timeout" :min="1" :max="300" style="width: 100%" />
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="最大结果数" name="max_results">
            <a-input-number v-model:value="formData.max_results" :min="1" :max="100" style="width: 100%" />
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="每日配额" name="daily_quota">
            <a-input-number v-model:value="formData.daily_quota" :min="0" style="width: 100%" />
            <span class="field-hint">0 表示不限制</span>
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="优先级" name="priority">
            <a-input-number v-model:value="formData.priority" :min="0" :max="100" style="width: 100%" />
            <span class="field-hint">数值越大越优先</span>
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="密钥(可选)" name="api_secret">
            <a-input-password v-model:value="formData.api_secret" placeholder="部分平台需要的额外密钥" />
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item label="状态" name="status">
            <a-switch
              v-model:checked="formData.status"
              checked-children="启用"
              un-checked-children="禁用"
            />
          </a-form-item>
        </a-col>

        <a-col :span="24">
          <a-form-item
            label="API Key"
            name="api_key"
            :rules="[{ required: true, message: '请输入 API Key' }]"
            style="margin-bottom: 0"
          >
            <a-input-password
              v-model:value="formData.api_key"
              placeholder="请输入 API Key"
              :visibility-toggle="true"
            />
          </a-form-item>
        </a-col>

        <a-col :span="24">
          <a-form-item label="URL" name="url" style="margin-bottom: 0">
            <a-input v-model:value="formData.url" placeholder="API 地址（自定义平台必填）" />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { loadAdminDicts, dictItems } from '@/composables/useAdminDict'
import { DictType } from '@/api/dictionary'
import {
  createWebSearch,
  updateWebSearch,
  type AiWebSearch,
} from '@/api/ai-web-search'

const props = defineProps<{
  open: boolean
  webSearch?: AiWebSearch | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const isEdit = computed(() => !!props.webSearch?.id)

onMounted(() => {
  loadAdminDicts([DictType.WEB_SEARCH_PLATFORM])
})

const formRef = ref()
const saving = ref(false)

const formData = reactive({
  name: '',
  platform: 'bocha',
  api_key: '',
  url: '',
  app_id: '',
  timeout: 30,
  max_results: 10,
  daily_quota: 0,
  priority: 50,
  api_secret: '',
  sort: 0,
  status: true,
})

// 监听 props.webSearch 变化，用于编辑回填
watch(
  () => props.webSearch,
  (val) => {
    if (val?.id) {
      formData.name = val.name || ''
      formData.platform = val.platform || 'bocha'
      formData.api_key = val.api_key || ''
      formData.url = val.url || ''
      formData.app_id = val.app_id || ''
      formData.timeout = val.timeout ?? 30
      formData.max_results = val.max_results ?? 10
      formData.daily_quota = val.daily_quota ?? 0
      formData.priority = val.priority ?? 50
      formData.api_secret = (val.property && val.property.api_secret) || ''
      formData.sort = val.sort || 0
      formData.status = val.status === 1
    } else {
      formData.name = ''
      formData.platform = 'bocha'
      formData.api_key = ''
      formData.url = ''
      formData.app_id = ''
      formData.timeout = 30
      formData.max_results = 10
      formData.daily_quota = 0
      formData.priority = 50
      formData.api_secret = ''
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
    const property: Record<string, any> = {}
    if (formData.api_secret) property.api_secret = formData.api_secret

    const payload = {
      name: formData.name,
      platform: formData.platform,
      api_key: formData.api_key,
      url: formData.url,
      app_id: formData.app_id,
      timeout: formData.timeout,
      max_results: formData.max_results,
      daily_quota: formData.daily_quota,
      priority: formData.priority,
      property,
      sort: formData.sort,
      status: formData.status ? 1 : 0,
    }

    if (isEdit.value && props.webSearch?.id) {
      await updateWebSearch({ id: props.webSearch.id, ...payload })
      message.success('更新成功')
    } else {
      await createWebSearch(payload)
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

<style lang="less" scoped>
.compact-form {
  :deep(.ant-form-item) {
    margin-bottom: 12px;
  }

  :deep(.ant-form-item-explain) {
    min-height: 0;
    font-size: 12px;
  }
}

.field-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
