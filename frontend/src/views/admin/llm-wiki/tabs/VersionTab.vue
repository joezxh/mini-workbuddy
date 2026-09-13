<template>
  <div class="version-tab">
    <a-select
      v-model:value="selectedArticleId"
      show-search
      :placeholder="t('wikiMgmt.ver.selectArticle')"
      style="width: 320px"
      :filter-option="filterOption"
      :options="articleOptions"
      :loading="loading"
      @change="onSelect"
    />
    <div style="margin-top: 16px" v-if="selectedArticleId">
      <VersionTimeline :article-id="selectedArticleId" :current-version="currentVersion" />
    </div>
    <a-empty v-else :description="t('wikiMgmt.ver.pleaseSelect')" style="margin-top: 40px" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { listArticles } from '@/api/wiki.ts'
import VersionTimeline from '@/views/kms/wiki/components/VersionTimeline.vue'

const { t } = useI18n()
const articleOptions = ref<any[]>([])
const selectedArticleId = ref<number | null>(null)
const currentVersion = ref(0)
const loading = ref(false)

async function reload() {
  loading.value = true
  try {
    const res = await listArticles({ page: 1, page_size: 200 })
    articleOptions.value = (res.items || []).map((a: any) => ({
      value: a.id,
      label: `v${a.version} · ${a.title}`,
    }))
  } catch (e) {
    message.error(t('wikiMgmt.art.loadFailed'))
  } finally {
    loading.value = false
  }
}
function onSelect(id: number) {
  const found = articleOptions.value.find((o) => o.value === id)
  currentVersion.value = found ? Number((found.label.match(/v(\d+)/) || [])[1] || 0) : 0
}
function filterOption(input: string, option: any) {
  return option.label.toLowerCase().includes(input.toLowerCase())
}
onMounted(reload)
</script>
