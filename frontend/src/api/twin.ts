/** 孪生应用 API 表面：T1–T12 + twin-p。逐一对齐 backend/app/routers/twin/twin.py，禁止臆造端点。 */
import request from '@/utils/request'
import type {
  CardsByGroup, TwinCard, TwinPage, TwinWidget, WidgetDatum, LoadPageResp, PublishInfo,
  PublishedMeta, PublishedData, WidgetCreateBody, WidgetPatchBody, LayoutItem,
  PublishAccess, AccessListResp,
} from '@/types/twin'

const TWINS = '/api/v1/twins'
const PUB = '/api/v1/twin-p'

export const listCards = () => request.get(`${TWINS}/cards`) as unknown as Promise<CardsByGroup>
export const createCard = (b: { name: string; icon?: string; description?: string;
  ontology_id: number; ontology_version: number; scene_key?: string }) =>
  request.post(`${TWINS}/cards`, b) as unknown as Promise<TwinCard>
export const getCard = (id: number) => request.get(`${TWINS}/cards/${id}`) as unknown as Promise<TwinCard>
export const patchCard = (id: number, b: Record<string, unknown>) =>
  request.patch(`${TWINS}/cards/${id}`, b) as unknown as Promise<TwinCard>
export const deleteCard = (id: number) => request.delete(`${TWINS}/cards/${id}`)
export const createCardFromTemplate = (b: { template_key: string; name: string; ontology_id?: number }) =>
  request.post(`${TWINS}/cards/from-template`, b) as unknown as Promise<TwinCard>

export const listPages = (cardId: number) =>
  request.get(`${TWINS}/cards/${cardId}/pages`) as unknown as Promise<TwinPage[]>
export const createPage = (cardId: number, b: { name: string; refresh_json?: Record<string, unknown> }) =>
  request.post(`${TWINS}/cards/${cardId}/pages`, b) as unknown as Promise<TwinPage>
export const reorderPages = (cardId: number, pageIds: number[]) =>
  request.post(`${TWINS}/cards/${cardId}/pages/reorder`, { page_ids: pageIds }) as unknown as Promise<TwinPage[]>
export const patchPage = (id: number, b: Record<string, unknown>) =>
  request.patch(`${TWINS}/pages/${id}`, b) as unknown as Promise<TwinPage>
export const deletePage = (id: number) => request.delete(`${TWINS}/pages/${id}`)

export const listWidgets = (pageId: number) =>
  request.get(`${TWINS}/pages/${pageId}/widgets`) as unknown as Promise<TwinWidget[]>
export const addWidget = (pageId: number, b: WidgetCreateBody) =>
  request.post(`${TWINS}/pages/${pageId}/widgets`, b) as unknown as Promise<TwinWidget>
export const saveLayout = (pageId: number, items: LayoutItem[]) =>
  request.post(`${TWINS}/pages/${pageId}/widgets/layout`, { items }) as unknown as Promise<TwinWidget[]>
export const patchWidget = (id: number, b: WidgetPatchBody) =>
  request.patch(`${TWINS}/widgets/${id}`, b) as unknown as Promise<TwinWidget>
export const deleteWidget = (id: number) => request.delete(`${TWINS}/widgets/${id}`)

export const loadPageData = (pageId: number, params?: Record<string, unknown>) =>
  request.post(`${TWINS}/pages/${pageId}/data`, params ? { params } : {}) as unknown as Promise<LoadPageResp>
export const loadWidgetData = (id: number) =>
  request.get(`${TWINS}/widgets/${id}/data`) as unknown as Promise<WidgetDatum>

export const publishPage = (pageId: number, b?: { access?: PublishAccess; role_codes?: string[] }) =>
  request.post(`${TWINS}/pages/${pageId}/publish`, b ?? {}) as unknown as Promise<PublishInfo>
export const unpublish = (publishId: number) => request.delete(`${TWINS}/publish/${publishId}`)  // twin.py:318

export const getPublished = (slug: string) =>
  request.get(`${PUB}/${slug}`) as unknown as Promise<PublishedMeta>
export const runPublished = (slug: string, params?: Record<string, unknown>) =>
  request.post(`${PUB}/${slug}/data`, params ? { params } : {}) as unknown as Promise<PublishedData>

export const requestCardAccess = (cardId: number, reason?: string) =>
  request.post(`${TWINS}/cards/${cardId}/access-request`, reason ? { reason } : {}) as unknown as Promise<Record<string, unknown>>
export const listAccessRequests = () =>
  request.get(`${TWINS}/access-requests`) as unknown as Promise<AccessListResp>
export const approveAccessRequest = (id: number, expiresInDays?: number) =>
  request.post(`${TWINS}/access-requests/${id}/approve`,
    expiresInDays ? { expires_in_days: expiresInDays } : {}) as unknown as Promise<Record<string, unknown>>
export const rejectAccessRequest = (id: number) =>
  request.post(`${TWINS}/access-requests/${id}/reject`, {}) as unknown as Promise<Record<string, unknown>>
