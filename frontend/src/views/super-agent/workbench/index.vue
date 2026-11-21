<script setup lang="ts">
// 工作台模块容器：Dashboard 看板 / 电商营销 Demo / 执行详情。
// 三个视图走真实嵌套子路由（各页保留独立 SSE / 刷新逻辑），由 SaSideNav 切换。
</script>

<template>
  <div class="sa-workbench">
    <router-view />
  </div>
</template>

<style scoped lang="less">
.sa-workbench {
  height: 100%;
  min-height: 0;
}
</style>
