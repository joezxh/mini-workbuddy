<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑脚本' : '新建脚本'"
    :confirm-loading="loading"
    width="600px"
    @ok="handleSubmit"
    @cancel="visible = false"
  >
    <a-form
      ref="formRef"
      :model="form"
      :label-col="{ span: 6 }"
      :wrapper-col="{ span: 16 }"
      autocomplete="off"
    >
      <a-form-item
        label="脚本 ID"
        name="script_id"
        :rules="[{ required: true, message: '请输入脚本 ID' }, { pattern: /^[a-z0-9-]+$/, message: '仅支持小写字母、数字、中划线' }]"
      >
        <a-input v-model:value="form.script_id" placeholder="如 list-datasets" :disabled="isEdit" />
      </a-form-item>

      <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
        <a-input v-model:value="form.name" placeholder="如 查询数据集" />
      </a-form-item>

      <a-form-item label="命令" name="command" :rules="[{ required: true, message: '请输入执行命令' }]">
        <a-input v-model:value="form.command" placeholder="如 python scripts/inspect.py --list" />
      </a-form-item>

      <a-form-item label="描述" name="description">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="简要描述该脚本的功能..." />
      </a-form-item>

      <a-form-item label="排序" name="sort_order">
        <a-input-number v-model:value="form.sort_order" :min="0" :max="9999" style="width:100%" />
      </a-form-item>

      <a-form-item label="启用" name="enabled">
        <a-switch v-model:checked="form.enabled" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { createScript, updateScript } from '@/api/skill'
import type { SkillScript } from '@/api/skill'

const props = defineProps<{
  packageId: string
  script?: SkillScript | null
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()

const visible = ref(false)
const loading = ref(false)
const formRef = ref()

const isEdit = computed(() => !!props.script)

const defaultForm = () => ({
  script_id: '',
  name: '',
  command: '',
  description: '',
  sort_order: 0,
  enabled: true,
})

const form = ref(defaultForm())

function open(script?: SkillScript | null) {
  if (script) {
    form.value = {
      script_id: script.script_id,
      name: script.name,
      command: script.command,
      description: script.description || '',
      sort_order: script.sort_order || 0,
      enabled: script.enabled !== false,
    }
  } else {
    form.value = defaultForm()
  }
  visible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    if (isEdit.value && props.script) {
      await updateScript(props.packageId, props.script.script_id, form.value)
      message.success('更新成功')
    } else {
      await createScript(props.packageId, form.value)
      message.success('创建成功')
    }
    visible.value = false
    emit('success')
  } catch (err: any) {
    message.error(err?.data?.detail || err?.message || '操作失败')
  } finally {
    loading.value = false
  }
}

defineExpose({ open })
</script>
