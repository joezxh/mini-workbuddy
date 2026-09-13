<template>
  <div class="article-view" v-if="article">
    <div class="article-toolbar">
      <a-breadcrumb>
        <a-breadcrumb-item><a @click="$router.push('/wiki')">{{ t('kmsWiki.title') }}</a></a-breadcrumb-item>
        <a-breadcrumb-item>{{ article.title }}</a-breadcrumb-item>
      </a-breadcrumb>
      <div class="toolbar-actions">
        <a-button @click="$router.push(`/wiki/edit/${article.id}`)">
          <template #icon><EditOutlined /></template>
          {{ t('common.edit') }}
        </a-button>
        <a-button @click="showVersions = true">
          <template #icon><HistoryOutlined /></template>
          {{ t('wikiMgmt.tabVersion') }} ({{ article.version }})
        </a-button>
        <a-popconfirm :title="t('wikiMgmt.deleteConfirm')" @confirm="handleDelete">
          <a-button danger>
            <template #icon><DeleteOutlined /></template>
            {{ t('common.delete') }}
          </a-button>
        </a-popconfirm>
      </div>
    </div>

    <a-row :gutter="24">
      <!-- 主内容 -->
      <a-col :span="18">
        <a-card>
          <h1>{{ article.title }}</h1>
          <div class="article-meta-bar">
            <a-tag v-for="tag in article.tags" :key="tag" color="blue">{{ tag }}</a-tag>
            <span class="meta-info">
              v{{ article.version }} · {{ t('kmsWiki.views', { count: article.view_count }) }} · {{ formatDate(article.updated_at) }}
            </span>
          </div>
          <a-divider />
          <!-- Markdown 渲染 -->
          <div class="markdown-body" v-html="renderedContent"></div>
        </a-card>
      </a-col>

      <!-- 侧边栏 -->
      <a-col :span="6">
        <!-- OWL 类标注 -->
        <a-card :title="t('kmsWiki.owlClasses')" size="small" v-if="article.owl_class_uris?.length">
          <a-tag v-for="uri in article.owl_class_uris" :key="uri" color="purple">
            {{ extractLabel(uri) }}
          </a-tag>
        </a-card>

        <!-- 反向链接 -->
        <a-card :title="t('kmsWiki.backlinks')" size="small" v-if="article.backlinks?.length" style="margin-top: 16px">
          <a-list :data-source="article.backlinks" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a @click="$router.push(`/wiki/${item}`)">{{ item }}</a>
              </a-list-item>
            </template>
          </a-list>
        </a-card>

        <!-- Wiki 链接 -->
        <a-card :title="t('kmsWiki.wikiLinks')" size="small" v-if="article.wiki_links?.length" style="margin-top: 16px">
          <a-list :data-source="article.wiki_links" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a @click="$router.push(`/wiki/${item}`)">{{ item }}</a>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>

    <!-- 版本历史抽屉 -->
    <a-drawer
      v-model:open="showVersions"
      :title="t('kmsWiki.versionHistory')"
      :width="480"
    >
      <a-list
        :data-source="versions"
        :loading="loadingVersions"
        size="small"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta
              :title="`v${item.version} - ${item.title}`"
              :description="`${item.change_note || t('kmsWiki.noNote')} · ${formatDate(item.created_at)}`"
            />
          </a-list-item>
        </template>
      </a-list>
    </a-drawer>
  </div>
  <a-spin v-else style="display: flex; justify-content: center; padding: 100px" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { EditOutlined, HistoryOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { getArticleBySlug, deleteArticle, getArticleVersions } from '@/api/wiki'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const md = new MarkdownIt({ html: false, linkify: true, typographer: true })

const article = ref<any>(null)
const versions = ref<any[]>([])
const showVersions = ref(false)
const loadingVersions = ref(false)

const renderedContent = computed(() => {
  if (!article.value?.content) return `<p>${t('kmsWiki.noContent')}</p>`
  const raw = md.render(article.value.content)
  return DOMPurify.sanitize(raw)
})

onMounted(() => loadArticle())
watch(() => route.params.slug, () => loadArticle())

async function loadArticle() {
  const slug = route.params.slug as string
  try {
    const res = await getArticleBySlug(slug)
    article.value = res.data
  } catch (e: any) {
    message.error(t('kmsWiki.notFound'))
    router.push('/wiki')
  }
}

async function handleDelete() {
  if (!article.value) return
  try {
    await deleteArticle(article.value.id)
    message.success(t('kbMgmt.common.deleted'))
    router.push('/wiki')
  } catch (e) {
    message.error(t('kbMgmt.common.deleteFailed'))
  }
}

// 版本历史 - 延迟加载
watch(showVersions, async (val) => {
  if (val && article.value && !versions.value.length) {
    loadingVersions.value = true
    try {
      const res = await getArticleVersions(article.value.id)
      versions.value = res.data || []
    } catch (e) {
      message.error(t('kmsWiki.loadVersionsFailed'))
    } finally {
      loadingVersions.value = false
    }
  }
})

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

function extractLabel(uri: string) {
  // 从 URI 提取可读标签
  const parts = uri.split(/[#/]/)
  return parts[parts.length - 1] || uri
}
</script>

<style scoped>
.article-view {
  padding: 24px;
}
.article-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.article-meta-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.meta-info {
  color: var(--fg-muted);
  font-size: 12px;
}
.markdown-body {
  line-height: 1.8;
  font-size: 15px;
}
</style>
