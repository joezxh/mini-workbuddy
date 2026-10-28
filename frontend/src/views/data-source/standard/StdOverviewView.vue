<template>
  <div class="std-overview">
    <!-- 计数卡片：目录 / 对象 / 关系 -->
    <div class="std-overview__cards">
      <a-card v-for="c in cards" :key="c.key" size="small" class="std-overview__card">
        <a-statistic :title="c.title" :value="c.value" />
      </a-card>
    </div>

    <!-- 校验三态分布 -->
    <div class="std-overview__chart">
      <BarChart v-if="checkTotal > 0" :data="checkData" :title="t('kbMgmt.overview.chart')" />
      <a-empty v-else :description="t('kbMgmt.overview.empty')" />
    </div>

    <a-input-search
      v-model:value="question"
      class="std-overview__search"
      :placeholder="t('kbMgmt.overview.searchPlaceholder')"
      :loading="searching"
      enter-button
      @search="onSearch"
    />

    <a-alert v-if="degraded" type="warning" show-icon :message="t('kbMgmt.overview.degraded')" />
    <a-alert
      v-else-if="summary"
      type="info"
      show-icon
      :message="t('kbMgmt.overview.summary')"
      :description="summary"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 标准总览（纯展示）：计数卡片 + 校验三态柱状 + NL 检索框。
 * 数据与请求都由 StandardManagement 持有，这里只呈现并把提问抛上去，
 * 便于无 DOM 的 SSR 渲染测直接断言统计值与降级提示。
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BarChart from '@/components/charts/BarChart.vue'

interface OverviewStats {
  catalogs: number
  objects: number
  relations: number
  relation_check: { hit: number; missing: number; conflict: number }
}

const props = withDefaults(
  defineProps<{
    stats?: OverviewStats
    loading?: boolean
    summary?: string
    degraded?: boolean
    searching?: boolean
  }>(),
  {
    stats: () => ({
      catalogs: 0,
      objects: 0,
      relations: 0,
      relation_check: { hit: 0, missing: 0, conflict: 0 },
    }),
    loading: false,
    summary: '',
    degraded: false,
    searching: false,
  },
)

const emit = defineEmits<{ (e: 'search', question: string): void }>()

const { t } = useI18n()
const question = ref('')

const cards = computed(() => [
  { key: 'catalogs', title: t('kbMgmt.overview.catalogs'), value: props.stats.catalogs },
  { key: 'objects', title: t('kbMgmt.overview.objects'), value: props.stats.objects },
  { key: 'relations', title: t('kbMgmt.overview.relations'), value: props.stats.relations },
])

const checkData = computed(() => [
  { name: t('kbMgmt.overview.hit'), value: props.stats.relation_check.hit, color: '#52c41a' },
  { name: t('kbMgmt.overview.missing'), value: props.stats.relation_check.missing, color: '#ff4d4f' },
  { name: t('kbMgmt.overview.conflict'), value: props.stats.relation_check.conflict, color: '#faad14' },
])
const checkTotal = computed(() => checkData.value.reduce((sum, d) => sum + (d.value || 0), 0))

function onSearch(value: string) {
  const q = (value || '').trim()
  if (!q) return
  emit('search', q)
}
</script>

<style scoped>
.std-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow: auto;
}
.std-overview__cards {
  display: flex;
  gap: 12px;
}
.std-overview__card {
  flex: 1;
}
.std-overview__chart {
  height: 200px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
}
.std-overview__search {
  max-width: 560px;
}
</style>
