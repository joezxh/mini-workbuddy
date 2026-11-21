<!-- SuperAgent Ticket 看板（Task 4.2）—— 8 stage 分组 + SSE + 5s 轮询 fallback -->
<template>
  <div class="sa-board">
    <div class="sa-board__header">
      <div>
        <h1 class="sa-board__title">📊 Dashboard 看板</h1>
        <p class="sa-board__desc">实时查看所有 Ticket 状态，快速进入执行详情</p>
        <span class="sa-board__sub">
          <a-badge :status="store.connected ? 'success' : 'default'" />
          {{ store.connected ? 'SSE 已连接' : '未连接（轮询中）' }}
          <template v-if="store.lastEvent">· 最近事件：{{ store.lastEvent.event }}</template>
        </span>
      </div>
      <div class="sa-board__actions">
        <a-space>
          <a-button @click="router.push('/super-agent/workbench/demo')">▶ Demo 一键运行</a-button>
          <a-button type="primary" @click="openCreate">➕ 新建 Ticket</a-button>
        </a-space>
      </div>
    </div>

    <!-- 原型 Dashboard 4 统计卡 -->
    <div class="sa-stats">
      <div class="sa-stat">
        <div class="lab">执行中</div><div class="val">{{ stat('working') }}</div><div class="delta">WORKING + REFLECTING</div>
      </div>
      <div class="sa-stat peach">
        <div class="lab">待决策</div><div class="val">{{ stat('pending') }}</div><div class="delta">需要你审批</div>
      </div>
      <div class="sa-stat green">
        <div class="lab">本周完成</div><div class="val">{{ stat('completed') }}</div><div class="delta">COMPLETED</div>
      </div>
      <div class="sa-stat red">
        <div class="lab">阻塞 / 等待人工</div><div class="val">{{ stat('blocked') }}</div><div class="delta">BLOCKED + WAITING</div>
      </div>
    </div>

    <a-spin :spinning="store.loadingTickets">
      <div class="sa-board__lanes">
        <div v-for="stage in STAGES" :key="stage" class="sa-board__lane">
          <div class="sa-board__lane-head">
            <span class="sa-board__lane-name">{{ stage }}</span>
            <a-badge :count="store.stageGroups[stage]?.length || 0" :number-style="{ backgroundColor: stageColor(stage) }" />
          </div>
          <div class="sa-board__lane-body">
            <div
              v-for="t in store.stageGroups[stage]"
              :key="t.id"
              class="sa-ticket-card"
              @click="router.push(`/super-agent/workbench/detail/${t.id}`)"
            >
              <div class="sa-ticket-card__title">{{ t.title }}</div>
              <div class="sa-ticket-card__meta">
                <a-tag :color="sourceColor(t.source)" style="margin-inline-end: 4px">{{ t.source }}</a-tag>
                <span>{{ duration(t.created_at) }}</span>
              </div>
            </div>
            <div v-if="!store.stageGroups[stage]?.length" class="sa-board__empty">—</div>
          </div>
        </div>
      </div>
    </a-spin>

    <!-- 创建 Ticket -->
    <a-modal v-model:open="createOpen" title="创建 Ticket" @ok="doCreate" :confirm-loading="creating">
      <a-form layout="vertical">
        <a-form-item label="标题" required>
          <a-input v-model:value="createForm.title" placeholder="要做什么？" :maxlength="500" />
        </a-form-item>
        <a-form-item label="Prompt（可选）">
          <a-textarea v-model:value="createForm.prompt" placeholder="给 Agent 的执行指令" :rows="4" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { createTicket } from '@/api/super-agent'
import { STAGES, useSuperAgentStore } from '@/stores/super-agent'

const router = useRouter()
const store = useSuperAgentStore()

const createOpen = ref(false)
const creating = ref(false)
const createForm = reactive({ title: '', prompt: '' })

const STAGE_COLORS: Record<string, string> = {
  PENDING_ASSESS: 'gold', ACCEPTED: 'blue', WORKING: 'geekblue', REFLECTING: 'purple',
  WAITING_PERSON: 'orange', BLOCKED: 'red', COMPLETED: 'green', DROPPED: 'default',
}
const stageColor = (s: string) => STAGE_COLORS[s] || 'default'

const SOURCE_COLORS: Record<string, string> = {
  github: 'black', feishu: 'blue', manual: 'green', http: 'purple',
}
const sourceColor = (s: string) => SOURCE_COLORS[s] || 'default'

function duration(createdAt?: string): string {
  if (!createdAt) return ''
  const ms = Date.now() - new Date(createdAt.replace('Z', '+00:00')).getTime()
  const m = Math.max(0, Math.floor(ms / 60000))
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h${m % 60}m`
}

/** Dashboard 统计卡：按聚合口径归并 stage 计数。 */
function stat(kind: 'working' | 'pending' | 'completed' | 'blocked'): number {
  const g = store.stageGroups
  switch (kind) {
    case 'working': return (g.WORKING?.length || 0) + (g.REFLECTING?.length || 0)
    case 'pending': return (g.PENDING_ASSESS?.length || 0) + (g.ACCEPTED?.length || 0)
    case 'completed': return g.COMPLETED?.length || 0
    case 'blocked': return (g.BLOCKED?.length || 0) + (g.WAITING_PERSON?.length || 0)
  }
}

function openCreate() {
  createForm.title = ''
  createForm.prompt = ''
  createOpen.value = true
}

async function doCreate() {
  if (!createForm.title.trim()) {
    message.warning('请输入标题')
    return
  }
  creating.value = true
  try {
    await createTicket({ workspace_id: 1, title: createForm.title, prompt: createForm.prompt || undefined })
    message.success('Ticket 已创建')
    createOpen.value = false
    await store.fetchTickets()
  } catch {
    /* request 拦截器已提示 */
  } finally {
    creating.value = false
  }
}

// SSE 由 SuperAgentShell 统一订阅；这里只拉数据，离开看板不再断开全局连接。
onMounted(() => {
  store.fetchTickets()
})
</script>

<style scoped lang="less">
.sa-board {
  padding: 16px 20px;
  height: 100%;
  overflow: auto;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  &__title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }

  &__sub {
    font-size: 12px;
    color: var(--ant-color-text-secondary, #8c8c8c);
  }

  &__lanes {
    display: flex;
    gap: 12px;
    align-items: stretch;
    overflow-x: auto;
    padding-bottom: 12px;
  }

  &__lane {
    flex: 0 0 220px;
    display: flex;
    flex-direction: column;
    background: var(--ant-color-fill-quaternary, #fafafa);
    border-radius: 8px;
    padding: 10px;
  }

  &__lane-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  &__lane-name {
    font-size: 12px;
    font-weight: 600;
    color: var(--ant-color-text-secondary, #595959);
  }

  &__lane-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 60px;
  }

  &__empty {
    text-align: center;
    color: var(--ant-color-text-quaternary, #d9d9d9);
    padding: 16px 0;
  }
}

.sa-ticket-card {
  background: var(--sa-surface, var(--ant-color-bg-container, #fff));
  border: 1px solid var(--sa-border, var(--ant-color-border-secondary, #f0f0f0));
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  &__title {
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 6px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--ant-color-text-tertiary, #bfbfbf);
  }
}

.sa-board__desc {
  font-size: 13px;
  color: var(--sa-text-3);
  margin: -8px 0 6px;
}

.sa-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

.sa-stat {
  position: relative;
  overflow: hidden;
  background: var(--sa-surface);
  border: 1px solid var(--sa-border);
  border-radius: var(--sa-radius);
  padding: 16px 18px;

  &::before {
    content: '';
    position: absolute; inset: 0 0 auto 0; height: 3px;
    background: linear-gradient(90deg, var(--sa-accent), var(--sa-mauve));
  }
  &.peach::before { background: linear-gradient(90deg, var(--sa-peach), var(--sa-yellow)); }
  &.green::before { background: linear-gradient(90deg, var(--sa-green), var(--sa-teal)); }
  &.red::before { background: linear-gradient(90deg, var(--sa-red), var(--sa-pink)); }

  .lab { font-size: 12px; color: var(--sa-text-3); text-transform: uppercase; letter-spacing: 0.08em; }
  .val { font-size: 30px; font-weight: 800; color: var(--sa-text-1); font-variant-numeric: tabular-nums; margin: 6px 0; }
  .delta { font-size: 11px; color: var(--sa-text-3); }
}

@media (max-width: 1100px) {
  .sa-stats { grid-template-columns: repeat(2, 1fr); }
}
</style>
