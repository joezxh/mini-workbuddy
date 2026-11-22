import { ref } from 'vue'
import type { FileStatistics } from '@/api/file'
import { infraFileApi } from '@/api/file'

export function useFileStats() {
  const stats = ref<FileStatistics[]>([])
  const loading = ref(false)

  async function loadStats() {
    loading.value = true
    try {
      stats.value = await infraFileApi.getStatistics()
    } finally {
      loading.value = false
    }
  }

  return { stats, loading, loadStats }
}
