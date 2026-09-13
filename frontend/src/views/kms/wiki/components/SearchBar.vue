<template>
  <div class="search-bar">
    <a-input-search
      v-model:value="query"
      :placeholder="t('kmsWiki.searchAiPlaceholder')"
      :enter-button="t('kbMgmt.search.searchBtn')"
      size="large"
      :loading="loading"
      @search="emitSearch"
    />
    <div class="mode-row">
      <a-radio-group v-model:value="mode" size="small">
        <a-radio-button value="hybrid">{{ t('wikiMgmt.rag.modeHybrid') }}</a-radio-button>
        <a-radio-button value="semantic">{{ t('wikiMgmt.rag.modeSemantic') }}</a-radio-button>
        <a-radio-button value="keyword">{{ t('wikiMgmt.rag.modeKeyword') }}</a-radio-button>
      </a-radio-group>
      <a-button type="link" size="small" :loading="asking" @click="emitAsk">
        <template #icon><BulbOutlined /></template>
        {{ t('wikiMgmt.rag.askAi') }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { BulbOutlined } from '@ant-design/icons-vue'

defineProps<{ loading?: boolean; asking?: boolean }>()
const emit = defineEmits<{
  search: [payload: { query: string; mode: string }]
  ask: [payload: { query: string }]
}>()

const { t } = useI18n()
const query = ref('')
const mode = ref('hybrid')

function emitSearch() {
  if (query.value.trim()) emit('search', { query: query.value, mode: mode.value })
}
function emitAsk() {
  if (query.value.trim()) emit('ask', { query: query.value })
}
</script>

<style scoped>
.search-bar {
  max-width: 720px;
  margin: 0 auto 24px;
}
.mode-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
