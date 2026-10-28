<template>
  <div class="std-inspector">
    <a-empty v-if="!selected" :description="t('kbMgmt.graph.selectHint')" />

    <!-- 对象：定义 + 引用属性 + 绑定表（可下钻） -->
    <template v-else-if="selected.kind === 'node'">
      <div class="std-inspector__head">
        <h4>{{ object?.name }}</h4>
        <a-space>
          <a-button size="small" @click="emit('edit-object', selected.id)">{{ t('kbMgmt.common.edit') }}</a-button>
        </a-space>
      </div>
      <a-descriptions :column="1" size="small" bordered>
        <a-descriptions-item label="code">{{ object?.code || '—' }}</a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.meta.domain')">{{ object?.domain || '—' }}</a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.std.aliases')">
          {{ (object?.aliases || []).join(', ') || '—' }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.catalog.description')">
          {{ object?.description || '—' }}
        </a-descriptions-item>
      </a-descriptions>

      <a-divider>{{ t('kbMgmt.catalog.attributes') }}</a-divider>
      <a-list size="small" :data-source="attributes" :loading="loading">
        <template #renderItem="{ item }">
          <a-list-item>
            <span>{{ item.name }} <span class="std-inspector__muted">{{ item.code }}</span></span>
            <a-space>
              <a-tag v-if="item.security_level" color="red">{{ item.security_level }}</a-tag>
              <a-tag v-if="item.required" color="blue">{{ t('kbMgmt.graph.required') }}</a-tag>
            </a-space>
          </a-list-item>
        </template>
      </a-list>

      <a-divider>{{ t('kbMgmt.graph.boundTables') }}</a-divider>
      <a-list size="small" :data-source="bindings" :loading="loading">
        <template #renderItem="{ item }">
          <a-list-item>
            <span>
              {{ item.db_name ? item.db_name + '.' : '' }}{{ item.database ? item.database + '.' : '' }}{{ item.table_name }}
              <a-tag :color="item.status === 'accepted' ? 'green' : 'default'">{{ item.status }}</a-tag>
            </span>
            <a-button size="small" type="link" @click="drill(item)">{{ t('kbMgmt.graph.drill') }}</a-button>
          </a-list-item>
        </template>
      </a-list>
    </template>

    <!-- 关系：定义 + 各数据源校验结论 -->
    <template v-else>
      <div class="std-inspector__head">
        <h4>{{ relation?.name }}</h4>
        <a-space>
          <a-button size="small" @click="emit('edit-relation', selected.id)">{{ t('kbMgmt.common.edit') }}</a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="emit('delete-relation', selected.id)">
            <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
          </a-popconfirm>
        </a-space>
      </div>
      <a-descriptions :column="1" size="small" bordered>
        <a-descriptions-item label="code">{{ relation?.code || '—' }}</a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.graph.relationType')">{{ relation?.relation_type || '—' }}</a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.graph.fromTo')">
          {{ objectName(relation?.from_object_id) }} → {{ objectName(relation?.to_object_id) }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.catalog.description')">
          {{ relation?.description || '—' }}
        </a-descriptions-item>
      </a-descriptions>

      <a-divider>{{ t('kbMgmt.graph.checks') }}</a-divider>
      <a-empty v-if="!loading && !checks.length" :description="t('kbMgmt.graph.noChecks')" />
      <a-list size="small" :data-source="checks" :loading="loading">
        <template #renderItem="{ item }">
          <a-list-item>
            <span>{{ item.source_id }} / {{ item.database || '—' }}</span>
            <a-space>
              <a-tag :color="verdictColor(item.verdict)">{{ item.verdict }}</a-tag>
              <span v-if="item.confidence != null" class="std-inspector__muted">
                {{ Math.round(item.confidence * 100) }}%
              </span>
            </a-space>
          </a-list-item>
        </template>
      </a-list>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * 检视面板：点图上的对象 → 定义 + 引用属性 + 已绑定物理表（可下钻）；
 * 点边 → 关系定义 + 各 source 的三态校验结论（hit/missing/conflict）。
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/dataops'

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
}>()

const { t } = useI18n()
const loading = ref(false)
const object = ref<any>(null)
const relation = ref<any>(null)
const attributes = ref<any[]>([])
const bindings = ref<any[]>([])
const checks = ref<any[]>([])

function objectName(id?: number | null) {
  if (!id) return '—'
  return props.objects.find((o) => o.id === id)?.name || `#${id}`
}

function verdictColor(verdict: string) {
  if (verdict === 'hit') return 'green'
  if (verdict === 'conflict') return 'orange'
  return 'red'
}

function drill(row: any) {
  emit('drill-down', {
    source_id: row.source_id,
    db_name: row.db_name || undefined,
    database: row.database || undefined,
    table: row.table_name,
  })
}

async function load(payload: { kind: 'node' | 'edge'; id: number }) {
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

watch(
  () => props.selected,
  (payload) => {
    if (!payload) {
      object.value = null
      relation.value = null
      attributes.value = []
      bindings.value = []
      checks.value = []
      return
    }
    load(payload)
  },
  { immediate: true },
)
</script>

<style scoped>
.std-inspector {
  height: 100%;
  overflow: auto;
  padding-right: 4px;
}
.std-inspector__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.std-inspector__head h4 {
  margin: 0;
}
.std-inspector__muted {
  color: var(--fg-muted);
  font-size: 12px;
}
</style>
