<template>
  <a-drawer v-model:open="visible" :title="t('kbExt.contentTitle')" :width="880" destroy-on-close>
    <a-spin v-if="loading" />
    <a-result
      v-else-if="error"
      status="warning"
      :title="t('kbExt.contentFailed')"
      :sub-title="error"
    >
      <template #extra>
        <a-button type="primary" @click="load">{{ t('kbExt.retry') }}</a-button>
      </template>
    </a-result>
    <template v-else-if="content">
      <div class="edv__head">
        <div class="edv__title">{{ content.title || fallbackTitle }}</div>
        <a-space size="small" wrap>
          <a-tag color="blue">{{ platformLabel || content.source_type }}</a-tag>
          <span v-if="content.external_updated_at" class="edv__time">
            {{ t('kbExt.colUpdated') }} {{ content.external_updated_at }}
          </span>
        </a-space>
      </div>
      <a-alert type="info" show-icon :message="t('kbExt.contentHint')" class="edv__hint" />
      <div class="markdown-body" v-html="html" />
    </template>
    <a-empty v-else :description="t('common.noData')" />
  </a-drawer>
</template>

<script setup lang="ts">
/**
 * 外部文档全文预览。
 *
 * 正文不落库（导入只保留切片），由服务端按需回源拉取：这里只负责渲染与错误回退，
 * 平台不可达时提示改用「分段」查看已入库内容。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  getExternalDocumentContent,
  type ExternalDocumentContent,
} from '@/api/kbExternalSource'

const props = defineProps<{
  open: boolean
  /** 落地文档 uuid（= KbDocument.uuid_code） */
  documentUuid: string | null
  /** 回源结果缺标题时的兜底（列表里的外部标题） */
  fallbackTitle?: string
  /** 平台展示名（列表已解析好，避免组件内再拉一次 providers） */
  platformLabel?: string
}>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()
const { t } = useI18n()

const visible = computed({
  get: () => props.open,
  set: (v: boolean) => emit('update:open', v),
})

// html:false —— 外部平台正文不可信，原始 HTML 一律转义后再清洗
const md = new MarkdownIt({ linkify: true, typographer: true })

const loading = ref(false)
const error = ref('')
const content = ref<ExternalDocumentContent | null>(null)

const html = computed(() => {
  const text = content.value?.markdown || ''
  return text ? DOMPurify.sanitize(md.render(text)) : ''
})

watch(
  () => [props.open, props.documentUuid] as const,
  ([open]) => {
    if (open && props.documentUuid) load()
  },
  { immediate: true },
)

async function load() {
  if (!props.documentUuid) return
  loading.value = true
  error.value = ''
  try {
    // request 拦截器已解包 response.data，这里拿到的就是接口体
    content.value = await getExternalDocumentContent(props.documentUuid)
  } catch (e: any) {
    content.value = null
    error.value = e?.response?.data?.detail || t('kbExt.contentFailed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.edv__head {
  margin-bottom: 10px;
}
.edv__title {
  margin-bottom: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--fg);
}
.edv__time {
  font-size: 12px;
  color: var(--fg-muted);
}
.edv__hint {
  margin-bottom: 12px;
}
.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--fg);
  word-break: break-word;
}
.markdown-body :deep(pre) {
  background: var(--bg-subtle);
  border-radius: 6px;
  padding: 10px 12px;
  overflow: auto;
}
.markdown-body :deep(img) {
  max-width: 100%;
}
</style>
