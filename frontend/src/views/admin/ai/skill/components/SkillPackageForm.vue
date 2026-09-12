<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('skillMgmt.editPackage') : t('skillHub.newPackage')"
    :confirm-loading="loading"
    width="520px"
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
        :label="t('skillHub.pkgId')"
        name="package_id"
        :rules="[{ required: true, message: t('skillMgmt.pkgIdRequired') }, { pattern: /^[a-zA-Z0-9-]+$/, message: t('skillMgmt.idPattern') }]"
      >
        <a-input v-model:value="form.package_id" :placeholder="t('skillMgmt.pkgIdPlaceholder')" :disabled="isEdit" />
      </a-form-item>

      <a-form-item :label="t('skillMgmt.name')" name="name" :rules="[{ required: true, message: t('skillMgmt.nameRequired') }]">
        <a-input v-model:value="form.name" :placeholder="t('skillMgmt.namePlaceholder')" />
      </a-form-item>

      <a-form-item :label="t('skillHub.category')" name="category">
        <a-select v-model:value="form.category" :placeholder="t('skillMgmt.selectCategory')">
          <a-select-option v-for="opt in categoryOptions" :key="opt.item_code" :value="opt.item_code">
            {{ opt.item_name }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="t('skillMgmt.icon')" name="icon">
        <a-select v-model:value="form.icon" :placeholder="t('skillMgmt.selectIcon')">
          <a-select-option v-for="opt in ICON_OPTIONS" :key="opt.value" :value="opt.value">
            <span>{{ opt.label }}</span>
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="t('skillHub.version')" name="version">
        <a-input v-model:value="form.version" placeholder="1.0.0" />
      </a-form-item>

      <a-form-item :label="t('skillHub.description')" name="description">
        <a-textarea v-model:value="form.description" :rows="3" :placeholder="t('skillMgmt.descPlaceholder')" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { createSkillPackage, updateSkillPackage, ICON_OPTIONS } from '@/api/skill'
import { getDictionaryItems } from '@/api/dictionary'
import type { SkillPackage } from '@/api/skill'
import type { DictionaryItem } from '@/api/dictionary'

defineProps<{
  package?: SkillPackage | null
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()

const { t } = useI18n()

const visible = ref(false)
const loading = ref(false)
const formRef = ref()
const categoryOptions = ref<DictionaryItem[]>([])
const currentPackage = ref<SkillPackage | null>(null)

const isEdit = computed(() => !!currentPackage.value)

const defaultForm = () => ({
  package_id: '',
  name: '',
  category: 'other',
  icon: 'tool',
  version: '1.0.0',
  description: '',
})

const form = ref(defaultForm())

// 加载类目字典
async function loadCategoryOptions() {
  try {
    const res = await getDictionaryItems('skill_category')
    categoryOptions.value = res || []
  } catch (e) {
    console.error('加载类目字典失败:', e)
    categoryOptions.value = []
  }
}

function open(pkg?: SkillPackage | null) {
  currentPackage.value = pkg || null
  if (pkg) {
    form.value = {
      package_id: pkg.package_id,
      name: pkg.name,
      category: pkg.category || 'other',
      icon: pkg.icon || 'tool',
      version: pkg.version || '1.0.0',
      description: pkg.description || '',
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
    if (isEdit.value && currentPackage.value) {
      await updateSkillPackage(currentPackage.value.package_id, form.value)
      message.success(t('skillMgmt.updateSuccess'))
    } else {
      await createSkillPackage(form.value)
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

onMounted(() => {
  loadCategoryOptions()
})

defineExpose({ open })
</script>
