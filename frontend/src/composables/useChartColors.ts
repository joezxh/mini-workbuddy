/**
 * 图表颜色配置 Composable
 * 从字典数据中获取颜色配置（单例模式，避免重复加载）
 */
import { ref } from 'vue'
import { getRiskLevelsCached, getDisposalStatusCached, getEventTypesCached } from '@/api/dictionary'
import type { DictionaryItem } from '@/api/dictionary'

// 全局共享的颜色数据（单例）
const riskLevelColors = ref<Record<string, string>>({})
const disposalStatusColors = ref<Record<string, string>>({})
const eventTypeColors = ref<Record<string, string>>({})
let isLoading = false
let isLoaded = false

export function useChartColors() {

  // 默认颜色方案（作为后备）
  const defaultRiskColors: Record<string, string> = {
    'low': '#52c41a',
    'medium': '#faad14',
    'high': '#ff7a45',
    'critical': '#f5222d'
  }

  const defaultStatusColors: Record<string, string> = {
    'pending': '#d9d9d9',
    'processing': '#1890ff',
    'in_progress': '#1890ff',
    'completed': '#52c41a',
    'closed': '#8c8c8c'
  }

  const defaultEventTypeColors: Record<string, string> = {
    'neighbor_dispute': '#4096ff',
    'family_dispute': '#36cfc9',
    'labor_dispute': '#73d13d',
    'property_dispute': '#ffd666',
    'economic_dispute': '#ff7875',
    'medical_dispute': '#b37feb',
    'education_dispute': '#13c2c2',
    'land_dispute': '#fa8c16',
    'traffic_accident': '#eb2f96',
    'public_security': '#722ed1',
    'petition': '#52c41a',
    'other': '#8c8c8c'
  }

  // 加载字典颜色（单例模式，只加载一次）
  const loadColors = async () => {
    // 如果已经加载或正在加载，直接返回
    if (isLoaded || isLoading) {
      return
    }
    
    isLoading = true
    
    try {
      // 加载风险等级颜色
      const riskLevels = await getRiskLevelsCached()
      if (riskLevels && Array.isArray(riskLevels)) {
        riskLevels.forEach((item: DictionaryItem) => {
          if (item.color) {
            riskLevelColors.value[item.item_code] = item.color
            if (item.item_value && item.item_value !== item.item_code) {
              riskLevelColors.value[item.item_value] = item.color
            }
          }
        })
      }

      // 加载处置状态颜色
      const disposalStatus = await getDisposalStatusCached()
      if (disposalStatus && Array.isArray(disposalStatus)) {
        disposalStatus.forEach((item: DictionaryItem) => {
          if (item.color) {
            disposalStatusColors.value[item.item_code] = item.color
            if (item.item_value && item.item_value !== item.item_code) {
              disposalStatusColors.value[item.item_value] = item.color
            }
          }
        })
      }

      // 加载事件类型颜色
      const eventTypes = await getEventTypesCached()
      if (eventTypes && Array.isArray(eventTypes)) {
        eventTypes.forEach((item: DictionaryItem) => {
          if (item.color) {
            eventTypeColors.value[item.item_code] = item.color
            if (item.item_value && item.item_value !== item.item_code) {
              eventTypeColors.value[item.item_value] = item.color
            }
          }
        })
      }
      
      isLoaded = true
    } catch (error) {
      console.error('加载字典颜色失败:', error)
    } finally {
      isLoading = false
    }
  }

  // 获取风险等级颜色
  const getRiskLevelColor = (level: string): string => {
    return riskLevelColors.value[level] || defaultRiskColors[level] || '#d9d9d9'
  }

  // 获取处置状态颜色
  const getDisposalStatusColor = (status: string): string => {
    return disposalStatusColors.value[status] || defaultStatusColors[status] || '#d9d9d9'
  }

  // 获取事件类型颜色
  const getEventTypeColor = (type: string): string => {
    return eventTypeColors.value[type] || defaultEventTypeColors[type] || '#4096ff'
  }

  // 获取风险等级颜色数组（用于图表）
  const getRiskLevelColorArray = (): string[] => {
    return [
      getRiskLevelColor('low'),
      getRiskLevelColor('medium'),
      getRiskLevelColor('high'),
      getRiskLevelColor('critical')
    ]
  }

  // 获取事件类型颜色数组（用于图表）
  const getDisposalStatusColorArray = (): string[] => {
    return [
      getDisposalStatusColor('pending'),
      getDisposalStatusColor('processing'),
      getDisposalStatusColor('completed'),
      getDisposalStatusColor('closed')
    ]
  }

  // 通用方法：根据字典类型和代码获取颜色
  const getColorByCode = (dictType: string, code: string): string => {
    switch (dictType) {
      case 'risk_level':
        return getRiskLevelColor(code)
      case 'disposal_status':
        return getDisposalStatusColor(code)
      case 'event_type':
        return getEventTypeColor(code)
      case 'dept_type':
      case 'event_source_dept':
        // 部门类型使用默认颜色方案
        const deptColors: Record<string, string> = {
          'petition': '#1890ff',
          'public_security': '#52c41a',
          'justice': '#faad14',
          'court': '#ff7a45',
          'procuratorate': '#f5222d',
          'community': '#13c2c2',
          'street': '#722ed1',
          'other': '#8c8c8c'
        }
        return deptColors[code] || '#4096ff'
      case 'person_type':
        // 人员类型使用默认颜色方案
        const personColors: Record<string, string> = {
          'petition': '#1890ff',
          'mental_illness': '#ff7a45',
          'drug_user': '#f5222d',
          'released': '#faad14',
          'community_correction': '#52c41a',
          'aids': '#eb2f96',
          'cult': '#722ed1',
          'other': '#8c8c8c'
        }
        return personColors[code] || '#4096ff'
      default:
        return '#4096ff'
    }
  }

  // 自动加载颜色数据（如果还未加载）
  if (!isLoaded && !isLoading) {
    loadColors()
  }

  return {
    riskLevelColors,
    disposalStatusColors,
    eventTypeColors,
    getRiskLevelColor,
    getDisposalStatusColor,
    getEventTypeColor,
    getRiskLevelColorArray,
    getDisposalStatusColorArray,
    getColorByCode,
    loadColors
  }
}

