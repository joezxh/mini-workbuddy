<template>
  <div class="mgr">
    <div class="mgr-bar">
      <a-button type="primary" size="small" @click="addAgent">＋ 新增 Agent</a-button>
      <span class="hint">展开卡片编辑触发规则 / Prompt / 工具绑定 · 优先级决定编排顺序</span>
      <span class="spacer"></span>
      <span class="hint">{{ agents.length }} 个插件</span>
    </div>

    <div class="mgr-body">
      <div
        v-for="a in agents"
        :key="a.key"
        class="ag-card"
        :class="{ active: activeKey === a.key, open: expanded.has(a.key) }"
      >
        <div class="ag-main">
          <div class="ag-ic">{{ a.icon }}</div>
          <div class="ag-info" @click="emit('activate', a.key)">
            <div class="ag-nm">
              {{ a.name }}
              <span :class="['st', statusClass(a)]">{{ statusLabel(a) }}</span>
            </div>
            <div class="ag-key">{{ a.key }}</div>
            <div class="ag-desc">{{ a.desc }}</div>
            <span v-if="activeKey === a.key" :class="['reason', reasonClass(a)]">
              ● {{ a.activationLabel || '语音激活' }}
            </span>
          </div>
          <div class="prio">
            优先级 <span class="num">{{ a.priority }}</span>
            <span class="icon-btn" title="提高优先级" @click.stop="emit('reorder', { key: a.key, delta: -1 })">▲</span>
            <span class="icon-btn" title="降低优先级" @click.stop="emit('reorder', { key: a.key, delta: 1 })">▼</span>
          </div>
          <div class="switch" :class="{ on: a.enabled }" @click.stop="emit('toggle', a.key)"></div>
          <span class="icon-btn" @click.stop="toggleExpand(a.key)">{{ expanded.has(a.key) ? '▴' : '▾' }}</span>
        </div>

        <div class="ag-detail">
          <div class="field">
            <label>触发规则（意图 / 关键词）</label>
            <div class="rules">
              <span v-for="(r, idx) in a.rules" :key="idx" class="rule">
                {{ r }} <span class="x" @click="removeRule(a, idx)">×</span>
              </span>
              <a-button size="small" @click="addRule(a)">＋ 规则</a-button>
            </div>
          </div>
          <div class="field">
            <label>System Prompt</label>
            <a-textarea
              :value="a.prompt"
              rows="3"
              placeholder="输入该 Agent 的系统提示词"
              @update:value="(v: string) => emit('update', { ...a, prompt: v })"
            />
          </div>
          <div class="field">
            <label>工具绑定</label>
            <div class="tools">
              <label v-for="t in allTools" :key="t">
                <input
                  type="checkbox"
                  :checked="a.tools.includes(t)"
                  @change="toggleTool(a, t)"
                /> {{ t }}
              </label>
            </div>
          </div>
          <div class="detail-actions">
            <a-button size="small" type="primary" @click="emit('save', a)">保存设计</a-button>
            <a-button size="small" @click="emit('activate', a.key)">设为活跃</a-button>
            <a-button size="small" danger @click="emit('remove', a.key)">删除</a-button>
          </div>
        </div>
      </div>
      <a-empty v-if="!agents.length" description="暂无 Agent" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AgentView } from '../types'

const props = defineProps<{
  agents: AgentView[]
  activeKey: string
}>()

const emit = defineEmits<{
  activate: [key: string]
  toggle: [key: string]
  add: [agent: AgentView]
  remove: [key: string]
  update: [agent: AgentView]
  save: [agent: AgentView]
  reorder: [payload: { key: string; delta: number }]
}>()

const expanded = ref<Set<string>>(new Set())
const allTools = ['商品检索', '关税计算', '库存查询', '物流查询', '优惠券发放', '人工转接', '工单创建']

function toggleExpand(key: string) {
  const next = new Set(expanded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}

function statusClass(a: AgentView): string {
  if (!a.enabled) return 'off'
  return a.runtimeStatus === 'running' ? 'ok' : 'cfg'
}

function statusLabel(a: AgentView): string {
  if (!a.enabled) return '未启用'
  return a.runtimeStatus === 'running' ? '运行中' : '待命'
}

function reasonClass(a: AgentView): string {
  if (a.activationReason === 'voice') return 'voice'
  if (a.activationReason === 'text') return 'text'
  if (a.activationReason === 'intent') return 'intent'
  if (a.activationReason === 'processing') return 'proc'
  return 'default'
}

function addRule(a: AgentView) {
  const rule = window.prompt('新增触发规则（意图 / 关键词）')
  if (rule && rule.trim()) emit('update', { ...a, rules: [...a.rules, rule.trim()] })
}

function removeRule(a: AgentView, idx: number) {
  emit('update', { ...a, rules: a.rules.filter((_, i) => i !== idx) })
}

function toggleTool(a: AgentView, tool: string) {
  const tools = a.tools.includes(tool)
    ? a.tools.filter((t) => t !== tool)
    : [...a.tools, tool]
  emit('update', { ...a, tools })
}

function addAgent() {
  const key = `custom_agent_${Date.now()}`
  const agent: AgentView = {
    key,
    name: '新 Agent',
    icon: '🤖',
    desc: '自定义 Agent',
    enabled: false,
    priority: props.agents.length + 1,
    prompt: '',
    rules: [],
    tools: [],
    runtimeStatus: 'disabled',
  }
  emit('add', agent)
  expanded.value = new Set([...expanded.value, key])
}
</script>

<style scoped>
.mgr { display: flex; flex-direction: column; }
.mgr-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; border-bottom: 1px solid #374151; flex-wrap: wrap;
}
.mgr-bar .hint { font-size: 11px; color: #6b7280; }
.mgr-bar .spacer { flex: 1; }
.mgr-body { padding: 12px; max-height: 520px; overflow-y: auto; }
.ag-card { background: #1f2937; border: 1px solid #374151; border-radius: 10px; margin-bottom: 9px; overflow: hidden; transition: 0.25s; position: relative; }
.ag-card.active { border-color: #6366f1; box-shadow: 0 0 14px rgba(99, 102, 241, 0.18); }
.ag-card.active::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: #6366f1; border-radius: 3px 0 0 3px; }
.ag-main { display: flex; align-items: center; gap: 9px; padding: 10px 12px; }
.ag-ic { font-size: 18px; width: 24px; text-align: center; }
.ag-info { flex: 1; min-width: 0; cursor: pointer; }
.ag-nm { font-weight: 600; font-size: 12px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ag-key { font-size: 10px; color: #6b7280; font-family: monospace; }
.ag-desc { font-size: 10px; color: #9ca3af; margin-top: 1px; }
.st { font-size: 9px; padding: 1px 6px; border-radius: 6px; white-space: nowrap; }
.st.ok { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; }
.st.cfg { background: rgba(59, 130, 246, 0.16); color: #93c5fd; }
.st.off { background: rgba(148, 163, 184, 0.14); color: #9ca3af; }
.reason { font-size: 10px; margin-top: 5px; display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 6px; }
.reason.voice { background: rgba(16, 185, 129, 0.14); color: #6ee7b7; }
.reason.text { background: rgba(59, 130, 246, 0.14); color: #93c5fd; }
.reason.intent { background: rgba(245, 158, 11, 0.14); color: #fcd34d; }
.reason.proc { background: rgba(245, 158, 11, 0.14); color: #fcd34d; }
.reason.default { background: rgba(148, 163, 184, 0.14); color: #cbd5e1; }
.prio { display: flex; align-items: center; gap: 3px; font-size: 10px; color: #9ca3af; }
.prio .num { background: #6366f1; color: #fff; padding: 1px 7px; border-radius: 6px; }
.switch { width: 30px; height: 16px; border-radius: 10px; background: #374151; position: relative; cursor: pointer; flex-shrink: 0; transition: 0.2s; }
.switch::after { content: ''; position: absolute; width: 12px; height: 12px; border-radius: 50%; background: #9ca3af; top: 2px; left: 2px; transition: 0.2s; }
.switch.on { background: #10b981; }
.switch.on::after { left: 16px; background: #fff; }
.icon-btn { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 2px 5px; font-size: 13px; }
.icon-btn:hover { color: #e5e7eb; }
.ag-detail { display: none; border-top: 1px solid #374151; padding: 10px 12px; background: rgba(0, 0, 0, 0.15); }
.ag-card.open .ag-detail { display: block; }
.field { margin-bottom: 9px; }
.field label { display: block; font-size: 10px; color: #9ca3af; margin-bottom: 3px; }
.rules { display: flex; gap: 5px; flex-wrap: wrap; align-items: center; }
.rule { background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.35); color: #818cf8; padding: 2px 8px; border-radius: 6px; font-size: 10px; display: inline-flex; align-items: center; gap: 5px; }
.rule .x { cursor: pointer; color: #9ca3af; }
.rule .x:hover { color: #f87171; }
.tools { display: flex; gap: 12px; flex-wrap: wrap; }
.tools label { display: flex; align-items: center; gap: 5px; font-size: 11px; color: #e5e7eb; cursor: pointer; }
.detail-actions { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
</style>
