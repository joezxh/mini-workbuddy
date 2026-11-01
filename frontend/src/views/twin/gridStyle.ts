// frontend/src/views/twin/gridStyle.ts
import type { CSSProperties } from 'vue'
const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi)
export function gridStyleOf(grid: Record<string, unknown> | null): CSSProperties & Record<string, string> {
  const g = grid ?? {}
  const x = clamp(Number(g.x ?? 1), 1, 12)
  const y = clamp(Number(g.y ?? 1), 1, 64)
  const w = clamp(Number(g.w ?? 3), 1, 12)
  const h = clamp(Number(g.h ?? 2), 1, 64)
  return { gridColumn: `${x} / span ${w}`, gridRow: `${y} / span ${h}` }
}
