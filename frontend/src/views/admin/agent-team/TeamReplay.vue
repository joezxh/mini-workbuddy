<template>
  <div class="team-replay">
    <div class="replay-header">
      <div class="left">
        <a-button type="link" @click="goBack"><ArrowLeftOutlined /> 返回</a-button>
        <span class="title">运行回放 · {{ runId }}</span>
        <a-tag :color="run?.status === 'completed' ? 'green' : 'default'">{{ run?.status }}</a-tag>
      </div>
      <div class="right">
        <a-button @click="openRerun"><RetweetOutlined /> 分支重跑</a-button>
      </div>
    </div>

    <a-spin :spinning="loading">
      <div class="replay-body" v-if="timeline.length">
        <!-- 回放舞台 -->
        <div class="stage">
          <div class="stage-msg" v-for="(item, i) in playedItems" :key="i">
            <div class="sm-head">
              <span class="sm-type">{{ item.title }}</span>
              <a-tag v-if="item.node_key" size="small" color="blue">{{ item.node_key }}</a-tag>
            </div>
            <div class="sm-detail" v-if="item.detail">{{ item.detail }}</div>
          </div>
        </div>

        <!-- 播放控制条 -->
        <div class="player-bar">
          <a-button shape="circle" @click="togglePlay">
            <PauseOutlined v-if="playing" />
            <CaretRightOutlined v-else />
          </a-button>
          <a-slider
            class="progress"
            :value="current"
            :min="0"
            :max="timeline.length - 1"
            :tip-formatter="() => timeline[current]?.title"
            @change="seek"
          />
          <span class="time-label">{{ current + 1 }} / {{ timeline.length }}</span>
          <a-button size="small" @click="step(-1)"><StepBackwardOutlined /></a-button>
          <a-button size="small" @click="step(1)"><StepForwardOutlined /></a-button>
          <a-button size="small" @click="restart"><ReloadOutlined /></a-button>
        </div>

        <!-- 时间线列表 -->
        <div class="timeline-list">
          <div
            v-for="(item, i) in timeline"
            :key="i"
            class="tl-item"
            :class="{ active: i === current, played: i <= current }"
            @click="seek(i)"
          >
            <span class="tl-seq">{{ i + 1 }}</span>
            <span class="tl-title">{{ item.title }}</span>
            <span class="tl-time" v-if="item.created_at">{{ item.created_at.slice(11, 19) }}</span>
          </div>
        </div>
      </div>
      <a-empty v-else description="暂无回放数据" />
    </a-spin>

    <!-- 分支重跑弹窗 -->
    <a-modal v-model:open="rerunModal" title="分支重跑" @ok="submitRerun" :confirm-loading="rerunLoading">
      <a-form layout="vertical">
        <a-form-item label="重跑起点节点 (branch_from_node)">
          <a-select v-model:value="rerunForm.branch_from_node" :options="nodeOptions" allow-clear placeholder="留空表示从团队起点" />
        </a-form-item>
        <a-form-item label="覆盖输入 (可选)">
          <a-textarea v-model:value="rerunForm.input_text" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  RetweetOutlined,
  PauseOutlined,
  CaretRightOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import * as api from '@/api/agentTeam'

const route = useRoute()
const router = useRouter()
const runId = ref<string>(String(route.params.runId))

const loading = ref(false)
const timeline = ref<api.TimelineItem[]>([])
const run = ref<api.TeamRunOut | null>(null)
const current = ref(0)
const playing = ref(false)
let timer: number | undefined

const playedItems = computed(() => timeline.value.slice(0, current.value + 1))
const nodeOptions = computed(() => {
  const set = new Set(timeline.value.map(t => t.node_key).filter(Boolean) as string[])
  return Array.from(set).map(n => ({ label: n, value: n }))
})
const rerunModal = ref(false)
const rerunLoading = ref(false)
const rerunForm = reactive<api.TeamRerunCreate>({ branch_from_node: undefined, input_text: '' })

const fetchTimeline = async () => {
  loading.value = true
  try {
    const res = await api.replayTimeline(runId.value)
    timeline.value = (res as any).timeline || []
    run.value = (res as any).run
  } catch (e: any) {
    message.error('加载回放失败：' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

// ── 播放控制 ─────────────────────────────────────────
const play = () => {
  if (current.value >= timeline.value.length - 1) current.value = 0
  playing.value = true
  timer = window.setInterval(() => {
    if (current.value < timeline.value.length - 1) current.value++
    else stop()
  }, 700)
}
const stop = () => { playing.value = false; if (timer) { clearInterval(timer); timer = undefined } }
const togglePlay = () => playing.value ? stop() : play()
const seek = (i: number) => { current.value = Math.max(0, Math.min(i, timeline.value.length - 1)) }
const step = (d: number) => seek(current.value + d)
const restart = () => { current.value = 0; if (!playing.value) play() }

// ── 分支重跑 ─────────────────────────────────────────
const openRerun = () => { rerunModal.value = true }
const submitRerun = async () => {
  rerunLoading.value = true
  try {
    const res = await api.rerunBranch(runId.value, {
      branch_from_node: rerunForm.branch_from_node,
      input_text: rerunForm.input_text || undefined
    })
    rerunModal.value = false
    const newRunId = (res as any).run_id
    message.success('已创建分支运行，跳转对话')
    router.push(`/admin/agent-team/${run.value?.team_id}/run/${newRunId}`)
  } catch (e: any) {
    message.error('重跑失败：' + (e?.message || e))
  } finally {
    rerunLoading.value = false
  }
}

const goBack = () => {
  // 优先返回来源对话页
  if (window.history.length > 1) router.back()
  else router.push('/admin/agent-team')
}

onUnmounted(stop)
fetchTimeline()
</script>

<style scoped lang="less">
.team-replay {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-page);
}
.replay-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #eef0f3;
}
.replay-header .title { font-weight: 700; font-size: 16px; }
.replay-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 320px;
  grid-template-rows: 1fr auto;
  gap: 12px;
  padding: 12px;
  min-height: 0;
}
.stage {
  grid-row: 1;
  grid-column: 1;
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  overflow: auto;
  border: 1px solid #eef0f3;
}
.stage-msg {
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #f5f9ff;
  border-left: 3px solid var(--accent-cyan);
  animation: fadein 0.3s;
}
@keyframes fadein { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; } }
.sm-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.sm-type { font-weight: 700; color: var(--text-primary); }
.sm-detail { white-space: pre-wrap; line-height: 1.6; color: var(--text-secondary); }

.player-bar {
  grid-row: 2;
  grid-column: 1 / span 2;
  background: #fff;
  border-radius: 10px;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #eef0f3;
}
.progress { flex: 1; margin: 0 8px; }
.time-label { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }

.timeline-list {
  grid-row: 1;
  grid-column: 2;
  background: #fff;
  border-radius: 10px;
  padding: 8px;
  overflow: auto;
  border: 1px solid #eef0f3;
}
.tl-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  &.played { color: var(--text-primary); }
  &.active { background: rgba(0, 212, 255, 0.12); color: var(--accent-cyan); font-weight: 600; }
  &:hover { background: rgba(0, 0, 0, 0.03); }
}
.tl-seq {
  width: 22px; height: 22px;
  display: inline-flex; align-items: center; justify-content: center;
  background: #eef0f3; border-radius: 50%; font-size: 11px;
}
.tl-title { flex: 1; }
.tl-time { color: #9aa7b8; font-size: 11px; font-family: monospace; }
</style>
