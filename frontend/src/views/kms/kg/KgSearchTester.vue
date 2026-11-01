<template>
  <div class="kg-search-tester">
    <!-- 查询栏 -->
    <section class="kg-card">
      <header class="kg-card__hd">
        {{ t('kbMgmt.kg.tabSearchTest') }}
        <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.graphChannel') }} × RRF</span>
      </header>
      <div class="kg-card__bd">
        <div class="kg-search-tester__bar">
          <div class="kg-search-tester__bar-l">
            <a-input
              v-model:value="query"
              :placeholder="t('kbMgmt.kg.searchQueryPlaceholder')"
              class="kg-search-tester__input"
              allow-clear
              @pressEnter="onSearch"
            />
            <a-input-number
              v-model:value="topK"
              :min="1"
              :max="50"
              size="small"
              style="width: 88px"
            />
            <a-checkbox v-model:checked="useGraph" :disabled="compare">
              {{ t('kbMgmt.kg.graphChannel') }}
            </a-checkbox>
            <a-checkbox v-model:checked="compare">{{ t('kbMgmt.kg.compareMode') }}</a-checkbox>
            <a-button type="primary" size="small" :loading="loading" @click="onSearch">
              {{ t('kbMgmt.kg.search') }}
            </a-button>
          </div>
          <div class="kg-search-tester__bar-r">
            <span class="kg-badge kg-badge--ok">{{ t('kbMgmt.kg.fusionTag') }}</span>
            <span class="kg-muted kg-search-tester__rrf">
              rrf_k = 60 · graph_weight = {{ formatNumber(cfg?.graph_weight, 2) }} · ppr_damping =
              {{ formatNumber(cfg?.ppr_damping, 2) }} · graph_top_k = {{ cfg?.graph_top_k ?? '—' }}
            </span>
          </div>
        </div>

        <!-- 索引模式与图通道状态（只读，来自库配置 / 运行时探测） -->
        <div class="kg-search-tester__params">
          <span v-if="indexMode" class="kg-badge">{{ indexMode }}</span>
          <span
            class="kg-badge"
            :class="graphEnabled === false ? 'kg-badge--warn' : 'kg-badge--ok'"
          >
            {{ t('kbMgmt.kg.graphChannel') }}:
            {{ graphEnabled === false ? t('kbMgmt.kg.badgeDegraded') : t('kbMgmt.kg.badgeReady') }}
          </span>
        </div>

        <div v-if="graphEnabled === false" class="kg-alert kg-alert--warn kg-search-tester__alert">
          {{ t('kbMgmt.kg.graphDegradedDesc') }}
        </div>
      </div>
      <div v-if="mode === 'compare'" class="kg-note">{{ t('kbMgmt.kg.searchFooterNote') }}</div>
    </section>

    <!-- 对比模式：真双跑（左：仅向量 use_graph=false / 右：融合） -->
    <div v-if="mode === 'compare'" class="kg-search-tester__grid">
      <section class="kg-card">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.onlyVector') }}
          <span class="kg-card__hd-sub">{{ baseHits.length }}</span>
        </header>
        <div class="kg-card__bd kg-search-tester__list">
          <div v-if="!baseHits.length" class="kg-muted">{{ t('kbMgmt.kg.noSearchResult') }}</div>
          <article v-for="(hit, idx) in baseHits" :key="hitKey(hit, idx)" class="kg-hit">
            <header class="kg-hit__h">
              <span class="kg-hit__sc">score {{ formatScore(hit.score) }}</span>
              <span class="kg-tag kg-tag--p">chunk</span>
              <span class="kg-muted">{{ hit.document_id }} · #{{ hit.chunk_index }}</span>
            </header>
            <div class="kg-hit__b">{{ hit.content }}</div>
          </article>
        </div>
      </section>

      <section class="kg-card">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.fusedResult') }}
          <span class="kg-card__hd-sub">
            {{ fusedHits.length }} · +{{ newCount }}
          </span>
        </header>
        <div class="kg-card__bd kg-search-tester__list">
          <div v-if="!fusedHits.length" class="kg-muted">{{ t('kbMgmt.kg.noSearchResult') }}</div>
          <article
            v-for="(hit, idx) in fusedHits"
            :key="hitKey(hit, idx)"
            class="kg-hit"
            :class="{ 'kg-hit--new': isNew(hit) }"
          >
            <header class="kg-hit__h">
              <span class="kg-hit__sc">score {{ formatScore(hit.score) }}</span>
              <span
                v-for="s in hit.metadata?.fusion_sources || []"
                :key="s"
                class="kg-tag"
                :class="`kg-tag--${s === 'graph' ? 'g' : 'p'}`"
              >
                {{ s }}
              </span>
              <span class="kg-muted">{{ hit.document_id }} · #{{ hit.chunk_index }}</span>
            </header>
            <div class="kg-hit__b">{{ hit.content }}</div>
            <div v-if="pathTokens(hit).length" class="kg-hit__path">
              <span v-for="(tk, i) in pathTokens(hit)" :key="`p-${i}`" :class="tk.cls">
                {{ tk.text }}
              </span>
            </div>
          </article>
        </div>
      </section>
    </div>

    <!-- 单通道模式：图谱通道关闭即为纯向量召回 -->
    <section v-else class="kg-card kg-search-tester__single">
      <header class="kg-card__hd">
        {{ useGraph ? t('kbMgmt.kg.fusedResult') : t('kbMgmt.kg.onlyVector') }}
        <span class="kg-card__hd-sub">{{ fusedHits.length }}</span>
      </header>
      <div class="kg-card__bd kg-search-tester__list">
        <div v-if="!fusedHits.length" class="kg-muted">
          {{ loading ? '…' : t('kbMgmt.kg.noSearchResult') }}
        </div>
        <article v-for="(hit, idx) in fusedHits" :key="hitKey(hit, idx)" class="kg-hit">
          <header class="kg-hit__h">
            <span class="kg-hit__sc">score {{ formatScore(hit.score) }}</span>
            <span
              v-for="s in hit.metadata?.fusion_sources || []"
              :key="s"
              class="kg-tag"
              :class="`kg-tag--${s === 'graph' ? 'g' : 'p'}`"
            >
              {{ s }}
            </span>
            <span v-if="hit.metadata?.score_type" class="kg-muted">
              {{ hit.metadata.score_type }}
            </span>
            <span class="kg-muted">{{ hit.document_id }} · #{{ hit.chunk_index }}</span>
          </header>
          <div class="kg-hit__b">{{ hit.content }}</div>
          <div v-if="pathTokens(hit).length" class="kg-hit__path">
            <span v-for="(tk, i) in pathTokens(hit)" :key="`p-${i}`" :class="tk.cls">
              {{ tk.text }}
            </span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 图谱增强检索测试：展示融合来源（chunk / graph）与命中路径。
 *
 * 「对比模式」是真双跑——两次独立请求（use_graph=false / 默认融合），
 * 左侧永远是纯向量基线，右侧是融合结果，右栏的「+N」即图通道的净增量。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgGraphConfig, KgRetrieveHit } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const query = ref('')
const topK = ref(10)
const loading = ref(false)
const mode = ref<'fused' | 'compare'>('fused')
/** 单通道是否走图通道（对比模式恒为真双跑，此开关不生效） */
const useGraph = ref(true)
/** 「对比模式」复选框：与 mode 双向绑定 */
const compare = computed({
  get: () => mode.value === 'compare',
  set: (value: boolean) => {
    mode.value = value ? 'compare' : 'fused'
  },
})
const baseHits = ref<KgRetrieveHit[]>([])
const fusedHits = ref<KgRetrieveHit[]>([])
const graphEnabled = ref<boolean | null>(null)
const indexMode = ref('')
const cfg = ref<KgGraphConfig | null>(null)

const baseKeys = computed(() => new Set(baseHits.value.map(hitKey)))

/** 图通道带来的净新增命中数（对比模式右栏角标） */
const newCount = computed(
  () => fusedHits.value.filter((h) => !baseKeys.value.has(hitKey(h))).length,
)

function hitKey(hit: KgRetrieveHit, idx = -1) {
  if (hit?.document_id === undefined && idx >= 0) return `idx-${idx}`
  return `${hit?.document_id}::${hit?.chunk_index}`
}

function isNew(hit: KgRetrieveHit) {
  return !baseKeys.value.has(hitKey(hit))
}

function seeds(hit: KgRetrieveHit): string[] {
  const raw = (hit.metadata?.graph_seed_entities || []) as unknown[]
  return raw.map((s) => String(s))
}

/** 命中路径：优先用后端 BFS 回传的真实图路径，缺失时退化到种子实体 */
function hitPath(hit: KgRetrieveHit): { nodes: string[]; relations: string[] } {
  const raw = hit.metadata?.graph_path
  if (raw?.nodes?.length) {
    return {
      nodes: raw.nodes.map((n) => n.name || n.label || n.id),
      relations: (raw.relations || []).map((r) => String(r)),
    }
  }
  return { nodes: seeds(hit), relations: [] }
}

interface PathToken {
  cls: string
  text: string
}

/** 路径摊平成面包屑：实体 ── 关系 ──▶ 实体 ── 提及 ──▶ 命中切片 */
function pathTokens(hit: KgRetrieveHit): PathToken[] {
  const { nodes, relations } = hitPath(hit)
  if (!nodes.length) return []
  const tokens: PathToken[] = []
  nodes.forEach((name, i) => {
    if (i > 0) {
      tokens.push({ cls: 'kg-path__ar', text: '──' })
      if (relations[i - 1]) tokens.push({ cls: 'kg-path__rel', text: relations[i - 1] })
      tokens.push({ cls: 'kg-path__ar', text: '──▶' })
    }
    tokens.push({ cls: 'kg-path__node', text: name })
  })
  tokens.push({ cls: 'kg-path__ar', text: '──' })
  tokens.push({ cls: 'kg-path__rel', text: t('kbMgmt.kg.pathMention') })
  tokens.push({ cls: 'kg-path__ar', text: '──▶' })
  tokens.push({ cls: 'kg-muted', text: t('kbMgmt.kg.hitSegment', { id: hit.chunk_index }) })
  return tokens
}

function formatScore(score?: number) {
  return typeof score === 'number' ? score.toFixed(4) : '—'
}

function formatNumber(value?: number, digits = 2) {
  return typeof value === 'number' ? value.toFixed(digits) : '—'
}

async function loadConfig() {
  try {
    cfg.value = await api.getGraphConfig(props.knowledgeId)
  } catch {
    cfg.value = null
  }
}

async function onSearch() {
  const keyword = query.value.trim()
  if (!keyword) {
    message.warning(t('kbMgmt.kg.searchQueryRequired'))
    return
  }
  loading.value = true
  try {
    if (mode.value === 'compare') {
      // 真双跑：基线（关闭图通道）+ 融合（默认），互不影响
      const [base, fused] = await Promise.all([
        api.retrieveGraph(props.knowledgeId, keyword, topK.value, { useGraph: false }),
        api.retrieveGraph(props.knowledgeId, keyword, topK.value, { useGraph: true }),
      ])
      baseHits.value = base?.results || []
      fusedHits.value = fused?.results || []
      graphEnabled.value = fused?.graph_enabled ?? false
      indexMode.value = fused?.index_mode || base?.index_mode || ''
    } else {
      const res = await api.retrieveGraph(props.knowledgeId, keyword, topK.value, {
        useGraph: useGraph.value,
      })
      fusedHits.value = res?.results || []
      baseHits.value = []
      graphEnabled.value = res?.graph_enabled ?? false
      indexMode.value = res?.index_mode || ''
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.searchFailed'))
    baseHits.value = []
    fusedHits.value = []
    graphEnabled.value = false
  } finally {
    loading.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.kg-search-tester__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  flex-wrap: wrap;
}
.kg-search-tester__bar-l,
.kg-search-tester__bar-r {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.kg-search-tester__input {
  width: 320px;
  min-width: 200px;
  flex: 1;
  max-width: 420px;
}
.kg-search-tester__rrf {
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}
.kg-search-tester__params {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.kg-search-tester__alert {
  margin-top: 10px;
  margin-bottom: 0;
}
.kg-search-tester__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.kg-search-tester__single {
  margin-top: 12px;
}
.kg-search-tester__list {
  max-height: 520px;
  overflow: auto;
}

/* 命中卡片：与原型 .hit / .hit-h / .sc / .hit-b / .path 同口径 */
.kg-hit {
  padding: 11px 13px;
  margin-bottom: 9px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.kg-hit:hover {
  border-color: var(--kg-border-2);
  box-shadow: var(--kg-shadow-sm);
}
.kg-hit--new {
  background: var(--kg-tint);
}
.kg-hit__h {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
  flex-wrap: wrap;
}
.kg-hit__sc {
  padding: 1px 7px;
  border-radius: var(--kg-r-xs);
  background: var(--kg-tint);
  color: var(--kg-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11.5px;
}
.kg-tag {
  display: inline-flex;
  align-items: center;
  height: 21px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.kg-tag--g {
  background: #f9f0ff;
  color: #722ed1;
  border-color: #efdbff;
}
.kg-tag--p {
  background: var(--kg-tint);
  color: var(--kg-info-fg);
  border-color: var(--kg-info-border);
}
[data-theme='dark'] .kg-tag--g {
  background: rgba(146, 84, 222, 0.16);
  color: #b37feb;
  border-color: rgba(146, 84, 222, 0.34);
}
.kg-hit__b {
  color: var(--kg-text-2);
  font-size: 12.5px;
  line-height: 1.6;
}
.kg-hit__path {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 8px;
  padding: 9px 11px;
  border-radius: var(--kg-r-sm);
  background: var(--kg-subtle);
  color: var(--kg-text-2);
  font-size: 11.5px;
}
.kg-path__node {
  color: var(--kg-text);
  font-weight: 600;
}
.kg-path__rel {
  color: var(--kg-primary);
  font-weight: 500;
}
.kg-path__ar {
  color: var(--kg-text-3);
}
</style>
