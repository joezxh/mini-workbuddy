<!-- Agent 工作台 · Feed 动态时间线（Task 4.6.2）—— SSE + 5 kind chip 过滤 + quiet 语义 -->
<template>
  <div class="sa-feed">
    <div class="sa-feed__header">
      <h2 class="sa-feed__title">动态 Feed</h2>
      <span class="sa-feed__sub">
        <a-badge :status="store.connected ? 'success' : 'default'" />
        {{ store.connected ? '实时推送中' : '未连接' }}
      </span>
    </div>

    <!-- kind chip 过滤 -->
    <div class="sa-feed__chips">
      <a-tag
        v-for="k in KINDS"
        :key="k.value"
        :color="filter === k.value ? KIND_COLORS[k.value] : 'default'"
        :class="{ 'is-on': filter === k.value }"
        class="sa-feed__chip"
        @click="filter = filter === k.value ? '' : k.value"
      >
        {{ k.label }}
      </a-tag>
      <span class="sa-feed__quiet-tip">
        <a-tooltip title="quiet 事件不打扰展示，仅入库；需在过滤时可见">
          <QuestionCircleOutlined /> quiet 静默事件 {{ quietCount }} 条
        </a-tooltip>
      </span>
    </div>

    <!-- 时间线 -->
    <a-spin :spinning="store.loadingFeed">
      <div class="sa-feed__list">
        <div v-for="p in filteredFeed" :key="p.id" class="sa-feed__post" :class="{ 'is-unread': !p.read, 'is-quiet': p.quiet }">
          <div class="sa-feed__post-icon">{{ KIND_EMO[p.kind] || '📌' }}</div>
          <div class="sa-feed__post-body">
            <div class="sa-feed__post-title">
              <a-tag :color="KIND_COLORS[p.kind]" style="margin-inline-end: 6px">{{ p.kind }}</a-tag>
              {{ p.title }}
              <a-tag v-if="p.quiet" style="margin-left: 4px">quiet</a-tag>
            </div>
            <div v-if="p.body" class="sa-feed__post-desc">{{ p.body }}</div>
            <div class="sa-feed__post-actions">
              <span class="sa-feed__post-time">{{ fmtTime(p.created_at) }}</span>
              <a-space>
                <a-button v-if="p.prompt" size="small" type="link" @click="toChat(p.prompt)">
                  💬 带 prompt 发起对话
                </a-button>
                <a-button v-if="p.kind === 'approval' || p.goal_id" size="small" type="link" @click="toGoals(p.goal_id)">
                  🎯 到 Goals 审批
                </a-button>
                <a-button v-if="!p.read" size="small" type="link" @click="markRead(p)">标为已读</a-button>
              </a-space>
            </div>
          </div>
        </div>
        <a-empty v-if="!filteredFeed.length" description="暂无动态" style="margin-top: 60px" />
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import { markFeedRead } from '@/api/super-agent'
import { type FeedPost } from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'

const router = useRouter()
const store = useSuperAgentStore()

const filter = ref('')

const KINDS = [
  { value: 'system', label: '系统' },
  { value: 'ai_batch', label: 'AI 批量' },
  { value: 'reminder', label: '提醒' },
  { value: 'approval', label: '审批' },
  { value: 'goal_updated', label: '目标更新' },
]

const KIND_COLORS: Record<string, string> = {
  system: 'blue', ai_batch: 'purple', reminder: 'orange', approval: 'red', goal_updated: 'green',
}
const KIND_EMO: Record<string, string> = {
  system: '⚙️', ai_batch: '🤖', reminder: '⏰', approval: '✅', goal_updated: '🎯',
}

const filteredFeed = computed(() =>
  filter.value ? store.feed.filter(p => p.kind === filter.value) : store.feed
)
const quietCount = computed(() => store.feed.filter(p => p.quiet).length)

function fmtTime(ts?: string): string {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(5, 19)
}

async function markRead(p: FeedPost) {
  await markFeedRead(p.id, 1).catch(() => {})
  p.read = true
}

function toChat(prompt: string) {
  router.push({ path: '/super-agent/chat', query: { prompt } })
}

function toGoals(goalId?: string | null) {
  router.push({ path: '/super-agent/goals', query: goalId ? { goal: goalId } : {} })
}

onMounted(() => {
  store.fetchFeed()
  store.connectFeed()
})

onUnmounted(() => {
  store.disconnectFeed()
})
</script>

<style scoped lang="less">
.sa-feed {
  padding: 16px 20px;
  max-width: 860px;
  margin: 0 auto;

  &__header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 12px;
  }

  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }

  &__sub {
    font-size: 12px;
    color: var(--ant-color-text-tertiary, #8c8c8c);
  }

  &__chips {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }

  &__chip {
    cursor: pointer;
    padding: 2px 10px;
    font-size: 13px;

    &.is-on {
      font-weight: 600;
    }
  }

  &__quiet-tip {
    margin-left: auto;
    font-size: 12px;
    color: var(--ant-color-text-tertiary, #8c8c8c);
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__post {
    display: flex;
    gap: 10px;
    padding: 12px;
    background: #fff;
    border: 1px solid var(--ant-color-border-secondary, #f0f0f0);
    border-radius: 8px;

    &.is-unread {
      border-left: 3px solid var(--ant-color-primary, #1677ff);
    }

    &.is-quiet {
      opacity: 0.75;
    }
  }

  &__post-icon {
    font-size: 20px;
  }

  &__post-body {
    flex: 1;
    min-width: 0;
  }

  &__post-title {
    font-size: 14px;
    font-weight: 500;
  }

  &__post-desc {
    margin-top: 4px;
    font-size: 13px;
    color: var(--ant-color-text-secondary, #595959);
    white-space: pre-wrap;
    word-break: break-word;
  }

  &__post-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 6px;
  }

  &__post-time {
    font-size: 11px;
    color: var(--ant-color-text-quaternary, #d9d9d9);
  }
}
</style>
