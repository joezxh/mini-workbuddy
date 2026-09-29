<script setup lang="ts">
/**
 * SOPRenderer —— SOP 模式的里程碑编排壳。
 *
 * spec: docs/design/sop-assistant-mode-design.md §6.3
 *
 * 职责边界：只做「里程碑视图 + 人工验收入口」，不重复实现时间线滚动播放
 * （统一时间线由 TimelineFlowPlayer 负责）。
 *
 * 数据来源两条，优先取结构化运行状态：
 * 1. `sopRun.steps`（后端 SOPRunState，含 attempt / 验收反馈，刷新恢复后仍在）
 * 2. `unifiedSteps`（SSE step 事件聚合，按 seq 去重取末态）
 */
import { computed, ref } from 'vue'
import type {
  ChatMessage, SopStepState, UnifiedArtifact, UnifiedStep,
} from '../../types'

const props = defineProps<{
  executionId?: string
  streaming?: boolean
  sopRun?: ChatMessage['sopRun']
  sopHandover?: Array<{ from: string; content: string }>
  unifiedSteps?: UnifiedStep[]
  unifiedArtifacts?: UnifiedArtifact[]
}>()

const emit = defineEmits<{
  (e: 'verify', payload: { stepIndex: number; confirmed: boolean; message: string }): void
}>()

interface Milestone {
  index: number
  subject: string
  phase: string
  attempt: number
  maxAttempts: number
  verifierType: string
  feedback: string | null
  goalIter: number
}

/** SSE step.status（前端枚举）→ 后端 SOPPhase */
const STATUS_TO_PHASE: Record<string, string> = {
  pending: 'PENDING',
  running: 'RUNNING',
  awaiting: 'AWAITING',
  done: 'COMPLETED',
  failed: 'FAILED',
  warn: 'RUNNING',
}

const PHASE_LABEL: Record<string, string> = {
  PENDING: '待执行',
  RUNNING: '执行中',
  AWAITING: '待验收',
  COMPLETED: '已完成',
  FAILED: '失败',
}

const milestones = computed<Milestone[]>(() => {
  const run = props.sopRun
  if (run?.steps?.length) {
    return run.steps.map((s: SopStepState) => ({
      index: s.index,
      subject: s.subject,
      phase: s.phase,
      attempt: s.attempt,
      maxAttempts: s.max_attempts,
      verifierType: s.verifier_type,
      feedback: s.feedback ?? null,
      goalIter: s.goal_iter ?? 0,
    }))
  }

  // 回退：按 seq 聚合 SSE 步骤事件，同一步取最后一条（末态）
  const bySeq = new Map<number, Milestone>()
  for (const st of props.unifiedSteps || []) {
    bySeq.set(st.seq ?? 0, {
      index: st.seq ?? 0,
      subject: st.title,
      phase: STATUS_TO_PHASE[st.status] ?? 'RUNNING',
      attempt: st.attempt ?? 1,
      maxAttempts: st.max_attempts ?? 1,
      verifierType: st.verifier_type ?? '',
      feedback: st.feedback ?? null,
      goalIter: st.goal_iter ?? 0,
    })
  }
  return [...bySeq.values()].sort((a, b) => a.index - b.index)
})

const flowName = computed(() => props.sopRun?.definition?.name || 'SOP 流程')

const overallPhase = computed(() => {
  if (props.sopRun?.phase) return props.sopRun.phase
  const list = milestones.value
  if (!list.length) return 'PENDING'
  if (list.some(m => m.phase === 'FAILED')) return 'FAILED'
  if (list.every(m => m.phase === 'COMPLETED')) return 'COMPLETED'
  return 'RUNNING'
})

const doneCount = computed(
  () => milestones.value.filter(m => m.phase === 'COMPLETED').length
)

/** 当前挂起待人工验收的步骤（至多一个，引擎串行推进） */
const awaiting = computed<Milestone | null>(
  () => milestones.value.find(m => m.phase === 'AWAITING') ?? null
)

const handovers = computed(() => props.sopHandover ?? [])

const rejectReason = ref('')

function phaseClass(phase: string): string {
  return `phase-${phase.toLowerCase()}`
}
function phaseLabel(phase: string): string {
  return PHASE_LABEL[phase] ?? phase
}

function submit(confirmed: boolean) {
  const step = awaiting.value
  if (!step) return
  emit('verify', {
    stepIndex: step.index,
    confirmed,
    message: confirmed ? '' : rejectReason.value.trim(),
  })
  rejectReason.value = ''
}
</script>

<template>
  <div class="sop-renderer">
    <div class="sop-head">
      <div class="sop-title">
        <span class="sop-badge">SOP</span>
        <span class="sop-name">{{ flowName }}</span>
      </div>
      <div class="sop-meta">
        <span class="tag" :class="phaseClass(overallPhase)">{{ phaseLabel(overallPhase) }}</span>
        <span class="progress">{{ doneCount }} / {{ milestones.length }} 步</span>
      </div>
    </div>

    <ol v-if="milestones.length" class="sop-timeline">
      <li
        v-for="m in milestones"
        :key="m.index"
        class="sop-step"
        :class="phaseClass(m.phase)"
      >
        <span class="dot" />
        <div class="step-body">
          <div class="step-top">
            <span class="seq">{{ m.index + 1 }}</span>
            <span class="subject">{{ m.subject }}</span>
            <span class="tag" :class="phaseClass(m.phase)">{{ phaseLabel(m.phase) }}</span>
            <span v-if="m.verifierType === 'human'" class="tag verify-human">人工验收</span>
            <span v-else-if="m.verifierType === 'ai'" class="tag verify-ai">AI 验收</span>
            <span v-if="m.attempt > 1" class="tag attempt">
              第 {{ m.attempt }}/{{ m.maxAttempts }} 次
            </span>
            <span v-if="m.goalIter > 0" class="tag iter">迭代 {{ m.goalIter }}</span>
          </div>
          <p v-if="m.feedback" class="feedback">{{ m.feedback }}</p>
        </div>
      </li>
    </ol>

    <!-- 人工验收：引擎在该步挂起（AWAITING），由用户拍板后 resume 续跑 -->
    <div v-if="awaiting" class="verify-panel">
      <div class="verify-title">步骤「{{ awaiting.subject }}」待验收</div>
      <textarea
        v-model="rejectReason"
        class="verify-input"
        rows="2"
        placeholder="驳回原因（驳回时必填）"
      />
      <div class="verify-actions">
        <button class="btn primary" @click="submit(true)">通过</button>
        <button class="btn danger" :disabled="!rejectReason.trim()" @click="submit(false)">
          驳回
        </button>
      </div>
    </div>

    <div v-if="handovers.length" class="handover">
      <div class="handover-title">交接摘要</div>
      <div v-for="(h, i) in handovers" :key="i" class="handover-item">
        <span class="handover-from">{{ h.from }}</span>
        <span class="handover-content">{{ h.content }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sop-renderer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 13px;
  color: var(--text-color, #d0d4dc);
}

.sop-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.sop-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.sop-badge {
  padding: 1px 6px;
  border-radius: 4px;
  background: #3371fc;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.4px;
}
.sop-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sop-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.progress {
  color: #8b90a0;
  font-size: 12px;
}

.sop-timeline {
  list-style: none;
  margin: 0;
  padding: 0 0 0 4px;
}
.sop-step {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 6px 0 6px 14px;
  border-left: 1px solid #2c3040;
}
.sop-step:last-child {
  border-left-color: transparent;
}
.dot {
  position: absolute;
  left: -5px;
  top: 11px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #4a5063;
}
.step-body {
  min-width: 0;
  flex: 1;
}
.step-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.seq {
  color: #8b90a0;
  font-variant-numeric: tabular-nums;
}
.subject {
  font-weight: 500;
}
.feedback {
  margin: 4px 0 0;
  padding: 6px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.04);
  color: #b6bbc8;
  white-space: pre-wrap;
  word-break: break-word;
}

.tag {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: #2c3040;
  color: #b6bbc8;
}
.verify-human { background: rgba(214, 148, 26, 0.18); color: #e0a33c; }
.verify-ai { background: rgba(51, 113, 252, 0.18); color: #6f9bff; }
.attempt { background: rgba(255, 255, 255, 0.06); }
.iter { background: rgba(122, 92, 255, 0.18); color: #a68cff; }

.phase-pending .dot { background: #4a5063; }
.phase-running .dot { background: #3371fc; }
.phase-awaiting .dot { background: #e0a33c; }
.phase-completed .dot { background: #2ea36b; }
.phase-failed .dot { background: #e05252; }

.tag.phase-running { background: rgba(51, 113, 252, 0.18); color: #6f9bff; }
.tag.phase-awaiting { background: rgba(224, 163, 60, 0.18); color: #e0a33c; }
.tag.phase-completed { background: rgba(46, 163, 107, 0.18); color: #4fc48a; }
.tag.phase-failed { background: rgba(224, 82, 82, 0.18); color: #ef6b6b; }

.verify-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(224, 163, 60, 0.35);
  border-radius: 6px;
  background: rgba(224, 163, 60, 0.07);
}
.verify-title {
  font-weight: 600;
  color: #e0a33c;
}
.verify-input {
  width: 100%;
  resize: vertical;
  padding: 6px 8px;
  border: 1px solid #2c3040;
  border-radius: 4px;
  background: #1b1e28;
  color: inherit;
  font: inherit;
}
.verify-actions {
  display: flex;
  gap: 8px;
}
.btn {
  padding: 4px 14px;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.btn.primary { background: #2ea36b; color: #fff; }
.btn.danger { background: #e05252; color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.handover { display: flex; flex-direction: column; gap: 6px; }
.handover-title { font-weight: 600; color: #b6bbc8; }
.handover-item { display: flex; gap: 8px; }
.handover-from { flex-shrink: 0; color: #8b90a0; }
.handover-content {
  color: #b6bbc8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
