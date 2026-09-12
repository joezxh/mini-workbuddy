<template>
  <div>
    <a-input-search
      v-model:value="kw"
      placeholder="按标题搜索文章"
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
            {{ record.status === 1 ? '发布' : record.status === -1 ? '归档' : '草稿' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="router.push(`/wiki/${record.slug}`)">查看</a>
          <a-divider type="vertical" />
          <a @click="router.push(`/wiki/edit/${record.id}`)">编辑</a>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { listArticles } from '@/api/wiki.ts'

const router = useRouter()
const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: 'Slug', dataIndex: 'slug', key: 'slug' },
  { title: '版本', dataIndex: 'version', key: 'version' },
  { title: '状态', key: 'status' },
  { title: '操作', key: 'action' },
]
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
    message.error('加载文章失败')
  } finally {
    loading.value = false
  }
}
onMounted(reload)
</script>
