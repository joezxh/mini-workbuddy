<template>
  <div class="rag-test">
    <div class="rag-test__head">
      <h2 class="rag-test__title">{{ t('wikiMgmt.rag.title') || 'RAG 测试' }}</h2>
      <a-button @click="closeShellTab('kg-wiki-rag', '/wiki')">
        <template #icon><ArrowLeftOutlined /></template>
        {{ t('common.back') }}
      </a-button>
    </div>

    <a-input-search
      v-model:value="query"
      :placeholder="t('wikiMgmt.rag.queryPlaceholder')"
      :enter-button="t('kbMgmt.search.searchBtn')"
      @search="onSearch"
      :loading="searching"
    />
    <div class="mode-row">
      <!-- 知识库作用域：缺省为全部知识库 -->
      <a-select
        v-model:value="knowledgeId"
        allow-clear
        style="min-width: 200px"
        :placeholder="t('kmsWiki.ragAllKnowledges')"
        :options="knowledgeOptions"
      />
      <a-radio-group v-model:value="mode" size="small">
        <a-radio-button value="hybrid">{{ t('wikiMgmt.rag.modeHybrid') }}</a-radio-button>
        <a-radio-button value="semantic">{{ t('wikiMgmt.rag.modeSemantic') }}</a-radio-button>
        <a-radio-button value="keyword">{{ t('wikiMgmt.rag.modeKeyword') }}</a-radio-button>
      </a-radio-group>
      <a-button type="link" :loading="asking" @click="onAsk">
        <template #icon><BulbOutlined /></template>{{ t('wikiMgmt.rag.askAi') }}
      </a-button>
    </div>

    <a-tabs v-model:activeKey="resultTab" style="margin-top: 12px">
      <a-tab-pane key="result" :tab="t('wikiMgmt.rag.resultsTab')">
        <SearchResultList :items="results" :loading="searching" />
      </a-tab-pane>
      <a-tab-pane key="ai" :tab="t('wikiMgmt.rag.aiTab')">
        <a-spin :spinning="asking">
          <LLMAnswerPanel v-if="llmAnswer" :answer="llmAnswer" :citations="llmCitations" />
          <a-empty v-else :description="t('wikiMgmt.rag.askHint')" />
        </a-spin>
      </a-tab-pane>
    </a-tabs>

    <a-divider>{{ t('wikiMgmt.rag.recentLogs') }}</a-divider>
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
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ArrowLeftOutlined, BulbOutlined } from '@ant-design/icons-vue'
import { searchWiki, askWiki, listSearchLogs, listKnowledges } from '@/api/wiki'
import SearchResultList from './components/SearchResultList.vue'
import LLMAnswerPanel from './components/LLMAnswerPanel.vue'
import type { SearchItem, CitationItem, SearchLogItem } from './types/wiki'
import { closeShellTab } from '@/utils/shellTab'

const { t } = useI18n()
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
/** 检索作用域：选中的知识库，null = 全部知识库 */
const knowledgeId = ref<number | null>(null)
const knowledgeOptions = ref<{ label: string; value: number }[]>([])

async function loadKnowledges() {
  try {
    const res = await listKnowledges()
    knowledgeOptions.value = (res || []).map((k: any) => ({
      label: k.name || k.title || String(k.id),
      value: k.id,
    }))
  } catch {
    knowledgeOptions.value = []
  }
}

const logColumns = computed(() => [
  { title: t('wikiMgmt.rag.time'), dataIndex: 'created_at', key: 'created_at' },
  { title: t('wikiMgmt.rag.query'), dataIndex: 'query', key: 'query' },
  { title: t('wikiMgmt.rag.mode'), dataIndex: 'mode', key: 'mode' },
  { title: t('wikiMgmt.rag.hits'), dataIndex: 'result_count', key: 'result_count' },
  { title: t('kbMgmt.ext.duration'), dataIndex: 'latency_ms', key: 'latency_ms' },
])

async function onSearch() {
  if (!query.value.trim()) return
  searching.value = true
  resultTab.value = 'result'
  try {
    const res = await searchWiki({
      query: query.value,
      mode: mode.value as any,
      top_k: 10,
      knowledge_id: knowledgeId.value ?? undefined,
    })
    results.value = res.items || []
    loadLogs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.search.searchFailed'))
  } finally {
    searching.value = false
  }
}
async function onAsk() {
  if (!query.value.trim()) return
  asking.value = true
  resultTab.value = 'ai'
  try {
    const res = await askWiki({
      query: query.value,
      top_k: 5,
      knowledge_id: knowledgeId.value ?? undefined,
    })
    llmAnswer.value = res.answer || ''
    llmCitations.value = res.citations || []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('wikiMgmt.rag.askFailed'))
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
onMounted(() => {
  loadLogs()
  loadKnowledges()
})
</script>

<style scoped>
.rag-test {
  max-width: 880px;
  padding: 24px;
}
.rag-test__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.rag-test__title {
  margin: 0;
  font-size: 18px;
  color: var(--fg);
}
.mode-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
