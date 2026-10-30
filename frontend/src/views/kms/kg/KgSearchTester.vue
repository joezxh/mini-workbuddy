<template>
  <div class="kg-search-tester">
    <a-space class="kg-search-tester__bar" wrap>
      <a-input
        v-model:value="query"
        :placeholder="t('kbMgmt.kg.searchQueryPlaceholder')"
        style="width: 320px"
        allow-clear
        @pressEnter="onSearch"
      />
      <a-input-number v-model:value="topK" :min="1" :max="50" style="width: 110px" />
      <a-button type="primary" :loading="loading" @click="onSearch">
        {{ t('kbMgmt.kg.search') }}
      </a-button>
      <a-switch v-model:checked="compareMode" />
      <span class="kg-muted">{{ t('kbMgmt.kg.compareMode') }}</span>
    </a-space>

    <a-alert
      v-if="graphEnabled === false"
      type="warning"
      show-icon
      class="kg-search-tester__alert"
      :message="t('kbMgmt.kg.graphDegraded')"
      :description="t('kbMgmt.kg.graphDegradedDesc')"
    />

    <a-row v-if="compareMode" :gutter="12">
      <a-col :span="12">
        <a-card size="small" :title="t('kbMgmt.kg.onlyVector')">
          <a-list size="small" :data-source="hits" bordered>
            <template #renderItem="{ item }">
              <a-list-item>{{ item.content?.slice(0, 60) }}</a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card size="small" :title="t('kbMgmt.kg.fusedResult')">
          <a-list size="small" :data-source="hits" bordered>
            <template #renderItem="{ item }">
              <a-list-item>
                <a-space>
                  <a-tag
                    v-for="s in item.metadata?.fusion_sources || []"
                    :key="s"
                    :color="s === 'graph' ? 'purple' : 'blue'"
                  >
                    {{ s }}
                  </a-tag>
                  <span>{{ item.content?.slice(0, 50) }}</span>
                </a-space>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>

    <a-list v-else size="small" bordered :data-source="hits" class="kg-search-tester__list">
      <template #renderItem="{ item }">
        <a-list-item>
          <div class="kg-search-tester__hit">
            <a-space>
              <a-tag color="green">{{ item.score?.toFixed?.(4) }}</a-tag>
              <a-tag
                v-for="s in item.metadata?.fusion_sources || []"
                :key="s"
                :color="s === 'graph' ? 'purple' : 'blue'"
              >
                {{ s }}
              </a-tag>
              <a-tag v-if="item.metadata?.score_type" color="default">
                {{ item.metadata.score_type }}
              </a-tag>
              <span class="kg-muted">#{{ item.chunk_index }} · {{ item.document_id }}</span>
            </a-space>
            <div class="kg-search-tester__content">{{ item.content }}</div>
            <div v-if="(item.metadata?.graph_seed_entities || []).length" class="kg-search-tester__path">
              {{ t('kbMgmt.kg.hitPath') }}:
              {{ (item.metadata?.graph_seed_entities || []).join(' → ') }}
            </div>
          </div>
        </a-list-item>
      </template>
    </a-list>

    <a-empty v-if="!hits.length && !loading" :description="t('kbMgmt.kg.noSearchResult')" />
  </div>
</template>

<script setup lang="ts">
/**
 * 图谱增强检索测试：展示融合来源（chunk / graph）与命中路径，
 * 并提供「仅向量 vs 融合」对比模式，直观看出图通道的增量贡献。
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgRetrieveHit } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const query = ref('')
const topK = ref(10)
const loading = ref(false)
const compareMode = ref(false)
const hits = ref<KgRetrieveHit[]>([])
const graphEnabled = ref<boolean | null>(null)

async function onSearch() {
  if (!query.value.trim()) {
    message.warning(t('kbMgmt.kg.searchQueryRequired'))
    return
  }
  loading.value = true
  try {
    const res = await api.retrieveGraph(props.knowledgeId, query.value.trim(), topK.value)
    hits.value = res?.results || []
    graphEnabled.value = res?.graph_enabled ?? false
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.searchFailed'))
    hits.value = []
    graphEnabled.value = false
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.kg-search-tester__bar {
  margin-bottom: 12px;
}
.kg-search-tester__alert {
  margin-bottom: 12px;
}
.kg-search-tester__hit {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}
.kg-search-tester__content {
  font-size: 13px;
}
.kg-search-tester__path {
  color: #722ed1;
  font-size: 12px;
}
.kg-muted {
  color: #999;
}
</style>
