<template>
  <div class="team-editor">
    <!-- 顶部条 -->
    <div class="editor-header">
      <div class="left">
        <a-button type="link" @click="goBack">
          <ArrowLeftOutlined /> 返回
        </a-button>
        <span class="title">{{ team?.team_name || '团队编排' }}</span>
        <a-tag v-if="team" color="blue">{{ team.team_code }}</a-tag>
      </div>
      <div class="right">
        <a-button @click="validateTopology">
          <CheckCircleOutlined /> 校验拓扑
        </a-button>
        <a-button type="primary" :loading="saving" @click="saveTopology">
          <SaveOutlined /> 保存编排
        </a-button>
      </div>
    </div>

    <div class="editor-body no-canvas">
      <!-- 左侧：成员面板 -->
      <div class="side-panel">
        <div class="panel-title">成员面板</div>
        <a-input-search
          v-model:value="memberKeyword"
          placeholder="搜索成员 / agent"
          size="small"
          class="member-search"
        />
        <div class="member-list">
          <div
            v-for="m in filteredMembers"
            :key="m.node_key"
            class="member-item"
            :class="{ selected: selectedMember === m.node_key }"
            @click="selectMember(m)"
          >
            <div class="member-row">
              <span class="m-name">
                <CrownOutlined v-if="m.is_leader" style="color:#faad14" />
                {{ m.role_name }}
              </span>
              <a-tag v-if="m.agent_code" size="small">{{ m.agent_code }}</a-tag>
            </div>
            <div class="member-sub">{{ m.node_key }} · {{ m.model || '默认模型' }}</div>
          </div>
          <a-empty v-if="filteredMembers.length === 0" description="无成员" :image="undefined" />
        </div>
        <a-button block class="add-member-btn" @click="openMemberModal">
          <PlusOutlined /> 添加成员
        </a-button>
      </div>

      <!-- 中间：DAG 编排画布（当前隐藏，仅保留逻辑） -->
      <div v-if="false" class="canvas-wrap" @drop="onDrop" @dragover.prevent>
        <VueFlow
          :nodes="nodes"
          :edges="edges"
          :fit-view-on-init="true"
          :min-zoom="0.2"
          :max-zoom="2"
          @nodes-change="onNodesChange"
          @edges-change="onEdgesChange"
          @connect="onConnect"
          @node-click="onNodeClick"
          @pane-click="onPaneClick"
        >
          <Background :gap="16" pattern-color="#c7d6e8" />
          <Controls />
          <MiniMap />
          <template #node-custom="props">
            <div
              class="flow-node"
              :class="{ leader: props.data.is_leader, active: props.data.active }"
            >
              <div class="node-role">{{ props.data.label }}</div>
              <div class="node-code">{{ props.data.agent_code }}</div>
            </div>
          </template>
        </VueFlow>

        <div class="canvas-tip">拖拽左侧成员到画布生成节点 · 连线建立依赖</div>
      </div>

      <!-- 右侧：节点属性 -->
      <div class="side-panel right">
        <div class="panel-title">节点属性</div>
        <a-empty v-if="!selectedMember" description="点击左侧成员查看属性" />
        <div v-else class="property-form">
          <a-form layout="vertical" :model="nodeForm">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="节点键 (node_key)">
                  <a-input v-model:value="nodeForm.node_key" disabled />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="角色名">
                  <a-input v-model:value="nodeForm.role_name" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="Agent 编码">
                  <a-input v-model:value="nodeForm.agent_code" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="模型">
                  <a-select v-model:value="nodeForm.model" :options="modelOptions" allow-clear />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="是否 Leader">
              <a-switch v-model:checked="nodeForm.is_leader" />
            </a-form-item>
            <a-form-item label="系统提示词">
              <a-textarea v-model:value="nodeForm.system_prompt" :rows="6" />
            </a-form-item>
          </a-form>
          <a-button danger block @click="removeSelectedNode">
            <DeleteOutlined /> 删除节点
          </a-button>
        </div>
      </div>
    </div>

    <!-- 添加成员弹窗 -->
    <a-modal
      v-model:open="memberModal"
      title="添加成员"
      @ok="submitMember"
      :confirm-loading="memberSubmitting"
    >
      <a-form layout="vertical">
        <a-form-item label="节点键 (node_key)" required>
          <a-input v-model:value="memberForm.node_key" placeholder="如 risk_analyst" />
        </a-form-item>
        <a-form-item label="角色名" required>
          <a-input v-model:value="memberForm.role_name" placeholder="如 风险分析师" />
        </a-form-item>
        <a-form-item label="Agent 编码">
          <a-input v-model:value="memberForm.agent_code" />
        </a-form-item>
        <a-form-item label="模型">
          <a-select v-model:value="memberForm.model" :options="modelOptions" allow-clear />
        </a-form-item>
        <a-form-item label="设为 Leader">
          <a-switch v-model:checked="memberForm.is_leader" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  VueFlow,
  useVueFlow,
  MarkerType,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge
} from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  SaveOutlined,
  PlusOutlined,
  CrownOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import * as api from '@/api/agentTeam'

const router = useRouter()
const props = defineProps<{ teamId: number }>()
const teamId = computed(() => Number(props.teamId))

const team = ref<api.TeamDetail | null>(null)
const members = ref<api.TeamMember[]>([])
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const saving = ref(false)
const selectedMember = ref<string | null>(null)
const memberKeyword = ref('')
const memberModal = ref(false)
const memberSubmitting = ref(false)

const modelOptions = [
  { label: 'deepseek-chat', value: 'deepseek-chat' },
  { label: 'gpt-4o', value: 'gpt-4o' },
  { label: 'claude-3-5-sonnet', value: 'claude-3-5-sonnet' },
  { label: 'qwen-max', value: 'qwen-max' }
]

const filteredMembers = computed(() => {
  const k = memberKeyword.value.trim().toLowerCase()
  if (!k) return members.value
  return members.value.filter(
    m => m.role_name.toLowerCase().includes(k) || (m.agent_code || '').toLowerCase().includes(k)
  )
})

const nodeForm = ref<api.TeamMember>({
  node_key: '', role_name: '', agent_code: '', model: '', is_leader: false, system_prompt: ''
})
const memberForm = ref<Partial<api.TeamMember>>({
  node_key: '', role_name: '', agent_code: '', model: '', is_leader: false
})

const goBack = () => {
  // 在 admin tab 框架内时，通知父级关闭本 tab 并回到团队列表
  window.dispatchEvent(new CustomEvent('close-agent-team-editor', { bubbles: true }))
  // 兜底：若非 tab 框架内直接访问（/admin/agent-team/:id），回到团队列表路由
  setTimeout(() => {
    if (router.currentRoute.value.path.startsWith('/admin/agent-team/')) {
      router.push('/admin?tab=agent-team')
    }
  }, 0)
}
const { addNodes, addEdges, project, getViewport } = useVueFlow()

// ── 数据加载 ─────────────────────────────────────────
const fetchDetail = async () => {
  try {
    const res = await api.getTeam(teamId.value)
    const data = (res as any) || {}
    team.value = data
    members.value = data.members || []
    edges.value = ((data.edges || []) as any[]).map((e: any) => ({
      id: 'e_' + e.id,
      source: String(e.source),
      target: String(e.target),
      label: e.edge_type || '',
      markerEnd: MarkerType.ArrowClosed
    }))
    syncNodesFromMembers()
  } catch (e: any) {
    message.error('加载团队失败：' + (e?.message || e))
  }
}

const syncNodesFromMembers = () => {
  nodes.value = members.value.map((m, i) => ({
    id: m.node_key,
    type: 'custom',
    position: { x: 80 + (i % 4) * 220, y: 80 + Math.floor(i / 4) * 140 },
    data: {
      label: m.role_name,
      agent_code: m.agent_code,
      is_leader: m.is_leader,
      active: false
    }
  }))
}

const onNodesChange = (changes: any[]) => { nodes.value = applyNodeChanges(changes, nodes.value as any) as any }
const onEdgesChange = (changes: any[]) => { edges.value = applyEdgeChanges(changes, edges.value as any) as any }

const onConnect = (conn: any) => {
  addEdges([{
    id: `e_${conn.source}_${conn.target}_${Date.now()}`,
    source: conn.source,
    target: conn.target,
    markerEnd: MarkerType.ArrowClosed
  }])
}

// ── 拖拽生成节点（画布隐藏时保留逻辑，待恢复） ──────
const onDrop = (ev: DragEvent) => {
  ev.preventDefault()
  const key = (ev as any).dataTransfer?.getData('node_key')
  const m = members.value.find(x => x.node_key === key)
  if (!m) return
  if (nodes.value.some(n => n.id === m.node_key)) {
    message.warning('该成员已在画布中')
    return
  }
  const position = project({ x: ev.clientX, y: ev.clientY })
  addNodes([{
    id: m.node_key,
    type: 'custom',
    position,
    data: { label: m.role_name, agent_code: m.agent_code, is_leader: m.is_leader, active: false }
  }])
}

// ── 选择 / 属性 ──────────────────────────────────────
const onNodeClick = (e: any) => {
  const id = e.node.id
  selectedMember.value = id
  const m = members.value.find(x => x.node_key === id)
  if (m) nodeForm.value = { ...m }
}
const onPaneClick = () => { selectedMember.value = null }

const selectMember = (m: api.TeamMember) => {
  selectedMember.value = m.node_key
  nodeForm.value = { ...m }
  // 高亮画布节点
  nodes.value = nodes.value.map(n => ({
    ...n,
    data: { ...n.data, active: n.id === m.node_key }
  }))
}

const removeSelectedNode = () => {
  if (!selectedMember.value) return
  members.value = members.value.filter(m => m.node_key !== selectedMember.value)
  nodes.value = nodes.value.filter(n => n.id !== selectedMember.value)
  edges.value = edges.value.filter(
    e => e.source !== selectedMember.value && e.target !== selectedMember.value
  )
  selectedMember.value = null
  message.success('已移除节点')
}

// ── 保存 ─────────────────────────────────────────────
const saveTopology = async () => {
  saving.value = true
  try {
    // 以画布 nodes 为准同步成员列表（role_name/agent_code/is_leader 取自节点 data）
    members.value = nodes.value.map(n => ({
      ...(members.value.find(m => m.node_key === n.id) || {}),
      node_key: n.id,
      role_name: n.data.label,
      agent_code: n.data.agent_code,
      is_leader: n.data.is_leader
    }))

    // 构建 §6.2 拓扑保存载荷：成员 + 边 + 画布布局
    const graphMembers = nodes.value.map(n => {
      const m = members.value.find(x => x.node_key === n.id) || ({} as api.TeamMember)
      const agentConfigId = (m as any).agent_id
      if (!agentConfigId) {
        throw new Error(`节点「${n.data.label || n.id}」未关联 Agent，无法保存拓扑`)
      }
      return {
        node_key: n.id,
        agent_config_id: Number(agentConfigId),
        role_name: (m.role_name as string) || n.data.label,
        model: (m.model as string) || undefined,
        system_prompt: (m.system_prompt as string) || undefined
      }
    })

    const graphEdges = edges.value.map(e => ({
      from_node_key: String(e.source),
      to_node_key: String(e.target),
      edge_config: (e as any).edge_config || {}
    }))

    // 画布布局快照（对应后端 AgentTeam.graph 字段，结构对齐 TeamGraphLayout）
    const layout = {
      nodes: nodes.value.map(n => ({ node_key: n.id, x: n.position.x, y: n.position.y })),
      viewport: (typeof getViewport === 'function' ? getViewport() : undefined) || null
    }

    await api.saveGraph(teamId.value, {
      members: graphMembers,
      edges: graphEdges,
      layout
    })
    message.success('编排已保存')
  } catch (e: any) {
    message.error('保存失败：' + (e?.message || e))
  } finally {
    saving.value = false
  }
}

const validateTopology = async () => {
  try {
    await api.validateTeam(teamId.value)
    message.success('拓扑校验通过')
  } catch (e: any) {
    message.error('校验未通过：' + (e?.message || e))
  }
}

// ── 添加成员 ─────────────────────────────────────────
const openMemberModal = () => {
  memberForm.value = { node_key: '', role_name: '', agent_code: '', model: '', is_leader: false }
  memberModal.value = true
}
const submitMember = () => {
  if (!memberForm.value.node_key || !memberForm.value.role_name) {
    message.warning('请填写节点键与角色名')
    return
  }
  if (members.value.some(m => m.node_key === memberForm.value.node_key)) {
    message.warning('节点键已存在')
    return
  }
  const m: api.TeamMember = {
    node_key: memberForm.value.node_key!,
    role_name: memberForm.value.role_name!,
    agent_code: memberForm.value.agent_code,
    model: memberForm.value.model,
    is_leader: memberForm.value.is_leader
  }
  members.value.push(m)
  syncNodesFromMembers()
  memberModal.value = false
  message.success('成员已添加，记得保存编排')
}

watch(() => props.teamId, () => {
  fetchDetail()
})

onMounted(fetchDetail)
</script>

<style scoped lang="less">
.team-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-page);
}
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #eef0f3;
}
.editor-header .left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.editor-header .title {
  font-size: 16px;
  font-weight: 700;
}
.editor-body {
  flex: 1;
  display: flex;
  min-height: 0;

  &.no-canvas .side-panel.right {
    flex: 1;
    width: auto;
    align-items: center;
    justify-content: flex-start;
    background: #f7fafd;
    padding: 24px;

    .panel-title {
      width: 100%;
      max-width: 820px;
      margin-bottom: 16px;
    }

    .property-form {
      width: 100%;
      max-width: 820px;
      background: #fff;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    }

    .ant-empty {
      width: 100%;
      max-width: 820px;
      margin-top: 40px;
    }
  }
}
.side-panel {
  width: 270px;
  background: #fff;
  border-right: 1px solid #eef0f3;
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: auto;
}
.side-panel.right {
  border-right: none;
  border-left: 1px solid #eef0f3;
}
.panel-title {
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text-primary);
}
.member-search {
  margin-bottom: 10px;
}
.member-list {
  flex: 1;
  overflow: auto;
}
.member-item {
  padding: 8px 10px;
  border: 1px solid #eef0f3;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: grab;
  transition: all 0.2s;
  &:hover {
    border-color: var(--accent-cyan);
    background: rgba(0, 212, 255, 0.05);
  }
  &.selected {
    border-color: var(--accent-cyan);
    background: rgba(0, 212, 255, 0.1);
  }
}
.member-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-name {
  font-weight: 600;
  font-size: 13px;
}
.member-sub {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
  font-family: monospace;
}
.add-member-btn {
  margin-top: 8px;
}
.canvas-wrap {
  flex: 1;
  position: relative;
  background: #f7fafd;
}
.canvas-tip {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
  pointer-events: none;
}
.flow-node {
  min-width: 120px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 2px solid #4f9bff;
  background: #eaf3ff;
  text-align: center;
  &.leader {
    border-color: #faad14;
    background: #fff7e6;
  }
  &.active {
    box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.3);
  }
}
.node-role {
  font-weight: 700;
  font-size: 13px;
}
.node-code {
  font-size: 11px;
  color: #6b7a90;
  font-family: monospace;
}
</style>
