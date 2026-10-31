<template>
  <GraphCanvas
    ref="canvasRef"
    :nodes="canvasNodes"
    :edges="canvasEdges"
    :selection="selection"
    :focus-node-codes="highlightCodes || []"
    :focus-edge-codes="highlightRelationCodes || []"
    :loading="loading"
    :hint-text="t('kbMgmt.graph.selectHint')"
    :legend-size-text="t('kbMgmt.graph.legendNodeSize')"
    :empty-title="t('kbMgmt.graph.empty')"
    :empty-desc="t('kbMgmt.graph.graphEmptyDesc')"
    :empty-action-text="canvasNodes.length ? '' : t('kbMgmt.graph.modeFull')"
    @select="emit('select', $event)"
    @empty-action="emit('clear-filter')"
  />
</template>

<script setup lang="ts">
/**
 * 标准关系图：共享 SVG 画布的薄壳。
 *
 * 只做「原始对象/关系 → 画布节点/边」的取色取标签（graphViewUtils），
 * 布局、指针、分色图例、三态淡化全部交给 GraphCanvas；不发请求、不做筛选。
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import GraphCanvas from '@/components/common/graph/GraphCanvas.vue'
import type { CanvasEdge, CanvasNode, CanvasSelection } from '@/components/common/graph/graphTypes'
import { toCanvasEdges, toCanvasNodes, type StdGraphEdge, type StdGraphNode } from './graphViewUtils'

const props = defineProps<{
  nodes: StdGraphNode[]
  edges: StdGraphEdge[]
  selection: CanvasSelection | null
  /** 高亮对象标准 code（NL 检索 / 下钻联动）：无选中时当焦点做邻接淡化 */
  highlightCodes?: string[]
  /** 高亮关系标准 code（NL 检索命中边） */
  highlightRelationCodes?: string[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', v: CanvasSelection | null): void
  (e: 'clear-filter'): void
}>()

const { t } = useI18n()
const canvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)

const canvasNodes = computed<CanvasNode[]>(() => toCanvasNodes(props.nodes || []))
const canvasEdges = computed<CanvasEdge[]>(() => toCanvasEdges(props.edges || []))

/** 父级工具栏「在图中定位」：把 id 居中（透传画布 expose） */
function locate(id: number) {
  canvasRef.value?.locate(id)
}
defineExpose({ locate })
</script>
