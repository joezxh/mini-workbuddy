<template>
  <div class="kg-provenance">
    <a-row :gutter="12">
      <a-col :span="8">
        <a-card size="small" :title="t('kbMgmt.kg.provSource')">
          <a-select
            v-model:value="entityId"
            show-search
            :filter-option="filterEntity"
            :options="entityOptions"
            :placeholder="t('kbMgmt.kg.selectEntity')"
            style="width: 100%"
            @change="loadMentions"
          />
          <a-divider orientation="left">{{ t('kbMgmt.kg.provMentions') }}</a-divider>
          <a-list size="small" bordered :data-source="mentions">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="kg-provenance__item">
                  <span class="kg-provenance__meta">
                    #{{ item.chunk_index }} · {{ item.document_id }}
                  </span>
                  <span class="kg-provenance__text">{{ item.content }}</span>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <div v-if="!mentions.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
        </a-card>
      </a-col>

      <a-col :span="8">
        <a-card size="small" :title="t('kbMgmt.kg.provDocument')">
          <a-select
            v-model:value="documentId"
            show-search
            :options="documentOptions"
            :placeholder="t('kbMgmt.kg.selectDocument')"
            style="width: 100%"
            @change="loadByDocument"
          />
          <a-divider orientation="left">{{ t('kbMgmt.kg.provContributions') }}</a-divider>
          <a-list size="small" bordered :data-source="contributions">
            <template #renderItem="{ item }">
              <a-list-item>
                <span>
                  <a-tag v-if="item.type_code" color="blue">{{ item.type_code }}</a-tag>
                  {{ item.name }}
                </span>
              </a-list-item>
            </template>
          </a-list>
          <div v-if="!contributions.length" class="kg-muted">{{ t('kbMgmt.kg.noData') }}</div>
        </a-card>
      </a-col>

      <a-col :span="8">
        <a-card size="small" :title="t('kbMgmt.kg.failedList')">
          <a-list size="small" bordered :data-source="failed">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="kg-provenance__item">
                  <span class="kg-provenance__meta">
                    #{{ item.chunk_index }} · {{ item.document_id }}
                  </span>
                  <span class="kg-provenance__text kg-provenance__text--error">
                    {{ item.details?.error || t('kbMgmt.kg.failedStructure') }}
                  </span>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <div v-if="!failed.length" class="kg-muted">{{ t('kbMgmt.kg.noFailedSegments') }}</div>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
/**
 * 溯源面板（双向）：
 *   实体 -> 提及它的切片（看依据从哪来）
 *   文档 -> 它贡献的实体/关系（看这个文档影响了图谱什么）
 * 外加抽取失败切片清单（供重试定位）。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/kg'
import type { KgEntity, KgFailedSegment } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const entities = ref<KgEntity[]>([])
const entityId = ref<number | undefined>(undefined)
const documentId = ref<string | undefined>(undefined)
const mentions = ref<{ chunk_index: number; document_id: string; content: string }[]>([])
const contributions = ref<{ id: number; name: string; type_code?: string | null }[]>([])
const failed = ref<KgFailedSegment[]>([])

const entityOptions = computed(() =>
  entities.value.map((e) => ({ label: `${e.name}（${e.entity_key}）`, value: e.id })),
)
const documentOptions = computed(() => {
  const ids = new Set<string>()
  entities.value.forEach((e) => (e.source_document_ids || []).forEach((d) => ids.add(d)))
  return Array.from(ids).map((d) => ({ label: d, value: d }))
})

function filterEntity(input: string, option: any) {
  const kw = (input || '').toLowerCase()
  return String(option?.label || '').toLowerCase().includes(kw)
}

async function loadEntities() {
  try {
    const res = await api.listEntities(props.knowledgeId, { limit: 500 })
    entities.value = res?.items || []
  } catch {
    entities.value = []
  }
}

async function loadMentions() {
  mentions.value = []
  if (!entityId.value) return
  try {
    const res = await api.getEntityMentions(props.knowledgeId, entityId.value)
    mentions.value = res?.items || []
  } catch {
    mentions.value = []
  }
}


async function loadByDocument() {
  contributions.value = []
  if (!documentId.value) return
  contributions.value = entities.value
    .filter((e) => (e.source_document_ids || []).includes(documentId.value as string))
    .map((e) => ({ id: e.id, name: e.name, type_code: e.type_code }))
}

async function loadFailed() {
  try {
    const res = await api.listFailedSegments(props.knowledgeId)
    failed.value = res?.items || []
  } catch {
    failed.value = []
  }
}

onMounted(async () => {
  await loadEntities()
  await loadFailed()
})
</script>

<style scoped>
.kg-muted {
  color: #999;
}
.kg-provenance__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kg-provenance__meta {
  color: #999;
  font-size: 12px;
}
.kg-provenance__text {
  font-size: 12px;
}
.kg-provenance__text--error {
  color: #cf1322;
}
</style>
