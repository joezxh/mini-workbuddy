<template>
  <a-modal
    v-model:open="visible"
    :title="`搜索测试 - ${webSearch?.name || ''}`"
    width="800px"
    :footer="null"
    :destroy-on-close="true"
    @cancel="visible = false"
  >
    <div class="search-test-container">
      <!-- 供应商信息 -->
      <div class="provider-info" v-if="webSearch">
        <a-descriptions :column="3" size="small">
          <a-descriptions-item label="平台">
            <a-tag color="blue">{{ dictLabel(DictType.WEB_SEARCH_PLATFORM, webSearch.platform) || webSearch.platform }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="URL">
            <span class="url-text">{{ webSearch.url || '默认' }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="webSearch.status === 1 ? 'success' : 'error'">
              {{ webSearch.status === 1 ? '启用' : '禁用' }}
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <!-- 搜索输入 -->
      <div class="search-input-area">
        <a-input-search
          v-model:value="query"
          placeholder="输入搜索关键词..."
          enter-button="搜索"
          size="large"
          :loading="loading"
          :disabled="!enabled"
          @search="handleSearch"
        />
      </div>

      <!-- 结果区域 -->
      <div class="results-area" v-if="hasResult">
        <!-- 状态栏 -->
        <div class="result-status" v-if="!loading">
          <a-tag :color="error ? 'error' : 'success'" size="small">
            {{ error ? '搜索失败' : '搜索完成' }}
          </a-tag>
          <span class="meta" v-if="!error">
            共 {{ results.length }} 条结果 · 耗时 {{ duration }}ms
          </span>
        </div>

        <!-- 错误信息 -->
        <a-alert v-if="error" type="error" :message="error" show-icon style="margin-bottom: 12px" />

        <!-- 结果列表 -->
        <div class="result-list" v-if="results.length > 0">
          <div v-for="(item, index) in results" :key="index" class="result-item">
            <div class="result-index">{{ index + 1 }}</div>
            <div class="result-content">
              <div class="result-title">
                <a :href="item.url" target="_blank" rel="noopener">{{ item.title || '无标题' }}</a>
              </div>
              <div class="result-url">{{ item.url }}</div>
              <div class="result-snippet">{{ item.snippet }}</div>
            </div>
            <div class="result-score" v-if="item.score">
              <a-tooltip title="相关度评分">
                <a-tag color="purple">{{ (item.score * 100).toFixed(0) }}%</a-tag>
              </a-tooltip>
            </div>
          </div>
        </div>

        <!-- 无结果 -->
        <a-empty v-if="!error && results.length === 0 && !loading" description="未找到相关结果" />
      </div>

      <!-- 初始状态 -->
      <a-empty v-if="!hasResult && !loading" description="输入关键词开始搜索">
        <template #image>
          <SearchOutlined style="font-size: 48px; color: var(--fg-muted)" />
        </template>
      </a-empty>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import { testWebSearch, type AiWebSearch } from '@/api/ai-web-search'
import { loadAdminDicts, dictLabel } from '@/composables/useAdminDict'
import { DictType } from '@/api/dictionary'

interface SearchResultItem {
  title: string
  url: string
  snippet: string
  score: number
}

const props = defineProps<{
  open: boolean
  webSearch?: AiWebSearch | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const query = ref('')
const loading = ref(false)
const results = ref<SearchResultItem[]>([])
const error = ref('')
const duration = ref(0)
const hasResult = ref(false)

// 仅当供应商启用时允许交互；输入是否为空不禁用输入框（否则无法输入）
const enabled = computed(() => props.webSearch?.status === 1)
const canSearch = computed(() => {
  return enabled.value && query.value.trim().length > 0
})

onMounted(() => {
  loadAdminDicts([DictType.WEB_SEARCH_PLATFORM])
})

// 打开时重置
watch(
  () => props.open,
  (val) => {
    if (val) {
      query.value = ''
      results.value = []
      error.value = ''
      duration.value = 0
      hasResult.value = false
    }
  }
)

const handleSearch = async () => {
  if (!canSearch.value || !props.webSearch) return

  loading.value = true
  error.value = ''
  results.value = []
  hasResult.value = true

  const startTime = Date.now()

  try {
    const res = await testWebSearch({
      id: props.webSearch.id,
      query: query.value.trim(),
    })
    duration.value = Date.now() - startTime
    results.value = res.results || []

    if (res.raw?.error) {
      error.value = res.raw.error
    } else {
      emit('success')
    }
  } catch (e: any) {
    duration.value = Date.now() - startTime
    error.value = e.message || '搜索请求失败'
  } finally {
    loading.value = false
  }
}
</script>

<style lang="less" scoped>
.search-test-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.provider-info {
  padding: 12px;
  background: var(--bg-input);
  border-radius: 6px;
  border: 1px solid var(--border);

  .url-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--fg-secondary);
  }
}

.search-input-area {
  margin: 8px 0;
}

.results-area {
  .result-status {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .meta {
      font-size: 13px;
      color: var(--fg-secondary);
    }
  }
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 500px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .result-index {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-hover);
    border-radius: 50%;
    font-size: 12px;
    font-weight: 600;
    color: var(--fg-secondary);
    flex-shrink: 0;
  }

  .result-content {
    flex: 1;
    min-width: 0;

    .result-title {
      font-size: 14px;
      font-weight: 500;
      margin-bottom: 4px;

      a {
        color: var(--accent);
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }
    }

    .result-url {
      font-size: 12px;
      color: var(--ok);
      margin-bottom: 6px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .result-snippet {
      font-size: 13px;
      color: var(--fg-secondary);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }

  .result-score {
    flex-shrink: 0;
  }
}
</style>
