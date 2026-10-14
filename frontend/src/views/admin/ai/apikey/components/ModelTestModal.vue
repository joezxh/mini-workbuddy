<template>
  <a-modal
    v-model:open="visible"
    :title="t('apiKeyMgmt.testTitle')"
    width="1100px"
    :footer="null"
    :destroy-on-close="true"
    @cancel="handleClose"
  >
    <div class="model-test-container">
      <!-- 模型选择区 -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">{{ t('apiKeyMgmt.selectModel') }}</span>
          <a-tag color="blue">{{ t('apiKeyMgmt.selectedCount', { count: selectedModels.length }) }}</a-tag>
        </div>
        <a-checkbox-group v-model:value="selectedModelIds" class="model-checkbox-group">
          <a-checkbox
            v-for="m in availableModels"
            :key="m.id"
            :value="m.id"
            class="model-checkbox"
          >
            <span class="model-label">
              <span class="model-name">{{ m.name }}</span>
              <span class="model-id">{{ m.model }}</span>
              <a-tag :color="typeTagColor(m.type)" size="small">{{ typeName(m.type) }}</a-tag>
            </span>
          </a-checkbox>
        </a-checkbox-group>
        <div class="probe-hint">{{ t('apiKeyMgmt.probeHint') }}</div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <a-button type="primary" :loading="isRunning" :disabled="!canRun" @click="runTest">
          <SendOutlined /> {{ t('apiKeyMgmt.startTest') }}
        </a-button>
        <a-button v-if="isRunning" danger @click="stopTest">
          <StopOutlined /> {{ t('apiKeyMgmt.stop') }}
        </a-button>
        <a-button @click="clearResults">
          <ClearOutlined /> {{ t('apiKeyMgmt.clearResults') }}
        </a-button>
        <a-tag v-if="hasResult" color="geekgold" class="summary-tag">
          {{ t('apiKeyMgmt.probeSummary', {
            total: doneCount + failedCount,
            passed: doneCount,
            failed: failedCount,
          }) }}
        </a-tag>
      </div>

      <!-- 结果展示区 -->
      <div class="results-section" v-if="Object.keys(results).length > 0">
        <div class="section-header">
          <span class="section-title">{{ t('apiKeyMgmt.testResults') }}</span>
        </div>
        <div class="results-grid" :class="{ 'multi-grid': Object.keys(results).length > 1 }">
          <div
            v-for="(result, modelId) in results"
            :key="modelId"
            class="result-card"
            :class="{ 'result-card--fail': result.status === 'error' }"
          >
            <div class="result-header">
              <span class="result-model-name">{{ result.modelName }}</span>
              <a-tag :color="typeTagColor(result.type)" size="small">{{ typeName(result.type) }}</a-tag>
              <a-tag
                :color="result.status === 'done' ? 'success' : result.status === 'error' ? 'error' : 'processing'"
                size="small"
              >
                {{ statusText(result.status) }}
              </a-tag>
              <span v-if="result.latencyMs" class="result-meta">
                {{ t('apiKeyMgmt.probeLatency') }} {{ result.latencyMs }}ms
              </span>
            </div>

            <div class="result-content">
              <div class="probe-row">
                <span class="probe-key">{{ t('apiKeyMgmt.probeEndpoint') }}</span>
                <span class="probe-val probe-endpoint">{{ result.endpoint || '—' }}</span>
              </div>
              <div class="probe-row">
                <span class="probe-key">{{ t('apiKeyMgmt.colModelId') }}</span>
                <span class="probe-val">{{ result.message || (result.ok ? 'OK' : '—') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SendOutlined, StopOutlined, ClearOutlined } from '@ant-design/icons-vue'
import { probeModel, type AiChatModel } from '@/api/ai-apikey'
import { useDictionary } from '@/composables/useDictionary'

const { t } = useI18n()

interface ProbeResult {
  modelName: string
  type: number
  status: 'running' | 'done' | 'error'
  ok: boolean
  message: string
  latencyMs: number
  endpoint: string
}

const props = defineProps<{
  open: boolean
  models: AiChatModel[]
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

// 模型类别标签/颜色统一取自数据字典（model_type），避免硬编码错位
const { modelTypes, loadModelTypes } = useDictionary()
onMounted(() => {
  loadModelTypes()
})

const availableModels = computed(() => props.models || [])
const selectedModelIds = ref<number[]>([])
const isRunning = ref(false)
const cancelled = ref(false)
const results = ref<Record<number, ProbeResult>>({})

const selectedModels = computed(() =>
  availableModels.value.filter(m => selectedModelIds.value.includes(m.id))
)

const canRun = computed(() =>
  selectedModelIds.value.length > 0 && !isRunning.value
)

const doneCount = computed(() =>
  Object.values(results.value).filter(r => r.status === 'done').length
)
const failedCount = computed(() =>
  Object.values(results.value).filter(r => r.status === 'error').length
)
const hasResult = computed(() => Object.keys(results.value).length > 0)

// 打开时默认选中所有模型
watch(
  () => props.open,
  (val) => {
    if (val) {
      selectedModelIds.value = availableModels.value.map(m => m.id)
      results.value = {}
      cancelled.value = false
    }
  }
)

function typeName(type?: number): string {
  if (type === undefined || type === null) return '-'
  const item = modelTypes.value.find(
    tp => Number(tp.item_value ?? tp.item_code) === Number(type)
  )
  return item?.item_name || String(type)
}

function typeTagColor(type?: number): string {
  if (type === undefined || type === null) return 'default'
  const item = modelTypes.value.find(
    tp => Number(tp.item_value ?? tp.item_code) === Number(type)
  )
  return item?.color || 'blue'
}

function statusText(status: string): string {
  if (status === 'running') return t('apiKeyMgmt.probing')
  if (status === 'done') return t('apiKeyMgmt.statusDone')
  if (status === 'error') return t('apiKeyMgmt.statusError')
  return status
}

async function runTest() {
  if (!canRun.value) return
  isRunning.value = true
  cancelled.value = false

  const models = selectedModels.value
  // 初始化每条结果
  for (const model of models) {
    results.value[model.id] = {
      modelName: `${model.name} (${model.model})`,
      type: model.type ?? 1,
      status: 'running',
      ok: false,
      message: '',
      latencyMs: 0,
      endpoint: '',
    }
  }

  // 并行探测所有选中模型
  await Promise.all(models.map(m => probeOne(m)))

  if (!cancelled.value) {
    isRunning.value = false
  }
}

async function probeOne(model: AiChatModel) {
  try {
    const res = await probeModel(model.id)
    if (cancelled.value) return
    const r = results.value[model.id]
    if (!r) return
    r.ok = res.ok
    r.status = res.ok ? 'done' : 'error'
    r.message = res.message
    r.latencyMs = res.latency_ms
    r.endpoint = res.endpoint
  } catch (e: any) {
    if (cancelled.value) return
    const r = results.value[model.id]
    if (r) {
      r.ok = false
      r.status = 'error'
      r.message = e?.message || t('apiKeyMgmt.requestFailed')
    }
  }
}

function stopTest() {
  cancelled.value = true
  isRunning.value = false
  // 将仍在进行中的结果标记为已停止
  Object.values(results.value).forEach(r => {
    if (r.status === 'running') {
      r.status = 'error'
      r.message = t('apiKeyMgmt.testStopped')
    }
  })
  message.info(t('apiKeyMgmt.testStopped'))
}

function clearResults() {
  results.value = {}
}

function handleClose() {
  stopTest()
  visible.value = false
}
</script>

<style lang="less" scoped>
.model-test-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section {
  .section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .section-title {
      font-weight: 600;
      font-size: 14px;
      color: var(--fg);
    }
  }
}

.probe-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--fg-muted);
}

.model-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
  padding: 8px;
  background: var(--bg-input);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.model-checkbox {
  margin-right: 0 !important;
}

.model-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  .model-name {
    font-weight: 500;
  }

  .model-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--fg-secondary);
    background: var(--bg-hover);
    padding: 1px 4px;
    border-radius: 3px;
  }
}

.action-bar {
  display: flex;
  gap: 8px;
  align-items: center;

  .summary-tag {
    margin-left: auto;
  }
}

.results-section {
  .section-header {
    margin-bottom: 8px;
  }
}

.results-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;

  &.multi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 12px;
  }
}

.result-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-surface);

  &--fail {
    border-color: var(--error, #ff4d4f);
  }
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-input);
  border-bottom: 1px solid var(--border);

  .result-model-name {
    font-weight: 600;
    font-size: 13px;
    flex: 1;
  }

  .result-meta {
    font-size: 11px;
    color: var(--fg-secondary);
    font-family: monospace;
  }
}

.result-content {
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  min-height: 60px;

  .probe-row {
    display: flex;
    gap: 8px;
    align-items: baseline;
    margin-bottom: 6px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .probe-key {
    flex: 0 0 72px;
    color: var(--fg-muted);
    font-size: 12px;
  }

  .probe-val {
    flex: 1;
    word-break: break-all;
  }

  .probe-endpoint {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--fg-secondary);
  }
}
</style>
