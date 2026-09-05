<!--
  ScheduledTaskManage.vue — AI 任务定时调度管理（「我的异步任务」的调度 Tab）

  职责：
  1. 展示当前用户配置的定时调度任务（深度研究 / Agent / AgentTeam）；
  2. 新建 / 编辑调度（cron / interval / once 三种调度类型）；
  3. 暂停 / 恢复 / 立即执行 / 删除；
  4. 触发后生成的一次性异步任务回到「异步任务」Tab 查看进度与结果。
-->
<template>
  <div class="stm">
    <div class="stm-toolbar">
      <a-select
        v-model:value="statusFilter"
        :options="statusOptions"
        style="width: 120px"
        placeholder="全部状态"
        allow-clear
        @change="onFilterChange"
      />
      <a-button type="primary" @click="openCreate">
        <PlusOutlined /> 新建调度任务
      </a-button>
    </div>

    <a-table
      row-key="id"
      :columns="columns"
      :data-source="items"
      :loading="loading"
      :pagination="pagination"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'targetMode'">
          <a-tag :color="modeColor(record.targetMode)">{{ modeLabel(record.targetMode) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'schedule'">
          <span class="stm-schedule">{{ scheduleDesc(record) }}</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-badge
            :status="record.status === 'enabled' ? 'processing' : 'default'"
            :text="record.status === 'enabled' ? '启用中' : '已暂停'"
          />
        </template>
        <template v-else-if="column.key === 'nextRunAt'">{{ formatTime(record.nextRunAt) }}</template>
        <template v-else-if="column.key === 'lastRunAt'">{{ formatTime(record.lastRunAt) }}</template>
        <template v-else-if="column.key === 'stats'">
          <span>{{ record.runCount || 0 }}</span>
          <span v-if="record.failCount > 0" class="stm-fail"> / {{ record.failCount }}失败</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space :size="0">
            <a-button v-if="record.status === 'enabled'" type="link" size="small" @click="onPause(record)">暂停</a-button>
            <a-button v-else type="link" size="small" @click="onResume(record)">恢复</a-button>
            <a-tooltip title="立即执行一次（不改变调度计划）">
              <a-button type="link" size="small" @click="onRunNow(record)">执行</a-button>
            </a-tooltip>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="删除该调度任务？" @confirm="onDelete(record)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新建 / 编辑弹窗 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? '编辑调度任务' : '新建调度任务'"
      width="640px"
      :confirm-loading="saving"
      @ok="onSave"
    >
      <a-form layout="vertical" class="stm-form">
        <a-form-item label="任务名称" required>
          <a-input v-model:value="form.taskName" :maxlength="200" placeholder="例如：每日早报深度研究" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="执行类型" required>
              <!-- 创建后不允许切换执行类型（target_mode 不可更新，避免关联字段错乱） -->
              <a-select
                v-model:value="form.targetMode"
                :options="targetModeOptions"
                :disabled="!!editingId"
                @change="onTargetModeChange"
              />
            </a-form-item>
          </a-col>
          <a-col v-if="form.targetMode === 'agent'" :span="12">
            <a-form-item label="选择智能体" required>
              <a-select
                v-model:value="form.agentId"
                :options="agentOptions"
                show-search
                option-filter-prop="label"
                placeholder="搜索并选择智能体"
              />
            </a-form-item>
          </a-col>
          <a-col v-else-if="form.targetMode === 'team'" :span="12">
            <a-form-item label="专家团队">
              <a-input disabled value="默认专家团队" />
            </a-form-item>
          </a-col>
          <a-col v-else-if="form.targetMode === 'skill'" :span="12">
            <a-form-item label="技能包" required>
              <a-select
                v-model:value="form.skillPackageId"
                :options="skillPackageOptions"
                show-search
                option-filter-prop="label"
                placeholder="搜索并选择技能包"
                @change="onSkillPackageChange"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row v-if="form.targetMode === 'skill'" :gutter="12">
          <a-col :span="12">
            <a-form-item label="技能脚本" required>
              <a-select
                v-model:value="form.skillScriptId"
                :options="skillScriptOptions"
                show-search
                option-filter-prop="label"
                :placeholder="form.skillPackageId ? '选择技能脚本' : '请先选择技能包'"
                :disabled="!form.skillPackageId"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="脚本说明">
              <a-input :value="selectedSkillScript?.description || selectedSkillScript?.name || ''" disabled />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="form.targetMode === 'deep_research' ? '研究主题' : '执行指令'" required>
          <a-textarea
            v-model:value="form.prompt"
            :rows="3"
            :placeholder="form.targetMode === 'deep_research' ? '例如：分析近期低空经济政策动向与投资机会' : '例如：总结昨日系统风险事件并给出处置建议'"
          />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="调度类型" required>
              <a-select v-model:value="form.scheduleType" :options="scheduleTypeOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item v-if="form.scheduleType === 'cron'" label="Cron 表达式" required>
              <a-input v-model:value="form.cronExpression" placeholder="0 9 * * *" />
              <div class="stm-hint">5 段式（分 时 日 月 周）：0 9 * * * = 每天 09:00</div>
            </a-form-item>
            <a-form-item v-else-if="form.scheduleType === 'interval'" label="间隔（秒）" required>
              <a-input-number v-model:value="form.intervalSeconds" :min="60" :step="60" style="width: 100%" />
              <div class="stm-hint">最小 60 秒</div>
            </a-form-item>
            <a-form-item v-else label="执行时间" required>
              <a-date-picker v-model:value="runAtValue" show-time style="width: 100%" placeholder="选择执行时间" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-alert
          type="info"
          show-icon
          message="调度触发后将自动生成异步任务，执行进度与结果在「异步任务」Tab 查看"
        />
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  listScheduledTasks,
  createScheduledTask,
  updateScheduledTask,
  pauseScheduledTask,
  resumeScheduledTask,
  runScheduledTaskNow,
  deleteScheduledTask,
  type AgentScheduledTaskDTO,
  type ScheduledTaskSavePayload,
  type ScheduledSkillInfo,
} from '@/api/aiAgent'
import { getAgentRegistry } from '@/api/agent'
import { getSkills, type SkillPackage } from '@/api/skill'

const loading = ref(false)
const items = ref<AgentScheduledTaskDTO[]>([])
const statusFilter = ref<string | undefined>(undefined)
const statusOptions = [
  { label: '启用中', value: 'enabled' },
  { label: '已暂停', value: 'paused' },
]
const page = reactive({ current: 1, pageSize: 10, total: 0 })

const columns = [
  { title: '任务名称', dataIndex: 'taskName', key: 'taskName', ellipsis: true },
  { title: '执行类型', key: 'targetMode', width: 110 },
  { title: '调度规则', key: 'schedule', width: 190 },
  { title: '状态', key: 'status', width: 90 },
  { title: '下次执行', key: 'nextRunAt', width: 160 },
  { title: '最近执行', key: 'lastRunAt', width: 160 },
  { title: '触发/失败', key: 'stats', width: 100, align: 'center' as const },
  { title: '操作', key: 'action', width: 210, align: 'center' as const },
]

const pagination = computed(() => ({
  current: page.current,
  pageSize: page.pageSize,
  total: page.total,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
}))

// ── 表单 ──
const targetModeOptions = [
  { label: '深度研究', value: 'deep_research' },
  { label: '单智能体', value: 'agent' },
  { label: '智能体团队', value: 'team' },
  { label: '技能', value: 'skill' },
]
const scheduleTypeOptions = [
  { label: 'Cron 定时', value: 'cron' },
  { label: '固定间隔', value: 'interval' },
  { label: '单次执行', value: 'once' },
]
const agentOptions = ref<{ label: string; value: number }[]>([])

// 技能（skill 模式）：包 → 脚本级联选择
const skillPackages = ref<SkillPackage[]>([])
const skillPackageOptions = computed(() =>
  skillPackages.value
    .filter((p) => p.enabled !== false)
    .map((p) => ({ label: p.name, value: p.package_id })),
)
const skillScriptOptions = computed(() => {
  const pkg = skillPackages.value.find((p) => p.package_id === form.skillPackageId)
  return (pkg?.scripts || [])
    .filter((s) => s.enabled !== false)
    .map((s) => ({ label: s.name, value: s.script_id }))
})
const selectedSkillPackage = computed(() =>
  skillPackages.value.find((p) => p.package_id === form.skillPackageId),
)
const selectedSkillScript = computed(() =>
  selectedSkillPackage.value?.scripts?.find((s) => s.script_id === form.skillScriptId),
)

const modalOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const runAtValue = ref<Dayjs | null>(null)

const defaultForm = () => ({
  taskName: '',
  description: '',
  targetMode: 'deep_research',
  agentId: undefined as number | undefined,
  skillPackageId: undefined as string | undefined,
  skillScriptId: undefined as string | undefined,
  prompt: '',
  scheduleType: 'cron',
  cronExpression: '',
  intervalSeconds: 3600 as number | undefined,
})
const form = reactive(defaultForm())

// ── 展示辅助 ──
function modeLabel(m?: string) {
  return ({ deep_research: '深度研究', agent: '智能体', team: '专家团队', skill: '技能' } as Record<string, string>)[m || ''] || (m || '—')
}
function modeColor(m?: string) {
  return ({ deep_research: 'geekblue', agent: 'green', team: 'purple', skill: 'cyan' } as Record<string, string>)[m || ''] || 'default'
}
function scheduleDesc(r: AgentScheduledTaskDTO) {
  if (r.scheduleType === 'cron') return `Cron：${r.cronExpression || '—'}`
  if (r.scheduleType === 'interval') return `每 ${r.intervalSeconds ?? '—'} 秒`
  return `单次：${formatTime(r.runAt)}`
}
function formatTime(t?: string | null) {
  if (!t) return '—'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// ── 列表 ──
async function reload() {
  loading.value = true
  try {
    const res = await listScheduledTasks({
      status: statusFilter.value || undefined,
      page: page.current,
      size: page.pageSize,
    })
    items.value = res.items || []
    page.total = res.total || 0
  } catch (e: any) {
    message.error(e?.message || '加载调度任务失败')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.current = 1
  reload()
}

function onTableChange(p: any) {
  page.current = p.current
  page.pageSize = p.pageSize
  reload()
}

// ── 新建 / 编辑 ──
function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  runAtValue.value = null
  modalOpen.value = true
}

function openEdit(record: AgentScheduledTaskDTO) {
  editingId.value = record.id
  form.taskName = record.taskName
  form.description = record.description || ''
  form.targetMode = record.targetMode
  form.agentId = record.agentId ?? undefined
  const si = record.skillInfo
  form.skillPackageId = si?.package_id || undefined
  form.skillScriptId = si?.script_id || undefined
  form.prompt = record.prompt
  form.scheduleType = record.scheduleType
  form.cronExpression = record.cronExpression || ''
  form.intervalSeconds = record.intervalSeconds ?? undefined
  runAtValue.value = record.runAt ? dayjs(record.runAt) : null
  modalOpen.value = true
}

function onTargetModeChange() {
  if (form.targetMode !== 'agent') form.agentId = undefined
  if (form.targetMode !== 'skill') {
    form.skillPackageId = undefined
    form.skillScriptId = undefined
  }
}

/** 切换技能包后重置脚本选择 */
function onSkillPackageChange() {
  form.skillScriptId = undefined
}

async function onSave() {
  if (!form.taskName.trim()) { message.warning('请填写任务名称'); return }
  if (!form.prompt.trim()) {
    message.warning(form.targetMode === 'deep_research' ? '请填写研究主题' : '请填写执行指令')
    return
  }
  if (form.targetMode === 'agent' && !form.agentId) { message.warning('请选择智能体'); return }
  if (form.targetMode === 'skill' && !form.skillPackageId) { message.warning('请选择技能包'); return }
  if (form.targetMode === 'skill' && !form.skillScriptId) { message.warning('请选择技能脚本'); return }
  if (form.scheduleType === 'cron' && !form.cronExpression.trim()) { message.warning('请填写 Cron 表达式'); return }
  if (form.scheduleType === 'interval' && (!form.intervalSeconds || form.intervalSeconds < 60)) {
    message.warning('间隔不能小于 60 秒')
    return
  }
  if (form.scheduleType === 'once' && !runAtValue.value) { message.warning('请选择执行时间'); return }

  const skillInfo: ScheduledSkillInfo | null =
    form.targetMode === 'skill' && selectedSkillPackage.value && selectedSkillScript.value
      ? {
          package_id: selectedSkillPackage.value.package_id,
          package_name: selectedSkillPackage.value.name,
          script_id: selectedSkillScript.value.script_id,
          script_name: selectedSkillScript.value.name,
        }
      : null

  const payload: ScheduledTaskSavePayload = {
    task_name: form.taskName.trim(),
    description: form.description || null,
    target_mode: form.targetMode,
    agent_id: form.targetMode === 'agent' ? form.agentId! : null,
    team_id: null,
    skill_info: skillInfo,
    prompt: form.prompt.trim(),
    schedule_type: form.scheduleType,
    cron_expression: form.scheduleType === 'cron' ? form.cronExpression.trim() : null,
    interval_seconds: form.scheduleType === 'interval' ? form.intervalSeconds! : null,
    run_at: form.scheduleType === 'once' && runAtValue.value
      ? runAtValue.value.format('YYYY-MM-DD HH:mm:ss')
      : null,
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateScheduledTask(editingId.value, payload)
      message.success('调度任务已更新')
    } else {
      await createScheduledTask(payload)
      message.success('调度任务已创建')
    }
    modalOpen.value = false
    await reload()
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ── 操作 ──
async function onPause(record: AgentScheduledTaskDTO) {
  try {
    await pauseScheduledTask(record.id)
    message.success('已暂停调度')
    await reload()
  } catch (e: any) {
    message.error(e?.message || '暂停失败')
  }
}

async function onResume(record: AgentScheduledTaskDTO) {
  try {
    await resumeScheduledTask(record.id)
    message.success('已恢复调度')
    await reload()
  } catch (e: any) {
    message.error(e?.message || '恢复失败')
  }
}

async function onRunNow(record: AgentScheduledTaskDTO) {
  try {
    const res = await runScheduledTaskNow(record.id)
    message.success(res.message || '已触发执行，请在异步任务 Tab 查看进度')
  } catch (e: any) {
    message.error(e?.message || '触发失败')
  }
}

async function onDelete(record: AgentScheduledTaskDTO) {
  try {
    await deleteScheduledTask(record.id)
    message.success('已删除')
    await reload()
  } catch (e: any) {
    message.error(e?.message || '删除失败')
  }
}

onMounted(() => {
  void reload()
  // 加载智能体列表（agent 模式选择用）
  getAgentRegistry()
    .then((reg: any) => {
      agentOptions.value = (reg?.agents || []).map((a: any) => ({ label: a.name, value: a.id }))
    })
    .catch(() => { /* 静默：选择器留空 */ })
  // 加载技能包列表（skill 模式级联选择用）
  getSkills({ enabled: true })
    .then((res) => { skillPackages.value = res.packages || [] })
    .catch(() => { /* 静默：选择器留空 */ })
})
</script>

<style scoped>
.stm-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.stm-schedule { font-size: 13px; color: var(--fg-secondary); }
.stm-fail { color: var(--err); }
.stm-form { margin-top: 8px; }
.stm-hint { font-size: 12px; color: var(--fg-muted); margin-top: 4px; }
</style>
