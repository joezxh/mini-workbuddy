<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('skillMgmt.editScript') : t('skillHub.newScript')"
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
        :label="t('skillMgmt.scriptId')"
        name="script_id"
        :rules="[{ required: true, message: t('skillMgmt.scriptIdRequired') }, { pattern: /^[a-z0-9-]+$/, message: t('skillMgmt.scriptIdPattern') }]"
      >
        <a-input v-model:value="form.script_id" :placeholder="t('skillMgmt.scriptIdPlaceholder')" :disabled="isEdit" />
      </a-form-item>

      <a-form-item :label="t('skillMgmt.name')" name="name" :rules="[{ required: true, message: t('skillMgmt.nameRequired') }]">
        <a-input v-model:value="form.name" :placeholder="t('skillMgmt.scriptNamePlaceholder')" />
      </a-form-item>

      <a-form-item :label="t('skillMgmt.command')" name="command" :rules="[{ required: true, message: t('skillMgmt.commandRequired') }]">
        <a-input v-model:value="form.command" placeholder="如 python scripts/inspect.py --list" />
      </a-form-item>

      <a-form-item :label="t('skillHub.description')" name="description">
        <a-textarea v-model:value="form.description" :rows="2" :placeholder="t('skillMgmt.scriptDescPlaceholder')" />
      </a-form-item>

      <a-form-item :label="t('skillMgmt.sort')" name="sort_order">
        <a-input-number v-model:value="form.sort_order" :min="0" :max="9999" style="width:100%" />
      </a-form-item>

      <a-form-item :label="t('skillHub.enabled')" name="enabled">
        <a-switch v-model:checked="form.enabled" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

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
      message.success(t('skillMgmt.updateSuccess'))
    } else {
      await createScript(props.packageId, form.value)
      message.success(t('skillMgmt.createSuccess'))
    }
    visible.value = false
    emit('success')
  } catch (err: any) {
    message.error(err?.data?.detail || err?.message || t('common.error'))
  } finally {
    loading.value = false
  }
}

defineExpose({ open })
</script>
