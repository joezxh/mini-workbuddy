<script setup lang="ts">
// 登录页。
//
// 直接复用 rcs Console 的登录页实现：全屏视口、光晕背景 + 双栏玻璃卡片，
// 登录成功后跳转到目标路由（或默认首页）。
//
// 与 rcs 的差异仅在于数据层：
//   * 会话来自 @/stores/user 的 useUserStore（MinWorkBuddy 的鉴权 store）
//   * 额外保留“租户选择”这一业务必选项
//   * 路由为静态注册，因此没有 registerDynamicRoutes
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BankOutlined, GlobalOutlined, LockOutlined, UserOutlined } from '@ant-design/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { LOCALE_LABELS, SUPPORTED_LOCALES } from '@/i18n'
import { useI18n } from 'vue-i18n'
import { getTenantSimpleList } from '@/api/auth'
import type { LocaleKey } from '@/i18n'

interface TenantOption {
  tenantId: number
  name: string
}

const { t } = useI18n()
const user = useUserStore()
const app = useAppStore()
const route = useRoute()
const router = useRouter()

const form = reactive<{ username: string; password: string; tenantId?: number }>({
  username: '',
  password: '',
  tenantId: undefined,
})
const submitting = ref(false)
const errorMessage = ref('')

const tenantList = ref<TenantOption[]>([])
const tenantOptions = computed(() =>
  tenantList.value.map((item) => ({ value: item.tenantId, label: item.name })),
)

onMounted(() => {
  // 已登录时进入登录页，说明在其他地方退出过，这里清理本地会话
  if (user.token) user.reset()
  void loadTenantList()
})

/** 加载租户列表；优先选中 id=0 的系统租户（MiniWorkBuddy） */
async function loadTenantList() {
  try {
    const res = (await getTenantSimpleList()) as any
    const data = res?.data ?? res ?? []
    tenantList.value = Array.isArray(data)
      ? data.map((item: any) => ({
          tenantId: item.tenantId ?? item.tenant_id,
          name: item.name,
        }))
      : []
    // 优先选中系统租户（id=0）；只有一个租户时也自动选中
    const systemTenant = tenantList.value.find((t) => t.tenantId === 0)
    if (systemTenant) {
      form.tenantId = systemTenant.tenantId
    } else if (tenantList.value.length === 1) {
      form.tenantId = tenantList.value[0].tenantId
    }
  } catch (err) {
    // 租户列表不可用时仍允许登录（后端可不启用多租户）；
    // 但把错误打到控制台，便于排查"租户下拉不显示"的问题
    console.error('[login] 加载租户列表失败:', err)
  }
}

async function onSubmit() {
  if (submitting.value) return
  errorMessage.value = ''
  submitting.value = true
  try {
    await user.login(form.username.trim(), form.password, form.tenantId)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : null
    await router.replace(redirect ?? '/dashboard')
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
  } finally {
    submitting.value = false
  }
}

function onLocale({ key }: { key: string }) {
  app.setAppLocale(key as LocaleKey)
}
</script>

<template>
  <div class="login-page">
    <div class="glow glow-a" aria-hidden="true" />
    <div class="glow glow-b" aria-hidden="true" />

    <div class="lang-switch">
      <a-dropdown>
        <button class="lang-btn" type="button">
          <GlobalOutlined />
          {{ LOCALE_LABELS[app.locale] }}
        </button>
        <template #overlay>
          <a-menu :selected-keys="[app.locale]" @click="onLocale">
            <a-menu-item v-for="loc in SUPPORTED_LOCALES" :key="loc">{{ LOCALE_LABELS[loc] }}</a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>

    <div class="login-shell">
      <!-- Hero side -->
      <aside class="login-hero">
        <span class="kicker">{{ t('sys.login.kicker') }}</span>
        <h1 class="hero-title">{{ t('sys.login.title') }}</h1>
        <p class="hero-sub">{{ t('sys.login.subtitle') }}</p>

        <ul class="hero-points">
          <li><span class="tick">◇</span> {{ t('sys.login.f1') }}</li>
          <li><span class="tick">◇</span> {{ t('sys.login.f2') }}</li>
          <li><span class="tick">◇</span> {{ t('sys.login.f3') }}</li>
        </ul>
      </aside>

      <!-- Form side -->
      <div class="panel">
        <div class="brand-row">
          <span class="brand-mark">M</span>
          <div>
            <h2 class="panel-title">{{ t('sys.login.signin') }}</h2>
            <p class="panel-sub">{{ t('sys.login.subtitle') }}</p>
          </div>
        </div>

        <a-form layout="vertical" @submit.prevent="onSubmit">
          <a-form-item v-if="tenantList.length > 0" :label="t('sys.login.tenant')">
            <a-select
              v-model:value="form.tenantId"
              size="large"
              :options="tenantOptions"
              :placeholder="t('sys.login.tenantPlaceholder')"
            >
              <template #prefix><BankOutlined /></template>
            </a-select>
          </a-form-item>

          <a-form-item>
            <a-input
              v-model:value="form.username"
              size="large"
              :placeholder="t('sys.login.username')"
              autocomplete="username"
            >
              <template #prefix><UserOutlined /></template>
            </a-input>
          </a-form-item>

          <a-form-item>
            <a-input-password
              v-model:value="form.password"
              size="large"
              :placeholder="t('sys.login.password')"
              autocomplete="current-password"
              @press-enter="onSubmit"
            >
              <template #prefix><LockOutlined /></template>
            </a-input-password>
          </a-form-item>

          <a-alert v-if="errorMessage" class="alert" type="error" show-icon :message="errorMessage" />

          <a-button
            type="primary"
            size="large"
            block
            html-type="submit"
            :loading="submitting"
            @click="onSubmit"
          >
            {{ submitting ? t('sys.login.submitting') : t('sys.login.submit') }}
          </a-button>
        </a-form>

        <p class="hint">{{ t('sys.login.demoHint') }}</p>
      </div>
    </div>

    <footer class="footer">MiniWorkBuddy · {{ t('sys.brand') }}</footer>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100%;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--bg-base);
  overflow: hidden;
}

.glow {
  position: absolute;
  width: 560px;
  height: 560px;
  border-radius: 50%;
  filter: blur(110px);
  opacity: 0.32;
  pointer-events: none;
}

.glow-a {
  background: var(--accent);
  top: -200px;
  left: -160px;
}

.glow-b {
  background: var(--accent-2);
  bottom: -240px;
  right: -180px;
}

.lang-switch {
  position: absolute;
  top: 20px;
  right: 24px;
  z-index: 3;
}

.lang-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-surface);
  color: var(--fg-secondary);
  cursor: pointer;
  font-size: 13px;
}

.lang-btn:hover {
  color: var(--accent);
  border-color: var(--border-strong);
}

/* 双栏布局：左侧 hero + 右侧玻璃卡片 */
.login-shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  align-items: center;
  gap: 40px;
  width: min(960px, 94vw);
  padding: 28px;
}

.login-hero {
  padding: 12px 8px;
}

.kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-tech);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
}

.kicker::before {
  content: '';
  width: 22px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.hero-title {
  margin: 14px 0 10px;
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 700;
  line-height: 1.08;
  letter-spacing: -0.02em;
  color: var(--fg);
}

.hero-sub {
  margin: 0;
  max-width: 420px;
  font-size: 15px;
  color: var(--fg-secondary);
}

.hero-points {
  list-style: none;
  margin: 26px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hero-points li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--fg-secondary);
}

.tick {
  color: var(--accent);
}

.panel {
  position: relative;
  z-index: 1;
  width: 100%;
  padding: 32px;
  border-radius: var(--radius-xl);
  background: var(--bg-surface);
  -webkit-backdrop-filter: var(--glass);
  backdrop-filter: var(--glass);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  border-radius: var(--radius);
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 22px;
  color: var(--fg-inverse);
  background: linear-gradient(135deg, var(--accent), var(--accent-hover));
  box-shadow: var(--shadow-sm);
}

:root[data-theme='light'] .brand-mark {
  color: #fff;
}

.panel-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  color: var(--fg);
}

.panel-sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--fg-secondary);
}

.alert {
  margin-bottom: 14px;
}

.hint {
  margin: 18px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--fg-muted);
}

.footer {
  position: absolute;
  bottom: 20px;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--fg-muted);
}

@media (max-width: 820px) {
  .login-shell {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .login-hero {
    display: none;
  }
}
</style>
