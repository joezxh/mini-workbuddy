/// <reference types="vite/client" />

// Vue SFC 模块声明，使 TypeScript 能识别 .vue 文件导入
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_USE_MOCK: string
  readonly VITE_LOG_LEVEL: string
  readonly VITE_ENABLE_DEVTOOLS: string
  readonly VITE_ENABLE_PERF: string
  readonly VITE_SSE_TIMEOUT: string
  readonly VITE_REQUEST_TIMEOUT: string
  readonly DEV: boolean
  readonly PROD: boolean
  readonly MODE: string
  readonly BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
