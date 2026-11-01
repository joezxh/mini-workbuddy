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
      >
        <template #title="node">
          <span v-if="node.dotClass !== undefined" class="tn">
            <span :class="['dotk', node.dotClass]" />
            <span class="nm">{{ node.title }}</span>
          </span>
          <span v-else>{{ node.title }}</span>
        </template>
      </a-tree>
      <a-empty v-else :description="t2('暂无已接入数据源')" />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产类型树（AF-01，E40 /assets/tree）：external_type 分组 + 连接节点 + 探活状态点。
 * 数据映射委托纯函数 :func:`buildAssetTree`（空组「暂无连接」占位、online 绿点/其余灰点）；
 * 选中连接节点 emit `select-source`；「全部」节点 emit null（不限 source_id）。
 */
import { ref } from 'vue'
import { assetsTree } from '@/api/dataops'
import { t2 } from '../ontology/ontologyText'
import { buildAssetTree, type AssetTreeNode } from './assetTree'

const emit = defineEmits<{ (e: 'select-source', sourceId: number | null): void }>()

const loading = ref(false)
const treeData = ref<AssetTreeNode[]>([])
const selectedKeys = ref<string[]>(['all'])

async function reload() {
  loading.value = true
  try {
    const resp: any = await assetsTree()
    const groups: any[] = Array.isArray(resp) ? resp : []
    treeData.value = buildAssetTree(groups, t2)
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
  // type/empty 节点不可选，点击不改选中态（a-tree 仍会回调，这里忽略）
}

reload()
defineExpose({ reload })
</script>

<style lang="less" scoped>
.asset-tree {
  height: 100%;
  overflow: auto;
}
.tn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.tn .nm {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
// 探活状态点（复制原型 .tn .dotk 口径：online 绿、其余灰）
.dotk {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #52c41a;
  flex-shrink: 0;
}
.dotk.off {
  background: #d9d9d9;
}
</style>
