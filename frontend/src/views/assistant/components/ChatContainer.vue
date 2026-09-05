<template>
  <div class="chat-container">
    <!-- 空状态 -->
    <div v-if="!currentSession" class="chat-empty">
      <div class="empty-icon"><RobotOutlined /></div>
      <h3 class="empty-title">AI 调解助手</h3>
      <p class="empty-desc">直接输入问题发送，或从左侧选择历史会话</p>
      <div class="quick-questions">
        <p class="quick-label"><BulbOutlined /> 示例提问</p>
        <div class="quick-btns">
          <a-button v-for="q in defaultQuestions" :key="q" class="quick-btn" @click="$emit('send-message', q)">{{ q }}</a-button>
        </div>
      </div>
    </div>

    <template v-else>
      <!-- 标题栏 -->
      <div class="chat-header">
        <div class="chat-header-left">
          <RobotOutlined class="chat-header-icon" />
          <span class="chat-header-title">{{ currentSession.session_title || '新对话' }}</span>
          <a-tag :color="sessionTypeColor(currentSession.session_type)" size="small" style="margin-left:8px">
            {{ typeLabel(currentSession.session_type) }}
          </a-tag>
        </div>
        <div class="chat-header-actions">
          <a-tooltip title="清空消息">
            <a-popconfirm title="确认清空所有消息？" @confirm="$emit('clear-messages')">
              <a-button size="small" type="text" danger><ClearOutlined /></a-button>
            </a-popconfirm>
          </a-tooltip>
          <a-tooltip title="删除会话">
            <a-popconfirm title="确认删除该会话？" @confirm="$emit('delete-session', currentSession.session_id)">
              <a-button size="small" type="text" danger><DeleteOutlined /></a-button>
            </a-popconfirm>
          </a-tooltip>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="chat-messages" ref="msgListRef">
        <div v-if="msgHasMore" class="load-more">
          <a-button size="small" type="dashed" :loading="loadingMsg" @click="$emit('load-more')">加载更多消息</a-button>
        </div>

        <template v-for="msg in parsedMessages" :key="msg.message_id">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="msg-row user">
            <div class="msg-ai-wrap-user">
              <div class="msg-bubble user-bubble">
                <div class="msg-text">{{ msg.content }}</div>
                <div class="msg-footer">
                  <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
                  <a-tooltip title="复制"><CopyOutlined class="copy-btn" @click="$emit('copy', msg.content)" /></a-tooltip>
                </div>
              </div>
              <div v-if="hasAttachments(msg)" class="msg-attachments">
                <AttachmentCard v-for="att in getMessageAttachments(msg)" :key="att.file_id || att.id" :file="att" expandable />
              </div>
              <div v-if="analysisProgress" class="analysis-progress">
                <a-progress :percent="analysisProgress.progress" :show-info="false" size="small" />
                <div class="progress-info">
                  <LoadingOutlined />
                  <span>{{ analysisProgress.message }}</span>
                </div>
              </div>
            </div>
            <div class="msg-avatar user-avatar"><UserOutlined /></div>
          </div>

          <!-- AI 消息 -->
          <div v-else-if="msg.role === 'assistant'" class="msg-row assistant">
            <div class="msg-avatar ai-avatar"><RobotOutlined /></div>
            <div class="msg-ai-wrap">
              <!-- 数据分析消息：使用 SqlBotRenderer -->
              <SqlBotRenderer
                v-if="msg.sqlbotData"
                :answer="msg.content"
                :sql="msg.sqlbotData.sql"
                :records="msg.sqlbotData.records"
                :total="msg.sqlbotData.total"
                :stage="msg.sqlbotData.stage"
                :progress-message="msg.sqlbotData.progressMessage"
                :chart-config="msg.sqlbotData.chartConfig"
                :error="msg.sqlbotData.error"
              />
              <!-- 智能体模式：AgentExecutionPanel（Tab 标签页，独立展示） -->
              <template v-else-if="msg.renderKind === 'agent'">
                <AgentExecutionPanel
                  :execution-id="msg.executionId"
                  :streaming="false"
                  :events="msg.executionEvents"
                  :thinking-steps="msg.thinkingSteps"
                  :unified-steps="msg.unifiedSteps"
                  :unified-artifacts="msg.unifiedArtifacts"
                />
                <ArtifactCard
                  v-if="msg.artifacts?.length"
                  :artifacts="msg.artifacts"
                />
                <GeneralRenderer
                  :parsed="msg.parsed || { rawContent: msg.content, sections: {}, thinking: '', isDispute: false, references: {} as any }"
                  :expanded="thinkingExpanded[msg.message_id]"
                  :session-type="currentSessionType"
                  @toggle-thinking="$emit('toggle-thinking', msg.message_id)"
                />
              </template>
              <!-- 智能体团队模式：TeamExecutionPanel（Tab 标签页，独立展示） -->
              <template v-else-if="msg.renderKind === 'team'">
                <TeamExecutionPanel
                  :execution-id="msg.executionId"
                  :streaming="false"
                  :events="msg.executionEvents"
                  :unified-steps="msg.unifiedSteps"
                  :unified-artifacts="msg.unifiedArtifacts"
                />
                <ArtifactCard
                  v-if="msg.artifacts?.length"
                  :artifacts="msg.artifacts"
                />
                <GeneralRenderer
                  :parsed="msg.parsed || { rawContent: msg.content, sections: {}, thinking: '', isDispute: false, references: {} as any }"
                  :expanded="thinkingExpanded[msg.message_id]"
                  :session-type="currentSessionType"
                  @toggle-thinking="$emit('toggle-thinking', msg.message_id)"
                />
              </template>
              <!-- 深度研究模式：DeepResearchExecutionPanel（Tab 标签页，独立展示） -->
              <template v-else-if="msg.renderKind === 'research'">
                <DeepResearchExecutionPanel
                  :execution-id="msg.executionId"
                  :streaming="false"
                  :events="msg.executionEvents"
                  :thinking-steps="msg.thinkingSteps"
                  :sources="msg.researchSources"
                  :unified-steps="msg.unifiedSteps"
                  :unified-artifacts="msg.unifiedArtifacts"
                />
                <ArtifactCard
                  v-if="msg.artifacts?.length"
                  :artifacts="msg.artifacts"
                />
                <GeneralRenderer
                  :parsed="msg.parsed || { rawContent: msg.content, sections: {}, thinking: '', isDispute: false, references: {} as any }"
                  :expanded="thinkingExpanded[msg.message_id]"
                  :session-type="currentSessionType"
                  @toggle-thinking="$emit('toggle-thinking', msg.message_id)"
                />
              </template>
              <!-- 技能执行消息 / 携带统一执行时间线的消息：使用 SkillExecutionPanel（Tab 标签页，与 MediatorPanel 对齐）。
                   即时会话完成后与回放保持一致布局：执行详情 Tab 在上、结果正文在下。 -->
              <template
                v-else-if="(msg.skillEvent && (msg.executionId || msg.sseUrl)) || usesTopTimelineBranch(msg)"
              >
                <SkillExecutionPanel
                  :execution-id="msg.executionId"
                  :streaming="false"
                  :unified-steps="msg.unifiedSteps"
                  :unified-artifacts="msg.unifiedArtifacts"
                />
                <ArtifactCard
                  v-if="msg.artifacts?.length"
                  :artifacts="msg.artifacts"
                />
                <GeneralRenderer
                  :parsed="msg.parsed || { rawContent: msg.content, sections: {}, thinking: '', isDispute: false, references: {} as any }"
                  :expanded="thinkingExpanded[msg.message_id]"
                  :session-type="currentSessionType"
                  @toggle-thinking="$emit('toggle-thinking', msg.message_id)"
                />
              </template>
              <!-- THINKING 思考模式：ThinkingExecutionPanel（Tab 在上）+ 结论正文在下，与技能模式布局一致。
                   必须先于 skill 分支判断：思考消息同时携带 skillEvent+executionId（复用 completed 保存路径） -->
              <template v-else-if="msg.renderKind === 'thinking' || (currentSessionType === 'thinking' && msg.thinkingMode)">
                <ThinkingExecutionPanel
                  :execution-id="msg.executionId"
                  :thinking-steps="msg.thinkingSteps || []"
                  :unified-steps="msg.unifiedSteps"
                  :unified-artifacts="msg.unifiedArtifacts"
                />
                <GeneralRenderer
                  :parsed="msg.parsed || { rawContent: msg.content, sections: {}, thinking: '', isDispute: false, references: {} as any }"
                  :session-type="currentSessionType"
                />
              </template>
              <!-- DEEP_RESEARCH 深度研究模式（兼容旧消息）：过程面板 + 报告渲染 -->
              <template v-else-if="msg.renderKind === 'research-legacy' || (currentSessionType === 'deep_research' && msg.researchReport)">
                <ResearchPanel
                  :plan="msg.researchPlan || []"
                  :stage="msg.researchStage"
                  :progress="msg.researchProgress || 0"
                  :active="false"
                />
                <ResearchReportRenderer
                  v-if="msg.researchReport"
                  :report="msg.researchReport"
                />
              </template>
              <!-- 深度研究后台异步模式：任务卡片（轮询状态 + 实时进度） -->
              <DeepResearchTaskCard
                v-else-if="msg.renderKind === 'research-async'"
                :task="msg.asyncTask!"
              />
              <!-- SCHEDULED 云端调度模式：任务卡片 -->
              <ScheduledTaskCard
                v-else-if="msg.renderKind === 'scheduled' || (currentSessionType === 'scheduled' && msg.asyncTask)"
                :task="msg.asyncTask!"
              />
              <GeneralRenderer
                v-else
                :parsed="msg.parsed || { thinking: '', isDispute: false, sections: {}, rawContent: msg.content, references: { caseType: '', parties: '', caseSummary: '', legalCases: '', legal: '', strategy: '', hasAny: false } }"
                :expanded="thinkingExpanded[msg.message_id]"
                :session-type="currentSessionType"
                @toggle-thinking="$emit('toggle-thinking', msg.message_id)"
              />

              <div class="msg-footer msg-footer-row">
                <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
                <a-tooltip title="复制"><CopyOutlined class="copy-btn" @click="$emit('copy', msg.content)" /></a-tooltip>
              </div>
              <div v-if="msg.suggestedQuestions?.length" class="suggested-questions">
                <span class="suggested-label"><BulbOutlined /> 继续追问：</span>
                <div class="suggested-btns">
                  <a-button v-for="sq in msg.suggestedQuestions" :key="sq" size="small"
                    class="suggested-btn" :disabled="streaming" @click="$emit('send-message', sq)">{{ sq }}</a-button>
                </div>
              </div>
              <!-- 统一执行详情：时间线 Tab（避免挂载在消息下方）。
                   已走上方「Tab 在上、正文在下」分支的场景（skill / 携带统一时间线）不再重复渲染 -->
              <SkillExecutionPanel
                v-if="hasUnifiedTimeline(msg) && !(msg.skillEvent && (msg.executionId || msg.sseUrl)) && !usesTopTimelineBranch(msg)"
                :unified-steps="msg.unifiedSteps"
                :unified-artifacts="msg.unifiedArtifacts"
              />
              <DataAnalysisCard v-if="getMessageAnalysis(msg)" :analysis="getMessageAnalysis(msg)" expandable />
            </div>
          </div>
        </template>

        <!-- 流式输出 -->
        <div v-if="streaming" class="msg-row assistant">
          <div class="msg-avatar ai-avatar"><RobotOutlined /></div>
          <div class="msg-ai-wrap">
            <!-- 思考模式流式：ThinkingExecutionPanel（独立面板，Tab 在上）+ 结论正文在下 -->
            <template v-if="isThinkingStreaming">
              <div v-if="!streamingText" class="ai-stream-waiting">
                <LoadingOutlined spin /> AI 正在思考...
              </div>
              <ThinkingExecutionPanel
                v-if="streamingFlatEvents?.length || streamingThinkingSteps?.length || streamingUnifiedSteps?.length"
                :events="streamingFlatEvents || []"
                :streaming="true"
                :thinking-steps="streamingThinkingSteps || []"
                :unified-steps="streamingUnifiedSteps || []"
                :unified-artifacts="streamingUnifiedArtifacts || []"
              />
              <!-- 结论正文：执行详情 Tab 下方，正文输出后隐藏思考提示 -->
              <GeneralRenderer
                v-if="streamingText"
                :parsed="streamingParsed"
                streaming
                :session-type="currentSessionType"
              />
            </template>
            <!-- 智能体模式流式：AgentExecutionPanel（独立面板）+ 结果正文在 Tab 底下 -->
            <template v-else-if="isAgentStreaming">
              <div v-if="!streamingText && !(streamingFlatEvents?.length || streamingUnifiedSteps?.length)" class="ai-stream-waiting">
                <LoadingOutlined spin /> AI 正在执行...
              </div>
              <AgentExecutionPanel
                v-if="streamingFlatEvents?.length || streamingThinkingSteps?.length || streamingUnifiedSteps?.length || streamingUnifiedArtifacts?.length"
                :events="streamingFlatEvents || []"
                :streaming="true"
                :thinking-steps="streamingThinkingSteps || []"
                :unified-steps="streamingUnifiedSteps || []"
                :unified-artifacts="streamingUnifiedArtifacts || []"
              />
              <GeneralRenderer
                v-if="streamingText"
                :parsed="streamingParsed"
                streaming
                :session-type="currentSessionType"
              />
            </template>
            <!-- 智能体团队模式流式：TeamExecutionPanel（独立面板）+ 结果正文在 Tab 底下 -->
            <template v-else-if="isTeamStreaming">
              <div v-if="!streamingText && !(streamingFlatEvents?.length || streamingUnifiedSteps?.length)" class="ai-stream-waiting">
                <LoadingOutlined spin /> AI 团队正在协作...
              </div>
              <TeamExecutionPanel
                v-if="streamingFlatEvents?.length || streamingUnifiedSteps?.length || streamingUnifiedArtifacts?.length"
                :events="streamingFlatEvents || []"
                :streaming="true"
                :unified-steps="streamingUnifiedSteps || []"
                :unified-artifacts="streamingUnifiedArtifacts || []"
              />
              <GeneralRenderer
                v-if="streamingText"
                :parsed="streamingParsed"
                streaming
                :session-type="currentSessionType"
              />
            </template>
            <!-- 深度研究模式流式：DeepResearchExecutionPanel（独立面板）+ 报告在 Tab 底下 -->
            <template v-else-if="isResearchStreaming">
              <div v-if="!streamingText && !(streamingFlatEvents?.length || streamingThinkingSteps?.length || streamingUnifiedSteps?.length)" class="ai-stream-waiting">
                <LoadingOutlined spin /> AI 正在深度研究...
              </div>
              <DeepResearchExecutionPanel
                v-if="streamingFlatEvents?.length || streamingThinkingSteps?.length || streamingUnifiedSteps?.length || streamingUnifiedArtifacts?.length"
                :events="streamingFlatEvents || []"
                :streaming="true"
                :thinking-steps="streamingThinkingSteps || []"
                :sources="streamingResearchSources || []"
                :unified-steps="streamingUnifiedSteps || []"
                :unified-artifacts="streamingUnifiedArtifacts || []"
              />
              <GeneralRenderer
                v-if="streamingText"
                :parsed="streamingParsed"
                streaming
                :session-type="currentSessionType"
              />
            </template>
            <!-- 技能模式流式：SkillExecutionPanel（Tab 标签页）+ 结果正文在 Tab 底下（与回放消息结构一致） -->
            <template v-else-if="isSkillStreaming">
              <div v-if="!streamingText" class="ai-stream-waiting">
                <LoadingOutlined spin /> AI 正在思考...
              </div>
              <SkillExecutionPanel
                v-if="streamingFlatEvents?.length || streamingUnifiedSteps?.length || streamingUnifiedArtifacts?.length"
                :events="streamingFlatEvents || []"
                :streaming="true"
                :unified-steps="streamingUnifiedSteps || []"
                :unified-artifacts="streamingUnifiedArtifacts || []"
              />
              <!-- 结果正文：执行详情 Tab 下方（回放同款效果），正文输出后隐藏思考提示 -->
              <GeneralRenderer
                v-if="streamingText"
                :parsed="streamingParsed"
                streaming
                :session-type="currentSessionType"
              />
            </template>
            <!-- 非技能模式：保持原有逻辑 -->
            <template v-else>
            <!-- 实时执行过程：当存在 agentGroups 或 toolHistory 时显示步骤时间线 -->
            <ExecutionPanel
              v-if="executionAgentGroups?.size || streamingToolHistory?.length"
              :agent-groups="executionAgentGroups"
              :agent-order="executionAgentOrder"
              :team-state="executionTeamState"
              :tasks="executionTasks"
              :progress-history="executionProgressHistory"
              :phase="(executionPhase as any) || 'streaming'"
              :streaming="true"
            />
            <!-- 技能执行进度提示（尚无实际输出且无事件时显示，轻量提示，非事件记录） -->
            <div v-if="skillProgress && !streamingText && !(executionAgentGroups?.size) && !streamingToolHistory?.length" class="skill-progress-card">
              <div class="skill-progress-header">
                <LoadingOutlined />
                <span class="skill-progress-title">技能执行中</span>
              </div>
              <div class="skill-progress-message">{{ skillProgress.message }}</div>
              <div class="skill-progress-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
            <!-- 数据分析流式：使用 SqlBotRenderer -->
            <SqlBotRenderer
              v-if="streamingSqlbotData || currentSessionType === 'data'"
              :answer="streamingSqlbotData?.progressMessage || streamingText || streamingParsed.rawContent"
              :sql="streamingSqlbotData?.sql"
              :records="streamingSqlbotData?.records"
              :total="streamingSqlbotData?.total"
              :stage="streamingSqlbotData?.stage"
              :progress-message="streamingSqlbotData?.progressMessage"
              :chart-config="streamingSqlbotData?.chartConfig"
              :error="streamingSqlbotData?.error"
            />
            <GeneralRenderer v-else-if="streamingText" :parsed="streamingParsed" streaming :session-type="currentSessionType" />
            <!-- THINKING 流式：思考卡片 -->
            <ThinkingCard
              v-else-if="currentSessionType === 'thinking' && streamingThinkingSteps?.length"
              :steps="streamingThinkingSteps"
              :conclusion="streamingText"
              :active="true"
            />
            <!-- DEEP_RESEARCH 流式：研究过程面板 -->
            <ResearchPanel
              v-else-if="currentSessionType === 'deep_research'"
              :plan="streamingResearchPlan || []"
              :stage="streamingResearchStage || undefined"
              :progress="streamingResearchProgress || 0"
              :active="true"
            />
            <!-- SCHEDULED 流式：任务卡片 -->
            <ScheduledTaskCard
              v-else-if="currentSessionType === 'scheduled' && streamingAsyncTask"
              :task="streamingAsyncTask"
              :active="true"
            />
            </template>
          </div>
        </div>
      </div>

      <!-- 空会话快捷提问 -->
      <div v-if="!messages.length && !streaming" class="chat-quick-area">
        <p class="quick-label"><BulbOutlined /> 快速开始：</p>
        <div class="quick-btns">
          <a-button v-for="q in defaultQuestions" :key="q" class="quick-btn" @click="$emit('send-message', q)">{{ q }}</a-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import {
  RobotOutlined, UserOutlined, CopyOutlined, DeleteOutlined,
  ClearOutlined, BulbOutlined, LoadingOutlined,
} from '@ant-design/icons-vue'
import { GeneralRenderer, SqlBotRenderer, ExecutionPanel } from './renderers'
import SkillExecutionPanel from './renderers/execution/SkillExecutionPanel.vue'
import ThinkingExecutionPanel from './renderers/execution/ThinkingExecutionPanel.vue'
import AgentExecutionPanel from './renderers/execution/AgentExecutionPanel.vue'
import DeepResearchExecutionPanel from './renderers/execution/DeepResearchExecutionPanel.vue'
import TeamExecutionPanel from './renderers/execution/TeamExecutionPanel.vue'
import ThinkingCard from './renderers/ThinkingCard.vue'
import ResearchPanel from './renderers/ResearchPanel.vue'
import ResearchReportRenderer from './renderers/ResearchReportRenderer.vue'
import ScheduledTaskCard from './renderers/ScheduledTaskCard.vue'
import DeepResearchTaskCard from './renderers/DeepResearchTaskCard.vue'
import ArtifactCard from './renderers/ArtifactCard.vue'
import AttachmentCard from './AttachmentCard.vue'
import DataAnalysisCard from './DataAnalysisCard.vue'
import type { ChatMessage } from './types'
import type { AiChatSession } from '@/api/aiSession'
import type { SqlBotData } from './types'

defineProps<{
  currentSession: AiChatSession | null
  parsedMessages: ChatMessage[]
  messages: ChatMessage[]
  streaming: boolean
  streamingParsed: any
  streamingActiveTab: string
  thinkingExpanded: Record<number, boolean>
  msgActiveTab: Record<number, string>
  msgHasMore: boolean
  loadingMsg: boolean
  analysisProgress: any
  /** 技能执行进度信息 */
  skillProgress?: { stage: string; message: string } | null
  /** 执行面板 composable 状态（实时流模式） */
  executionAgentGroups?: Map<string, any> | undefined
  executionAgentOrder?: string[] | undefined
  executionTeamState?: any | undefined
  executionTasks?: any[] | undefined
  executionProgressHistory?: Array<{ stage: string; progress: number; message: string }> | undefined
  executionPhase?: string | undefined
  /** 当前执行 ID */
  currentExecutionId?: string | null
  /** 流式扁平执行事件（供 SkillExecutionPanel 使用） */
  streamingFlatEvents?: import('@/types/shared').ExecutionEvent[] | null
  /** 是否为技能流式执行 */
  isSkillStreaming?: boolean
  /** 是否为思考模式流式执行（使用独立的 ThinkingExecutionPanel 渲染） */
  isThinkingStreaming?: boolean
  /** 是否为智能体模式流式执行（使用独立的 AgentExecutionPanel 渲染） */
  isAgentStreaming?: boolean
  /** 是否为智能体团队模式流式执行（使用独立的 TeamExecutionPanel 渲染） */
  isTeamStreaming?: boolean
  /** 是否为深度研究模式流式执行（使用独立的 DeepResearchExecutionPanel 渲染） */
  isResearchStreaming?: boolean
  /** 流式深度研究来源列表 */
  streamingResearchSources?: Array<{ title: string; url?: string; snippet?: string }> | null
  /** 思考内容 */
  streamingThinkingContent?: string | null
  /** 工具调用历史 */
  streamingToolHistory?: Array<{
    name: string
    input: any
    result?: string
  }> | null
  /** 流式统一时间线步骤（SSE type=step / progress / engine_decision 归一化） */
  streamingUnifiedSteps?: Array<{
    phase: string; event_type: string; title: string; seq: number
    status: string; detail?: string | null; elapsed_ms?: number | null; artifact_id?: string | null
  }> | null
  /** 流式统一时间线产物（SSE type=artifact 归一化） */
  streamingUnifiedArtifacts?: Array<any> | null
  /** 消息 SSE URL (用于历史消息) */
  sseUrl?: string
  /** 当前会话阶段信息 */
  stage?: string
  /** 进度消息 */
  progressMessage?: string
  /** 错误信息 */
  error?: string
  defaultQuestions: string[]
  typeLabel: (t: string) => string
  sessionTypeColor: (t: string) => string
  formatTime: (t: string) => string
  hasAttachments: (msg: ChatMessage) => boolean
  getMessageAttachments: (msg: ChatMessage) => any[]
  getMessageAnalysis: (msg: ChatMessage) => any
  /** SQLBot 流式数据（数据分析会话） */
  streamingSqlbotData?: SqlBotData | null
  /** 当前会话类型 */
  currentSessionType?: string
  /** 流式输出文本 */
  streamingText?: string
  /** THINKING 流式步骤 */
  streamingThinkingSteps?: Array<{
    step: number; title: string; content: string; confidence?: number
  }> | null
  /** DEEP_RESEARCH 流式状态 */
  streamingResearchPlan?: Array<any> | null
  streamingResearchStage?: string | null
  streamingResearchProgress?: number | null
  /** SCHEDULED 流式任务 */
  streamingAsyncTask?: any | null
}>()

defineEmits<{
  (e: 'send-message', text: string): void
  (e: 'load-more'): void
  (e: 'clear-messages'): void
  (e: 'delete-session', id: number): void
  (e: 'toggle-thinking', id: number): void
  (e: 'copy', text: string): void
  (e: 'update:streamingActiveTab', val: string): void
  (e: 'completed', result: any): void
}>()

const msgListRef = ref<HTMLElement>()

// ── 统一执行时间线渲染分支 ─────────────────────────────────────────────────
/** 消息是否携带统一执行时间线数据（归一化步骤 / 产物） */
function hasUnifiedTimeline(msg: ChatMessage): boolean {
  return !!(msg.unifiedSteps?.length || msg.unifiedArtifacts?.length)
}

/**
 * 是否走「执行详情 Tab 在上、结果正文在下」的渲染分支：
 * 携带统一时间线、
 * 非 thinking / research / scheduled 专属卡片模式。
 * 目的：即时会话完成后与历史回放的布局保持一致（Tab 在上、结果在下），
 * 不再依赖 execution_id 是否随 completed 事件到达前端。
 */
function usesTopTimelineBranch(msg: ChatMessage): boolean {
  return hasUnifiedTimeline(msg) && !msg.renderKind
}

function scrollToBottom(smooth = true) {
  nextTick(() => {
    const el = msgListRef.value
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  })
}

defineExpose({ scrollToBottom })
</script>

<style scoped lang="less">
.chat-container { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; }
.chat-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 40px 20px; text-align: center;
}
.empty-icon { font-size: 52px; color: var(--accent); margin-bottom: 16px; opacity: .7; }
.empty-title { font-size: 20px; font-weight: 700; color: var(--fg); margin: 0 0 8px; }
.empty-desc { color: var(--fg-secondary); margin: 0 0 28px; font-size: 14px; }
.quick-questions { width: 100%; max-width: 560px; }
.quick-label { font-size: 13px; color: var(--fg-secondary); margin-bottom: 10px; display: flex; align-items: center; gap: 5px; }
.quick-btns { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; width: 100%; }
.quick-btn {
  font-size: 13px; border-radius: 18px; border-color: var(--border); color: var(--fg);
  height: auto; padding: 5px 14px; white-space: normal; text-align: left;
  width: 100%; max-width: 100%; line-height: 1.5;
  &:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
}
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--border); background: var(--bg-surface); flex-shrink: 0;
}
.chat-header-left { display: flex; align-items: center; gap: 6px; min-width: 0; }
.chat-header-icon { font-size: 18px; color: var(--accent); }
.chat-header-title { font-size: 15px; font-weight: 700; color: var(--fg); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 380px; }
.chat-header-actions { display: flex; gap: 4px; flex-shrink: 0; }
.chat-messages {
  flex: 1; overflow-y: auto; padding: 16px 18px;
  display: flex; flex-direction: column; gap: 16px; min-height: 0;
}
.load-more { text-align: center; margin-bottom: 8px; }
.msg-row { display: flex; align-items: flex-start; gap: 10px; &.user { flex-direction: row-reverse; } }
.msg-avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.user-avatar { background: var(--accent); color: #fff; }
.ai-avatar { background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-soft); }
.msg-bubble { max-width: 72%; border-radius: 12px; padding: 10px 14px; }
.user-bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 3px; }
.ai-bubble { background: var(--bg-surface); border: 1px solid var(--border); border-bottom-left-radius: 3px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.msg-text { font-size: 14px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.msg-footer { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.msg-footer-row { padding: 0 2px; }
.msg-time { font-size: 11px; opacity: .55; }
.copy-btn { font-size: 12px; cursor: pointer; opacity: .5; &:hover { opacity: 1; } }
.suggested-questions { margin-top: 8px; padding-top: 8px; border-top: 1px solid #f0f0f0; }
.suggested-label { font-size: 12px; color: var(--fg-secondary); display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.suggested-btns { display: flex; flex-wrap: wrap; gap: 6px; }
.suggested-btn {
  font-size: 12px; border-radius: 14px; border-color: var(--border); color: var(--accent);
  background: var(--accent-soft); height: auto; padding: 3px 10px;
  &:hover:not(:disabled) { background: var(--accent); color: #fff; border-color: var(--accent); }
}
.msg-ai-wrap { flex: 1; min-width: 0; max-width: calc(100% - 52px); display: flex; flex-direction: column; gap: 8px; }
.msg-ai-wrap-user { flex: 1; min-width: 0; max-width: calc(100% - 52px); display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.msg-attachments { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; align-items: flex-end; }
.analysis-progress { margin-top: 8px; padding: 8px 12px; background: var(--accent-soft); border: 1px solid var(--accent-soft); border-radius: 6px; max-width: 480px; width: 100%; }
.progress-info { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--accent); margin-top: 4px; }
// ── 技能执行进度卡片 ──
.skill-progress-card {
  padding: 12px 16px; background: linear-gradient(135deg, var(--accent-soft) 0%, var(--accent-soft) 100%);
  border: 1px solid var(--accent-soft); border-radius: 10px; max-width: 360px;
}
.skill-progress-header { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--accent); }
.skill-progress-message { font-size: 12px; color: var(--fg-secondary); margin-top: 6px; }
.skill-progress-dots {
  display: flex; gap: 4px; margin-top: 8px;
  span {
    width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    animation: dotBlink 1.2s infinite;
    &:nth-child(2) { animation-delay: .2s; }
    &:nth-child(3) { animation-delay: .4s; }
  }
}
@keyframes dotBlink { 0%, 80%, 100% { opacity: .3; } 40% { opacity: 1; } }
.chat-quick-area { padding: 10px 16px 0; flex-shrink: 0; .quick-btn { font-size: 12px; border-radius: 14px; } }
.ai-stream-waiting {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; font-size: 13px; color: #722ed1;
  background: rgba(114, 46, 209, 0.04); border: 1px solid rgba(114, 46, 209, 0.1);
  border-radius: 8px; margin-bottom: 4px;
}
</style>
