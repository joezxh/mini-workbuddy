/** 孪生工作区状态机（Plan 2 spec §3）。服务器态为真相源；loading 本地驱动。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/twin'
import type {
  CardsByGroup, TwinCard, TwinPage, TwinWidget, WidgetDatum, TwinMode,
  PublishInfo, AccessListResp, LoadPageResp,
} from '@/types/twin'

export const useTwinStore = defineStore('twin', () => {
  const cards = ref<CardsByGroup>({ mine: [], shared: [], restricted: [] })
  const activeCardId = ref<number | null>(null)
  const cardDetail = ref<TwinCard | null>(null)
  const pages = ref<TwinPage[]>([])
  const activePageId = ref<number | null>(null)
  const widgets = ref<TwinWidget[]>([])
  const pageData = ref<Record<number, WidgetDatum>>({})   // 切卡/切页即弃（W11 旁证）
  const mode = ref<TwinMode>('edit')
  const loadingPage = ref(false)
  const accessRequests = ref<AccessListResp | null>(null)
  const publishInfo = ref<PublishInfo | null>(null)
  const collectedAt = ref<string | null>(null)                  // T8 回体 collected_at（statusbar 新鲜度）
  const aiDraft = ref<[]>([])                              // D1：占位，无端点

  let timer: ReturnType<typeof setInterval> | null = null
  const intervalMs = ref(10000)                            // 档位 10000/30000/0（off）

  function applyRefreshCfg(cfg: Record<string, unknown> | null) {
    const raw = Number((cfg as any)?.interval ?? 10000)
    intervalMs.value = raw === 0 ? 0 : (raw === 30000 ? 30000 : 10000)
  }
  function startScheduler() {
    stopScheduler()
    if (intervalMs.value > 0 && activePageId.value != null)
      timer = setInterval(() => { void refreshPage() }, intervalMs.value)
  }
  function stopScheduler() { if (timer) { clearInterval(timer); timer = null } }
  /** 由 visibilitychange 宿主（TwinWorkspace）接线：hidden→暂停；visible→立刷一次并重启 */
  function onVisibility(hidden: boolean) {
    if (hidden) stopScheduler()
    else { void refreshPage().then(startScheduler) }
  }

  async function loadCards() { cards.value = await api.listCards() }
  async function openCard(id: number) {          // 换卡 = 全量重置（W11 前端旁证）
    activeCardId.value = id; pageData.value = {}; publishInfo.value = null
    cardDetail.value = await api.getCard(id)
    pages.value = await api.listPages(id)
    if (pages.value.length) await selectPage(pages.value[0].id)
  }
  async function selectPage(id: number) {        // W4：切页触发一次加载
    activePageId.value = id; pageData.value = {}
    widgets.value = await api.listWidgets(id)
    await refreshPage()
    if (mode.value === 'run' || mode.value === 'edit') startScheduler()
  }
  async function refreshPage(params?: Record<string, unknown>) {  // W8：永远只 1 个请求
    if (activePageId.value == null) return
    loadingPage.value = true
    try {
      const resp: LoadPageResp = await api.loadPageData(activePageId.value, params)
      const next: Record<number, WidgetDatum> = {}
      for (const it of resp.items) next[it.widget_id] = it
      pageData.value = next
      collectedAt.value = resp.collected_at ?? null
      applyRefreshCfg(resp.refresh)
    } finally { loadingPage.value = false }
  }
  async function retryWidget(widgetId: number) {
    const d = await api.loadWidgetData(widgetId)
    pageData.value = { ...pageData.value, [widgetId]: d }
  }
  function setMode(m: TwinMode) { mode.value = m }

  async function publish(cfg: { access: 'org' | 'role'; role_codes?: string[] }) {
    if (activePageId.value == null) return null
    publishInfo.value = await api.publishPage(activePageId.value, cfg)   // 恒 200 = 版本推进
    return publishInfo.value
  }
  async function unpublish() {
    if (publishInfo.value) { await api.unpublish(publishInfo.value.publish_id); publishInfo.value = null }
  }
  async function loadRequests() { accessRequests.value = await api.listAccessRequests() }
  async function requestAccess(cardId: number, reason?: string) { return api.requestCardAccess(cardId, reason) }
  async function approve(id: number, days?: number) { await api.approveAccessRequest(id, days); await loadRequests() }
  async function reject(id: number) { await api.rejectAccessRequest(id); await loadRequests() }

  return { cards, activeCardId, cardDetail, pages, activePageId, widgets, pageData, mode,
           loadingPage, accessRequests, publishInfo, collectedAt, aiDraft, intervalMs,
           applyRefreshCfg, startScheduler, stopScheduler, onVisibility,
           loadCards, openCard, selectPage, refreshPage, retryWidget, setMode,
           publish, unpublish, loadRequests, requestAccess, approve, reject }
})
