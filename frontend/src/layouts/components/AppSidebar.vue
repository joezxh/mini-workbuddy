<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { useMenuStore } from '@/stores/menu'
import type { MenuNode } from '@/types/menu'
import SidebarItem from './SidebarItem.vue'
import AppLogo from './AppLogo.vue'

const router = useRouter()
const { t } = useI18n()
const app = useAppStore()
const user = useUserStore()
const menuStore = useMenuStore()
const { sidebarCollapsed: collapsed } = storeToRefs(app)

// 菜单完全来自后端权限数据，缓存在 menu store（由 /me 一并返回，避免重复请求）
const menus = computed<MenuNode[]>(() => menuStore.menus)
// 已登录但菜单尚未加载完成（fetchUserInfo 进行中）时显示加载态
const loading = computed(() => !!user.userInfo && !menuStore.loaded)

function toggle() {
  app.toggleSidebar()
}
function onSelect(path: string) {
  if (!path) return
  // 在控制台（/admin）中以 Tab 形式打开对应页面；菜单导航统一由左侧 rail 承担，不再重复菜单层
  const m = path.match(/^\/admin\/([^/]+)/)
  if (m) {
    router.push({ path: '/admin', query: { tab: m[1] } })
  } else {
    router.push(path)
  }
}
</script>

<template>
  <aside class="rail" :class="{ 'rail--collapsed': collapsed }">
    <div class="rail-brand" @click="router.push('/dashboard')">
      <AppLogo :size="26" class="rail-brand__logo" />
      <div class="rail-brand__text">
        <span class="rail-brand__kicker">{{ t('sys.brandKicker') }}</span>
        <span class="rail-brand__name">{{ t('sys.brand') }}</span>
      </div>
    </div>

    <nav class="rail-nav">
      <template v-if="loading">
        <div class="rail-loading">…</div>
      </template>
      <template v-else>
        <template v-if="menus.length">
          <SidebarItem
            v-for="m in menus"
            :key="m.id"
            :node="m"
            :collapsed="collapsed"
            @select="onSelect"
          />
        </template>
        <div v-else class="rail-empty">暂无可用菜单</div>
      </template>
    </nav>

    <button class="rail-collapse" @click="toggle">
      {{ collapsed ? '»' : '«' }}
    </button>
  </aside>
</template>

<style scoped>
.rail {
  width: 220px;
  height: 100%;
  background: var(--rail-bg);
  color: var(--rail-fg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s, background-color var(--transition), color var(--transition);
}
.rail--collapsed {
  width: 64px;
}
.rail--collapsed .rail-brand__text {
  display: none;
}
.rail--collapsed .rail-brand {
  justify-content: center;
  padding: 0;
}
.rail-brand {
  /* 与右侧主窗体顶部标题栏（--header-h）等高，保证左右顶部齐平 */
  height: var(--header-h);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  font-weight: 600;
  cursor: pointer;
  border-bottom: 1px solid var(--rail-border);
}
.rail-brand__logo {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
}
.rail-brand__name {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.2px;
  color: var(--fg);
  margin: 2px 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rail-brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
  min-width: 0;
}

.rail-brand__kicker {
  font-family: var(--font-tech);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--accent);
  white-space: nowrap;
}
.rail-nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 0;
}
.rail-loading {
  padding: 16px;
  color: var(--rail-fg-muted);
  text-align: center;
}
.rail-empty {
  padding: 24px 16px;
  color: var(--rail-fg-muted);
  font-size: 13px;
  text-align: center;
}
.rail-collapse {
  height: 44px;
  border: none;
  background: transparent;
  color: var(--rail-fg-muted);
  cursor: pointer;
  border-top: 1px solid var(--rail-border);
  transition: color var(--transition);
}
.rail-collapse:hover {
  color: var(--rail-fg);
}

</style>
