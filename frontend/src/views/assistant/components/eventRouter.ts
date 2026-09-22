/** 执行/消息主渲染路由（EventRouter）。
 *
 * 将 ChatContainer 中「按 renderKind / 会话类型 / 统一时间线」选择渲染分支的判定逻辑
 * 收敛到单一决策函数，作为主渲染逐步切到 EventRouter 的第一步（spec：主渲染切到 EventRouter）。
 *
 * 这里只负责「判定该消息走哪个渲染分支」，具体渲染组件与 props 仍由各分支模板持有，
 * 后续可进一步收敛为数据驱动的渲染表。
 */
import type { Component } from 'vue'
import type { ChatMessage } from './types'
import AgentExecutionPanel from './renderers/execution/AgentExecutionPanel.vue'
import TeamExecutionPanel from './renderers/execution/TeamExecutionPanel.vue'
import DeepResearchExecutionPanel from './renderers/execution/DeepResearchExecutionPanel.vue'
import SkillExecutionPanel from './renderers/execution/SkillExecutionPanel.vue'
import ThinkingExecutionPanel from './renderers/execution/ThinkingExecutionPanel.vue'
import ReactTimeline from './ReactTimeline.vue'
import ResearchPanel from './renderers/ResearchPanel.vue'
import ResearchReportRenderer from './renderers/ResearchReportRenderer.vue'
import DeepResearchTaskCard from './renderers/DeepResearchTaskCard.vue'
import ScheduledTaskCard from './renderers/ScheduledTaskCard.vue'

/** 主渲染分支种类 */
export type RenderKind =
  | 'agent'
  | 'team'
  | 'research'
  | 'react'
  | 'skill'
  | 'thinking'
  | 'research-legacy'
  | 'research-async'
  | 'scheduled'
  | 'default'

export interface RenderContext {
  /** 当前会话类型（thinking / agent / team / deep_research / scheduled / data ...） */
  currentSessionType?: string
}

/** 消息是否携带统一执行时间线数据（归一化步骤 / 产物） */
export function hasUnifiedTimeline(msg: ChatMessage): boolean {
  return !!(msg.unifiedSteps?.length || msg.unifiedArtifacts?.length)
}

/**
 * 是否走「执行详情 Tab 在上、结果正文在下」的渲染分支：
 * 携带统一时间线、且未显式指定其它 renderKind。
 * 目的：即时会话完成后与历史回放的布局保持一致（Tab 在上、结果在下），
 * 不再依赖 execution_id 是否随 completed 事件到达前端。
 */
export function usesTopTimelineBranch(msg: ChatMessage): boolean {
  return hasUnifiedTimeline(msg) && !msg.renderKind
}

/**
 * 解析消息主渲染分支（统一决策入口）。
 *
 * 优先级与原 ChatContainer 模板链一致：
 * agent → team → research → react → skill → thinking → research-legacy →
 * research-async → scheduled → default(GeneralRenderer)。
 * 注意：sqlbot（数据分析）分支不在本路由内，由 ChatContainer 在调用前单独处理。
 */
export function resolveRenderKind(msg: ChatMessage, ctx: RenderContext = {}): RenderKind {
  if (msg.renderKind === 'agent') return 'agent'
  if (msg.renderKind === 'team') return 'team'
  if (msg.renderKind === 'research') return 'research'
  if (msg.renderKind === 'react') return 'react'
  if ((msg.skillEvent && (msg.executionId || msg.sseUrl)) || usesTopTimelineBranch(msg)) {
    return 'skill'
  }
  if (msg.renderKind === 'thinking' || (ctx.currentSessionType === 'thinking' && msg.thinkingMode)) {
    return 'thinking'
  }
  if (
    msg.renderKind === 'research-legacy' ||
    (ctx.currentSessionType === 'deep_research' && msg.researchReport)
  ) {
    return 'research-legacy'
  }
  if (msg.renderKind === 'research-async') return 'research-async'
  if (msg.renderKind === 'scheduled' || (ctx.currentSessionType === 'scheduled' && msg.asyncTask)) {
    return 'scheduled'
  }
  return 'default'
}

// ── 渲染表：分支 → 主渲染组件 + props + 附加渲染开关 ────────────────────────

/** 单个主渲染组件条目（when 不满足时不渲染该条目） */
export interface RenderEntry {
  component: Component
  props: (msg: ChatMessage) => Record<string, unknown>
  when?: (msg: ChatMessage) => boolean
}

/** 渲染规格：主组件列表 + 产物卡片 / 正文回退开关 */
export interface RenderSpec {
  /** 主渲染组件（按顺序渲染；default 分支为空，仅正文回退） */
  primary: RenderEntry[]
  /** 是否渲染 ArtifactCard（msg.artifacts 存在时） */
  showArtifacts: boolean
  /** 是否渲染 GeneralRenderer 正文回退 */
  showText: boolean
  /** thinking 分支：正文不传 expanded / toggle-thinking */
  textBare?: boolean
}

/** 分支 → 渲染规格（与原 ChatContainer 模板逐分支等价） */
export const RENDER_SPECS: Record<RenderKind, RenderSpec> = {
  agent: {
    primary: [{
      component: AgentExecutionPanel,
      props: m => ({
        executionId: m.executionId, streaming: false, events: m.executionEvents,
        thinkingSteps: m.thinkingSteps, unifiedSteps: m.unifiedSteps, unifiedArtifacts: m.unifiedArtifacts,
      }),
    }],
    showArtifacts: true, showText: true,
  },
  team: {
    primary: [{
      component: TeamExecutionPanel,
      props: m => ({
        executionId: m.executionId, streaming: false, events: m.executionEvents,
        unifiedSteps: m.unifiedSteps, unifiedArtifacts: m.unifiedArtifacts,
      }),
    }],
    showArtifacts: true, showText: true,
  },
  research: {
    primary: [{
      component: DeepResearchExecutionPanel,
      props: m => ({
        executionId: m.executionId, streaming: false, events: m.executionEvents,
        thinkingSteps: m.thinkingSteps, sources: m.researchSources,
        unifiedSteps: m.unifiedSteps, unifiedArtifacts: m.unifiedArtifacts,
      }),
    }],
    showArtifacts: true, showText: true,
  },
  react: {
    primary: [{
      component: ReactTimeline,
      props: m => ({
        events: m.reactEvents || [], goal: m.content,
        planStatus: m.reactRunId ? 'done' : 'planning', showActions: false,
      }),
    }],
    showArtifacts: false, showText: true,
  },
  skill: {
    primary: [{
      component: SkillExecutionPanel,
      props: m => ({
        executionId: m.executionId, streaming: false,
        unifiedSteps: m.unifiedSteps, unifiedArtifacts: m.unifiedArtifacts,
      }),
    }],
    showArtifacts: true, showText: true,
  },
  thinking: {
    primary: [{
      component: ThinkingExecutionPanel,
      props: m => ({
        executionId: m.executionId, thinkingSteps: m.thinkingSteps || [],
        unifiedSteps: m.unifiedSteps, unifiedArtifacts: m.unifiedArtifacts,
      }),
    }],
    showArtifacts: false, showText: true, textBare: true,
  },
  'research-legacy': {
    primary: [
      {
        component: ResearchPanel,
        props: m => ({
          plan: m.researchPlan || [], stage: m.researchStage,
          progress: m.researchProgress || 0, active: false,
        }),
      },
      { component: ResearchReportRenderer, props: m => ({ report: m.researchReport }), when: m => !!m.researchReport },
    ],
    showArtifacts: false, showText: false,
  },
  'research-async': {
    primary: [{ component: DeepResearchTaskCard, props: m => ({ task: m.asyncTask }) }],
    showArtifacts: false, showText: false,
  },
  scheduled: {
    primary: [{ component: ScheduledTaskCard, props: m => ({ task: m.asyncTask }) }],
    showArtifacts: false, showText: false,
  },
  default: { primary: [], showArtifacts: false, showText: true },
}
