<template>
  <div class="general-renderer">
    <!-- 思考块 -->
    <div v-if="parsed.thinking" :class="['thinking-block', streaming ? 'streaming' : 'done']">
      <div class="thinking-header" @click="$emit('toggle-thinking')">
        <span class="thinking-icon">🧠</span>
        <span class="thinking-title">{{ streaming ? '正在思考' : '思考过程' }}</span>
        <span v-if="!streaming" class="thinking-toggle-btn">
          {{ expanded ? '收起 ▲' : '展开 ▼' }}
        </span>
        <span v-else class="streaming-dots"><span></span><span></span><span></span></span>
      </div>
      <transition name="collapse">
        <div v-if="streaming || expanded" class="thinking-body">
          <div class="thinking-text" v-html="renderMarkdown(parsed.thinking)"></div>
          <span v-if="streaming" class="typing-cursor">▋</span>
        </div>
      </transition>
    </div>

    <!-- 正文 Markdown（含超链接 hover 弹窗） -->
    <div v-if="parsed.rawContent" :class="['msg-bubble', 'ai-bubble', { 'streaming-bubble': streaming }]">
      <div
        class="msg-markdown"
        v-html="processedContent"
        @mouseover="handleCombinedHover($event)"
        @mouseout="handleCombinedLeave"
      ></div>
      <span v-if="streaming" class="typing-cursor">▋</span>
    </div>

    <!-- 法条/类案 Hover 弹窗 -->
    <div
      v-if="refPopover.visible"
      class="ref-popover"
      :style="{ top: refPopover.y + 'px', left: refPopover.x + 'px' }"
    >
      <a-spin v-if="refPopover.loading" size="small" />
      <template v-else>
        <div class="ref-popover-title">{{ refPopover.title }}</div>
        <div class="ref-popover-body" v-html="refPopover.content"></div>
      </template>
    </div>
    <!-- 实体 Hover 弹窗 -->
    <EntityPopover
      :popover="entityPopover"
      @enter="onEntityPopoverEnter"
      @leave="onEntityPopoverLeave"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from 'vue'
import type { ParsedMsg } from '../types'
import { renderMarkdown } from '../markdown'
import { useEntityPopover } from '../useEntityPopover'
import EntityPopover from '../EntityPopover.vue'

const props = defineProps<{
  parsed: ParsedMsg
  streaming?: boolean
  expanded?: boolean
}>()

defineEmits<{
  (e: 'toggle-thinking'): void
}>()

// ── 超链接后处理 HTML 缓存 ─────────────────────────────────────────────────
const processedContent = computed(() => renderMarkdown(props.parsed.rawContent || ''))

// ── 法条/类案 Hover 弹窗 ──────────────────────────────────────────────────────
const refPopover = reactive({
  visible: false,
  loading: false,
  x: 0,
  y: 0,
  title: '',
  content: '',
})

let popoverTimer: ReturnType<typeof setTimeout> | null = null

async function handleRefHover(event: MouseEvent) {
  const target = (event.target as HTMLElement).closest('a[data-ref-type]') as HTMLElement | null
  if (!target) return

  const refType = target.dataset.refType
  const refId = target.dataset.refId
  const refKeyword = target.dataset.refKeyword || ''

  if (popoverTimer) clearTimeout(popoverTimer)
  popoverTimer = setTimeout(async () => {
    const rect = target.getBoundingClientRect()
    refPopover.x = rect.left
    refPopover.y = rect.bottom + 6
    refPopover.visible = true
    refPopover.loading = true
    refPopover.title = refKeyword
    refPopover.content = ''

    try {
      if (refType === 'legal' && refId) {
        // 法律法条 API 已移除，显示占位信息
        refPopover.title = refKeyword
        refPopover.content = '法律法条模块已清理'
      } else if (refType === 'case' && refId) {
        // 案例 API 已移除，显示占位信息
        refPopover.title = refKeyword
        refPopover.content = '案例模块已清理'
      } else if (refType === 'person' && refId) {
        const { getPersonByIdCard } = await import('@/api/aiSession')
        const detail = await getPersonByIdCard(refId)
        if (detail) {
          refPopover.title = detail.real_name || refKeyword
          const riskLabel: Record<string, string> = { high: '高', medium: '中', low: '低' }
          refPopover.content = [
            `<p><b>身份证号：</b>${detail.id_card || refId}</p>`,
            detail.gender ? `<p><b>性别：</b>${detail.gender}</p>` : '',
            detail.age ? `<p><b>年龄：</b>${detail.age}</p>` : '',
            detail.person_type ? `<p><b>人员类型：</b>${detail.person_type}</p>` : '',
            detail.occupation ? `<p><b>职业：</b>${detail.occupation}</p>` : '',
            detail.current_region_name ? `<p><b>管辖地区：</b>${detail.current_region_name}</p>` : '',
            `<p><b>风险等级：</b><span style="color:${detail.risk_level === 'high' ? '#e53e3e' : detail.risk_level === 'medium' ? '#dd6b20' : '#38a169'}">${riskLabel[detail.risk_level] || detail.risk_level}</span></p>`,
            detail.is_key_person ? '<p><b>⚠ 重点人员</b></p>' : '',
          ].filter(Boolean).join('')
        } else {
          refPopover.title = '人员信息'
          refPopover.content = `<p>未找到身份证号 ${refId} 对应的风险人员记录</p>`
        }
      } else if (refType === 'entity' && refId) {
        const { getEntityByCreditCode } = await import('@/api/aiSession')
        const detail = await getEntityByCreditCode(refId)
        if (detail) {
          refPopover.title = detail.entity_name || refKeyword
          const riskLabel: Record<string, string> = { high: '高', medium: '中', low: '低' }
          refPopover.content = [
            `<p><b>信用代码：</b>${detail.unified_social_credit_code || refId}</p>`,
            detail.entity_type ? `<p><b>企业类型：</b>${detail.entity_type}</p>` : '',
            detail.legal_person ? `<p><b>法定代表人：</b>${detail.legal_person}</p>` : '',
            detail.registered_capital ? `<p><b>注册资本：</b>${detail.registered_capital}万元</p>` : '',
            detail.industry ? `<p><b>行业：</b>${detail.industry}</p>` : '',
            detail.registered_address ? `<p><b>注册地址：</b>${detail.registered_address}</p>` : '',
            `<p><b>风险等级：</b><span style="color:${detail.risk_level === 'high' ? '#e53e3e' : detail.risk_level === 'medium' ? '#dd6b20' : '#38a169'}">${riskLabel[detail.risk_level] || detail.risk_level}</span></p>`,
          ].filter(Boolean).join('')
        } else {
          refPopover.title = '企业信息'
          refPopover.content = `<p>未找到信用代码 ${refId} 对应的风险企业记录</p>`
        }
      } else if (refType === 'entity-name' && refId) {
        const { getEntityByName } = await import('@/api/aiSession')
        const detail = await getEntityByName(refKeyword || refId)
        if (detail) {
          refPopover.title = detail.entity_name || refKeyword
          const riskLabel: Record<string, string> = { high: '高', medium: '中', low: '低' }
          refPopover.content = [
            detail.unified_social_credit_code ? `<p><b>信用代码：</b>${detail.unified_social_credit_code}</p>` : '',
            detail.entity_type ? `<p><b>企业类型：</b>${detail.entity_type}</p>` : '',
            detail.legal_person ? `<p><b>法定代表人：</b>${detail.legal_person}</p>` : '',
            detail.registered_capital ? `<p><b>注册资本：</b>${detail.registered_capital}万元</p>` : '',
            detail.industry ? `<p><b>行业：</b>${detail.industry}</p>` : '',
            detail.registered_address ? `<p><b>注册地址：</b>${detail.registered_address}</p>` : '',
            `<p><b>风险等级：</b><span style="color:${detail.risk_level === 'high' ? '#e53e3e' : detail.risk_level === 'medium' ? '#dd6b20' : '#38a169'}">${riskLabel[detail.risk_level] || detail.risk_level}</span></p>`,
          ].filter(Boolean).join('')
        } else {
          refPopover.title = '企业信息'
          refPopover.content = `<p>未找到"${refKeyword || refId}"对应的风险企业记录</p>`
        }
      } else if (refType === 'law' && refId) {
        const { getLegalByTitle } = await import('@/api/aiSession')
        const detail = await getLegalByTitle(refKeyword || '')
        if (detail) {
          refPopover.title = detail.law_title || refKeyword
          const timelinesMap: Record<number, string> = { 1: '现行有效', 2: '已修改', 3: '已废止', 4: '尚未生效' }
          refPopover.content = [
            detail.release_org ? `<p><b>发布机关：</b>${detail.release_org}</p>` : '',
            detail.release_date ? `<p><b>发布时间：</b>${detail.release_date}</p>` : '',
            detail.implement_date ? `<p><b>施行时间：</b>${detail.implement_date}</p>` : '',
            detail.disable_date ? `<p><b>失效时间：</b>${detail.disable_date}</p>` : '',
            detail.timelines ? `<p><b>时效性：</b>${timelinesMap[detail.timelines] || detail.timelines}</p>` : '',
            detail.keywords ? `<p><b>关键字：</b>${detail.keywords}</p>` : '',
          ].filter(Boolean).join('') || '暂无法律详细信息'
        } else {
          refPopover.title = '法律信息'
          refPopover.content = `<p>未找到"${refKeyword}"对应的法律记录</p>`
        }
      } else if (refType === 'person-name' && refId) {
        // 当事人姓名 → 查找风险人员
        const { getPersonByName } = await import('@/api/aiSession')
        const detail = await getPersonByName(refKeyword || '')
        if (detail) {
          refPopover.title = detail.real_name || refKeyword
          const riskLabel: Record<string, string> = { high: '高', medium: '中', low: '低' }
          refPopover.content = [
            detail.id_card ? `<p><b>身份证号：</b>${detail.id_card}</p>` : '',
            detail.gender ? `<p><b>性别：</b>${detail.gender}</p>` : '',
            detail.age ? `<p><b>年龄：</b>${detail.age}</p>` : '',
            detail.person_type ? `<p><b>人员类型：</b>${detail.person_type}</p>` : '',
            detail.occupation ? `<p><b>职业：</b>${detail.occupation}</p>` : '',
            detail.current_region_name ? `<p><b>管辖地区：</b>${detail.current_region_name}</p>` : '',
            `<p><b>风险等级：</b><span style="color:${detail.risk_level === 'high' ? '#e53e3e' : detail.risk_level === 'medium' ? '#dd6b20' : '#38a169'}">${riskLabel[detail.risk_level] || detail.risk_level}</span></p>`,
            detail.is_key_person ? '<p><b>⚠ 重点人员</b></p>' : '',
          ].filter(Boolean).join('')
        } else {
          refPopover.title = '人员信息'
          refPopover.content = `<p>未找到"${refKeyword}"对应的风险人员记录</p>`
        }
      }
    } catch (e) {
      refPopover.content = '加载失败，请稍后重试'
    } finally {
      refPopover.loading = false
    }
  }, 300)
}

function handleRefLeave() {
  if (popoverTimer) { clearTimeout(popoverTimer); popoverTimer = null }
  setTimeout(() => { refPopover.visible = false }, 200)
}

// ── 实体 Hover 弹窗 ──────────────────────────────────────────────────────────
const { popover: entityPopover, handleEntityHover, handleEntityLeave } = useEntityPopover()

let entityPopoverTimer: ReturnType<typeof setTimeout> | null = null
function onEntityPopoverEnter() {
  if (entityPopoverTimer) { clearTimeout(entityPopoverTimer); entityPopoverTimer = null }
}
function onEntityPopoverLeave() {
  entityPopoverTimer = setTimeout(() => { entityPopover.visible = false }, 200)
}

/** 组合 Hover：同时处理法条/类案弹窗和实体弹窗 */
function handleCombinedHover(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.closest('.entity-link[data-entity-type]')) {
    handleEntityHover(event)
    return
  }
  handleRefHover(event)
}

function handleCombinedLeave() {
  handleRefLeave()
  handleEntityLeave()
}
</script>

<style scoped lang="less">
.thinking-block {
  margin-bottom: 8px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;

  &.streaming { border-color: #91caff; background: #f0f7ff; }
}
.thinking-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; cursor: pointer; user-select: none;
  &:hover { background: #f0f0f0; }
}
.thinking-icon { font-size: 14px; }
.thinking-title { font-size: 12px; font-weight: 600; color: #666; }
.thinking-toggle-btn { font-size: 11px; color: #999; margin-left: auto; }
.streaming-dots {
  margin-left: auto; display: flex; gap: 3px;
  span { width: 5px; height: 5px; border-radius: 50%; background: #1677ff; animation: dotBlink 1.2s infinite; }
  span:nth-child(2) { animation-delay: .2s; }
  span:nth-child(3) { animation-delay: .4s; }
}
@keyframes dotBlink { 0%,80%,100% { opacity: .3; } 40% { opacity: 1; } }
.thinking-body { padding: 8px 12px; border-top: 1px solid #f0f0f0; max-height: 300px; overflow-y: auto; }
.thinking-text { font-size: 13px; color: #555; line-height: 1.6; }
.typing-cursor { animation: blink 1s step-end infinite; color: #1677ff; }
@keyframes blink { 50% { opacity: 0; } }
.msg-bubble { position: relative; }
.streaming-bubble { border-color: #91caff; }
.collapse-enter-active, .collapse-leave-active { transition: all .2s ease; }
.collapse-enter-from, .collapse-leave-to { max-height: 0; opacity: 0; padding: 0 12px; }

// ── 法条/类案 Hover 弹窗 ──
.ref-popover {
  position: fixed; z-index: 1050;
  max-width: 420px; min-width: 240px;
  background: #fff; border-radius: 8px;
  box-shadow: 0 6px 24px rgba(0,0,0,.12);
  border: 1px solid #e8e8e8;
  padding: 12px 16px;
  pointer-events: auto;
}
.ref-popover-title { font-size: 13px; font-weight: 700; color: #1a1a1a; margin-bottom: 8px; border-bottom: 1px solid #f0f0f0; padding-bottom: 6px; }
.ref-popover-body { font-size: 12px; color: #555; line-height: 1.7; max-height: 260px; overflow-y: auto; }

// ── 实体链接样式 ──
:deep(.entity-link) {
  color: #1677ff;
  cursor: pointer;
  border-bottom: 1px dashed #1677ff;
  padding: 0 1px;
  transition: all 0.15s;

  &:hover {
    background: #e6f4ff;
    border-bottom-style: solid;
  }

  &.entity-person {
    color: #52c41a;
    border-bottom-color: #52c41a;
    &:hover { background: #f6ffed; }
  }

  &.entity-location {
    color: #fa8c16;
    border-bottom-color: #fa8c16;
    &:hover { background: #fff7e6; }
  }
}

// ── ref 链接样式（法条/类案/人员/企业/法律） ──
:deep(a.ref-legal),
:deep(a.ref-case),
:deep(a.ref-person),
:deep(a.ref-entity),
:deep(a.ref-law) {
  cursor: pointer;
  border-bottom: 1px dashed;
  padding: 0 1px;
  transition: all 0.15s;
  text-decoration: none;
}
:deep(a.ref-legal) {
  color: #722ed1; border-bottom-color: #722ed1;
  &:hover { background: #f9f0ff; border-bottom-style: solid; }
}
:deep(a.ref-case) {
  color: #1677ff; border-bottom-color: #1677ff;
  &:hover { background: #e6f4ff; border-bottom-style: solid; }
}
:deep(a.ref-person) {
  color: #52c41a; border-bottom-color: #52c41a;
  &:hover { background: #f6ffed; border-bottom-style: solid; }
}
:deep(a.ref-entity) {
  color: #fa8c16; border-bottom-color: #fa8c16;
  &:hover { background: #fff7e6; border-bottom-style: solid; }
}
:deep(a.ref-law) {
  color: #13c2c2; border-bottom-color: #13c2c2;
  &:hover { background: #e6fffb; border-bottom-style: solid; }
}
</style>
