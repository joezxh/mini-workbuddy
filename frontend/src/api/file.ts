/**
 * 统一文件管理 API
 *
 * 对齐后端 /api/v1/system/file 与 /api/v1/system/file-config。
 * 所有响应统一为 { code, message, data } 契约（code=0 成功）。
 */
import request from '@/utils/request'

// ── 类型定义 ────────────────────────────────────────────────────────────────

export interface InfraFileVO {
  id: number
  configId: number | null
  path: string
  name: string | null
  url: string | null
  type: string | null
  size: number
  createTime: string | null
}

export interface FilePageParam {
  page?: number
  pageSize?: number
  configId?: number
  path?: string
  type?: string
}

export interface FilePageResp {
  data: InfraFileVO[]
  total: number
  page: number
  pageSize: number
}

export interface FileConfigPageResp {
  data: FileConfigVO[]
  total: number
  page: number
  pageSize: number
}

export interface FilePresignedUrlVO {
  configId: number
  uploadUrl: string
  url: string
  path: string
}

export interface FileCreateVO {
  configId?: number
  path: string
  name: string
  url?: string
  type?: string
  code?: string
  size: number
}

export interface DirectoryItem {
  name: string
  path: string
  hasChildren: boolean
  children: DirectoryItem[]
}

export interface FileStatistics {
  configId: number
  configName: string
  storageType: number
  fileCount: number
  totalSize: number
  storage: number
}

/** 存储类型枚举（对齐 Java FileStorageEnum） */
export const FileStorageEnum = {
  DB: 1,
  LOCAL: 10,
  FTP: 11,
  SFTP: 12,
  S3: 20,
  OSS: 30
} as const

/** 本期实现的存储类型（其余为预留扩展位） */
export const IMPLEMENTED_STORAGES = [FileStorageEnum.DB, FileStorageEnum.LOCAL, FileStorageEnum.S3]

export const FileStorageLabels: Record<number, string> = {
  1: '数据库 (DB)',
  10: '本地磁盘 (LOCAL)',
  11: 'FTP（待实现）',
  12: 'SFTP（待实现）',
  20: 'S3 兼容对象存储',
  30: '阿里云 OSS（待实现）'
}

export const FileStorageColorMap: Record<number, string> = {
  1: 'blue', 10: 'green', 11: 'default', 12: 'default', 20: 'purple', 30: 'default'
}

/** 各存储类型的配置字段（驱动动态表单） */
export interface FileClientConfig {
  domain?: string
  basePath?: string
  endpoint?: string
  bucket?: string
  accessKey?: string
  accessSecret?: string
  enablePathStyleAccess?: boolean
  enablePublicAccess?: boolean
  region?: string
  [key: string]: unknown
}

export interface FileConfigVO {
  id: number
  name: string
  code: string
  storage: number
  master: boolean
  config: FileClientConfig
  remark: string | null
  createTime: string | null
}

export interface FileConfigSaveVO {
  id?: number
  name: string
  code: string
  storage: number
  config: FileClientConfig
  remark?: string
}

// ── 压缩包任务类型 ──────────────────────────────────────────────────────────

export const ArchiveExtractStatus = {
  PENDING: 0, PROCESSING: 1, SUCCESS: 2, PARTIAL: 3, FAILED: 4, CANCELED: 5
} as const

export interface ArchiveUploadVO {
  taskId: string
  archiveName: string
  total: number
}

export interface ArchiveExtractFileVO {
  name: string
  url: string
  size: number
}

export interface ArchiveExtractFailedVO {
  name: string
  reason: string
}

export interface ArchiveExtractProgressVO {
  taskId: string
  archiveName: string
  status: number
  total: number
  done: number
  list: ArchiveExtractFileVO[]
  failed: ArchiveExtractFailedVO[]
  message: string
}

// ── 响应包装解包 ────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function unwrap<T>(res: any): T {
  if (res && typeof res === 'object' && 'code' in res && 'data' in res) {
    if (res.code !== 0) throw new Error(res.message || '请求失败')
    return res.data as T
  }
  return res as T
}

// ── 文件 API ────────────────────────────────────────────────────────────────

export const infraFileApi = {
  page(params: FilePageParam) {
    return request.get('/api/v1/system/file/page', { params }).then(r => unwrap<FilePageResp>(r))
  },
  upload(form: FormData, onProgress?: (percent: number) => void) {
    return request.post('/api/v1/system/file/upload', form, {
      timeout: 120000,
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
      }
    }).then(r => unwrap<{ id: number; url: string; path: string; name: string; size: number; type: string }>(r))
  },
  uploadArchive(form: FormData) {
    return request.post('/api/v1/system/file/upload-archive', form, { timeout: 120000 })
      .then(r => unwrap<ArchiveUploadVO>(r))
  },
  getArchiveProgress(taskId: string) {
    return request.get(`/api/v1/system/file/upload-archive/${taskId}`)
      .then(r => unwrap<ArchiveExtractProgressVO>(r))
  },
  cancelArchive(taskId: string) {
    return request.delete(`/api/v1/system/file/upload-archive/${taskId}`).then(r => unwrap<boolean>(r))
  },
  getPresignedUrl(name: string, directory?: string, code?: string) {
    return request.get('/api/v1/system/file/presigned-url', { params: { name, directory, code } })
      .then(r => unwrap<FilePresignedUrlVO>(r))
  },
  create(data: FileCreateVO) {
    return request.post('/api/v1/system/file/create', data).then(r => unwrap<number>(r))
  },
  delete(id: number) {
    return request.delete('/api/v1/system/file/delete', { params: { id } }).then(r => unwrap<boolean>(r))
  },
  deleteList(ids: number[]) {
    return request.delete('/api/v1/system/file/delete-list', { params: { ids: ids.join(',') } })
      .then(r => unwrap<boolean>(r))
  },
  getDirectories() {
    return request.get('/api/v1/system/file/directories').then(r => unwrap<DirectoryItem[]>(r))
  },
  getStatistics() {
    return request.get('/api/v1/system/file/statistics').then(r => unwrap<FileStatistics[]>(r))
  },
  downloadUrl(file: InfraFileVO): string {
    // 仅绝对 http(s) 的预签名/公开 URL 直接用（浏览器按 Content-Type 处理）；
    // 相对 url 走代理并强制 attachment（后端默认 inline 供预览）
    if (file.url && /^https?:\/\//i.test(file.url)) return file.url
    return `/api/v1/system/file/${file.configId}/get/${file.path}?download=1`
  },
  /** 预览 URL：同源代理，inline + 正确 Content-Type（img/video/audio/iframe/fetch 通用） */
  previewUrl(file: InfraFileVO): string {
    return `/api/v1/system/file/${file.configId}/get/${file.path}`
  }
}

// ── 文件配置 API ────────────────────────────────────────────────────────────

export const fileConfigApi = {
  page(params?: { page?: number; pageSize?: number; name?: string; code?: string; storage?: number }) {
    return request.get('/api/v1/system/file-config/page', { params }).then(r => unwrap<FileConfigPageResp>(r))
  },
  get(id: number) {
    return request.get('/api/v1/system/file-config/get', { params: { id } }).then(r => unwrap<FileConfigVO>(r))
  },
  create(data: FileConfigSaveVO) {
    return request.post('/api/v1/system/file-config/create', data).then(r => unwrap<number>(r))
  },
  update(data: FileConfigSaveVO) {
    return request.put('/api/v1/system/file-config/update', data).then(r => unwrap<boolean>(r))
  },
  delete(id: number) {
    return request.delete('/api/v1/system/file-config/delete', { params: { id } }).then(r => unwrap<boolean>(r))
  },
  deleteList(ids: number[]) {
    return request.delete('/api/v1/system/file-config/delete-list', { params: { ids: ids.join(',') } })
      .then(r => unwrap<boolean>(r))
  },
  test(id: number) {
    return request.get('/api/v1/system/file-config/test', { params: { id } }).then(r => unwrap<string>(r))
  },
  setMaster(id: number) {
    return request.put('/api/v1/system/file-config/update-master', undefined, { params: { id } })
      .then(r => unwrap<boolean>(r))
  },
  exportConfig() {
    return request.get('/api/v1/system/file-config/export').then(r => unwrap<FileConfigVO[]>(r))
  },
  importConfig(configs: FileConfigVO[]) {
    return request.post('/api/v1/system/file-config/import', configs).then(r => unwrap<number[]>(r))
  }
}

// 供旧调用方使用的兼容别名
export const infraFileConfigApi = fileConfigApi
