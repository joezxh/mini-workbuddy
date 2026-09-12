<template>
  <div class="version-timeline">
    <a-list :data-source="versions" :loading="loading" size="small" :locale="{ emptyText: '暂无版本记录' }">
      <template #renderItem="{ item }">
        <a-list-item>
          <a-list-item-meta
            :title="`v${item.version} - ${item.title}`"
            :description="`${item.change_note || '无说明'} · 操作:${item.operation_type} · ${formatDate(item.created_at)}`"
          />
          <template #actions>
            <a @click="showDiff(item)">对比</a>
            <VersionRollbackButton
              :article-id="articleId"
              :version-id="item.id"
              :version-number="item.version"
              :current-version="currentVersion"
              @done="reload"
            />
          </template>
        </a-list-item>
      </template>
    </a-list>

    <VersionDiffView
      v-if="activeDiff"
      :article-id="articleId"
      :version-id="activeDiff.id"
      :current-version="currentVersion"
      :target-version="activeDiff.version"
      :open="diffVisible"
      @close="diffVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getArticleVersions } from '@/api/wiki'
import VersionRollbackButton from './VersionRollbackButton.vue'
import VersionDiffView from './VersionDiffView.vue'
import type { VersionItem } from '../types/wiki'

const props = defineProps<{ articleId: number; currentVersion: number }>()

const versions = ref<VersionItem[]>([])
const loading = ref(false)
const diffVisible = ref(false)
const activeDiff = ref<VersionItem | null>(null)

async function reload() {
  loading.value = true
  try {
    const res: VersionItem[] = await getArticleVersions(props.articleId)
    versions.value = (res || []).slice().reverse() // 新版本在前
  } finally {
    loading.value = false
  }
}

function showDiff(item: VersionItem) {
  activeDiff.value = item
  diffVisible.value = true
}

function formatDate(d?: string) {
  return d ? dayjs(d).format('YYYY-MM-DD HH:mm') : ''
}

onMounted(reload)
defineExpose({ reload })
</script>

<style scoped>
.version-timeline {
  padding: 4px 0;
}
</style>
