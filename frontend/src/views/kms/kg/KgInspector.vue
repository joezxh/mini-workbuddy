<template>
  <a-drawer
    :open="open"
    :title="t('kbMgmt.kg.inspectorTitle')"
    :width="440"
    @close="$emit('close')"
  >
    <a-spin :spinning="loading">
      <template v-if="entity">
        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item :label="t('kbMgmt.kg.entityName')">
            {{ entity.name }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.kg.entityKey')">
            {{ entity.entity_key }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.kg.entityType')">
            <a-tag v-if="entity.type_code" color="blue">{{ entity.type_code }}</a-tag>
            <span v-else class="kg-muted">{{ t('kbMgmt.kg.unclassified') }}</span>
          </a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.kg.aliases')">
            {{ (entity.aliases || []).join('、') || '-' }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.kg.status')">
            <a-tag :color="entity.status === 'active' ? 'green' : 'orange'">
              {{ entity.status }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.kg.mentionCount')">
            {{ entity.mention_count ?? 0 }}
          </a-descriptions-item>
        </a-descriptions>

        <template v-if="entity.properties && Object.keys(entity.properties).length">
          <a-divider orientation="left">{{ t('kbMgmt.kg.properties') }}</a-divider>
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item
              v-for="(v, k) in entity.properties"
              :key="k"
              :label="String(k)"
            >
              {{ v }}
            </a-descriptions-item>
          </a-descriptions>
        </template>

        <a-divider orientation="left">{{ t('kbMgmt.kg.adjacentRelations') }}</a-divider>
        <a-list size="small" bordered :data-source="adjacent">
          <template #renderItem="{ item }">
            <a-list-item>
              <span class="kg-inspector__rel">
                <a-button type="link" size="small" @click="onInspectEntity(item.from_entity_id)">
                  {{ item.from_entity_name || `#${item.from_entity_id}` }}
                </a-button>
                <a-tag v-if="item.relation_code" color="purple">{{ item.relation_code }}</a-tag>
                <a-button type="link" size="small" @click="onInspectEntity(item.to_entity_id)">
                  {{ item.to_entity_name || `#${item.to_entity_id}` }}
                </a-button>
              </span>
            </a-list-item>
          </template>
        </a-list>

        <a-space class="kg-inspector__actions">
          <a-button @click="$emit('locate', entity.id)">
            {{ t('kbMgmt.kg.locateInGraph') }}
          </a-button>
          <a-button @click="$emit('provenance', entity.id)">
            {{ t('kbMgmt.kg.viewProvenance') }}
          </a-button>
        </a-space>
      </template>

      <a-empty v-else-if="!loading" :description="t('kbMgmt.kg.noSelection')" />
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
/**
 * 图谱检视面板：展示实体详情 + 属性 + 邻接关系，并提供下钻入口。
 * 对标标准中心的 StdInspector（选中 -> 拉详情 -> 描述列表 + 分割线 + 列表）。
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/kg'
import type { KgEntity, KgRelation } from '@/api/kg'

const props = defineProps<{
  open: boolean
  knowledgeId: number
  entityId?: number | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'locate', entityId: number): void
  (e: 'provenance', entityId: number): void
  (e: 'inspect-entity', entityId: number): void
}>()

const { t } = useI18n()

const entity = ref<KgEntity | null>(null)
const adjacent = ref<KgRelation[]>([])
const loading = ref(false)

async function load() {
  if (!props.entityId) {
    entity.value = null
    adjacent.value = []
    return
  }
  loading.value = true
  try {
    entity.value = await api.getEntity(props.knowledgeId, props.entityId)
    const sub = await api.getNeighbors(props.knowledgeId, props.entityId, 1, 50)
    const ids = new Set<number>()
    sub?.edges?.forEach((e) => {
      ids.add(e.from)
      ids.add(e.to)
    })
    adjacent.value = (sub?.edges || []).map((e) => ({
      id: e.id,
      relation_code: e.relation_type,
      predicate: e.predicate ?? null,
      from_entity_id: e.from,
      to_entity_id: e.to,
      from_entity_name: sub.nodes?.find((n) => n.id === e.from)?.name ?? null,
      to_entity_name: sub.nodes?.find((n) => n.id === e.to)?.name ?? null,
      weight: e.weight ?? null,
      status: (e.status as any) || 'suggested',
      properties: {},
      evidence: null,
      created_at: null,
      updated_at: null,
    }))
  } catch {
    entity.value = null
    adjacent.value = []
  } finally {
    loading.value = false
  }
}

function onInspectEntity(id: number) {
  emit('inspect-entity', id)
}

watch(() => [props.open, props.entityId], load, { immediate: true })
</script>

<style scoped>
.kg-muted {
  color: #999;
}
.kg-inspector__rel {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.kg-inspector__actions {
  margin-top: 12px;
}
</style>
