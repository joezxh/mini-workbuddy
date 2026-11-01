<template>
  <div class="ont-build">
    <OntScopePicker :ontology-id="ontologyId" @changed="onScopeChanged" />

    <a-divider style="margin: 12px 0" />

    <a-space wrap class="ont-build__ctrl">
      <span>{{ t2('构建模式') }}：</span>
      <a-radio-group v-model:value="mode" button-style="solid">
        <a-radio-button value="rules">{{ t2('仅规则') }}</a-radio-button>
        <a-radio-button value="rules+semantic">{{ t2('规则 + AI 语义补全') }}</a-radio-button>
      </a-radio-group>
      <a-button type="primary" :loading="starting" :disabled="!canStart" @click="start">
        {{ running ? t2('构建中…') : t2('开始构建') }}
      </a-button>
      <a-button v-if="running" danger @click="cancel">{{ t2('取消') }}</a-button>
    </a-space>

    <a-progress
      v-if="job"
      :percent="Math.round((job.progress || 0) * 100)"
      :status="progressStatus"
      class="ont-build__progress"
    />
    <p v-if="job" class="ont-build__phase">{{ t2('阶段') }}: {{ job.phase || '-' }} · {{ job.status }}</p>

    <a-alert v-if="degradedReason" type="warning" show-icon class="ont-build__degraded"
             :message="t2('AI 语义补全不可用，已按规则构建') + (degradedReason ? `（${degradedReason}）` : '')" />

    <!-- 日志流 -->
    <div v-if="logs.length" class="ont-build__logs">
      <div v-for="(l, i) in logs" :key="i" class="ont-build__log" :class="`ont-build__log--${l.level || 'info'}`">
        {{ l.msg }}
      </div>
    </div>

    <a-alert v-if="doneStats" type="success" show-icon class="ont-build__done"
             :message="t2('构建完成')" :description="statsText" />
  </div>
</template>

<script setup lang="ts">
/**
 * 构建面板（E4/E7 SSE + E8 取消）：scope 从草稿提升为正式，启动后台 worker，进度经 SSE 推送。
 * §6.2：done/error 收尾即关闭连接，避免通用 sseClient 对终态任务无限重连。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { createBuildJob, cancelBuildJob, buildJobStreamPath, getDraftScope } from '@/api/dataops'
import { connectEventStream } from '@/utils/sseClient'
import { t2 } from './ontologyText'
import OntScopePicker from './OntScopePicker.vue'

const props = defineProps<{ ontologyId: number | null }>()
const emit = defineEmits<{ (e: 'built'): void }>()

const mode = ref<'rules' | 'rules+semantic'>('rules')
const scope = ref<Record<string, any>>({})
const starting = ref(false)
const running = ref(false)
const job = ref<any>(null)
const logs = ref<any[]>([])
const doneStats = ref<any>(null)
const degradedReason = ref('')
let client: any = null

const canStart = computed(() => (scope.value.tables || []).length > 0 && !running.value && props.ontologyId)
const progressStatus = computed(() => {
  if (!job.value) return 'normal'
  if (job.value.status === 'failed') return 'exception'
  if (job.value.status === 'succeeded') return 'success'
  return 'active'
})
const statsText = computed(() => (doneStats.value ? JSON.stringify(doneStats.value) : ''))

async function onScopeChanged() {
  if (props.ontologyId) scope.value = (await getDraftScope(props.ontologyId)) || {}
}

watch(() => props.ontologyId, onScopeChanged, { immediate: true })

function closeStream() {
  client?.close?.()
  client = null
}

function openStream(jobId: number) {
  closeStream()
  client = connectEventStream(buildJobStreamPath(jobId), {
    onEvent: (ev: any) => {
      if (ev.phase != null) {
        job.value = { ...(job.value || {}), phase: ev.phase, progress: ev.progress, status: 'running' }
      } else if (ev.level) {
        logs.value = [...logs.value, ev].slice(-200)
      } else if (ev.reason) {
        degradedReason.value = ev.reason
      } else if (ev.status === 'succeeded') {
        doneStats.value = ev.stats
        job.value = { ...(job.value || {}), status: 'succeeded', progress: 1 }
        finishRun()
      } else if (ev.code) {
        job.value = { ...(job.value || {}), status: 'failed', error_code: ev.code }
        message.error(`${t2('构建失败')}: ${ev.code}`)
        finishRun()
      }
    },
    onError: () => finishRun(),
  })
}

function finishRun() {
  closeStream()
  running.value = false
  emit('built')
}

async function start() {
  if (!canStart.value || !props.ontologyId) return
  starting.value = true
  logs.value = []
  doneStats.value = null
  degradedReason.value = ''
  try {
    const resp: any = await createBuildJob(props.ontologyId, { mode: mode.value, scope: scope.value })
    const j = resp?.job ?? resp
    job.value = { ...j, progress: j.progress || 0, status: j.status || 'pending' }
    running.value = true
    openStream(j.id)
    if (resp?.created === false) message.info(t2('命中既有任务（幂等），复用其进度'))
  } finally {
    starting.value = false
  }
}

async function cancel() {
  if (!job.value?.id) return
  await cancelBuildJob(job.value.id)
  message.success(t2('已请求取消'))
}

onBeforeUnmount(closeStream)
</script>

<style lang="less" scoped>
.ont-build {
  &__ctrl {
    margin-bottom: 8px;
  }
  &__phase {
    color: var(--fg-mute, #999);
    font-size: 12px;
  }
  &__logs {
    margin-top: 12px;
    max-height: 240px;
    overflow: auto;
    background: var(--bg-subtle, #fafafa);
    border-radius: 6px;
    padding: 8px;
    font-family: monospace;
    font-size: 12px;
  }
  &__log--warn {
    color: #d46b08;
  }
  &__log--error {
    color: #cf1322;
  }
  &__degraded,
  &__done {
    margin-top: 12px;
  }
}
</style>
