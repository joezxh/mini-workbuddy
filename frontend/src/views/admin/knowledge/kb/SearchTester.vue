<template>
  <div class="kb-search">
    <div class="kb-search__bar">
      <a-select v-model:value="kbId" placeholder="选择数据集" style="width: 240px">
        <a-select-option v-for="d in datasets" :key="d.kb_id" :value="d.kb_id">{{ d.name }}</a-select-option>
      </a-select>
      <a-input v-model:value="query" placeholder="输入检索 query" style="flex: 1" @press-enter="run" />
      <a-input-number v-model:value="topK" :min="1" :max="20" />
      <a-switch v-model:checked="compare" /> <span class="muted">对比模式</span>
      <a-button type="primary" :disabled="!kbId" @click="run"><SearchOutlined /> 检索</a-button>
    </div>

    <div class="kb-search__result" v-if="!compare">
      <a-list :data-source="results" :locale="{ emptyText: t('knowledge.common.empty') }">
        <template #renderItem="{ item, index }">
          <a-list-item>
            <a-list-item-meta :description="item.content">
              <template #title>#{{ index + 1 }} · score {{ item.score?.toFixed?.(3) }} · 来源 {{ item.source }}</template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </div>

    <div class="kb-search__cmp" v-else>
      <div class="kb-search__cmp-col">
        <h4>纯向量</h4>
        <a-list size="small" :data-source="vecResults" :locale="{ emptyText: t('knowledge.common.empty') }">
          <template #renderItem="{ item, index }">
            <a-list-item>#{{ index + 1 }} {{ item.content?.slice(0, 60) }}</a-list-item>
          </template>
        </a-list>
      </div>
      <div class="kb-search__cmp-col">
        <h4>向量 + 混合</h4>
        <a-list size="small" :data-source="hybResults" :locale="{ emptyText: t('knowledge.common.empty') }">
          <template #renderItem="{ item, index }">
            <a-list-item>#{{ index + 1 }} {{ item.content?.slice(0, 60) }}</a-list-item>
          </template>
        </a-list>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/knowledgeBase'

const { t } = useI18n()
const datasets = ref<any[]>([])
const kbId = ref<string>()
const query = ref('')
const topK = ref(5)
const compare = ref(false)
const results = ref<any[]>([])
const vecResults = ref<any[]>([])
const hybResults = ref<any[]>([])

async function loadDatasets() {
  const r: any = await api.listDatasets()
  datasets.value = r.data || r || []
}
async function run() {
  if (!kbId.value) return
  try {
    if (compare.value) {
      const v: any = await api.retrieve(kbId.value, query.value, topK.value, false)
      const h: any = await api.retrieve(kbId.value, query.value, topK.value, true)
      vecResults.value = v.data?.results || v.results || []
      hybResults.value = h.data?.results || h.results || []
    } else {
      const r: any = await api.retrieve(kbId.value, query.value, topK.value, false)
      results.value = r.data?.results || r.results || []
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '检索失败')
  }
}
onMounted(loadDatasets)
</script>

<style scoped>
.kb-search__bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.kb-search__cmp { display: flex; gap: 16px; }
.kb-search__cmp-col { flex: 1; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px; }
.muted { color: var(--fg-muted); }
</style>
