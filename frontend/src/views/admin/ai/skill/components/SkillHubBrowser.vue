<template>
  <div class="hub-body">
    <!-- 仓库选择栏：仓库列表横向一行 -->
    <div class="hub-toolbar">
      <div class="hub-repo-tabs">
        <div
          v-for="r in hubRepos"
          :key="r.id"
          class="hub-repo-tab"
          :class="{ active: hubActiveRepoId === r.id }"
          @click="selectHubRepo(r.id)"
        >
          <span class="hub-repo-name">{{ r.name }}</span>
          <a-tag v-if="r.source_type === 'skillhub'" color="purple" size="small">{{ t('skillHub.cloudMarket') }}</a-tag>
          <a-tag v-else-if="r.is_official" color="blue" size="small">{{ t('skillHub.official') }}</a-tag>
        </div>
        <a-button type="dashed" size="small" class="hub-repo-add" @click="openRepoModal()">
          <PlusOutlined /> {{ t('skillHub.manageRepo') }}
        </a-button>
      </div>
      <div class="hub-toolbar-right">
        <a-input-search
          v-model:value="hubKeyword"
          :placeholder="t('skillHub.searchSkill')"
          allow-clear
          style="width: 280px"
          @search="loadHubSkills(true)"
        />
        <a-button @click="handleRefreshHubRepo" :loading="hubRefreshing">
          <ReloadOutlined /> {{ t('skillHub.refreshRepo') }}
        </a-button>
      </div>
    </div>

    <div class="hub-content" v-if="hubActiveRepoId">
      <!-- 左侧分类 -->
      <div class="hub-cats">
        <div
          class="hub-cat-item"
          :class="{ active: hubActiveCat === '' }"
          @click="selectHubCat('')"
        >
          {{ t('skillHub.all') }} ({{ hubSkillTotal }})
        </div>
        <div
          v-for="c in hubCategories"
          :key="c.key"
          class="hub-cat-item"
          :class="{ active: hubActiveCat === c.key }"
          @click="selectHubCat(c.key)"
        >
          {{ (isCloudMarket ? cloudCategoryLabel(c) : c.name) }} ({{ c.count }})
        </div>
      </div>

      <!-- 右侧列表 -->
      <div class="hub-list">
        <a-spin :spinning="hubLoading">
          <div class="hub-cards">
            <a-card
              v-for="item in hubSkills"
              :key="item.id"
              size="small"
              class="hub-card"
              :title="item.name"
            >
              <template #extra>
                <a-button
                  type="link"
                  size="small"
                  :loading="item._installing"
                  @click="handleInstallHubSkill(item)"
                >
                  {{ t('skillHub.install') }}
                </a-button>
              </template>
              <div class="hub-card-desc">{{ item.description || '—' }}</div>
              <div class="hub-card-meta">
                <a-tag v-if="item.category_name" color="green" size="small">
                  {{ item.category_name }}
                </a-tag>
                <a-tag v-if="item.version" size="small">v{{ item.version }}</a-tag>
                <a-tag v-for="t in (item.tags || [])" :key="t" size="small">{{ t }}</a-tag>
              </div>
            </a-card>
          </div>
          <a-empty v-if="!hubLoading && !hubSkills.length" :description="t('skillHub.noSkillsInCat')" />
          <div class="hub-pagination" v-if="hubSkillTotal > hubPageSize">
            <a-pagination
              v-model:current="hubPage"
              v-model:page-size="hubPageSize"
              :total="hubSkillTotal"
              show-size-changer
              :show-total="(tt: number) => t('skillHub.totalCount', { total: tt })"
              @change="loadHubSkills(false)"
            />
          </div>
        </a-spin>
      </div>
    </div>
    <a-empty v-else :description="t('skillHub.selectOrAddRepo')" />

    <!-- 技能仓库管理弹窗 -->
    <a-modal
      v-model:visible="repoModalVisible"
      :title="t('skillHub.repoModalTitle')"
      @ok="saveRepo"
      :confirm-loading="repoSaving"
      :ok-text="repoEditingId ? t('common.save') : t('skillHub.addRepo')"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('skillHub.repoName')">
          <a-input v-model:value="repoForm.name" :placeholder="t('skillHub.repoNamePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('skillHub.gitUrl')">
          <a-input
            v-model:value="repoForm.url"
            :placeholder="t('skillHub.gitUrlPlaceholder')"
            :disabled="repoForm.is_official"
          />
        </a-form-item>
        <a-form-item :label="t('skillHub.branch')">
          <a-input v-model:value="repoForm.branch" :disabled="repoForm.is_official" />
        </a-form-item>
      </a-form>
      <a-divider>{{ t('skillHub.configuredRepos') }}</a-divider>
      <a-list size="small" :data-source="hubRepos">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta :description="item.url">
              <template #title>
                {{ item.name }}
                <a-tag v-if="item.source_type === 'skillhub'" color="purple" size="small">{{ t('skillHub.cloudMarket') }}</a-tag>
                <a-tag v-else-if="item.is_official" color="blue" size="small">{{ t('skillHub.official') }}</a-tag>
              </template>
            </a-list-item-meta>
            <template #actions>
              <a v-if="!item.is_official" @click="editRepo(item)">{{ t('common.edit') }}</a>
              <a-popconfirm
                v-if="!item.is_official"
                :title="t('skillHub.deleteRepoConfirm')"
                @confirm="deleteRepo(item)"
              >
                <a style="color:var(--err)">{{ t('common.delete') }}</a>
              </a-popconfirm>
              <span v-if="item.is_official" class="text-disabled">{{ t('skillHub.notDeletable') }}</span>
            </template>
          </a-list-item>
        </template>
      </a-list>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getLocale, type LocaleKey } from '@/i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import {
  listHubRepos, createHubRepo, updateHubRepo, deleteHubRepo, refreshHubRepo,
  listHubCategories, listHubSkills, installHubSkill,
  type HubRepo, type HubCategory, type HubSkillItem,
} from '@/api/skillHub'

const emit = defineEmits<{
  (e: 'install'): void
}>()

const { t } = useI18n()

// ── 技能仓库状态 ─────────────────────────────────────────────────────────────
const hubRepos = ref<HubRepo[]>([])
const hubReposLoading = ref(false)
const hubActiveRepoId = ref<number | null>(null)
const hubRefreshing = ref(false)
const hubCategories = ref<HubCategory[]>([])
const hubActiveCat = ref('')
const hubKeyword = ref('')
const hubSkills = ref<HubSkillItem[]>([])
const hubLoading = ref(false)
const hubPage = ref(1)
const hubPageSize = ref(20)
const hubSkillTotal = ref(0)

// 仓库管理弹窗
const repoModalVisible = ref(false)
const repoSaving = ref(false)
const repoEditingId = ref<number | null>(null)
const repoForm = ref<{ name: string; url: string; branch: string; is_official: boolean }>({
  name: '', url: '', branch: 'main', is_official: false,
})

const activeRepo = computed(() => hubRepos.value.find(r => r.id === hubActiveRepoId.value) || null)
const isCloudMarket = computed(() => activeRepo.value?.source_type === 'skillhub')

// ── 数据加载 ─────────────────────────────────────────────────────────────────

onMounted(() => {
  loadHubRepos()
})

async function loadHubRepos() {
  hubReposLoading.value = true
  try {
    const repos = await listHubRepos()
    hubRepos.value = repos || []
    if (!hubActiveRepoId.value && hubRepos.value.length) {
      hubActiveRepoId.value = hubRepos.value[0].id
      await loadHubCategoriesAndSkills()
    }
  } catch (e: any) {
    message.error(t('skillHub.loadRepoFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    hubReposLoading.value = false
  }
}

async function loadHubCategoriesAndSkills() {
  if (!hubActiveRepoId.value) return
  hubLoading.value = true
  try {
    const [cats, list] = await Promise.all([
      listHubCategories(hubActiveRepoId.value),
      listHubSkills(hubActiveRepoId.value, {
        category: hubActiveCat.value || undefined,
        q: hubKeyword.value || undefined,
        page: hubPage.value,
        page_size: hubPageSize.value,
      }),
    ])
    hubCategories.value = cats || []
    hubSkills.value = list.items || []
    hubSkillTotal.value = list.total || 0
  } catch (e: any) {
    message.error(t('skillHub.loadSkillsFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    hubLoading.value = false
  }
}

function onHubRepoChange() {
  hubActiveCat.value = ''
  hubPage.value = 1
  loadHubCategoriesAndSkills()
}

function selectHubRepo(id: number) {
  if (hubActiveRepoId.value === id) return
  hubActiveRepoId.value = id
  onHubRepoChange()
}

function selectHubCat(key: string) {
  hubActiveCat.value = key
  hubPage.value = 1
  loadHubCategoriesAndSkills()
}

function loadHubSkills(resetPage: boolean) {
  if (resetPage) hubPage.value = 1
  loadHubCategoriesAndSkills()
}

async function handleRefreshHubRepo() {
  if (!hubActiveRepoId.value) return
  hubRefreshing.value = true
  try {
    await refreshHubRepo(hubActiveRepoId.value)
    message.success(t('skillHub.repoRefreshed'))
    await loadHubCategoriesAndSkills()
  } catch (e: any) {
    message.error(t('skillHub.refreshFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    hubRefreshing.value = false
  }
}

async function handleInstallHubSkill(item: HubSkillItem) {
  if (!hubActiveRepoId.value) return
  item._installing = true
  try {
    const res = await installHubSkill(hubActiveRepoId.value, item.id)
    message.success(t('skillHub.installed', { name: res.name || item.name }))
    emit('install')
  } catch (e: any) {
    message.error(t('skillHub.installFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    item._installing = false
  }
}

// ── 仓库管理弹窗 ─────────────────────────────────────────────────────────────

function openRepoModal() {
  repoEditingId.value = null
  repoForm.value = { name: '', url: '', branch: 'main', is_official: false }
  repoModalVisible.value = true
}

function editRepo(r: HubRepo) {
  repoEditingId.value = r.id
  repoForm.value = { name: r.name, url: r.url, branch: r.branch, is_official: r.is_official }
  repoModalVisible.value = true
}

async function saveRepo() {
  if (!repoForm.value.name.trim() || !repoForm.value.url.trim()) {
    message.warning(t('skillHub.repoFormRequired'))
    return
  }
  repoSaving.value = true
  try {
    if (repoEditingId.value) {
      await updateHubRepo(repoEditingId.value, {
        name: repoForm.value.name,
        url: repoForm.value.url,
        branch: repoForm.value.branch,
      })
    } else {
      await createHubRepo({
        name: repoForm.value.name,
        url: repoForm.value.url,
        branch: repoForm.value.branch,
      })
    }
    message.success(t('skillHub.repoSaved'))
    repoModalVisible.value = false
    await loadHubRepos()
  } catch (e: any) {
    message.error(t('skillHub.saveFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    repoSaving.value = false
  }
}

async function deleteRepo(r: HubRepo) {
  try {
    await deleteHubRepo(r.id)
    message.success(t('skillHub.repoDeleted'))
    if (hubActiveRepoId.value === r.id) {
      hubActiveRepoId.value = null
      hubSkills.value = []
    }
    await loadHubRepos()
  } catch (e: any) {
    message.error(t('skillHub.deleteFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  }
}

// ── 工具 ─────────────────────────────────────────────────────────────────────

// SkillHub 云市场分类多语言映射
const CLOUD_CATEGORY_I18N: Record<string, Partial<Record<LocaleKey, string>>> = {
  'office-efficiency': { 'zh-CN': '办公提效', 'zh-TW': '辦公提效', 'en-US': 'Office Efficiency', 'ja-JP': 'オフィス効率化' },
  'writing': { 'zh-CN': '写作辅助', 'zh-TW': '寫作輔助', 'en-US': 'Writing', 'ja-JP': 'ライティング' },
  'programming': { 'zh-CN': '编程开发', 'zh-TW': '程式開發', 'en-US': 'Programming', 'ja-JP': 'プログラミング' },
  'design': { 'zh-CN': '设计创意', 'zh-TW': '設計創意', 'en-US': 'Design', 'ja-JP': 'デザイン' },
  'research': { 'zh-CN': '科研学术', 'zh-TW': '科研學術', 'en-US': 'Research', 'ja-JP': '研究' },
  'marketing': { 'zh-CN': '营销增长', 'zh-TW': '營銷增長', 'en-US': 'Marketing', 'ja-JP': 'マーケティング' },
  'data-analysis': { 'zh-CN': '数据分析', 'zh-TW': '資料分析', 'en-US': 'Data Analysis', 'ja-JP': 'データ分析' },
  'education': { 'zh-CN': '教育培训', 'zh-TW': '教育培訓', 'en-US': 'Education', 'ja-JP': '教育' },
  'life': { 'zh-CN': '生活助手', 'zh-TW': '生活助手', 'en-US': 'Life Assistant', 'ja-JP': '生活支援' },
  'business': { 'zh-CN': '商业办公', 'zh-TW': '商業辦公', 'en-US': 'Business', 'ja-JP': 'ビジネス' },
  'image': { 'zh-CN': '图像生成', 'zh-TW': '圖像生成', 'en-US': 'Image', 'ja-JP': '画像生成' },
  'video': { 'zh-CN': '视频处理', 'zh-TW': '視頻處理', 'en-US': 'Video', 'ja-JP': '動画' },
  'audio': { 'zh-CN': '音频处理', 'zh-TW': '音頻處理', 'en-US': 'Audio', 'ja-JP': '音声' },
  'translation': { 'zh-CN': '翻译', 'zh-TW': '翻譯', 'en-US': 'Translation', 'ja-JP': '翻訳' },
  'finance': { 'zh-CN': '金融财经', 'zh-TW': '金融財經', 'en-US': 'Finance', 'ja-JP': '金融' },
  'law': { 'zh-CN': '法律', 'zh-TW': '法律', 'en-US': 'Law', 'ja-JP': '法律' },
  'health': { 'zh-CN': '医疗健康', 'zh-TW': '醫療健康', 'en-US': 'Health', 'ja-JP': 'ヘルスケア' },
  'game': { 'zh-CN': '游戏', 'zh-TW': '遊戲', 'en-US': 'Game', 'ja-JP': 'ゲーム' },
  'other': { 'zh-CN': '其他', 'zh-TW': '其他', 'en-US': 'Other', 'ja-JP': 'その他' },
}

function cloudCategoryLabel(c: HubCategory): string {
  const loc = getLocale()
  return CLOUD_CATEGORY_I18N[c.key]?.[loc] || c.name || c.key
}

defineExpose({ openRepoModal })
</script>

<style scoped>
.hub-body {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  min-height: 0;
  padding: 16px;
  overflow: visible;
}

/* 未选择仓库时的空状态居中可见 */
.hub-body > .ant-empty {
  margin: auto;
}

.hub-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

/* 仓库列表：横向一行 Tab */
.hub-repo-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hub-repo-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 16px;
  font-size: 13px;
  color: var(--fg-secondary);
  cursor: pointer;
  background: var(--bg-input);
  transition: all 0.2s;
  white-space: nowrap;
}

.hub-repo-tab:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.hub-repo-tab.active {
  color: var(--fg-inverse);
  background: var(--accent);
  border-color: var(--accent);
}

.hub-repo-tab.active .ant-tag {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
  color: var(--fg-inverse);
}

.hub-repo-name {
  font-weight: 500;
}

.hub-repo-add {
  border-radius: 16px;
}

.hub-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hub-content {
  display: flex;
  gap: 16px;
  align-items: stretch;
  flex: 1 1 auto;
  height: calc(100vh - 56px - 32px - 64px);
  min-height: 0;
  overflow: visible;
}

.hub-cats {
  width: 200px;
  flex-shrink: 0;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  max-height: 100%;
  overflow-y: auto;
}

.hub-cat-item {
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: var(--fg-secondary);
  transition: all 0.2s;
}

.hub-cat-item:hover {
  background: var(--accent-soft);
}

.hub-cat-item.active {
  background: var(--accent);
  color: var(--fg-inverse);
  font-weight: 600;
}

.hub-list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 400px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.hub-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.hub-card {
  background: var(--bg-surface);
}

.hub-card-desc {
  font-size: 12px;
  color: var(--fg-secondary);
  line-height: 1.6;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.hub-card-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.hub-pagination {
  margin-top: 16px;
  text-align: right;
}

.text-disabled {
  color: var(--fg-muted);
  font-size: 12px;
}
</style>
