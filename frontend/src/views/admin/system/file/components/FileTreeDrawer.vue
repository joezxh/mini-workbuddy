<template>
  <a-drawer
    :open="open"
    title="文件目录"
    placement="left"
    :width="300"
    @close="$emit('update:open', false)"
  >
    <a-tree
      :tree-data="treeData"
      :selected-keys="selected ? [selected] : []"
      default-expand-all
      @select="onSelect"
    />
    <div class="tree-empty-hint">选择目录可按路径筛选文件</div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DirectoryItem } from '@/api/file'

const props = defineProps<{
  open: boolean
  directories: DirectoryItem[]
  selected: string
}>()
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'select', path: string): void
}>()

interface TreeNode { title: string; key: string; children: TreeNode[] }

const treeData = computed(() => [
  { title: '全部文件', key: '', children: props.directories.map(toNode) }
])

function toNode(item: DirectoryItem): TreeNode {
  return { title: item.name, key: item.path, children: item.children.map(toNode) }
}
function onSelect(keys: Array<string | number>) {
  emit('select', String(keys[0] ?? ''))
}
</script>

<style scoped lang="less">
.tree-empty-hint { margin-top: 16px; font-size: 12px; color: var(--fg-secondary); }
</style>
