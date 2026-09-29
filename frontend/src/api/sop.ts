import { getToken } from '@/utils/auth'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface SopTemplateItem {
  id: number
  template_key: string
  name: string
  description?: string | null
  tags?: string[]
  definition: {
    name: string
    description?: string
    steps: Array<{
      subject: string
      description?: string
      verifier_type?: string
      loop?: string
      max_attempts?: number
    }>
    source?: string
  }
  builtin: boolean
}

/** 拉取 SOP 模板列表（keyword 按 key/名称/描述/标签匹配）。 */
export async function listSopTemplates(keyword = ''): Promise<SopTemplateItem[]> {
  const qs = keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''
  const res = await fetch(`${baseUrl}/api/v1/sop/templates${qs}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error(`SOP 模板加载失败（${res.status}）`)
  return await res.json()
}
