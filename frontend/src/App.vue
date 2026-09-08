<script setup lang="ts">
// 应用根节点。
//
// 职责：
//   * 提供跟随深色 / 浅色皮肤的 Ant Design 主题（算法 + 组件令牌）
//   * 提供对应的 Ant Design 语言包（分页、空状态、日期选择等内置文案）
//   * 同步 <html data-theme>，使 CSS 变量整体切换皮肤
import { computed, onMounted, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { theme as antdTheme } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import zhTW from 'ant-design-vue/es/locale/zh_TW'
import enUS from 'ant-design-vue/es/locale/en_US'
import jaJP from 'ant-design-vue/es/locale/ja_JP'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import ElectronServerButton from '@/layouts/components/ElectronServerButton.vue'
import type { LocaleKey } from '@/i18n'

const app = useAppStore()
const user = useUserStore()
const route = useRoute()

/** 登录页没有顶栏，桌面端退化成悬浮入口，保证后端地址不通时仍能修改。 */
const showFloatingServerEntry = computed(() => route.name === 'Login')

/** Ant Design 语言包，按项目自身的语言代码索引。 */
const ANTD_LOCALES: Record<LocaleKey, unknown> = {
  'zh-CN': zhCN,
  'zh-TW': zhTW,
  'en-US': enUS,
  'ja-JP': jaJP,
}

const antdLocale = computed(() => ANTD_LOCALES[app.locale] ?? zhCN)

/**
 * 组件令牌覆盖。颜色全部取自 CSS 变量，切换皮肤只需改一个属性；
 * 这里只设置结构性令牌（圆角、控件高度、字体）。
 */
const componentTokens = computed(() => ({
  // 大圆角 + 略高的控件，匹配 explorer 的毛玻璃质感
  borderRadius: 14,
  borderRadiusLG: 20,
  borderRadiusSM: 10,
  fontSize: 14,
  controlHeight: 36,
  // 让表面採用我们的调色板，而不是 AntD 固定的白 / 灰
  colorBgContainer: 'var(--bg-surface)',
  colorBgElevated: 'var(--bg-elevated)',
  colorBorder: 'var(--border)',
  colorBorderSecondary: 'var(--border)',
  colorPrimary: 'var(--accent)',
  colorPrimaryHover: 'var(--accent-hover)',
  colorText: 'var(--fg)',
  colorTextSecondary: 'var(--fg-secondary)',
  fontFamily: "'IBM Plex Sans', 'Space Grotesk', 'HarmonyOS Sans SC', system-ui, sans-serif",
}))

const algorithm = computed(() =>
  app.isDark ? [antdTheme.darkAlgorithm, antdTheme.compactAlgorithm] : [antdTheme.defaultAlgorithm],
)

// 把皮肤写到 <html>，tokens.css 据此选择调色板
watchEffect(() => {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', app.theme)
  document.documentElement.style.colorScheme = app.theme
})

onMounted(() => {
  if (user.token) {
    void user.fetchUserInfo().catch(() => {})
  }
})
</script>

<template>
  <a-config-provider
    :locale="antdLocale"
    :theme="{ algorithm, token: componentTokens, cssVar: true, hashed: false }"
  >
    <a-app class="app-root">
      <router-view />
      <ElectronServerButton v-if="showFloatingServerEntry" floating />
    </a-app>
  </a-config-provider>
</template>

<style>
.app-root {
  height: 100%;
}
</style>
