import fs from 'node:fs'
import path from 'node:path'
import { app } from 'electron'
import type { AppConfig } from '../shared/ipc'

/**
 * 客户端配置读写。
 *
 * 配置文件落在 `userData/app-config.json`，因此：
 *   - 开发态：%APPDATA%/miniworkbuddy-desktop/app-config.json
 *   - 安装后：%APPDATA%/<productName>/app-config.json
 * 升级 / 重装不会丢失后端地址，且无需重新打包即可改地址。
 */

/** 构建期默认值（由 scripts/electron.cjs 写入 dist-electron/defaults.json）。 */
function readBuildDefaults(): Partial<AppConfig> {
  try {
    const file = path.join(__dirname, '..', 'defaults.json')
    return JSON.parse(fs.readFileSync(file, 'utf-8')) as Partial<AppConfig>
  } catch {
    return {}
  }
}

export const DEFAULT_API_BASE_URL = readBuildDefaults().apiBaseUrl || 'http://localhost:8000'

function configFile(): string {
  return path.join(app.getPath('userData'), 'app-config.json')
}

function readFromDisk(): AppConfig {
  try {
    const raw = fs.readFileSync(configFile(), 'utf-8')
    const parsed = JSON.parse(raw) as Partial<AppConfig>
    return { apiBaseUrl: parsed.apiBaseUrl ?? DEFAULT_API_BASE_URL }
  } catch {
    return { apiBaseUrl: DEFAULT_API_BASE_URL }
  }
}

/** 进程内缓存，避免每次请求都读盘。 */
let cached: AppConfig | null = null

export function getConfig(): AppConfig {
  if (!cached) cached = readFromDisk()
  return { ...cached }
}

export function setConfig(patch: Partial<AppConfig>): AppConfig {
  const next: AppConfig = { ...getConfig(), ...patch }
  if (typeof next.apiBaseUrl === 'string') {
    // 去掉结尾斜杠，拼接时统一由调用方补 /
    next.apiBaseUrl = next.apiBaseUrl.trim().replace(/\/+$/, '')
  }
  cached = next
  try {
    fs.mkdirSync(path.dirname(configFile()), { recursive: true })
    fs.writeFileSync(configFile(), JSON.stringify(next, null, 2), 'utf-8')
  } catch (err) {
    console.error('[electron] 写入配置失败:', err)
  }
  return { ...next }
}
