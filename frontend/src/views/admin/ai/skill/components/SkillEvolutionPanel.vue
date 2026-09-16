<template>
  <a-spin :spinning="loading">
    <!-- 指标概览 -->
    <div class="evo-metrics">
      <a-row :gutter="12">
        <a-col :span="6">
          <a-statistic :title="t('skillHub.metricSuccess')" :value="(evoMetrics.success_rate * 100).toFixed(1)" suffix="%" />
        </a-col>
        <a-col :span="6">
          <a-statistic :title="t('skillHub.metricLatency')" :value="evoMetrics.avg_latency.toFixed(2)" suffix="s" />
        </a-col>
        <a-col :span="6">
          <a-statistic :title="t('skillHub.metricExec')" :value="evoMetrics.execution_count" />
        </a-col>
        <a-col :span="6">
          <a-statistic :title="t('skillHub.metricRating')" :value="evoMetrics.user_rating.toFixed(2)" />
        </a-col>
      </a-row>
    </div>

    <!-- 进化态 -->
    <a-alert
      v-if="evoScore < evoConfig.threshold"
      type="warning"
      show-icon
      :message="t('skillHub.evoLow', { score: evoScore.toFixed(3), threshold: evoConfig.threshold })"
      class="evo-alert"
    />
    <a-alert
      v-else
      type="success"
      show-icon
      :message="t('skillHub.evoGood', { score: evoScore.toFixed(3), threshold: evoConfig.threshold })"
      class="evo-alert"
    />

    <!-- 操作按钮 -->
    <div class="evo-actions">
      <a-button type="primary" :loading="evoTriggering" @click="handleTriggerEvolution">
        <ThunderboltOutlined /> {{ t('skillHub.trainEvo') }}
      </a-button>
      <a-button @click="loadData">
        <ReloadOutlined /> {{ t('skillHub.evoRefresh') }}
      </a-button>
    </div>

    <!-- 配置表单 -->
    <a-divider>{{ t('skillHub.evoParams') }}</a-divider>
    <a-form layout="inline" class="evo-config-form">
      <a-form-item :label="t('skillHub.evoThreshold')">
        <a-input-number
          v-model:value="evoConfig.threshold"
          :min="0.1" :max="1.0" :step="0.05"
          @change="saveEvoConfig"
        />
      </a-form-item>
      <a-form-item :label="t('skillHub.evoWeightSuccess')">
        <a-input-number
          v-model:value="evoConfig.weight_success"
          :min="0" :max="1" :step="0.1"
          @change="saveEvoConfig"
        />
      </a-form-item>
      <a-form-item :label="t('skillHub.evoWeightLatency')">
        <a-input-number
          v-model:value="evoConfig.weight_latency"
          :min="0" :max="1" :step="0.1"
          @change="saveEvoConfig"
        />
      </a-form-item>
      <a-form-item :label="t('skillHub.evoWeightRating')">
        <a-input-number
          v-model:value="evoConfig.weight_user_rating"
          :min="0" :max="1" :step="0.1"
          @change="saveEvoConfig"
        />
      </a-form-item>
      <a-form-item :label="t('skillHub.evoAuto')">
        <a-switch v-model:checked="evoConfig.is_auto_enabled" @change="saveEvoConfig" />
      </a-form-item>
      <a-form-item :label="t('skillHub.evoModel')">
        <a-select
          v-model:value="evoConfig.model_code"
          :placeholder="t('skillHub.evoModelDefault')"
          style="width: 220px"
          :loading="chatModelsLoading"
          allow-clear
          @change="saveEvoConfig"
        >
          <a-select-option v-for="m in chatModels" :key="m.code" :value="m.code">
            {{ m.name || m.model || m.code }}
            <span v-if="m.platform" class="model-platform">（{{ m.platform }}）</span>
          </a-select-option>
        </a-select>
      </a-form-item>
    </a-form>

    <!-- 版本历史 -->
    <a-divider>{{ t('skillHub.evoVersionHistory') }}</a-divider>
    <a-table
      :columns="versionColumns"
      :data-source="evoVersions"
      :pagination="false"
      row-key="version_number"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'is_stable'">
          <a-tag :color="record.is_stable ? 'green' : 'default'">
            {{ record.is_stable ? t('skillHub.stable') : t('skillHub.history') }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-popconfirm
            v-if="!record.is_stable"
            :title="t('skillHub.rollbackConfirm', { version: record.version_number })"
            @confirm="handleRollback(record.version_number)"
          >
            <a-button type="link" size="small">{{ t('skillHub.rollback') }}</a-button>
          </a-popconfirm>
          <span v-else class="text-disabled">{{ t('skillHub.current') }}</span>
        </template>
      </template>
    </a-table>
    <a-empty v-if="evoVersions.length === 0" :description="t('skillHub.noVersions')" />

    <!-- 进化日志 -->
    <a-divider>{{ t('skillHub.evoLogs') }}</a-divider>
    <a-table
      :columns="logColumns"
      :data-source="evoLogs"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'result'">
          <a-tag :color="record.result === 'success' ? 'green' : record.result === 'failed' ? 'red' : 'orange'">
            {{ record.result }}
          </a-tag>
        </template>
      </template>
    </a-table>
    <a-empty v-if="evoLogs.length === 0" :description="t('skillHub.noEvoLogs')" />
  </a-spin>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import {
  getSkillMetrics, getEvolutionConfig, updateEvolutionConfig,
  triggerEvolution, getSkillVersions, rollbackVersion, getEvolutionLogs,
  getChatModels,
  type SkillMetrics, type EvolutionConfig, type SkillVersion, type EvolutionLog,
  type ChatModelOption,
} from '@/api/skillEvolution'

const props = defineProps<{
  packageId: string
}>()

const { t } = useI18n()

const loading = ref(false)
const evoTriggering = ref(false)
const evoMetrics = ref<SkillMetrics>({ skill_id: '', execution_count: 0, success_rate: 0, avg_latency: 0, user_rating: 0 })
const evoConfig = ref<EvolutionConfig>({
  skill_id: '', threshold: 0.7, weight_success: 0.4,
  weight_latency: 0.2, weight_user_rating: 0.3, resource_score: 0.8, is_auto_enabled: false,
  model_code: null,
})
const chatModels = ref<ChatModelOption[]>([])
const chatModelsLoading = ref(false)
const evoVersions = ref<SkillVersion[]>([])
const evoLogs = ref<EvolutionLog[]>([])

const evoScore = computed(() => {
  const m = evoMetrics.value
  const c = evoConfig.value
  const latencyScore = Math.max(0, 1 - (m.avg_latency || 0) / 60)
  return (
    c.weight_success * (m.success_rate || 0) +
    c.weight_user_rating * (m.user_rating || 0) +
    c.weight_latency * latencyScore +
    (c.resource_score || 0.8) * 0.1
  )
})

const versionColumns = [
  { title: t('skillHub.verNum'), dataIndex: 'version_number', key: 'version_number', width: 80 },
  { title: t('skillHub.status'), key: 'is_stable', width: 80 },
  { title: t('skillHub.createdAt'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('skillHub.verAction'), key: 'action', width: 80 },
]

const logColumns = [
  { title: t('skillHub.logTriggerType'), dataIndex: 'trigger_type', key: 'trigger_type', width: 100 },
  { title: t('skillHub.logVerChange'), key: 'version_change', width: 120,
    customRender: ({ record }: any) => `${record.from_version ?? '-'} → ${record.to_version ?? '-'}` },
  { title: t('skillHub.logResult'), key: 'result', width: 100 },
  { title: t('skillHub.logTime'), dataIndex: 'created_at', key: 'created_at', width: 180 },
]

// ── 数据加载 ─────────────────────────────────────────────────────────────────

async function loadData() {
  if (!props.packageId) return
  loading.value = true
  try {
    const skillId = props.packageId
    const [metrics, config, versions, logs] = await Promise.all([
      getSkillMetrics(skillId),
      getEvolutionConfig(skillId),
      getSkillVersions(skillId),
      getEvolutionLogs(skillId),
    ])
    evoMetrics.value = metrics
    evoConfig.value = config
    evoVersions.value = versions
    evoLogs.value = logs
    await loadChatModels()
  } catch (e: any) {
    message.error(t('skillHub.loadEvoFailed') + (e.message || t('skillHub.unknownError')))
  } finally {
    loading.value = false
  }
}

async function loadChatModels() {
  chatModelsLoading.value = true
  try {
    chatModels.value = await getChatModels()
  } catch (e: any) {
    chatModels.value = []
  } finally {
    chatModelsLoading.value = false
  }
}

async function saveEvoConfig() {
  if (!props.packageId) return
  try {
    const { skill_id, ...data } = evoConfig.value
    await updateEvolutionConfig(props.packageId, data)
    message.success(t('skillHub.evoSaved'))
  } catch (e: any) {
    message.error(t('skillHub.saveFailed') + (e.message || t('skillHub.unknownError')))
  }
}

async function handleTriggerEvolution() {
  if (!props.packageId) return
  evoTriggering.value = true
  try {
    const res = await triggerEvolution(
      props.packageId,
      evoConfig.value.model_code || null,
    )
    if (res.evolved) {
      message.success(res.message)
    } else {
      message.info(res.message)
    }
    await loadData()
  } catch (e: any) {
    message.error(t('skillHub.evoFailed') + (e?.data?.detail || e.message || t('skillHub.unknownError')))
  } finally {
    evoTriggering.value = false
  }
}

async function handleRollback(version: number) {
  if (!props.packageId) return
  try {
    await rollbackVersion(props.packageId, version)
    message.success(t('skillHub.rolledBack', { version }))
    await loadData()
  } catch (e: any) {
    message.error(t('skillHub.rollbackFailed') + (e?.data?.detail || e.message || t('skillHub.unknownError')))
  }
}

// 监听 packageId 变化自动加载
watch(() => props.packageId, (val) => {
  if (val) loadData()
})

defineExpose({ loadData })
</script>

<style scoped>
.evo-metrics {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--bg-input);
  border-radius: 6px;
}

.evo-alert {
  margin-bottom: 16px;
}

.evo-actions {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;
}

.evo-config-form {
  margin-bottom: 16px;
}

.text-disabled {
  color: var(--fg-muted);
  font-size: 12px;
}
</style>
