/**
 * 本体工作台文案入口（i18n 单点注入，spec §6.3）。
 *
 * 组件层所有可见文案统一经 `t2(中文原文)` 收口：中文原文即文案键，
 * 译文登记在 `@/i18n/ontologyLocale`（ONTOLOGY_UI，中文→en-US/ja-JP）。
 * 这里响应式读取 vue-i18n 当前 locale——`setLocale` 后模板重渲染即换文案；
 * 未翻译串优雅回退（zh 系→原文，其余→en-US→原文），组件层零改动。
 */
import i18n from '@/i18n'
import { translateOntology } from '@/i18n/ontologyLocale'

/** 按当前 locale 解析本体文案；入参为中文原文（同时是 zh 环境的显示值） */
export function t2(zh: string): string {
  // 读取 .value 建立渲染依赖：语言切换时调用方模板自动重渲染
  const locale = String(i18n.global.locale.value ?? 'zh-CN')
  return translateOntology(zh, locale)
}
