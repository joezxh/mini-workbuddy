<template>
  <div class="conversations-container">
    <a-row :gutter="[16, 0]">
      <!-- 左侧：会话列表 -->
      <a-col :span="8">
        <div class="session-list-panel">
          <div class="panel-header">
            <span>{{ t('skillHub.execHistory', { total: sessionPagination.total }) }}</span>
          </div>
          
          <a-spin :spinning="sessionsLoading" style="width: 100%">
            <div class="session-list" ref="sessionListRef">
              <div
                v-for="session in sessions"
                :key="session.session_id"
                class="session-item"
                :class="{ active: currentSessionId === session.session_id }"
                @click="loadSessionMessages(session)"
              >
                <div class="session-header">
                  <span class="session-title">{{ session.session_title || t('skillHub.noTitle') }}</span>
                  <span class="session-time">{{ formatTime(session.updated_at) }}</span>
                </div>
                <div class="session-info">
                  <span class="session-user">{{ t('skillHub.userId') }}: {{ session.user_id }}</span>
                  <span class="session-msg-count">{{ t('skillHub.msgCount') }}：{{ session.message_count }}</span>
                </div>
              </div>
              
              <a-empty v-if="!sessions.length && !sessionsLoading" :description="t('skillHub.noSessions')" />
              
              <!-- 分页 -->
              <div class="pagination-wrapper" v-if="sessionPagination.total > (sessionPagination.pageSize || 20)">
                <a-pagination
                  v-model:current="sessionPage"
                  v-model:page-size="sessionPageSize"
                  :total="sessionPagination.total"
                  show-size-changer
                  show-quick-jumper
                  :show-total="(total: number) => t('common.total', { total })"
                  @change="onSessionPageChange"
                />
              </div>
            </div>
          </a-spin>
        </div>
      </a-col>

      <!-- 右侧：消息详情 -->
      <a-col :span="16">
        <div class="messages-panel" v-if="currentSessionId">
          <div class="panel-header">
            <span>{{ t('skillHub.sessionMessages') }}</span>
            <a-button size="small" @click="clearCurrentSession">{{ t('skillHub.clear') }}</a-button>
          </div>
          
          <div class="messages-content">
            <div
              v-for="msg in messages"
              :key="msg.message_id"
              class="message-item"
              :class="msg.role"
            >
              <div class="message-header">
                <a-tag :color="msg.role === 'user' ? 'blue' : 'green'">
                  {{ msg.role === 'user' ? t('skillHub.roleUser') : t('skillHub.roleAi') }}
                </a-tag>
                <span class="message-time">{{ formatTime(msg.created_at) }}</span>
              </div>
              <div class="message-content">
                {{ msg.content }}
              </div>
              
              <!-- 工具调用信息 -->
              <div v-if="msg.tool_calls" class="tool-calls">
                <a-divider plain>{{ t('skillHub.toolCalls') }}</a-divider>
                <pre class="json-preview">{{ JSON.stringify(msg.tool_calls, null, 2) }}</pre>
              </div>
              
              <!-- 工具结果信息 -->
              <div v-if="msg.tool_results" class="tool-results">
                <a-divider plain>{{ t('skillHub.toolResults') }}</a-divider>
                <pre class="json-preview">{{ JSON.stringify(msg.tool_results, null, 2) }}</pre>
              </div>
            </div>
            
            <a-spin v-if="messagesLoading" :style="{ textAlign: 'center', padding: '20px' }" />
            <a-empty v-if="!messages.length && !messagesLoading && currentSessionId" :description="t('skillHub.noMessages')" />
          </div>
          
          <!-- 加载更多 -->
          <div v-if="messages.length > 0" class="load-more-wrapper">
            <a-button 
              block 
              @click="loadMoreMessages" 
              :loading="messagesLoading"
              v-if="messages.length >= 50"
            >
              {{ t('skillHub.loadMore') }}
            </a-button>
          </div>
        </div>
        
        <div v-else class="messages-placeholder">
          <span>{{ t('skillHub.selectSessionHint') }}</span>
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { postSessions, getMessages } from '@/api/chatHistory'

const props = defineProps<{
  packageId: string
  /** 当前 Tab 是否为 conversations */
  active: boolean
}>()

const { t } = useI18n()

const sessionsLoading = ref(false)
const messagesLoading = ref(false)
const sessions = ref<any[]>([])
const messages = ref<any[]>([])
const currentSessionId = ref<number | null>(null)
const sessionPage = ref(1)
const sessionPageSize = ref(20)
const sessionPagination = ref<{ total: number; pageSize?: number }>({ total: 0 })
const sessionListRef = ref<HTMLDivElement>()

interface GetSessionsRequest {
  skill_id: string
  page: number
  page_size: number
}

interface GetMessagesRequest {
  session_id: number
  limit: number
  before_message_id?: number
}

// ── 数据加载 ─────────────────────────────────────────────────────────────────

async function loadSessions() {
  if (!props.packageId) return
  
  sessionsLoading.value = true
  messages.value = []
  currentSessionId.value = null
  
  try {
    const req: GetSessionsRequest = {
      skill_id: props.packageId,
      page: sessionPage.value,
      page_size: sessionPageSize.value,
    }
    const res = await postSessions(req)
    sessions.value = res.sessions || []
    sessionPagination.value.total = res.total || 0
  } catch (e: any) {
    console.error('加载会话列表失败:', e)
    message.error(e?.data?.detail || e?.message || t('skillHub.loadSessionsFailed'))
  } finally {
    sessionsLoading.value = false
  }
}

function onSessionPageChange(page: number, pageSize?: number) {
  sessionPage.value = page
  sessionPageSize.value = pageSize || sessionPageSize.value
  loadSessions()
}

async function loadSessionMessages(session: any) {
  if (!session.session_id || !props.packageId) return
  
  currentSessionId.value = session.session_id
  messagesLoading.value = true
  messages.value = []
  
  try {
    const req: GetMessagesRequest = {
      session_id: session.session_id,
      limit: 50,
    }
    const res = await getMessages(props.packageId, req)
    messages.value = res.messages || []
  } catch (e: any) {
    console.error('加载消息失败:', e)
    message.error(e?.data?.detail || t('skillHub.loadMessagesFailed'))
  } finally {
    messagesLoading.value = false
  }
}

function clearCurrentSession() {
  currentSessionId.value = null
  messages.value = []
}

async function loadMoreMessages() {
  if (!currentSessionId.value || !props.packageId) return
  
  try {
    const lastMsg = messages.value[messages.value.length - 1]
    const req: GetMessagesRequest = {
      session_id: currentSessionId.value,
      limit: 50,
      before_message_id: lastMsg.message_id,
    }
    const res = await getMessages(props.packageId, req)
    const moreMessages = res.messages || []
    
    // 避免重复加载
    if (moreMessages.length > 0 && moreMessages[moreMessages.length - 1].message_id !== lastMsg.message_id) {
      messages.value = [...moreMessages, ...messages.value]
    }
  } catch (e: any) {
    console.error('加载更多消息失败:', e)
    message.error(e?.data?.detail || t('skillHub.loadMoreFailed'))
  }
}

function formatTime(timeStr: string): string {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 当切换到 conversations Tab 时自动加载
watch(
  () => props.active,
  (val) => {
    if (val && props.packageId) {
      loadSessions()
    } else {
      messages.value = []
      currentSessionId.value = null
    }
  },
)

defineExpose({ loadSessions })
</script>

<style scoped>
.conversations-container {
  min-height: 500px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-input);
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
  border-radius: 4px 4px 0 0;
}

.panel-header span {
  font-weight: 600;
  font-size: 13px;
}

.session-list-panel {
  background: var(--bg-surface);
  border-radius: 4px;
  border: 1px solid var(--border);
  height: calc(100vh - 380px);
  overflow-y: auto;
}

.session-list {
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  margin-bottom: 6px;
  background: var(--bg-input);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.session-item:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
}

.session-item.active {
  background: var(--accent-soft);
  border-color: var(--accent);
  box-shadow: 0 2px 4px rgba(24, 144, 255, 0.2);
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.session-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: calc(100% - 60px);
}

.session-time {
  font-size: 12px;
  color: var(--fg-muted);
}

.session-info {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--fg-secondary);
}

.session-user, .session-msg-count {
  flex-shrink: 0;
}

.pagination-wrapper {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.messages-panel {
  background: var(--bg-surface);
  border-radius: 4px;
  border: 1px solid var(--border);
  height: calc(100vh - 380px);
  display: flex;
  flex-direction: column;
}

.messages-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message-item {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-input);
  border-radius: 4px;
  border-left: 3px solid var(--border);
}

.message-item.user {
  border-left-color: var(--accent);
}

.message-item.assistant {
  border-left-color: var(--ok);
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.message-time {
  font-size: 12px;
  color: var(--fg-muted);
}

.message-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--fg);
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-calls, .tool-results {
  margin-top: 8px;
}

.json-preview {
  background: var(--bg-input);
  padding: 8px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
}

.load-more-wrapper {
  padding: 16px;
  border-top: 1px solid var(--border);
}

.messages-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--fg-muted);
  font-size: 13px;
}
</style>
