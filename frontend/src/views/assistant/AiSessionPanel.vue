<template>
  <div class="ai-session-panel">
    <div class="panel-header">
      <h2 class="panel-title">AI会话管理</h2>
      <div class="header-actions">
        <a-input-search
          v-model:value="filterUserId"
          placeholder="按用户ID过滤"
          allow-clear
          style="width: 180px"
          @search="loadSessions"
        />
        <a-select
          v-model:value="filterStatus"
          placeholder="会话状态"
          allow-clear
          style="width: 140px"
          @change="loadSessions"
        >
          <a-select-option value="active">活跃</a-select-option>
          <a-select-option value="archived">已归档</a-select-option>
        </a-select>
        <a-button
          danger
          :disabled="selectedSessionIds.length === 0"
          @click="handleBatchDeleteSessions"
        >
          批量删除会话 ({{ selectedSessionIds.length }})
        </a-button>
      </div>
    </div>

    <!-- 会话表格 -->
    <a-table
      :columns="sessionColumns"
      :data-source="sessions"
      :loading="loadingSession"
      :pagination="sessionPagination"
      row-key="session_id"
      :row-selection="{ selectedRowKeys: selectedSessionIds, onChange: onSessionSelect }"
      size="small"
      @change="onSessionTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'session_title'">
          <span class="session-title" @click="openMessages(record)">{{ record.session_title }}</span>
        </template>
        <template v-if="column.key === 'is_pinned'">
          <a-tag :color="record.is_pinned ? 'gold' : 'default'">
            {{ record.is_pinned ? '已置顶' : '-' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">
            {{ record.status === 'active' ? '活跃' : '归档' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" @click="openMessages(record)">查看消息</a-button>
            <a-popconfirm title="确认删除该会话及所有消息？" @confirm="handleDeleteSession(record.session_id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 消息抽屉 -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="drawerTitle"
      width="680"
      placement="right"
      @close="drawerVisible = false"
    >
      <div class="msg-toolbar">
        <a-space>
          <a-button
            danger
            :disabled="selectedMsgIds.length === 0"
            size="small"
            @click="handleBatchDeleteMessages"
          >
            批量删除消息 ({{ selectedMsgIds.length }})
          </a-button>
          <a-popconfirm title="确认清空该会话所有消息？" @confirm="handleClearMessages">
            <a-button danger size="small">清空全部消息</a-button>
          </a-popconfirm>
        </a-space>
        <a-pagination
          v-model:current="msgPage"
          :total="msgTotal"
          :page-size="msgPageSize"
          size="small"
          show-total
          @change="loadMessages"
        />
      </div>

      <a-spin :spinning="loadingMsg">
        <div class="msg-list">
          <div
            v-for="msg in messages"
            :key="msg.message_id"
            :class="['msg-item', msg.role]"
          >
            <a-checkbox
              :checked="selectedMsgIds.includes(msg.message_id)"
              @change="toggleMsgSelect(msg.message_id)"
              class="msg-checkbox"
            />
            <div class="msg-bubble">
              <div class="msg-meta">
                <a-tag :color="roleColor(msg.role)" size="small">{{ roleLabel(msg.role) }}</a-tag>
                <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
              </div>
              <div class="msg-content">{{ msg.content }}</div>
            </div>
          </div>
          <a-empty v-if="messages.length === 0 && !loadingMsg" description="暂无消息" />
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message as antMessage } from 'ant-design-vue'
import {
  adminGetAllSessions,
  adminDeleteSession,
  adminBatchDeleteSessions,
  adminGetSessionMessages,
  adminClearSessionMessages,
  adminBatchDeleteMessages,
  type AiChatSession,
  type AiChatMessage,
} from '@/api/aiSession'

// ── 会话列表状态 ──────────────────────────────────────────────────────────────
const sessions = ref<AiChatSession[]>([])
const loadingSession = ref(false)
const filterUserId = ref<string>('')
const filterStatus = ref<string | undefined>(undefined)
const sessionPage = ref(1)
const sessionPageSize = ref(20)
const sessionTotal = ref(0)
const selectedSessionIds = ref<number[]>([])

const sessionPagination = computed(() => ({
  current: sessionPage.value,
  pageSize: sessionPageSize.value,
  total: sessionTotal.value,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
}))

const sessionColumns = [
  { title: '会话ID', dataIndex: 'session_id', key: 'session_id', width: 80 },
  { title: '用户ID', dataIndex: 'user_id', key: 'user_id', width: 80 },
  { title: '会话标题', dataIndex: 'session_title', key: 'session_title', ellipsis: true },
  { title: '类型', dataIndex: 'session_type', key: 'session_type', width: 100 },
  { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 80 },
  { title: '置顶', key: 'is_pinned', width: 80 },
  { title: '状态', key: 'status', width: 80 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 160,
    customRender: ({ text }: any) => formatTime(text) },
  { title: '操作', key: 'actions', width: 140, fixed: 'right' },
]

async function loadSessions() {
  loadingSession.value = true
  try {
    const uid = filterUserId.value ? Number(filterUserId.value) : undefined
    const res = await adminGetAllSessions({
      page: sessionPage.value,
      page_size: sessionPageSize.value,
      user_id: uid,
      status: filterStatus.value,
    })
    sessions.value = res.items
    sessionTotal.value = res.total
  } finally {
    loadingSession.value = false
  }
}

function onSessionSelect(keys: number[]) {
  selectedSessionIds.value = keys
}

function onSessionTableChange(pagination: any) {
  sessionPage.value = pagination.current
  sessionPageSize.value = pagination.pageSize
  loadSessions()
}

async function handleDeleteSession(sessionId: number) {
  await adminDeleteSession(sessionId)
  antMessage.success('删除成功')
  loadSessions()
}

async function handleBatchDeleteSessions() {
  if (selectedSessionIds.value.length === 0) return
  await adminBatchDeleteSessions(selectedSessionIds.value)
  antMessage.success(`已删除 ${selectedSessionIds.value.length} 个会话`)
  selectedSessionIds.value = []
  loadSessions()
}

// ── 消息抽屉状态 ──────────────────────────────────────────────────────────────
const drawerVisible = ref(false)
const drawerTitle = ref('')
const currentSessionId = ref<number | null>(null)
const messages = ref<AiChatMessage[]>([])
const loadingMsg = ref(false)
const msgPage = ref(1)
const msgPageSize = 50
const msgTotal = ref(0)
const selectedMsgIds = ref<number[]>([])

async function openMessages(session: AiChatSession) {
  currentSessionId.value = session.session_id
  drawerTitle.value = `会话消息 — ${session.session_title} (ID: ${session.session_id})`
  selectedMsgIds.value = []
  msgPage.value = 1
  drawerVisible.value = true
  await loadMessages()
}

async function loadMessages() {
  if (!currentSessionId.value) return
  loadingMsg.value = true
  try {
    const res = await adminGetSessionMessages(currentSessionId.value, {
      page: msgPage.value,
      page_size: msgPageSize,
    })
    messages.value = res.items
    msgTotal.value = res.total
  } finally {
    loadingMsg.value = false
  }
}

function toggleMsgSelect(id: number) {
  const idx = selectedMsgIds.value.indexOf(id)
  if (idx === -1) selectedMsgIds.value.push(id)
  else selectedMsgIds.value.splice(idx, 1)
}

async function handleBatchDeleteMessages() {
  if (selectedMsgIds.value.length === 0) return
  await adminBatchDeleteMessages(selectedMsgIds.value)
  antMessage.success(`已删除 ${selectedMsgIds.value.length} 条消息`)
  selectedMsgIds.value = []
  loadMessages()
  loadSessions()  // 刷新消息计数
}

async function handleClearMessages() {
  if (!currentSessionId.value) return
  await adminClearSessionMessages(currentSessionId.value)
  antMessage.success('已清空所有消息')
  messages.value = []
  msgTotal.value = 0
  loadSessions()
}

// ── 工具函数 ─────────────────────────────────────────────────────────────────
function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 16)
}

function roleLabel(role: string) {
  const map: Record<string, string> = { user: '用户', assistant: 'AI', system: '系统' }
  return map[role] ?? role
}

function roleColor(role: string) {
  const map: Record<string, string> = { user: 'blue', assistant: 'green', system: 'orange' }
  return map[role] ?? 'default'
}

onMounted(() => loadSessions())
</script>

<style lang="less" scoped>
.ai-session-panel {
  padding: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.panel-title {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.session-title {
  color: var(--accent-cyan, #1677ff);
  cursor: pointer;
  &:hover { text-decoration: underline; }
}

.msg-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.msg-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  padding-right: 4px;
}

.msg-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;

  &.user {
    flex-direction: row-reverse;
    .msg-bubble {
      background: rgba(22, 119, 255, 0.08);
      border: 1px solid rgba(22, 119, 255, 0.2);
      align-items: flex-end;
    }
  }

  &.assistant .msg-bubble {
    background: rgba(82, 196, 26, 0.06);
    border: 1px solid rgba(82, 196, 26, 0.2);
  }

  &.system .msg-bubble {
    background: rgba(250, 173, 20, 0.06);
    border: 1px solid rgba(250, 173, 20, 0.2);
  }
}

.msg-checkbox {
  margin-top: 6px;
  flex-shrink: 0;
}

.msg-bubble {
  flex: 1;
  border-radius: 8px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 90%;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.msg-time {
  font-size: 11px;
  color: #999;
}

.msg-content {
  font-size: 13px;
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

