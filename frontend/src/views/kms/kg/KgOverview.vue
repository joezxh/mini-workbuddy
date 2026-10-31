<template>
  <div class="kg-overview">
    <a-spin :spinning="loading">
      <!-- ── 8 张统计卡 ───────────────────────────────────────────────── -->
      <div class="kg-stats">
        <div v-for="card in statCards" :key="card.key" class="kg-stat">
          <div class="kg-stat__label">
            <span
              v-if="card.color"
              class="kg-stat__dot"
              :style="{ background: card.color }"
            />
            {{ card.label }}
          </div>
          <div class="kg-stat__val">{{ card.value }}</div>
          <div v-if="card.sub" class="kg-muted">{{ card.sub }}</div>
        </div>
      </div>

      <!-- ── 类型分布（语义色）──────────────────────────────────────────── -->
      <div class="kg-grid2 kg-mt">
        <section class="kg-card">
          <header class="kg-card__hd">
            {{ t('kbMgmt.kg.entityTypeDistribution') }}
            <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.distByLabel') }}</span>
          </header>
          <div class="kg-card__bd">
            <div v-if="!typeRows.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div v-for="row in typeRows" :key="row.key" class="kg-distrow">
              <span
                class="kg-swatch"
                :style="{ background: typeTone(row.key).color }"
              />
              <span class="kg-distrow__label" :title="row.key">
                {{ typeLabel(row.key) || t('kbMgmt.kg.unclassified') }}
              </span>
              <span class="kg-bar">
                <span
                  class="kg-bar__fill"
                  :style="{ width: pct(row.value, maxType) + '%', background: typeTone(row.key).color }"
                />
              </span>
              <span class="kg-distrow__val">{{ row.value }}</span>
            </div>
          </div>
        </section>

        <section class="kg-card">
          <header class="kg-card__hd">
            {{ t('kbMgmt.kg.relationTypeDistribution') }}
            <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.distByRelationType') }}</span>
          </header>
          <div class="kg-card__bd">
            <div v-if="!relationRows.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div v-for="row in relationRows" :key="row.key" class="kg-distrow">
              <span class="kg-swatch" :style="{ background: 'var(--kg-primary)' }" />
              <span class="kg-distrow__label" :title="row.key">
                {{ row.key || t('kbMgmt.kg.freePredicate') }}
              </span>
              <span class="kg-bar">
                <span
                  class="kg-bar__fill"
                  :style="{ width: pct(row.value, maxRelation) + '%', background: 'var(--kg-primary)' }"
                />
              </span>
              <span class="kg-distrow__val">{{ row.value }}</span>
            </div>
          </div>
        </section>
      </div>

      <!-- ── 两阶段构建进度（唯一一处构建状态，不再重复）────────────────── -->
      <section class="kg-card kg-mt">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.buildStatus') }}
          <span class="kg-badge" :class="stateBadgeClass">
            <span v-if="status?.running" class="kg-dot" />
            {{ stateText }}
          </span>
        </header>
        <div class="kg-card__bd">
          <div class="kg-stage">
            <div class="kg-stage__hd">
              <span>{{ t('kbMgmt.kg.stageStructureWrite') }}</span>
              <span class="kg-stage__num">
                {{ status?.structure_done ?? 0 }} / {{ status?.segments ?? 0 }}
              </span>
            </div>
            <span class="kg-bar">
              <span
                class="kg-bar__fill"
                :style="{ width: structurePct + '%', background: 'var(--kg-ok)' }"
              />
            </span>
          </div>

          <div class="kg-stage">
            <div class="kg-stage__hd">
              <span>{{ t('kbMgmt.kg.stageVectorIndex') }}</span>
              <span class="kg-stage__num">
                {{ status?.vector_done ?? 0 }} / {{ status?.segments ?? 0 }}
              </span>
            </div>
            <span class="kg-bar">
              <span
                class="kg-bar__fill"
                :style="{ width: vectorPct + '%', background: 'var(--kg-primary)' }"
              />
            </span>
          </div>

          <div v-if="lastBuildText" class="kg-muted kg-stage__note">{{ lastBuildText }}</div>

          <div
            v-if="status && !status.neo4j_available"
            class="kg-alert kg-alert--warn kg-stage__note"
          >
            {{ t('kbMgmt.kg.neo4jDegradedAlert') }}
          </div>
        </div>
      </section>

      <!-- ── CDM 双向校验（三色卡）─────────────────────────────────────── -->
      <section class="kg-card kg-mt">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.cdmCheck') }}
          <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.cdmSubtitle') }}</span>
        </header>
        <div class="kg-card__bd">
          <div class="kg-cdm">
            <div class="kg-cdm__item kg-cdm__item--ok">
              <div class="kg-cdm__num">{{ cdm.hit ?? 0 }}</div>
              <div class="kg-cdm__label">{{ t('kbMgmt.kg.verdictHit') }}</div>
            </div>
            <div class="kg-cdm__item kg-cdm__item--warn">
              <div class="kg-cdm__num">{{ cdm.missing ?? 0 }}</div>
              <div class="kg-cdm__label">{{ t('kbMgmt.kg.verdictMissing') }}</div>
            </div>
            <div class="kg-cdm__item kg-cdm__item--err">
              <div class="kg-cdm__num">{{ cdm.conflict ?? 0 }}</div>
              <div class="kg-cdm__label">{{ t('kbMgmt.kg.verdictConflict') }}</div>
            </div>
          </div>

          <ul v-if="cdmItems.length" class="kg-cdm__list">
            <li v-for="item in cdmItems" :key="`${item.verdict}-${item.relation_code}-${item.from_type}-${item.to_type}`">
              <span class="kg-badge" :class="verdictBadgeClass(item.verdict)">
                {{ verdictLabel(item.verdict) }}
              </span>
              <span class="kg-cdm__code">{{ item.relation_code || '—' }}</span>
              <span class="kg-muted">{{ item.from_type || '?' }} → {{ item.to_type || '?' }}</span>
              <span v-if="item.count" class="kg-muted">×{{ item.count }}</span>
              <span v-if="item.detail" class="kg-muted kg-cdm__detail">{{ item.detail }}</span>
            </li>
          </ul>
          <div v-else class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>

          <div class="kg-note kg-cdm__foot">
            <span>{{ t('kbMgmt.kg.cdmConflictNote') }}</span>
            <a class="kg-link" @click="openStandardCenter">{{ t('kbMgmt.kg.cdmOpenCenter') }}</a>
            <template v-if="(cdm.uncovered || []).length">
              <span>· {{ t('kbMgmt.kg.verdictUncovered') }} {{ cdm.uncovered?.length }}</span>
            </template>
          </div>
        </div>
      </section>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import * as api from '@/api/kg'
import type { KgBuildStatus, KgCdmCheck, KgStats, KgVerdict } from '@/api/kg'
import { typeLabel, typeTone } from '@/components/common/graph/graphTheme'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const stats = ref<KgStats>({ entities: 0, relations: 0, by_type: {}, by_relation: {} })
const status = ref<KgBuildStatus | null>(null)
const cdm = ref<KgCdmCheck>({
  hit: 0, missing: 0, conflict: 0, items: [], uncovered: [],
  total_relations: 0, total_triples: 0,
})

const typeRows = computed(() =>
  Object.entries(stats.value.by_type || {})
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value),
)
const relationRows = computed(() =>
  Object.entries(stats.value.by_relation || {})
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value),
)
const maxType = computed(() => Math.max(1, ...typeRows.value.map((r) => r.value)))
const maxRelation = computed(() => Math.max(1, ...relationRows.value.map((r) => r.value)))

/** 统计卡：8 张（原型两行四列） */
const statCards = computed(() => {
  const segments = status.value?.segments ?? 0
  const structureDone = status.value?.structure_done ?? 0
  const vectorDone = status.value?.vector_done ?? 0
  const failed = status.value?.failed ?? 0
  return [
    {
      key: 'entities',
      label: t('kbMgmt.kg.statEntitiesTotal'),
      value: stats.value.entities ?? 0,
      color: 'var(--kg-primary)',
      sub: `${typeRows.value.length} ${t('kbMgmt.kg.statEntityTypes')}`,
    },
    {
      key: 'relations',
      label: t('kbMgmt.kg.statRelationsTotal'),
      value: stats.value.relations ?? 0,
      color: '#52c41a',
      sub: `${relationRows.value.length} ${t('kbMgmt.kg.statRelationTypes')}`,
    },
    {
      key: 'mentions',
      label: t('kbMgmt.kg.statMentionsTotal'),
      value: stats.value.mentions ?? 0,
      color: '#722ed1',
      sub: '',
    },
    {
      key: 'pending',
      label: t('kbMgmt.kg.statPendingReview'),
      value: stats.value.pending_review ?? 0,
      color: '#faad14',
      sub: '',
    },
    {
      key: 'segments',
      label: t('kbMgmt.kg.statSegments'),
      value: segments,
      color: '',
      sub: '',
    },
    {
      key: 'structure',
      label: t('kbMgmt.kg.statIndexedSegments'),
      value: structureDone,
      color: '',
      sub: `${structureDone - failed < 0 ? 0 : structureDone - failed} / ${structureDone}`,
    },
    {
      key: 'vector',
      label: t('kbMgmt.kg.stageVector'),
      value: vectorDone,
      color: '',
      sub: '',
    },
    {
      key: 'failed',
      label: t('kbMgmt.kg.statFailedSegments'),
      value: failed,
      color: '#ff4d4f',
      sub: '',
    },
  ]
})

const structurePct = computed(() => pct(status.value?.structure_done ?? 0, status.value?.segments ?? 0))
const vectorPct = computed(() => pct(status.value?.vector_done ?? 0, status.value?.segments ?? 0))

const stateText = computed(() => {
  switch (status.value?.state) {
    case 'running': return t('kbMgmt.kg.stateRunning')
    case 'ready': return t('kbMgmt.kg.badgeReady')
    case 'pending': return t('kbMgmt.kg.statePending')
    case 'partial_failed': return t('kbMgmt.kg.statePartialFailed')
    default: return t('kbMgmt.kg.stateNotBuilt')
  }
})

const stateBadgeClass = computed(() => {
  switch (status.value?.state) {
    case 'running': return 'kg-badge--warn'
    case 'ready': return 'kg-badge--ok'
    case 'partial_failed': return 'kg-badge--err'
    default: return ''
  }
})

/** 最近一次构建：时间 / 耗时 / 失败环节（来自 graph_build 元信息） */
const lastBuildText = computed(() => {
  const at = status.value?.last_build_at
  if (!at) return ''
  const time = formatTime(at)
  const duration = status.value?.last_build_duration
  const durationText = duration === null || duration === undefined ? '—' : `${duration}s`
  const step = status.value?.last_failed_step
  const stepText = step === 'structure'
    ? t('kbMgmt.kg.stageStructure')
    : step === 'vector'
      ? t('kbMgmt.kg.stageVector')
      : '—'
  return t('kbMgmt.kg.lastBuildNote', {
    time,
    duration: durationText,
    step: stepText,
    count: status.value?.last_failed_count ?? 0,
  })
})

const cdmItems = computed(() => (cdm.value.items || []).slice(0, 6))

function pct(value: number, total: number) {
  if (!total) return 0
  return Math.min(100, Math.round((value / total) * 100))
}

function formatTime(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function verdictLabel(verdict: KgVerdict) {
  if (verdict === 'hit') return t('kbMgmt.kg.verdictHit')
  if (verdict === 'missing') return t('kbMgmt.kg.verdictMissing')
  return t('kbMgmt.kg.verdictConflict')
}

function verdictBadgeClass(verdict: KgVerdict) {
  if (verdict === 'hit') return 'kg-badge--ok'
  if (verdict === 'missing') return 'kg-badge--warn'
  return 'kg-badge--err'
}

/** 「在标准中心查看」→ 数据源面板的标准管理页 */
function openStandardCenter() {
  router.push({ path: '/admin', query: { tab: 'kg-data-source' } })
}

async function load() {
  loading.value = true
  try {
    stats.value = (await api.getGraphStats(props.knowledgeId)) || stats.value
  } catch {
    // 概览统计失败不阻塞主流程（实体/关系页仍可用）
    stats.value = { entities: 0, relations: 0, by_type: {}, by_relation: {} }
  }
  try {
    status.value = await api.getGraphBuildStatus(props.knowledgeId)
  } catch {
    status.value = null
  }
  try {
    cdm.value = (await api.getCdmCheck(props.knowledgeId)) || cdm.value
  } catch {
    cdm.value = {
      hit: 0, missing: 0, conflict: 0, items: [], uncovered: [],
      total_relations: 0, total_triples: 0,
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kg-overview {
  padding-bottom: 4px;
}
.kg-mt {
  margin-top: 12px;
}

/* 统计卡：两行四列 */
.kg-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.kg-grid2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

/* 色块（分布条前的语义色点，静态不闪烁） */
.kg-swatch {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
}

/* 双阶段进度 */
.kg-stage + .kg-stage {
  margin-top: 10px;
}
.kg-stage__hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 5px;
  color: var(--kg-text-2);
  font-size: 12px;
}
.kg-stage__num {
  color: var(--kg-text);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.kg-stage__note {
  margin-top: 10px;
}

/* CDM 三色卡 */
.kg-cdm {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.kg-cdm__item {
  padding: 8px 12px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-sm);
  background: var(--kg-subtle);
}
.kg-cdm__item--ok {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
}
.kg-cdm__item--warn {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
}
.kg-cdm__item--err {
  border-color: var(--kg-err-border);
  background: var(--kg-err-bg);
}
.kg-cdm__num {
  color: var(--kg-text);
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  font-variant-numeric: tabular-nums;
}
.kg-cdm__label {
  color: var(--kg-text-3);
  font-size: 11.5px;
}
.kg-cdm__list {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}
.kg-cdm__list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px dashed var(--kg-border);
  font-size: 12px;
}
.kg-cdm__code {
  color: var(--kg-text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11.5px;
}
.kg-cdm__detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kg-cdm__foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px -14px -14px;
}
.kg-link {
  color: var(--kg-primary);
  white-space: nowrap;
}
.kg-link:hover {
  text-decoration: underline;
}
</style>
