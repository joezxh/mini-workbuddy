<template>
  <a-card size="small" :title="t('kbMgmt.kg.buildStatus')" class="kg-build-status">
    <a-spin :spinning="loading">
      <a-descriptions :column="4" size="small" bordered>
        <a-descriptions-item :label="t('kbMgmt.kg.buildStatus')">
          <a-tag :color="statusColor">{{ statusText }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.statSegments')">
          {{ status?.segments ?? 0 }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.stageStructure')">
          {{ status?.structure_done ?? 0 }} / {{ status?.segments ?? 0 }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.kg.stageVector')">
          {{ status?.vector_done ?? 0 }} / {{ status?.segments ?? 0 }}
        </a-descriptions-item>
      </a-descriptions>

      <a-alert
        v-if="status && !status.neo4j_available"
        type="warning"
        show-icon
        class="kg-build-status__block"
        :message="t('kbMgmt.kg.neo4jDown')"
        :description="t('kbMgmt.kg.neo4jDownDesc')"
      />

      <a-alert
        v-else-if="status && status.state === 'not_built'"
        type="info"
        show-icon
        class="kg-build-status__block"
        :message="t('kbMgmt.kg.buildPendingTip')"
        :description="t('kbMgmt.kg.buildPendingDesc')"
      />

      <template v-if="failed.length">
        <a-divider orientation="left">{{ t('kbMgmt.kg.failedList') }}</a-divider>
        <a-list size="small" bordered :data-source="failed">
          <template #renderItem="{ item }">
            <a-list-item>
              <div class="kg-build-status__failed">
                <span class="kg-build-status__failed-meta">
                  #{{ item.chunk_index }} · {{ item.document_id }}
                </span>
                <span class="kg-build-status__failed-reason">{{ failedReason(item) }}</span>
              </div>
            </a-list-item>
          </template>
        </a-list>
      </template>
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/kg'
import type { KgBuildStatus, KgFailedSegment } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const loading = ref(false)
const status = ref<KgBuildStatus | null>(null)
const failed = ref<KgFailedSegment[]>([])

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

/** 失败原因：优先取 details.error，其次退化为阶段说明 */
function failedReason(item: KgFailedSegment) {
  const err = (item.details as any)?.error
  if (err) return String(err)
  if (item.structure_indexed === false) return t('kbMgmt.kg.failedStructure')
  return t('kbMgmt.kg.failedVector')
}

async function load() {
  loading.value = true
  try {
    status.value = await api.getGraphBuildStatus(props.knowledgeId)
    const res = await api.listFailedSegments(props.knowledgeId)
    failed.value = res?.items || []
  } catch {
    status.value = null
    failed.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kg-build-status__block {
  margin-top: 12px;
}
.kg-build-status__failed {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kg-build-status__failed-meta {
  color: #999;
  font-size: 12px;
}
.kg-build-status__failed-reason {
  color: #cf1322;
  font-size: 12px;
}
</style>
