<script setup lang="ts">
// SuperAgent 工作区：作为控制台外壳（admin/index.vue）的一个 Tab 组件渲染。
// 内部对齐 super-agent-demo 原型：顶栏 + 左侧分组侧栏（3 组 14 项）+ 右侧主区，
// 侧栏点哪切哪，无内部 tab。左侧系统菜单、外层系统 Tab 均保持原样。
import { computed, provide, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Board from './board.vue'
import Demo from './demo.vue'
import Detail from './detail.vue'
import Chat from './workbench/chat.vue'
import Feed from './workbench/feed.vue'
import Ideas from './workbench/ideas.vue'
import Goals from './workbench/goals.vue'
import ConfigSource from './config-source.vue'
import PolicyConfig from './manage/PolicyConfig.vue'
import ExecParams from './manage/ExecParams.vue'
import SecuritySettings from './manage/SecuritySettings.vue'
import { provideWorkspaceNav, type SaLeaf } from './workspace-nav'
import { MUSE_NAV_KEY, type MuseNavContext } from './muse-nav'
import { useSuperAgentStore } from '@/stores/super-agent'
import '@/styles/super-agent-tokens.css'

const router = useRouter()
const store = useSuperAgentStore()
const nav = provideWorkspaceNav()

// 桥接：子视图 inject 的 MUSE_NAV_KEY 指向工作区导航
const museNav: MuseNavContext = {
  view: nav.museView,
  params: nav.params,
  switchView: nav.switchMuse,
}
provide(MUSE_NAV_KEY, museNav)

type NavItem = { key: SaLeaf; label: string; icon: string; badge?: 'green' | 'red' | 'new' }
type NavGroup = { title: string; items: NavItem[] }
const GROUPS: NavGroup[] = [
  {
    title: 'SuperAgent',
    items: [
      { key: 'dashboard', label: 'Dashboard 看板', icon: '📊', badge: 'green' },
      { key: 'demo', label: '电商营销 Demo', icon: '🎯' },
      { key: 'detail', label: '执行详情', icon: '📋' },
    ],
  },
  {
    title: 'Agent 工作台（独立对话空间）',
    items: [
      { key: 'chat', label: 'SuperAgent 对话', icon: '💬' },
      { key: 'feed', label: '动态', icon: '🌊', badge: 'green' },
      { key: 'ideas', label: '点子', icon: '💡' },
      { key: 'goals', label: '目标', icon: '🎯' },
    ],
  },
  {
    title: '配置',
    items: [
      { key: 'model', label: '模型配置', icon: '🧠' },
      { key: 'mcp', label: 'MCP Server', icon: '🔌' },
      { key: 'policy', label: 'Policy 规则', icon: '🛡️' },
      { key: 'kb', label: '知识库绑定', icon: '📚' },
      { key: 'exec', label: '执行参数', icon: '⚙️' },
      { key: 'security', label: '安全设置', icon: '🔒' },
      { key: 'source', label: 'Source 管理', icon: '🔗', badge: 'new' },
    ],
  },
]

const HEADS: Partial<Record<SaLeaf, { h1: string; p: string }>> = {
  dashboard: { h1: '📊 Dashboard 看板', p: '实时查看所有 Ticket 状态，快速进入执行详情' },
  demo: { h1: '🎯 电商营销 Demo · 完整端到端范例', p: '数据采集 → 竞品分析 → 方案生成 → 反思校验 → ERP 执行' },
  detail: { h1: '📋 执行详情', p: 'Ticket 生命周期 · Mandate 授权 · 执行时间线' },
  model: { h1: '🧠 模型配置', p: '重用 ai_api_key + ai_chat_model · 绑定电商营销工作空间' },
  mcp: { h1: '🔌 MCP Server 配置', p: '登记 playwright / windows-mcp / kira-mcp 等 stdio 服务' },
  kb: { h1: '📚 知识库绑定', p: 'Workspace 级绑定 · AgentScope RAG 检索可见范围' },
}

// 配置里的 model/mcp/kb 复用后台现有配置中心（跳转卡片）
const JUMPS: Partial<Record<SaLeaf, { title: string; desc: string; to: string; query: Record<string, string> }>> = {
  model: { title: '前往模型配置中心', desc: '管理 API Key 与已注册模型（含 Jev 决策模型 platform=typeSafeai）。', to: '/dashboard', query: { tab: 'apikey' } },
  mcp: { title: '前往 MCP 服务管理', desc: '登记 stdio 服务，配置 capabilities 与健康检查。', to: '/dashboard', query: { tab: 'mcp' } },
  kb: { title: '前往知识库管理', desc: '创建 Collection、配置 RAG 检索与分段，供 Worker 作为工具注入。', to: '/wiki', query: {} },
}
const jumpFor = computed(() => JUMPS[nav.active.value])
function doJump() {
  const j = jumpFor.value
  if (j) router.push({ path: j.to, query: j.query })
}

const feedCount = computed(() => store.unreadFeedCount)
function badgeText(item: NavItem): string | null {
  if (item.key === 'feed') return feedCount.value ? String(feedCount.value) : null
  if (item.badge === 'new') return 'new'
  return null
}

// Tab 打开即挂载并常驻，SSE 在此统一订阅，卸载（关闭 Tab）时断开。
onMounted(() => {
  store.connectEvents()
  store.connectFeed()
})
onUnmounted(() => {
  store.disconnectEvents()
  store.disconnectFeed()
})
</script>

<template>
  <div class="super-agent-shell sa-workspace">
      <!-- 顶栏 -->
      <header class="sa-topbar">
        <div class="brand">
          <span class="logo">SA</span>
          <b>SuperAgent 工作台</b>
          <span class="sub">MinWorkBuddy · AgentScope · 绑定 Workspace</span>
        </div>
        <span class="spacer"></span>
        <span class="pill">🏢 电商营销工作空间（活跃）</span>
        <span class="pill on">WorkspaceManager PER_TICKET</span>
        <span class="pill on">Worker 2/3</span>
      </header>

      <div class="sa-body">
        <!-- 左侧分组侧栏（对齐原型） -->
        <aside class="sa-sidenav">
          <div v-for="group in GROUPS" :key="group.title" class="nav-group">
            <div class="nav-group-title">{{ group.title }}</div>
            <button
              v-for="item in group.items"
              :key="item.key"
              class="nav-item"
              :class="{ active: nav.active.value === item.key }"
              @click="nav.go(item.key)"
            >
              <span class="ic">{{ item.icon }}</span>
              <span class="label">{{ item.label }}</span>
              <span v-if="badgeText(item)" class="badge" :class="item.badge || 'green'">{{ badgeText(item) }}</span>
            </button>
          </div>
          <div class="sidenav-bottom">v0.1.0 · 2026.11.08<br />基于 spec.md · A+C 双 MCP 方案</div>
        </aside>

        <!-- 右侧主区 -->
        <main class="sa-main">
          <div class="page-head" v-if="HEADS[nav.active.value]">
            <h1>{{ HEADS[nav.active.value]!.h1 }}</h1>
            <p>{{ HEADS[nav.active.value]!.p }}</p>
          </div>

          <Board v-show="nav.active.value === 'dashboard'" />
          <Demo v-show="nav.active.value === 'demo'" />
          <Detail v-show="nav.active.value === 'detail'" :id="nav.detailId.value" />
          <Chat v-show="nav.active.value === 'chat'" />
          <Feed v-show="nav.active.value === 'feed'" />
          <Ideas v-show="nav.active.value === 'ideas'" />
          <Goals v-show="nav.active.value === 'goals'" />
          <ConfigSource v-show="nav.active.value === 'source'" />
          <PolicyConfig v-show="nav.active.value === 'policy'" />
          <ExecParams v-show="nav.active.value === 'exec'" />
          <SecuritySettings v-show="nav.active.value === 'security'" />

          <!-- model / mcp / kb：跳转卡片 -->
          <template v-if="jumpFor">
            <div class="sa-note-ok">✅ <b>零新表设计</b>：配置复用 MinWorkBuddy 现有能力表，点击卡片前往配置中心完成登记。</div>
            <button class="sa-jump" @click="doJump">
              <span class="emo">{{ nav.active.value === 'model' ? '🧠' : nav.active.value === 'mcp' ? '🔌' : '📚' }}</span>
              <span class="txt"><b>{{ jumpFor.title }}</b><span>{{ jumpFor.desc }}</span></span>
              <span class="go">前往配置 →</span>
            </button>
          </template>
      </main>
    </div>
  </div>
</template>

<style scoped lang="less">
@import './manage-shared.less';

.sa-workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sa-topbar {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  background: var(--sa-surface);
  border-bottom: 1px solid var(--sa-border);

  .brand { display: flex; align-items: center; gap: 10px; font-size: 14px; }
  .logo {
    width: 28px; height: 28px; border-radius: 8px;
    display: inline-flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, var(--sa-accent), var(--sa-mauve));
    color: #fff; font-weight: 800; font-size: 13px;
  }
  .sub { font-size: 11px; color: var(--sa-text-3); padding-left: 10px; border-left: 1px solid var(--sa-border); }
  .spacer { flex: 1; }
  .pill {
    font-size: 11px; color: var(--sa-text-2); padding: 5px 12px; border-radius: 20px;
    background: var(--sa-surface-2); border: 1px solid var(--sa-border);
    &.on { color: var(--sa-green); }
  }
}

.sa-body { flex: 1; display: flex; min-height: 0; overflow: hidden; }

.sa-sidenav {
  width: 220px;
  flex-shrink: 0;
  overflow-y: auto;
  padding: 12px 8px;
  background: var(--sa-surface);
  border-right: 1px solid var(--sa-border);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nav-group-title {
  font-size: 10px; color: var(--sa-text-3);
  text-transform: uppercase; letter-spacing: .1em;
  padding: 14px 10px 6px;
}

.nav-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 9px 12px; border-radius: var(--sa-radius-sm);
  font-size: 12px; color: var(--sa-text-2); text-align: left;
  border: 1px solid transparent; background: transparent; cursor: pointer;
  transition: all .15s;
  .ic { font-size: 15px; width: 18px; text-align: center; }
  .label { flex: 1; }
  .badge {
    font-size: 10px; padding: 1px 6px; border-radius: 10px;
    background: var(--sa-red); color: #fff;
    &.green { background: var(--sa-green); color: #1a1a2e; }
  }
  &:hover { background: var(--sa-surface-2); color: var(--sa-text-1); }
  &.active {
    background: var(--sa-accent-dim); color: var(--sa-accent);
    border-color: color-mix(in srgb, var(--sa-accent) 30%, transparent); font-weight: 600;
  }
}

.sidenav-bottom {
  margin-top: auto; padding: 12px 10px; border-top: 1px solid var(--sa-border);
  font-size: 10px; color: var(--sa-text-3); line-height: 1.7;
}

.sa-main {
  flex: 1; min-width: 0; height: 100%; overflow: auto; padding: 18px 20px;
  background: var(--sa-bg);
  > * { min-height: 0; }
}

.page-head { margin-bottom: 16px; h1 { font-size: 20px; font-weight: 700; } p { font-size: 12px; color: var(--sa-text-3); margin-top: 4px; } }
.sa-jump { width: 100%; text-align: left; .go { margin-left: auto; color: var(--sa-accent); } }
</style>
