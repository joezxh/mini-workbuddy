<template>
  <div class="std-overview">
    <!-- 计数卡片：目录 / 对象 / 关系 -->
    <div class="std-overview__cards">
      <a-card v-for="c in cards" :key="c.key" size="small" class="std-overview__card">
        <a-statistic :title="c.title" :value="c.value" />
      </a-card>
    </div>

    <!-- 校验三态分布：有数据给柱状，无数据把「为什么没有」和「下一步做什么」说清楚 -->
    <div class="std-overview__chart">
      <BarChart v-if="checkTotal > 0" :data="checkData" :title="t('kbMgmt.overview.chart')" />
      <div v-else class="std-overview__empty">
        <a-empty :description="t('kbMgmt.overview.empty')" />
        <p class="std-overview__empty-title">{{ noCheckTitle }}</p>
        <p class="std-overview__empty-hint">{{ noCheckHint }}</p>
      </div>
    </div>
    <!-- 有校验结果时把结论写完整：三态各多少 + 整体是否通过 -->
    <a-alert
      v-if="checkTotal > 0"
      :type="verdictPassed ? 'success' : 'warning'"
      show-icon
      :message="checkConclusion"
      :description="verdictHint"
    />

    <a-input-search
      v-model:value="question"
      class="std-overview__search"
      :placeholder="t('kbMgmt.overview.searchPlaceholder')"
      :loading="searching"
      enter-button
      @search="onSearch"
    />
    <p class="std-overview__hint">{{ t('kbMgmt.overview.searchHint') }}</p>

    <!-- AI 不可用：讲清原因，并说明已经自动改用关键字检索 -->
    <a-alert v-if="degraded" type="warning" show-icon :message="t('kbMgmt.overview.degraded')">
      <template #description>
        <p v-if="degradedReason">{{ t('kbMgmt.overview.degradedReason', { reason: degradedReason }) }}</p>
        <p>{{ t('kbMgmt.overview.fallbackNotice') }}</p>
      </template>
    </a-alert>

    <!-- 检索结果：摘要 + 命中对象/关系 code（与标准图高亮同一份数据） -->
    <div v-if="hasResult" class="std-overview__result">
      <div class="std-overview__result-head">
        <span class="std-overview__result-title">{{ resultTitle }}</span>
        <span class="std-overview__spacer" />
        <a-button v-if="hasHits" type="link" size="small" @click="emit('view-in-graph')">
          {{ t('kbMgmt.overview.viewInGraph') }}
        </a-button>
      </div>
      <p v-if="summary" class="std-overview__summary">{{ summary }}</p>
      <p v-else-if="keywordSummary" class="std-overview__summary">{{ keywordSummary }}</p>
      <a-empty v-if="searchEmpty" :description="t('kbMgmt.overview.noHit')" />
      <div v-if="hits.objects.length" class="std-overview__hits">
        <span class="std-overview__hits-label">{{ t('kbMgmt.overview.hitObjects') }}</span>
        <a-tag v-for="code in hits.objects" :key="code" color="blue">{{ code }}</a-tag>
      </div>
      <div v-if="hits.relations.length" class="std-overview__hits">
        <span class="std-overview__hits-label">{{ t('kbMgmt.overview.hitRelations') }}</span>
        <a-tag v-for="code in hits.relations" :key="code" color="purple">{{ code }}</a-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 标准总览（纯展示）：计数卡片 + 校验结论 + 检索结果。
 * 数据与请求都由 StandardManagement 持有，这里只呈现并把提问抛上去，
 * 便于无 DOM 的 SSR 渲染测直接断言统计值、结论文案与降级提示。
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
    /** 降级原因（后端透传的 LLM 异常），为空时只说「不可用」 */
    degradedReason?: string
    /** 命中的对象 / 关系 code，与标准图高亮同源 */
    hits?: { objects: string[]; relations: string[] }
    /** 检索跑完了但一条都没命中 */
    searchEmpty?: boolean
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
    degradedReason: '',
    hits: () => ({ objects: [], relations: [] }),
    searchEmpty: false,
    searching: false,
  },
)

const emit = defineEmits<{
  (e: 'search', question: string): void
  (e: 'view-in-graph'): void
}>()

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

/** 有校验数据时的完整结论：三态各多少 */
const checkConclusion = computed(() =>
  t('kbMgmt.overview.checkConclusion', {
    total: checkTotal.value,
    hit: props.stats.relation_check.hit,
    missing: props.stats.relation_check.missing,
    conflict: props.stats.relation_check.conflict,
  }),
)
/** 只有「缺失 / 冲突」都为零才算整体通过 */
const verdictPassed = computed(
  () => props.stats.relation_check.missing === 0 && props.stats.relation_check.conflict === 0,
)
const verdictHint = computed(() =>
  verdictPassed.value
    ? t('kbMgmt.overview.checkPass')
    : t('kbMgmt.overview.checkFail', {
        missing: props.stats.relation_check.missing,
        conflict: props.stats.relation_check.conflict,
      }),
)

/** 没有校验结论时区分两种情况：还没建关系 / 建了关系但没跑过校验 */
const hasRelations = computed(() => (props.stats.relations || 0) > 0)
const noCheckTitle = computed(() =>
  hasRelations.value
    ? t('kbMgmt.overview.noCheckHasRelation', { n: props.stats.relations })
    : t('kbMgmt.overview.noCheckNoRelation'),
)
const noCheckHint = computed(() =>
  hasRelations.value
    ? t('kbMgmt.overview.noCheckHasRelationHint')
    : t('kbMgmt.overview.noCheckNoRelationHint'),
)

const hasHits = computed(
  () => (props.hits?.objects?.length || 0) + (props.hits?.relations?.length || 0) > 0,
)
const hasResult = computed(() => !!props.summary || hasHits.value || props.searchEmpty)
/** 降级后走的是关键字检索，标题要跟着换，避免把关键字结果说成 AI 解读 */
const resultTitle = computed(() =>
  props.degraded ? t('kbMgmt.overview.keywordResult') : t('kbMgmt.overview.summary'),
)
/** 关键字模式没有 AI 摘要，用命中数凑一句结论，免得用户只看到一堆 code */
const keywordSummary = computed(() =>
  props.degraded && hasHits.value
    ? t('kbMgmt.overview.keywordSummary', {
        objects: props.hits.objects.length,
        relations: props.hits.relations.length,
      })
    : '',
)

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
  min-height: 200px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
}
/* 空态：标题之外再补一段解释 + 下一步引导 */
.std-overview__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 180px;
  padding: 0 16px;
  text-align: center;
}
.std-overview__empty-title {
  margin: 0;
  color: var(--fg);
}
.std-overview__empty-hint {
  margin: 0;
  color: var(--fg-muted);
  font-size: 12px;
  line-height: 1.6;
}
.std-overview__search {
  max-width: 560px;
}
.std-overview__hint {
  margin: -4px 0 0;
  color: var(--fg-muted);
  font-size: 12px;
}
.std-overview__result {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}
.std-overview__result-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.std-overview__result-title {
  font-weight: 600;
}
.std-overview__spacer {
  flex: 1;
}
.std-overview__summary {
  margin: 0;
  white-space: pre-wrap;
}
.std-overview__hits {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.std-overview__hits-label {
  color: var(--fg-muted);
  font-size: 12px;
}
</style>
