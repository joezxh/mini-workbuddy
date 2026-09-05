import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Report {
  reportId: string
  reportTitle: string
  reportType: string
  contentMarkdown: string
  generatedAt: string
  [key: string]: any
}

export const useReportStore = defineStore('report', () => {
  // 当前查看的报表
  const currentReport = ref<Report | null>(null)
  
  // 报表列表
  const reportList = ref<Report[]>([])
  
  // 报表加载状态
  const loading = ref(false)

  /**
   * 设置当前报表
   */
  function setCurrentReport(report: Report | null) {
    currentReport.value = report
  }

  /**
   * 设置报表列表
   */
  function setReportList(list: Report[]) {
    reportList.value = list
  }

  /**
   * 设置加载状态
   */
  function setLoading(status: boolean) {
    loading.value = status
  }

  /**
   * 清空当前报表
   */
  function clearCurrentReport() {
    currentReport.value = null
  }

  return {
    currentReport,
    reportList,
    loading,
    setCurrentReport,
    setReportList,
    setLoading,
    clearCurrentReport
  }
})

