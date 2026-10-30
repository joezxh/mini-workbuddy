<template>
  <div class="kb-graph-pane">
    <div class="kb-graph-pane__header">
      <div class="kb-graph-pane__title">
        <PartitionOutlined class="kb-graph-pane__icon" />
        <span>{{ knowledgeName }}</span>
        <a-tag color="purple">{{ t('kbMgmt.kg.typeLabel') }}</a-tag>
        <a-tag :color="statusColor">{{ statusText }}</a-tag>
        <a-tag v-if="status && !status.neo4j_available" color="orange">
          {{ t('kbMgmt.kg.neo4jDown') }}
        </a-tag>
      </div>
      <a-space>
        <a-button
          type="primary"
          :loading="submitting"
          :disabled="!canBuild"
          @click="onBuild('build')"
        >
          {{ t('kbMgmt.kg.actionBuild') }}
        </a-button>
        <a-button :disabled="!canBuild" @click="onBuild('rebuild')">
          {{ t('kbMgmt.kg.actionRebuild') }}
        </a-button>
        <a-button :loading="refreshing" @click="refreshAll">
          {{ t('common.refresh') }}
        </a-button>
      </a-space>
    </div>

    <a-tabs v-model:activeKey="activeTab" class="kb-graph-pane__tabs">
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
      <a-tab-pane key="config" :tab="t('kbMgmt.kg.tabConfig')">
        <KgBuildConfig :knowledge-id="knowledgeId" />
      </a-tab-pane>

      <!-- 后续阶段交付：禁用占位并标注阶段，避免误以为功能缺失 -->
      <a-tab-pane key="documents" :tab="t('kbMgmt.kg.tabDoc')" disabled />
      <a-tab-pane key="graph" :tab="t('kbMgmt.kg.tabGraph')" disabled />
      <a-tab-pane key="provenance" :tab="t('kbMgmt.kg.tabProvenance')" disabled />
      <a-tab-pane key="search" :tab="t('kbMgmt.kg.tabSearchTest')" disabled />
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
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PartitionOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import KgOverview from './KgOverview.vue'
import KgEntityTable from './KgEntityTable.vue'
import KgTripleTable from './KgTripleTable.vue'
import KgBuildConfig from './KgBuildConfig.vue'
import * as api from '@/api/kg'
import type { KgBuildStatus, KgEntity } from '@/api/kg'

const props = defineProps<{ knowledgeId: number; knowledgeName?: string }>()

const { t } = useI18n()

const activeTab = ref('overview')
const refreshing = ref(false)
const submitting = ref(false)
const inspectorOpen = ref(false)
const inspected = ref<KgEntity | null>(null)
/** 递增以强制子组件重建（子组件 watch(immediate) 随之重载数据） */
const reloadKey = ref(0)
const status = ref<KgBuildStatus | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const statusText = computed(() => {
  switch (status.value?.state) {
    case 'running': return t('kbMgmt.kg.stateRunning')
    case 'ready': return t('kbMgmt.kg.stateReady')
    case 'pending': return t('kbMgmt.kg.statePending')
    case 'partial_failed': return t('kbMgmt.kg.statePartialFailed')
    default: return t('kbMgmt.kg.stateNotBuilt')
  }
})

const statusColor = computed(() => {
  switch (status.value?.state) {
    case 'running': return 'blue'
    case 'ready': return 'green'
    case 'partial_failed': return 'red'
    case 'pending': return 'orange'
    default: return 'default'
  }
})

/** Neo4j 不可用时禁止构建（否则图结构投影必失败，用户白等一次抽取） */
const canBuild = computed(() => status.value?.neo4j_available !== false)

async function loadStatus() {
  try {
    status.value = await api.getGraphBuildStatus(props.knowledgeId)
  } catch {
    status.value = null
  }
}

/** 轮询：仅在构建中轮询，终态即停（R17：定时器必须随组件卸载清理） */
function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    await loadStatus()
    if (status.value && status.value.state !== 'running') stopPolling()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function onBuild(action: 'build' | 'rebuild') {
  submitting.value = true
  try {
    await api.submitGraphBuild(props.knowledgeId, action)
    message.success(t('kbMgmt.kg.buildSubmitted'))
    await loadStatus()
    startPolling()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    submitting.value = false
  }
}

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
  loadStatus()
  setTimeout(() => {
    refreshing.value = false
  }, 400)
}

watch(
  () => props.knowledgeId,
  async () => {
    await loadStatus()
    if (status.value?.state === 'running') startPolling()
  },
  { immediate: true },
)

onUnmounted(stopPolling)
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
