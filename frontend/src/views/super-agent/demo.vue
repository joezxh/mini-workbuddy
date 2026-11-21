<!-- SuperAgent Demo 页面（Task 4.4）—— 预设脚本：一键运行 → 实时进度 → 最终报告 -->
<template>
  <div class="sa-demo">
    <div class="sa-page-head demo-head">
      <h1>🎯 电商营销 Demo · 完整端到端范例</h1>
      <p>数据采集 → 竞品分析 → 方案生成 → 反思校验 → ERP 执行，完整跑通 SuperAgent 流水线</p>
      <a-button class="demo-run" type="primary" :loading="running" :disabled="running" @click="run">
        {{ running ? '运行中…' : '🚀 一键运行' }}
      </a-button>
    </div>

    <!-- 预设脚本说明 -->
    <a-card title="Demo 脚本" size="small" class="mb12">
      <a-steps :current="stepIndex" size="small" :items="stepItems" />
    </a-card>

    <div class="sa-demo__grid">
      <!-- 运行参数 -->
      <a-card title="运行参数" size="small" class="mb12">
        <a-form layout="vertical">
          <a-form-item label="任务标题">
            <a-input v-model:value="form.title" :maxlength="500" />
          </a-form-item>
          <a-form-item label="Prompt（Agent 指令）">
            <a-textarea v-model:value="form.prompt" :rows="5" />
          </a-form-item>
          <a-alert
            v-if="!running"
            type="info"
            show-icon
            message="点击「一键运行」将创建 Ticket（skip eval 直接 accept），并订阅 SSE 实时渲染引擎事件。"
          />
        </a-form>
      </a-card>

      <!-- 实时事件流 -->
      <a-card size="small" class="mb12">
        <template #title>
          实时进度
          <a-badge :status="store.connected ? 'processing' : 'default'" :text="store.connected ? 'SSE 已连接' : '未连接'" style="margin-left: 8px" />
        </template>
        <div ref="timelineEl" class="sa-demo__timeline">
          <div v-for="(e, i) in events" :key="i" class="sa-demo__evt" :class="`sa-demo__evt--${e.level}`">
            <span class="sa-demo__evt-time">{{ e.time }}</span>
            <a-tag :color="e.color" style="margin-inline-end: 6px">{{ e.event }}</a-tag>
            <span class="sa-demo__evt-text">{{ e.summary }}</span>
          </div>
          <a-empty v-if="!events.length && !running" description="点击「一键运行」开始" :image-style="{ height: '50px' }" />
          <div v-if="running && !events.length" class="sa-demo__typing">
            <span></span><span></span><span></span> 等待引擎事件…
          </div>
        </div>
      </a-card>

      <!-- 最终报告 -->
      <a-card v-if="report" title="最终报告" size="small">
        <a-descriptions :column="1" size="small">
          <a-descriptions-item label="Ticket 状态">
            <a-tag color="green">{{ ticketStatus }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="报告内容">
            <pre class="sa-demo__report">{{ reportText }}</pre>
          </a-descriptions-item>
        </a-descriptions>
        <a-button type="link" @click="router.push(`/super-agent/workbench/detail/${ticketId}`)">
          查看 Ticket 详情 →
        </a-button>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { type TicketDetail, createTicket, getTicket, openEventsSSE } from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'

const router = useRouter()
const store = useSuperAgentStore()

// ============ 预设 Demo 脚本 ============
const stepItems = [
  { title: '创建 Ticket', description: '手动触发，skip eval' },
  { title: 'Engine 分派', description: 'Mandate + Assignment' },
  { title: 'Worker 执行', description: 'AgentScope ReAct' },
  { title: '反思与交付', description: 'ticket_completed' },
]
const form = reactive({
  title: '整理 GitHub 仓库待处理事项',
  prompt: '请帮我梳理当前仓库的待处理事项，输出一份结构化清单。',
})

// ============ 运行状态 ============
const running = ref(false)
const ticketId = ref('')
const ticketStatus = ref('')
const report = ref(false)
const reportText = ref('')
const events = ref<{ event: string; summary: string; time: string; color: string; level: string }[]>([])
const timelineEl = ref<HTMLElement | null>(null)

const stepIndex = computed(() => {
  if (!running.value && report.value) return 4
  if (events.value.some(e => e.event.startsWith('effect_launch'))) return 2
  if (events.value.some(e => e.event.startsWith('effect_assess') || e.event === 'ticket_created')) return 1
  return 0
})

function nowTime(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function pushEvent(event: string, data: any) {
  const meta: Record<string, { color: string; level: string }> = {
    ticket_created: { color: 'blue', level: 'info' },
    effect_assess: { color: 'gold', level: 'info' },
    effect_launch: { color: 'geekblue', level: 'info' },
    ticket_completed: { color: 'green', level: 'done' },
    connected: { color: 'default', level: 'muted' },
  }
  const m = meta[event] || { color: 'purple', level: 'info' }
  const summary = (event === 'ticket_completed' && data?.ticket_id)
    ? `Ticket ${data.ticket_id} 完成`
    : JSON.stringify(data).slice(0, 120)
  events.value.push({ event, summary, time: nowTime(), color: m.color, level: m.level })
  nextTick(() => timelineEl.value?.scrollTo({ top: timelineEl.value.scrollHeight, behavior: 'smooth' }))
}

let es: EventSource | null = null
let fallbackTimer: number | null = null

async function run() {
  if (running.value) return
  events.value = []
  report.value = false
  reportText.value = ''
  running.value = true

  // 订阅引擎 SSE
  es = openEventsSSE(1, {
    connected: () => pushEvent('connected', { workspace_id: 1 }),
    ticket_created: (d) => pushEvent('ticket_created', d),
    effect_assess: (d) => pushEvent('effect_assess', d),
    effect_launch: (d) => pushEvent('effect_launch', d),
    ticket_completed: (d) => {
      pushEvent('ticket_completed', d)
      finish(d?.ticket_id || ticketId.value)
    },
  })

  try {
    // ① 创建 Ticket（skip eval，直接 accept）
    const t = await createTicket({ workspace_id: 1, title: form.title, prompt: form.prompt }) as any
    ticketId.value = t.id
    message.success(`Ticket ${t.id} 已创建`)
    // ② 轮询兜底：SSE 收不到 ticket_completed 时 60s 后拉详情收尾
    if (fallbackTimer) window.clearTimeout(fallbackTimer)
    fallbackTimer = window.setTimeout(() => { if (running.value) finish(ticketId.value) }, 60000)
  } catch {
    es?.close(); es = null
    running.value = false
  }
}

async function finish(id: string) {
  running.value = false
  es?.close(); es = null
  try {
    const detail = await getTicket(id) as any as TicketDetail
    ticketStatus.value = detail.status
    const fr = (detail.assignment as any)?.final_report
    reportText.value = fr && Object.keys(fr).length
      ? JSON.stringify(fr, null, 2)
      : detail.intent_evidence || '（暂无 Worker 报告）'
    report.value = true
  } catch {
    report.value = true
    reportText.value = '（Ticket 详情拉取失败）'
  }
}

onUnmounted(() => {
  es?.close()
  if (fallbackTimer) window.clearTimeout(fallbackTimer)
})
</script>

<style scoped lang="less">
.demo-head {
  position: relative;
  .demo-run { position: absolute; right: 0; top: 2px; }
}

.sa-demo {
  &__grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0;
  }

  &__timeline {
    max-height: 320px;
    overflow: auto;
    font-size: 13px;
  }

  &__evt {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    border-radius: 4px;

    &--done { background: rgba(82, 196, 26, 0.08); }
    &--muted { opacity: 0.6; }
  }

  &__evt-time {
    font-size: 11px;
    color: var(--ant-color-text-tertiary, #bfbfbf);
    font-family: monospace;
  }

  &__evt-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--ant-color-text-secondary, #595959);
  }

  &__typing {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px;
    color: var(--ant-color-text-tertiary, #8c8c8c);
    font-size: 12px;

    span {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--ant-color-primary, #1677ff);
      animation: sa-typing 1s infinite ease-in-out;

      &:nth-child(2) { animation-delay: 0.15s; }
      &:nth-child(3) { animation-delay: 0.3s; }
    }
  }

  &__report {
    margin: 0;
    padding: 12px;
    background: var(--ant-color-fill-quaternary, #fafafa);
    border-radius: 6px;
    font-size: 12px;
    max-height: 240px;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

@keyframes sa-typing {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-4px); opacity: 1; }
}
</style>
