<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSuperAgentStore } from '@/stores/super-agent'

// 左侧分组导航：原型三组结构（SuperAgent / Agent 工作台 / 配置）。
// 工作台走独立子路由；Muse 与管理的组内项走单路由 + view query，保持视图内嵌状态。
const route = useRoute()
const router = useRouter()
const store = useSuperAgentStore()

type NavItem = { key: string; label: string; icon: string; to: string; badge?: 'green' | 'red' | 'new' }
type NavGroup = { title: string; items: NavItem[] }

const groups: NavGroup[] = [
  {
    title: 'SuperAgent',
    items: [
      { key: 'dashboard', label: 'Dashboard 看板', icon: '📊', to: '/super-agent/workbench', badge: 'green' },
      { key: 'demo', label: '电商营销 Demo', icon: '🎯', to: '/super-agent/workbench/demo' },
      { key: 'detail', label: '执行详情', icon: '📋', to: '/super-agent/workbench/detail' },
    ],
  },
  {
    title: 'Agent 工作台（独立对话空间）',
    items: [
      { key: 'chat', label: 'SuperAgent 对话', icon: '💬', to: '/super-agent/muse?view=chat' },
      { key: 'feed', label: '动态', icon: '🌊', to: '/super-agent/muse?view=feed', badge: 'green' },
      { key: 'ideas', label: '点子', icon: '💡', to: '/super-agent/muse?view=ideas' },
      { key: 'goals', label: '目标', icon: '🎯', to: '/super-agent/muse?view=goals' },
    ],
  },
  {
    title: '配置',
    items: [
      { key: 'model', label: '模型配置', icon: '🧠', to: '/super-agent/manage?view=model' },
      { key: 'mcp', label: 'MCP Server', icon: '🔌', to: '/super-agent/manage?view=mcp' },
      { key: 'policy', label: 'Policy 规则', icon: '🛡️', to: '/super-agent/manage?view=policy' },
      { key: 'kb', label: '知识库绑定', icon: '📚', to: '/super-agent/manage?view=kb' },
      { key: 'exec', label: '执行参数', icon: '⚙️', to: '/super-agent/manage?view=exec' },
      { key: 'security', label: '安全设置', icon: '🔒', to: '/super-agent/manage?view=security' },
      { key: 'source', label: 'Source 管理', icon: '🔗', to: '/super-agent/manage?view=source', badge: 'new' },
    ],
  },
]

const activeKey = computed(() => {
  const view = String(route.query.view || '')
  if (route.path.startsWith('/super-agent/workbench')) {
    if (route.path.endsWith('/demo')) return 'demo'
    if (route.path.includes('/detail')) return 'detail'
    return 'dashboard'
  }
  if (route.path === '/super-agent/muse' || route.path === '/super-agent/muse/') return view || 'chat'
  if (route.path === '/super-agent/manage' || route.path === '/super-agent/manage/') return view || 'model'
  return 'dashboard'
})

const feedCount = computed(() => store.unreadFeedCount)

function badgeFor(item: NavItem): string | null {
  if (item.key === 'feed') return feedCount.value ? String(feedCount.value) : null
  return null
}

function go(item: NavItem) {
  const [path, query] = item.to.split('?')
  if (query) router.push({ path, query: Object.fromEntries(new URLSearchParams(query)) })
  else router.push(path)
}
</script>

<template>
  <aside class="sa-sidenav">
    <div v-for="group in groups" :key="group.title" class="nav-group">
      <div class="nav-group-title">{{ group.title }}</div>
      <button
        v-for="item in group.items"
        :key="item.key"
        class="nav-item"
        :class="{ active: activeKey === item.key }"
        @click="go(item)"
      >
        <span class="ic">{{ item.icon }}</span>
        <span class="label">{{ item.label }}</span>
        <span v-if="badgeFor(item)" class="badge" :class="item.badge || 'green'">{{ badgeFor(item) }}</span>
        <span v-else-if="item.badge" class="badge" :class="item.badge">
          {{ item.badge === 'new' ? 'new' : '' }}
        </span>
      </button>
    </div>

    <div class="sidenav-bottom">
      v0.1.0 · 2026.11.08<br />
      基于 spec.md · A+C 双 MCP 方案
    </div>
  </aside>
</template>

<style scoped lang="less">
.sa-sidenav {
  width: var(--sa-sidebar-w);
  flex-shrink: 0;
  height: 100%;
  overflow-y: auto;
  padding: 14px 10px;
  background: var(--sa-surface);
  border-right: 1px solid var(--sa-border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-group-title {
  font-size: 11px;
  color: var(--sa-text-3);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 14px 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--sa-radius-sm);
  font-size: 13px;
  color: var(--sa-text-2);
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { background: var(--sa-surface-2); color: var(--sa-text-1); }
  &.active {
    background: var(--sa-accent-dim);
    color: var(--sa-accent);
    border-color: rgba(137, 180, 250, 0.3);
    font-weight: 600;
  }
  .ic { font-size: 16px; width: 20px; text-align: center; }
  .label { flex: 1; }
  .badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    background: var(--sa-red);
    color: #fff;
    &.green { background: var(--sa-green); color: #1a1a2e; }
  }
}

.sidenav-bottom {
  margin-top: auto;
  padding: 12px 10px;
  border-top: 1px solid var(--sa-border);
  font-size: 11px;
  color: var(--sa-text-3);
  line-height: 1.7;
}
</style>
