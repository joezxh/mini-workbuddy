<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑技能包' : '新建技能包'"
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
        label="包 ID"
        name="package_id"
        :rules="[{ required: true, message: '请输入包 ID' }, { pattern: /^[a-zA-Z0-9-]+$/, message: '仅支持字母、数字、中划线' }]"
      >
        <a-input v-model:value="form.package_id" placeholder="如 dataease" :disabled="isEdit" />
      </a-form-item>

      <a-form-item label="名称" name="name" :rules="[{ required: true, message: '请输入名称' }]">
        <a-input v-model:value="form.name" placeholder="如 DataEase 数据分析" />
      </a-form-item>

      <a-form-item label="类目" name="category">
        <a-select v-model:value="form.category" placeholder="选择类目">
          <a-select-option v-for="opt in categoryOptions" :key="opt.item_code" :value="opt.item_code">
            {{ opt.item_name }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="图标" name="icon">
        <a-select v-model:value="form.icon" placeholder="选择图标">
          <a-select-option v-for="opt in ICON_OPTIONS" :key="opt.value" :value="opt.value">
            <span>{{ opt.label }}</span>
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="版本" name="version">
        <a-input v-model:value="form.version" placeholder="1.0.0" />
      </a-form-item>

      <a-form-item label="描述" name="description">
        <a-textarea v-model:value="form.description" :rows="3" placeholder="简要描述该技能包的功能..." />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
      message.success('更新成功')
    } else {
      await createSkillPackage(form.value)
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

onMounted(() => {
  loadCategoryOptions()
})

defineExpose({ open })
</script>
