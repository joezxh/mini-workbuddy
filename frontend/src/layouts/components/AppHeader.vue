<script setup lang="ts">
// 顶栏：侧栏开关、品牌标题、快捷导航、语言 / 皮肤 / 全屏开关与用户菜单。
//
// 外观与交互沿用 rcs Console 的 topbar：底部一条渐变“总线”高亮线、脉冲状态点、
// 等宽时钟、胶囊形用户芯片。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  BulbFilled,
  BulbOutlined,
  DownOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  GlobalOutlined,
  IdcardOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import ElectronServerButton from './ElectronServerButton.vue'
import { LOCALE_LABELS, SUPPORTED_LOCALES } from '@/i18n'
import { useI18n } from 'vue-i18n'
import { resolveIcon } from '@/utils/icons'
import type { LocaleKey } from '@/i18n'

const { t } = useI18n()
const user = useUserStore()
const app = useAppStore()
const router = useRouter()

const currentTime = ref('')
let timer: number | undefined

function tick() {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  currentTime.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

onMounted(() => {
  tick()
  timer = window.setInterval(tick, 1000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

const isFullscreen = ref(false)

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().then(() => (isFullscreen.value = true)).catch(() => {})
  } else {
    document.exitFullscreen().then(() => (isFullscreen.value = false)).catch(() => {})
  }
}

const initial = computed(() => user.userInfo?.realName?.charAt(0)?.toUpperCase() ?? 'U')

/** 快捷导航：直达各业务首页，图标与侧栏保持一致。 */
const QUICK_NAV = [
  { path: '/dashboard', icon: 'DashboardOutlined', titleKey: 'sys.menu.dashboard' },
  { path: '/ai-assistant', icon: 'MessageOutlined', titleKey: 'sys.menu.assistant' },
  { path: '/wiki', icon: 'BookOutlined', titleKey: 'sys.menu.wiki' },
  { path: '/admin', icon: 'SettingOutlined', titleKey: 'sys.menu.admin' },
]

function onUserMenu({ key }: { key: string | number }) {
  if (key === 'profile') router.push('/admin?tab=profile')
  if (key === 'logout') void onLogout()
}

async function onLogout() {
  await user.logout()
  router.push({ name: 'Login' })
}

function onLocale({ key }: { key: string }) {
  app.setAppLocale(key as LocaleKey)
}

function onQuickNav({ key }: { key: string | number }) {
  const path = String(key)
  if (path && path !== 'undefined') router.push(path)
}
</script>

<template>
  <header class="topbar">
    <button class="icon-btn" type="button" @click="app.toggleSidebar()">
      <MenuUnfoldOutlined v-if="app.sidebarCollapsed" />
      <MenuFoldOutlined v-else />
    </button>

    <!-- 移动端品牌标识：仅在小屏幕显示 -->
    <span class="topbar-brand-mobile">
      <img src="/brand/logo-icon.svg" width="22" height="22" alt="" aria-hidden="true" />
    </span>

    <a-dropdown>
      <button class="portal-btn" type="button">
        <GlobalOutlined />
        <span>{{ t('sys.header.quickNav') }}</span>
        <DownOutlined class="caret" />
      </button>
      <template #overlay>
        <a-menu @click="onQuickNav">
          <a-menu-item v-for="m in QUICK_NAV" :key="m.path">
            <component :is="resolveIcon(m.icon)" />
            {{ t(m.titleKey) }}
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>

    <div class="spacer" />

    <span class="live-dot" aria-hidden="true" />
    <span class="clock mono">{{ currentTime }}</span>

    <a-dropdown>
      <button class="icon-btn" type="button" :title="t('sys.header.language')">
        <GlobalOutlined />
      </button>
      <template #overlay>
        <a-menu :selected-keys="[app.locale]" @click="onLocale">
          <a-menu-item v-for="loc in SUPPORTED_LOCALES" :key="loc">
            {{ LOCALE_LABELS[loc] }}
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>

    <button class="icon-btn" type="button" :title="t('sys.header.theme')" @click="app.toggleTheme()">
      <BulbFilled v-if="app.isDark" />
      <BulbOutlined v-else />
    </button>

    <!-- 桌面端：可运行时切换后端地址；浏览器部署下该组件不渲染 -->
    <ElectronServerButton />

    <button class="icon-btn" type="button" :title="t('sys.header.fullscreen')" @click="toggleFullscreen">
      <FullscreenExitOutlined v-if="isFullscreen" />
      <FullscreenOutlined v-else />
    </button>

    <a-dropdown placement="bottomRight">
      <div class="user-chip">
        <a-avatar :size="30" class="avatar">{{ initial }}</a-avatar>
        <span class="user-name">{{ user.userInfo?.realName ?? '-' }}</span>
        <DownOutlined class="caret" />
      </div>
      <template #overlay>
        <a-menu @click="onUserMenu">
          <a-menu-item key="profile">
            <IdcardOutlined />
            {{ t('sys.header.profile') }}
          </a-menu-item>
          <a-menu-divider />
          <a-menu-item key="logout">
            <LogoutOutlined />
            {{ t('sys.header.logout') }}
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>
  </header>
</template>

<style scoped>
.topbar {
  position: relative;
  height: var(--header-h);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  background: var(--topbar-bg);
  -webkit-backdrop-filter: var(--glass);
  backdrop-filter: var(--glass);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

/* 底部渐变“系统总线”高亮线，替代普通的 1px 分割线。 */
.topbar::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0.55;
  pointer-events: none;
}

.topbar-title {
  display: flex;
  flex-direction: column;
  line-height: 1;
}

.kicker {
  font-family: var(--font-tech);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--accent);
}

.title {
  margin: 3px 0 0;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.2px;
  color: var(--fg);
  white-space: nowrap;
}

.spacer {
  flex: 1;
}

.clock {
  font-size: 12px;
  color: var(--fg-secondary);
  white-space: nowrap;
}

/* 与时钟并排的脉冲状态点，表示会话在线。 */
.live-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: var(--ok);
  box-shadow: var(--glow-ok);
  animation: live-pulse 2s ease-in-out infinite;
}

@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.82);
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-dot {
    animation: none;
  }
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--fg-secondary);
  cursor: pointer;
  font-size: 15px;
  transition: all var(--transition);
}

.icon-btn:hover {
  color: var(--accent);
  border-color: var(--border-strong);
  background: var(--bg-hover);
}

.portal-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--fg-secondary);
  cursor: pointer;
  font-size: 13px;
  transition: all var(--transition);
}

.portal-btn:hover {
  color: var(--accent);
  border-color: var(--border-strong);
  background: var(--bg-hover);
}

.caret {
  font-size: 10px;
  opacity: 0.7;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition);
}

.user-chip:hover {
  background: var(--bg-hover);
  border-color: var(--border-strong);
}

.avatar {
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: var(--fg-inverse) !important;
  font-weight: 700;
  flex-shrink: 0;
}

.user-name {
  font-size: 13px;
  color: var(--fg);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .live-dot,
  .clock,
  .topbar-title {
    display: none;
  }
}

/* 移动端品牌标识：默认隐藏，小屏幕显示 */
.topbar-brand-mobile {
  display: none;
  align-items: center;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .topbar-brand-mobile {
    display: flex;
  }

  .portal-btn span {
    display: none;
  }

  .portal-btn .caret {
    display: none;
  }

  .user-name {
    display: none;
  }

  .topbar {
    gap: 8px;
    padding: 0 12px;
  }
}

</style>
