<template>
  <div>
    <a-input-search
      v-model:value="kw"
      :placeholder="t('wikiMgmt.art.searchPlaceholder')"
      style="max-width: 320px; margin-bottom: 12px"
      @search="reload"
      allow-clear
    />
    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      :pagination="{ pageSize: 20 }"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 1 ? 'green' : record.status === -1 ? 'default' : 'orange'">
            {{ record.status === 1 ? t('wikiMgmt.art.published') : record.status === -1 ? t('wikiMgmt.art.archived') : t('wikiMgmt.art.draft') }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="router.push(`/wiki/${record.slug}`)">{{ t('wikiMgmt.art.view') }}</a>
          <a-divider type="vertical" />
          <a @click="router.push(`/wiki/edit/${record.id}`)">{{ t('common.edit') }}</a>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { listArticles } from '@/api/wiki.ts'

const { t } = useI18n()
const router = useRouter()
const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: t('kbMgmt.common.title'), dataIndex: 'title', key: 'title' },
  { title: 'Slug', dataIndex: 'slug', key: 'slug' },
  { title: t('wikiMgmt.tabVersion'), dataIndex: 'version', key: 'version' },
  { title: t('kbMgmt.common.status'), key: 'status' },
  { title: t('kbMgmt.common.actions'), key: 'action' },
])
const rows = ref<any[]>([])
const loading = ref(false)
const kw = ref('')

async function reload() {
  loading.value = true
  try {
    const params: any = { page: 1, page_size: 200 }
    if (kw.value.trim()) params.search = kw.value
    const res = await listArticles(params)
    rows.value = res.items || []
  } catch (e) {
    message.error(t('wikiMgmt.art.loadFailed'))
  } finally {
    loading.value = false
  }
}
onMounted(reload)
</script>
