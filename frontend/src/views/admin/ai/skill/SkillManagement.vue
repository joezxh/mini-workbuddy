<template>
  <div class="skill-management">
    <!-- 顶部工具栏：标题 + 主 Tab 切换 + 操作按钮（单行，不增加高度） -->
    <div class="page-header">
      <div class="header-main">
        <h2 class="page-title">{{ t('skillHub.pageTitle') }}</h2>
        <div class="top-tab-bar">
          <div class="top-tab" :class="{ active: activeMainTab === 'packages' }" @click="activeMainTab = 'packages'">{{ t('skillHub.tabPackages') }}</div>
          <div class="top-tab" :class="{ active: activeMainTab === 'hub' }" @click="activeMainTab = 'hub'">{{ t('skillHub.tabHub') }}</div>
        </div>
      </div>
      <div class="header-actions">
        <template v-if="activeMainTab === 'packages'">
          <a-button @click="handleImport">
            <UploadOutlined /> {{ t('skillHub.importZip') }}
          </a-button>
          <a-button type="primary" @click="openPackageForm()">
            <PlusOutlined /> {{ t('skillHub.newPackage') }}
          </a-button>
        </template>
        <a-button v-else type="primary" @click="hubBrowserRef?.openRepoModal()">
          <PlusOutlined /> {{ t('skillHub.addRepo') }}
        </a-button>
      </div>
    </div>

    <!-- 主内容区：占用剩余高度，内部滚动 -->
    <div class="skill-main">
      <!-- 主 Tab 1: 技能包管理 -->
      <div v-show="activeMainTab === 'packages'" class="management-body">
      <!-- 左侧:包列表 -->
      <div class="left-panel">
        <div class="search-box">
          <a-input-search
            v-model:value="keyword"
            :placeholder="t('skillHub.searchPackage')"
            allow-clear
            @search="loadPackages"
          />
        </div>

        <a-spin v-if="loading" class="loading-wrap" />
        <div v-else-if="!groupedPackages.size" class="empty-hint">
          {{ t('skillHub.noPackages') }}
        </div>
        <div v-else class="package-list">
          <div
            v-for="[cat, pkgs] in groupedPackages"
            :key="cat"
            class="category-group"
          >
            <div class="cat-header" @click="toggleCat(cat)">
              <span>{{ t('skillHub.groupCount', { name: categoryLabel(cat), count: pkgs.length }) }}</span>
              <DownOutlined v-if="collapsedCats.has(cat)" />
              <UpOutlined v-else />
            </div>
            <div v-show="!collapsedCats.has(cat)" class="cat-packages">
              <div
                v-for="pkg in pkgs"
                :key="pkg.package_id"
                class="package-item"
                :class="{ active: selected?.package_id === pkg.package_id }"
                @click="selectPackage(pkg)"
              >
                <span class="pkg-icon">{{ iconLabel(pkg.icon) }}</span>
                <span class="pkg-name">{{ pkg.name }}</span>
                <a-tag v-if="!pkg.enabled" color="default" size="small">{{ t('skillHub.disabled') }}</a-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧:包详情 + 触发规则 Tabs -->
      <div class="right-panel">
        <div v-if="!selected" class="detail-placeholder">
          <span>{{ t('skillHub.selectPackageHint') }}</span>
        </div>
        <div v-else class="detail-content">
          <!-- 包头部信息 -->
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-icon">{{ iconLabel(selected.icon) }}</span>
              <span>{{ selected.name }}</span>
            </div>
            <div class="detail-actions">
              <a-button size="small" @click="openPackageForm(selected)">{{ t('common.edit') }}</a-button>
              <a-button size="small" @click="toggleEnabled(selected)">
                {{ selected.enabled ? t('skillHub.disabled') : t('skillHub.enabled') }}
              </a-button>
              <a-button size="small" @click="handleExport(selected)">{{ t('skillHub.export') }}</a-button>
              <a-popconfirm :title="t('skillHub.deletePackageConfirm')" @confirm="handleDelete(selected)">
                <a-button size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </div>

          <!-- Tabs: 包详情 / 触发规则 -->
          <a-tabs v-model:activeKey="activeTab" class="detail-tabs">
            <!-- Tab 1: 包详情 -->
            <a-tab-pane key="detail" :tab="t('skillHub.tabDetail')">
              <a-descriptions :column="2" size="small" class="detail-meta">
                <a-descriptions-item :label="t('skillHub.pkgId')">{{ selected.package_id }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.category')">{{ categoryLabel(selected.category) }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.version')">{{ selected.version }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.status')">
                  <a-tag :color="selected.enabled ? 'green' : 'default'">
                    {{ selected.enabled ? t('skillHub.enabled') : t('skillHub.disabled') }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.path')">{{ selected.file_path }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.createdAt')">{{ selected.created_at }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.description')" :span="2">{{ selected.description || '—' }}</a-descriptions-item>
              </a-descriptions>

              <a-divider>
                {{ t('skillHub.fileList') }}
                <span class="file-count-hint">{{ t('skillHub.fileCount', { count: fileRows.length }) }}</span>
              </a-divider>

              <a-spin :spinning="filesLoading">
                <div class="script-list">
                  <div v-if="!fileRows.length" class="script-empty">
                    {{ t('skillHub.noFiles') }}
                  </div>
                  <div
                    v-for="row in fileRows"
                    :key="row.file.path"
                    class="script-item file-item"
                    @click="openFilePreview(row.file)"
                  >
                    <div class="script-info">
                      <div class="script-name">
                        <span :class="{ 'text-disabled': row.script && !row.script.enabled }">{{ row.file.path }}</span>
                        <a-tag :color="fileTypeColor(row.file.type)" size="small">{{ fileTypeLabel(row.file.type) }}</a-tag>
                        <a-tag v-if="row.script && !row.script.enabled" color="default" size="small">{{ t('skillHub.disabled') }}</a-tag>
                      </div>
                      <div class="script-cmd">{{ formatSize(row.file.size) }}</div>
                      <div v-if="row.script?.description" class="script-desc">{{ row.script.description }}</div>
                    </div>
                    <div v-if="row.script" class="script-actions" @click.stop>
                      <a-switch
                        :checked="row.script.enabled"
                        size="small"
                        @change="(v: boolean) => onScriptToggle(row, v)"
                      />
                      <a-button size="small" type="text" @click="onScriptEdit(row)">{{ t('common.edit') }}</a-button>
                      <a-popconfirm :title="t('skillHub.deleteScriptConfirm')" @confirm="onScriptDelete(row)">
                        <a-button size="small" type="text" danger>{{ t('common.delete') }}</a-button>
                      </a-popconfirm>
                    </div>
                  </div>
                </div>
              </a-spin>

              <div class="script-footer">
                <a-button type="dashed" @click="openScriptForm()">
                  <PlusOutlined /> {{ t('skillHub.newScript') }}
                </a-button>
              </div>
            </a-tab-pane>

            <!-- Tab 2: 触发规则 -->
            <a-tab-pane key="rules" :tab="t('skillHub.tabRules')">
              <div class="rules-toolbar">
                <a-button type="primary" size="small" @click="openCreateRule">
                  <PlusOutlined /> {{ t('skillHub.newRule') }}
                </a-button>
                <a-button size="small" @click="loadRules">
                  <ReloadOutlined :spin="rulesLoading" /> {{ t('skillHub.refresh') }}
                </a-button>
              </div>

              <a-spin :spinning="rulesLoading">
                <a-table
                  :columns="ruleColumns"
                  :data-source="rules"
                  :pagination="false"
                  row-key="id"
                  size="small"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'is_active'">
                      <a-switch
                        :checked="record.is_active"
                        @change="(val: boolean) => toggleRuleActive(record, val)"
                        size="small"
                      />
                    </template>
                    <template v-else-if="column.key === 'priority'">
                      <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'conditions'">
                      <a-tooltip :title="formatConditions(record.conditions)">
                        <code class="conditions-preview">{{ truncate(formatConditions(record.conditions), 60) }}</code>
                      </a-tooltip>
                    </template>
                    <template v-else-if="column.key === 'action'">
                      <a-space>
                        <a-button type="link" size="small" @click="openEditRule(record)">
                          <EditOutlined /> {{ t('common.edit') }}
                        </a-button>
                        <a-popconfirm
                          :title="t('skillHub.deleteRuleConfirm')"
                          :ok-text="t('common.confirm')"
                          :cancel-text="t('common.cancel')"
                          @confirm="handleDeleteRule(record)"
                        >
                          <a-button type="link" size="small" danger>
                            <DeleteOutlined /> {{ t('common.delete') }}
                          </a-button>
                        </a-popconfirm>
                      </a-space>
                    </template>
                  </template>
                </a-table>
                <a-empty v-if="!rulesLoading && rules.length === 0" :description="t('skillHub.noRules')" />
              </a-spin>
            </a-tab-pane>

            <!-- Tab 3: SKILL.md 文档 -->
            <a-tab-pane key="markdown" tab="SKILL.md">
              <div class="markdown-toolbar">
                <a-space v-if="!markdownEditing">
                  <a-button size="small" type="primary" @click="startEditMarkdown">
                    <EditOutlined /> {{ t('common.edit') }}
                  </a-button>
                  <a-button size="small" @click="loadMarkdown">
                    <ReloadOutlined :spin="markdownLoading" /> {{ t('skillHub.refresh') }}
                  </a-button>
                </a-space>
                <a-space v-else>
                  <a-button size="small" type="primary" :loading="markdownSaving" @click="saveMarkdown">
                    {{ t('common.save') }}
                  </a-button>
                  <a-button size="small" :disabled="markdownSaving" @click="cancelEditMarkdown">
                    {{ t('common.cancel') }}
                  </a-button>
                </a-space>
                <span v-if="markdownSource" class="markdown-source-tag">
                  {{ t('skillHub.source') }}：{{ markdownSourceLabel }}
                </span>
              </div>
              <div class="markdown-container">
                <a-spin :spinning="markdownLoading">
                  <div v-if="markdownError" class="markdown-error">
                    <a-empty :description="markdownError" />
                  </div>
                  <a-textarea
                    v-else-if="markdownEditing"
                    v-model:value="markdownDraft"
                    class="markdown-editor"
                    :placeholder="t('skillHub.markdownPlaceholder')"
                    :auto-size="{ minRows: 18, maxRows: 36 }"
                  />
                  <pre v-else-if="markdownContent" class="markdown-pre">{{ markdownContent }}</pre>
                  <a-empty v-else-if="!markdownLoading" :description="t('skillHub.markdownEmpty')" />
                </a-spin>
              </div>
            </a-tab-pane>

            <!-- Tab 4: 进化配置 -->
            <a-tab-pane key="evolution" :tab="t('skillHub.tabEvolution')">
              <SkillEvolutionPanel ref="evoPanelRef" :package-id="selected?.package_id || ''" />
            </a-tab-pane>

            <!-- Tab 5: 对话记录 -->
            <a-tab-pane key="conversations" :tab="t('skillHub.tabConversations')">
              <SkillConversationsPanel
                ref="convoPanelRef"
                :package-id="selected?.package_id || ''"
                :active="activeTab === 'conversations'"
              />
            </a-tab-pane>
          </a-tabs>
        </div>
      </div>
      </div>

      <!-- 主 Tab 2: 技能仓库 -->
      <SkillHubBrowser ref="hubBrowserRef" v-show="activeMainTab === 'hub'" @install="loadPackages" />
    </div>
  </div>

    <!-- 弹窗 -->
    <SkillPackageForm ref="pkgFormRef" @success="loadPackages" />
    <SkillScriptForm
      ref="scrFormRef"
      :package-id="selected?.package_id || ''"
      @success="reloadSelected"
    />
    <SkillRuleFormModal
      v-model:visible="ruleFormVisible"
      :rule-id="editingRule?.id"
      :rule-data="editingRule"
      @success="handleRuleFormSuccess"
    />

    <!-- 文件预览弹窗 -->
    <a-modal
      v-model:open="previewVisible"
      :title="previewPath"
      width="820px"
      :footer="null"
    >
      <a-spin :spinning="previewLoading">
        <a-alert v-if="previewError" type="error" show-icon :message="previewError" />
        <pre v-else class="file-preview-pre">{{ previewContent }}</pre>
      </a-spin>
    </a-modal>

    <!-- 隐藏的上传 input -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".zip"
      style="display:none"
      @change="onFileSelected"
    />

</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import {
  PlusOutlined, UploadOutlined, DownOutlined, UpOutlined,
  ReloadOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons-vue'
import {
  getSkills, deleteSkillPackage, updateSkillPackage,
  deleteScript as apiDeleteScript, updateScript, importSkillPackage, exportSkillPackage,
  getSkillMarkdown, saveSkillMarkdown, ICON_OPTIONS,
  getSkillFiles, getSkillFileContent,
} from '@/api/skill'
import { getDictionaryItems } from '@/api/dictionary'
import type { DictionaryItem } from '@/api/dictionary'
import type { SkillPackage, SkillScript, SkillFileItem, SkillFileType } from '@/api/skill'
import {
  getSkillRules, updateSkillRule, deleteSkillRule,
  type SkillRule,
} from '@/api/skillRule'
import SkillPackageForm from './components/SkillPackageForm.vue'
import SkillScriptForm from './components/SkillScriptForm.vue'
import SkillRuleFormModal from './components/SkillRuleFormModal.vue'
import SkillHubBrowser from './components/SkillHubBrowser.vue'
import SkillEvolutionPanel from './components/SkillEvolutionPanel.vue'
import SkillConversationsPanel from './components/SkillConversationsPanel.vue'

const route = useRoute()
const { t } = useI18n()
const loading = ref(false)
const packages = ref<SkillPackage[]>([])
const selected = ref<SkillPackage | null>(null)
const keyword = ref('')
const collapsedCats = ref<Set<string>>(new Set())
const pkgFormRef = ref()
const scrFormRef = ref()
const fileInputRef = ref<HTMLInputElement>()
const categoryOptions = ref<DictionaryItem[]>([])
const activeTab = ref('detail')
const activeMainTab = ref('hub')
const hubBrowserRef = ref()
const evoPanelRef = ref()
const convoPanelRef = ref()

// ── 触发规则相关 ──────────────────────────────────────────────────────────────
const rules = ref<SkillRule[]>([])
const rulesLoading = ref(false)
const ruleFormVisible = ref(false)
const editingRule = ref<SkillRule | null>(null)

// ── SKILL.md 相关 ─────────────────────────────────────────────────────────────
const markdownContent = ref('')
const markdownLoading = ref(false)
const markdownError = ref('')
const markdownEditing = ref(false)
const markdownSaving = ref(false)
const markdownDraft = ref('')

// ── 文件树相关（磁盘扫描，只读预览）────────────────────────────────────────
interface FileRow {
  file: SkillFileItem
  /** 该文件对应 ai_skill_script 记录（仅 scripts/<script_id>.py 可匹配） */
  script: SkillScript | null
}
const files = ref<SkillFileItem[]>([])
const filesLoading = ref(false)
const previewVisible = ref(false)
const previewPath = ref('')
const previewContent = ref('')
const previewError = ref('')
const previewLoading = ref(false)
// 来源标记：db=数据库优先 / workspace=工作区 / file=文件系统
const markdownSource = ref('')
const markdownSourceLabel = computed(() => {
  switch (markdownSource.value) {
    case 'db': return t('skillHub.srcDb')
    case 'workspace': return t('skillHub.srcWorkspace')
    case 'file': return t('skillHub.srcFile')
    default: return ''
  }
})

function startEditMarkdown() {
  markdownDraft.value = markdownContent.value || ''
  markdownEditing.value = true
}

function cancelEditMarkdown() {
  markdownEditing.value = false
  markdownDraft.value = ''
}

async function saveMarkdown() {
  if (!selected.value) return
  markdownSaving.value = true
  try {
    await saveSkillMarkdown(selected.value.package_id, markdownDraft.value)
    markdownContent.value = markdownDraft.value
    if (selected.value) {
      selected.value.skill_markdown = markdownDraft.value
    }
    markdownEditing.value = false
    markdownDraft.value = ''
    message.success(t('skillHub.savedMarkdown'))
  } catch (e: any) {
    message.error(t('skillHub.saveFailed') + (e?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    markdownSaving.value = false
  }
}

const ruleColumns = [
  { title: t('skillHub.ruleName'), dataIndex: 'name', key: 'name', width: 180 },
  { title: t('skillHub.ruleAgent'), dataIndex: 'agent_name', key: 'agent_name', width: 150 },
  { title: t('skillHub.rulePriority'), dataIndex: 'priority', key: 'priority', width: 80 },
  { title: t('skillHub.ruleConditions'), key: 'conditions', width: 240 },
  { title: t('skillHub.ruleStatus'), key: 'is_active', width: 80 },
  { title: t('skillHub.ruleAction'), key: 'action', width: 150, fixed: 'right' as const },
]

// ── 数据加载 ─────────────────────────────────────────────────────────────────

async function loadCategoryOptions() {
  try {
    const res = await getDictionaryItems('skill_category')
    categoryOptions.value = res || []
  } catch (e) {
    console.error('加载类目字典失败:', e)
    categoryOptions.value = []
  }
}

async function loadPackages() {
  loading.value = true
  try {
    const res = await getSkills()
    packages.value = res?.packages || []
    if (selected.value) {
      const updated = packages.value.find(p => p.package_id === selected.value!.package_id)
      selected.value = updated || null
    }
  } catch (e: any) {
    message.error(t('skillHub.loadFailed') + (e?.data?.detail || e?.message || String(e)))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCategoryOptions()
  loadPackages()
})

// 根据 package_id 自动选中技能包（从外部跳转过来时）
function selectPackageById(packageId: string) {
  const pkg = packages.value.find(p => p.package_id === packageId)
  if (pkg) {
    selectPackage(pkg)
  }
}

// 监听路由 query 参数变化，自动定位到对应技能包
watch(
  () => route.query.package_id,
  (packageId) => {
    if (packageId && typeof packageId === 'string') {
      // 如果包列表已加载，直接选中；否则等加载完成后选中
      if (packages.value.length > 0) {
        selectPackageById(packageId)
      }
    }
  },
)

// 包列表加载完成后，检查路由中是否有 package_id 参数
watch(
  () => packages.value,
  (pkgs) => {
    if (pkgs.length > 0) {
      const packageId = route.query.package_id
      if (packageId && typeof packageId === 'string') {
        selectPackageById(packageId)
      }
    }
  },
)

async function loadRules() {
  if (!selected.value) return
  rulesLoading.value = true
  try {
    const res = await getSkillRules({
      page: 1,
      page_size: 100,
      package_id: selected.value.package_id,
    }) as any
    rules.value = res.items || []
  } catch (e: any) {
    message.error(t('skillHub.loadRulesFailed') + (e.message || t('skillHub.unknownError')))
  } finally {
    rulesLoading.value = false
  }
}

async function loadMarkdown() {
  if (!selected.value) return
  markdownLoading.value = true
  markdownError.value = ''
  markdownContent.value = ''
  try {
    const res = await getSkillMarkdown(selected.value.package_id)
    markdownContent.value = res.content || ''
    // 来源标记：若数据库已保存 skill_markdown 则优先标记为数据库
    markdownSource.value = selected.value?.skill_markdown ? 'db' : 'file'
  } catch (e: any) {
    if (e?.data?.detail?.includes('不存在')) {
      markdownError.value = t('skillHub.markdownMissing')
    } else {
      markdownError.value = t('skillHub.readFailed') + (e?.data?.detail || e?.message || t('skillHub.unknownError'))
    }
  } finally {
    markdownLoading.value = false
  }
}

// ── 文件树加载 / 预览 ───────────────────────────────────────────────────────

/** 文件行与 ai_skill_script 记录合并：scripts/<script_id>.py 视为可管理脚本行 */
const fileRows = computed<FileRow[]>(() => {
  const scripts = selected.value?.scripts || []
  return files.value.map(file => ({
    file,
    script: scripts.find(s => `scripts/${s.script_id}.py` === file.path) || null,
  }))
})

async function loadFiles() {
  if (!selected.value) {
    files.value = []
    return
  }
  filesLoading.value = true
  try {
    const res = await getSkillFiles(selected.value.package_id)
    files.value = res.files || []
  } catch (e: any) {
    files.value = []
    message.error(t('skillHub.loadFilesFailed') + (e?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    filesLoading.value = false
  }
}

async function openFilePreview(file: SkillFileItem) {
  if (!selected.value) return
  previewPath.value = file.path
  previewContent.value = ''
  previewError.value = ''
  previewVisible.value = true
  previewLoading.value = true
  try {
    const res = await getSkillFileContent(selected.value.package_id, file.path)
    previewContent.value = res.content
  } catch (e: any) {
    previewError.value = e?.data?.detail || e?.message || t('skillHub.unknownError')
  } finally {
    previewLoading.value = false
  }
}

function fileTypeLabel(type: SkillFileType): string {
  if (type === 'script') return t('skillHub.fileTypeScript')
  if (type === 'reference') return t('skillHub.fileTypeReference')
  return t('skillHub.fileTypeOther')
}

function fileTypeColor(type: SkillFileType): string {
  if (type === 'script') return 'blue'
  if (type === 'reference') return 'green'
  return 'default'
}

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// 脚本行操作（数据仍来自 ai_skill_script）
function onScriptToggle(row: FileRow, enabled: boolean) {
  if (row.script) toggleScriptEnabled(row.script, enabled)
}

function onScriptEdit(row: FileRow) {
  if (row.script) openScriptForm(row.script)
}

function onScriptDelete(row: FileRow) {
  if (row.script) handleDeleteScript(row.script)
}

// ── 过滤与分组 ──────────────────────────────────────────────────────────────

const filteredPackages = computed(() => {
  if (!keyword.value) return packages.value
  const k = keyword.value.toLowerCase()
  return packages.value.filter(p =>
    p.name.toLowerCase().includes(k) || p.package_id.includes(k)
  )
})

const groupedPackages = computed(() => {
  const map = new Map<string, SkillPackage[]>()
  for (const pkg of filteredPackages.value) {
    const cat = pkg.category || 'other'
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(pkg)
  }
  return map
})

// ── 交互 ─────────────────────────────────────────────────────────────────────

function toggleCat(cat: string) {
  if (collapsedCats.value.has(cat)) collapsedCats.value.delete(cat)
  else collapsedCats.value.add(cat)
}

function selectPackage(pkg: SkillPackage) {
  selected.value = pkg
  activeTab.value = 'detail'
}

// 切换包时自动加载规则 / SKILL.md / 文件树
watch(() => selected.value?.package_id, () => {
  if (selected.value) {
    loadRules()
    loadMarkdown()
    loadFiles()
  } else {
    rules.value = []
    markdownContent.value = ''
    markdownError.value = ''
    files.value = []
  }
})

async function reloadSelected() {
  if (!selected.value) return
  try {
    const res = await getSkills()
    const updated = (res?.packages || []).find((p: SkillPackage) => p.package_id === selected.value!.package_id)
    selected.value = updated || null
  } catch { /* ignore */ }
  await loadFiles()
}

async function toggleEnabled(pkg: SkillPackage) {
  try {
    await updateSkillPackage(pkg.package_id, { enabled: !pkg.enabled })
    pkg.enabled = !pkg.enabled
    if (selected.value?.package_id === pkg.package_id) {
      selected.value = { ...selected.value }
    }
    message.success(pkg.enabled ? t('skillHub.enabled') : t('skillHub.disabled'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.opFailed'))
  }
}

async function toggleScriptEnabled(s: SkillScript, enabled: boolean) {
  if (!selected.value) return
  try {
    await updateScript(selected.value.package_id, s.script_id, { enabled })
    s.enabled = enabled
    selected.value = { ...selected.value }
    message.success(enabled ? t('skillHub.enabled') : t('skillHub.disabled'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.opFailed'))
  }
}

async function handleDelete(pkg: SkillPackage) {
  try {
    await deleteSkillPackage(pkg.package_id)
    if (selected.value?.package_id === pkg.package_id) selected.value = null
    await loadPackages()
    message.success(t('skillHub.deleted'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.deleteFailed'))
  }
}

async function handleDeleteScript(s: SkillScript) {
  if (!selected.value) return
  try {
    await apiDeleteScript(selected.value.package_id, s.script_id)
    selected.value.scripts = (selected.value.scripts || []).filter(
      x => x.script_id !== s.script_id
    )
    await loadFiles()
    message.success(t('skillHub.deleted'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.deleteFailed'))
  }
}

function openPackageForm(pkg?: SkillPackage) {
  pkgFormRef.value?.open(pkg)
}

function openScriptForm(s?: SkillScript) {
  scrFormRef.value?.open(s)
}

// ── 触发规则操作 ──────────────────────────────────────────────────────────────

function openCreateRule() {
  editingRule.value = null
  ruleFormVisible.value = true
}

function openEditRule(record: SkillRule) {
  editingRule.value = record
  ruleFormVisible.value = true
}

async function toggleRuleActive(record: SkillRule, val: boolean) {
  try {
    await updateSkillRule(record.id, { is_active: val })
    record.is_active = val
    message.success(val ? t('skillHub.enabled') : t('skillHub.disabled'))
  } catch (e: any) {
    message.error(t('skillHub.updateFailed') + (e.message || t('skillHub.unknownError')))
  }
}

async function handleDeleteRule(record: SkillRule) {
  try {
    await deleteSkillRule(record.id)
    message.success(t('skillHub.deleted'))
    loadRules()
  } catch (e: any) {
    message.error(t('skillHub.deleteFailed') + (e.message || t('skillHub.unknownError')))
  }
}

function handleRuleFormSuccess() {
  ruleFormVisible.value = false
  loadRules()
}

function priorityColor(p: number): string {
  if (p <= 10) return 'red'
  if (p <= 50) return 'orange'
  if (p <= 100) return 'blue'
  return 'default'
}

function formatConditions(c: any): string {
  if (!c) return t('skillMgmt.noConditions')
  return JSON.stringify(c, null, 2)
}

function truncate(s: string, n: number): string {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '...' : s
}

// ── 导入/导出 ────────────────────────────────────────────────────────────────

function handleImport() {
  fileInputRef.value?.click()
}

function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)

  Modal.confirm({
    title: t('skillHub.importConfirmTitle'),
    content: t('skillHub.importConfirm', { name: file.name }),
    okText: t('skillHub.import'),
    onOk: async () => {
      try {
        const res = await importSkillPackage(file)
        const d = res.data
        message.success(t('skillHub.importSuccess', { name: d.name, count: d.scripts_count }))
        await loadPackages()
        const newly = packages.value.find(p => p.package_id === d.package_id)
        if (newly) selectPackage(newly)
      } catch (e: any) {
        message.error(e?.data?.detail || t('skillHub.importFailed'))
      }
    },
  })

  ;(e.target as HTMLInputElement).value = ''
}

async function handleExport(pkg: SkillPackage) {
  try {
    const blob = await exportSkillPackage(pkg.package_id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${pkg.package_id}.zip`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('skillHub.exportSuccess'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.exportFailed'))
  }
}

function categoryLabel(cat?: string) {
  if (!cat) return t('skillMgmt.other')
  // 官方仓库分类：优先走 i18n（officialCategories / cloudCategories），回退到字典 item_name
  const officialKey = `skillHub.officialCategories.${cat}`
  const official = t(officialKey)
  if (official !== officialKey) return official
  const cloudKey = `skillHub.cloudCategories.${cat}`
  const cloud = t(cloudKey)
  if (cloud !== cloudKey) return cloud
  return categoryOptions.value.find(o => o.item_code === cat)?.item_name || cat
}

function iconLabel(icon?: string) {
  return ICON_OPTIONS.find(o => o.value === icon)?.label || '📦'
}
</script>

<style scoped>
.skill-management {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  height: 100vh;
  background: var(--bg-input);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.header-main {
  display: flex;
  align-items: center;
  gap: 24px;
  height: 100%;
}

.page-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

/* 顶部主 Tab 切换（位于标题栏，单行） */
.top-tab-bar {
  display: flex;
  align-items: stretch;
  height: 100%;
}

.top-tab {
  display: flex;
  align-items: center;
  padding: 0 4px;
  margin-right: 20px;
  font-size: 14px;
  color: var(--fg-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.top-tab:hover {
  color: var(--accent);
}

.top-tab.active {
  color: var(--accent);
  font-weight: 600;
  border-bottom-color: var(--accent);
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: nowrap;
  white-space: nowrap;
}

/* 主内容区：占用标题栏以下全部高度，内部各自滚动 */
.skill-main {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.management-body {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  overflow: visible;
}

/* 左侧 */
.left-panel {
  width: 280px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-box {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.loading-wrap {
  margin: 24px auto;
  display: block;
}

.empty-hint {
  padding: 24px;
  text-align: center;
  color: var(--fg-muted);
  font-size: 13px;
}

.package-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.category-group {
  margin-bottom: 4px;
}

.cat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-secondary);
  cursor: pointer;
  user-select: none;
}

.cat-header:hover {
  background: var(--bg-input);
}

.cat-packages {
  padding: 0;
}

.package-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px 7px 20px;
  cursor: pointer;
  font-size: 13px;
  color: var(--fg);
  border-radius: 0;
}

.package-item:hover {
  background: var(--accent-soft);
}

.package-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-right: 2px solid var(--accent);
}

.pkg-icon {
  font-size: 14px;
}

.pkg-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 右侧 */
.right-panel {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-input);
}

.detail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--fg-muted);
  font-size: 14px;
}

.detail-content {
  padding: 20px 24px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.detail-icon {
  font-size: 20px;
}

.detail-actions {
  display: flex;
  gap: 6px;
}

.detail-meta {
  background: var(--bg-surface);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 16px;
}

.detail-tabs {
  margin-top: 8px;
}

/* 触发规则 Tab */
.rules-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.conditions-preview {
  font-family: monospace;
  font-size: 12px;
  background: var(--bg-input);
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--fg);
}

.script-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.script-empty {
  text-align: center;
  color: var(--fg-muted);
  padding: 16px;
  background: var(--bg-surface);
  border-radius: 6px;
}

.script-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-surface);
  border-radius: 6px;
  border: 1px solid var(--border);
  gap: 12px;
}

.script-info {
  flex: 1;
  min-width: 0;
}

.script-name {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.script-name .text-disabled {
  color: var(--fg-muted);
  text-decoration: line-through;
}

.script-cmd {
  font-size: 12px;
  color: var(--fg-secondary);
  font-family: monospace;
  margin-top: 2px;
}

.script-desc {
  font-size: 12px;
  color: var(--fg-secondary);
  margin-top: 2px;
}

.script-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.script-footer {
  margin-top: 12px;
}

/* 文件列表 */
.file-count-hint {
  margin-left: 8px;
  font-size: 12px;
  color: var(--fg-muted);
  font-weight: 400;
}

.file-item {
  cursor: pointer;
}

.file-item:hover {
  border-color: var(--accent);
}

/* 文件预览 */
.file-preview-pre {
  margin: 0;
  padding: 12px;
  max-height: 60vh;
  overflow: auto;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--fg);
}

/* SKILL.md Tab */
.markdown-container {
  background: var(--bg-surface);
  border-radius: 6px;
  border: 1px solid var(--border);
  min-height: 300px;
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}

.markdown-pre {
  margin: 0;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--fg);
}

.markdown-error {
  padding: 24px;
}

.markdown-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-input);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.markdown-source-tag {
  font-size: 12px;
  color: var(--fg-secondary);
}

.markdown-editor {
  margin: 12px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

</style>
