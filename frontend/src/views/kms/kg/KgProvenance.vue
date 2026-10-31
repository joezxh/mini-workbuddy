<template>
  <div class="kg-provenance">
    <div class="kg-provenance__grid">
      <!-- 左栏：实体 / 关系 → 切片 -->
      <section class="kg-card">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.provLeftTitle') }}
          <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.slicesCount', { count: mentions.length }) }}</span>
        </header>
        <div class="kg-card__bd">
          <a-input
            v-model:value="keyword"
            size="small"
            allow-clear
            :placeholder="t('kbMgmt.kg.provSearchPh')"
          />

          <!-- 可溯源对象：实体在前、关系在后（均按提及数降序） -->
          <div class="kg-prov-picker">
            <div v-if="!pickerItems.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <button
              v-for="item in pickerItems"
              :key="`${item.kind}-${item.id}`"
              type="button"
              class="kg-mini"
              :class="{ 'kg-mini--on': isPicked(item) }"
              @click="pick(item)"
            >
              <span
                class="kg-type-tag"
                :style="{
                  color: item.tone.fg,
                  background: item.tone.bg,
                  borderColor: item.tone.border,
                }"
              >
                {{ item.tag }}
              </span>
              <span class="kg-mini__name">{{ item.name }}</span>
              <span class="kg-muted kg-mini__tail">
                {{ t('kbMgmt.kg.slicesCount', { count: item.count }) }}
              </span>
            </button>
          </div>

          <div class="kg-sec-t">
            {{ t('kbMgmt.kg.provSourceSegments', { name: pickedName || '—' }) }}
          </div>
          <div class="kg-kvlist">
            <div v-if="!mentions.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div
              v-for="(item, idx) in mentions"
              :key="`m-${item.segment_id}-${idx}`"
              class="kg-kvrow kg-kvrow--link"
              :title="item.content"
              @click="openSegments(item.document_id)"
            >
              <span class="kg-kvrow__k">#{{ item.chunk_index }}</span>
              <span class="kg-kvrow__v">{{ item.document_id }}</span>
            </div>
          </div>
          <div class="kg-note">{{ t('kbMgmt.kg.provSegTip') }}</div>
        </div>
      </section>

      <!-- 右栏：文档 → 实体 / 关系 + 失败切片 -->
      <section class="kg-card">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.provRightTitle') }}
          <span class="kg-card__hd-sub">
            {{ t('kbMgmt.kg.provDocContrib', { entities: contributions.length, relations: docRelationCount }) }}
          </span>
        </header>
        <div class="kg-card__bd">
          <a-select
            v-model:value="documentId"
            show-search
            :options="documentOptions"
            :placeholder="t('kbMgmt.kg.selectDocument')"
            size="small"
            style="width: 100%"
            @change="loadByDocument"
          />

          <div class="kg-sec-t">
            {{ t('kbMgmt.kg.provDocContrib', { entities: contributions.length, relations: docRelationCount }) }}
          </div>
          <div class="kg-prov-list">
            <div v-if="!contributions.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div v-for="item in contributions" :key="`c-${item.id}`" class="kg-mini kg-mini--static">
              <span
                class="kg-type-tag"
                :style="{
                  color: typeTone(item.type_code).fg,
                  background: typeTone(item.type_code).bg,
                  borderColor: typeTone(item.type_code).border,
                }"
              >
                {{ typeLabel(item.type_code) || t('kbMgmt.kg.unclassified') }}
              </span>
              <a class="kg-mini__name" @click="$emit('inspect-entity', item.id)">{{ item.name }}</a>
              <span class="kg-muted kg-mini__tail">
                {{ t('kbMgmt.kg.mentionsShort', { count: item.mention_count ?? 0 }) }}
              </span>
            </div>
          </div>

          <div class="kg-prov-ops">
            <a-popconfirm
              :title="t('kbMgmt.kg.confirmRevokeContrib')"
              :disabled="!documentId"
              @confirm="onRevoke"
            >
              <a-button size="small" danger :disabled="!documentId" :loading="revoking">
                {{ t('kbMgmt.kg.revokeDocContrib') }}
              </a-button>
            </a-popconfirm>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.kg.provFailedTitle', { count: failed.length }) }}</div>
          <div class="kg-kvlist">
            <div v-if="!failed.length" class="kg-muted">{{ t('kbMgmt.kg.noFailedSegments') }}</div>
            <div v-for="item in failed" :key="`f-${item.segment_id}`" class="kg-kvrow">
              <span class="kg-kvrow__k">{{ item.document_id }}</span>
              <span class="kg-kvrow__v">
                <span class="kg-badge kg-badge--err">
                  {{ (item.details as any)?.error || t('kbMgmt.kg.failedStructure') }}
                </span>
              </span>
            </div>
          </div>
          <div class="kg-prov-ops">
            <a-button
              size="small"
              :disabled="!failed.length"
              :loading="retrying"
              @click="onRetryFailed"
            >
              {{ t('kbMgmt.kg.retryFailedExtraction') }}
            </a-button>
          </div>
        </div>
      </section>
    </div>

    <!-- 分段详情：复用 kb 模块的 SegmentDetail（零改动） -->
    <SegmentDetail v-model:open="segmentOpen" :document-id="segmentDocId" />
  </div>
</template>

<script setup lang="ts">
/**
 * 溯源面板（两栏）：
 *   左：实体 / 关系 → 提及它的切片（看依据从哪来，点切片打开分段详情）
 *   右：文档 → 它贡献的实体/关系（看这个文档影响了图谱什么）+ 失败切片与重试
 *
 * 撤销贡献走 build 的 clear_document 动作：只清理该文档在图谱里的投影，
 * 文档与切片本身保留（不会被误删源文件）。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgEntity, KgFailedSegment, KgMentionSlice, KgRelation } from '@/api/kg'
import type { TypeTone } from '@/components/common/graph/graphTheme'
import { typeLabel, typeTone } from '@/components/common/graph/graphTheme'
import SegmentDetail from '@/views/kms/kb/SegmentDetail.vue'

const props = defineProps<{ knowledgeId: number }>()
defineEmits<{ (e: 'inspect-entity', entityId: number): void }>()

const { t } = useI18n()

interface PickerItem {
  kind: 'node' | 'edge'
  id: number
  name: string
  tag: string
  tone: TypeTone
  count: number
}

const entities = ref<KgEntity[]>([])
const relations = ref<KgRelation[]>([])
const keyword = ref('')

/** 左侧当前溯源对象（实体或关系，二选一） */
const picked = ref<{ kind: 'node' | 'edge'; id: number } | null>(null)
const mentions = ref<KgMentionSlice[]>([])

const documentId = ref<string | undefined>(undefined)
const contributions = ref<KgEntity[]>([])
const failed = ref<KgFailedSegment[]>([])
const revoking = ref(false)
const retrying = ref(false)

const segmentOpen = ref(false)
const segmentDocId = ref<string | null>(null)

const entityNameMap = computed(() => new Map(entities.value.map((e) => [e.id, e.name])))

/** 候选：实体按提及数降序 + 关系按提及数降序，关键词过滤 */
const pickerItems = computed<PickerItem[]>(() => {
  const kw = keyword.value.trim().toLowerCase()
  const hit = (text: string) => !kw || text.toLowerCase().includes(kw)

  const nodes: PickerItem[] = entities.value
    .filter((e) => hit(e.name))
    .sort((a, b) => (b.mention_count ?? 0) - (a.mention_count ?? 0))
    .slice(0, 12)
    .map((e) => ({
      kind: 'node' as const,
      id: e.id,
      name: e.name,
      tag: typeLabel(e.type_code) || t('kbMgmt.kg.unclassified'),
      tone: typeTone(e.type_code),
      count: e.mention_count ?? 0,
    }))

  const edges: PickerItem[] = relations.value
    .filter((r) => {
      const label = `${entityNameMap.value.get(r.from_entity_id) || ''} ${entityNameMap.value.get(r.to_entity_id) || ''} ${r.relation_code || ''}`
      return hit(label)
    })
    .sort((a, b) => (b.mention_count ?? 0) - (a.mention_count ?? 0))
    .slice(0, 8)
    .map((r) => ({
      kind: 'edge' as const,
      id: r.id,
      name: `${entityNameMap.value.get(r.from_entity_id) || `#${r.from_entity_id}`} → ${
        entityNameMap.value.get(r.to_entity_id) || `#${r.to_entity_id}`
      }`,
      tag: r.relation_code || t('kbMgmt.kg.freePredicate'),
      tone: typeTone('REL_' + (r.relation_code || '')),
      count: r.mention_count ?? 0,
    }))

  return [...nodes, ...edges]
})

const pickedName = computed(() => {
  if (!picked.value) return ''
  if (picked.value.kind === 'node') {
    return entityNameMap.value.get(picked.value.id) || ''
  }
  const row = relations.value.find((r) => r.id === picked.value?.id)
  if (!row) return ''
  const from = entityNameMap.value.get(row.from_entity_id) || `#${row.from_entity_id}`
  const to = entityNameMap.value.get(row.to_entity_id) || `#${row.to_entity_id}`
  return `${from} → ${to}`
})

const documentOptions = computed(() => {
  const ids = new Set<string>()
  entities.value.forEach((e) => (e.source_document_ids || []).forEach((d) => ids.add(d)))
  failed.value.forEach((f) => f.document_id && ids.add(f.document_id))
  return Array.from(ids).map((d) => ({ label: d, value: d }))
})

/** 该文档贡献的关系数：关系两端实体都来自该文档时计入 */
const docRelationCount = computed(() => {
  const ids = new Set(contributions.value.map((e) => e.id))
  if (!ids.size) return 0
  return relations.value.filter(
    (r) => ids.has(r.from_entity_id) && ids.has(r.to_entity_id),
  ).length
})

function isPicked(item: PickerItem) {
  return picked.value?.kind === item.kind && picked.value?.id === item.id
}

async function pick(item: PickerItem) {
  picked.value = { kind: item.kind, id: item.id }
  await loadMentions()
}

async function loadMentions() {
  mentions.value = []
  if (!picked.value) return
  try {
    const res =
      picked.value.kind === 'node'
        ? await api.getEntityMentions(props.knowledgeId, picked.value.id)
        : await api.getRelationMentions(props.knowledgeId, picked.value.id)
    mentions.value = res?.items || []
  } catch {
    mentions.value = []
  }
}

async function loadEntities() {
  try {
    const [entRes, relRes] = await Promise.all([
      api.listEntities(props.knowledgeId, { limit: 500 }),
      api.listRelations(props.knowledgeId, { limit: 500 }),
    ])
    entities.value = entRes?.items || []
    relations.value = relRes?.items || []
  } catch {
    entities.value = []
    relations.value = []
  }
}

async function loadByDocument() {
  contributions.value = []
  if (!documentId.value) return
  contributions.value = entities.value.filter((e) =>
    (e.source_document_ids || []).includes(documentId.value as string),
  )
}

async function loadFailed() {
  try {
    const res = await api.listFailedSegments(props.knowledgeId)
    failed.value = res?.items || []
  } catch {
    failed.value = []
  }
}

function openSegments(docId: string) {
  segmentDocId.value = docId
  segmentOpen.value = true
}

/** 撤销本文档贡献：清理该文档在图谱中的实体/关系/提及（文档本身保留） */
async function onRevoke() {
  if (!documentId.value) return
  revoking.value = true
  try {
    await api.submitGraphBuild(props.knowledgeId, 'clear_document', documentId.value)
    message.success(t('kbMgmt.kg.deleted'))
    picked.value = null
    mentions.value = []
    await Promise.all([loadEntities(), loadFailed(), loadByDocument()])
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    revoking.value = false
  }
}

/** 重试失败抽取：按文档重跑阶段 1（structure），已完成切片自动跳过 */
async function onRetryFailed() {
  const docs = Array.from(new Set(failed.value.map((f) => f.document_id))).filter(Boolean)
  if (!docs.length) return
  retrying.value = true
  try {
    const results = await Promise.allSettled(
      docs.map((doc) => api.submitGraphBuild(props.knowledgeId, 'build', doc)),
    )
    const failedCount = results.filter((r) => r.status === 'rejected').length
    if (failedCount) {
      message.warning(`${failedCount} / ${docs.length} ${t('kbMgmt.kg.actionFailed')}`)
    } else {
      message.success(t('kbMgmt.kg.rebuildSubmitted'))
    }
    await loadFailed()
  } finally {
    retrying.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadEntities(), loadFailed()])
})
</script>

<style scoped>
.kg-provenance__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}
@media (max-width: 1180px) {
  .kg-provenance__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
/* 候选列表：实体/关系小行 */
.kg-prov-picker {
  margin-top: 10px;
  max-height: 232px;
  overflow: auto;
}
.kg-prov-list {
  max-height: 240px;
  overflow: auto;
}
.kg-mini {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 5px 6px;
  border: 0;
  border-radius: var(--kg-r-xs);
  background: transparent;
  color: var(--kg-text);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.kg-mini:hover {
  background: var(--kg-subtle);
}
.kg-mini--on {
  background: var(--kg-tint);
}
.kg-mini--static {
  cursor: default;
}
.kg-mini--static:hover {
  background: transparent;
}
.kg-mini__name {
  overflow: hidden;
  color: var(--kg-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}
a.kg-mini__name:hover {
  color: var(--kg-primary);
}
.kg-mini__tail {
  margin-left: auto;
  flex: none;
  font-size: 11px;
}
.kg-prov-ops {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}
.kg-type-tag {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border: 1px solid transparent;
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}
</style>
