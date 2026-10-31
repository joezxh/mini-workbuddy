<template>
  <section class="kg-insp">
    <header class="kg-insp__hd">
      <span>
        {{ selection?.kind === 'edge' ? t('kbMgmt.kg.relationDetail') : t('kbMgmt.kg.inspectorTitle') }}
      </span>
      <span v-if="relation && relation.status === 'suggested'" class="kg-insp__hd-ops">
        <a-button size="small" :loading="reviewing" @click="onReview('accepted')">
          {{ t('kbMgmt.kg.accept') }}
        </a-button>
        <a-popconfirm
          :title="t('kbMgmt.kg.confirmRejectRelation')"
          @confirm="onReview('rejected')"
        >
          <a-button size="small" danger :disabled="reviewing">{{ t('kbMgmt.kg.reject') }}</a-button>
        </a-popconfirm>
      </span>
    </header>

    <div class="kg-insp__bd">
      <a-spin :spinning="loading">
        <!-- 空态：未选中 -->
        <div v-if="!selection" class="kg-insp__empty">
          <div class="kg-insp__empty-icon">🔍</div>
          <div class="kg-insp__empty-t">{{ t('kbMgmt.kg.noSelectionAny') }}</div>
          <p>{{ t('kbMgmt.kg.noSelectionAnyDesc') }}</p>
        </div>

        <!-- 形态一：实体 -->
        <template v-else-if="entity">
          <dl class="kg-kv">
            <dt>{{ t('kbMgmt.kg.entityName') }}</dt>
            <dd class="is-strong">{{ entity.name }}</dd>
            <dt>{{ t('kbMgmt.kg.typeCode') }}</dt>
            <dd>
              <span
                v-if="entity.type_code"
                class="kg-type-tag"
                :style="typeTagStyle(entity.type_code)"
              >
                {{ typeLabel(entity.type_code) || entity.type_code }}
              </span>
              <span v-else class="kg-muted">{{ t('kbMgmt.kg.unclassified') }}</span>
              <code v-if="entity.type_code" class="kg-code">{{ entity.type_code }}</code>
            </dd>
            <dt>{{ t('kbMgmt.kg.normalizedName') }}</dt>
            <dd><code class="kg-code">{{ entity.entity_key }}</code></dd>
            <dt>{{ t('kbMgmt.kg.aliases') }}</dt>
            <dd>
              <template v-if="entity.aliases?.length">
                <span v-for="alias in entity.aliases" :key="alias" class="kg-insp__alias">
                  {{ alias }}
                </span>
              </template>
              <span v-else class="kg-muted">—</span>
            </dd>
            <dt>{{ t('kbMgmt.kg.mentionCount') }}</dt>
            <dd>{{ t('kbMgmt.kg.slicesCount', { count: entity.mention_count ?? 0 }) }}</dd>
            <dt>{{ t('kbMgmt.kg.status') }}</dt>
            <dd>
              <span class="kg-badge" :class="statusBadgeClass(entity.status)">
                {{ statusText(entity.status) }}
              </span>
            </dd>
            <dt>{{ t('kbMgmt.kg.colVector') }}</dt>
            <dd>
              <span class="kg-badge" :class="entity.has_vector ? 'kg-badge--ok' : ''">
                {{ entity.has_vector ? t('kbMgmt.kg.vectorIndexed') : t('kbMgmt.kg.vectorPending') }}
              </span>
            </dd>
          </dl>

          <div class="kg-sec-t">{{ t('kbMgmt.kg.propertyInstances') }}</div>
          <div class="kg-kvlist">
            <div v-if="!propertyRows.length" class="kg-kvrow">
              <span class="k kg-muted">{{ t('kbMgmt.kg.noData') }}</span>
            </div>
            <div v-for="row in propertyRows" :key="row.key" class="kg-kvrow">
              <span class="k">{{ row.key }}</span>
              <span class="v">{{ row.value }}</span>
            </div>
          </div>

          <div class="kg-sec-t">
            {{ t('kbMgmt.kg.adjacentRelations') }}（{{ adjacent.length }}）
          </div>
          <div>
            <div v-if="!adjacent.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div
              v-for="row in adjacent"
              :key="`adj-${row.id}`"
              class="kg-mini"
              @click="emit('inspect-relation', row.id)"
            >
              <span class="kg-type-tag kg-type-tag--rel">{{ row.code || '—' }}</span>
              <span class="kg-insp__dir">{{ row.dir }}</span>
              <span class="kg-insp__strong">{{ row.otherName }}</span>
              <span class="kg-mini__tail">{{ formatWeight(row.weight) }}</span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.kg.actionTitle') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('provenance', entity.id)">
              {{ t('kbMgmt.kg.provDrill') }}
            </a-button>
            <a-button size="small" @click="emit('locate', entity.id)">
              {{ t('kbMgmt.kg.locateInGraph') }}
            </a-button>
            <a-button size="small" @click="openStandardCenter">
              {{ t('kbMgmt.kg.standardCenter') }}
            </a-button>
          </div>
        </template>

        <!-- 形态二：关系 -->
        <template v-else-if="relation">
          <dl class="kg-kv">
            <dt>{{ t('kbMgmt.kg.colSource') }}</dt>
            <dd class="is-strong">
              <a class="kg-insp__link" @click="emit('inspect-entity', relation.from_entity_id)">
                {{ relation.from_entity_name || `#${relation.from_entity_id}` }}
              </a>
            </dd>
            <dt>{{ t('kbMgmt.kg.colTarget') }}</dt>
            <dd class="is-strong">
              <a class="kg-insp__link" @click="emit('inspect-entity', relation.to_entity_id)">
                {{ relation.to_entity_name || `#${relation.to_entity_id}` }}
              </a>
            </dd>
            <dt>{{ t('kbMgmt.kg.relationType') }}</dt>
            <dd>
              <span class="kg-type-tag kg-type-tag--rel">{{ relation.relation_code || '—' }}</span>
            </dd>
            <dt>{{ t('kbMgmt.kg.colWeight') }}</dt>
            <dd>
              <span class="kg-wbar">
                <span
                  class="kg-wbar__fill"
                  :style="{
                    width: `${Math.round(Number(relation.weight ?? 0) * 100)}%`,
                    background: weightColor(relation.weight),
                  }"
                />
              </span>
              <span class="kg-insp__weight">{{ formatWeight(relation.weight) }}</span>
            </dd>
            <dt>{{ t('kbMgmt.kg.status') }}</dt>
            <dd>
              <span class="kg-badge" :class="statusBadgeClass(relation.status)">
                {{ statusText(relation.status) }}
              </span>
            </dd>
            <dt>{{ t('kbMgmt.kg.colExtractor') }}</dt>
            <dd><code class="kg-code">{{ relation.extractor || '—' }}</code></dd>
            <dt>{{ t('kbMgmt.kg.mentionCount') }}</dt>
            <dd>{{ t('kbMgmt.kg.slicesCount', { count: relation.mention_count ?? 0 }) }}</dd>
          </dl>

          <div class="kg-sec-t">{{ t('kbMgmt.kg.extractionBasis') }}</div>
          <div v-if="evidenceText" class="kg-evidence">{{ evidenceText }}</div>
          <div v-else class="kg-evidence kg-evidence--empty">{{ t('kbMgmt.kg.noData') }}</div>

          <div class="kg-sec-t">
            {{ t('kbMgmt.kg.provenanceSegments', { count: relation.mention_count ?? 0 }) }}
          </div>
          <div v-if="!relation.mention_count" class="kg-muted">
            {{ t('kbMgmt.kg.noFailedSegments') }}
          </div>
          <div v-else class="kg-muted">{{ t('kbMgmt.kg.provSegTip') }}</div>

          <div class="kg-sec-t">{{ t('kbMgmt.kg.actionTitle') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('provenance', relation.from_entity_id)">
              {{ t('kbMgmt.kg.provDrill') }}
            </a-button>
            <a-button size="small" @click="emit('locate', relation.from_entity_id)">
              {{ t('kbMgmt.kg.locateInGraph') }}
            </a-button>
          </div>
        </template>

        <div v-else-if="!loading" class="kg-insp__empty">
          <div class="kg-insp__empty-t">{{ t('kbMgmt.kg.noData') }}</div>
        </div>
      </a-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * 图谱检视面板（306px 内联，原型 .insp）：实体 / 关系双形态。
 *
 * 选中态由父级（图谱画布）持有，本组件只负责按 id 拉详情并展示：
 * 实体 -> 基础信息 + 属性实例 + 邻接关系（可点进关系形态）；
 * 关系 -> 两端实体、权重、状态、抽取器、提及数、抽取依据，待评审可直接流转。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgEntity, KgRelation } from '@/api/kg'
import { formatWeight, typeLabel, typeTone, weightColor } from '@/components/common/graph/graphTheme'

const props = defineProps<{
  knowledgeId: number
  selection: { kind: 'node' | 'edge'; id: number } | null
}>()

const emit = defineEmits<{
  (e: 'inspect-entity', entityId: number): void
  (e: 'inspect-relation', relationId: number): void
  (e: 'locate', entityId: number): void
  (e: 'provenance', entityId: number): void
  (e: 'reviewed'): void
}>()

const { t } = useI18n()
const router = useRouter()

const entity = ref<KgEntity | null>(null)
const relation = ref<KgRelation | null>(null)
const loading = ref(false)
const reviewing = ref(false)

const propertyRows = computed(() =>
  Object.entries(entity.value?.properties || {}).map(([key, value]) => ({
    key,
    value: typeof value === 'string' ? value : JSON.stringify(value),
  })),
)

/** 邻接关系：方向 + 对端名，权重降序（枢纽实体的邻接可能很长，取前 50 条） */
const adjacent = computed(() => {
  const list = entity.value?.adjacent_relations || []
  const selfId = entity.value?.id
  return list
    .map((row) => ({
      id: row.id,
      code: row.relation_code,
      weight: row.weight,
      dir: row.from_entity_id === selfId ? '→' : '←',
      otherName:
        (row.from_entity_id === selfId ? row.to_entity_name : row.from_entity_name) ||
        `#${row.from_entity_id === selfId ? row.to_entity_id : row.from_entity_id}`,
    }))
    .sort((a, b) => Number(b.weight ?? 0) - Number(a.weight ?? 0))
    .slice(0, 50)
})

const evidenceText = computed(() => {
  const ev: any = relation.value?.evidence
  if (!ev) return ''
  if (typeof ev === 'string') return ev
  const plain = ev.quote ?? ev.text ?? ev.sentence ?? ev.content
  if (typeof plain === 'string' && plain) return plain
  try {
    return JSON.stringify(ev, null, 2)
  } catch {
    return ''
  }
})

function typeTagStyle(code: string) {
  const tone = typeTone(code)
  return { color: tone.fg, background: tone.bg, borderColor: tone.border }
}

const ENTITY_STATUS: Record<string, string> = {
  active: 'statusActive',
  suggested: 'statusSuggested',
  deprecated: 'statusDeprecated',
}
const RELATION_STATUS: Record<string, string> = {
  accepted: 'statusAccepted',
  suggested: 'statusSuggested',
  rejected: 'statusRejected',
}

function statusText(status?: string | null) {
  const key = ENTITY_STATUS[status || ''] || RELATION_STATUS[status || '']
  return key ? t(`kbMgmt.kg.${key}`) : String(status || '—')
}

function statusBadgeClass(status?: string | null) {
  if (status === 'active' || status === 'accepted') return 'kg-badge--ok'
  if (status === 'rejected' || status === 'deprecated') return 'kg-badge--err'
  if (status === 'suggested') return 'kg-badge--warn'
  return ''
}

function openStandardCenter() {
  // 无独立标准路由：落到标准管理工作台的「数据源」Tab
  void router.push({ path: '/admin', query: { tab: 'kg-data-source' } })
}

async function load() {
  const sel = props.selection
  if (!sel) {
    entity.value = null
    relation.value = null
    return
  }
  loading.value = true
  try {
    if (sel.kind === 'node') {
      relation.value = null
      entity.value = await api.getEntity(props.knowledgeId, sel.id)
    } else {
      entity.value = null
      relation.value = await api.getRelation(props.knowledgeId, sel.id)
    }
  } catch {
    entity.value = null
    relation.value = null
  } finally {
    loading.value = false
  }
}

async function onReview(verdict: 'accepted' | 'rejected') {
  if (!relation.value) return
  reviewing.value = true
  try {
    await api.reviewRelation(props.knowledgeId, relation.value.id, verdict)
    message.success(t('kbMgmt.kg.reviewDone'))
    await load()
    emit('reviewed')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    reviewing.value = false
  }
}

watch(
  () => [props.knowledgeId, props.selection?.kind, props.selection?.id],
  load,
  { immediate: true },
)
</script>
