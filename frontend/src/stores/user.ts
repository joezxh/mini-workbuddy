import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getToken, setToken, removeToken, setTenantId, removeTenantId } from '@/utils/auth'
import { getUserInfo, login as loginApi, logout as logoutApi, changePassword as changePasswordApi } from '@/api/auth'
import { batchGetDictItems, saveDictToStorage, clearDictStorage } from '@/api/common'
import type { UserInfo } from '@/types/user'

const BATCH_DICT_CODES = [
  'disposal_status',
  'person_type',
  'person_manage_status',
  'event_type',
  'risk_level'
]

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(getToken() || '')
  const userInfo = ref<UserInfo | null>(null)
  const regions = ref<any[]>([])
  const permissions = ref<string[]>([])
  const roles = ref<string[]>([])

  /**
   * 登录
   */
  async function login(username: string, password: string, tenantId?: number) {
    try {
      const res = await loginApi({ username, password, tenant_id: tenantId }) as {
        token?: string
        access_token?: string
        token_type?: string
        tenantId?: number
        [key: string]: unknown
      }
      // 兼容两种后端返回：{ token: "..." } 或 OAuth2 风格 { access_token: "...", token_type: "bearer" }
      const accessToken = res?.token ?? res?.access_token
      if (!accessToken || typeof accessToken !== 'string') {
        throw new Error('登录成功但未返回有效 token，请检查后端接口')
      }
      token.value = accessToken
      setToken(accessToken)
      // 存储租户 ID
      const resTenantId = res?.tenantId as number | undefined
      if (resTenantId) {
        setTenantId(resTenantId)
      }
      await fetchUserInfo()
      // 登录成功后批量拉取字典并写入 localStorage
      try {
        const dictData = await batchGetDictItems(BATCH_DICT_CODES)
        if (dictData) saveDictToStorage(dictData)
      } catch (e) {
        console.warn('批量字典加载失败，不影响登录:', e)
      }
      return res
    } catch (error) {
      throw error
    }
  }

  /**
   * 获取用户信息
   */
  async function fetchUserInfo() {
    try {
      const res = await getUserInfo()
      // 后端直接返回用户信息对象，不是包装在 data 中
      userInfo.value = res as any
      permissions.value = (res as any).permissions || []
      roles.value = (res as any).roles || []
      return res
    } catch (error) {
      throw error
    }
  }

  /**
   * 登出
   */
  async function logout() {
    try {
      await logoutApi()
    } catch (error) {
      console.error('登出失败:', error)
    } finally {
      token.value = ''
      userInfo.value = null
      removeToken()
      removeTenantId()
      clearDictStorage()
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    token.value = ''
    userInfo.value = null
    regions.value = []
    permissions.value = []
    roles.value = []
    removeToken()
    removeTenantId()
  }

  /**
   * 修改密码
   */
  async function changePassword(data: { old_password: string; new_password: string }) {
    await changePasswordApi(data)
  }

  return {
    token,
    userInfo,
    regions,
    permissions,
    roles,
    login,
    logout,
    fetchUserInfo,
    reset,
    changePassword,
  }
})

