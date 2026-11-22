import { ref, watch } from 'vue'

export type ViewMode = 'list' | 'grid'
const STORAGE_KEY = 'file-view-mode'

export function useFileView() {
  const saved = localStorage.getItem(STORAGE_KEY)
  const viewMode = ref<ViewMode>(saved === 'grid' ? 'grid' : 'list')
  watch(viewMode, (v) => localStorage.setItem(STORAGE_KEY, v))
  return { viewMode }
}
