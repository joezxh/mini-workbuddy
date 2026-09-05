const TOKEN_KEY = 'miniworkbuddy_token'
const LEGACY_TOKEN_KEY = 'risk_control_token'
const TENANT_ID_KEY = 'tenant_id'
const COOKIE_MAX_AGE = 30 * 24 * 3600 // 30 天（秒）

/**
 * 获取 Token（兼容旧 key 自动迁移）
 */
export function getToken(): string | null {
  const t = localStorage.getItem(TOKEN_KEY)
  if (t && t !== 'undefined') return t
  // fallback: 读旧 key 并自动迁移到新 key
  const legacy = localStorage.getItem(LEGACY_TOKEN_KEY)
  if (legacy && legacy !== 'undefined') {
    localStorage.setItem(TOKEN_KEY, legacy)
    localStorage.removeItem(LEGACY_TOKEN_KEY)
    return legacy
  }
  return null
}

/**
 * 设置 Token
 */
export function setToken(token: string): void {
  if (token && typeof token === 'string' && token !== 'undefined') {
    localStorage.setItem(TOKEN_KEY, token)
  }
}

/**
 * 移除 Token（同时清除新旧 key）
 */
export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
}

/**
 * 检查是否已登录
 */
export function isAuthenticated(): boolean {
  return !!getToken()
}

/**
 * 从 Cookie 读取指定值
 */
function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp('(?:^|;\\s*)' + name.replace(/[.*+\-?^${}()|[\]\\]/g, '\\$&') + '=([^;]*)')
  )
  return match ? decodeURIComponent(match[1]) : null
}

/**
 * 设置 Cookie
 */
function setCookie(name: string, value: string, maxAge: number = COOKIE_MAX_AGE): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; SameSite=Lax`
}

/**
 * 删除 Cookie
 */
function removeCookie(name: string): void {
  document.cookie = `${name}=; path=/; max-age=0`
}

/**
 * 获取租户 ID（从 Cookie 读取，支持跨域/SSO 场景）
 */
export function getTenantId(): number | null {
  const val = getCookie(TENANT_ID_KEY)
  return val ? Number(val) : null
}

/**
 * 设置租户 ID（写入 Cookie，max-age=30天）
 */
export function setTenantId(tenantId: number): void {
  setCookie(TENANT_ID_KEY, String(tenantId))
}

/**
 * 移除租户 ID
 */
export function removeTenantId(): void {
  removeCookie(TENANT_ID_KEY)
}
