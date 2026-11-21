<!-- Agent 工作台 · Goals 目标（Task 4.6.4）—— 卡片网格 + drawer（step 五态 / L4 proposal / 进展 / 状态） -->
<template>
  <div class="sa-goals">
    <div class="sa-goals__header">
      <h2 class="sa-goals__title">目标</h2>
      <a-button type="primary" @click="createOpen = true">+ 新目标</a-button>
    </div>

    <a-spin :spinning="store.loadingGoals">
      <div class="sa-goals__grid">
        <div v-for="g in store.goals" :key="g.id" class="sa-goal-card" @click="openDrawer(g.id)">
          <div class="sa-goal-card__head">
            <span class="sa-goal-card__title">{{ g.title }}</span>
            <a-tag :color="STATUS_COLORS[g.status] || 'default'" style="margin-inline-end: 0">{{ g.status }}</a-tag>
          </div>
          <a-progress :percent="g.progress" size="small" :status="g.status === 'done' ? 'success' : 'active'" />
          <div class="sa-goal-card__meta">
            <span>v{{ g.version }}</span>
            <span>{{ doneCount(g) }}/{{ g.steps.length }} steps</span>
            <a-badge v-if="pendingProposals(g)" :count="pendingProposals(g)" size="small">
              <a-tag color="orange">L4 建议</a-tag>
            </a-badge>
            <a-tag v-if="g.cron" style="margin-inline-end: 0">⏰ {{ g.cron }}</a-tag>
          </div>
        </div>
        <a-empty v-if="!store.goals.length" description="暂无目标" style="grid-column: 1 / -1; margin-top: 40px" />
      </div>
    </a-spin>

    <!-- 新建 Goal -->
    <a-modal v-model:open="createOpen" title="新目标" @ok="doCreate" :confirm-loading="creating">
      <a-form layout="vertical">
        <a-form-item label="标题" required>
          <a-input v-model:value="createForm.title" :maxlength="300" />
        </a-form-item>
        <a-form-item label="背景（可选）">
          <a-input v-model:value="createForm.context" :maxlength="300" />
        </a-form-item>
        <a-form-item label="初始步骤（每行一步，可空）">
          <a-textarea v-model:value="createForm.stepsText" :rows="4" placeholder="第一步&#10;第二步" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Goal 详情 Drawer -->
    <a-drawer
      v-model:open="drawerOpen"
      :title="detail?.title || '目标详情'"
      width="560"
      destroyOnClose
    >
      <template v-if="detail">
        <div class="sa-goals__drawer-status">
          <a-tag :color="STATUS_COLORS[detail.status]">{{ detail.status }}</a-tag>
          <span style="font-size: 12px; color: #8c8c8c">version v{{ detail.version }}</span>
          <a-select :value="detail.status" size="small" style="width: 120px; margin-left: auto" @change="changeStatus">
            <a-select-option value="active">active</a-select-option>
            <a-select-option value="paused">paused</a-select-option>
            <a-select-option value="done">done</a-select-option>
            <a-select-option value="cancelled">cancelled</a-select-option>
          </a-select>
        </div>

        <a-alert v-if="detail.context" :message="detail.context" type="info" show-icon style="margin-bottom: 12px" />

        <!-- Steps 五态 -->
        <div class="sa-goals__section-title">步骤（点击切换 done/pending）</div>
        <div class="sa-goals__steps">
          <div v-for="s in detail.steps" :key="s.idx" class="sa-goals__step" :class="`is-${s.status}`">
            <a-checkbox
              :checked="s.status === 'done'"
              :disabled="s.status === 'skipped' || detail.status !== 'active'"
              @click.prevent="toggleStep(s.idx)"
            />
            <span class="sa-goals__step-text">{{ s.text }}</span>
            <a-tag :color="STEP_COLORS[s.status] || 'default'" size="small" style="margin-inline-end: 0">{{ s.status }}</a-tag>
            <a-button v-if="s.status !== 'skipped' && detail.status === 'active'" size="small" type="link" @click="skipStep(s.idx)">
              跳过
            </a-button>
          </div>
          <a-empty v-if="!detail.steps.length" description="暂无步骤" :image-style="{ height: '40px' }" />
        </div>

        <!-- L4 Proposals：Agent 只 propose 不改写 -->
        <div class="sa-goals__section-title">
          Agent 建议（L4 proposal · pending 时不改写 plan）
          <a-button size="small" type="link" :loading="proposing" @click="propose">让 Agent 提议</a-button>
        </div>
        <div class="sa-goals__proposals">
          <div v-for="p in detail.proposals" :key="p.idx" class="sa-goals__proposal" :class="`is-${p.status}`">
            <div class="sa-goals__proposal-msg">{{ p.message }}</div>
            <div v-if="p.status === 'pending'" class="sa-goals__proposal-actions">
              <a-button size="small" type="primary" :loading="acting === `a-${p.idx}`" @click="accept(p.idx)">接受</a-button>
              <a-button size="small" :loading="acting === `d-${p.idx}`" @click="dismiss(p.idx)">忽略</a-button>
            </div>
            <a-tag v-else :color="p.status === 'accepted' ? 'green' : 'default'" style="margin-top: 6px">{{ p.status }}</a-tag>
          </div>
          <div v-if="!detail.proposals.length" class="sa-goals__ctx-empty">暂无建议</div>
        </div>

        <!-- 进展时间线 -->
        <div class="sa-goals__section-title">进展时间线</div>
        <a-timeline v-if="detail.notes.length" style="margin-bottom: 12px">
          <a-timeline-item v-for="(n, i) in [...detail.notes].reverse()" :key="i">
            <div style="font-size: 12px">{{ n.text }}</div>
            <div style="font-size: 11px; color: #bfbfbf">{{ fmtTime(n.ts) }}</div>
          </a-timeline-item>
        </a-timeline>
        <div class="sa-goals__add-note">
          <a-input v-model:value="noteText" placeholder="记录进展…" size="small" @pressEnter="addNote" />
          <a-button size="small" :disabled="!noteText.trim()" @click="addNote">添加</a-button>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  type Goal,
  acceptProposal, addGoalNote, createGoal, dismissProposal,
  getGoal, patchGoal, proposeGoal, skipGoalStep, toggleGoalStep,
} from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'
import { useMuseNav } from '../muse-nav'

const route = useRoute()
const store = useSuperAgentStore()
const museNav = useMuseNav()

const createOpen = ref(false)
const creating = ref(false)
const drawerOpen = ref(false)
const detail = ref<Goal | null>(null)
const noteText = ref('')
const proposing = ref(false)
const acting = ref('')

const STATUS_COLORS: Record<string, string> = {
  active: 'blue', paused: 'orange', done: 'green', cancelled: 'default',
}
const STEP_COLORS: Record<string, string> = {
  done: 'green', pending: 'default', in_progress: 'blue', blocked: 'red', skipped: 'orange',
}

const createForm = reactive({ title: '', context: '', stepsText: '' })

function doneCount(g: Goal): number {
  return g.steps.filter(s => s.status === 'done' || s.status === 'skipped').length
}
function pendingProposals(g: Goal): number {
  return g.proposals.filter(p => p.status === 'pending').length
}
function fmtTime(ts: string): string {
  return ts.replace('T', ' ').slice(0, 19)
}

async function doCreate() {
  if (!createForm.title.trim()) {
    message.warning('请输入标题')
    return
  }
  creating.value = true
  try {
    const steps = createForm.stepsText.split('\n').map(s => s.trim()).filter(Boolean)
    await createGoal({
      workspace_id: 1, title: createForm.title, context: createForm.context,
      steps, cron: undefined,
    })
    createOpen.value = false
    createForm.title = ''
    createForm.context = ''
    createForm.stepsText = ''
    await store.fetchGoals()
    message.success('目标已创建')
  } catch {
    /* request 拦截器已提示 */
  } finally {
    creating.value = false
  }
}

async function openDrawer(goalId: string) {
  drawerOpen.value = true
  await loadDetail(goalId)
}

async function loadDetail(goalId: string) {
  detail.value = await getGoal(goalId, 1) as any
  await store.fetchGoals()
}

async function toggleStep(stepIdx: number) {
  if (!detail.value) return
  detail.value = await toggleGoalStep(detail.value.id, stepIdx, 1) as any
  await store.fetchGoals()
}

async function skipStep(stepIdx: number) {
  if (!detail.value) return
  detail.value = await skipGoalStep(detail.value.id, stepIdx, 1) as any
  await store.fetchGoals()
}

async function changeStatus(status: string) {
  if (!detail.value) return
  detail.value = await patchGoal(detail.value.id, status, 1) as any
  await store.fetchGoals()
}

async function propose() {
  if (!detail.value) return
  proposing.value = true
  try {
    detail.value = await proposeGoal(detail.value.id, 1) as any
  } catch {
    /* request 拦截器已提示 */
  } finally {
    proposing.value = false
  }
}

async function accept(idx: number) {
  if (!detail.value) return
  acting.value = `a-${idx}`
  try {
    detail.value = await acceptProposal(detail.value.id, idx, 1) as any
    message.success('已接受，追加为新步骤（version+1）')
    await store.fetchGoals()
  } catch {
    /* request 拦截器已提示 */
  } finally {
    acting.value = ''
  }
}

async function dismiss(idx: number) {
  if (!detail.value) return
  acting.value = `d-${idx}`
  try {
    detail.value = await dismissProposal(detail.value.id, idx, 1) as any
    await store.fetchGoals()
  } catch {
    /* request 拦截器已提示 */
  } finally {
    acting.value = ''
  }
}

async function addNote() {
  if (!detail.value || !noteText.value.trim()) return
  detail.value = await addGoalNote(detail.value.id, noteText.value, 1) as any
  noteText.value = ''
}

onMounted(async () => {
  await store.fetchGoals()
  // Feed approval 卡片 / SSE goal_updated 跳转直达 drawer
  const goalId = (museNav?.params.value.goal || route.query.goal) as string | undefined
  if (goalId) await openDrawer(goalId)
})

// 内嵌态下组件不会重新挂载，监听跨视图传入的 goal
if (museNav) {
  watch(
    () => museNav.params.value.goal,
    (goalId) => { if (typeof goalId === 'string' && goalId) void openDrawer(goalId) },
  )
}
</script>

<style scoped lang="less">
.sa-goals {
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
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }

  &__drawer-status {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }

  &__section-title {
    font-size: 13px;
    font-weight: 600;
    margin: 16px 0 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__steps {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  &__step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border: 1px solid var(--ant-color-border-secondary, #f0f0f0);
    border-radius: 6px;

    &.is-done { background: rgba(82, 196, 26, 0.06); }
    &.is-skipped { opacity: 0.6; }

    .sa-goals__step-text {
      flex: 1;
      font-size: 13px;
      word-break: break-word;
    }
  }

  &__proposals {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__proposal {
    padding: 10px;
    border: 1px solid var(--ant-color-border-secondary, #f0f0f0);
    border-radius: 6px;

    &.is-pending {
      border-left: 3px solid var(--ant-color-warning, #faad14);
    }

    &.is-accepted {
      border-left: 3px solid var(--ant-color-success, #52c41a);
    }
  }

  &__proposal-msg {
    font-size: 13px;
    word-break: break-word;
  }

  &__proposal-actions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  &__ctx-empty {
    font-size: 12px;
    color: var(--ant-color-text-tertiary, #bfbfbf);
  }

  &__add-note {
    display: flex;
    gap: 8px;
  }
}

.sa-goal-card {
  background: var(--sa-surface, var(--ant-color-bg-container, #fff));
  border: 1px solid var(--sa-border, var(--ant-color-border-secondary, #f0f0f0));
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  }

  &__head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    font-size: 12px;
    color: var(--ant-color-text-tertiary, #8c8c8c);
  }
}
</style>
