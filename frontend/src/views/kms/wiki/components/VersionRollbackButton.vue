<template>
  <a-popconfirm
    :title="t('kmsWiki.rollbackConfirm', { version: versionNumber })"
    :description="t('kmsWiki.rollbackDescription', { from: versionNumber, to: (currentVersion || 0) + 1 })"
    :ok-text="t('skillHub.rollback')"
    :cancel-text="t('common.cancel')"
    :ok-button-props="{ loading }"
    @confirm="onRollback"
  >
    <a-button size="small">
      <template #icon><RollbackOutlined /></template>
      {{ t('kmsWiki.rollbackToVersion') }}
    </a-button>
  </a-popconfirm>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { RollbackOutlined } from '@ant-design/icons-vue'
import { rollbackArticle } from '@/api/wiki'

const props = defineProps<{
  articleId: number
  versionId: number
  versionNumber: number
  currentVersion: number
}>()
const emit = defineEmits<{ (e: 'done'): void }>()
const { t } = useI18n()
const loading = ref(false)

async function onRollback() {
  loading.value = true
  try {
    await rollbackArticle(props.articleId, props.versionId)
    message.success(t('kmsWiki.rolledBack'))
    emit('done')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kmsWiki.rollbackFailed'))
  } finally {
    loading.value = false
  }
}
</script>
