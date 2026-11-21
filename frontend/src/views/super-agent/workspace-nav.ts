import {
  inject, provide, ref, computed,
  type InjectionKey, type Ref, type ComputedRef,
} from 'vue'

/** 左侧分组侧栏的全部叶子视图（对齐 super-agent-demo 原型的 14 项）。 */
export type SaLeaf =
  | 'dashboard' | 'demo' | 'detail'
  | 'chat' | 'feed' | 'ideas' | 'goals'
  | 'model' | 'mcp' | 'policy' | 'kb' | 'exec' | 'security' | 'source'

const MUSE_LEAVES: SaLeaf[] = ['chat', 'feed', 'ideas', 'goals']

/**
 * SuperAgent 工作区导航上下文：由 SuperAgentWorkspace.vue provide。
 *
 * 工作区作为控制台外壳（admin/index.vue）的一个 Tab 组件渲染，当前路由恒为
 * `/dashboard?tab=super-agent`，没有 router-view 与路由参数。因此统一用一个
 * `active` 叶子视图 + 组件状态管理，左侧分组侧栏点哪切哪（对齐原型）；所有
 * 跨视图跳转都走 `go()`，不碰 router.push，避免跳出 Tab 外壳。
 */
export interface WorkspaceNavContext {
  /** 当前激活的叶子视图 */
  active: Ref<SaLeaf>
  /** 执行详情的 Ticket id（active==='detail' 时传给 detail 组件） */
  detailId: Ref<string | undefined>
  /** 跨视图参数（prompt / goal 等），消费方读取后不清空 */
  params: Ref<Record<string, any>>
  /** 切换叶子视图，可携带参数；detail 用 params.id 指定 Ticket */
  go: (leaf: SaLeaf, params?: Record<string, any>) => void

  /** Muse 子视图桥接（子视图 inject 的 MUSE_NAV_KEY 指向这里） */
  museView: ComputedRef<string>
  switchMuse: (view: string, params?: Record<string, any>) => void
}

export const WORKSPACE_NAV_KEY: InjectionKey<WorkspaceNavContext> = Symbol('sa-workspace-nav')

export function provideWorkspaceNav(): WorkspaceNavContext {
  const active = ref<SaLeaf>('dashboard')
  const detailId = ref<string | undefined>(undefined)
  const params = ref<Record<string, any>>({})

  const museView = computed(() => (MUSE_LEAVES.includes(active.value) ? active.value : 'chat'))

  const ctx: WorkspaceNavContext = {
    active,
    detailId,
    params,
    go(leaf, nextParams = {}) {
      params.value = nextParams
      active.value = leaf
      if (leaf === 'detail') detailId.value = nextParams.id as string | undefined
    },
    museView,
    switchMuse(view, nextParams = {}) {
      // 子视图 switchView('chat'|'feed'|'ideas'|'goals', params) → 平铺侧栏切换
      ctx.go(view as SaLeaf, nextParams)
    },
  }

  provide(WORKSPACE_NAV_KEY, ctx)
  return ctx
}

export function useWorkspaceNav(): WorkspaceNavContext | undefined {
  return inject(WORKSPACE_NAV_KEY)
}
