<!--
  SkillExecutionPanel.vue — Skill 模式执行详情面板（Tab 标签页）

  与 MediatorPanel / MediationDialogue 的执行详情面板 UI 完全对齐：
  - Tab 1「思考过程」：合并同一 thinking 块的所有增量事件为单一段落
  - Tab 2「执行事件」：工具调用（参数可折叠）+ 进度信息 + 产物

  流式阶段与完成阶段使用同一组件，确保视觉一致性。
-->
<template>
  <div class="skill-execution-panel">
    <div class="execution-events-header" @click="collapsed = !collapsed">
      <CaretRightOutlined class="expand-arrow" :class="{ expanded: !collapsed }" />
      <ThunderboltOutlined class="execution-icon" />
      <span class="execution-label">执行详情</span>
      <a-badge :count="allEvents.length" :number-style="{ backgroundColor: '#722ed1', fontSize: '10px' }" />
      <span v-if="streaming" class="exec-running-indicator"><LoadingOutlined spin /> 运行中...</span>
    </div>
    <div v-if="!collapsed" class="execution-events-body">
      <div v-if="internalLoading" class="exec-empty"><LoadingOutlined spin /> 加载中...</div>
      <a-tabs v-else size="small" :default-active-key="defaultTab">
        <!-- Tab 1: 思考过程（思考模式：按步骤分块；技能模式：合并为单段） -->
        <a-tab-pane key="thinking">
          <template #tab>
            <BulbOutlined style="color: #722ed1" />
            <span>思考过程</span>
          </template>
          <!-- 思考模式：每个 thinking 事件是一个带序号/标题的独立推理步骤 -->
          <div v-if="thinkingSteps.length" class="thinking-steps-list">
            <div v-for="s in thinkingSteps" :key="s.step" class="thinking-step-card">
              <div class="thinking-step-head">
                <span class="thinking-step-no">步骤 {{ s.step }}</span>
                <span class="thinking-step-title">{{ s.title }}</span>
                <span class="thinking-time">{{ formatTime(s.time) }}</span>
              </div>
              <div class="thinking-content">{{ s.content }}</div>
            </div>
          </div>
          <!-- 技能模式：同一 thinking 块的所有增量合并为单一段落 -->
          <div v-else-if="mergedThinking" class="thinking-merged-card">
            <span class="thinking-time">{{ formatTime(mergedThinking.time) }}</span>
            <div class="thinking-content">{{ mergedThinking.content }}</div>
          </div>
          <div v-else class="exec-empty">暂无思考记录</div>
        </a-tab-pane>
        <!-- Tab 2: 执行事件 -->
        <a-tab-pane key="events">
          <template #tab>
            <ToolOutlined style="color: #fa8c16" />
            <span>执行事件</span>
          </template>
            <!-- 工具调用 -->
            <div v-if="toolCallEvents.length || toolResultEvents.length" class="exec-section">
              <div class="exec-section-header"><ToolOutlined style="color: #fa8c16" /><span>工具调用</span></div>
              <template v-for="(evt, idx) in allToolEvents" :key="'tc' + idx">
                <div class="exec-item exec-tool-entry">
                  <span class="exec-time">{{ formatTime(evt.time) }}</span>
                  <span class="exec-icon-badge" :class="evt.type === 'tool_call' ? 'call' : 'result'">{{ evt.type === 'tool_call' ? '调用' : '结果' }}</span>
                  <span class="exec-tool-name">{{ evt.data?.tool_name || evt.message }}</span>
                </div>
                <div v-if="evt.type === 'tool_call' && evt.data?.parameters" class="exec-tool-params">
                  <div class="exec-params-toggle" @click="toggleExpand(`p_${idx}`)">
                    <CaretRightOutlined :class="{ expanded: expandedItems[`p_${idx}`] }" /><span>参数</span>
                  </div>
                  <pre v-if="expandedItems[`p_${idx}`]" class="exec-params-json">{{ formatJson(evt.data.parameters) }}</pre>
                </div>
                <div v-if="evt.type === 'tool_result' && evt.data?.result" class="exec-tool-result">
                  <div class="exec-result-text" :class="{ truncated: !expandedItems[`r_${idx}`] }">{{ evt.data.result }}</div>
                  <a v-if="(evt.data.result as string).length > 150" class="exec-result-toggle" @click="toggleExpand(`r_${idx}`)">{{ expandedItems[`r_${idx}`] ? '收起' : '展开' }}</a>
                </div>
              </template>
            </div>
            <!-- 进度信息 -->
            <div v-if="progressEvents.length" class="exec-section">
              <div class="exec-section-header"><LoadingOutlined style="color: #1890ff" /><span>执行步骤</span></div>
              <div v-for="(evt, idx) in progressEvents" :key="'p' + idx" class="exec-item">
                <span class="exec-time">{{ formatTime(evt.time) }}</span>
                <span class="exec-text progress-text">{{ evt.message }}</span>
              </div>
            </div>
            <!-- 产物 -->
            <div v-if="artifactEvents.length" class="exec-section">
              <div class="exec-section-header"><FileOutlined style="color: #13c2c2" /><span>生成产物</span></div>
              <div v-for="(evt, idx) in artifactEvents" :key="'a' + idx" class="exec-item">
                <span class="exec-time">{{ formatTime(evt.time) }}</span>
                <span class="exec-text">{{ evt.message }}</span>
              </div>
            </div>
            <div v-if="!toolCallEvents.length && !progressEvents.length && !artifactEvents.length" class="exec-empty">
              暂无执行事件记录
            </div>
        </a-tab-pane>
        <!-- Tab 3: 时间线（metaso 风格动态流程图：节点按序点亮 + 底部事件横轴 + 播放控制） -->
        <a-tab-pane key="timeline" class="timeline-pane">
          <template #tab>
            <HistoryOutlined style="color: #13c2c2" />
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
  CaretRightOutlined, ThunderboltOutlined, LoadingOutlined,
  BulbOutlined, ToolOutlined, FileOutlined, HistoryOutlined,
} from '@ant-design/icons-vue'
import type { ExecutionEvent } from '@/types/shared'
import { getToken } from '@/utils/auth'
import TimelineFlowPlayer from './TimelineFlowPlayer.vue'

const props = defineProps<{
  /** 扁平执行事件列表（流式阶段直接传入） */
  events?: ExecutionEvent[]
  /** 是否处于流式传输中 */
  streaming?: boolean
  /** 执行 ID（完成消息场景，用于加载历史事件） */
  executionId?: string | null
  /** 统一时间线步骤（归一化 step 形状，来自 unified-events 接口或实时收集） */
  unifiedSteps?: any[]
  /** 统一时间线产物 */
  unifiedArtifacts?: any[]
}>()

// ── 内部事件收集（支持 executionId 加载历史 + 流式追加） ──
const internalEvents = ref<ExecutionEvent[]>([])
const internalLoading = ref(false)
/** 历史回放时从落库事件还原的统一时间线步骤 / 产物 */
const internalSteps = ref<any[]>([])
const internalArtifacts = ref<any[]>([])

/** 合并外部 events 和 internalEvents */
const allEvents = computed(() => {
  if (props.events?.length) return props.events
  return internalEvents.value
})

/** 时间线步骤：优先使用父组件传入的实时数据，否则回退到历史接口还原的数据 */
const finalSteps = computed(() =>
  props.unifiedSteps?.length ? props.unifiedSteps : internalSteps.value,
)
/** 时间线产物：优先使用父组件传入的实时数据，否则回退到历史接口还原的数据 */
const finalArtifacts = computed(() =>
  props.unifiedArtifacts?.length ? props.unifiedArtifacts : internalArtifacts.value,
)

/** 从 API 加载历史执行事件 */
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
    // 将后端原始事件转换为 ExecutionEvent 格式
    const converted: ExecutionEvent[] = []
    const steps: any[] = []
    const artifacts: any[] = []
    for (const raw of rawEvents) {
      const type = raw.type as string
      if (type === 'step') {
        // 归一化步骤事件（Emitter.emit_step 已落库）：还原为时间线条目，
        // 此前该分支缺失，导致刷新/回放时时间线 Tab 恒为「暂无时间线记录」
        steps.push({
          phase: raw.phase ?? '执行',
          event_type: raw.event_type ?? 'step',
          title: raw.title ?? '',
          seq: raw.seq ?? steps.length + 1,
          status: raw.status ?? 'done',
          detail: raw.detail ?? null,
          elapsed_ms: raw.elapsed_ms ?? null,
          artifact_id: raw.artifact_id ?? null,
          // 工作流执行形式（并行分支/判断节点），供横向流程图渲染
          exec_mode: raw.exec_mode ?? 'serial',
          group_id: raw.group_id ?? null,
          branch_label: raw.branch_label ?? null,
          branch_note: raw.branch_note ?? null,
        })
        // 同时归一化为执行事件，使回放时「执行事件」Tab 也能看到时间线步骤
        // （与实时流 processEvent 的 step 分支对齐）
        converted.push({
          type: 'step',
          time: raw.timestamp || new Date().toISOString(),
          message: raw.title || raw.event_type || '',
          phase: raw.phase,
          eventType: raw.event_type,
          seq: raw.seq,
          status: raw.status,
          detail: raw.detail,
          elapsedMs: raw.elapsed_ms,
        })
      } else if (type === 'artifact' && (raw.artifact_id || raw.kind)) {
        // 归一化产物事件（ArtifactItem 归一化形状）
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
        converted.push({ type: 'thinking', time: raw.timestamp || new Date().toISOString(), message: raw.content || '' })
      } else if (type === 'tool_call') {
        converted.push({ type: 'tool_call', time: raw.timestamp || new Date().toISOString(), message: raw.tool_name || '', data: { tool_name: raw.tool_name, parameters: raw.parameters || raw.input || {} } })
      } else if (type === 'tool_result' || type === 'tool_error') {
        converted.push({ type: 'tool_result', time: raw.timestamp || new Date().toISOString(), message: raw.tool_name || '', data: { tool_name: raw.tool_name, result: type === 'tool_error' ? (raw.error_message || 'Error') : (typeof raw.result === 'string' ? raw.result : JSON.stringify(raw.result)) } })
      } else if (type === 'progress') {
        converted.push({ type: 'progress', time: raw.timestamp || new Date().toISOString(), message: raw.message || raw.stage || '' })
      } else if (type === 'artifact') {
        converted.push({ type: 'artifact', time: raw.timestamp || new Date().toISOString(), message: raw.filename || raw.message || '' })
      }
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
  if (props.executionId && !props.events?.length) {
    loadHistoricalEvents(props.executionId)
  }
})

// executionId 变化时重新加载
watch(() => props.executionId, (newId) => {
  if (newId && !props.events?.length) {
    loadHistoricalEvents(newId)
  }
})

/** 面板是否折叠 */
const collapsed = ref(false)

/** 默认激活 Tab：思考 > 执行事件 > 时间线 */
const defaultTab = computed(() => {
  // 思考模式分步推理 / 技能模式合并思考块，均优先落到「思考过程」Tab
  if (thinkingSteps.value.length || mergedThinking.value) return 'thinking'
  // 仅当没有任何常规执行事件时，才把默认 Tab 落到时间线（避免改变既有默认行为）
  if (toolCallEvents.value.length || progressEvents.value.length || artifactEvents.value.length) return 'events'
  if (finalSteps.value.length || finalArtifacts.value.length) return 'timeline'
  return 'events'
})

/** 展开/折叠状态（工具参数、工具结果） */
const expandedItems = reactive<Record<string, boolean>>({})
function toggleExpand(key: string) { expandedItems[key] = !expandedItems[key] }

// ── 事件分类 ────────────────────────────────────────────
const thinkingEvents = computed(() => allEvents.value.filter(e => e.type === 'thinking'))
const toolCallEvents = computed(() => allEvents.value.filter(e => e.type === 'tool_call'))
const toolResultEvents = computed(() => allEvents.value.filter(e => e.type === 'tool_result'))
const progressEvents = computed(() => allEvents.value.filter(e => e.type === 'progress'))
const artifactEvents = computed(() => allEvents.value.filter(e => e.type === 'artifact'))
/** 时间线步骤事件（SSE `type=step` 归一化，与「时间线」Tab 互补展示于执行事件 Tab） */
const stepEvents = computed(() =>
  [...allEvents.value.filter(e => e.type === 'step')].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0)),
)

/** 工具调用 + 结果交错排列（与 MediationDialogue 对齐） */
const allToolEvents = computed(() => [...toolCallEvents.value, ...toolResultEvents.value])

// ── Thinking 合并 ────────────────────────────────────────
/** 将同一 thinking 块的所有增量事件合并为单一段落，仅保留开始时间戳（技能模式） */
const mergedThinking = computed<{ time: string; content: string } | null>(() => {
  const evts = thinkingEvents.value
  if (!evts.length) return null
  return {
    time: evts[0].time,
    content: evts.map(e => e.message).join(''),
  }
})

/**
 * 思考模式的推理步骤列表：当 thinking 事件携带 step 序号时（思考模式），
 * 按步骤分块展示；技能模式事件无 step 字段，返回空数组，回退到合并展示。
 */
const thinkingSteps = computed<Array<{ step: number; title: string; content: string; time: string }>>(() => {
  const evts = thinkingEvents.value
  if (!evts.length) return []
  // 按 step 聚合同一步骤的多个增量分片（幂等覆盖 + 增量拼接）
  const byStep = new Map<number, { step: number; title: string; content: string; time: string }>()
  for (const e of evts) {
    const step = e.step
    if (step == null) {
      // 增量块模式（技能模式）不参与分步展示
      return []
    }
    const existing = byStep.get(step)
    if (existing) {
      existing.content += e.message || ''
      if (e.title) existing.title = e.title
    } else {
      byStep.set(step, {
        step,
        title: e.title || `步骤 ${step}`,
        content: e.message || '',
        time: e.time,
      })
    }
  }
  return [...byStep.values()].sort((a, b) => a.step - b.step)
})

// ── 工具函数 ────────────────────────────────────────────
function formatTime(t: string): string {
  if (!t) return ''
  // 仅显示 HH:mm:ss 部分
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
.skill-execution-panel {
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
  color: #722ed1;
  transition: color 0.2s;

  &:hover { color: #531dab; }

  .expand-arrow {
    font-size: 10px;
    transition: transform 0.25s ease;
    color: #b37feb;
  }
  .expand-arrow.expanded { transform: rotate(90deg); }

  .execution-icon { font-size: 13px; color: #722ed1; }
  .execution-label { font-weight: 500; font-size: 12px; }

  .exec-running-indicator {
    margin-left: auto;
    font-size: 11px;
    color: #b37feb;
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.execution-events-body {
  margin-top: 6px;
  padding: 8px 0 8px 12px;
  background: rgba(114, 46, 209, 0.03);
  border-left: 2px solid #d3adf7;
  border-radius: 0 6px 6px 0;
  font-size: 12px;

  // 三个 Tab（思考过程 / 执行事件 / 时间线）统一固定高度 + 滚动条，
  // 与「思考过程」卡片的高度约束保持一致，避免超长内容撑高窗体。
  :deep(.ant-tabs-tabpane) {
    max-height: 300px;
    overflow-y: auto;
    padding-right: 4px;
  }

  // 时间线 Tab：播放器自带固定高度与内部滚动，禁用 tabpane 滚动避免双滚动条
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
    border-top: 1px dashed #f0e6ff;
  }

  .exec-section-header {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    color: #8c8c8c;
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
    color: #bbb;
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

    &.call { background: #fff7e6; color: #fa8c16; border: 1px solid #ffd591; }
    &.result { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
    &.think { background: rgba(114, 46, 209, 0.08); color: #722ed1; border: 1px solid #d3adf7; }
  }

  .thinking-text {
    color: #722ed1 !important;
    font-style: italic;
    line-height: 1.6;
  }

  .step-text {
    color: #595959;
    .exec-step-phase { color: #13c2c2; font-weight: 500; }
    .exec-step-elapsed { color: #bfbfbf; font-size: 10px; margin-left: 4px; }
  }

  .exec-text {
    color: #595959;
    word-break: break-all;
    white-space: pre-wrap;
    &.progress-text { color: #1890ff; }
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
      color: #8c8c8c;
      padding: 2px 6px;
      border-radius: 3px;
      background: #fafafa;
      transition: background 0.2s;

      &:hover { background: #f0f0f0; }

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
      color: #1890ff;
      cursor: pointer;
      &:hover { color: #40a9ff; }
    }
  }
}

/* 思考过程合并卡片 */
.thinking-merged-card {
  background: rgba(114, 46, 209, 0.04);
  border: 1px solid rgba(114, 46, 209, 0.1);
  border-radius: 6px;
  padding: 8px 12px;

  .thinking-time {
    font-size: 10px;
    color: #b37feb;
    font-family: monospace;
  }

  .thinking-content {
    font-size: 12px;
    color: #722ed1;
    font-style: italic;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 300px;
    overflow-y: auto;
    margin-top: 4px;
  }
}

/* 思考模式：分步推理卡片列表 */
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
    }

    .thinking-step-no {
      font-size: 10px;
      color: #fff;
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
      margin-top: 3px;
    }
  }
}

/* 空状态 */
.exec-empty {
  text-align: center;
  color: #bfbfbf;
  font-size: 12px;
  padding: 16px 0;
}
</style>
