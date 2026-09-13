<template>
  <div class="agent-management">
    <!-- 顶部工具栏 -->
    <div class="page-header">
      <h2 class="page-title">🤖 {{ t('agentMgmt.pageTitle') }}</h2>
      <div class="header-actions">
        <a-button @click="loadStats">
          <ReloadOutlined :spin="loadingStats" /> {{ t('agentMgmt.refreshMonitor') }}
        </a-button>
        <a-button type="primary" @click="openCreateModal">
          <PlusOutlined /> {{ t('agentMgmt.createAgent') }}
        </a-button>
      </div>
    </div>

    <!-- 监控统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <div class="stat-label">{{ t('agentMgmt.statTotalAgents') }}</div>
          <div class="stat-value">{{ stats.total_agents || 0 }}</div>
          <div class="stat-meta">
            <span class="active">{{ t('agentMgmt.enabledCount', { count: stats.active_agents || 0 }) }}</span>
            <span class="inactive">{{ t('agentMgmt.disabledCount', { count: stats.inactive_agents || 0 }) }}</span>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <div class="stat-label">{{ t('agentMgmt.statActiveSessions') }}</div>
          <div class="stat-value">{{ stats.active_sessions || 0 }}</div>
          <div class="stat-meta">
            <span>{{ t('agentMgmt.totalSessions', { count: stats.total_sessions || 0 }) }}</span>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <div class="stat-label">{{ t('agentMgmt.statTodayInvocations') }}</div>
          <div class="stat-value">{{ stats.today_invocations || 0 }}</div>
          <div class="stat-meta">
            <span class="success">{{ t('agentMgmt.successCount', { count: stats.today_success || 0 }) }}</span>
            <span class="error">{{ t('agentMgmt.failedCount', { count: stats.today_error || 0 }) }}</span>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" class="stat-card">
          <div class="stat-label">{{ t('agentMgmt.avgDuration') }}</div>
          <div class="stat-value">{{ stats.avg_duration_ms || 0 }}ms</div>
          <div class="stat-meta">
            <span>{{ t('agentMgmt.traceCount', { count: stats.total_traces || 0 }) }}</span>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 筛选与列表 -->
    <a-card size="small" class="list-card">
      <div class="list-toolbar">
        <a-space>
          <a-select
            v-model:value="filterType"
            :placeholder="t('agentMgmt.implType')"
            style="width: 140px"
            allow-clear
            @change="loadAgents"
          >
            <a-select-option v-for="item in agentTypeDict" :key="item.item_code" :value="item.item_code">
              {{ item.item_name }}
            </a-select-option>
          </a-select>
          <a-select
            v-model:value="filterCategory"
            :placeholder="t('agentMgmt.category')"
            style="width: 140px"
            allow-clear
            @change="loadAgents"
          >
            <a-select-option v-for="item in agentCategoryDict" :key="item.item_code" :value="item.item_code">
              {{ item.item_name }}
            </a-select-option>
          </a-select>
          <a-select
            v-model:value="filterStatus"
            :placeholder="t('skillHub.status')"
            style="width: 120px"
            allow-clear
            @change="loadAgents"
          >
            <a-select-option :value="true">{{ t('skillHub.enabled') }}</a-select-option>
            <a-select-option :value="false">{{ t('skillHub.disabled') }}</a-select-option>
          </a-select>
          <a-input-search
            v-model:value="keyword"
            :placeholder="t('agentMgmt.searchAgent')"
            style="width: 240px"
            allow-clear
            @search="loadAgents"
          />
          <a-button @click="resetFilter">{{ t('common.reset') }}</a-button>
        </a-space>
      </div>

      <a-spin :spinning="loading">
        <a-table
          :columns="columns"
          :data-source="agents"
          :pagination="pagination"
          row-key="id"
          @change="handleTableChange"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'agent_type'">
              <a-tag :color="dictColor(agentTypeDict, record.agent_type)">
                {{ dictLabel(agentTypeDict, record.agent_type) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'category'">
              <a-tag :color="dictColor(agentCategoryDict, record.category)">
                {{ dictLabel(agentCategoryDict, record.category || '') }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'model_config'">
              <div v-if="record.model_config?.model" class="model-cell">
                <a-tag color="blue">{{ record.model_config.provider }}</a-tag>
                <span class="model-name">{{ record.model_config.model }}</span>
                <a-tag v-if="record.model_config.model_code" color="green">
                  {{ t('agentMgmt.systemKey') }}
                </a-tag>
              </div>
              <span v-else class="muted">—</span>
            </template>
            <template v-else-if="column.key === 'is_active'">
              <a-switch
                :checked="record.is_active"
                @change="(val: boolean) => toggleActive(record, val)"
                :checked-children="t('skillHub.enabled')"
                :un-checked-children="t('skillHub.disabled')"
              />
            </template>
            <template v-else-if="column.key === 'invocation_count'">
              <span class="num-cell">{{ record.invocation_count || 0 }}</span>
            </template>
            <template v-else-if="column.key === 'avg_duration'">
              <span class="num-cell">{{ record.avg_duration || 0 }}ms</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space>
                <a-tooltip :title="t('agentMgmt.viewDetail')">
                  <a-button type="link" size="small" @click="openDetailDrawer(record)">
                    <EyeOutlined /> {{ t('agentMgmt.detail') }}
                  </a-button>
                </a-tooltip>
                <a-tooltip :title="t('common.edit')">
                  <a-button type="link" size="small" @click="openEditModal(record)">
                    <EditOutlined /> {{ t('common.edit') }}
                  </a-button>
                </a-tooltip>
                <a-tooltip :title="t('agentMgmt.viewTrace')">
                  <a-button type="link" size="small" @click="openTraceDrawer(record)">
                    <BranchesOutlined /> {{ t('agentMgmt.trace') }}
                  </a-button>
                </a-tooltip>
                <a-tooltip :title="t('agentMgmt.configSkillRule')">
                  <a-button type="link" size="small" @click="openSkillRuleModal(record)">
                    <ToolOutlined /> {{ t('agentMgmt.rule') }}
                  </a-button>
                </a-tooltip>
                <a-popconfirm
                  :title="t('agentMgmt.deleteAgentConfirm')"
                  :ok-text="t('common.confirm')"
                  :cancel-text="t('common.cancel')"
                  @confirm="handleDelete(record)"
                >
                  <a-button type="link" size="small" danger>
                    <DeleteOutlined /> {{ t('common.delete') }}
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-spin>
    </a-card>

    <!-- Agent 创建/编辑弹窗 -->
    <AgentFormModal
      v-model:visible="formModalVisible"
      :agent-id="editingAgent?.id"
      :agent-data="editingAgent"
      @success="handleFormSuccess"
    />

    <!-- Agent 详情抽屉 -->
    <AgentDetailDrawer
      v-model:visible="detailDrawerVisible"
      :agent-id="detailAgent?.id"
    />

    <!-- 技能规则抽屉 -->
    <a-drawer
      v-model:open="skillRuleDrawerVisible"
      :title="t('agentMgmt.skillRuleTitle', { name: skillRuleAgent?.name || '' })"
      width="720"
      :destroy-on-close="true"
    >
      <div class="agent-rule-toolbar">
        <a-button type="primary" size="small" @click="openCreateAgentRule">
          <PlusOutlined /> {{ t('agentMgmt.createRule') }}
        </a-button>
        <a-button size="small" @click="skillRuleAgent && loadAgentRules(skillRuleAgent.name)">
          <ReloadOutlined /> {{ t('agentMgmt.refresh') }}
        </a-button>
      </div>

      <a-spin :spinning="agentRulesLoading">
        <a-table
          :columns="agentRuleColumns"
          :data-source="agentRules"
          :pagination="false"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'priority'">
              <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
            </template>
            <template v-else-if="column.key === 'is_active'">
              <a-switch
                :checked="record.is_active"
                @change="(val: boolean) => toggleAgentRuleActive(record, val)"
                size="small"
              />
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space>
                <a-button type="link" size="small" @click="openEditAgentRule(record)">
                  <EditOutlined /> {{ t('common.edit') }}
                </a-button>
                <a-popconfirm
                  :title="t('skillHub.deleteRuleConfirm')"
                  :ok-text="t('common.confirm')"
                  :cancel-text="t('common.cancel')"
                  @confirm="handleDeleteAgentRule(record)"
                >
                  <a-button type="link" size="small" danger>
                    <DeleteOutlined /> {{ t('common.delete') }}
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
        <a-empty v-if="!agentRulesLoading && agentRules.length === 0" :description="t('agentMgmt.noSkillRules')" />
      </a-spin>
    </a-drawer>

    <!-- 技能规则表单弹窗 -->
    <SkillRuleFormModal
      v-model:visible="ruleFormVisible"
      :rule-id="editingRule?.id"
      :rule-data="editingRule"
      :default-agent-name="skillRuleAgent?.name"
      @success="handleAgentRuleFormSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  ToolOutlined,
  BranchesOutlined,
} from '@ant-design/icons-vue'
import {
  getAgentList,
  deleteAgent,
  toggleAgent,
  getAgentStats,
  type AgentConfig,
  type AgentStats,
} from '@/api/agentConfig'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'
import {
  getSkillRules,
  updateSkillRule,
  deleteSkillRule,
  type SkillRule,
} from '@/api/skillRule'
import AgentFormModal from './components/AgentFormModal.vue'
import AgentDetailDrawer from './components/AgentDetailDrawer.vue'
import SkillRuleFormModal from '@/views/admin/ai/skill/components/SkillRuleFormModal.vue'

// ── 状态 ─────────────────────────────────────────────────────────────────────
const { t } = useI18n()
const loading = ref(false)
const loadingStats = ref(false)
const agents = ref<AgentConfig[]>([])
const stats = ref<AgentStats>({
  total_agents: 0,
  active_agents: 0,
  inactive_agents: 0,
  active_sessions: 0,
  total_sessions: 0,
  today_invocations: 0,
  today_success: 0,
  today_error: 0,
  avg_duration_ms: 0,
  total_traces: 0,
})

const keyword = ref('')
const filterType = ref<string | undefined>()
const filterCategory = ref<string | undefined>()
const filterStatus = ref<boolean | undefined>()

// 字典数据
const agentTypeDict = ref<DictionaryItem[]>([])
const agentCategoryDict = ref<DictionaryItem[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => t('common.total', { total }),
})

const formModalVisible = ref(false)
const editingAgent = ref<AgentConfig | null>(null)

const detailDrawerVisible = ref(false)
const detailAgent = ref<AgentConfig | null>(null)

// ── 技能规则相关 ─────────────────────────────────────────────────────────────
const skillRuleDrawerVisible = ref(false)
const skillRuleAgent = ref<AgentConfig | null>(null)
const agentRules = ref<SkillRule[]>([])
const agentRulesLoading = ref(false)
const ruleFormVisible = ref(false)
const editingRule = ref<SkillRule | null>(null)

// ── 表格列 ───────────────────────────────────────────────────────────────────
const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: t('agentMgmt.agentCode'), dataIndex: 'agent_code', key: 'agent_code', width: 160 },
  { title: t('agentMgmt.colName'), dataIndex: 'name', key: 'name', width: 180 },
  { title: t('agentMgmt.implType'), dataIndex: 'agent_type', key: 'agent_type', width: 110 },
  { title: t('agentMgmt.category'), dataIndex: 'category', key: 'category', width: 120 },
  { title: t('agentMgmt.colModelConfig'), key: 'model_config', width: 220 },
  { title: t('skillHub.status'), dataIndex: 'is_active', key: 'is_active', width: 100 },
  { title: t('agentMgmt.colInvocationCount'), key: 'invocation_count', width: 110 },
  { title: t('agentMgmt.avgDuration'), key: 'avg_duration', width: 110 },
  { title: t('agentMgmt.colSort'), dataIndex: 'sort_order', key: 'sort_order', width: 80 },
  {
    title: t('agentMgmt.colActions'),
    key: 'action',
    width: 320,
    fixed: 'right' as const,
  },
])

// ── 字典映射辅助函数 ───────────────────────────────────────────────────────────
function dictLabel(items: DictionaryItem[], code: string) {
  return items.find(i => i.item_code === code)?.item_name || code
}

function dictColor(items: DictionaryItem[], code: string) {
  return items.find(i => i.item_code === code)?.color || 'default'
}

// ── 加载数据 ──────────────────────────────────────────────────────────────────
async function loadAgents() {
  loading.value = true
  try {
    const res = await getAgentList({
      page: pagination.current,
      page_size: pagination.pageSize,
      agent_type: filterType.value,
      category: filterCategory.value,
      is_active: filterStatus.value,
      keyword: keyword.value || undefined,
    }) as any
    agents.value = res.items || []
    pagination.total = res.total || 0
  } catch (e: any) {
    message.error(t('agentMgmt.loadAgentsFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  loadingStats.value = true
  try {
    const res = await getAgentStats() as any
    stats.value = { ...stats.value, ...res }
  } catch (e) {
    // 静默失败，使用默认值
  } finally {
    loadingStats.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadAgents()
}

function resetFilter() {
  keyword.value = ''
  filterType.value = undefined
  filterCategory.value = undefined
  filterStatus.value = undefined
  pagination.current = 1
  loadAgents()
}

async function loadDicts() {
  try {
    const [types, cats] = await Promise.all([
      getDictionaryItems('agent_impl_type'),
      getDictionaryItems('agent_category'),
    ])
    agentTypeDict.value = types || []
    agentCategoryDict.value = cats || []
  } catch (e) {
    console.error('加载字典失败:', e)
  }
}

// ── 增删改 ────────────────────────────────────────────────────────────────────
function openCreateModal() {
  editingAgent.value = null
  formModalVisible.value = true
}

function openEditModal(record: AgentConfig) {
  editingAgent.value = record
  formModalVisible.value = true
}

async function toggleActive(record: AgentConfig, val: boolean) {
  try {
    const updated = await toggleAgent(record.id, val)
    Object.assign(record, updated)
    message.success(val ? t('agentMgmt.enabledMsg') : t('agentMgmt.disabledMsg'))
    loadStats()
  } catch (e: any) {
    message.error(t('agentMgmt.updateStatusFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  }
}

async function handleDelete(record: AgentConfig) {
  try {
    await deleteAgent(record.id)
    message.success(t('agentMgmt.deleteSuccess'))
    loadAgents()
    loadStats()
  } catch (e: any) {
    message.error(t('agentMgmt.deleteFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  }
}

function handleFormSuccess() {
  formModalVisible.value = false
  loadAgents()
  loadStats()
}

// ── 详情 ──────────────────────────────────────────────────────────────────────
function openDetailDrawer(record: AgentConfig) {
  detailAgent.value = record
  detailDrawerVisible.value = true
}

// ── 链路追踪 ──────────────────────────────────────────────────────────────────
async function openTraceDrawer(record: AgentConfig) {
  // 跳转到「调用记录」Tab，并按该 agent（agent_config.id）精确过滤调用链路
  const openExecutionTab = inject<(mode?: string, targetId?: string, label?: string) => void>('openExecutionTab')
  if (!openExecutionTab) {
    message.error(t('agentMgmt.execTabMissing'))
    return
  }
  const targetId = String(record.id)
  openExecutionTab(
    'agent',
    targetId,
    t('agentMgmt.filterAgentLabel', { name: record.name, id: targetId })
  )
}

function openSkillRuleModal(record: AgentConfig) {
  skillRuleAgent.value = record
  skillRuleDrawerVisible.value = true
  loadAgentRules(record.name)
}

async function loadAgentRules(agentName: string) {
  agentRulesLoading.value = true
  try {
    const res = await getSkillRules({
      page: 1,
      page_size: 100,
      agent_name: agentName,
    }) as any
    agentRules.value = res.items || []
  } catch (e: any) {
    message.error(t('agentMgmt.loadRulesFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  } finally {
    agentRulesLoading.value = false
  }
}

function openCreateAgentRule() {
  editingRule.value = null
  ruleFormVisible.value = true
}

function openEditAgentRule(record: SkillRule) {
  editingRule.value = record
  ruleFormVisible.value = true
}

async function toggleAgentRuleActive(record: SkillRule, val: boolean) {
  try {
    await updateSkillRule(record.id, { is_active: val })
    record.is_active = val
    message.success(val ? t('agentMgmt.enabledMsg') : t('agentMgmt.disabledMsg'))
  } catch (e: any) {
    message.error(t('agentMgmt.updateFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  }
}

async function handleDeleteAgentRule(record: SkillRule) {
  try {
    await deleteSkillRule(record.id)
    message.success(t('agentMgmt.deleteSuccess'))
    if (skillRuleAgent.value) loadAgentRules(skillRuleAgent.value.name)
  } catch (e: any) {
    message.error(t('agentMgmt.deleteFailed', { msg: e.message || t('agentMgmt.unknownError') }))
  }
}

function handleAgentRuleFormSuccess() {
  ruleFormVisible.value = false
  if (skillRuleAgent.value) loadAgentRules(skillRuleAgent.value.name)
}

const agentRuleColumns = computed(() => [
  { title: t('skillHub.ruleName'), dataIndex: 'name', key: 'name', width: 160 },
  { title: t('agentMgmt.targetSkill'), dataIndex: 'package_id', key: 'package_id', width: 140 },
  { title: t('skillHub.rulePriority'), dataIndex: 'priority', key: 'priority', width: 80 },
  { title: t('skillHub.status'), dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: t('agentMgmt.colActions'), key: 'action', width: 120, fixed: 'right' as const },
])

function priorityColor(p: number): string {
  if (p <= 10) return 'red'
  if (p <= 50) return 'orange'
  if (p <= 100) return 'blue'
  return 'default'
}

// formatConditions and truncate are kept for potential future use
// @ts-ignore
function formatConditions(c: any): string {
  if (!c) return t('agentMgmt.noCondition')
  return JSON.stringify(c, null, 2)
}

// @ts-ignore
function truncate(s: string, n: number): string {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '...' : s
}

onMounted(() => {
  loadDicts()
  loadAgents()
  loadStats()
})
</script>

<style scoped lang="less">
.model-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.model-name {
  font-weight: 600;
  color: var(--fg);
}
.muted {
  color: var(--fg-muted);
}
.form-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--fg-secondary);
}
.agent-management {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 16px 0;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--fg);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg-surface);
  border-radius: 8px;

  :deep(.ant-card-body) {
    padding: 16px;
  }
}

.stat-label {
  font-size: 13px;
  color: var(--fg-secondary);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--fg);
  line-height: 1.2;
  margin-bottom: 6px;
}

.stat-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--fg-muted);

  .success { color: var(--ok); }
  .error { color: var(--err); }
  .active { color: var(--accent); }
  .inactive { color: var(--fg-muted); }
}

.list-card {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.list-toolbar {
  margin-bottom: 12px;
}

.num-cell {
  font-family: monospace;
  font-size: 13px;
  color: var(--fg);
}

.agent-rule-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
</style>