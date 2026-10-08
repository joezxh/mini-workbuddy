<template>
  <a-drawer v-model:open="visible" :title="t('kbMgmt.segmentDetail')" :width="720">
    <a-spin v-if="loading" />
    <template v-else>
      <a-space class="sd__head" wrap>
        <a-tag color="blue">{{ documentId }}</a-tag>
        <span class="sd__count">{{ t('kbMgmt.segmentCount', { count: total }) }}</span>
      </a-space>

      <a-list size="small" :data-source="items" :pagination="pagination">
        <template #renderItem="{ item }">
          <a-list-item class="sd__item">
            <div class="sd__row">
              <a-tag :color="typeColor(item.chunk_type)">{{ item.chunk_type }}</a-tag>
              <span class="sd__idx">#{{ item.chunk_index }}</span>
              <a-tag v-if="!item.has_embedding" color="orange">{{ t('kbMgmt.noEmbedding') }}</a-tag>
              <a-space size="small">
                <a-button size="small" @click="startEdit(item)">{{ t('common.edit') }}</a-button>
                <a-button size="small" @click="startKeywords(item)">{{ t('kbMgmt.keywords') }}</a-button>
                <a-button size="small" @click="loadCitations(item)">{{ t('kbMgmt.viewCitations') }}</a-button>
                <a-popconfirm :title="t('kbMgmt.confirmDeleteSegment')" @confirm="remove(item)">
                  <a-button size="small" danger>{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </div>
            <div class="sd__content">{{ item.content }}</div>
            <div v-if="item.answer" class="sd__answer">
              <strong>{{ t('kbMgmt.answer') }}：</strong>{{ item.answer }}
            </div>
            <div v-if="Array.isArray(item.keywords) && item.keywords.length" class="sd__kw">
              <a-tag v-for="k in item.keywords" :key="k">{{ k }}</a-tag>
            </div>
          </a-list-item>
        </template>
      </a-list>

      <!-- 编辑 / 关键词 -->
      <a-modal
        v-model:open="editOpen"
        :title="editingKeywords ? t('kbMgmt.keywords') : t('kbMgmt.editSegment')"
        @ok="submitEdit"
        :confirm-loading="saving"
      >
        <a-form layout="vertical">
          <template v-if="editingKeywords">
            <a-form-item :label="t('kbMgmt.keywordsHint')">
              <a-select v-model:value="keywords" mode="tags" :placeholder="t('kbMgmt.keywordsPlaceholder')" />
            </a-form-item>
          </template>
          <template v-else>
            <a-form-item :label="t('kbMgmt.segmentContent')">
              <a-textarea v-model:value="content" :rows="8" />
            </a-form-item>
            <a-alert type="info" :message="t('kbMgmt.reembedHint')" show-icon />
          </template>
        </a-form>
      </a-modal>

      <!-- 引用来源 -->
      <a-modal v-model:open="citeOpen" :title="t('kbMgmt.citations')" :footer="null" width="640">
        <a-spin v-if="citeLoading" />
        <template v-else-if="citations">
          <a-descriptions size="small" :column="1" bordered>
            <a-descriptions-item :label="t('kbMgmt.sourceDocument')">
              {{ citations.document?.name || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('kbMgmt.siblingCount')">
              {{ citations.sibling_count }}
            </a-descriptions-item>
          </a-descriptions>
          <template v-if="citations.parent">
            <a-divider>{{ t('kbMgmt.parentChunk') }}</a-divider>
            <pre class="sd__cite">{{ citations.parent.content }}</pre>
          </template>
          <template v-if="citations.children?.length">
            <a-divider>{{ t('kbMgmt.childChunks') }} ({{ citations.children.length }})</a-divider>
            <pre v-for="c in citations.children" :key="c.id" class="sd__cite">#{{ c.chunk_index }} {{ c.content }}</pre>
          </template>
        </template>
      </a-modal>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  deleteSegment,
  getSegmentCitations,
  listDocumentSegments,
  updateSegment,
  updateSegmentKeywords,
  type KbSegment,
} from '@/api/kb'

const props = defineProps<{ documentId: string | null; open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'changed'): void }>()
const { t } = useI18n()

const visible = computed({
  get: () => props.open,
  set: (v: boolean) => emit('update:open', v),
})

const loading = ref(false)
const items = ref<KbSegment[]>([])
const total = ref(0)
const page = ref(1)
const page_size = 20

const pagination = computed(() => ({
  current: page.value,
  pageSize: page_size,
  total: total.value,
  size: 'small' as const,
  onChange: (p: number) => {
    page.value = p
    load()
  },
}))

const editOpen = ref(false)
const saving = ref(false)
const editing = ref<KbSegment | null>(null)
const editingKeywords = ref(false)
const content = ref('')
const keywords = ref<string[]>([])

const citeOpen = ref(false)
const citeLoading = ref(false)
const citations = ref<any>(null)

watch(
  () => [props.open, props.documentId],
  ([open]) => {
    if (open && props.documentId) load()
  },
  { immediate: true },
)

async function load() {
  if (!props.documentId) return
  loading.value = true
  try {
    const res: any = await listDocumentSegments(props.documentId, {
      page: page.value,
      page_size,
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.loadFailed'))
  } finally {
    loading.value = false
  }
}

function typeColor(chunkType: string) {
  return (
    { text: 'blue', qa: 'green', table_row: 'cyan', image: 'purple', parent: 'gold', child: 'geekblue' }[
      chunkType
    ] || 'default'
  )
}

function startEdit(item: KbSegment) {
  editing.value = item
  editingKeywords.value = false
  content.value = item.content || ''
  editOpen.value = true
}

function startKeywords(item: KbSegment) {
  editing.value = item
  editingKeywords.value = true
  keywords.value = Array.isArray(item.keywords) ? [...item.keywords] : []
  editOpen.value = true
}

async function submitEdit() {
  if (!editing.value) return
  saving.value = true
  try {
    if (editingKeywords.value) {
      await updateSegmentKeywords(editing.value.id, keywords.value)
    } else {
      await updateSegment(editing.value.id, { content: content.value })
    }
    message.success(t('kbMgmt.saved'))
    editOpen.value = false
    emit('changed')
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function remove(item: KbSegment) {
  try {
    await deleteSegment(item.id)
    message.success(t('kbMgmt.common.deleted'))
    emit('changed')
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

async function loadCitations(item: KbSegment) {
  citeOpen.value = true
  citeLoading.value = true
  try {
    citations.value = await getSegmentCitations(item.id)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.loadFailed'))
  } finally {
    citeLoading.value = false
  }
}
</script>

<style scoped>
.sd__head {
  margin-bottom: 8px;
}
.sd__count {
  color: var(--fg-muted);
  font-size: 12px;
}
.sd__item {
  display: block;
}
.sd__row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sd__idx {
  font-family: monospace;
  color: var(--fg-muted);
}
.sd__content {
  margin-top: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
.sd__answer {
  margin-top: 4px;
  color: var(--fg-muted);
}
.sd__kw {
  margin-top: 4px;
}
.sd__cite {
  background: var(--bg-subtle, #f6f8fa);
  border-radius: 4px;
  padding: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
}
</style>
