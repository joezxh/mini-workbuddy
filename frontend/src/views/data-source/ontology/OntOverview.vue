<template>
  <div class="ont-overview">
    <a-descriptions size="small" bordered :column="2" class="ont-overview__desc">
      <a-descriptions-item :label="t2('编码')">{{ ontology?.code }}</a-descriptions-item>
      <a-descriptions-item :label="t2('名称')">{{ ontology?.name }}</a-descriptions-item>
      <a-descriptions-item :label="t2('状态')">
        <a-tag :color="statusColor(ontology?.status)">{{ ontology?.status }}</a-tag>
      </a-descriptions-item>
      <a-descriptions-item :label="t2('当前版本')">v{{ ontology?.current_version ?? 0 }}</a-descriptions-item>
      <a-descriptions-item :label="t2('命名空间')" :span="2">{{ ontology?.namespace_uri || '-' }}</a-descriptions-item>
      <a-descriptions-item :label="t2('描述')" :span="2">{{ ontology?.description || '-' }}</a-descriptions-item>
    </a-descriptions>

    <div class="ont-overview__cards">
      <a-card v-for="c in cards" :key="c.key" size="small" class="ont-overview__card">
        <a-statistic :title="c.title" :value="c.value" />
      </a-card>
    </div>

    <a-alert v-if="needsBuild" type="info" show-icon :message="t2('本体尚无发布版本，请先在「构建」页签抽取并审阅后发布')" />
  </div>
</template>

<script setup lang="ts">
/**
 * 本体总览（E3 详情 + E24 manifest）：统计卡 + 元信息 + 未发布提示。
 */
import { computed, ref, watch } from 'vue'
import { agentManifest } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{ ontology: any | null }>()

const manifest = ref<any>(null)

const cards = computed(() => {
  const o = props.ontology || {}
  return [
    { key: 'object', title: t2('对象数'), value: o.object_count ?? 0 },
    { key: 'relation', title: t2('关系数'), value: o.relation_count ?? 0 },
    { key: 'version', title: t2('版本数'), value: o.version_count ?? 0 },
    { key: 'cq', title: t2('CQ 通过率'), value: cqRate.value },
  ]
})

const cqRate = computed(() => {
  const r = manifest.value?.cq_pass_rate
  return r == null ? '-' : `${Math.round(r * 100)}%`
})

const needsBuild = computed(() => (props.ontology?.current_version ?? 0) === 0)

function statusColor(s?: string) {
  return ({ published: 'green', draft: 'blue', archived: 'default', stopped: 'orange' } as Record<string, string>)[s || ''] || 'default'
}

watch(
  () => props.ontology?.id,
  async (id) => {
    manifest.value = null
    if (!id) return
    try {
      manifest.value = await agentManifest(id)
    } catch {
      /* 忽略：总览降级只丢 CQ 率 */
    }
  },
  { immediate: true },
)
</script>

<style lang="less" scoped>
.ont-overview {
  &__desc {
    margin-bottom: 16px;
  }
  &__cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  &__card {
    text-align: left;
  }
}
</style>
