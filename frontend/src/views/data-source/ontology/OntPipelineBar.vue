<template>
  <div class="ont-pipeline">
    <a-spin :spinning="loading">
      <a-steps size="small" :current="doneCount">
        <a-step v-for="s in steps" :key="s.code" :title="s.label" :status="stepStatus(s)">
          <template #description>
            <span class="ont-pipeline__counts">{{ countsText(s) }}</span>
          </template>
        </a-step>
      </a-steps>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
/**
 * 五步链路拓扑步骤条（E38，只读，§6.6）：数据源表→数据处理→子图建模→本体库→本体应用。
 * 未完成步显灰（step 5 blocking=false 不阻断发布）。
 */
import { computed, ref, watch } from 'vue'
import { ontologyPipeline } from '@/api/dataops'

const props = defineProps<{ ontologyId: number | null }>()
const loading = ref(false)
const steps = ref<any[]>([])

const doneCount = computed(() => steps.value.filter((s) => s.done).length)

function stepStatus(s: any) {
  if (s.done) return 'finish'
  return 'wait'
}

function countsText(s: any) {
  const c = s.counts || {}
  return Object.entries(c)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${k}:${v}`)
    .join(' · ')
}

async function reload() {
  if (!props.ontologyId) {
    steps.value = []
    return
  }
  loading.value = true
  try {
    const resp: any = await ontologyPipeline(props.ontologyId)
    steps.value = resp?.steps || []
  } finally {
    loading.value = false
  }
}

watch(() => props.ontologyId, reload, { immediate: true })
defineExpose({ reload })
</script>

<style lang="less" scoped>
.ont-pipeline {
  padding: 8px 4px 16px;
  &__counts {
    font-size: 12px;
    color: var(--fg-mute, #999);
  }
}
</style>
