<script setup lang="ts">
// 管理界面：对齐原型「配置」组（模型 / MCP / Policy / KB / 执行参数 / 安全 / Source）。
// - source：内嵌真实 config-source.vue（后端已有 GET/PUT /sources/{kind}/config）
// - policy/exec/security：内嵌展示态配置页
// - model/mcp/kb：跳转卡片，复用后台现有配置中心（避免复制管理逻辑与权限）
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfigSource from './config-source.vue'
import PolicyConfig from './manage/PolicyConfig.vue'
import ExecParams from './manage/ExecParams.vue'
import SecuritySettings from './manage/SecuritySettings.vue'

const route = useRoute()
const router = useRouter()

const view = computed(() => String(route.query.view || 'model'))

const TITLES: Record<string, { h1: string; p: string }> = {
  model: { h1: '🧠 模型配置', p: '重用 MinWorkBuddy ai_api_key + ai_chat_model · 绑定到电商营销工作空间' },
  mcp: { h1: '🔌 MCP Server 配置', p: '重用 ai_mcp_api_key + ToolManager + AgentScope WorkspaceManager' },
  kb: { h1: '📚 知识库绑定', p: 'Workspace 级绑定 · AgentScope RAG 检索可见范围' },
  source: { h1: '🔗 Source 管理', p: 'GitHub / 飞书触发源配置 · Thread / Subscription / Mandate 预览' },
  policy: { h1: '🛡️ Policy 规则', p: '准入规则 · source 白名单 · Jev 决策阈值' },
  exec: { h1: '⚙️ 执行参数', p: 'Worker / GoalPipeline 执行参数' },
  security: { h1: '🔒 安全设置', p: '鉴权 · 审计 · 沙箱 · 网络白名单' },
}
const head = computed(() => TITLES[view.value] || TITLES.model)

const JUMPS = [
  {
    key: 'model', emo: '🧠', title: '前往模型配置中心',
    desc: '在 AI 能力配置中管理 API Key 与已注册模型（含 Jev 决策模型 platform=typeSafeai）。',
    to: '/dashboard', query: { tab: 'apikey' },
  },
  {
    key: 'mcp', emo: '🔌', title: '前往 MCP 服务管理',
    desc: '登记 playwright / windows-mcp / kira-mcp 等 stdio 服务，配置 capabilities 与健康检查。',
    to: '/dashboard', query: { tab: 'mcp' },
  },
  {
    key: 'kb', emo: '📚', title: '前往知识库管理',
    desc: '创建 Collection、配置 RAG 检索与分段，供 SuperAgent Worker 作为工具注入。',
    to: '/wiki', query: {},
  },
]

function jump(item: (typeof JUMPS)[number]) {
  router.push({ path: item.to, query: item.query })
}
</script>

<template>
  <div class="sa-manage">
    <template v-if="view !== 'source' && view !== 'policy' && view !== 'exec' && view !== 'security'">
      <div class="sa-page-head">
        <h1>{{ head.h1 }}</h1>
        <p>{{ head.p }}</p>
      </div>
    </template>

    <!-- Source 管理：真实页 -->
    <ConfigSource v-if="view === 'source'" />

    <!-- 静态展示态配置页 -->
    <PolicyConfig v-else-if="view === 'policy'" />
    <ExecParams v-else-if="view === 'exec'" />
    <SecuritySettings v-else-if="view === 'security'" />

    <!-- 模型 / MCP / KB：复用后台配置中心 -->
    <template v-else>
      <div class="sa-note-ok">
        ✅ <b>零新表设计</b>：配置复用 MinWorkBuddy 现有能力表，点击卡片前往配置中心完成登记，返回后自动生效。
      </div>
      <button
        v-for="item in JUMPS.filter(j => j.key === view)"
        :key="item.key"
        class="sa-jump"
        @click="jump(item)"
      >
        <span class="emo">{{ item.emo }}</span>
        <span class="txt"><b>{{ item.title }}</b><span>{{ item.desc }}</span></span>
        <span style="margin-left: auto; color: var(--sa-accent)">前往配置 →</span>
      </button>
    </template>
  </div>
</template>

<style scoped lang="less">
@import './manage-shared.less';
.sa-manage { max-width: 1100px; }
</style>
