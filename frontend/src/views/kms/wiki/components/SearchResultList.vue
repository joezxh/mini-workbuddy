<template>
  <a-list :data-source="items" :loading="loading" size="small" :locale="{ emptyText: '暂无检索结果' }">
    <template #renderItem="{ item }">
      <a-list-item>
        <a-list-item-meta>
          <template #title>
            <a @click="open(item)">{{ item.title }}</a>
          </template>
          <template #description>
            <div class="snippet">{{ item.snippet }}</div>
            <a-tag v-if="item.score" color="blue" size="small">
              相关度 {{ item.score }}
            </a-tag>
          </template>
        </a-list-item-meta>
      </a-list-item>
    </template>
  </a-list>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { SearchItem } from '../types/wiki'

defineProps<{ items: SearchItem[]; loading?: boolean }>()
const router = useRouter()

function open(item: SearchItem) {
  router.push(`/wiki/${item.slug}`)
}
</script>

<style scoped>
.snippet {
  color: var(--fg-muted, #666);
  font-size: 13px;
  margin: 4px 0;
}
</style>
