// frontend/src/views/twin/stateMap.ts
import type { WidgetDatum, TwinMode } from '@/types/twin'

export interface WidgetViewState {
  branch: 'content' | 'empty' | 'error'
  loading: boolean          // 由宿主注入（本地态），这里恒 false 占位
  emptyTitle: string; emptyDesc: string
  errorText: string; retryable: boolean
  masked: boolean           // 仅 branch=content 有意义：值位 🔒 开关
}
export function widgetState(d: WidgetDatum, mode: TwinMode): WidgetViewState {
  const out: WidgetViewState = {
    branch: 'content', loading: false, emptyTitle: '暂无数据', emptyDesc: '',
    errorText: '', retryable: false, masked: d.state === 'masked',
  }
  if (d.state === 'empty') {
    out.branch = 'empty'
    if (d.reason === 'unbound') {
      out.emptyTitle = mode === 'edit' ? '未绑定查询，点击绑定' : '未绑定查询'
      out.emptyDesc = mode === 'edit' ? '从本体的 verified 查询中选一个' : ''
    } else {
      out.emptyTitle = '查询结果为空'; out.emptyDesc = ''
    }
  } else if (d.state === 'error') {
    out.branch = 'error'
    out.errorText = d.error ? `${d.error.code}: ${d.error.message}` : '未知错误'  // W6
    out.retryable = true                                                          // ↻ → T9
  }
  return out
}
