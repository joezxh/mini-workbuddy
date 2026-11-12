<!-- Ticket 详情 + 时间线（Task 4.3）—— 左：基本信息 + Mandate；右：执行时间线 -->
<template>
  <div class="sa-detail">
    <a-page-header
      :title="ticket?.title || 'Ticket 详情'"
      :sub-title="ticket?.id"
      @back="router.push('/super-agent')"
    />

    <a-spin :spinning="loading">
      <div class="sa-detail__grid">
        <!-- 左：基本信息 + Mandate + 配置 -->
        <div class="sa-detail__left">
          <a-card title="基本信息" size="small" class="mb12">
            <a-descriptions :column="1" size="small" v-if="ticket">
              <a-descriptions-item label="状态">
                <a-tag :color="statusColor(ticket.status)">{{ ticket.status }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="来源">
                <a-tag>{{ ticket.source }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">{{ ticket.created_at }}</a-descriptions-item>
              <a-descriptions-item label="意图证据" v-if="ticket.intent_evidence">
                {{ ticket.intent_evidence }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <a-card title="Mandate（授权）" size="small" class="mb12">
            <template v-if="ticket?.mandate">
              <a-descriptions :column="1" size="small">
                <a-descriptions-item label="强度">
                  <a-tag :color="ticket.mandate.strength === 'explicit' ? 'green' : 'blue'">
                    {{ ticket.mandate.strength }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Policy 版本">{{ ticket.mandate.policy_version }}</a-descriptions-item>
                <a-descriptions-item label="匹配规则">
                  <a-tag v-for="(r, i) in ticket.mandate.matched_rules" :key="i" style="margin-bottom: 4px">
                    {{ r.rule_id }}：{{ r.reason }}
                  </a-tag>
                </a-descriptions-item>
              </a-descriptions>
            </template>
            <a-empty v-else description="暂无 Mandate" :image-style="{ height: '40px' }" />
          </a-card>

          <a-card title="Assignment（执行）" size="small">
            <template v-if="ticket?.assignment">
              <a-descriptions :column="1" size="small">
                <a-descriptions-item label="状态">
                  <a-tag>{{ ticket.assignment.status }}</a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="Executor Session">
                  {{ ticket.assignment.executor_session || '—' }}
                </a-descriptions-item>
                <a-descriptions-item label="开始时间">{{ ticket.assignment.started_at || '—' }}</a-descriptions-item>
              </a-descriptions>
            </template>
            <a-empty v-else description="尚未分派" :image-style="{ height: '40px' }" />
          </a-card>
        </div>

        <!-- 右：执行时间线 -->
        <div class="sa-detail__right">
          <a-card title="执行时间线" size="small">
            <a-timeline v-if="timeline.length">
              <a-timeline-item v-for="(e, i) in timeline" :key="i" :color="e.color">
                <div class="sa-tl__head" @click="e.open = !e.open">
                  <b>{{ e.title }}</b>
                  <span class="sa-tl__time">{{ e.ts }}</span>
                </div>
                <div v-if="e.open" class="sa-tl__detail">{{ e.detail }}</div>
              </a-timeline-item>
            </a-timeline>
            <a-empty v-else description="暂无事件（引擎事件经 /events SSE 推送）" :image-style="{ height: '60px' }" />
          </a-card>
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { type TicketDetail, getTicket } from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'

const props = defineProps<{ id: string }>()
const router = useRouter()
const store = useSuperAgentStore()

const loading = ref(false)
const ticket = ref<TicketDetail | null>(null)

interface TlItem { title: string; detail: string; ts: string; color: string; open: boolean }

const timeline = computed<TlItem[]>(() => {
  const items: TlItem[] = []
  if (ticket.value?.created_at) {
    items.push({ title: 'Ticket 创建', detail: ticket.value.intent_evidence || '', ts: ticket.value.created_at, color: 'blue', open: false })
  }
  if (ticket.value?.mandate) {
    items.push({
      title: `Mandate 授权（${ticket.value.mandate.strength}）`,
      detail: `Policy ${ticket.value.mandate.policy_version}，规则 ${(ticket.value.mandate.matched_rules || []).map(r => r.rule_id).join(', ')}`,
      ts: ticket.value.created_at, color: 'green', open: false,
    })
  }
  if (ticket.value?.assignment) {
    items.push({
      title: `Assignment ${ticket.value.assignment.status}`,
      detail: `Executor: ${ticket.value.assignment.executor_session || '—'}`,
      ts: ticket.value.assignment.started_at || '', color: 'geekblue', open: false,
    })
  }
  // SSE 实时事件追加
  if (store.lastEvent) {
    items.push({
      title: `SSE 事件 · ${store.lastEvent.event}`,
      detail: JSON.stringify(store.lastEvent.data, null, 2),
      ts: new Date(store.lastEvent.ts).toISOString(),
      color: 'purple', open: false,
    })
  }
  return items
})

function statusColor(s: string): string {
  return ({ open: 'blue', working: 'geekblue', completed: 'green', failed: 'red', dropped: 'default' } as Record<string, string>)[s] || 'default'
}

onMounted(async () => {
  loading.value = true
  try {
    ticket.value = await getTicket(props.id) as any
    if (!ticket.value) message.error('Ticket 不存在')
  } catch {
    /* request 拦截器已提示 */
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="less">
.sa-detail {
  padding: 0 4px;

  &__grid {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: 12px;
    align-items: start;
  }

  &__left,
  &__right {
    min-width: 0;
  }
}

.mb12 {
  margin-bottom: 12px;
}

.sa-tl {
  &__head {
    display: flex;
    justify-content: space-between;
    cursor: pointer;
    font-size: 13px;
  }

  &__time {
    font-size: 11px;
    color: var(--ant-color-text-tertiary, #bfbfbf);
  }

  &__detail {
    margin-top: 4px;
    padding: 8px;
    background: var(--ant-color-fill-quaternary, #fafafa);
    border-radius: 4px;
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-all;
  }
}
</style>
