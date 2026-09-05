/**
 * 实体 Hover 弹窗组合式函数
 * 用于 AI 输出文本中的企业/人员/地点实体识别与 Hover 弹窗交互
 */
import { reactive } from 'vue'
import { lookupEntities, type EntityLookupResult } from '@/api/aiSession'

// ── 类型定义 ─────────────────────────────────────────────────────────────────

export type EntityType = 'entity' | 'person' | 'location'

export interface EntityData {
  type: EntityType
  id: number
  name: string
  detail: Record<string, any>
}

export interface EntityPopoverState {
  visible: boolean
  loading: boolean
  x: number
  y: number
  entityType: EntityType
  entityData: EntityData | null
}

// ── 缓存 ─────────────────────────────────────────────────────────────────────

/** 全局实体查询缓存（name -> EntityData | null） */
const entityCache = new Map<string, EntityData | null>()

// ── 工具函数 ─────────────────────────────────────────────────────────────────

/** 从文本中提取候选实体名称（匹配 [中文名称] 模式） */
function extractCandidateNames(text: string): string[] {
  const names = new Set<string>()
  // 匹配 [xxx] 中的中文名称（至少 2 个中文字符）
  const bracketRe = /\[([^\[\]]{2,50})\]/g
  let m: RegExpExecArray | null
  while ((m = bracketRe.exec(text)) !== null) {
    const candidate = m[1].trim()
    // 过滤掉明显是编码/数字的内容（如组织机构编码:xxx）
    if (/^[\dA-Za-z:：\-_/]+$/.test(candidate)) continue
    // 提取纯中文部分（去除前缀如 "组织机构编码:"）
    const chinesePart = candidate.replace(/^[^一-龟]+[:：]/, '').trim()
    if (/^[\u4e00-\u9fff\u3400-\u4dbf]{2,}$/.test(chinesePart)) {
      names.add(chinesePart)
    }
    // 也保留原始候选名（如果是纯中文）
    if (/^[\u4e00-\u9fff\u3400-\u4dbf]{2,}$/.test(candidate)) {
      names.add(candidate)
    }
  }
  return Array.from(names)
}

/** 将后端返回的实体转换为 EntityData */
function toEntityData(type: EntityType, item: any): EntityData {
  const name =
    type === 'entity' ? item.entity_name :
    type === 'person' ? item.real_name :
    item.location_name
  return { type, id: item[`${type}_id`] || item.entity_id || item.person_id || item.location_id, name, detail: item }
}

// ── Composable ───────────────────────────────────────────────────────────────

export function useEntityPopover() {
  const popover = reactive<EntityPopoverState>({
    visible: false,
    loading: false,
    x: 0,
    y: 0,
    entityType: 'entity',
    entityData: null,
  })

  /** 已处理的文本缓存（原始文本 -> 处理后 HTML） */
  const processedHtmlCache = new Map<string, string>()

  let popoverTimer: ReturnType<typeof setTimeout> | null = null

  /**
   * 处理原始文本：提取候选实体名 → 查询后端 → 替换为可交互链接 span
   * 返回处理后的 HTML 字符串（可直接用于 v-html）
   */
  async function processTextWithEntities(text: string): Promise<string> {
    if (!text) return ''

    // 检查缓存
    const cached = processedHtmlCache.get(text)
    if (cached) return cached

    // 提取候选名称
    const candidateNames = extractCandidateNames(text)
    if (candidateNames.length === 0) {
      processedHtmlCache.set(text, text)
      return text
    }

    // 查询后端（使用缓存）
    const toQuery: string[] = []
    const cachedResults = new Map<string, EntityData>()

    for (const name of candidateNames) {
      if (entityCache.has(name)) {
        const cached = entityCache.get(name)
        if (cached) cachedResults.set(name, cached)
      } else {
        toQuery.push(name)
      }
    }

    if (toQuery.length > 0) {
      try {
        const result = await lookupEntities(toQuery) as EntityLookupResult
        // 处理企业实体
        for (const e of result.entities || []) {
          const data = toEntityData('entity', e)
          entityCache.set(e.entity_name, data)
          cachedResults.set(e.entity_name, data)
          // 同时缓存归一化名称和简称
          if (e.entity_name !== e.entity_name) entityCache.set(e.entity_name, data)
        }
        // 处理人员
        for (const p of result.persons || []) {
          const data = toEntityData('person', p)
          entityCache.set(p.real_name, data)
          cachedResults.set(p.real_name, data)
        }
        // 处理地点
        for (const loc of result.locations || []) {
          const data = toEntityData('location', loc)
          entityCache.set(loc.location_name, data)
          cachedResults.set(loc.location_name, data)
        }
        // 未匹配到的名称缓存为 null（避免重复查询）
        const matchedNames = new Set([
          ...result.entities.map(e => e.entity_name),
          ...result.persons.map(p => p.real_name),
          ...result.locations.map(l => l.location_name),
        ])
        for (const name of toQuery) {
          if (!matchedNames.has(name)) entityCache.set(name, null)
        }
      } catch (e) {
        console.warn('[EntityPopover] 实体查询失败:', e)
      }
    }

    // 替换文本中的实体名称为交互链接
    let result = text
    // 按名称长度降序排列，优先匹配长名称（避免部分匹配）
    const sortedNames = Array.from(cachedResults.keys()).sort((a, b) => b.length - a.length)
    for (const name of sortedNames) {
      const data = cachedResults.get(name)!
      const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      // 匹配 [名称] 或 纯文本中的名称（避免重复替换已在 span 中的）
      const re = new RegExp(`\\[${escapedName}\\]`, 'g')
      const replacement = `<span class="entity-link entity-${data.type}" data-entity-type="${data.type}" data-entity-id="${data.id}">${name}</span>`
      result = result.replace(re, replacement)
    }

    processedHtmlCache.set(text, result)
    return result
  }

  /**
   * 处理已渲染的 HTML：在 HTML 中查找文本节点并替换实体名称
   * 用于 markdown 渲染后的后处理
   */
  async function processHtmlWithEntities(html: string): Promise<string> {
    if (!html) return ''

    // 从 HTML 中提取纯文本用于候选名称查找
    const tempDiv = typeof document !== 'undefined' ? document.createElement('div') : null
    let candidateNames: string[] = []
    if (tempDiv) {
      tempDiv.innerHTML = html
      const plainText = tempDiv.textContent || ''
      candidateNames = extractCandidateNames(plainText)
    }

    // 如果没有 [xxx] 模式，尝试直接匹配已知实体
    if (candidateNames.length === 0) {
      // 从缓存中获取已知实体名称，直接在 HTML 文本中替换
      const knownNames = Array.from(entityCache.entries())
        .filter(([_, v]) => v !== null)
        .map(([k, v]) => ({ name: k, data: v! }))
        .filter(x => x.name.length >= 2)
        .sort((a, b) => b.name.length - a.name.length)

      let processed = html
      for (const { name, data } of knownNames) {
        // 只替换不在 HTML 标签内的文本（简单策略：只替换 >...< 之间的内容）
        const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        const re = new RegExp(`(?<=>)([^<]*?)${escapedName}([^<]*?)(?=<)`, 'g')
        processed = processed.replace(re, (_match, before, after) => {
          const replacement = `<span class="entity-link entity-${data.type}" data-entity-type="${data.type}" data-entity-id="${data.id}">${name}</span>`
          return `>${before}${replacement}${after}<`
        })
      }
      return processed
    }

    // 有候选名称时，先查询后端
    const toQuery: string[] = []
    for (const name of candidateNames) {
      if (!entityCache.has(name)) toQuery.push(name)
    }
    if (toQuery.length > 0) {
      try {
        const result = await lookupEntities(toQuery) as EntityLookupResult
        for (const e of result.entities || []) entityCache.set(e.entity_name, toEntityData('entity', e))
        for (const p of result.persons || []) entityCache.set(p.real_name, toEntityData('person', p))
        for (const loc of result.locations || []) entityCache.set(loc.location_name, toEntityData('location', loc))
        const matchedNames = new Set([
          ...result.entities.map(e => e.entity_name),
          ...result.persons.map(p => p.real_name),
          ...result.locations.map(l => l.location_name),
        ])
        for (const name of toQuery) {
          if (!matchedNames.has(name)) entityCache.set(name, null)
        }
      } catch { /* ignore */ }
    }

    // 在 HTML 中替换匹配实体
    let processed = html
    const sortedEntries = Array.from(entityCache.entries())
      .filter(([_, v]) => v !== null)
      .map(([k, v]) => ({ name: k, data: v! }))
      .filter(x => candidateNames.includes(x.name) || html.includes(x.name))
      .sort((a, b) => b.name.length - a.name.length)

    for (const { name, data } of sortedEntries) {
      const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      // 替换 [名称] 模式
      const bracketRe = new RegExp(`\\[${escapedName}\\]`, 'g')
      const replacement = `<span class="entity-link entity-${data.type}" data-entity-type="${data.type}" data-entity-id="${data.id}">${name}</span>`
      processed = processed.replace(bracketRe, replacement)
    }

    return processed
  }

  /** Hover 事件处理：鼠标悬停在实体链接上 */
  function handleEntityHover(event: MouseEvent) {
    const target = (event.target as HTMLElement).closest('.entity-link[data-entity-type]') as HTMLElement | null
    if (!target) return

    const entityType = target.dataset.entityType as EntityType
    const entityId = Number(target.dataset.entityId)

    // 从缓存中查找实体数据
    let entityData: EntityData | null = null
    for (const [, data] of entityCache.entries()) {
      if (data && data.id === entityId && data.type === entityType) {
        entityData = data
        break
      }
    }
    if (!entityData) return

    if (popoverTimer) clearTimeout(popoverTimer)
    popoverTimer = setTimeout(() => {
      const rect = target.getBoundingClientRect()
      popover.x = rect.left
      popover.y = rect.bottom + 6
      popover.entityType = entityType
      popover.entityData = entityData
      popover.visible = true
      popover.loading = false
    }, 300)
  }

  /** Hover 离开事件处理 */
  function handleEntityLeave() {
    if (popoverTimer) { clearTimeout(popoverTimer); popoverTimer = null }
    setTimeout(() => { popover.visible = false }, 200)
  }

  return {
    popover,
    processTextWithEntities,
    processHtmlWithEntities,
    handleEntityHover,
    handleEntityLeave,
  }
}
