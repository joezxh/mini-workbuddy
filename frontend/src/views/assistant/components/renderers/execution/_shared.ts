/**
 * 共享样式类和工具函数 — 参考 AgentScope _shared.tsx
 */

/** 工具名标签样式 */
export const toolLabelClass = 'execution-tool-label'

/** 工具参数/描述样式 */
export const toolArgClass = 'execution-tool-arg'

/** Shimmer 动画样式类 */
export const shimmerClass = 'execution-shimmer'

/**
 * 格式化耗时毫秒为可读字符串
 */
export function formatDuration(ms: number | undefined): string {
  if (ms == null) return ''
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/**
 * 解析工具参数为可读摘要
 */
export function parseInputSummary(params: Record<string, any> | undefined): string {
  if (!params) return ''
  const entries = Object.entries(params)
  if (entries.length === 0) return ''
  for (const [_key, val] of entries) {
    if (val == null || val === '') continue
    const str = typeof val === 'string' ? val : JSON.stringify(val)
    return str.length > 40 ? str.slice(0, 40) + '…' : str
  }
  return ''
}

/**
 * 按工具类别统计分组（用于 ToolCallGroupRow 摘要）
 */
export function summarizeToolGroup(
  pairs: Array<{ toolName: string }>
): string {
  const counts: Record<string, number> = {}
  for (const p of pairs) {
    const cat = categorizeTool(p.toolName)
    counts[cat] = (counts[cat] || 0) + 1
  }
  return Object.entries(counts)
    .map(([cat, n]) => `${cat} ${n} 次`)
    .join(', ')
}

/** 简单工具分类 */
function categorizeTool(name: string): string {
  const lower = name.toLowerCase()
  if (lower.includes('query') || lower.includes('search') || lower.includes('get')) return '查询'
  if (lower.includes('analyze') || lower.includes('eval') || lower.includes('check')) return '分析'
  if (lower.includes('generate') || lower.includes('create') || lower.includes('build')) return '生成'
  if (lower.includes('send') || lower.includes('notify') || lower.includes('push')) return '推送'
  return '调用'
}
