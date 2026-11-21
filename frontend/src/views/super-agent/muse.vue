<script setup lang="ts">
// Muse 执行界面：单路由容器，左侧分组导航（SaSideNav）切换 chat/feed/ideas/goals，
// 这里用 v-show 内嵌四个视图，保证会话、SSE、筛选状态在切换时不被销毁。
// 对应原型 page-sa-chat / page-sa-feed / page-sa-ideas / page-sa-goals。
import { computed, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatView from './workbench/chat.vue'
import FeedView from './workbench/feed.vue'
import IdeasView from './workbench/ideas.vue'
import GoalsView from './workbench/goals.vue'
import { MUSE_NAV_KEY } from './muse-nav'
import type { MuseNavContext } from './muse-nav'

const route = useRoute()
const router = useRouter()

const VIEWS = ['chat', 'feed', 'ideas', 'goals'] as const
const view = computed(() => {
  const v = String(route.query.view || 'chat')
  return VIEWS.includes(v as any) ? v : 'chat'
})
const params = ref<Record<string, any>>({})

function switchView(next: string, nextParams: Record<string, any> = {}) {
  params.value = nextParams
  if (next !== view.value) router.push({ path: '/super-agent/muse', query: { view: next } })
}

provide<MuseNavContext>(MUSE_NAV_KEY, { view, params, switchView })
</script>

<template>
  <div class="sa-muse">
    <ChatView v-show="view === 'chat'" />
    <FeedView v-show="view === 'feed'" />
    <IdeasView v-show="view === 'ideas'" />
    <GoalsView v-show="view === 'goals'" />
  </div>
</template>

<style scoped lang="less">
.sa-muse {
  height: 100%;
  min-height: 0;

  > * {
    height: 100%;
  }
}
</style>
