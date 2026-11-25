import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/request', () => {
  const get = vi.fn()
  const post = vi.fn()
  const put = vi.fn()
  const del = vi.fn()
  return { default: { get, post, put, delete: del } }
})

import api from '@/utils/request'
import {
  listDomains, createDomain, updateDomain, toggleDomain, deleteDomain,
  listOntologies, listTables, assetsSearch,
} from '../dataops'

const getMock = api.get as unknown as ReturnType<typeof vi.fn>
const postMock = api.post as unknown as ReturnType<typeof vi.fn>
const putMock = api.put as unknown as ReturnType<typeof vi.fn>
const delMock = api.delete as unknown as ReturnType<typeof vi.fn>

const BASE = '/api/v1/dataops'

describe('ontology domain API', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
    delMock.mockReset()
  })

  it('domain CRUD hits the expected endpoints', async () => {
    await listDomains({ status: 'active' })
    expect(getMock).toHaveBeenCalledWith(`${BASE}/domains`, { params: { status: 'active' } })

    await createDomain({ code: 'hr', name: 'HR人力资源' })
    expect(postMock).toHaveBeenCalledWith(`${BASE}/domains`, { code: 'hr', name: 'HR人力资源' })

    await updateDomain(7, { name: '人力资源' })
    expect(putMock).toHaveBeenCalledWith(`${BASE}/domains/7`, { name: '人力资源' })

    await toggleDomain(7, 'disabled')
    expect(putMock).toHaveBeenCalledWith(`${BASE}/domains/7/toggle`, { status: 'disabled' })

    await deleteDomain(7)
    expect(delMock).toHaveBeenCalledWith(`${BASE}/domains/7`)
  })

  it('list endpoints forward domain filters', async () => {
    await listOntologies({ domain_id: 3 })
    expect(getMock).toHaveBeenCalledWith(`${BASE}/ontologies`, { params: { domain_id: 3 } })

    await listTables(9, 'public', 'miniworkbuddy', 3)
    expect(getMock).toHaveBeenCalledWith(`${BASE}/sources/9/tables`, {
      params: { database: 'public', db_name: 'miniworkbuddy', domain_id: 3 },
    })

    await assetsSearch({ domain_id: 3 })
    expect(getMock).toHaveBeenCalledWith(`${BASE}/assets/search`, { params: { domain_id: 3 } })
  })
})
