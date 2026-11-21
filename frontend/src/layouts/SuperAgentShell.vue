<script setup lang="ts">
// SuperAgent 独立全屏外壳：顶栏 + 左侧分组导航 + 主区 router-view。
// 1:1 复刻 docs/prototypes/super-agent-demo/super-agent-demo.html 的 SPA 结构，
// 不再叠加后台 AppLayout 的侧栏与顶栏。
// SSE（events / feed）在此统一订阅，避免子视图 v-show 切换时重复连接。
import { onMounted, onUnmounted } from 'vue'
import { theme as antdTheme } from 'ant-design-vue'
import SaTopbar from '@/components/super-agent/SaTopbar.vue'
import SaSideNav from '@/components/super-agent/SaSideNav.vue'
import { useSuperAgentStore } from '@/stores/super-agent'
import '@/styles/super-agent-tokens.css'

const store = useSuperAgentStore()

// 局部主题：强制暗色算法，颜色走 super-agent-tokens.css 的 --ant-* 覆盖。
const saTheme = {
  algorithm: [antdTheme.darkAlgorithm, antdTheme.compactAlgorithm],
  cssVar: true,
  hashed: false,
}

onMounted(() => {
  store.connectEvents()
  store.connectFeed()
})

onUnmounted(() => {
  store.disconnectEvents()
  store.disconnectFeed()
})
</script>

<template>
  <a-config-provider :theme="saTheme">
    <div class="super-agent-shell">
      <SaTopbar />
      <div class="sa-body">
        <SaSideNav />
        <main class="sa-main">
          <router-view v-slot="{ Component }">
            <component :is="Component" />
          </router-view>
        </main>
      </div>
    </div>
  </a-config-provider>
</template>

<style scoped lang="less">
.sa-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.sa-main {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow: auto;
  padding: 20px;
  background: var(--sa-bg);
}
</style>
