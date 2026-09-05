/**
 * 字典数据 API 接口
 */
import request from '@/utils/request'

// 字典项接口
export interface DictionaryItem {
  item_id: number
  dict_code: string
  item_code: string
  item_name: string
  item_value?: string
  parent_code?: string
  level: number
  color?: string
  icon?: string
  sort_order: number
  is_active: boolean
  extra_data?: Record<string, any>
  remark?: string
  created_at: string
  updated_at: string
}

// 字典接口
export interface Dictionary {
  dict_id: number
  dict_code: string
  dict_name: string
  dict_type: string
  description?: string
  sort_order: number
  is_active: boolean
  extra_data?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface DictionaryListResponse {
  data: Dictionary[]
  total: number
  page: number
  pageSize: number
}

// 字典树节点接口
export interface DictionaryTreeNode {
  item_id: number
  dict_code: string
  item_code: string
  item_name: string
  item_value?: string
  parent_code?: string
  level: number
  color?: string
  icon?: string
  sort_order: number
  is_active: boolean
  children: DictionaryTreeNode[]
}

// 字典类型常量
export const DictType = {
  RISK_LEVEL: 'risk_level',
  DISPOSAL_STATUS: 'disposal_status',
  EVENT_TYPE: 'event_type',
  /** 事件阶段：brewing/outbreak/escalation/disposal/calm */
  EVENT_PHASE: 'event_phase',
  /** 群体情绪：calm/anxious/angry/extreme */
  GROUP_EMOTION: 'group_emotion',
  /** 处置难度：easy/medium/hard/critical */
  DISPOSAL_DIFFICULTY: 'disposal_difficulty',
  /** 政治敏感度：normal/sensitive/highly_sensitive */
  POLITICAL_SENSITIVITY: 'political_sensitivity',
  REGION: 'region',
  SOURCE_TYPE: 'source_type',
  DEPT_TYPE: 'dept_type',
  PERSON_TYPE: 'person_type',
  TAG: 'tag',
  PERSON_MANAGE_STATUS: 'person_manage_status',
  /** 事件来源部门类型 */
  EVENT_SOURCE_TYPE: 'event_source_department',
  /** 定时任务类型 */
  TASK_TYPE: 'task_type',
  /** 企业实体类型（管理端企业表单） */
  ENTITY_TYPE: 'entity_type',
  /** 风险地点类型 */
  LOCATION_TYPE: 'location_type',
  /** 调解金句话术类型 */
  GOLD_SAYING_TYPE: 'gold_saying_type',
  /** AI 报告类型（处置分析/风险评估/趋势预测等） */
  REPORT_TYPE: 'report_type',
  /** 事件脊合维度（关键字/实体/人员/区域） */
  CLUSTER_DIMENSION: 'cluster_dimension',
  /** 仿真类型（单事件/聚合事件/反事实） */
  SIM_TYPE: 'sim_type',
  /** 仿真干预场景（无干预/调解干预/法律措施/舆情管控/经济补偿/反事实） */
  SIM_SCENARIO: 'sim_scenario',
  /** 仿真会话状态（待运行/运行中/已暂停/已完成/失败） */
  SIM_STATUS: 'sim_status',
  /** 纠纷调解时机阶段 */
  DISPUTE_TIMING_PHASE: 'dispute_timing_phase',
  /** AI 助手会话类型 */
  SESSION_TYPE: 'session_type',
  /** 时间粒度（小时/天/周） */
  TIME_GRANULARITY: 'time_granularity',
  /** 跨事件影响模式（双向传染/单向级联/资源竞争） */
  CROSS_EVENT_MODE: 'cross_event_mode',
  /** 反事实假设类型 */
  HYPOTHIS_TYPE: 'hypothesis_type',
  /** 聚合反事实假设类型 */
  CLUSTER_HYPOTHIS_TYPE: 'cluster_hypothesis_type',
  /** 假设干预策略 */
  COUNTERFACTUAL_SCENARIO: 'counterfactual_scenario',
  /** 初始事件阶段 */
  EVENT_STAGE: 'event_stage',
  /** 类案难度等级 (知识增强): 低/中/高 */
  CASE_DIFFICULTY: 'case_difficulty',
  /** 金句情绪阶段 (知识增强): 安抚/对抗/缓和 */
  EMOTION_STAGE: 'emotion_stage',
  /** 金句话术类型 (知识增强): 释法/共情/引导 */
  SPEECH_TYPE: 'speech_type',
  /** 本体关系类型（继承/实现/关联/聚合/组合/依赖） */
  ONTOLOGY_REL_TYPE: 'ontology_rel_type',
  /** 知识图谱推理执行模式（Skill/Tool/P1-P6 推理范式） */
  KG_REASONING_EXEC_MODE: 'kg_reasoning_exec_mode',
  /** AI 联网搜索平台（博查/Anspire/Google/Bing/自定义等） */
  WEB_SEARCH_PLATFORM: 'web_search_platform',
  /** AI 对话模型类型（文本/图片生成/视频生成等，由数据字典动态维护） */
  MODEL_TYPE: 'model_type',
}


// ==================== 字典管理 ====================

/**
 * 获取字典列表
 */
export function getDictionaries(params?: {
  dict_type?: string
  is_active?: boolean
  page?: number
  pageSize?: number
}) {
  return request.get<DictionaryListResponse>('/api/v1/dictionary/dictionaries', { params })
}

/**
 * 获取字典详情（包含字典项）
 */
export function getDictionary(dictCode: string, includeInactive = false) {
  return request.get<Dictionary & { items: DictionaryItem[] }>(
    `/api/v1/dictionary/dictionaries/${dictCode}`,
    { params: { include_inactive: includeInactive } }
  )
}

/**
 * 创建字典
 */
export function createDictionary(data: Partial<Dictionary>) {
  return request.post<Dictionary>('/api/v1/dictionary/dictionaries', data)
}

/**
 * 更新字典
 */
export function updateDictionary(dictCode: string, data: Partial<Dictionary>) {
  return request.put<Dictionary>(`/api/v1/dictionary/dictionaries/${dictCode}`, data)
}

/**
 * 删除字典
 */
export function deleteDictionary(dictCode: string) {
  return request.delete(`/api/v1/dictionary/dictionaries/${dictCode}`)
}

// ==================== 字典项管理 ====================

/**
 * 获取字典项列表
 */
export function getDictionaryItems(dictCode: string, params?: {
  parent_code?: string
  is_active?: boolean
}) {
  return request.get<DictionaryItem[]>(
    `/api/v1/dictionary/dictionaries/${dictCode}/items`,
    { params }
  )
}

/**
 * 获取字典树形结构
 */
export function getDictionaryTree(dictCode: string, includeInactive = false) {
  return request.get<DictionaryTreeNode[]>(
    `/api/v1/dictionary/dictionaries/${dictCode}/tree`,
    { params: { include_inactive: includeInactive } }
  )
}

/**
 * 创建字典项
 */
export function createDictionaryItem(dictCode: string, data: Partial<DictionaryItem>) {
  return request.post<DictionaryItem>(
    `/api/v1/dictionary/dictionaries/${dictCode}/items`,
    data
  )
}

/**
 * 更新字典项
 */
export function updateDictionaryItem(
  dictCode: string,
  itemCode: string,
  data: Partial<DictionaryItem>
) {
  return request.put<DictionaryItem>(
    `/api/v1/dictionary/dictionaries/${dictCode}/items/${itemCode}`,
    data
  )
}

/**
 * 删除字典项
 */
export function deleteDictionaryItem(dictCode: string, itemCode: string) {
  return request.delete(
    `/api/v1/dictionary/dictionaries/${dictCode}/items/${itemCode}`
  )
}

// ==================== 快捷查询接口 ====================

/**
 * 获取风险等级字典
 */
export function getRiskLevels() {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dict/risk-levels')
}

/**
 * 获取处置状态字典
 */
export function getDisposalStatus() {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dict/disposal-status')
}

/**
 * 获取事件类型字典
 */
export function getEventTypes() {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dict/event-types')
}

/**
 * 获取区域字典
 */
export function getRegions(parentCode?: string) {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dict/regions', {
    params: { parent_code: parentCode }
  })
}

/**
 * 获取来源类型字典
 */
export function getSourceTypes() {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dict/source-types')
}

/**
 * 获取部门类型字典
 */
export function getDeptTypes() {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dictionaries/dept_type/items')
}

/**
 * 获取人员管控状态字典
 */
export function getPersonManageStatus() {
  return request.get<DictionaryItem[]>('/api/v1/dictionary/dict/person-manage-status')
}


// ==================== 字典缓存管理 ====================

/**
 * 字典缓存类
 */
class DictionaryCache {
  private cache: Map<string, { data: DictionaryItem[]; timestamp: number }> = new Map()
  private readonly TTL = 5 * 60 * 1000 // 5分钟缓存

  /**
   * 获取缓存的字典数据
   */
  async get(dictCode: string, fetcher: () => Promise<DictionaryItem[]>): Promise<DictionaryItem[]> {
    const cached = this.cache.get(dictCode)
    const now = Date.now()

    // 如果缓存存在且未过期，返回缓存数据
    if (cached && now - cached.timestamp < this.TTL) {
      return cached.data
    }

    // 否则重新获取数据
    const data = await fetcher()
    this.cache.set(dictCode, { data, timestamp: now })
    return data
  }

  /**
   * 清除指定字典的缓存
   */
  clear(dictCode?: string) {
    if (dictCode) {
      this.cache.delete(dictCode)
    } else {
      this.cache.clear()
    }
  }
}

export const dictionaryCache = new DictionaryCache()

/**
 * 获取风险等级字典（带缓存）
 */
export async function getRiskLevelsCached() {
  return dictionaryCache.get(DictType.RISK_LEVEL, async () => {
    return await getRiskLevels()
  })
}

/**
 * 获取处置状态字典（带缓存）
 */
export async function getDisposalStatusCached() {
  return dictionaryCache.get(DictType.DISPOSAL_STATUS, async () => {
    return await getDisposalStatus()
  })
}

/**
 * 获取事件类型字典（带缓存）
 */
export async function getEventTypesCached() {
  return dictionaryCache.get(DictType.EVENT_TYPE, async () => {
    return await getEventTypes()
  })
}

/**
 * 获取人员管控状态字典（带缓存）
 */
export async function getPersonManageStatusCached() {
  return dictionaryCache.get(DictType.PERSON_MANAGE_STATUS, async () => {
    return await getPersonManageStatus()
  })
}

/**
 * 获取 AI 报告类型字典（带缓存）
 */
export async function getReportTypesCached() {
  return dictionaryCache.get(DictType.REPORT_TYPE, async () => {
    const res = await getDictionaryItems(DictType.REPORT_TYPE)
    return res
  })
}

/**
 * 获取 AI 对话模型类型字典（带缓存，model_type 数据字典，动态维护）
 */
export async function getModelTypesCached() {
  return dictionaryCache.get(DictType.MODEL_TYPE, async () => {
    return await getDictionaryItems(DictType.MODEL_TYPE)
  })
}

