<!--
  TeamExecutionPanel.vue — 智能体团队模式执行详情面板（独立组件，不复用 SkillExecutionPanel）

  与 SkillExecutionPanel 展示结构对齐（思考过程 / 执行事件 / 时间线三个 Tab + 结果正文在下），
  实现完全独立，便于后续做团队模式专属的个性化展示（专家拓扑、并行泳道、角色贡献度等）。

  与思考模式的关键差异：团队有多名专家并行产出思考，故「思考过程」Tab **按专家分组**
  （每位专家一张可折叠卡片，累积其全部思考增量），而非按全局步骤序号排列。
-->
<template>
  <div class="team-execution-panel">
    <div class="execution-events-header" @click="collapsed = !collapsed">
      <CaretRightOutlined class="expand-arrow" :class="{ expanded: !collapsed }" />
      <TeamOutlined class="execution-icon" />
      <span class="execution-label">专家团协作</span>
      <a-badge :count="allEvents.length" :number-style="{ backgroundColor: 'var(--ok)', fontSize: '10px' }" />
      <span v-if="expertGroups.length" class="exec-expert-indicator">{{ expertGroups.length }} 位专家</span>
      <span v-if="streaming" class="exec-running-indicator"><LoadingOutlined spin /> 协作中...</span>
    </div>
    <div v-if="!collapsed" class="execution-events-body">
      <div v-if="internalLoading" class="exec-empty"><LoadingOutlined spin /> 加载中...</div>
      <a-tabs v-else size="small" :default-active-key="defaultTab">
        <!-- Tab 1: 思考过程（按专家分组） -->
        <a-tab-pane key="thinking">
          <template #tab>
            <BulbOutlined style="color: #722ed1" />
            <span>思考过程</span>
            <a-badge
              v-if="expertGroups.length"
              :count="expertGroups.length"
              :number-style="{ backgroundColor: '#b37feb', fontSize: '10px', marginLeft: '4px' }"
            />
          </template>
          <div v-if="expertGroups.length" class="expert-group-list">
            <div v-for="g in expertGroups" :key="g.key" class="expert-card">
              <div class="expert-head" @click="toggleExpertExpand(g.key)">
                <CaretRightOutlined class="expert-arrow" :class="{ expanded: expandedExperts[g.key] }" />
                <UserOutlined class="expert-avatar" />
                <span class="expert-name">{{ g.name }}</span>
                <span class="expert-count">{{ g.count }} 条</span>
                <span class="expert-time">{{ formatTime(g.time) }}</span>
              </div>
              <div v-show="expandedExperts[g.key]" class="expert-content">{{ g.content }}</div>
            </div>
          </div>
          <div v-else class="exec-empty">暂无专家思考记录</div>
        </a-tab-pane>
        <!-- Tab 2: 执行事件 -->
        <a-tab-pane key="events">
          <template #tab>
            <ToolOutlined style="color: var(--accent-2)" />
            <span>执行事件</span>
          </template>
          <div v-if="toolCallEvents.length || toolResultEvents.length" class="exec-section">
            <div class="exec-section-header"><ToolOutlined style="color: var(--accent-2)" /><span>工具调用</span></div>
            <template v-for="(evt, idx) in allToolEvents" :key="'tc' + idx">
              <div class="exec-item exec-tool-entry">
                <span class="exec-time">{{ formatTime(evt.time) }}</span>
                <span class="exec-icon-badge" :class="evt.type === 'tool_call' ? 'call' : 'result'">{{ evt.type === 'tool_call' ? '调用' : '结果' }}</span>
                <span class="exec-tool-name">{{ evt.data?.tool_name || evt.message }}</span>
              </div>
              <div v-if="evt.type === 'tool_call' && evt.data?.input" class="exec-tool-params">
                <div class="exec-params-toggle" @click="toggleExpand(`p_${idx}`)">
                  <CaretRightOutlined :class="{ expanded: expandedItems[`p_${idx}`] }" /><span>参数</span>
                </div>
                <pre v-if="expandedItems[`p_${idx}`]" class="exec-params-json">{{ formatJson(evt.data.input) }}</pre>
              </div>
              <div v-if="evt.type === 'tool_result' && evt.data?.result" class="exec-tool-result">
                <div class="exec-result-text" :class="{ truncated: !expandedItems[`r_${idx}`] }">{{ evt.data.result }}</div>
                <a v-if="String(evt.data.result).length > 150" class="exec-result-toggle" @click="toggleExpand(`r_${idx}`)">{{ expandedItems[`r_${idx}`] ? '收起' : '展开' }}</a>
              </div>
            </template>
          </div>
          <div v-if="progressEvents.length" class="exec-section">
            <div class="exec-section-header"><LoadingOutlined style="color: var(--accent)" /><span>执行步骤</span></div>
            <div v-for="(evt, idx) in progressEvents" :key="'p' + idx" class="exec-item">
              <span class="exec-time">{{ formatTime(evt.time) }}</span>
              <span class="exec-text progress-text">{{ evt.message }}</span>
            </div>
          </div>
          <div v-if="artifactEvents.length" class="exec-section">
            <div class="exec-section-header"><FileOutlined style="color: var(--info)" /><span>生成产物</span></div>
            <div v-for="(evt, idx) in artifactEvents" :key="'a' + idx" class="exec-item">
              <span class="exec-time">{{ formatTime(evt.time) }}</span>
              <span class="exec-text">{{ evt.message }}</span>
            </div>
          </div>
          <div v-if="!toolCallEvents.length && !progressEvents.length && !artifactEvents.length" class="exec-empty">
            暂无执行事件记录
          </div>
        </a-tab-pane>
        <!-- Tab 3: 时间线（团队并行分支泳道） -->
        <a-tab-pane key="timeline" class="timeline-pane">
          <template #tab>
            <HistoryOutlined style="color: var(--info)" />
            <span>时间线</span>
          </template>
          <TimelineFlowPlayer
            v-if="finalSteps.length || finalArtifacts.length"
            :steps="finalSteps"
            :artifacts="finalArtifacts"
            :streaming="!!streaming"
          />
          <div v-else class="exec-empty">暂无时间线记录</div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import {
  CaretRightOutlined, LoadingOutlined,
  BulbOutlined, ToolOutlined, FileOutlined, HistoryOutlined,
  TeamOutlined, UserOutlined,
} from '@ant-design/icons-vue'
import type { ExecutionEvent } from '@/types/shared'
import { getToken } from '@/utils/auth'
import TimelineFlowPlayer from './TimelineFlowPlayer.vue'

/** 专家思考分组 */
interface ExpertGroup {
  key: string
  name: string
  content: string
  count: number
  time?: string
}

const props = defineProps<{
  events?: ExecutionEvent[]
  streaming?: boolean
  executionId?: string | null
  unifiedSteps?: any[]
  unifiedArtifacts?: any[]
}>()

const internalEvents = ref<ExecutionEvent[]>([])
const internalLoading = ref(false)
const internalSteps = ref<any[]>([])
const internalArtifacts = ref<any[]>([])

const allEvents = computed(() => (props.events?.length ? props.events : internalEvents.value))
const finalSteps = computed(() => (props.unifiedSteps?.length ? props.unifiedSteps : internalSteps.value))
const finalArtifacts = computed(() => (props.unifiedArtifacts?.length ? props.unifiedArtifacts : internalArtifacts.value))

/** 从 API 加载历史执行事件（与 skill / thinking / agent 模式共用同一回放接口） */
async function loadHistoricalEvents(executionId: string) {
  internalLoading.value = true
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    const token = getToken()
    const response = await fetch(`${baseUrl}/api/v1/ai-agent/skill-execution/${executionId}/events`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    const rawEvents = data.events || []
    const converted: ExecutionEvent[] = []
    const steps: any[] = []
    const artifacts: any[] = []
    // model_call（leader 答案 token 流）按 tool_call_id 聚合成单条 tool_call，
    // 避免逐 token 产生上百条碎片；生成文本合并后展示在执行事件 Tab。
    const mcMap: Record<string, { content: string; time: string; role?: string }> = {}
    for (const raw of rawEvents) {
      const type = raw.type as string
      if (type === 'step') {
        steps.push({
          phase: raw.phase ?? '执行',
          event_type: raw.event_type ?? 'step',
          title: raw.title ?? '',
          seq: raw.seq ?? steps.length + 1,
          status: raw.status ?? 'done',
          detail: raw.detail ?? null,
          elapsed_ms: raw.elapsed_ms ?? null,
          artifact_id: raw.artifact_id ?? null,
          exec_mode: raw.exec_mode ?? 'serial',
          group_id: raw.group_id ?? null,
          branch_label: raw.branch_label ?? null,
          branch_note: raw.branch_note ?? null,
        })
      } else if (type === 'artifact' && (raw.artifact_id || raw.kind)) {
        artifacts.push({
          artifact_id: raw.artifact_id,
          kind: raw.kind ?? 'file',
          title: raw.title ?? raw.filename ?? '产物',
          seq: raw.seq ?? artifacts.length,
          mime_type: raw.mime_type ?? null,
          file_id: raw.file_id ?? null,
          chart_config: raw.chart_config ?? null,
          media_data: raw.media_data ?? null,
          size_bytes: raw.size_bytes ?? null,
          status: raw.status ?? 'ready',
          error: raw.error ?? null,
          suggestion: raw.suggestion ?? null,
        })
      } else if (type === 'thinking') {
        converted.push({
          type: 'thinking',
          time: raw.timestamp || new Date().toISOString(),
          message: raw.content || '',
          step: raw.step,
          title: raw.title,
          data: { agent_id: raw.agent_id, role_name: raw.role_name },
        })
      } else if (type === 'tool_call') {
        converted.push({ type: 'tool_call', time: raw.timestamp || new Date().toISOString(), message: raw.tool_name || '', data: { tool_name: raw.tool_name, parameters: raw.parameters || raw.input || {} } })
      } else if (type === 'tool_result' || type === 'tool_error') {
        converted.push({ type: 'tool_result', time: raw.timestamp || new Date().toISOString(), message: raw.tool_name || '', data: { tool_name: raw.tool_name, result: type === 'tool_error' ? (raw.error_message || 'Error') : (typeof raw.result === 'string' ? raw.result : JSON.stringify(raw.result)) } })
      } else if (type === 'progress') {
        converted.push({ type: 'progress', time: raw.timestamp || new Date().toISOString(), message: raw.message || raw.stage || '' })
      } else if (type === 'artifact') {
        converted.push({ type: 'artifact', time: raw.timestamp || new Date().toISOString(), message: raw.filename || raw.message || '' })
      } else if (type === 'model_call') {
        // 按 tool_call_id 聚合 leader 的答案 token 流
        const tcId = (raw.tool_call_id || (raw.metadata && raw.metadata.tool_call_id) || 'default') as string
        const c = typeof raw.content === 'string' ? raw.content : ''
        if (!mcMap[tcId]) {
          mcMap[tcId] = {
            content: '',
            time: raw.timestamp || new Date().toISOString(),
            role: raw.node_role || raw.role_name,
          }
        }
        mcMap[tcId].content += c
      }
    }
    // 将聚合后的 model_call 作为单条 tool_call 渲染（执行事件 Tab）
    for (const tcId of Object.keys(mcMap)) {
      const m = mcMap[tcId]
      if (!m.content) continue
      converted.push({
        type: 'tool_call',
        time: m.time,
        message: m.role ? `调用大模型（${m.role}）` : '调用大模型',
        data: { tool_name: '大模型', parameters: {}, content: m.content },
      })
    }
    internalEvents.value = converted
    internalSteps.value = steps.sort((a, b) => a.seq - b.seq)
    internalArtifacts.value = artifacts.sort((a, b) => a.seq - b.seq)
  } catch {
    // 加载失败时保持空列表
  } finally {
    internalLoading.value = false
  }
}

onMounted(() => {
  if (props.executionId && !props.events?.length) loadHistoricalEvents(props.executionId)
})

watch(() => props.executionId, (newId) => {
  if (newId && !props.events?.length) loadHistoricalEvents(newId)
})

const collapsed = ref(false)
const expandedExperts = reactive<Record<string, boolean>>({})
function toggleExpertExpand(key: string) { expandedExperts[key] = !expandedExperts[key] }
const expandedItems = reactive<Record<string, boolean>>({})
function toggleExpand(key: string) { expandedItems[key] = !expandedItems[key] }

const thinkingEvents = computed(() => allEvents.value.filter(e => e.type === 'thinking'))
const toolCallEvents = computed(() => allEvents.value.filter(e => e.type === 'tool_call'))
const toolResultEvents = computed(() => allEvents.value.filter(e => e.type === 'tool_result'))
const progressEvents = computed(() => allEvents.value.filter(e => e.type === 'progress'))
const artifactEvents = computed(() => allEvents.value.filter(e => e.type === 'artifact'))
const allToolEvents = computed(() => [...toolCallEvents.value, ...toolResultEvents.value])

/**
 * 思考过程按专家分组：团队模式下多名专家并行产出思考，
 * 按 agent_id（缺失时回退 role_name / 未知专家）聚合成每位专家一段内容。
 */
const expertGroups = computed<ExpertGroup[]>(() => {
  const evts = thinkingEvents.value
  if (!evts.length) return []
  const byAgent = new Map<string, ExpertGroup>()
  for (const e of evts) {
    const role = (e.data?.role_name as string) || ''
    const key = (e.data?.agent_id as string) || role || 'unknown'
    const existing = byAgent.get(key)
    if (existing) {
      existing.content += e.message || ''
      existing.count += 1
      if (role && existing.name === '未知专家') existing.name = role
    } else {
      byAgent.set(key, {
        key,
        name: role || (e.data?.agent_id as string) || '未知专家',
        content: e.message || '',
        count: 1,
        time: e.time,
      })
    }
  }
  return [...byAgent.values()]
})

const defaultTab = computed(() => {
  if (expertGroups.value.length) return 'thinking'
  if (toolCallEvents.value.length || progressEvents.value.length || artifactEvents.value.length) return 'events'
  if (finalSteps.value.length || finalArtifacts.value.length) return 'timeline'
  return 'thinking'
})

function formatTime(t?: string): string {
  if (!t) return ''
  return t.includes('T') ? t.slice(11, 19) : t.length > 8 ? t.slice(0, 8) : t
}

function formatJson(data: any): string {
  try {
    return typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}
</script>

<style scoped lang="less">
.team-execution-panel {
  margin-top: 8px;
}

.execution-events-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
  font-size: 12px;
  color: var(--ok);
  transition: color 0.2s;

  &:hover { color: #237804; }

  .expand-arrow {
    font-size: 10px;
    transition: transform 0.25s ease;
    color: #95de64;
  }
  .expand-arrow.expanded { transform: rotate(90deg); }
  .execution-icon { font-size: 13px; color: var(--ok); }
  .execution-label { font-weight: 500; font-size: 12px; }

  .exec-expert-indicator {
    font-size: 10px;
    color: var(--ok);
    background: rgba(82, 196, 26, 0.1);
    border-radius: 3px;
    padding: 0 5px;
  }

  .exec-running-indicator {
    margin-left: auto;
    font-size: 11px;
    color: #95de64;
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.execution-events-body {
  margin-top: 6px;
  padding: 8px 0 8px 12px;
  background: rgba(82, 196, 26, 0.03);
  border-left: 2px solid #b7eb8f;
  border-radius: 0 6px 6px 0;
  font-size: 12px;

  :deep(.ant-tabs-tabpane) {
    max-height: 300px;
    overflow-y: auto;
    padding-right: 4px;
  }

  :deep(.timeline-pane) {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
}

.exec-section {
  & + .exec-section {
    margin-top: 8px;
    padding-top: 6px;
    border-top: 1px dashed var(--ok-soft);
  }

  .exec-section-header {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    color: var(--fg-secondary);
    margin-bottom: 4px;
  }

  .exec-item {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 2px 0;
    line-height: 1.5;
  }

  .exec-time {
    color: var(--fg-muted);
    font-size: 10px;
    flex-shrink: 0;
    min-width: 56px;
    font-family: monospace;
  }

  .exec-icon-badge {
    font-size: 10px;
    padding: 0 4px;
    border-radius: 3px;
    flex-shrink: 0;
    line-height: 18px;

    &.call { background: var(--warn-soft); color: var(--accent-2); border: 1px solid #ffd591; }
    &.result { background: var(--ok-soft); color: var(--ok); border: 1px solid #b7eb8f; }
  }

  .exec-text {
    color: #595959;
    word-break: break-all;
    white-space: pre-wrap;
    &.progress-text { color: var(--accent); }
  }

  .exec-tool-entry { align-items: center; }
  .exec-tool-name { font-weight: 500; color: #262626; font-family: monospace; font-size: 12px; }

  .exec-tool-params {
    margin: 2px 0 2px 62px;

    .exec-params-toggle {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      cursor: pointer;
      font-size: 11px;
      color: var(--fg-secondary);
      padding: 2px 6px;
      border-radius: 3px;
      background: var(--bg-input);
      transition: background 0.2s;

      &:hover { background: var(--border); }
      .anticon { font-size: 9px; transition: transform 0.2s; }
      .expanded { transform: rotate(90deg); }
    }

    .exec-params-json {
      margin: 4px 0 0;
      padding: 6px 8px;
      background: #f6f8fa;
      border-radius: 4px;
      font-size: 11px;
      line-height: 1.4;
      color: #262626;
      overflow-x: auto;
      max-height: 200px;
      overflow-y: auto;
      white-space: pre;
    }
  }

  .exec-tool-result {
    margin: 2px 0 2px 62px;

    .exec-result-text {
      font-size: 11px;
      color: #595959;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-all;

      &.truncated {
        max-height: 60px;
        overflow: hidden;
        mask-image: linear-gradient(to bottom, black 40%, transparent 100%);
        -webkit-mask-image: linear-gradient(to bottom, black 40%, transparent 100%);
      }
    }

    .exec-result-toggle {
      font-size: 11px;
      color: var(--accent);
      cursor: pointer;
      &:hover { color: #40a9ff; }
    }
  }
}

/* 思考过程：按专家分组卡片 */
.expert-group-list {
  display: flex;
  flex-direction: column;
  gap: 6px;

  .expert-card {
    background: rgba(114, 46, 209, 0.04);
    border: 1px solid rgba(114, 46, 209, 0.1);
    border-radius: 6px;
    padding: 6px 10px;

    .expert-head {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      cursor: pointer;
      user-select: none;
    }

    .expert-arrow {
      font-size: 9px;
      color: #b37feb;
      transition: transform 0.2s;
      &.expanded { transform: rotate(90deg); }
    }

    .expert-avatar {
      font-size: 12px;
      color: var(--fg-inverse);
      background: #b37feb;
      border-radius: 50%;
      width: 16px;
      height: 16px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .expert-name {
      font-size: 12px;
      color: #531dab;
      font-weight: 600;
      flex: 1;
      min-width: 0;
      word-break: break-word;
    }

    .expert-count {
      font-size: 10px;
      color: #9254de;
      background: rgba(114, 46, 209, 0.08);
      border-radius: 3px;
      padding: 0 4px;
      flex-shrink: 0;
    }

    .expert-time {
      font-size: 10px;
      color: #b37feb;
      font-family: monospace;
      flex-shrink: 0;
    }

    .expert-content {
      font-size: 12px;
      color: #722ed1;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      margin-top: 4px;
      max-height: 260px;
      overflow-y: auto;
    }
  }
}

.exec-empty {
  text-align: center;
  color: var(--fg-muted);
  font-size: 12px;
  padding: 16px 0;
}
</style>
