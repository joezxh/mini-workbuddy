<template>
  <a-drawer
    :open="open"
    :title="t('kbMgmt.flowTitle')"
    width="520"
    placement="right"
    @close="onClose"
  >
    <a-skeleton v-if="loading" active :paragraph="{ rows: 6 }" />

    <template v-else>
      <!-- 概要 -->
      <a-descriptions :column="2" size="small" bordered class="flow-drawer__meta">
        <a-descriptions-item :label="t('common.status')">
          <a-tag :color="statusColor(flow?.status || record.status)">
            {{ flow?.status || record.status }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.segmentCount')">
          {{ flow?.segment_count ?? record.segment_count ?? 0 }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.retryCount')">
          {{ flow?.retry_count ?? 0 }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('kbMgmt.fileName')">
          {{ flow?.name || record.name }}
        </a-descriptions-item>
      </a-descriptions>

      <!-- 流程步骤 -->
      <a-steps
        class="flow-drawer__steps"
        direction="vertical"
        size="small"
        :current="currentStep"
        :status="stepsStatus"
      >
        <a-step v-for="(s, i) in steps" :key="s.key" :title="s.label">
          <template #description>
            <div class="flow-drawer__desc">
              <span>{{ s.detail || '—' }}</span>
              <a-tag v-if="s.tag" size="small">{{ s.tag }}</a-tag>
            </div>
          </template>
        </a-step>
      </a-steps>

      <!-- 失败信息 -->
      <a-alert
        v-if="failedStep"
        class="flow-drawer__alert"
        type="error"
        show-icon
        :message="`${t('kbMgmt.flowFailedAt')}：${stepLabel(failedStep)}`"
      >
        <template #description>
          <pre class="flow-drawer__err">{{ errorText }}</pre>
        </template>
      </a-alert>

      <a-empty
        v-if="!steps.length"
        :description="t('kbMgmt.flowNoDetail')"
      />
    </template>

    <template #footer>
      <a-space>
        <a-button :loading="retrying" type="primary" @click="onRetry">
          {{ t('kbMgmt.retry') }}
        </a-button>
        <a-button :loading="reprocessing" @click="onReprocess">
          {{ t('kbMgmt.reprocess') }}
        </a-button>
      </a-space>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { getDocumentFlow, retryDocument, reprocessDocument, type KbDocument } from '@/api/kb'

const props = defineProps<{ open: boolean; record: KbDocument }>()
const emit = defineEmits<{ 'update:open': [boolean]; changed: [] }>()
const { t } = useI18n()

const loading = ref(false)
const retrying = ref(false)
const reprocessing = ref(false)
const flow = ref<any>(null)

// 固定流程（与后端 document_pipeline 的步骤一一对应）
const STEP_KEYS = ['upload', 'parse', 'clean', 'chunk', 'vectorize', 'done'] as const
type StepKey = typeof STEP_KEYS[number]

const STEP_LABELS: Record<StepKey, string> = {
  upload: 'kbMgmt.flowUpload',
  parse: 'kbMgmt.flowParse',
  clean: 'kbMgmt.flowClean',
  chunk: 'kbMgmt.flowChunk',
  vectorize: 'kbMgmt.flowVectorize',
  done: 'kbMgmt.flowDone',
}

function stepLabel(key: string) {
  const k = key as StepKey
  return STEP_LABELS[k] ? t(STEP_LABELS[k]) : key
}

const failedStep = computed(() => flow.value?.failed_step || null)
const errorText = computed(() => flow.value?.error_detail || '')

/** 把后端 pipeline_steps 的产出摘要挂到对应步骤上 */
const stepDetails = computed(() => {
  const out: Record<string, { detail: string; tag?: string }> = {}
  const list: any[] = flow.value?.steps || []
  for (const s of list) {
    if (s?.step === 'parse') {
      out.parse = {
        detail: `${t('kbMgmt.flowSections')}：${s.sections ?? 0}`,
        tag: s.parser,
      }
    } else if (s?.step === 'clean') {
      out.clean = { detail: `${t('kbMgmt.flowOperators')}：${(s.operators || []).length}` }
    } else if (s?.step === 'chunk') {
      out.chunk = {
        detail: `${t('kbMgmt.flowChunks')}：${s.chunks ?? 0}`,
        tag: s.chunker,
      }
    } else if (s?.step === 'vectorize') {
      out.vectorize = { detail: `${t('kbMgmt.flowVectors')}：${s.chunks ?? 0}` }
    }
  }
  return out
})

const steps = computed(() => {
  const status = flow.value?.status || props.record.status
  if (status === 'pending' && !flow.value) return []
  return STEP_KEYS.map((key) => ({
    key,
    label: stepLabel(key),
    detail: stepDetails.value[key]?.detail || '',
    tag: stepDetails.value[key]?.tag || '',
  }))
})

const failedIndex = computed(() => {
  if (!failedStep.value) return -1
  return STEP_KEYS.indexOf(failedStep.value as StepKey)
})

const currentStep = computed(() => {
  const status = flow.value?.status || props.record.status
  if (failedIndex.value >= 0) return failedIndex.value
  if (status === 'completed') return STEP_KEYS.length - 1
  if (status === 'processing') return 1
  return 0
})

const stepsStatus = computed(() => {
  const status = flow.value?.status || props.record.status
  if (failedIndex.value >= 0) return 'error'
  if (status === 'completed') return 'finish'
  if (status === 'processing') return 'process'
  return 'wait'
})

function statusColor(status: string) {
  return (
    { pending: 'default', processing: 'processing', completed: 'success', failed: 'error' }[
      status
    ] || 'default'
  )
}

async function load() {
  loading.value = true
  try {
    const res: any = await getDocumentFlow(props.record.document_id)
    flow.value = res
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.flowLoadFailed'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (v) => {
    if (v) load()
  },
  { immediate: true },
)

function onClose() {
  emit('update:open', false)
}

async function onRetry() {
  retrying.value = true
  try {
    await retryDocument(props.record.document_id)
    message.success(t('kbMgmt.retryStarted'))
    await load()
    emit('changed')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.retryFailed'))
  } finally {
    retrying.value = false
  }
}

async function onReprocess() {
  reprocessing.value = true
  try {
    await reprocessDocument(props.record.document_id)
    message.success(t('kbMgmt.reprocessStarted'))
    await load()
    emit('changed')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.reprocessFailed'))
  } finally {
    reprocessing.value = false
  }
}
</script>

<style scoped>
.flow-drawer__meta {
  margin-bottom: 16px;
}
.flow-drawer__steps {
  margin-top: 8px;
}
.flow-drawer__desc {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--fg-secondary, #666);
}
.flow-drawer__alert {
  margin-top: 16px;
}
.flow-drawer__err {
  margin: 8px 0 0;
  padding: 10px;
  max-height: 220px;
  overflow: auto;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
