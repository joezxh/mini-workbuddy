import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { isAuthenticated } from '@/utils/auth'
import { message } from 'ant-design-vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', requiresAuth: false, hideHeader: true }
  },
  {
    // 孪生只读发布页（T11）：不套 AppLayout（无左导航/把手，W12）；P0 仅登录态
    path: '/twin-p/:slug',
    name: 'TwinPublished',
    component: () => import('@/views/twin/TwinPublishedPage.vue'),
    props: true,
    meta: { title: '孪生看板', requiresAuth: true, hideHeader: true }
  },
  {
    // 控制台外壳：左侧导航栏 + 顶栏，所有需要登录的页面都挂在它下面。
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        // 登录首页直接以控制台 Tab 外壳呈现（首屏即页签栏，控制台页签不可关闭并默认激活）
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '控制台', icon: 'DashboardOutlined' }
      },
      {
        path: 'ai-assistant',
        name: 'AIAssistant',
        component: () => import('@/views/assistant/index.vue'),
        meta: { title: 'AI助理', icon: 'MessageOutlined' }
      },
      {
        path: 'ai-assistant/skills',
        name: 'SkillManagement',
        component: () => import('@/views/admin/ai/skill/SkillManagement.vue'),
        meta: { title: '技能管理', icon: 'ApiOutlined' }
      },
      {
        path: 'wiki',
        name: 'Wiki',
        component: () => import('@/views/kms/wiki/index.vue'),
        meta: { title: '知识库 Wiki', icon: 'BookOutlined' }
      },
      {
        path: 'wiki/edit/:id',
        name: 'WikiEdit',
        component: () => import('@/views/kms/wiki/ArticleEdit.vue'),
        meta: { title: '编辑文章', hidden: true }
      },
      {
        path: 'wiki/:slug',
        name: 'WikiArticle',
        component: () => import('@/views/kms/wiki/ArticleView.vue'),
        meta: { title: '文章', hidden: true }
      },
      {
        // RAG 检索 / 问答测试台（自 admin/llm-wiki/RagTestTab 迁移）
        path: 'wiki/rag',
        name: 'WikiRagTest',
        component: () => import('@/views/kms/wiki/RagTest.vue'),
        meta: { title: 'RAG 测试', hidden: true }
      },
      {
        // 历史入口：控制台壳已迁到 /dashboard，/admin 仅带 query 透传重定向（/admin?tab=apikey 照旧可用）
        path: 'admin',
        redirect: to => ({ path: '/dashboard', query: to.query }),
        meta: { title: '管理员', icon: 'SettingOutlined', requiresAdmin: true }
      },
      {
        path: 'admin/agent-team',
        name: 'AgentTeamList',
        component: () => import('@/views/admin/agent-team/TeamList.vue'),
        meta: { title: '智能体团队', icon: 'ApartmentOutlined', requiresAdmin: true }
      },
      {
        path: 'admin/agent-team/:teamId',
        name: 'AgentTeamEditor',
        component: () => import('@/views/admin/agent-team/TeamEditor.vue'),
        props: true,
        meta: { title: '团队编排', icon: 'ApartmentOutlined', requiresAdmin: true, hidden: true }
      },
      {
        path: 'admin/agent-team/:teamId/run/:runId',
        name: 'AgentTeamConversation',
        component: () => import('@/views/admin/agent-team/TeamConversation.vue'),
        meta: { title: '团队对话', hidden: true }
      },
      {
        path: 'admin/agent-team/run/:runId/replay',
        name: 'AgentTeamReplay',
        component: () => import('@/views/admin/agent-team/TeamReplay.vue'),
        meta: { title: '运行回放', hidden: true }
      },
      // ── 工作流管理 ──
      {
        path: 'admin/workflow',
        name: 'WorkflowManagement',
        component: () => import('@/views/admin/workflow/WorkflowManagement.vue'),
        meta: { title: '工作流管理', icon: 'ApiOutlined', requiresAdmin: true }
      },
      // ── 数据资产目录（AF-01~AF-08）：独立路由，等价于 /dashboard?tab=data-asset 的外壳 Tab ──
      {
        path: 'admin/data-asset',
        name: 'DataAsset',
        component: () => import('@/views/data-source/DataAssetPanel.vue'),
        meta: { title: '数据资产', icon: 'DatabaseOutlined', requiresAdmin: true }
      },
      // ── 推演沙盘（沙箱域 S1–S21）：独立路由，等价于 /dashboard?tab=simulation 的外壳 Tab ──
      {
        path: 'admin/simulation',
        name: 'SimulationSandbox',
        component: () => import('@/views/sandbox/SimulationSandbox.vue'),
        meta: { title: '推演沙盘', icon: 'NodeIndexOutlined', requiresAdmin: true }
      },
      // ── 孪生应用（Plan 2）：sys_menu 2407 (/admin/digital-twin)，与沙盘同构双挂载 ──
      {
        path: 'admin/digital-twin',
        name: 'DigitalTwin',
        component: () => import('@/views/twin/TwinWorkspace.vue'),
        meta: { title: '孪生应用', icon: 'DeploymentUnitOutlined', requiresAdmin: true }
      },
      {
        // 调解语音 RTC 演示（迁移自 risk_control）
        path: 'duplex/voice-demo',
        name: 'DuplexVoiceDemo',
        component: () => import('@/views/duplex/VoiceDemo.vue'),
        meta: { title: '调解语音 RTC 演示' }
      },
      {
        // 语音能力 Demo（2026-11-10，spec docs/superpowers/specs/2026-11-10-voice-demo-design.md）
        path: 'voice-demo',
        name: 'VoiceDemo',
        component: () => import('@/views/voice-demo/VoiceDemo.vue'),
        meta: { title: '语音演示', icon: 'AudioOutlined' }
      },
      {
        // 视频会议（LiveKit 自建 SFU，docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md）
        path: 'meeting',
        name: 'MeetingRoom',
        component: () => import('@/views/meeting/MeetingRoom.vue'),
        meta: { title: '视频会议', icon: 'VideoCameraOutlined' }
      },
      // ── SuperAgent（Task 4：前端入口 + Demo）──
      {
        path: 'super-agent',
        name: 'SuperAgentBoard',
        component: () => import('@/views/super-agent/board.vue'),
        meta: { title: 'SuperAgent 看板', icon: 'RobotOutlined' }
      },
      {
        path: 'super-agent/detail/:id',
        name: 'SuperAgentTicketDetail',
        component: () => import('@/views/super-agent/detail.vue'),
        props: true,
        meta: { title: 'Ticket 详情', hidden: true }
      },
      {
        path: 'super-agent/demo',
        name: 'SuperAgentDemo',
        component: () => import('@/views/super-agent/demo.vue'),
        meta: { title: 'SuperAgent Demo', hidden: true }
      },
      {
        path: 'super-agent/config-source',
        name: 'SuperAgentConfigSource',
        component: () => import('@/views/super-agent/config-source.vue'),
        meta: { title: 'Source 配置', hidden: true }
      },
      {
        // HITL 审批列表（spec 步骤三 4.4）：agent_hitl_pause 只读表格
        path: 'super-agent/hitl',
        name: 'SuperAgentHitl',
        component: () => import('@/views/super-agent/hitl.vue'),
        meta: { title: 'HITL 审批', icon: 'AuditOutlined' }
      },
      // ── SuperAgent Agent 工作台（Task 4.6：Chat/Feed/Ideas/Goals）──
      {
        path: 'super-agent/chat',
        name: 'SuperAgentChat',
        component: () => import('@/views/super-agent/workbench/chat.vue'),
        meta: { title: 'Agent 对话', icon: 'CommentOutlined' }
      },
      {
        path: 'super-agent/feed',
        name: 'SuperAgentFeed',
        component: () => import('@/views/super-agent/workbench/feed.vue'),
        meta: { title: '动态 Feed', icon: 'UnorderedListOutlined' }
      },
      {
        path: 'super-agent/ideas',
        name: 'SuperAgentIdeas',
        component: () => import('@/views/super-agent/workbench/ideas.vue'),
        meta: { title: '点子库', icon: 'BulbOutlined' }
      },
      {
        path: 'super-agent/goals',
        name: 'SuperAgentGoals',
        component: () => import('@/views/super-agent/workbench/goals.vue'),
        meta: { title: '目标', icon: 'AimOutlined' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !isAuthenticated()) {
    message.warning('请先登录')
    next('/login')
  } else if (to.path === '/login' && isAuthenticated()) {
    next('/')
  } else {
    next()
  }
})

export default router
