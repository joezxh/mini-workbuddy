/** AI 助手共享类型定义 */
import type { AiChatMessage } from '@/api/aiSession'

/** 消息解析结果 */
export interface ParsedMsg {
  thinking: string
  rawContent: string
  toolHistory?: Array<{
    name: string
    input: any
    result?: string
  }>
}

/** SQLBot 数据分析结果 */
export interface SqlBotData {
  sql?: string
  records?: Record<string, any>[]
  total?: number
  stage?: string
  progressMessage?: string
  chartConfig?: ChartConfig
  error?: string
  /** SQLBot 多轮对话会话 ID（用于后续查询复用上下文） */
  chatId?: number
}

/** 图表配置 */
export interface ChartConfig {
  type: 'column' | 'bar' | 'line' | 'pie' | 'table'
  title?: string
  axis?: {
    x?: { name: string; value: string }
    y?: { name: string; value: string }
    series?: { name: string; value: string }
  }
  columns?: Array<{ name: string; value: string }>
}

/** 扩展的聊天消息类型 */
export type ChatMessage = AiChatMessage & {
  suggestedQuestions?: string[]
  parsed?: ParsedMsg
  /** SQLBot 数据分析结果（session_type='data' 时） */
  sqlbotData?: SqlBotData
  /** 技能执行事件相关 */
  skillEvent?: boolean
  result?: any
  executionSteps?: Array<{
    type: string
    title: string
    content: string
    active: boolean
    done: boolean
  }>
  thinkingContent?: string
  toolHistory?: Array<{
    name: string
    input: any
    result?: string
  }>
  stage?: string
  progressMessage?: string
  error?: string
  
  // Skill Timeline View 新增字段
  executionId?: string       // 执行 ID（用于构建 SSE URL）
  sseUrl?: string            // SSE 流地址（可选，如果提供则优先使用）

  /** 技能执行产物文件 */
  artifacts?: Array<{
    file_id: string
    filename: string
    size_bytes: number
    mime_type: string
  }>

  file?: {
    id: number
    name: string
    size: number
    type?: string
    url: string
  }

  /** THINKING 模式：思考步骤（流式 + 历史回放） */
  thinkingSteps?: Array<{
    step: number
    title: string
    content: string
    confidence?: number
  }>
  thinkingMode?: boolean

  /** DEEP_RESEARCH 模式：研究过程与报告 */
  researchReport?: {
    summary: string
    keyFindings: string[]
    analysis: string
    sources: Array<{ title: string; url: string; credibility: number }>
  }
  researchPlan?: Array<{
    id: string
    question: string
    status: 'queued' | 'searching' | 'done' | 'failed'
    sources: Array<{ title: string; url: string; credibility: number }>
  }>
  researchStage?: string
  researchProgress?: number

  /** SCHEDULED 模式：异步任务卡片信息 */
  asyncTask?: AsyncTaskInfo

  /** 通用：标记该消息使用何种专属渲染器
   *  research-async：深度研究后台异步任务卡片
   *  research-legacy：旧版深度研究消息（过程面板 + 报告） */
  renderKind?: 'thinking' | 'research' | 'scheduled' | 'general' | 'skill' | 'agent' | 'team' | 'data'
    | 'research-async' | 'research-legacy' | 'react' | 'sop'
  attachments?: Array<{
    file_id?: string
    db_id?: number
    name?: string
    size?: number
    url?: string
    sheet_count?: number
    row_count?: number
    col_count?: number
    sheets?: string[]
    preview_data?: Record<string, any>[]
  }>
  file_db_ids?: number[]

  /** 统一步骤事件（跨模式归一化时间线，SSE type=step） */
  unifiedSteps?: UnifiedStep[]
  /** 统一产物事件（跨模式归一化产物画廊，SSE type=artifact） */
  unifiedArtifacts?: UnifiedArtifact[]

  /** SOP 模式：流程定义 + 运行状态快照（对应后端 SOPRunState，用于刷新后恢复） */
  sopRun?: {
    definition: SopDefinition
    phase: SopPhase
    steps: SopStepState[]
    runStateJson?: string
  }
  /** SOP 模式：各步交接摘要（from=步骤名，content=交付内容） */
  sopHandover?: Array<{ from: string; content: string }>

  /** 扁平事件（跨模式归一化，含 thinking/text_chunk/tool_call 等，回放时直读） */
  executionEvents?: Array<import('@/types/shared').ExecutionEvent>
  /** 深度研究来源列表（回放直读） */
  researchSources?: Array<{ title: string; url?: string; snippet?: string }>

  /** ReAct 模式：SSE 事件列表（回放直读） */
  reactEvents?: Array<{ type: string; [key: string]: any }>
  /** ReAct 模式：运行 ID（供 HITL API 调用） */
  reactRunId?: string
}

/** 技能信息 */
export interface SkillInfo {
  packageId: string
  packageName: string
  packageIcon: string
  scriptId: string
  scriptName: string
  scriptDescription: string
  params?: Record<string, any>
}

/** 消息解析函数 */
export function parseMsg(text: string): ParsedMsg {
  let thinkingParts: string[] = []
  let remaining = text

  // 1. 提取 <think>...</think>（仅在 <think> 标签存在时收集为思考内容）
  const thinkRe = /<think>([\s\S]*?)(<\/think>|$)/gi
  let m: RegExpExecArray | null
  while ((m = thinkRe.exec(text)) !== null) thinkingParts.push(m[1].trim())
  remaining = text.replace(/<think>[\s\S]*?(<\/think>|$)/gi, '').trim()

  // 1b. <think> 之前的内容不直接显示（丢弃），仅在 <think> 存在时生效
  const hasThinkTag = /<think>/i.test(text)
  if (hasThinkTag) {
    const thinkStart = text.search(/<think>/i)
    if (thinkStart > 0) {
      // <think> 前的文本已在 remaining 中，需要移除（它不是正文也不是思考）
      // remaining 此时已去掉 <think> 块，但 <think> 之前的纯文本仍在
      // 通过截取 <think> 之后的部分来丢弃前缀
      const afterFirstThink = text.slice(thinkStart).replace(/<think>[\s\S]*?(<\/think>|$)/gi, '').trim()
      // 仅当 afterFirstThink 比 remaining 短时才替换（说明确实有前缀被丢弃）
      if (afterFirstThink.length < remaining.length) {
        remaining = afterFirstThink
      }
    }
  }

  const thinking = thinkingParts.filter(Boolean).join('\n\n---\n\n')
  return { thinking, rawContent: remaining }
}

// ─────────────────────────────────────────────────────────────
// 思考 / 深度研究 / 云端调度 三种新模式类型
// ─────────────────────────────────────────────────────────────

/** 思考步骤 */
export interface ThinkingStep {
  step: number
  title: string
  content: string
  confidence?: number
}

/** 研究子问题 */
export interface ResearchSubQuestion {
  id: string
  question: string
  status: 'queued' | 'searching' | 'done' | 'failed'
  sources: Array<{ title: string; url: string; credibility: number }>
}

/** 结构化研究报告 */
export interface ResearchReport {
  summary: string
  keyFindings: string[]
  analysis: string
  sources: Array<{ title: string; url: string; credibility: number }>
}

/** 异步任务信息（SCHEDULED 模式卡片） */
export interface AsyncTaskInfo {
  taskId: number
  taskNo?: string
  taskName?: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  priority?: number
  errorMessage?: string
  /** 网关执行 ID（后端启动即写入，运行中即可实时回放执行事件） */
  executionId?: string | null
  resultData?: any
  submittedAt?: string
  finishedAt?: string
}

// ─────────────────────────────────────────────────────────────
// 会话类别（session_type）是否展示「模型选择」下拉框
// ChatInput.vue 用其控制模型下拉渲染；AssistantPanel.vue 用其决定
// 切换类别时是否保留已选模型。两处共用同一常量，保证行为一致。
// ─────────────────────────────────────────────────────────────
export const MODEL_SELECTABLE_TYPES: string[] = [
  'skill',        // 技能
  'thinking',     // 思考
  'deep_research',// 深度研究
  'agent',        // 智能体
  'team',         // 智能体团队（仅 UI 显示 + 透传，执行走全局 Dify 通道）
  'scheduled',    // 云端调度（模型随任务参数透传，后台执行时生效）
]

// ─────────────────────────────────────────────────────────────
// 统一步骤 / 产物事件（跨 8 种模式归一化）
// 后端 StepEvent / ArtifactItem 的 SSE 形状见 backend/app/ai/gateway/mode_handlers/_common.py
// ─────────────────────────────────────────────────────────────

/** 统一步骤事件（对应后端 StepEvent，SSE type=step） */
export interface UnifiedStep {
  phase: string
  event_type: string
  title: string
  seq: number
  status: 'running' | 'done' | 'failed' | 'warn'
  detail?: string | null
  elapsed_ms?: number | null
  artifact_id?: string | null
  /** 工作流执行形式：serial 串行 | parallel 并行分支成员 | branch 分支判断/汇聚 */
  exec_mode?: 'serial' | 'parallel' | 'branch'
  /** 并行分组 ID：同组步骤渲染为上下分支泳道 */
  group_id?: string | null
  /** 并行分支显示标签（如 worker 角色名） */
  branch_label?: string | null
  /** 分支判断说明 */
  branch_note?: string | null
  /** SOP 扩展：当前尝试次数 */
  attempt?: number
  /** SOP 扩展：最大尝试次数 */
  max_attempts?: number
  /** SOP 扩展：验收方式（ai / human / none） */
  verifier_type?: string
  /** SOP 扩展：验收反馈（驳回原因 / 通过意见） */
  feedback?: string | null
  /** SOP 扩展：loop=goal 当前迭代轮次 */
  goal_iter?: number
}

/** 统一产物事件（对应后端 ArtifactItem，SSE type=artifact） */
export interface UnifiedArtifact {
  artifact_id: string
  kind: 'file' | 'chart' | 'image' | 'video'
  title: string
  seq: number
  mime_type?: string | null
  file_id?: string | null
  chart_config?: Record<string, any> | null
  media_data?: string | null
  size_bytes?: number | null
  status: 'generating' | 'ready' | 'failed'
  error?: string | null
  suggestion?: string | null
}

// ─────────────────────────────────────────────────────────────
// SOP 模式数据结构（对应后端 app/ai/sop/schemas.py）
// ─────────────────────────────────────────────────────────────

/** SOP 阶段（后端 SOPPhase） */
export type SopPhase = 'PENDING' | 'RUNNING' | 'AWAITING' | 'COMPLETED' | 'FAILED'

/** SOP 步骤定义（后端 SOPStepDef） */
export interface SopStepDef {
  subject: string
  description?: string
  executor_agent?: string
  verifier_type?: 'ai' | 'human' | 'none'
  verifier_agent?: string | null
  max_attempts?: number
  loop?: 'none' | 'goal'
  goal_max_iters?: number
  goal_max_retries?: number
  goal_verifier_reset_ctx?: boolean
  exec_mode?: 'serial' | 'parallel'
  group_id?: string | null
  artifact_key?: string | null
}

/** SOP 流程定义（后端 SOPDefinition） */
export interface SopDefinition {
  name: string
  description?: string
  steps: SopStepDef[]
  source?: string
  template_id?: number | null
}

/** SOP 单步运行时状态（后端 StepRuntimeState） */
export interface SopStepState {
  index: number
  subject: string
  phase: SopPhase
  attempt: number
  max_attempts: number
  verifier_type: string
  feedback?: string | null
  output?: string | null
  goal_iter?: number
  exec_mode?: string
  group_id?: string | null
}

