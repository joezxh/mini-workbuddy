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

      <template v-if="failedRows.length">
        <a-divider orientation="left">{{ t('kbMgmt.kg.failedList') }}</a-divider>
        <a-list size="small" bordered :data-source="failedRows">
          <template #renderItem="{ item: row }">
            <a-list-item>
              <div class="kg-build-status__failed">
                <span class="kg-build-status__failed-meta">
                  #{{ row.item.chunk_index }} · {{ row.item.document_id }}
                  · {{ row.reason.stage === 'vector' ? t('kbMgmt.kg.failedVector') : t('kbMgmt.kg.failedStructure') }}
                </span>
                <a-tooltip v-if="row.reason.detail">
                  <template #title>
                    <div class="kg-build-status__tip">{{ row.reason.detail }}</div>
                  </template>
                  <span class="kg-build-status__failed-reason">{{ t(row.reason.textKey) }}</span>
                </a-tooltip>
                <span v-else class="kg-build-status__failed-reason">{{ t(row.reason.textKey) }}</span>
                <span class="kg-build-status__failed-fix">{{ t(row.reason.fixKey) }}</span>
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
import { resolveKgFailure } from '@/utils/kgFailureReason'

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

/**
 * 失败行：把切片预先归一成「码 → 文案」，一份数据只解一次。
 *
 * 主行说人话（分类文案），次行给处置建议，悬浮保留后端原始串——
 * 旧数据没有 error_code 时统一回落 unknown，界面不至于空白。
 */
const failedRows = computed(() =>
  failed.value.map((item) => ({ item, reason: resolveKgFailure(item) })),
)

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
.kg-build-status__failed-fix {
  color: #666;
  font-size: 12px;
}
.kg-build-status__tip {
  max-width: 420px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
