<template>
  <a-select
    v-model:value="selected"
    class="tenant-filter-select"
    allow-clear
    :placeholder="t('sys.tenant.allTenants')"
    :loading="loading"
    @change="onChange"
  >
    <a-select-option v-for="t in options" :key="t.tenant_id" :value="t.tenant_id">
      {{ t.name }}
    </a-select-option>
  </a-select>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getTenantSimpleList, type TenantSimpleVO } from '@/api/tenant'

const props = defineProps<{
  modelValue?: number | undefined
}>()

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number | undefined): void
  (e: 'change', value: number | undefined): void
}>()

// 受控组件：v-model 直接同步父级值，无需额外本地状态
const selected = computed<number | undefined>({
  get: () => props.modelValue,
  set: (v) => {
    emit('update:modelValue', v)
    emit('change', v)
  }
})

const options = ref<TenantSimpleVO[]>([])
const loading = ref(false)

onMounted(async () => {
  try {
    loading.value = true
    const res = await getTenantSimpleList()
    options.value = (res as any) || []
  } catch (e) {
    options.value = []
  } finally {
    loading.value = false
  }
})

const onChange = (val: number | undefined) => {
  // 已通过 computed setter 同步，这里仅用于触发（如需父级额外逻辑可监听 change）
  emit('change', val)
}
</script>

<style scoped>
.tenant-filter-select {
  min-width: 220px;
}
</style>
