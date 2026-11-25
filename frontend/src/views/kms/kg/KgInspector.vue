<template>
  <section class="kg-insp">
    <header class="kg-insp__hd">
      <span>
        {{ selection?.kind === 'edge' ? t('kbMgmt.kg.relationDetail') : t('kbMgmt.kg.inspectorTitle') }}
      </span>
      <span
        v-if="relation && relation.status === 'suggested'
          || entity && entity.status === 'suggested'"
        class="kg-insp__hd-ops"
      >
        <a-button size="small" :loading="reviewing" @click="onAcceptSelected">
          {{ t('kbMgmt.kg.accept') }}
        </a-button>
        <a-popconfirm
          :title="relation ? t('kbMgmt.kg.confirmRejectRelation') : t('kbMgmt.kg.confirmDeleteEntity')"
          @confirm="onRejectOrDeleteSelected"
        >
          <a-button size="small" danger :disabled="reviewing">
            {{ relation ? t('kbMgmt.kg.reject') : t('common.delete') }}
          </a-button>
        </a-popconfirm>
      </span>
      <span v-if="entity" class="kg-insp__hd-ops">
        <a-button size="small" @click="openEdit">{{ t('common.edit') }}</a-button>
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
              <span
                v-if="relation.review_verdict"
                class="kg-review-badge"
                :class="`kg-review-badge--${relation.review_verdict}`"
                :title="relation.review_note || ''"
              >
                {{ reviewBadgeText(relation.review_verdict) }}
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
          <!-- 关系自身的溯源切片内联列出（旧实现用 from_entity_id 近似，已修正） -->
          <div class="kg-kvlist kg-insp__mentions">
            <div v-if="!relationMentions.length" class="kg-muted">
              {{ t('kbMgmt.kg.noFailedSegments') }}
            </div>
            <div
              v-for="(m, idx) in relationMentions"
              :key="`rm-${m.segment_id}-${idx}`"
              class="kg-kvrow kg-kvrow--link"
              @click="openSegments(m.document_id)"
            >
              <span class="kg-kvrow__k">#{{ m.chunk_index }}</span>
              <span class="kg-kvrow__v">{{ mentionExcerpt(m.content) }}</span>
            </div>
          </div>
          <div class="kg-note">{{ t('kbMgmt.kg.provSegTip') }}</div>

          <div class="kg-sec-t">{{ t('kbMgmt.kg.actionTitle') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('provenance-edge', relation.id)">
              {{ t('kbMgmt.kg.provDrill') }}
            </a-button>
            <a-button size="small" @click="emit('locate-edge', relation.id)">
              {{ t('kbMgmt.kg.locateInGraph') }}
            </a-button>
          </div>
        </template>

        <div v-else-if="!loading" class="kg-insp__empty">
          <div class="kg-insp__empty-t">{{ t('kbMgmt.kg.noData') }}</div>
        </div>
      </a-spin>
    </div>

    <!-- 实体编辑（名称/类型/别名/属性键值；归一 key 派生自名称，随保存更新） -->
    <a-modal
      v-model:open="editOpen"
      :title="t('kbMgmt.kg.editEntity')"
      :confirm-loading="saving"
      @ok="onSaveEntity"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.kg.entityName')" required>
          <a-input v-model:value="editForm.name" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.entityType')">
          <a-auto-complete
            v-model:value="editForm.type_code"
            :options="typeCodeOptions"
            :placeholder="t('kbMgmt.kg.entityTypePlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.aliases')">
          <a-select v-model:value="editForm.aliases" mode="tags" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.properties')">
          <div class="kg-props-editor">
            <div v-for="(p, i) in editForm.propsList" :key="i" class="kg-props-editor__row">
              <a-input v-model:value="p.key" :placeholder="t('kbMgmt.kg.propKey')" style="width: 40%" />
              <a-input v-model:value="p.value" :placeholder="t('kbMgmt.kg.propValue')" />
              <a-button size="small" type="text" danger @click="editForm.propsList.splice(i, 1)">
                <template #icon><DeleteOutlined /></template>
              </a-button>
            </div>
            <a-button size="small" type="dashed" block @click="editForm.propsList.push({ key: '', value: '' })">
              <template #icon><PlusOutlined /></template>
              {{ t('kbMgmt.kg.addProp') }}
            </a-button>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分段详情抽屉（零改动复用） -->
    <SegmentDetail v-model:open="segmentOpen" :document-id="segmentDocId" />
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
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/kg'
import type { KgEntity, KgMentionSlice, KgRelation } from '@/api/kg'
import { formatWeight, typeLabel, typeTone, weightColor } from '@/components/common/graph/graphTheme'
import SegmentDetail from '@/views/kms/kb/SegmentDetail.vue'
import { SHELL_PATH } from '@/utils/shellTab'

const props = defineProps<{
  knowledgeId: number
  selection: { kind: 'node' | 'edge'; id: number } | null
}>()

const emit = defineEmits<{
  (e: 'inspect-entity', entityId: number): void
  (e: 'inspect-relation', relationId: number): void
  (e: 'locate', entityId: number): void
  (e: 'locate-edge', relationId: number): void
  (e: 'provenance', entityId: number): void
  (e: 'provenance-edge', relationId: number): void
  (e: 'reviewed'): void
}>()

const { t } = useI18n()
const router = useRouter()

const entity = ref<KgEntity | null>(null)
const relation = ref<KgRelation | null>(null)
const loading = ref(false)
const reviewing = ref(false)

/** 关系自身的溯源切片（内联展示，替代旧的 from_entity_id 近似） */
const relationMentions = ref<KgMentionSlice[]>([])

const segmentOpen = ref(false)
const segmentDocId = ref<string | null>(null)

function openSegments(docId: string) {
  segmentDocId.value = docId
  segmentOpen.value = true
}

function mentionExcerpt(content: string) {
  return !content || content.length <= 90 ? content || '' : `${content.slice(0, 90)}…`
}

/** 复核徽标文案 */
function reviewBadgeText(verdict: string) {
  if (verdict === 'supported') return t('kbMgmt.kg.reviewSupported')
  if (verdict === 'weak') return t('kbMgmt.kg.reviewWeak')
  if (verdict === 'unsupported') return t('kbMgmt.kg.reviewUnsupported')
  return t('kbMgmt.kg.reviewFailed')
}

// ── 实体编辑弹窗 ─────────────────────────────────────────────────────────
const editOpen = ref(false)
const saving = ref(false)
const editForm = ref({
  name: '',
  type_code: undefined as string | undefined,
  aliases: [] as string[],
  propsList: [] as { key: string; value: string }[],
})
const typeCodeOptions = computed(() =>
  entity.value?.type_code ? [{ value: entity.value.type_code }] : [],
)

function openEdit() {
  const ent = entity.value
  if (!ent) return
  editForm.value = {
    name: ent.name,
    type_code: ent.type_code || undefined,
    aliases: [...(ent.aliases || [])],
    propsList: Object.entries(ent.properties || {}).map(([key, value]) => ({
      key,
      value: value == null ? '' : String(value),
    })),
  }
  editOpen.value = true
}

async function onSaveEntity() {
  const ent = entity.value
  if (!ent) return
  if (!editForm.value.name.trim()) {
    message.warning(t('kbMgmt.kg.entityNameRequired'))
    return
  }
  saving.value = true
  try {
    const properties: Record<string, string> = {}
    for (const p of editForm.value.propsList) {
      const k = p.key.trim()
      if (k) properties[k] = p.value
    }
    await api.updateEntity(props.knowledgeId, ent.id, {
      name: editForm.value.name.trim(),
      type_code: editForm.value.type_code || undefined,
      aliases: editForm.value.aliases || [],
      properties,
    })
    message.success(t('common.saved'))
    editOpen.value = false
    await load()
    emit('reviewed')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.saveFailed'))
  } finally {
    saving.value = false
  }
}

/** 头部「接受」：实体 suggested→active，关系 suggested→accepted */
async function onAcceptSelected() {
  reviewing.value = true
  try {
    if (relation.value) {
      await api.reviewRelation(props.knowledgeId, relation.value.id, 'accepted')
    } else if (entity.value) {
      await api.acceptEntity(props.knowledgeId, entity.value.id)
    }
    message.success(t('kbMgmt.kg.reviewDone'))
    await load()
    emit('reviewed')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    reviewing.value = false
  }
}

/** 头部「驳回/删除」：关系驳回、实体删除（后端实体无 reject 态，删除即清理） */
async function onRejectOrDeleteSelected() {
  reviewing.value = true
  try {
    if (relation.value) {
      await api.reviewRelation(props.knowledgeId, relation.value.id, 'rejected')
    } else if (entity.value) {
      await api.deleteEntity(props.knowledgeId, entity.value.id)
    }
    message.success(t('kbMgmt.kg.reviewDone'))
    await load()
    emit('reviewed')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    reviewing.value = false
  }
}

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
  void router.push({ path: SHELL_PATH, query: { tab: 'kg-data-source' } })
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
      relationMentions.value = []
      entity.value = await api.getEntity(props.knowledgeId, sel.id)
    } else {
      entity.value = null
      relation.value = await api.getRelation(props.knowledgeId, sel.id)
      try {
        const res = await api.getRelationMentions(props.knowledgeId, sel.id)
        relationMentions.value = res?.items || []
      } catch {
        relationMentions.value = []
      }
    }
  } catch {
    entity.value = null
    relation.value = null
    relationMentions.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.knowledgeId, props.selection?.kind, props.selection?.id],
  load,
  { immediate: true },
)
</script>

<style scoped>
/* LLM 二次复核徽标（与关系表同款） */
.kg-review-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  margin-left: 6px;
  padding: 0 6px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  line-height: 1;
}
.kg-review-badge--supported {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-review-badge--weak {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-review-badge--unsupported {
  border-color: var(--kg-danger-border, #cf1322);
  background: var(--kg-danger-bg, #fff1f0);
  color: var(--kg-danger-fg, #cf1322);
}
.kg-review-badge--review_failed {
  color: var(--kg-text-3);
}
/* 关系溯源切片内联列表 */
.kg-insp__mentions {
  max-height: 220px;
  overflow: auto;
}
.kg-insp__mentions .kg-kvrow__v {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 属性键值编辑器 */
.kg-props-editor__row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
</style>
