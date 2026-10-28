<template>
  <div class="std-tree">
    <a-spin :spinning="loading">
      <a-tree
        v-if="treeData.length"
        :tree-data="treeData"
        :field-names="fieldNames"
        :selected-keys="selectedKeys"
        block-node
        default-expand-all
        @select="onSelect"
      />
      <a-empty v-else :description="t('kbMgmt.catalog.empty')" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
/**
 * 标准中心目录树（纯展示）：数据由父组件用 `listCatalogs()` 拉取后经 props 注入，
 * 便于在 node 环境（无 DOM）下做渲染测，也让父组件复用同一份目录数据喂对象表单。
 */
import { useI18n } from 'vue-i18n'

withDefaults(
  defineProps<{
    treeData: any[]
    selectedKeys?: (string | number)[]
    loading?: boolean
  }>(),
  { selectedKeys: () => [], loading: false },
)

const { t } = useI18n()
const emit = defineEmits<{ (e: 'select', catalogId: number | null): void }>()

const fieldNames = { title: 'name', key: 'id', children: 'children' }

/** 取消选中（空 keys）= 回到「全部对象」 */
function onSelect(keys: (string | number)[]) {
  emit('select', keys.length ? Number(keys[0]) : null)
}
</script>

<style scoped>
.std-tree {
  min-height: 120px;
}
</style>
