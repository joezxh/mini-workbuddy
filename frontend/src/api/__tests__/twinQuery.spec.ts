import { describe, it, expect, vi, beforeEach } from 'vitest'
vi.mock('@/utils/request', () => {
  const post = vi.fn(); const get = vi.fn()
  return { default: { post, get } }
})
import api from '@/utils/request'
import { listQueries, previewQuery } from '../twinQuery'
const getMock = api.get as unknown as ReturnType<typeof vi.fn>
const postMock = api.post as unknown as ReturnType<typeof vi.fn>

describe('api/twinQuery（Q2/Q3 挂 /api/v1/dataops）', () => {
  beforeEach(() => { getMock.mockReset(); postMock.mockReset() })

  it('listQueries verified_only 转小写 query 参数', async () => {
    getMock.mockResolvedValueOnce([])
    await listQueries(11, { shape: 'kpi', verifiedOnly: true })
    expect(getMock).toHaveBeenCalledWith('/api/v1/dataops/ontologies/11/queries?shape=kpi&verified_only=true')
  })

  it('previewQuery 默认 limit=200（与后端同口径，不给预览拉全量的后门）', async () => {
    postMock.mockResolvedValueOnce({ records: [] })
    await previewQuery(4, { region: 'east' })
    expect(postMock).toHaveBeenCalledWith('/api/v1/dataops/queries/4/preview',
      { params: { region: 'east' }, limit: 200 })
  })
})
