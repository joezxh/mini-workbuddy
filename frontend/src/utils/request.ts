import axios, { AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'
import { getToken, removeToken } from './auth'
import router from '@/router'

// 创建 axios 实例
// 开发环境使用空 baseURL，所有 /api 请求走 Vite proxy 代理，避免 CORS 问题
// 生产环境通过 VITE_API_BASE_URL 配置实际后端地址
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json;charset=utf-8'
  }
})

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken()
    if (token && token !== 'undefined' && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
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
      
      switch (status) {
        case 401:
          message.error('登录已过期，请重新登录')
          removeToken()
          router.push('/login')
          break
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
          const respData = (error.response?.data || {}) as Record<string, any>
          const detail = respData.detail || respData.message || respData.msg
          const text = typeof detail === 'string'
            ? detail
            : (detail && detail.msg) || error.message || '请求失败'
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
  }
}

export default request

