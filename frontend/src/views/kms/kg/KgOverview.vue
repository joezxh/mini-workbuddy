<template>
  <div class="kg-overview">
    <a-spin :spinning="loading">
      <a-row :gutter="12">
        <a-col :span="6">
          <a-card size="small">
            <a-statistic :title="t('kbMgmt.kg.statEntities')" :value="stats.entities" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic :title="t('kbMgmt.kg.statRelations')" :value="stats.relations" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic :title="t('kbMgmt.kg.statEntityTypes')" :value="typeRows.length" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic :title="t('kbMgmt.kg.statRelationTypes')" :value="relationRows.length" />
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="12" class="kg-overview__row">
        <a-col :span="12">
          <a-card size="small" :title="t('kbMgmt.kg.entityTypeDistribution')">
            <div v-if="!typeRows.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div v-for="r in typeRows" :key="r.key" class="kg-overview__bar">
              <span class="kg-overview__bar-label">{{ r.key || t('kbMgmt.kg.unclassified') }}</span>
              <a-progress :percent="percent(r.value, maxType)" size="small" />
              <span class="kg-overview__bar-value">{{ r.value }}</span>
            </div>
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card size="small" :title="t('kbMgmt.kg.relationTypeDistribution')">
            <div v-if="!relationRows.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
            <div v-for="r in relationRows" :key="r.key" class="kg-overview__bar">
              <span class="kg-overview__bar-label">{{ r.key || t('kbMgmt.kg.freePredicate') }}</span>
              <a-progress :percent="percent(r.value, maxRelation)" size="small" />
              <span class="kg-overview__bar-value">{{ r.value }}</span>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <a-card size="small" :title="t('kbMgmt.kg.buildStatus')" class="kg-overview__row">
        <a-alert
          type="info"
          show-icon
          :message="t('kbMgmt.kg.buildPendingTip')"
          :description="t('kbMgmt.kg.buildPendingDesc')"
        />
      </a-card>

      <div class="kg-overview__row">
        <KgBuildStatusCard :knowledge-id="knowledgeId" />
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/kg'
import type { KgStats } from '@/api/kg'
import KgBuildStatusCard from './KgBuildStatusCard.vue'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const loading = ref(false)
const stats = ref<KgStats>({ entities: 0, relations: 0, by_type: {}, by_relation: {} })

const typeRows = computed(() =>
  Object.entries(stats.value.by_type || {}).map(([key, value]) => ({ key, value })),
)
const relationRows = computed(() =>
  Object.entries(stats.value.by_relation || {}).map(([key, value]) => ({ key, value })),
)
const maxType = computed(() => Math.max(1, ...typeRows.value.map((r) => r.value)))
const maxRelation = computed(() => Math.max(1, ...relationRows.value.map((r) => r.value)))

function percent(value: number, max: number) {
  return Math.round((value / max) * 100)
}

async function load() {
  loading.value = true
  try {
    stats.value = (await api.getGraphStats(props.knowledgeId)) || stats.value
  } catch {
    // 概览统计失败不阻塞主流程（实体/关系页仍可用）
    stats.value = { entities: 0, relations: 0, by_type: {}, by_relation: {} }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kg-overview__row {
  margin-top: 12px;
}
.kg-overview__bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.kg-overview__bar-label {
  width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kg-overview__bar-value {
  width: 40px;
  text-align: right;
  color: #666;
}
.kg-muted {
  color: #999;
}
</style>
