<template>
  <div class="rag-test">
    <a-input-search
      v-model:value="query"
      placeholder="输入检索词或问题"
      enter-button="检索"
      @search="onSearch"
      :loading="searching"
    />
    <div class="mode-row">
      <a-radio-group v-model:value="mode" size="small">
        <a-radio-button value="hybrid">混合</a-radio-button>
        <a-radio-button value="semantic">语义</a-radio-button>
        <a-radio-button value="keyword">关键词</a-radio-button>
      </a-radio-group>
      <a-button type="link" :loading="asking" @click="onAsk">
        <template #icon><BulbOutlined /></template>问 AI
      </a-button>
    </div>

    <a-tabs v-model:activeKey="resultTab" style="margin-top: 12px">
      <a-tab-pane key="result" tab="检索结果">
        <SearchResultList :items="results" :loading="searching" />
      </a-tab-pane>
      <a-tab-pane key="ai" tab="AI 回答">
        <a-spin :spinning="asking">
          <LLMAnswerPanel v-if="llmAnswer" :answer="llmAnswer" :citations="llmCitations" />
          <a-empty v-else description="点击「问 AI」获取答案" />
        </a-spin>
      </a-tab-pane>
    </a-tabs>

    <a-divider>最近检索日志</a-divider>
    <a-table
      :columns="logColumns"
      :data-source="logs"
      :loading="logsLoading"
      :pagination="false"
      row-key="id"
      size="small"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { BulbOutlined } from '@ant-design/icons-vue'
import { searchWiki, askWiki, listSearchLogs } from '@/api/wiki.ts'
import SearchResultList from '@/views/kms/wiki/components/SearchResultList.vue'
import LLMAnswerPanel from '@/views/kms/wiki/components/LLMAnswerPanel.vue'
import type { SearchItem, CitationItem, SearchLogItem } from '@/views/kms/wiki/types/wiki.ts'

const query = ref('')
const mode = ref('hybrid')
const searching = ref(false)
const asking = ref(false)
const resultTab = ref('result')
const results = ref<SearchItem[]>([])
const llmAnswer = ref('')
const llmCitations = ref<CitationItem[]>([])
const logs = ref<SearchLogItem[]>([])
const logsLoading = ref(false)

const logColumns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at' },
  { title: '检索词', dataIndex: 'query', key: 'query' },
  { title: '模式', dataIndex: 'mode', key: 'mode' },
  { title: '命中', dataIndex: 'result_count', key: 'result_count' },
  { title: '耗时(ms)', dataIndex: 'latency_ms', key: 'latency_ms' },
]

async function onSearch() {
  if (!query.value.trim()) return
  searching.value = true
  resultTab.value = 'result'
  try {
    const res = await searchWiki({ query: query.value, mode: mode.value as any, top_k: 10 })
    results.value = res.items || []
    loadLogs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '检索失败')
  } finally {
    searching.value = false
  }
}
async function onAsk() {
  if (!query.value.trim()) return
  asking.value = true
  resultTab.value = 'ai'
  try {
    const res = await askWiki({ query: query.value, top_k: 5 })
    llmAnswer.value = res.answer || ''
    llmCitations.value = res.citations || []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || 'AI 问答失败')
  } finally {
    asking.value = false
  }
}
async function loadLogs() {
  logsLoading.value = true
  try {
    const res = await listSearchLogs({ page: 1, page_size: 20 })
    logs.value = res.items || []
  } catch (e) {
    // 忽略
  } finally {
    logsLoading.value = false
  }
}
onMounted(loadLogs)
</script>

<style scoped>
.rag-test {
  max-width: 880px;
}
.mode-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
