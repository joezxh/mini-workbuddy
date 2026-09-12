<template>
  <a-popconfirm
    :title="`确认回滚到 v${versionNumber} 吗？`"
    :description="`将基于 v${versionNumber} 生成新版本 v${(currentVersion || 0) + 1}，历史不会被删除`"
    ok-text="回滚"
    cancel-text="取消"
    :ok-button-props="{ loading }"
    @confirm="onRollback"
  >
    <a-button size="small">
      <template #icon><RollbackOutlined /></template>
      回滚到此版本
    </a-button>
  </a-popconfirm>
</template>

<script setup lang="ts">
import { ref } from 'vue'
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
const loading = ref(false)

async function onRollback() {
  loading.value = true
  try {
    await rollbackArticle(props.articleId, props.versionId)
    message.success('已回滚到该版本')
    emit('done')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '回滚失败')
  } finally {
    loading.value = false
  }
}
</script>
