import axios, { AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'
import { getToken, removeToken } from './auth'
import router from '@/router'
import { getApiBase, onApiBaseChange } from './apiBase'
import { resolveApiError } from './apiErrorCodes'

// 创建 axios 实例
// 开发环境使用空 baseURL，所有 /api 请求走 Vite proxy 代理，避免 CORS 问题
// 生产环境通过 VITE_API_BASE_URL 配置实际后端地址
// 桌面端 VITE_API_BASE_URL 为空，实际地址在 initApiBase() 后由 onApiBaseChange 写入
const service = axios.create({
  baseURL: getApiBase(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json;charset=utf-8'
  }
})

// 暴露实例本身，便于在外部调整默认配置
export const http = service

// 桌面端允许运行时修改后端地址，这里保持 axios 与 apiBase 同步
onApiBaseChange((base) => {
  service.defaults.baseURL = base
})

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken()
    if (token && token !== 'undefined' && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    // FormData 上传：删除默认的 JSON Content-Type，让浏览器自动补上
    // multipart/form-data; boundary=…，否则 FastAPI 收不到 file 字段（422）
    if (config.data instanceof FormData && config.headers) {
      delete config.headers['Content-Type']
    }
    return config
  },
  (error: AxiosError) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // 直接返回 response.data，这样 request 方法就能正确获取数据
    return response.data
  },
  (error: AxiosError) => {
    console.error('响应错误:', error)

    if (error.response) {
      const status = error.response.status

      // 401 认证失效优先处理（即便响应体带 code 也要跳转登录）
      if (status === 401) {
        message.error('登录已过期，请重新登录')
        removeToken()
        router.push('/login')
        return Promise.reject(error)
      }

      // R3 错误契约：本体端点返回 {code,message,detail?}，优先按 code 映射文案，
      // 覆盖 404/409/500/503 等通用分支；既有 47 端点无 code，走下方回落逻辑。
      const data = error.response.data as Record<string, any>
      if (data && typeof data.code === 'string') {
        const codeText = resolveApiError(data)
        if (codeText) {
          message.error(codeText)
          return Promise.reject(error)
        }
      }

      switch (status) {
        case 403:
          message.error('没有权限访问该资源')
          break
        case 404:
          message.error('请求的资源不存在')
          break
        case 500:
          message.error('服务器错误')
          break
        default: {
          // 优先展示后端返回的详细错误信息（detail / message）
          const text = resolveApiError(data) || error.message || '请求失败'
          message.error(text)
        }
      }
    } else {
      message.error('网络连接失败')
    }

    return Promise.reject(error)
  }
)

// 封装常用请求方法
// 说明：响应拦截器已直接返回 response.data，故此处断言为 Promise<T>，
// 与拦截器"解包 data"的行为保持一致，避免 axios 泛型推断冲突。
const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.get(url, config) as Promise<T>
  },

  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.post(url, data, config) as Promise<T>
  },

  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.put(url, data, config) as Promise<T>
  },

  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.delete(url, config) as Promise<T>
  },

  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.patch(url, data, config) as Promise<T>
  }
}

export default request

