import { inject, type ComputedRef, type InjectionKey, type Ref } from 'vue'

/** Muse 执行界面内部导航上下文：由 muse.vue provide，四个内嵌视图 inject。 */
export interface MuseNavContext {
  /** 当前视图 key：chat / feed / ideas / goals */
  view: ComputedRef<string>
  /** 跨视图传递的参数（prompt / goal 等），切换后消费方读取 */
  params: Ref<Record<string, any>>
  /** 切换内部视图并可携带参数 */
  switchView: (view: string, params?: Record<string, any>) => void
}

export const MUSE_NAV_KEY: InjectionKey<MuseNavContext> = Symbol('sa-muse-nav')

export function useMuseNav(): MuseNavContext | undefined {
  return inject(MUSE_NAV_KEY)
}
