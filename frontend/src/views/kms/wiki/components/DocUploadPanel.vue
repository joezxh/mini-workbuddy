<template>
  <div class="doc-upload">
    <a-upload-dragger
      :show-upload-list="false"
      :accept="ACCEPT"
      :disabled="converting"
      :before-upload="beforeUpload"
      :custom-request="customRequest"
    >
      <p class="ant-upload-drag-icon">
        <inbox-outlined />
      </p>
      <p class="ant-upload-text">{{ t('kmsWiki.docUploadHint') }}</p>
      <p class="ant-upload-hint">{{ t('kmsWiki.docUploadFormats') }}</p>
    </a-upload-dragger>

    <div v-if="converting" class="doc-upload__status">
      <a-spin size="small" />
      <span>{{ t('kmsWiki.docConverting') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import { convertDocument, type ArticleConvertResult } from '@/api/wiki'

const ACCEPT = '.pdf,.docx,.txt,.md,.markdown,.pptx,.xlsx,.xls'
const MAX_MB = 20
const ALLOWED_EXTS = ACCEPT.split(',')

const emit = defineEmits<{ converted: [ArticleConvertResult] }>()

const { t } = useI18n()
const converting = ref(false)

function beforeUpload(file: File) {
  const lower = file.name.toLowerCase()
  if (!ALLOWED_EXTS.some((ext) => lower.endsWith(ext))) {
    message.error(t('kmsWiki.docUploadFormats'))
    return false
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    message.error(`文件超过 ${MAX_MB}MB 上限`)
    return false
  }
  return true
}

async function customRequest(option: any) {
  converting.value = true
  try {
    const result = await convertDocument(option.file)
    message.success(t('kmsWiki.docConvertSuccess', { name: option.file.name }))
    emit('converted', result)
    option.onSuccess?.(result)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    message.error(typeof detail === 'string' ? detail : t('kmsWiki.docConvertFailed'))
    option.onError?.(e)
  } finally {
    converting.value = false
  }
}
</script>

<style scoped>
.doc-upload {
  width: 100%;
}
.doc-upload__status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--fg-secondary, #646a73);
}
</style>
