<template>
  <a-drawer
    v-model:open="visible"
    title="执行链路追踪"
    placement="right"
    :width="600"
    :body-style="{ padding: '12px' }"
  >
    <a-spin :spinning="loading">
      <!-- 链路概览 -->
      <a-card size="small" title="链路概览" class="trace-overview-card">
        <a-descriptions :column="2" size="small">
          <a-descriptions-item label="Trace ID">
            <a-tooltip :title="traceData?.trace_id">
              <span class="trace-id">{{ truncateId(traceData?.trace_id) }}</span>
            </a-tooltip>
            <CopyOutlined class="copy-icon" @click="copyText(traceData?.trace_id || '')" />
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor">{{ traceData?.status || 'OK' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="Agent">{{ traceData?.agent_id }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ traceData?.agent_type }}</a-descriptions-item>
          <a-descriptions-item label="耗时">{{ traceData?.duration_ms }}ms</a-descriptions-item>
          <a-descriptions-item label="Span数">{{ traceData?.total_spans }}</a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- 链路时间线 -->
      <a-card size="small" title="执行时间线" class="trace-timeline-card" style="margin-top: 12px">
        <template #extra>
          <a-space>
            <a-button size="small" @click="loadTrace">
              <ReloadOutlined :spin="loading" />
            </a-button>
            <a-button size="small" type="link" :href="jaegerUrl" target="_blank">
              <LinkOutlined /> Jaeger
            </a-button>
          </a-space>
        </template>
        
        <a-timeline>
          <a-timeline-item
            v-for="span in spans"
            :key="span.span_id"
            :color="getSpanColor(span)"
          >
            <div class="span-item">
              <div class="span-header">
                <span class="span-name">{{ span.name }}</span>
                <span class="span-duration">{{ span.duration_ms }}ms</span>
              </div>
              <div class="span-meta">
                <a-tag size="small" :color="getSpanTypeColor(span.attributes?.span_type)">
                  {{ span.attributes?.span_type || 'execute' }}
                </a-tag>
                <span class="span-time">{{ formatTime(span.start_time) }}</span>
              </div>
              <div v-if="span.attributes && Object.keys(span.attributes).length > 0" class="span-attrs">
                <div v-for="(val, key) in span.attributes" :key="key" class="attr-item">
                  <span class="attr-key">{{ key }}:</span>
                  <span class="attr-val">{{ formatAttrValue(val) }}</span>
                </div>
              </div>
              <div v-if="span.events && span.events.length > 0" class="span-events">
                <div v-for="(event, idx) in span.events" :key="idx" class="event-item">
                  <ClockCircleOutlined /> {{ event.name }}
                </div>
              </div>
            </div>
          </a-timeline-item>
        </a-timeline>

        <a-empty v-if="spans.length === 0 && !loading" description="暂无链路数据" />
      </a-card>
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message as antMsg } from 'ant-design-vue'
import {
  CopyOutlined,
  ReloadOutlined,
  LinkOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons-vue'
import { getTraceTimeline, getTraceSpans } from '@/api/agent'

const props = defineProps<{
  traceId?: string
  agentId?: string
  jaegerBaseUrl?: string
}>()

const visible = defineModel<boolean>('visible', { default: false })
const loading = ref(false)
const traceData = ref<any>(null)
const spans = ref<any[]>([])

const jaegerUrl = computed(() => {
  if (!props.traceId || !props.jaegerBaseUrl) return '#'
  return `${props.jaegerBaseUrl}/trace/${props.traceId}`
})

const statusColor = computed(() => {
  const status = traceData.value?.status
  return status === 'ERROR' ? 'red' : 'green'
})

watch(() => props.traceId, (val) => {
  if (val && visible.value) {
    loadTrace()
  }
})

watch(visible, (val) => {
  if (val && props.traceId) {
    loadTrace()
  }
})

async function loadTrace() {
  if (!props.traceId) return
  
  loading.value = true
  try {
    const timelineRes = await getTraceTimeline(props.traceId)
    const spansRes = await getTraceSpans(props.traceId)
    
    if (timelineRes) {
      traceData.value = {
        ...timelineRes,
        trace_id: timelineRes.trace_id || props.traceId,
        agent_id: props.agentId,
      }
    }
    
    if (spansRes?.spans) {
      spans.value = spansRes.spans
    } else if (timelineRes?.spans) {
      spans.value = timelineRes.spans
    }
  } catch (e: any) {
    antMsg.error('加载链路失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function getSpanColor(span: any): string {
  if (span.status === 'ERROR') return 'red'
  if (span.duration_ms > 1000) return 'orange'
  return 'green'
}

function getSpanTypeColor(type?: string): string {
  const map: Record<string, string> = {
    skill_execution: 'blue',
    llm_call: 'purple',
    tool_call: 'cyan',
    agent_execute: 'green',
    context_inject: 'orange',
  }
  return map[type || ''] || 'default'
}

function truncateId(id?: string): string {
  if (!id) return ''
  return id.length > 16 ? id.slice(0, 8) + '...' + id.slice(-8) : id
}

function formatTime(time?: string): string {
  if (!time) return ''
  try {
    const d = new Date(time)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}.${d.getMilliseconds().toString().padStart(3, '0')}`
  } catch {
    return time
  }
}

function formatAttrValue(val: any): string {
  if (val === null || val === undefined) return 'null'
  if (Array.isArray(val)) return JSON.stringify(val).slice(0, 100)
  if (typeof val === 'object') return JSON.stringify(val).slice(0, 100)
  return String(val).slice(0, 100)
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    antMsg.success('已复制')
  } catch {
    antMsg.error('复制失败')
  }
}
</script>

<style scoped lang="less">
.trace-id {
  font-family: monospace;
  font-size: 12px;
  background: var(--bg-input);
  padding: 2px 6px;
  border-radius: 4px;
}

.copy-icon {
  margin-left: 6px;
  cursor: pointer;
  color: var(--accent);
  &:hover { color: var(--accent-hover); }
}

.span-item {
  padding: 4px 0;
}

.span-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.span-name {
  font-weight: 500;
  color: var(--fg);
  font-size: 13px;
}

.span-duration {
  font-size: 12px;
  color: var(--fg-secondary);
  font-family: monospace;
}

.span-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.span-time {
  font-size: 11px;
  color: var(--fg-muted);
  font-family: monospace;
}

.span-attrs {
  background: var(--bg-input);
  border-radius: 4px;
  padding: 6px 8px;
  margin-top: 4px;
}

.attr-item {
  font-size: 11px;
  line-height: 1.6;
  color: var(--fg-secondary);
}

.attr-key {
  color: var(--fg-secondary);
  margin-right: 4px;
}

.attr-val {
  color: var(--fg);
  word-break: break-all;
}

.span-events {
  margin-top: 4px;
  padding-left: 8px;
}

.event-item {
  font-size: 11px;
  color: var(--fg-secondary);
  line-height: 1.6;
}

.trace-overview-card :deep(.ant-descriptions-item-label) {
  color: var(--fg-secondary);
  font-size: 12px;
}

.trace-overview-card :deep(.ant-descriptions-item-content) {
  font-size: 12px;
}
</style>
