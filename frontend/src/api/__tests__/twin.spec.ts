// frontend/src/api/__tests__/twin.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/request', () => {
  const post = vi.fn(); const get = vi.fn(); const patch = vi.fn(); const del = vi.fn()
  // 注：真实封装面是 get/post/put/delete/patch（utils/request.ts:106-126），mock 键名跟随现状用 delete
  return { default: { post, get, patch, delete: del } }
})
import api from '@/utils/request'
import * as twin from '../twin'
const postMock = api.post as unknown as ReturnType<typeof vi.fn>
const patchMock = api.patch as unknown as ReturnType<typeof vi.fn>
const delMock = api.delete as unknown as ReturnType<typeof vi.fn>

describe('api/twin（T1–T12 契约钉死）', () => {
  beforeEach(() => { postMock.mockReset(); patchMock.mockReset(); delMock.mockReset() })

  it('T8 整页取数：POST /api/v1/twins/pages/{id}/data，params 缺省发空体', async () => {
    postMock.mockResolvedValueOnce({ items: [] })
    await twin.loadPageData(7)
    expect(postMock).toHaveBeenCalledWith('/api/v1/twins/pages/7/data', {})
    await twin.loadPageData(7, { region: 'east' })
    expect(postMock).toHaveBeenLastCalledWith('/api/v1/twins/pages/7/data', { params: { region: 'east' } })
  })

  it('T6 解绑必须显式携带 query_id:null 键', async () => {
    patchMock.mockResolvedValueOnce({})
    await twin.patchWidget(3, { query_id: null })
    expect(patchMock).toHaveBeenCalledWith('/api/v1/twins/widgets/3', { query_id: null })
  })

  it('T10 发布走 TWINS 前缀并透传 PublishBody', async () => {
    postMock.mockResolvedValueOnce({ slug: 'abc' })
    await twin.publishPage(9, { access: 'role', role_codes: ['ops'] })
    expect(postMock).toHaveBeenCalledWith('/api/v1/twins/pages/9/publish',
      { access: 'role', role_codes: ['ops'] })
  })

  it('T11 只读页走 twin-p 前缀（与写权限面隔离）', async () => {
    postMock.mockResolvedValueOnce({ items: [] })
    await twin.runPublished('abc', { p: 1 })
    expect(postMock).toHaveBeenCalledWith('/api/v1/twin-p/abc/data', { params: { p: 1 } })
  })

  it('T12 approve 缺省不发体，带值发 {expires_in_days}', async () => {
    postMock.mockResolvedValueOnce({})
    await twin.approveAccessRequest(5)
    expect(postMock).toHaveBeenCalledWith('/api/v1/twins/access-requests/5/approve', {})
    await twin.approveAccessRequest(5, 30)
    expect(postMock).toHaveBeenLastCalledWith('/api/v1/twins/access-requests/5/approve', { expires_in_days: 30 })
  })
})
