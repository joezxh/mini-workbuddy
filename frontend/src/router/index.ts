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
    // 控制台外壳：左侧导航栏 + 顶栏，所有需要登录的页面都挂在它下面。
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
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
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/admin/index.vue'),
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
