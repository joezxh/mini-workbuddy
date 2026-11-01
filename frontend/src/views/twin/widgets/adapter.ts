// frontend/src/views/twin/widgets/adapter.ts
// wire 形状 → 组件 props 的薄纯函数适配（只转置键名，不重定义语义；spec §5）
type Rec = Record<string, any>
export function toMultiLine(d: { records: Rec[]; t: string; values: string[] }) {
  return {
    xAxis: (d.records ?? []).map((r) => String(r[d.t] ?? '')),
    series: (d.values ?? []).map((v) => ({ name: v, data: (d.records ?? []).map((r) => r[v] ?? null) })),
  }
}
export function toBar(d: { records: Rec[]; t: string; values: string[] }) {
  const key = (d.values ?? [])[0]
  return (d.records ?? []).map((r) => ({ name: String(r[d.t] ?? ''), value: Number(r[key] ?? 0) }))
}
export function toPie(d: { records: Rec[]; parts: string[] }) {
  const [k, v] = d.parts ?? []
  return (d.records ?? []).map((r) => ({ name: String(r[k] ?? ''), value: Number(r[v] ?? 0) }))
}
export const toTable = (d: { records?: Rec[] }) => d.records ?? []
export const kpiValue = (d: { value?: unknown }) => d?.value ?? null
