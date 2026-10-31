<template>
  <section class="kg-insp">
    <header class="kg-insp__hd">
      <span>{{ isEdge ? t('kbMgmt.graph.relationDetail') : t('kbMgmt.graph.objectDetail') }}</span>
      <span v-if="selected" class="kg-insp__hd-ops">
        <template v-if="isEdge">
          <a-button size="small" @click="emit('edit-relation', selected.id)">
            {{ t('kbMgmt.common.edit') }}
          </a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="emit('delete-relation', selected.id)">
            <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
          </a-popconfirm>
        </template>
        <a-button v-else size="small" @click="emit('edit-object', selected.id)">
          {{ t('kbMgmt.common.edit') }}
        </a-button>
      </span>
    </header>

    <div class="kg-insp__bd">
      <a-spin :spinning="loading">
        <div v-if="!selected" class="kg-insp__empty">
          <div class="kg-insp__empty-icon">🔍</div>
          <div class="kg-insp__empty-t">{{ t('kbMgmt.graph.selectHint') }}</div>
        </div>

        <!-- 形态一：对象标准（定义 + 引用属性 + 邻接关系 + 绑定表） -->
        <template v-else-if="!isEdge">
          <dl class="kg-kv">
            <dt>{{ t('kbMgmt.common.name') }}</dt>
            <dd class="is-strong">{{ object?.name || '—' }}</dd>
            <dt>{{ t('kbMgmt.common.type') }}</dt>
            <dd>
              <span v-if="object?.code" class="kg-type-tag" :style="typeTagStyle(object.code)">
                {{ typeLabel(object.code) || object.code }}
              </span>
              <code v-if="object?.code" class="kg-code">{{ object.code }}</code>
              <span v-else class="kg-muted">—</span>
            </dd>
            <dt>{{ t('kbMgmt.meta.domain') }}</dt>
            <dd>{{ object?.domain || '—' }}</dd>
            <dt>{{ t('kbMgmt.std.aliases') }}</dt>
            <dd>
              <template v-if="object?.aliases?.length">
                <span v-for="alias in object.aliases" :key="alias" class="kg-insp__alias">{{ alias }}</span>
              </template>
              <span v-else class="kg-muted">—</span>
            </dd>
            <dt>{{ t('kbMgmt.common.status') }}</dt>
            <dd>
              <span class="kg-badge" :class="statusBadgeClass(object?.status)">{{ statusText(object?.status) }}</span>
            </dd>
            <dt>{{ t('kbMgmt.catalog.description') }}</dt>
            <dd>{{ object?.description || '—' }}</dd>
          </dl>

          <div class="kg-sec-t">{{ t('kbMgmt.catalog.attributes') }}</div>
          <div class="kg-kvlist">
            <div v-if="!attributes.length" class="kg-kvrow">
              <span class="k kg-muted">{{ t('kbMgmt.graph.noAttributes') }}</span>
            </div>
            <div v-for="row in attributes" :key="row.id || row.code" class="kg-kvrow">
              <span class="k">
                {{ row.name }} <code class="kg-code">{{ row.code }}</code>
              </span>
              <span class="v">
                <span v-if="row.required" class="kg-badge kg-badge--ok">{{ t('kbMgmt.graph.required') }}</span>
                <span v-if="row.security_level" class="kg-badge kg-badge--err">{{ row.security_level }}</span>
                <span v-if="!row.required && !row.security_level" class="kg-muted">—</span>
              </span>
            </div>
          </div>

          <div class="kg-sec-t">
            {{ t('kbMgmt.graph.adjacentRelations') }}（{{ adjacent.length }}）
          </div>
          <div v-if="!adjacent.length" class="kg-muted">{{ t('kbMgmt.graph.noAdjacent') }}</div>
          <div v-else>
            <div
              v-for="row in adjacent"
              :key="`adj-${row.id}`"
              class="kg-mini"
              @click="emit('inspect-relation', row.id)"
            >
              <span class="kg-type-tag kg-type-tag--rel">{{ row.name }}</span>
              <span class="kg-insp__dir">{{ row.dir }}</span>
              <span class="kg-insp__strong">{{ row.otherName }}</span>
              <span class="kg-mini__tail">{{ row.relation_type || '—' }}</span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.graph.boundTables') }}</div>
          <div v-if="!bindings.length" class="kg-muted">{{ t('kbMgmt.graph.noBindings') }}</div>
          <div v-else>
            <div v-for="(row, i) in bindings" :key="`bind-${i}`" class="kg-mini">
              <span class="kg-insp__strong">{{ bindingTitle(row) }}</span>
              <span class="kg-badge" :class="row.status === 'accepted' ? 'kg-badge--ok' : 'kg-badge--warn'">
                {{ row.status || '—' }}
              </span>
              <span class="kg-mini__tail" @click.stop="drill(row)">{{ t('kbMgmt.graph.drill') }}</span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.common.actions') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('locate', selected.id)">
              {{ t('kbMgmt.graph.locateInGraph') }}
            </a-button>
          </div>
        </template>

        <!-- 形态二：关系标准（两端 + 基数 + 校验三态） -->
        <template v-else>
          <dl class="kg-kv">
            <dt>{{ t('kbMgmt.graph.fromObject') }}</dt>
            <dd class="is-strong">
              <a class="kg-insp__link" @click="emit('inspect-entity', relation?.from_object_id)">
                {{ objectName(relation?.from_object_id) }}
              </a>
            </dd>
            <dt>{{ t('kbMgmt.graph.toObject') }}</dt>
            <dd class="is-strong">
              <a class="kg-insp__link" @click="emit('inspect-entity', relation?.to_object_id)">
                {{ objectName(relation?.to_object_id) }}
              </a>
            </dd>
            <dt>{{ t('kbMgmt.common.name') }}</dt>
            <dd>
              <span class="kg-type-tag kg-type-tag--rel">{{ relation?.name || '—' }}</span>
              <code v-if="relation?.code" class="kg-code">{{ relation.code }}</code>
            </dd>
            <dt>{{ t('kbMgmt.graph.relationType') }}</dt>
            <dd>{{ relation?.relation_type || '—' }}</dd>
            <dt>{{ t('kbMgmt.common.status') }}</dt>
            <dd>
              <span class="kg-badge" :class="statusBadgeClass(relation?.status)">
                {{ statusText(relation?.status) }}
              </span>
            </dd>
            <dt>{{ t('kbMgmt.catalog.description') }}</dt>
            <dd>{{ relation?.description || '—' }}</dd>
          </dl>

          <div class="kg-sec-t">{{ t('kbMgmt.graph.checks') }}</div>
          <div v-if="!checks.length" class="kg-muted">{{ t('kbMgmt.graph.noChecks') }}</div>
          <div v-else class="kg-kvlist">
            <div v-for="(row, i) in checks" :key="`chk-${i}`" class="kg-kvrow">
              <span class="k">{{ row.source_id }} / {{ row.database || '—' }}</span>
              <span class="v">
                <span class="kg-badge" :class="verdictBadgeClass(row.verdict)">{{ verdictText(row.verdict) }}</span>
                <span v-if="row.confidence != null"> {{ Math.round(row.confidence * 100) }}%</span>
              </span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.common.actions') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('locate', relation?.from_object_id)">
              {{ t('kbMgmt.graph.locateInGraph') }}
            </a-button>
          </div>
        </template>
      </a-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * 标准中心检视面板：对齐原型 .insp 形态（原 a-descriptions/a-list 版式替换）。
 *
 * 与 KgInspector 同构（同一套 kg-* 皮肤），但字段只出标准中心真实存在的：
 * 没有提及数、向量状态、归一化名、权重与抽取依据 —— 不编造原型有而标准无的数据（spec §5）。
 * 邻接关系取全量 relations 而非当前可见边集：详情反映标准本身，不受视图筛选影响。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/dataops'
import { typeLabel, typeTone } from '@/components/common/graph/graphTheme'
import {
  bindingTitle,
  statusBadgeClass,
  statusTextKey,
  verdictBadgeClass,
  verdictTextKey,
} from './inspectorFormat'

const props = defineProps<{
  selected: { kind: 'node' | 'edge'; id: number } | null
  objects: any[]
  relations: any[]
}>()

const emit = defineEmits<{
  (e: 'edit-object', id: number): void
  (e: 'edit-relation', id: number): void
  (e: 'delete-relation', id: number): void
  (e: 'drill-down', payload: { source_id: number; db_name?: string; database?: string; table: string }): void
  (e: 'inspect-entity', id: number): void
  (e: 'inspect-relation', id: number): void
  (e: 'locate', id: number): void
}>()

const { t } = useI18n()
const loading = ref(false)
const object = ref<any>(null)
const relation = ref<any>(null)
const attributes = ref<any[]>([])
const bindings = ref<any[]>([])
const checks = ref<any[]>([])

const isEdge = computed(() => props.selected?.kind === 'edge')

function typeTagStyle(code: string) {
  const tone = typeTone(code)
  return { color: tone.fg, background: tone.bg, borderColor: tone.border }
}

function objectName(id?: number | null) {
  if (!id) return '—'
  return props.objects.find((o) => o.id === id)?.name || `#${id}`
}

/** 邻接关系：方向箭头 + 对端名 + 基数，按 id 稳定排序 */
const adjacent = computed(() => {
  const id = props.selected?.kind === 'node' ? props.selected.id : null
  if (id === null) return []
  return props.relations
    .filter((r: any) => r.from_object_id === id || r.to_object_id === id)
    .map((r: any) => ({
      id: r.id,
      name: r.name || r.code,
      relation_type: r.relation_type,
      dir: r.from_object_id === id ? '→' : '←',
      otherName: objectName(r.from_object_id === id ? r.to_object_id : r.from_object_id),
    }))
    .sort((a, b) => a.id - b.id)
})

/**
 * 组件层只把 key 变成文案；映射本身在 inspectorFormat（可在组件外单测）。
 * 模板里直接用导入的 statusBadgeClass / verdictBadgeClass / bindingTitle。
 */
function statusText(status?: string | null) {
  const key = statusTextKey(status)
  return key ? t(key) : String(status || '—')
}

function verdictText(verdict?: string | null) {
  const key = verdictTextKey(verdict)
  return key ? t(key) : String(verdict || '—')
}

function drill(row: any) {
  emit('drill-down', {
    source_id: row.source_id,
    db_name: row.db_name || undefined,
    database: row.database || undefined,
    table: row.table_name,
  })
}

async function load(payload: { kind: 'node' | 'edge'; id: number } | null) {
  if (!payload) {
    object.value = null
    relation.value = null
    attributes.value = []
    bindings.value = []
    checks.value = []
    return
  }
  loading.value = true
  attributes.value = []
  bindings.value = []
  checks.value = []
  try {
    if (payload.kind === 'node') {
      relation.value = null
      object.value = props.objects.find((o) => o.id === payload.id) || null
      const detail: any = await api.getObject(payload.id)
      const data = detail.data || detail
      object.value = { ...(object.value || {}), ...data }
      attributes.value = data.attributes || []
      const b: any = await api.listObjectBindings(payload.id)
      bindings.value = b.data || b || []
    } else {
      object.value = null
      relation.value = props.relations.find((r) => r.id === payload.id) || null
      const c: any = await api.listRelationChecks(payload.id)
      checks.value = c.data || c || []
    }
  } finally {
    loading.value = false
  }
}

watch(() => [props.selected?.kind, props.selected?.id], () => load(props.selected), { immediate: true })
</script>
