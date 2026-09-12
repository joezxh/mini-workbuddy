<template>
  <div class="search-bar">
    <a-input-search
      v-model:value="query"
      placeholder="搜索知识库内容，或输入问题让 AI 回答"
      enter-button="检索"
      size="large"
      :loading="loading"
      @search="emitSearch"
    />
    <div class="mode-row">
      <a-radio-group v-model:value="mode" size="small">
        <a-radio-button value="hybrid">混合</a-radio-button>
        <a-radio-button value="semantic">语义</a-radio-button>
        <a-radio-button value="keyword">关键词</a-radio-button>
      </a-radio-group>
      <a-button type="link" size="small" :loading="asking" @click="emitAsk">
        <template #icon><BulbOutlined /></template>
        问 AI
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { BulbOutlined } from '@ant-design/icons-vue'

defineProps<{ loading?: boolean; asking?: boolean }>()
const emit = defineEmits<{
  search: [payload: { query: string; mode: string }]
  ask: [payload: { query: string }]
}>()

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
