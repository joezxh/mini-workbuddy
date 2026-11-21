<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createTicket } from '@/api/super-agent'
import { useSuperAgentStore } from '@/stores/super-agent'
import { message } from 'ant-design-vue'

// 顶栏：原型左侧的 SA 渐变 Logo + 标题/版本副标 + 工作空间下拉 + 运行态胶囊 + 通知 + 新建 Ticket。
const router = useRouter()
const store = useSuperAgentStore()

const workspaces = [
  '🏢 电商营销工作空间（活跃）',
  '🔬 知识库增强空间',
  '💻 ERP 自动化空间',
  '⚙️ 默认工作空间',
]
const workspace = ref(workspaces[0])
const creating = ref(false)

const unread = computed(() => store.unreadFeedCount)

async function newTicket() {
  if (creating.value) return
  creating.value = true
  try {
    const ticket = await createTicket({
      workspace_id: 1,
      title: '新建营销任务',
      prompt: '请描述你的营销任务，例如：抓竞品活动页 + 自家销售数据 + 历史爆款，产出本周营销方案',
    }) as any
    message.success('Ticket 已创建')
    if (ticket?.id) router.push(`/super-agent/workbench/detail/${ticket.id}`)
  } catch (e: any) {
    message.error(e?.message || '创建 Ticket 失败')
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <header class="sa-topbar">
    <div class="brand">
      <div class="brand-logo">SA</div>
      <span class="brand-title">SuperAgent 工作台</span>
      <span class="brand-sub">MinWorkBuddy · AgentScope 2.0.11 · <b>绑定 Workspace</b></span>
    </div>

    <div class="spacer" />

    <a-select v-model:value="workspace" size="small" class="ws-select" popupClassName="sa-ws-menu">
      <a-select-option v-for="ws in workspaces" :key="ws" :value="ws">{{ ws }}</a-select-option>
    </a-select>

    <span class="sa-pill on"><span class="dot" /> WorkspaceManager PER_TICKET</span>
    <span class="sa-pill on"><span class="dot" /> Worker 2/3</span>
    <span class="sa-pill accent"><span class="dot" /> windows-mcp ✓</span>
    <span class="sa-pill accent"><span class="dot" /> kira-mcp ✓</span>
    <span class="sa-pill peach"><span class="dot" /> Jev 1.14 就绪</span>

    <button class="sa-btn bell" title="动态通知" @click="router.push('/super-agent/muse')">
      🔔 <span v-if="unread" class="badge">{{ unread }}</span>
    </button>
    <button class="sa-btn sa-btn-primary" :disabled="creating" @click="newTicket">
      ➕ {{ creating ? '创建中…' : '新建 Ticket' }}
    </button>
  </header>
</template>

<style scoped lang="less">
.sa-topbar {
  height: var(--sa-topbar-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  background: var(--sa-surface);
  border-bottom: 1px solid var(--sa-border);
  z-index: 100;
}

.brand { display: flex; align-items: center; gap: 10px; white-space: nowrap; }
.brand-logo {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, var(--sa-accent), var(--sa-mauve));
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 800; font-size: 15px;
}
.brand-title { font-weight: 700; font-size: 15px; color: var(--sa-text-1); }
.brand-sub {
  color: var(--sa-text-3); font-size: 12px; margin-left: 4px;
  padding-left: 12px; border-left: 1px solid var(--sa-border);
}
.brand-sub b { color: var(--sa-peach); font-weight: 600; }
.spacer { flex: 1; min-width: 8px; }
.ws-select { width: 240px; }
.bell { padding: 7px 12px; position: relative; }
.badge {
  margin-left: 4px; background: var(--sa-red); color: #fff;
  padding: 1px 6px; border-radius: 10px; font-size: 10px;
}

@media (max-width: 1400px) {
  .brand-sub, .sa-pill { display: none; }
}
</style>
