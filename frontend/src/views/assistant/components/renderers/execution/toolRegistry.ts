import type { VNode } from 'vue'
import type { ToolCallPair } from '../types/timeline'
import type { ToolRenderer } from './types'
import { DefaultToolRenderer } from './DefaultToolRenderer'

/** 工具渲染器注册表 — Record<string, ToolRenderer> 模式 */
const renderers: Record<string, ToolRenderer> = {}

/** 获取渲染器，未注册时返回空对象（回退到默认实现） */
function getRenderer(toolName: string): ToolRenderer {
  return renderers[toolName] ?? {}
}

/** 获取工具显示名称 */
export function getDisplayName(pair: ToolCallPair): string {
  const r = getRenderer(pair.toolName)
  return r.getDisplayName?.(pair) ?? pair.toolName
}

/** 渲染触发行 header */
export function renderHeader(pair: ToolCallPair): VNode | string {
  const r = getRenderer(pair.toolName)
  return r.renderHeader?.(pair) ?? DefaultToolRenderer.renderHeader!(pair)
}

/** 渲染展开内容 body — 返回 null 表示不可展开 */
export function renderBody(pair: ToolCallPair): VNode | null {
  const r = getRenderer(pair.toolName)
  return r.renderBody?.(pair) ?? DefaultToolRenderer.renderBody!(pair) ?? null
}

/** 注册新的工具渲染器 */
export function registerToolRenderer(toolName: string, renderer: ToolRenderer) {
  renderers[toolName] = renderer
}
