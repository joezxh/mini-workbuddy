/// <reference types="node" />

declare namespace NodeJS {
  interface ProcessEnv {
    /** 由 scripts/electron.cjs 注入：Vite dev server 地址 */
    VITE_DEV_SERVER_URL?: string
    /** 设置为 1 时打包后仍允许打开 DevTools */
    ELECTRON_ENABLE_DEVTOOLS?: string
    /** 构建期写入的默认后端地址（供 scripts/electron.cjs 读取） */
    ELECTRON_DEFAULT_API_BASE_URL?: string
  }
}
