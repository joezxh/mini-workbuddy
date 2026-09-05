<!--
  DeepResearchExecutionPanel.vue — 深度研究模式执行详情面板（独立组件，不复用 SkillExecutionPanel）

  与 SkillExecutionPanel 展示结构对齐（思考过程 / 执行事件 / 时间线三个 Tab + 结果正文在下），
  实现完全独立，便于后续做深度研究专属的个性化展示（检索来源图谱、证据可信度矩阵等）。

  与思考模式的差异：思考过程 = 研究流水线阶段（计划拆解 / 来源检索 / 阶段进展），
  并在思考过程 Tab 底部追加「引用来源」清单（标题 + 链接 + 可信度）。
-->
<template>
  <div class="research-execution-panel">
    <div class="execution-events-header" @click="collapsed = !collapsed">
      <CaretRightOutlined class="expand-arrow" :class="{ expanded: !collapsed }" />
      <FileSearchOutlined class="execution-icon" />
      <span class="execution-label">深度研究</span>
      <a-badge :count="allEvents.length" :number-style="{ backgroundColor: 'var(--info)', fontSize: '10px' }" />
      <span v-if="sourceList.length" class="exec-source-indicator">{{ sourceList.length }} 个来源</span>
      <span v-if="streaming" class="exec-running-indicator"><LoadingOutlined spin /> 研究中...</span>
    </div>
    <div v-if="!collapsed" class="execution-events-body" :class="{ 'full-mode': full }">
      <div v-if="internalLoading" class="exec-empty"><LoadingOutlined spin /> 加载中...</div>
      <a-tabs v-else size="small" :default-active-key="defaultTab">
        <!-- Tab 1: 思考过程（研究流水线） -->
        <a-tab-pane key="thinking">
          <template #tab>
            <BulbOutlined style="color: #722ed1" />
            <span>思考过程</span>
            <a-badge
              v-if="displayThinkingSteps.length"
              :count="displayThinkingSteps.length"
              :number-style="{ backgroundColor: '#b37feb', fontSize: '10px', marginLeft: '4px' }"
            />
          </template>
          <div v-if="displayThinkingSteps.length" class="thinking-steps-list">
            <div v-for="s in displayThinkingSteps" :key="s.step" class="thinking-step-card">
              <div class="thinking-step-head" @click="toggleStepExpand(s.step)">
                <CaretRightOutlined class="step-arrow" :class="{ expanded: expandedSteps[s.step] }" />
                <span class="thinking-step-no">步骤 {{ s.step }}</span>
                <span class="thinking-step-title">{{ s.title }}</span>
                <span class="thinking-time">{{ formatTime(s.time) }}</span>
              </div>
              <div v-show="expandedSteps[s.step]" class="thinking-content" :class="{ 'full-content': full }">{{ s.content }}</div>
            </div>
          </div>
          <!-- 引用来源清单（深度研究专属） -->
          <div v-if="sourceList.length" class="research-sources">
            <div class="exec-section-header">
              <LinkOutlined style="color: var(--info)" /><span>引用来源（{{ sourceList.length }}）</span>
            </div>
            <div v-for="(s, i) in sourceList" :key="'src' + i" class="source-item">
              <span class="source-index">{{ i + 1 }}</span>
              <a v-if="s.url" :href="s.url" target="_blank" rel="noopener" class="source-title">{{ s.title || s.url }}</a>
              <span v-else class="source-title">{{ s.title || '未命名来源' }}</span>
              <span v-if="s.credibility != null" class="source-cred">可信度 {{ Math.round(Number(s.credibility) * 100) }}%</span>
            </div>
          </div>
          <div v-if="!displayThinkingSteps.length && !sourceList.length" class="exec-empty">暂无研究记录</div>
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
                <div class="exec-result-text" :class="{ truncated: !expandedItems[`r_${idx}`] && !full }">{{ evt.data.result }}</div>
                <a v-if="String(evt.data.result).length > 150 && !full" class="exec-result-toggle" @click="toggleExpand(`r_${idx}`)">{{ expandedItems[`r_${idx}`] ? '收起' : '展开' }}</a>
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
        <!-- Tab 3: 时间线 -->
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
  FileSearchOutlined, LinkOutlined,
} from '@ant-design/icons-vue'
import type { ExecutionEvent } from '@/types/shared'
import { getUnifiedEvents } from '@/api/agentExecution'
import TimelineFlowPlayer from './TimelineFlowPlayer.vue'

interface ThinkingStepLike {
  step: number
  title: string
  content: string
  time?: string
}

interface ResearchSource {
  title?: string
  url?: string
  credibility?: number
}

const props = defineProps<{
  events?: ExecutionEvent[]
  streaming?: boolean
  executionId?: string | null
  thinkingSteps?: ThinkingStepLike[]
  /** 研究引用来源（历史回放由 extra_data.research_report.sources 还原） */
  sources?: ResearchSource[]
  unifiedSteps?: any[]
  unifiedArtifacts?: any[]
  /**
   * 全量展示模式：取消各视图的高度限制与默认折叠，完整呈现该任务的
   * 全部思考过程 / 执行事件 / 时间线，便于「跳转查看」时追溯完整执行链路。
   * 默认为 false（会话内联实时面板沿用紧凑展示）。
   */
  full?: boolean
}>()

const internalEvents = ref<ExecutionEvent[]>([])
const internalLoading = ref(false)
const internalSteps = ref<any[]>([])
const internalArtifacts = ref<any[]>([])
const internalSources = ref<ResearchSource[]>([])

const allEvents = computed(() => (props.events?.length ? props.events : internalEvents.value))
const finalSteps = computed(() => (props.unifiedSteps?.length ? props.unifiedSteps : internalSteps.value))
const finalArtifacts = computed(() => (props.unifiedArtifacts?.length ? props.unifiedArtifacts : internalArtifacts.value))
/** 引用来源：优先外部传入，否则取历史接口还原的 */
const sourceList = computed<ResearchSource[]>(() =>
  props.sources?.length ? props.sources : internalSources.value
)

/** 从 API 加载历史执行事件（深度研究模式统一回放接口 /agent-execution/{id}/unified-events） */
async function loadHistoricalEvents(executionId: string) {
  internalLoading.value = true
  try {
    const data = await getUnifiedEvents(executionId)
    const rawSteps = data.steps || []
    const rawArtifacts = data.artifacts || []
    const converted: ExecutionEvent[] = []
    const steps: any[] = []
    const artifacts: any[] = []
    let sourceSeq = 0
    for (const raw of rawSteps) {
      const et = raw.event_type as string | undefined
      // unified-events 的 step 结构：{seq, type, phase, title, detail, status, elapsed_ms, ...}
      if (et === 'engine_decision') {
        // 引擎决策：归入执行事件（progress）
        converted.push({ type: 'progress', time: raw.timestamp || '', message: `[${raw.phase || '引擎'}] ${raw.title || raw.detail || ''}` })
        continue
      }
      if (et === 'llm_think') {
        converted.push({
          type: 'thinking',
          time: raw.timestamp || '',
          message: raw.detail || raw.title || '',
          step: raw.seq,
          title: raw.title || `步骤 ${raw.seq}`,
        })
      } else if (et === 'model_call') {
        converted.push({ type: 'tool_call', time: raw.timestamp || '', message: raw.title || '调用大模型', data: { tool_name: raw.title || 'model_call', parameters: {} } })
      } else if (et === 'progress') {
        converted.push({ type: 'progress', time: raw.timestamp || '', message: raw.title || raw.detail || '' })
      } else if (et === 'research_plan') {
        converted.push({ type: 'thinking', time: raw.timestamp || '', message: raw.title || raw.detail || '', step: raw.seq, title: raw.title || '研究计划' })
      } else if (et === 'run_start') {
        converted.push({ type: 'progress', time: raw.timestamp || '', message: raw.title || '启动' })
      } else if (et === 'artifact') {
        converted.push({ type: 'artifact', time: raw.timestamp || '', message: raw.title || raw.detail || '产物' })
      } else {
        // 兜底：作为执行步骤/进度展示
        converted.push({ type: 'progress', time: raw.timestamp || '', message: raw.title || raw.detail || '' })
      }
      // 结构化 step（供时间线 Tab 使用）
      steps.push({
        phase: raw.phase ?? '执行',
        event_type: et ?? 'step',
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
    }
    for (const a of rawArtifacts) {
      artifacts.push({
        artifact_id: a.artifact_id,
        kind: a.kind ?? 'file',
        title: a.title ?? a.filename ?? '产物',
        seq: a.seq ?? sourceSeq++,
        mime_type: a.mime_type ?? null,
        file_id: a.file_id ?? null,
        filename: a.filename ?? null,
        chart_config: a.chart_config ?? null,
        media_data: a.media_data ?? null,
        size_bytes: a.size_bytes ?? null,
        status: a.status ?? 'ready',
        error: a.error ?? null,
        suggestion: a.suggestion ?? null,
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
const expandedSteps = reactive<Record<number, boolean>>({})
function toggleStepExpand(step: number) { expandedSteps[step] = !expandedSteps[step] }
const expandedItems = reactive<Record<string, boolean>>({})
function toggleExpand(key: string) { expandedItems[key] = !expandedItems[key] }

const thinkingEvents = computed(() => allEvents.value.filter(e => e.type === 'thinking'))
const toolCallEvents = computed(() => allEvents.value.filter(e => e.type === 'tool_call'))
const toolResultEvents = computed(() => allEvents.value.filter(e => e.type === 'tool_result'))
const progressEvents = computed(() => allEvents.value.filter(e => e.type === 'progress'))
const artifactEvents = computed(() => allEvents.value.filter(e => e.type === 'artifact'))
const allToolEvents = computed(() => [...toolCallEvents.value, ...toolResultEvents.value])

/** 从扁平事件流按 step 聚合研究阶段（append 增量语义） */
const aggregatedSteps = computed<ThinkingStepLike[]>(() => {
  const evts = thinkingEvents.value
  if (!evts.length) return []
  const byStep = new Map<number, ThinkingStepLike>()
  for (const e of evts) {
    const step = e.step
    if (step == null) continue
    const existing = byStep.get(step)
    if (existing) {
      existing.content += e.message || ''
      if (e.title) existing.title = e.title
    } else {
      byStep.set(step, { step, title: e.title || `步骤 ${step}`, content: e.message || '', time: e.time })
    }
  }
  return [...byStep.values()].sort((a, b) => a.step - b.step)
})

const displayThinkingSteps = computed<ThinkingStepLike[]>(() => {
  if (props.thinkingSteps?.length) return props.thinkingSteps
  return aggregatedSteps.value
})

const defaultTab = computed(() => {
  if (displayThinkingSteps.value.length) return 'thinking'
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
.research-execution-panel {
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
  color: #08979c;
  transition: color 0.2s;

  &:hover { color: #006d75; }

  .expand-arrow {
    font-size: 10px;
    transition: transform 0.25s ease;
    color: #5cdbd3;
  }
  .expand-arrow.expanded { transform: rotate(90deg); }
  .execution-icon { font-size: 13px; color: var(--info); }
  .execution-label { font-weight: 500; font-size: 12px; }

  .exec-source-indicator {
    font-size: 10px;
    color: #08979c;
    background: rgba(19, 194, 194, 0.1);
    border-radius: 3px;
    padding: 0 5px;
  }

  .exec-running-indicator {
    margin-left: auto;
    font-size: 11px;
    color: #5cdbd3;
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.execution-events-body {
  margin-top: 6px;
  padding: 8px 0 8px 12px;
  background: rgba(19, 194, 194, 0.03);
  border-left: 2px solid #87e8de;
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

  /* 全量展示模式：取消各视图高度限制，完整呈现任务执行链路 */
  &.full-mode {
    :deep(.ant-tabs-tabpane) {
      max-height: none;
      overflow: visible;
    }

    .thinking-content.full-content {
      max-height: none;
      overflow: visible;
    }
  }
}

.exec-section {
  & + .exec-section {
    margin-top: 8px;
    padding-top: 6px;
    border-top: 1px dashed #e6fffb;
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

/* 研究阶段：分步卡片 */
.thinking-steps-list {
  display: flex;
  flex-direction: column;
  gap: 6px;

  .thinking-step-card {
    background: rgba(114, 46, 209, 0.04);
    border: 1px solid rgba(114, 46, 209, 0.1);
    border-radius: 6px;
    padding: 6px 10px;

    .thinking-step-head {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      cursor: pointer;
      user-select: none;
    }

    .step-arrow {
      font-size: 9px;
      color: #b37feb;
      transition: transform 0.2s;
      &.expanded { transform: rotate(90deg); }
    }

    .thinking-step-no {
      font-size: 10px;
      color: var(--fg-inverse);
      background: #b37feb;
      border-radius: 3px;
      padding: 0 5px;
      flex-shrink: 0;
    }

    .thinking-step-title {
      font-size: 12px;
      color: #531dab;
      font-weight: 600;
      flex: 1;
      min-width: 0;
      word-break: break-word;
    }

    .thinking-time {
      font-size: 10px;
      color: #b37feb;
      font-family: monospace;
      flex-shrink: 0;
    }

    .thinking-content {
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

/* 引用来源清单（深度研究专属） */
.research-sources {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #e6fffb;

  .source-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 0;
    font-size: 11px;

    .source-index {
      flex-shrink: 0;
      width: 16px;
      height: 16px;
      line-height: 16px;
      text-align: center;
      border-radius: 3px;
      background: rgba(19, 194, 194, 0.12);
      color: #08979c;
      font-size: 10px;
    }

    .source-title {
      flex: 1;
      min-width: 0;
      color: #08979c;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-decoration: none;

      &:hover { text-decoration: underline; }
    }

    .source-cred {
      flex-shrink: 0;
      font-size: 10px;
      color: var(--fg-secondary);
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
