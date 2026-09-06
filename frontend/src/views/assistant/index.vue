<template>
  <div class="ai-assistant-page">
    <!-- 顶部导航栏 -->
    <div class="ai-page-header">
      <div class="header-logo">
        <div class="logo-icon">
          <img src="/brand/logo-icon.svg" width="26" height="26" alt="" />
        </div>
        <h1 class="logo-text">智能调解</h1>
      </div>
      
    </div>

    <!-- 主体：直接嵌入 AssistantPanel -->
    <div class="ai-page-body">
      <AssistantPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import AssistantPanel from '@/views/assistant/components/AssistantPanel.vue'

const currentDate    = ref('')
const currentTime    = ref('')
const currentWeekday = ref('')
const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
let timeInterval: number

function updateTime() {
  const now = new Date()
  currentDate.value    = `${now.getFullYear()}年${String(now.getMonth() + 1).padStart(2, '0')}月${String(now.getDate()).padStart(2, '0')}日`
  currentTime.value    = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  currentWeekday.value = WEEKDAYS[now.getDay()]
}

onMounted(() => { updateTime(); timeInterval = window.setInterval(updateTime, 1000) })
onUnmounted(() => clearInterval(timeInterval))
</script>

<style lang="less" scoped>
// 顶层路由 /ai-assistant 不在 AppLayout 内，#app 通过 overflow:hidden 锁住。
// 这里让整个页面的滚动落在 .ai-page-body 上，保证长内容（消息、分页、会话列表）能滚动展示。
.ai-assistant-page {
  width: 100%;
  height: 100%;
  background: var(--bg-base);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ai-page-header {
  height: 54px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}

.header-logo { display: flex; align-items: center; gap: 10px; }
.logo-text { font-size: 18px; font-weight: 700; color: var(--fg); margin: 0; }

.header-right { display: flex; align-items: center; }
.header-time { font-size: 13px; color: var(--fg-secondary); font-variant-numeric: tabular-nums; }

.ai-page-body {
  flex: 1;
  min-height: 0;
  // 让嵌入的 AssistantPanel 在视口高度内自适应，超出部分由内部滚动，
  // 避免输入栏被推出可视区域。
  display: flex;
  overflow: hidden;
  padding: 12px;
  box-sizing: border-box;
}
</style>
