<template>
  <div class="schema-tree">
    <div class="schema-tree__search">
      <a-input-search
        v-model:value="keyword"
        :placeholder="t('knowledge.common.search')"
        allow-clear
        size="small"
      />
    </div>
    <div class="schema-tree__body">
      <a-tree
        v-if="filteredTree.length"
        :tree-data="filteredTree"
        :default-expand-all="false"
        :field-names="{ title: 'title', key: 'key', children: 'children' }"
        @select="onSelect"
      >
        <template #title="{ data }">
          <span class="schema-tree__node" :class="`schema-tree__node--${data.level}`">
            <component :is="iconFor(data.level)" v-if="data.level !== 'column'" />
            <span>{{ data.title }}</span>
            <a-tag v-if="data.tag" size="small" class="schema-tree__tag">{{ data.tag }}</a-tag>
          </span>
        </template>
      </a-tree>
      <a-empty v-else :description="t('knowledge.common.empty')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { DatabaseOutlined, TableOutlined, ColumnHeightOutlined } from '@ant-design/icons-vue'

export interface SchemaNode {
  key: string
  title: string
  level: 'db' | 'table' | 'column'
  tag?: string
  children?: SchemaNode[]
}

const props = defineProps<{ data?: SchemaNode[] }>()
const emit = defineEmits<{ (e: 'select', node: SchemaNode): void }>()
const { t } = useI18n()
const keyword = ref('')

function iconFor(level: string) {
  return level === 'db' ? DatabaseOutlined : level === 'table' ? TableOutlined : ColumnHeightOutlined
}

function match(node: SchemaNode): boolean {
  if (!keyword.value) return true
  const k = keyword.value.toLowerCase()
  if (node.title.toLowerCase().includes(k)) return true
  return (node.children || []).some(match)
}

const filteredTree = computed(() =>
  (props.data || []).map((db) => ({
    ...db,
    children: (db.children || []).filter(match).map((tb) => ({
      ...tb,
      children: keyword.value ? (tb.children || []).filter((c) => c.title.toLowerCase().includes(keyword.value.toLowerCase())) : tb.children,
    })),
  })).filter(match),
)

function onSelect(_keys: any[], info: any) {
  emit('select', info.node as SchemaNode)
}
</script>

<style lang="less" scoped>
.schema-tree {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__search {
    margin-bottom: 8px;
  }

  &__body {
    flex: 1;
    overflow: auto;
  }

  &__node {
    display: inline-flex;
    align-items: center;
    gap: 6px;

    &--column {
      color: var(--fg-secondary);
      font-size: 12.5px;
    }
  }

  &__tag {
    margin-left: 4px;
  }
}
</style>
