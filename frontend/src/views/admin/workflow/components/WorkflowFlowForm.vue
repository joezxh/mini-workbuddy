<template>
  <a-form :model="form" layout="vertical" style="max-width: 720px">
    <a-form-item label="流程编码" required>
      <a-input v-model:value="form.flow_code" :disabled="!!props.initial" />
    </a-form-item>
    <a-form-item label="名称" required>
      <a-input v-model:value="form.flow_name" />
    </a-form-item>
    <a-row :gutter="16">
      <a-col :span="12">
        <a-form-item label="平台类型" required>
          <a-select v-model:value="form.platform_type" :options="platformOptions" />
        </a-form-item>
      </a-col>
      <a-col :span="12">
        <a-form-item label="流程类型" required>
          <a-select v-model:value="form.flow_type" :options="flowTypeOptions" />
        </a-form-item>
      </a-col>
    </a-row>
    <a-form-item label="API 基地址" required>
      <a-input v-model:value="form.base_url" placeholder="https://api.dify.net" />
    </a-form-item>
    <a-form-item label="API Key" :required="!props.initial">
      <a-input-password v-model:value="form.api_key" :placeholder="props.initial ? '留空不修改' : '输入 API Key'" />
    </a-form-item>
    <a-form-item label="描述">
      <a-textarea v-model:value="form.description" :rows="3" />
    </a-form-item>
    <a-form-item>
      <a-space>
        <a-button type="primary" :loading="saving" @click="handleSave">保存</a-button>
        <a-button @click="$emit('saved')">取消</a-button>
      </a-space>
    </a-form-item>
  </a-form>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { createFlow, updateFlow, getPlatformTypes } from '@/api/workflow'
import { message } from 'ant-design-vue'

const props = defineProps<{ initial: any }>()
const emit = defineEmits(['saved'])

const form = reactive<any>({
  flow_code: '', flow_name: '', platform_type: 'dify', flow_type: 'Workflow',
  base_url: '', api_key: '', description: '',
})
const saving = ref(false)
const platformOptions = ref<any[]>([])
const flowTypeOptions = ref<any[]>([])

onMounted(async () => {
  if (props.initial) {
    Object.assign(form, { ...props.initial, api_key: '' })
  }
  const res = await getPlatformTypes()
  platformOptions.value = res.data.platform_types.map((v: string) => ({ label: v, value: v }))
  flowTypeOptions.value = res.data.flow_types.map((v: string) => ({ label: v, value: v }))
})

async function handleSave() {
  saving.value = true
  try {
    if (props.initial?.id) {
      await updateFlow(props.initial.id, form)
    } else {
      await createFlow(form)
    }
    message.success('保存成功')
    emit('saved')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}
</script>
