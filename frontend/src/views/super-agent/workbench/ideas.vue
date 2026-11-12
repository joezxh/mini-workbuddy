<!-- Agent 工作台 · Ideas 点子库（Task 4.6.3）—— 卡片网格 + action sheet + AI refresh -->
<template>
  <div class="sa-ideas">
    <div class="sa-ideas__header">
      <h2 class="sa-ideas__title">点子库</h2>
      <a-space>
        <a-button :loading="refreshing" @click="refresh">🤖 AI 生成点子</a-button>
        <a-button type="primary" @click="createOpen = true">+ 手动添加</a-button>
      </a-space>
    </div>

    <a-spin :spinning="store.loadingIdeas">
      <div class="sa-ideas__grid">
        <div v-for="i in store.ideas" :key="i.id" class="sa-idea-card" @click="openAction(i)">
          <div class="sa-idea-card__top">
            <span class="sa-idea-card__emo">{{ i.emo }}</span>
            <a-tag v-if="i.pinned" color="orange" style="margin-inline-end: 0">置顶</a-tag>
          </div>
          <div class="sa-idea-card__pitch">{{ i.pitch }}</div>
          <div v-if="i.detail" class="sa-idea-card__detail">{{ i.detail }}</div>
          <div class="sa-idea-card__meta">
            <a-tag :color="KIND_COLORS[i.kind] || 'default'" style="margin-inline-end: 4px">{{ i.kind }}</a-tag>
            <a-tag style="margin-inline-end: 0">{{ i.src || 'manual' }}</a-tag>
          </div>
        </div>
        <a-empty v-if="!store.ideas.length" description="暂无点子，点击右上角生成" style="grid-column: 1 / -1; margin-top: 40px" />
      </div>
    </a-spin>

    <!-- Action Sheet（demo.html 语义：转对话 / 转 Goal / 转 Routine / 置顶） -->
    <a-modal v-model:open="actionOpen" :title="active?.emo + ' ' + (active?.pitch || '')" :footer="null" width="480px">
      <template v-if="active">
        <p class="sa-ideas__action-detail">{{ active.detail }}</p>
        <div class="sa-ideas__actions">
          <a-button block @click="toChat">💬 发送到 Chat（预填 prompt）</a-button>
          <a-button block :loading="converting === 'goal'" @click="toGoal">
            🎯 创建 Goal（L3 确认后落库）
          </a-button>
          <a-button block :loading="converting === 'routine'" @click="toRoutine">
            ⏰ 建立 Routine（每日 check-in）
          </a-button>
          <a-button block @click="pin">{{ active.pinned ? '📍 取消置顶' : '📍 置顶' }}</a-button>
        </div>
      </template>
    </a-modal>

    <!-- 手动添加 -->
    <a-modal v-model:open="createOpen" title="添加点子" @ok="doCreate" :confirm-loading="creating">
      <a-form layout="vertical">
        <a-form-item label="Emoji">
          <a-input v-model:value="createForm.emo" style="width: 80px" />
        </a-form-item>
        <a-form-item label="一句话卖点" required>
          <a-input v-model:value="createForm.pitch" :maxlength="300" />
        </a-form-item>
        <a-form-item label="补充说明">
          <a-textarea v-model:value="createForm.detail" :rows="3" />
        </a-form-item>
        <a-form-item label="类型">
          <a-radio-group v-model:value="createForm.kind">
            <a-radio value="chat">对话</a-radio>
            <a-radio value="goal">目标</a-radio>
            <a-radio value="routine">例行</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { createGoal, createIdea, pinIdea, refreshIdeas } from '@/api/super-agent'
import { type Idea } from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'

const router = useRouter()
const store = useSuperAgentStore()

const actionOpen = ref(false)
const createOpen = ref(false)
const creating = ref(false)
const refreshing = ref(false)
const converting = ref('')
const active = ref<Idea | null>(null)

const KIND_COLORS: Record<string, string> = { chat: 'blue', goal: 'green', routine: 'purple' }

const createForm = reactive({ emo: '💡', pitch: '', detail: '', kind: 'chat' })

function openAction(i: Idea) {
  active.value = i
  actionOpen.value = true
}

function toChat() {
  if (!active.value) return
  actionOpen.value = false
  router.push({ path: '/super-agent/chat', query: { prompt: active.value.prompt || active.value.pitch } })
}

async function toGoal() {
  if (!active.value) return
  converting.value = 'goal'
  try {
    await createGoal({
      workspace_id: 1,
      title: active.value.pitch,
      context: active.value.detail || '',
      steps: [], // 由 Agent propose 或用户在 Goals 页拆解
    })
    message.success('Goal 已创建（L3 确认）')
    actionOpen.value = false
    router.push('/super-agent/goals')
  } catch {
    /* request 拦截器已提示 */
  } finally {
    converting.value = ''
  }
}

async function toRoutine() {
  if (!active.value) return
  converting.value = 'routine'
  try {
    // routine = 带 check-in cron 的 Goal（demo.html 语义）
    await createGoal({
      workspace_id: 1,
      title: `[Routine] ${active.value.pitch}`,
      context: active.value.detail || '',
      steps: [],
      cron: '0 9 * * *', // 每日 9:00 check-in
    })
    message.success('Routine 已建立（每日 9:00 check-in）')
    actionOpen.value = false
    router.push('/super-agent/goals')
  } catch {
    /* request 拦截器已提示 */
  } finally {
    converting.value = ''
  }
}

async function pin() {
  if (!active.value) return
  await pinIdea(active.value.id, 1).catch(() => {})
  await store.fetchIdeas()
  actionOpen.value = false
}

async function refresh() {
  refreshing.value = true
  try {
    const r = await refreshIdeas(1, 3) as any
    message.success(`生成 ${r.count} 条点子${r.count === 0 ? '（全部为已有去重）' : ''}`)
    await store.fetchIdeas()
  } catch {
    /* request 拦截器已提示 */
  } finally {
    refreshing.value = false
  }
}

async function doCreate() {
  if (!createForm.pitch.trim()) {
    message.warning('请输入卖点')
    return
  }
  creating.value = true
  try {
    await createIdea({
      workspace_id: 1, emo: createForm.emo, pitch: createForm.pitch,
      detail: createForm.detail, kind: createForm.kind,
    })
    createOpen.value = false
    createForm.pitch = ''
    createForm.detail = ''
    await store.fetchIdeas()
  } catch {
    /* request 拦截器已提示（409 去重） */
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  store.fetchIdeas()
})
</script>

<style scoped lang="less">
.sa-ideas {
  padding: 16px 20px;
  max-width: 1100px;
  margin: 0 auto;

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

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
  }

  &__action-detail {
    font-size: 13px;
    color: var(--ant-color-text-secondary, #595959);
    margin-bottom: 16px;
  }

  &__actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}

.sa-idea-card {
  background: #fff;
  border: 1px solid var(--ant-color-border-secondary, #f0f0f0);
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  }

  &__top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  &__emo {
    font-size: 24px;
  }

  &__pitch {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 6px;
  }

  &__detail {
    font-size: 12px;
    color: var(--ant-color-text-secondary, #595959);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 8px;
  }

  &__meta {
    display: flex;
    gap: 4px;
  }
}
</style>
