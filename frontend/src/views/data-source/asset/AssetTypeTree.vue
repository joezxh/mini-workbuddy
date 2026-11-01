<template>
  <div class="asset-tree">
    <a-spin :spinning="loading">
      <a-tree
        v-if="treeData.length"
        :tree-data="treeData"
        :default-expand-all="true"
        :selected-keys="selectedKeys"
        block-node
        @select="onSelect"
      />
      <a-empty v-else :description="t2('暂无已接入数据源')" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产类型树（AF-01，E40 /assets/tree）：类型分组 + 连接节点 + 表数角标。
 * 选中连接节点 emit `select-source`；「全部」节点 emit null（不限 source_id）。
 */
import { ref } from 'vue'
import { assetsTree } from '@/api/dataops'
import { t2 } from '../ontology/ontologyText'

const emit = defineEmits<{ (e: 'select-source', sourceId: number | null): void }>()

const loading = ref(false)
const treeData = ref<any[]>([])
const selectedKeys = ref<string[]>(['all'])

async function reload() {
  loading.value = true
  try {
    const resp: any = await assetsTree()
    const groups: any[] = Array.isArray(resp) ? resp : []
    treeData.value = [
      {
        key: 'all',
        title: t2('全部来源'),
        selectable: true,
        children: groups.map((g) => ({
          key: `type:${g.code}`,
          title: `${g.label}（${g.count ?? 0}）`,
          selectable: false,
          children: (g.children || []).map((c: any) => ({
            key: `source:${c.id}`,
            title: `${c.label}${c.count != null ? ` [${c.count}]` : ''}`,
            selectable: true,
            isLeaf: true,
          })),
        })),
      },
    ]
  } finally {
    loading.value = false
  }
}

function onSelect(keys: string[]) {
  const key = keys[0]
  if (!key) {
    selectedKeys.value = ['all']
    emit('select-source', null)
    return
  }
  if (key.startsWith('source:')) {
    selectedKeys.value = [key]
    emit('select-source', Number(key.slice('source:'.length)))
  }
  // type 节点不可选，点击不改选中态（a-tree 仍会回调，这里忽略）
}

reload()
defineExpose({ reload })
</script>

<style lang="less" scoped>
.asset-tree {
  height: 100%;
  overflow: auto;
}
</style>
