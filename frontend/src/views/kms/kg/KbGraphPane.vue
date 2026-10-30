<template>
  <div class="kb-graph-pane">
    <div class="kb-graph-pane__header">
      <div class="kb-graph-pane__title">
        <PartitionOutlined class="kb-graph-pane__icon" />
        <span>{{ knowledgeName }}</span>
        <a-tag color="purple">{{ t('kbMgmt.kg.typeLabel') }}</a-tag>
      </div>
      <a-space>
        <a-button :loading="refreshing" @click="refreshAll">
          {{ t('common.refresh') }}
        </a-button>
      </a-space>
    </div>

    <a-tabs v-model:activeKey="activeTab" class="kb-graph-pane__tabs">
      <!-- P1 已交付 -->
      <a-tab-pane key="overview" :tab="t('kbMgmt.kg.tabOverview')">
        <KgOverview :key="`ov-${reloadKey}`" :knowledge-id="knowledgeId" />
      </a-tab-pane>
      <a-tab-pane key="entities" :tab="t('kbMgmt.kg.tabEntity')">
        <KgEntityTable
          :key="`ent-${reloadKey}`"
          :knowledge-id="knowledgeId"
          @inspect-entity="onInspectEntity"
        />
      </a-tab-pane>
      <a-tab-pane key="relations" :tab="t('kbMgmt.kg.tabRelation')">
        <KgTripleTable
          :key="`rel-${reloadKey}`"
          :knowledge-id="knowledgeId"
          @inspect-entity="onInspectEntity"
        />
      </a-tab-pane>

      <!-- 后续阶段交付：禁用占位并标注阶段，避免误以为功能缺失 -->
      <a-tab-pane key="documents" :tab="t('kbMgmt.kg.tabDoc')" disabled />
      <a-tab-pane key="graph" :tab="t('kbMgmt.kg.tabGraph')" disabled />
      <a-tab-pane key="provenance" :tab="t('kbMgmt.kg.tabProvenance')" disabled />
      <a-tab-pane key="search" :tab="t('kbMgmt.kg.tabSearchTest')" disabled />
      <a-tab-pane key="config" :tab="t('kbMgmt.kg.tabConfig')" disabled />
    </a-tabs>

    <a-drawer v-model:open="inspectorOpen" :title="t('kbMgmt.kg.inspectorTitle')" :width="420">
      <a-descriptions :column="1" size="small" bordered>
        <a-descriptions-item :label="t('kbMgmt.kg.entityName')">
          {{ inspected?.name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.entityKey')">
          {{ inspected?.entity_key || '-' }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.entityType')">
          {{ inspected?.type_code || t('kbMgmt.kg.unclassified') }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.aliases')">
          {{ (inspected?.aliases || []).join('、') || '-' }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.status')">
          <a-tag :color="inspected?.status === 'active' ? 'green' : 'orange'">
            {{ inspected?.status }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.mentionCount')">
          {{ inspected?.mention_count ?? 0 }}
        </a-descriptions-item>
      </a-descriptions>

      <a-divider orientation="left">{{ t('kbMgmt.kg.adjacentRelations') }}</a-divider>
      <a-list size="small" bordered :data-source="inspected?.adjacent_relations || []">
        <template #renderItem="{ item }">
          <a-list-item>
            <span>
              {{ item.from_entity_name || `#${item.from_entity_id}` }}
              →
              {{ item.to_entity_name || `#${item.to_entity_id}` }}
              <a-tag v-if="item.relation_code" color="purple">{{ item.relation_code }}</a-tag>
            </span>
          </a-list-item>
        </template>
      </a-list>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PartitionOutlined } from '@ant-design/icons-vue'
import KgOverview from './KgOverview.vue'
import KgEntityTable from './KgEntityTable.vue'
import KgTripleTable from './KgTripleTable.vue'
import * as api from '@/api/kg'
import type { KgEntity } from '@/api/kg'

const props = defineProps<{ knowledgeId: number; knowledgeName?: string }>()

const { t } = useI18n()

const activeTab = ref('overview')
const refreshing = ref(false)
const inspectorOpen = ref(false)
const inspected = ref<KgEntity | null>(null)
/** 递增以强制子组件重建（子组件 watch(immediate) 随之重载数据） */
const reloadKey = ref(0)

async function onInspectEntity(entityId: number) {
  try {
    inspected.value = await api.getEntity(props.knowledgeId, entityId)
    inspectorOpen.value = true
  } catch {
    inspectorOpen.value = false
  }
}

function refreshAll() {
  refreshing.value = true
  reloadKey.value += 1
  setTimeout(() => {
    refreshing.value = false
  }, 400)
}
</script>

<style scoped>
.kb-graph-pane__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.kb-graph-pane__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
}
.kb-graph-pane__icon {
  color: #722ed1;
}
.kb-graph-pane__tabs {
  background: #fff;
}
</style>
