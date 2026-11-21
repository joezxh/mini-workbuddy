<!-- Agent 工作台 · Chat 独立对话页（Task 4.6.1）—— 三栏：Session / 对话主区 / 上下文卡 -->
<template>
  <div class="sa-chat">
    <!-- 左栏：Session 列表 -->
    <div class="sa-chat__side">
      <a-button type="primary" block @click="newSession" :loading="creatingSession">+ 新对话</a-button>
      <div class="sa-chat__sessions">
        <div
          v-for="s in store.chatSessions"
          :key="s.id"
          class="sa-chat__session"
          :class="{ 'is-active': s.id === store.activeSessionId }"
          @click="switchSession(s.id)"
        >
          <div class="sa-chat__session-title">{{ s.title }}</div>
          <div class="sa-chat__session-meta">{{ s.message_count || 0 }} 条消息</div>
        </div>
        <a-empty v-if="!store.chatSessions.length" description="暂无会话" :image-style="{ height: '40px' }" />
      </div>
    </div>

    <!-- 中栏：对话主区 -->
    <div class="sa-chat__main">
      <template v-if="store.activeSessionId">
        <div ref="msgEl" class="sa-chat__messages">
          <div
            v-for="(m, i) in store.chatMessages"
            :key="i"
            class="sa-chat__msg"
            :class="`sa-chat__msg--${m.role}`"
          >
            <div class="sa-chat__bubble">{{ m.text }}</div>
          </div>
          <div v-if="store.chatStreaming" class="sa-chat__typing">
            <span></span><span></span><span></span>
          </div>
        </div>
        <div class="sa-chat__input">
          <a-textarea
            v-model:value="input"
            placeholder="输入消息，Enter 发送 / Shift+Enter 换行"
            :rows="3"
            :disabled="store.chatStreaming"
            @keydown.enter.exact.prevent="send"
          />
          <div class="sa-chat__input-actions">
            <a-button v-if="store.chatStreaming" danger @click="abort">中断</a-button>
            <a-button v-else type="primary" :disabled="!input.trim()" @click="send">发送</a-button>
          </div>
        </div>
      </template>
      <a-empty v-else description="选择或新建一个会话" style="margin-top: 80px" />
    </div>

    <!-- 右栏：上下文卡 -->
    <div class="sa-chat__context">
      <a-card title="上下文" size="small">
        <div class="sa-chat__ctx-item" @click="goView('goals')">
          🎯 目标 <a-badge :count="store.goals.length" size="small" />
        </div>
        <div class="sa-chat__ctx-item" @click="goView('ideas')">
          💡 点子 <a-badge :count="store.ideas.length" size="small" />
        </div>
        <div class="sa-chat__ctx-item" @click="goView('feed')">
          📋 Feed 未读 <a-badge :count="store.unreadFeedCount" size="small" />
        </div>
        <div class="sa-chat__ctx-item" @click="wsNav?.go('dashboard')">
          🤖 看板
        </div>
      </a-card>
      <a-card title="工具调用" size="small" style="margin-top: 12px">
        <a-collapse v-if="toolEvents.length" size="small">
          <a-collapse-panel v-for="(t, i) in toolEvents" :key="i" :header="t">
            {{ t }}
          </a-collapse-panel>
        </a-collapse>
        <div v-else class="sa-chat__ctx-empty">本次对话暂无工具调用</div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  abortChat, createChatSession, getChatSession, streamChatSend,
} from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'
import { useMuseNav } from '../muse-nav'
import { useWorkspaceNav } from '../workspace-nav'

const route = useRoute()
const router = useRouter()
const store = useSuperAgentStore()
const museNav = useMuseNav()
const wsNav = useWorkspaceNav()

/** 容器内切视图；独立打开（旧路由仍可达）时回退到 router.push。 */
function goView(view: string, params?: Record<string, any>) {
  if (museNav) museNav.switchView(view, params)
  else router.push(params ? { path: `/super-agent/muse`, query: { view, ...params } } : `/super-agent/muse`)
}

const input = ref('')
const creatingSession = ref(false)
const msgEl = ref<HTMLElement | null>(null)
const toolEvents = ref<string[]>([])
let currentRunId = ''

function scrollToBottom() {
  nextTick(() => msgEl.value?.scrollTo({ top: msgEl.value.scrollHeight, behavior: 'smooth' }))
}

async function newSession() {
  creatingSession.value = true
  try {
    const s = await createChatSession(1) as any
    store.openSession(s.id, [])
    await store.fetchChatSessions()
  } finally {
    creatingSession.value = false
  }
}

async function switchSession(id: string) {
  const s = await getChatSession(id, 1) as any
  store.openSession(id, s.messages || [])
  scrollToBottom()
}

async function send() {
  const text = input.value.trim()
  if (!text || !store.activeSessionId) return
  input.value = ''
  currentRunId = `run-${Date.now().toString(36)}`
  toolEvents.value = []

  store.appendMessage({ role: 'user', text, ts: new Date().toISOString() })
  scrollToBottom()
  store.chatStreaming = true

  // 流式接收：先挂一个空的 assistant 气泡，text_delta 增量渲染
  const streamMsg = { role: 'assistant' as const, text: '', ts: new Date().toISOString() }
  let appended = false

  await streamChatSend(store.activeSessionId, text, currentRunId, (event, data) => {
    if (event === 'text_delta') {
      if (!appended) {
        store.appendMessage(streamMsg)
        appended = true
      }
      streamMsg.text += data.delta || ''
      scrollToBottom()
    } else if (event === 'done') {
      if (!appended && data?.reply) store.appendMessage({ role: 'assistant', text: data.reply, ts: new Date().toISOString() })
    } else if (event === 'interrupted') {
      message.info('已中断')
    } else if (event === 'error') {
      message.error(data?.message || '对话出错')
    }
  }).catch(e => message.error(String(e)))

  store.chatStreaming = false
  scrollToBottom()
}

async function abort() {
  if (!currentRunId) return
  await abortChat(currentRunId).catch(() => {})
  store.chatStreaming = false
}

onMounted(async () => {
  await store.fetchChatSessions()
  await store.fetchGoals()
  await store.fetchIdeas()
  await store.fetchFeed()
  // 预填：从 Feed/Ideas「带 prompt 发起对话」跳转
  const prefill = (museNav?.params.value.prompt || route.query.prompt) as string | undefined
  if (prefill) input.value = prefill
  // 有历史会话则自动打开最近一个
  if (!store.activeSessionId && store.chatSessions.length) {
    await switchSession(store.chatSessions[0].id)
  }
})

// 内嵌态下组件不会重新挂载，监听跨视图传入的 prompt
if (museNav) {
  watch(
    () => museNav.params.value.prompt,
    (p) => { if (typeof p === 'string' && p) input.value = p },
  )
}
</script>

<style scoped lang="less">
.sa-chat {
  display: flex;
  height: 100%;
  gap: 12px;
  padding: 16px 20px;
  overflow: hidden;

  &__side {
    flex: 0 0 220px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow: auto;
  }

  &__sessions {
    flex: 1;
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__session {
    padding: 10px;
    border: 1px solid var(--ant-color-border-secondary, #f0f0f0);
    border-radius: 6px;
    cursor: pointer;

    &.is-active {
      border-color: var(--ant-color-primary, #1677ff);
      background: rgba(22, 119, 255, 0.04);
    }
  }

  &__session-title {
    font-size: 13px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__session-meta {
    font-size: 11px;
    color: var(--ant-color-text-tertiary, #bfbfbf);
    margin-top: 4px;
  }

  &__main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    border: 1px solid var(--ant-color-border-secondary, #f0f0f0);
    border-radius: 8px;
    overflow: hidden;
  }

  &__messages {
    flex: 1;
    overflow: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  &__msg {
    display: flex;

    &--user { justify-content: flex-end; }
    &--assistant { justify-content: flex-start; }
  }

  &__bubble {
    max-width: 72%;
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;

    .sa-chat__msg--user & {
      background: var(--ant-color-primary, #1677ff);
      color: #fff;
      border-bottom-right-radius: 2px;
    }

    .sa-chat__msg--assistant & {
      background: var(--ant-color-fill-quaternary, #f5f5f5);
      border-bottom-left-radius: 2px;
    }
  }

  &__typing {
    display: flex;
    gap: 4px;
    padding: 8px 12px;

    span {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--ant-color-text-quaternary, #bfbfbf);
      animation: sa-chat-typing 1s infinite ease-in-out;

      &:nth-child(2) { animation-delay: 0.15s; }
      &:nth-child(3) { animation-delay: 0.3s; }
    }
  }

  &__input {
    border-top: 1px solid var(--ant-color-border-secondary, #f0f0f0);
    padding: 12px;

    textarea {
      resize: none;
    }
  }

  &__input-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 8px;
  }

  &__context {
    flex: 0 0 260px;
    overflow: auto;
  }

  &__ctx-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 4px;
    font-size: 13px;
    cursor: pointer;
    border-radius: 4px;

    &:hover { background: var(--ant-color-fill-quaternary, #f5f5f5); }
  }

  &__ctx-empty {
    font-size: 12px;
    color: var(--ant-color-text-tertiary, #bfbfbf);
    padding: 8px 0;
  }
}

@keyframes sa-chat-typing {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-4px); opacity: 1; }
}
</style>
