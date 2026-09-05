/**
 * 字典数据 Composable（单例模式，避免重复加载）
 */
import { ref, computed } from 'vue'
import {
  getRiskLevelsCached,
  getDisposalStatusCached,
  getEventTypesCached,
  getPersonManageStatusCached,
  getModelTypesCached,
  getRegions,

  getSourceTypes,
  dictionaryCache,
  type DictionaryItem
} from '@/api/dictionary'

// 全局共享的字典数据（单例）
const riskLevels = ref<DictionaryItem[]>([])
const disposalStatus = ref<DictionaryItem[]>([])
const eventTypes = ref<DictionaryItem[]>([])
const personManageStatus = ref<DictionaryItem[]>([])
const regions = ref<DictionaryItem[]>([])

const sourceTypes = ref<DictionaryItem[]>([])
const deptTypes = ref<DictionaryItem[]>([])
const modelTypes = ref<DictionaryItem[]>([])

const loading = ref(false)
const error = ref<string | null>(null)

// 加载状态标志
const loadingStates = {
  riskLevels: false,
  disposalStatus: false,
  eventTypes: false,
  personManageStatus: false,
  regions: false,
  sourceTypes: false,
  deptTypes: false,
  modelTypes: false
}

const loadedStates = {
  riskLevels: false,
  disposalStatus: false,
  eventTypes: false,
  personManageStatus: false,
  regions: false,
  sourceTypes: false,
  deptTypes: false,
  modelTypes: false
}

/**
 * 使用字典数据
 */
export function useDictionary() {

  /**
   * 加载风险等级字典
   */
  const loadRiskLevels = async () => {
    if (loadedStates.riskLevels || loadingStates.riskLevels) {
      return
    }

    try {
      loadingStates.riskLevels = true
      loading.value = true
      const data = await getRiskLevelsCached()
      riskLevels.value = data || []
      loadedStates.riskLevels = true
    } catch (err: any) {
      error.value = err.message || '加载风险等级字典失败'
      console.error('加载风险等级字典失败:', err)
      riskLevels.value = []
    } finally {
      loadingStates.riskLevels = false
      loading.value = false
    }
  }

  /**
   * 加载处置状态字典
   */
  const loadDisposalStatus = async () => {
    if (loadedStates.disposalStatus || loadingStates.disposalStatus) {
      return
    }

    try {
      loadingStates.disposalStatus = true
      loading.value = true
      const data = await getDisposalStatusCached()
      disposalStatus.value = data || []
      loadedStates.disposalStatus = true
    } catch (err: any) {
      error.value = err.message || '加载处置状态字典失败'
      console.error('加载处置状态字典失败:', err)
      disposalStatus.value = []
    } finally {
      loadingStates.disposalStatus = false
      loading.value = false
    }
  }

  /**
   * 加载事件类型字典
   */
  const loadEventTypes = async () => {
    if (loadedStates.eventTypes || loadingStates.eventTypes) {
      return
    }

    try {
      loadingStates.eventTypes = true
      loading.value = true
      const data = await getEventTypesCached()
      eventTypes.value = data || []
      loadedStates.eventTypes = true
    } catch (err: any) {
      error.value = err.message || '加载事件类型字典失败'
      console.error('加载事件类型字典失败:', err)
      eventTypes.value = []
    } finally {
      loadingStates.eventTypes = false
      loading.value = false
    }
  }

  const loadPersonManageStatus = async () => {
    if (loadedStates.personManageStatus || loadingStates.personManageStatus) {
      return
    }

    try {
      loadingStates.personManageStatus = true
      loading.value = true
      const data = await getPersonManageStatusCached()
      personManageStatus.value = data || []
      loadedStates.personManageStatus = true
    } catch (err: any) {
      error.value = err.message || '加载人员管控状态字典失败'
      console.error('加载人员管控状态字典失败:', err)
      personManageStatus.value = []
    } finally {
      loadingStates.personManageStatus = false
      loading.value = false
    }
  }

  /**
   * 加载区域字典

   */
  const loadRegions = async (parentCode?: string) => {
    if (loadedStates.regions || loadingStates.regions) {
      return
    }

    try {
      loadingStates.regions = true
      loading.value = true
      const response = await getRegions(parentCode)
      regions.value = response || []
      loadedStates.regions = true
    } catch (err: any) {
      error.value = err.message || '加载区域字典失败'
      console.error('加载区域字典失败:', err)
      regions.value = []
    } finally {
      loadingStates.regions = false
      loading.value = false
    }
  }

  /**
   * 加载来源类型字典
   */
  const loadSourceTypes = async () => {
    if (loadedStates.sourceTypes || loadingStates.sourceTypes) {
      return
    }

    try {
      loadingStates.sourceTypes = true
      loading.value = true
      const response = await getSourceTypes()
      sourceTypes.value = response || []
      loadedStates.sourceTypes = true
    } catch (err: any) {
      error.value = err.message || '加载来源类型字典失败'
      console.error('加载来源类型字典失败:', err)
      sourceTypes.value = []
    } finally {
      loadingStates.sourceTypes = false
      loading.value = false
    }
  }

  /**
   * 加载部门类型字典
   */
  const loadDeptTypes = async () => {
    if (loadedStates.deptTypes || loadingStates.deptTypes) {
      return
    }

    try {
      loadingStates.deptTypes = true
      loading.value = true
      const { getDeptTypes } = await import('@/api/dictionary')
      const response = await getDeptTypes()
      deptTypes.value = response || []
      loadedStates.deptTypes = true
    } catch (err: any) {
      error.value = err.message || '加载部门类型字典失败'
      console.error('加载部门类型字典失败:', err)
      deptTypes.value = []
    } finally {
      loadingStates.deptTypes = false
      loading.value = false
    }
  }

  /**
   * 加载 AI 对话模型类型字典（model_type，由数据字典动态维护）
   */
  const loadModelTypes = async () => {
    if (loadedStates.modelTypes || loadingStates.modelTypes) {
      return
    }

    try {
      loadingStates.modelTypes = true
      loading.value = true
      const data = await getModelTypesCached()
      modelTypes.value = data || []
      loadedStates.modelTypes = true
    } catch (err: any) {
      error.value = err.message || '加载模型类型字典失败'
      console.error('加载模型类型字典失败:', err)
      modelTypes.value = []
    } finally {
      loadingStates.modelTypes = false
      loading.value = false
    }
  }

  /**
   * 加载所有常用字典
   */
  const loadAllDictionaries = async () => {
    await Promise.all([
      loadRiskLevels(),
      loadDisposalStatus(),
      loadEventTypes(),
      loadSourceTypes(),
      loadDeptTypes(),
      loadModelTypes()
    ])
  }

  /**
   * 清除字典缓存
   */
  const clearCache = (dictCode?: string) => {
    dictionaryCache.clear(dictCode)
  }

  /**
   * 根据编码获取字典项名称
   */
  const getDictItemName = (items: DictionaryItem[], code: string): string => {
    const item = items.find(i => i.item_code === code || i.item_value === code)
    return item?.item_name || code
  }

  /**
   * 根据编码获取字典项颜色
   */
  const getDictItemColor = (items: DictionaryItem[], code: string): string | undefined => {
    const item = items.find(i => i.item_code === code || i.item_value === code)
    return item?.color
  }

  /**
   * 根据编码获取字典项
   */
  const getDictItem = (items: DictionaryItem[], code: string): DictionaryItem | undefined => {
    return items.find(i => i.item_code === code || i.item_value === code)
  }

  /**
   * 根据字典类型获取字典项列表
   */
  const getDictItemsByType = async (dictType: string): Promise<DictionaryItem[]> => {
    try {
      // 根据类型返回对应的字典数据
      switch (dictType) {
        case 'risk_level':
          if (!loadedStates.riskLevels) {
            await loadRiskLevels()
          }
          return riskLevels.value || []
        case 'disposal_status':
          if (!loadedStates.disposalStatus) {
            await loadDisposalStatus()
          }
          return disposalStatus.value || []
        case 'event_type':
          if (!loadedStates.eventTypes) {
            await loadEventTypes()
          }
          return eventTypes.value || []
        case 'dept_type':
        case 'event_source_dept':
          if (!loadedStates.deptTypes) {
            await loadDeptTypes()
          }
          return deptTypes.value || []
        case 'model_type':
          if (!loadedStates.modelTypes) {
            await loadModelTypes()
          }
          return modelTypes.value || []
        case 'region':
          if (!loadedStates.regions) {
            await loadRegions()
          }
          return regions.value || []
        default:
          console.warn(`未知的字典类型: ${dictType}`)
          return []
      }
    } catch (err) {
      console.error(`获取字典数据失败 (${dictType}):`, err)
      return []
    }
  }

  // 计算属性：风险等级映射
  const riskLevelMap = computed(() => {
    const map: Record<string, DictionaryItem> = {}
    riskLevels.value.forEach(item => {
      map[item.item_code] = item
      if (item.item_value) {
        map[item.item_value] = item
      }
    })
    return map
  })

  // 计算属性：处置状态映射（含旧英文状态码的兜底映射，确保未更新数据库时也能正确显示中文）
  const disposalStatusMap = computed(() => {
    const map: Record<string, DictionaryItem> = {}

    // 旧英文状态码兜底（优先被字典数据覆盖）
    const legacyFallback: Record<string, Partial<DictionaryItem>> = {
      completed: { item_name: '已闭环', color: '#52c41a' },
      pending: { item_name: '待审核', color: '#faad14' },
      processing: { item_name: '处置中', color: '#4096ff' },
      in_attention: { item_name: '关注中', color: '#1890ff' },
      closed: { item_name: '已闭环', color: '#52c41a' },
      pending_review: { item_name: '待审核', color: '#faad14' },
    }
    Object.entries(legacyFallback).forEach(([code, info]) => {
      map[code] = { item_code: code, item_name: info.item_name!, color: info.color, item_value: code } as DictionaryItem
    })

    // 字典数据覆盖兜底（优先级更高）
    disposalStatus.value.forEach(item => {
      map[item.item_code] = item
      if (item.item_value) {
        map[item.item_value] = item
      }
    })
    return map
  })

  // 计算属性：事件类型映射（含全量纠纷类型兜底，确保字典未落库时也能正确显示中文）
  const eventTypeMap = computed(() => {
    const map: Record<string, DictionaryItem> = {}

    // 全量纠纷类型内建兼容映射
    const legacyEventTypes: Record<string, Partial<DictionaryItem>> = {
      'neighbor_dispute': { item_name: '邻里纠纷', color: '#4096ff' },
      'family_dispute': { item_name: '家庭婚姻纠纷', color: '#722ed1' },
      'labor_dispute': { item_name: '劳资纠纷', color: '#eb2f96' },
      'property_dispute': { item_name: '房产物业纠纷', color: '#fa8c16' },
      'economic_dispute': { item_name: '经济纠纷', color: '#faad14' },
      'medical_dispute': { item_name: '医疗纠纷', color: '#52c41a' },
      'education_dispute': { item_name: '教育纠纷', color: '#13c2c2' },
      'land_dispute': { item_name: '土地纠纷', color: '#1890ff' },
      'traffic_accident': { item_name: '交通事故', color: '#f5222d' },
      'public_security': { item_name: '治安事件', color: '#ff4d4f' },
      'petition': { item_name: '信访事件', color: '#ff7a45' },
      'other': { item_name: '其他', color: '#d9d9d9' },
    }
    Object.entries(legacyEventTypes).forEach(([code, info]) => {
      map[code] = { item_code: code, item_name: info.item_name!, color: info.color, item_value: code } as DictionaryItem
    })

    // 字典数据覆盖兜底（优先级更高）
    eventTypes.value.forEach(item => {
      map[item.item_code] = item
      if (item.item_value) {
        map[item.item_value] = item
      }
    })
    return map
  })

  // 计算属性：人员管控状态映射
  const personManageStatusMap = computed(() => {
    const map: Record<string, DictionaryItem> = {}

    // 内建兜底映射
    const legacyStatus: Record<string, Partial<DictionaryItem>> = {
      'in_attention':  { item_name: '关注中', color: '#1890ff' },
      'pending_manage':{ item_name: '待纳管', color: '#faad14' },
      'managing':      { item_name: '管控中', color: '#4096ff' },
      'released':      { item_name: '已闭环', color: '#52c41a' },
      // 旧版数据映射（disposal_status 字段遗留值）
      'pending':        { item_name: '待纳管', color: '#faad14' },
      'pending_review': { item_name: '待纳管', color: '#faad14' },
      'processing':     { item_name: '管控中', color: '#4096ff' },
      'completed':      { item_name: '已闭环', color: '#52c41a' },
      'closed':         { item_name: '已闭环', color: '#52c41a' },
      'failed':         { item_name: '处置失败', color: '#f5222d' },
    }

    Object.entries(legacyStatus).forEach(([code, info]) => {
      map[code] = { item_code: code, item_name: info.item_name!, color: info.color, item_value: code } as DictionaryItem
    })

    // 字典实际数据覆盖
    personManageStatus.value.forEach(item => {
      map[item.item_code] = item
      if (item.item_value) {
        map[item.item_value] = item
      }
    })
    return map
  })


  return {
    // 数据
    riskLevels,
    disposalStatus,
    personManageStatus,
    eventTypes,

    regions,
    sourceTypes,
    deptTypes,
    modelTypes,
    loading,
    error,

    // 映射
    riskLevelMap,
    disposalStatusMap,
    personManageStatusMap,
    eventTypeMap,


    // 方法
    loadRiskLevels,
    loadDisposalStatus,
    loadPersonManageStatus,
    loadEventTypes,

    loadRegions,
    loadSourceTypes,
    loadDeptTypes,
    loadModelTypes,
    loadAllDictionaries,
    clearCache,
    getDictItemName,
    getDictItemColor,
    getDictItem,
    getDictItemsByType
  }
}

/**
 * 风险等级辅助函数
 */
export function useRiskLevel() {
  const { riskLevels, riskLevelMap, loadRiskLevels } = useDictionary()

  const getRiskLevelName = (code: string) => {
    return riskLevelMap.value[code]?.item_name || code
  }

  const getRiskLevelColor = (code: string) => {
    return riskLevelMap.value[code]?.color || '#d9d9d9'
  }

  return {
    riskLevels,
    loadRiskLevels,
    getRiskLevelName,
    getRiskLevelColor
  }
}

/**
 * 处置状态辅助函数
 */
export function useDisposalStatus() {
  const { disposalStatus, disposalStatusMap, loadDisposalStatus } = useDictionary()

  const getDisposalStatusName = (code: string) => {
    return disposalStatusMap.value[code]?.item_name || code
  }

  const getDisposalStatusColor = (code: string) => {
    return disposalStatusMap.value[code]?.color || '#d9d9d9'
  }

  return {
    disposalStatus,
    loadDisposalStatus,
    getDisposalStatusName,
    getDisposalStatusColor
  }
}

/**
 * 事件类型辅助函数
 */
export function useEventType() {
  const { eventTypes, eventTypeMap, loadEventTypes } = useDictionary()

  const getEventTypeName = (code: string) => {
    return eventTypeMap.value[code]?.item_name || code
  }

  return {
    eventTypes,
    loadEventTypes,
    getEventTypeName
  }
}

