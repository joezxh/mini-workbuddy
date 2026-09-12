<template>
  <a-modal
    :open="open"
    :title="`版本对比：v${targetVersion} ↔ 当前(v${currentVersion})`"
    width="80%"
    @update:open="(v) => { if (!v) emit('close') }"
  >
    <a-spin :spinning="loading">
      <pre class="diff-pre">{{ diff || '两个版本内容一致，无差异' }}</pre>
    </a-spin>
    <template #footer>
      <a-button @click="emit('close')">关闭</a-button>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { diffArticle } from '@/api/wiki'

const props = defineProps<{
  articleId: number
  versionId: number
  currentVersion: number
  targetVersion: number
  open: boolean
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const diff = ref('')
const loading = ref(false)

watch(
  () => props.open,
  async (v) => {
    if (v) await load()
  },
  { immediate: true }
)

async function load() {
  loading.value = true
  try {
    const res = await diffArticle(props.articleId, props.versionId)
    diff.value = res.diff || ''
  } catch (e) {
    diff.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.diff-pre {
  background: #f6f8fa;
  padding: 12px;
  border-radius: 6px;
  max-height: 60vh;
  overflow: auto;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
}
</style>
