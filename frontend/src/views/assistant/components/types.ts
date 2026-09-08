/** AI 助手共享类型定义 */
import type { AiChatMessage } from '@/api/aiSession'

/** 消息解析结果 */
export interface ParsedMsg {
  thinking: string
  isDispute: boolean
  sections: Record<string, string>
  rawContent: string
  references: MsgReferences
  toolHistory?: Array<{
    name: string
    input: any
    result?: string
  }>
}

/** 从 AI 输出中提取的引用参考信息 */
export interface MsgReferences {
  caseType: string     // <case_type> 纠纷类型
  parties: string      // <party> 当事人信息
  caseSummary: string  // <summary> 案情摘要
  legalCases: string   // <legal_case> / <legal-case> 类案信息
  legal: string        // <legal> 法律法规信息
  strategy: string     // <strategy> 调解策略信息
  hasAny: boolean      // 是否有任何引用内容
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
  renderKind?: 'thinking' | 'research' | 'scheduled' | 'general' | 'skill' | 'agent' | 'team' | 'dispute' | 'data'
    | 'research-async' | 'research-legacy' | 'react'
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

/** 纠纷调解板块定义 */
export interface DisputeSectionDef {
  key: string
  label: string
  re: RegExp
  emptyHint: string
}

export const DISPUTE_SECTION_DEFS: DisputeSectionDef[] = [
  { key: 'case_overview', label: '📋 案情概述', re: /##\s*[📋🗒️]*\s*案情概述/, emptyHint: ' 正在提取案情信息...' },
  { key: 'strategy',      label: '🎯 策略建议', re: /##\s*[🎯🏹]*\s*策略建议/,   emptyHint: ' 正在检索策略库...' },
  { key: 'golden_words',  label: '💬 调解启示语', re: /##\s*[💬🗨️]*\s*调解启示语/, emptyHint: ' 正在检索金句库...' },
  { key: 'legal_advisor', label: '⚖️ AI 法律顾问', re: /##\s*[⚖️⚡]*\s*AI\s*法律顾问/, emptyHint: ' 正在生成法律分析...' },
]

/** 从文本中提取结构化标签内容，并返回清洗后的文本和引用信息。
 *  支持的标签：<case_type>、<party>、<summary>、<legal_case>/<legal-case>、<legal>、<strategy> */
function extractReferences(text: string): { cleaned: string; refs: MsgReferences } {
  let caseType = ''
  let parties = ''
  let caseSummary = ''
  let legalCases = ''
  let legal = ''
  let strategy = ''

  // 提取各标签内容（支持未闭合标签 —— 流式输出中常见）
  // <case_type>
  const ctRe = /<case_type>([\s\S]*?)(<\/case_type>|$)/gi
  // <party>
  const ptRe = /<party>([\s\S]*?)(<\/party>|$)/gi
  // <summary>
  const smRe = /<summary>([\s\S]*?)(<\/summary>|$)/gi
  // <legal_case> 或 <legal-case>（兼容两种写法）
  const lcRe = /<legal[_-]case>([\s\S]*?)(<\/legal[_-]case>|$)/gi
  // <legal>
  const lgRe = /<legal>([\s\S]*?)(<\/legal>|$)/gi
  // <strategy>
  const stRe = /<strategy>([\s\S]*?)(<\/strategy>|$)/gi

  let m: RegExpExecArray | null
  while ((m = ctRe.exec(text)) !== null) caseType += m[1].trim() + '\n'
  while ((m = ptRe.exec(text)) !== null) parties += m[1].trim() + '\n'
  while ((m = smRe.exec(text)) !== null) caseSummary += m[1].trim() + '\n'
  while ((m = lcRe.exec(text)) !== null) legalCases += m[1].trim() + '\n'
  while ((m = lgRe.exec(text)) !== null) legal += m[1].trim() + '\n'
  while ((m = stRe.exec(text)) !== null) strategy += m[1].trim() + '\n'

  caseType = caseType.trim()
  parties = parties.trim()
  caseSummary = caseSummary.trim()
  legalCases = legalCases.trim()
  legal = legal.trim()
  strategy = strategy.trim()

  // 从文本中移除这些标签（同时清理 <legal_case> 和 <legal-case> 两种写法）
  const cleaned = text
    .replace(/<case_type>[\s\S]*?(<\/case_type>|$)/gi, '')
    .replace(/<party>[\s\S]*?(<\/party>|$)/gi, '')
    .replace(/<summary>[\s\S]*?(<\/summary>|$)/gi, '')
    .replace(/<legal[_-]case>[\s\S]*?(<\/legal[_-]case>|$)/gi, '')
    .replace(/<legal>[\s\S]*?(<\/legal>|$)/gi, '')
    .replace(/<strategy>[\s\S]*?(<\/strategy>|$)/gi, '')
    .trim()

  const hasAny = !!(caseType || parties || caseSummary || legalCases || legal || strategy)
  return {
    cleaned,
    refs: { caseType, parties, caseSummary, legalCases, legal, strategy, hasAny },
  }
}

/**
 * 降级引用提取：当 AI 输出不含结构化标签时，从纯文本中通过关键词/正则模式自动提取引用摘要。
 * 用于通用对话模式（general）的引用卡片展示。
 */
function extractReferencesFallback(text: string): MsgReferences {
  const empty: MsgReferences = { caseType: '', parties: '', caseSummary: '', legalCases: '', legal: '', strategy: '', hasAny: false }
  if (!text || text.length < 15) return empty

  const lines = text.split('\n').map(l => l.trim()).filter(Boolean)

  // ── 1. 纠纷类型：匹配含"纠纷/争议/案件类型"等关键词的行 ──
  let caseType = ''
  const caseTypeKw = /(?:纠纷类型|案件类型|争议类型|纠纷)[：:\s]*(.+)/
  for (const line of lines) {
    const m = line.match(caseTypeKw)
    if (m) { caseType = m[1].trim(); break }
  }
  if (!caseType) {
    const typeMap: [RegExp, string][] = [
      [/(?:劳动|欠薪|工资|薪酬)(?:纠纷|争议)/, '劳动纠纷'],
      [/(?:邻里|相邻)(?:纠纷|争议|关系)/, '相邻权纠纷'],
      [/(?:借贷|借款|债务)(?:纠纷|争议)/, '民间借贷纠纷'],
      [/(?:婚姻|离婚|家庭)(?:纠纷|争议)/, '婚姻家庭纠纷'],
      [/(?:合同|违约)(?:纠纷|争议)/, '合同纠纷'],
      [/(?:侵权)(?:纠纷|争议|损害)/, '侵权责任纠纷'],
      [/(?:物业)(?:纠纷|争议)/, '物业纠纷'],
      [/(?:消费)(?:纠纷|争议|维权)/, '消费纠纷'],
      [/(?:交通|车祸|车祸)(?:事故|纠纷|争议)/, '交通事故纠纷'],
      [/(?:医疗)(?:纠纷|争议|事故)/, '医疗纠纷'],
    ]
    for (const [re, label] of typeMap) {
      if (re.test(text)) { caseType = label; break }
    }
  }

  // ── 2. 当事人信息：匹配 甲乙方/申请被申请人/原被告/"与"字结构 ──
  let parties = ''
  const partyLines: string[] = []
  const partyRoleRe = /((?:甲方|乙方|申请人|被申请人|原告|被告|投诉人|被投诉人|甲方|乙方|第三人)[^\n,，。；]{0,60})/g
  let pm: RegExpExecArray | null
  while ((pm = partyRoleRe.exec(text)) !== null) {
    const val = pm[1].trim()
    if (val.length > 2 && !partyLines.includes(val)) partyLines.push(val)
  }
  if (partyLines.length > 0) {
    parties = partyLines.slice(0, 6).join('\n')
  } else {
    // 尝试 "张三 与 李四" / "张三诉李四" 模式
    const vsRe = /([\u4e00-\u9fa5]{2,4})\s*(?:与|诉|和)\s*([\u4e00-\u9fa5]{2,4})/
    const vm = text.match(vsRe)
    if (vm) parties = `${vm[1]} 与 ${vm[2]}`
  }

  // ── 3. 案情摘要：取第一段非空非标题的实质文本（≤200字） ──
  let caseSummary = ''
  for (const line of lines) {
    if (line.startsWith('#') || line.length < 12) continue
    if (/^(?:参考|相关|根据|依据|建议|策略|分析|总结|综上)/.test(line) && line.length < 30) continue
    caseSummary = line.length > 200 ? line.slice(0, 200) + '…' : line
    break
  }

  // ── 4. 法律法规：匹配 《法律名》及第N条 ──
  const legalSet: string[] = []
  const lawRe = /《([^》]{2,30})》(?:\s*第\s*[\d零一二三四五六七八九十百千]+\s*条)?/g
  let lm: RegExpExecArray | null
  while ((lm = lawRe.exec(text)) !== null) {
    const full = lm[0].trim()
    if (!legalSet.includes(full)) legalSet.push(full)
  }
  const legal = legalSet.slice(0, 8).join('\n')

  // ── 5. 类案参考：匹配案号 (20XX)X...X号 或 "案例/判例" 相关行 ──
  const caseSet: string[] = []
  const caseNoRe = /(?:（\d{4}）|[(]\d{4}[)])[^\n]{2,50}号/g
  let cm: RegExpExecArray | null
  while ((cm = caseNoRe.exec(text)) !== null) {
    const val = cm[0].trim()
    if (!caseSet.includes(val)) caseSet.push(val)
  }
  if (caseSet.length === 0) {
    // 尝试匹配含 "案例/判例/类案" 关键词的行
    const caseKwRe = /(?:类案|案例|判例|参考案例|指导案例)[：:\s]*(.+)/
    for (const line of lines) {
      const m = line.match(caseKwRe)
      if (m) { caseSet.push(m[0].trim()); if (caseSet.length >= 3) break }
    }
  }
  const legalCases = caseSet.slice(0, 5).join('\n')

  // ── 6. 调解策略/建议：匹配含策略/建议/方案等关键词的行 ──
  const stratLines: string[] = []
  const stratKwRe = /(?:调解?策略|处理建议|解决方案|调解方案|建议[：:]|策略[：:]|调解建议|工作建议)[：:\s]*(.+)/
  for (const line of lines) {
    const m = line.match(stratKwRe)
    if (m) { stratLines.push(m[0].trim()); if (stratLines.length >= 3) break }
  }
  let strategy = stratLines.join('\n')

  // 若没有明确策略标题，尝试含"建议"的短句
  if (!strategy) {
    const suggestions: string[] = []
    for (const line of lines) {
      if (/(?:建议|应当|可以|需要|注意)/.test(line) && line.length > 8 && line.length < 120) {
        suggestions.push(line)
        if (suggestions.length >= 3) break
      }
    }
    strategy = suggestions.join('\n')
  }

  const hasAny = !!(caseType || parties || caseSummary || legalCases || legal || strategy)
  return { caseType, parties, caseSummary, legalCases, legal, strategy, hasAny }
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

  // 2. 提取引用标签（<legal-case>、<legal>、<strategy>）
  let { cleaned: remainingClean, refs } = extractReferences(remaining)
  remaining = remainingClean

  // 2b. 降级提取：当标签提取无结果时，从纯文本中自动提取引用摘要
  if (!refs.hasAny) {
    const fallbackRefs = extractReferencesFallback(remaining)
    if (fallbackRefs.hasAny) refs = fallbackRefs
  }

  // 3. 找到第一个纠纷章节标题
  let firstIdx = remaining.length
  let isDispute = false
  for (const def of DISPUTE_SECTION_DEFS) {
    const hit = def.re.exec(remaining)
    if (hit && hit.index < firstIdx) { firstIdx = hit.index; isDispute = true }
  }

  // 4. 章节前的普通文字：不显示（不归入思考），直接丢弃
  //    （之前版本会将 pre-section 文字放入思考块，现在仅在 <think> 标签内才算思考）

  const sectionText = isDispute ? remaining.slice(firstIdx) : remaining
  const thinking = thinkingParts.filter(Boolean).join('\n\n---\n\n')

  // 5. 解析各章节内容
  const sections: Record<string, string> = {}
  if (isDispute) {
    const positions: Array<{ key: string; start: number }> = []
    for (const def of DISPUTE_SECTION_DEFS) {
      const hit = def.re.exec(sectionText)
      if (hit) positions.push({ key: def.key, start: hit.index })
    }
    positions.sort((a, b) => a.start - b.start)
    for (let i = 0; i < positions.length; i++) {
      const { key, start } = positions[i]
      const end = positions[i + 1]?.start ?? sectionText.length
      const chunk = sectionText.slice(start, end)
      const hdr = /##[^\n]*\n/.exec(chunk)
      sections[key] = hdr ? chunk.slice(hdr.index + hdr[0].length).trim() : chunk.trim()
    }
  }

  return { thinking, isDispute, sections, rawContent: isDispute ? sectionText : remaining, references: refs }
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

