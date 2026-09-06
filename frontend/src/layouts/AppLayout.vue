<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
import AppHeader from './components/AppHeader.vue'
</script>

<template>
  <a-layout class="workspace">
    <AppSidebar />

    <a-layout class="workspace-main">
      <AppHeader />

      <a-layout-content class="workspace-content hud-grid">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped>
.workspace {
  display: flex !important;
  flex-direction: row !important;
  height: 100dvh;
  background: transparent;
}

.workspace-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100dvh;
  overflow: hidden;
  background: transparent;
}

.workspace-content {
  flex: 1;
  min-height: 0;
  /* 存量页面大多自带滚动容器，这里保留可滚动回退，避免出现无法滚动的死角 */
  overflow: auto;
}

/* 使用了 .app-page / .page 原语的页面自行撑满并滚动 */
.workspace-content :deep(.app-page),
.workspace-content :deep(.page) {
  height: 100%;
}
</style>
