import { defineStore } from 'pinia'

/**
 * 推演沙盘游标 store（§4.3）：**仅持游标** {sceneId, branchId, tick, execMode}。
 * 世界状态真源恒在后端沙箱表——切场景/切分支/跳转都是服务端重算，快照数据不进 store。
 */
export const useSandboxStore = defineStore('sandbox', {
  state: () => ({
    sceneId: null as number | null,
    branchId: null as number | null,
    tick: 0,
    execMode: 'auto',
  }),
  actions: {
    setCursor(p: Partial<{ sceneId: number | null; branchId: number | null; tick: number; execMode: string }>) {
      Object.assign(this, p)
    },
    reset() {
      this.sceneId = null
      this.branchId = null
      this.tick = 0
      this.execMode = 'auto'
    },
  },
})
