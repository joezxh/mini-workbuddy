/**
 * 资产卡片文案/格式化工具（AF-05，从原型 JS 移植）。
 *
 * - :func:`hl`：把首次命中的关键词包进 `<mark>`（输出已转义的 HTML，调用处 `v-html`）；
 * - :func:`fmtRows`：行数按 亿/万 缩写，取整口径忠实复刻原型（≥1e8→1 位小数亿；≥1e6→0 位万；1e4..1e6→1 位万）。
 */

/** HTML 转义（与原型 `esc` 一致，仅处理 & < > "） */
export function esc(s: unknown): string {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string))
}

/** 大小写不敏感高亮首次命中；无命中或空词仅转义整串 */
export function hl(text: unknown, kw: string): string {
  const t = String(text ?? '')
  if (!kw) return esc(t)
  const i = t.toLowerCase().indexOf(kw.toLowerCase())
  if (i < 0) return esc(t)
  return esc(t.slice(0, i)) + '<mark>' + esc(t.slice(i, i + kw.length)) + '</mark>' + esc(t.slice(i + kw.length))
}

/** 行数缩写；null/undefined → 占位 '-' */
export function fmtRows(n: number | null | undefined): string {
  if (n == null) return '-'
  if (n >= 1e8) return (n / 1e8).toFixed(1) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(n >= 1e6 ? 0 : 1) + '万'
  return String(n)
}
