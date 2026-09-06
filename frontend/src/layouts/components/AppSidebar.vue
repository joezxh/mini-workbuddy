<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { useMenuStore } from '@/stores/menu'
import type { MenuNode } from '@/types/menu'
import SidebarItem from './SidebarItem.vue'
import AppLogo from './AppLogo.vue'

const router = useRouter()
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
    <div class="rail-brand" @click="router.push('/admin?tab=dashboard')">
      <img v-if="!collapsed" src="/brand/logo-full.svg" style="width: 100%; height: 100%; object-fit: contain; display: block;" alt="MiniWorkBuddy" />
      <img v-else src="/brand/logo-icon.svg" class="rail-brand__icon" alt="MiniWorkBuddy" />
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

    <button class="rail-collapse" :title="collapsed ? '展开侧栏' : '收起侧栏'" @click="toggle">
      <span class="rail-collapse__icon">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path
            :d="collapsed
              ? 'M6 3l5 5-5 5'
              : 'M10 3L5 8l5 5'"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </button>
  </aside>
</template>

<style scoped>
.rail {
  width: 220px;
  min-width: 64px;
  height: 100%;
  background: var(--rail-bg);
  color: var(--rail-fg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  transition: width 0.2s, background-color var(--transition), color var(--transition);
}
.rail--collapsed {
  width: 64px;
}
.rail--collapsed .rail-brand {
  justify-content: center;
  padding: 0;
}
.rail-brand {
  height: var(--header-h);
  display: flex;
  align-items: stretch;
  font-weight: 600;
  cursor: pointer;
  border-bottom: 1px solid var(--rail-border);
}
.rail-brand__logo {
  width: 100%;
  height: 100%;
  flex-shrink: 0;
}
.rail-brand__icon {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
}
.rail-nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
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
  transition: color var(--transition), background-color var(--transition);
  display: flex;
  align-items: center;
  justify-content: center;
}
.rail-collapse:hover {
  color: var(--accent);
  background: var(--rail-hover);
}
.rail-collapse__icon {
  display: grid;
  place-items: center;
  transition: transform var(--transition);
}
.rail-collapse:hover .rail-collapse__icon {
  transform: scale(1.1);
}

</style>
