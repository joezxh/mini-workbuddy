<template>
  <div class="skill-selector">
    <div class="skill-header" @click="toggleExpand">
      <span class="skill-icon">⌨</span>
      <span class="skill-title">技能</span>
      <span v-if="selectedSkill" class="selected-badge">
        {{ selectedSkill.packageName }}
        <span class="selected-remove" @click.stop="clearSelection">×</span>
      </span>
      <span class="expand-icon">{{ isExpanded ? '▼' : '▶' }}</span>
    </div>

    <div v-show="isExpanded" class="skill-content">
      <!-- 文件关联提示（当有 fileId 时显示） -->
      <div v-if="fileId" class="file-context-hint">
        <FileExcelOutlined class="file-icon" />
        <span class="file-name">{{ fileName || '已选择文件' }}</span>
      </div>

      <div v-if="loading" class="skill-loading">
        <a-spin size="small" />
        <span>加载中...</span>
      </div>

      <div v-else-if="error" class="skill-error">
        <span>加载失败</span>
        <a-button type="link" size="small" @click="loadSkills">重试</a-button>
      </div>

      <div v-else-if="!packages.length" class="skill-empty">
        <span>暂无可用技能</span>
      </div>

      <div v-else class="skill-list">
        <!-- 按 category 分组 -->
        <div v-for="(pkgs, cat) in groupedPackages" :key="cat" class="skill-category">
          <div class="cat-header" @click="toggleCat(cat)">
            <span>{{ categoryLabel(cat) }} ({{ pkgs.length }})</span>
            <span class="cat-arrow">{{ collapsedCats.has(cat) ? '▶' : '▼' }}</span>
          </div>
          <div v-show="!collapsedCats.has(cat)" class="cat-packages">
            <!-- 按技能选择：点击包名即选中（后端执行单位本就是整技能） -->
            <div
              v-for="pkg in pkgs"
              :key="pkg.package_id"
              :class="['package-item', { 'package-selected': isPackageSelected(pkg.package_id) }]"
              :title="pkg.description"
              @click="selectPackage(pkg)"
            >
              <span class="package-icon">{{ getPackageIcon(pkg.icon || '') }}</span>
              <span class="package-name">{{ pkg.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { FileExcelOutlined } from '@ant-design/icons-vue'
import {
  getSkills,
  type SkillPackage,
} from '@/api/skill'
import { getDictionaryItems } from '@/api/dictionary'
import type { DictionaryItem } from '@/api/dictionary'

defineProps<{
  fileId?: string
  fileName?: string
  sessionId?: number
}>()

export interface SkillSelectInfo {
  packageId: string
  packageName: string
  packageIcon: string
  /** 按技能执行后不再有脚本粒度，保持字段以兼容父组件链路 */
  scriptId: string
  scriptName: string
  scriptDescription: string
  params?: Record<string, any>
}

const emit = defineEmits<{
  // 事件名保持 script-change，父组件（SessionSidebar → AssistantPanel）链路零改动
  (e: 'script-change', info: SkillSelectInfo | null): void
}>()

// 默认收起
const isExpanded = ref(false)
const loading = ref(false)
const error = ref(false)
const packages = ref<SkillPackage[]>([])
const collapsedCats = ref<Set<string>>(new Set())
const categoryOptions = ref<DictionaryItem[]>([])

// 当前选中的技能包（直接选中，无弹窗）
const selectedSkill = ref<SkillSelectInfo | null>(null)

const groupedPackages = computed(() => {
  const map: Record<string, SkillPackage[]> = {}
  for (const pkg of packages.value) {
    const cat = pkg.category || 'other'
    if (!map[cat]) map[cat] = []
    map[cat].push(pkg)
  }
  return map
})

function categoryLabel(cat?: string) {
  return categoryOptions.value.find(o => o.item_code === cat)?.item_name || cat || '其他'
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function toggleCat(cat: string) {
  if (collapsedCats.value.has(cat)) collapsedCats.value.delete(cat)
  else collapsedCats.value.add(cat)
}

function isPackageSelected(packageId: string): boolean {
  return selectedSkill.value?.packageId === packageId
}

function clearSelection() {
  selectedSkill.value = null
  emit('script-change', null)
}

function getPackageIcon(icon?: string): string {
  const iconMap: Record<string, string> = {
    database: '📊',
    chart: '📈',
    capture: '📸',
    tool: '🔧',
    file: '📄',
    search: '🔍',
    gavel: '⚖️',
    bell: '🔔',
    code: '💻',
  }
  return iconMap[icon || ''] || '🔧'
}

async function loadCategoryOptions() {
  try {
    const res = await getDictionaryItems('skill_category')
    categoryOptions.value = res || []
  } catch (e) {
    console.error('加载类目字典失败:', e)
    categoryOptions.value = []
  }
}

async function loadSkills() {
  loading.value = true
  error.value = false
  try {
    const res = await getSkills()
    packages.value = res.packages || []
    // 默认将所有类别折叠
    const allCats = new Set(packages.value.map(p => p.category || 'other'))
    collapsedCats.value = allCats
  } catch (e) {
    error.value = true
    console.error('Failed to load skills:', e)
  } finally {
    loading.value = false
  }
}

// 选择技能包（整技能）：直接 emit 给父组件，不弹确认窗口。
// 后端执行单位本就是整技能（SkillExecutionService.execute(package_id)），
// 故脚本字段统一置空串。
function selectPackage(pkg: SkillPackage) {
  const info: SkillSelectInfo = {
    packageId: pkg.package_id,
    packageName: pkg.name,
    packageIcon: pkg.icon || 'tool',
    scriptId: '',
    scriptName: '',
    scriptDescription: pkg.description || '',
  }
  selectedSkill.value = info
  emit('script-change', info)
}

onMounted(() => {
  loadCategoryOptions()
  loadSkills()
})
</script>

<style scoped lang="less">
.skill-selector {
  background: transparent;
}

.skill-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 4px;
  cursor: pointer;
  user-select: none;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fg-secondary);

  &:hover {
    color: var(--accent);
  }
}

.skill-icon { font-size: 13px; }
.skill-title { flex: 1; }
.expand-icon { font-size: 10px; color: var(--fg-muted); }

.selected-badge {
  flex: 1;
  font-size: 11px;
  font-weight: 500;
  color: var(--ok);
  background: var(--ok-soft);
  border: 1px solid #b7eb8f;
  border-radius: 10px;
  padding: 1px 8px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.selected-remove {
  cursor: pointer;
  font-size: 13px;
  color: var(--fg-muted);
  line-height: 1;
  &:hover { color: var(--err); }
}

.skill-content {
  padding: 4px 0 2px;
  max-height: 50vh;
  overflow-y: auto;
}

.skill-loading,
.skill-error,
.skill-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 4px;
  font-size: 12px;
  color: var(--fg-secondary);
}

.skill-error { color: var(--err); }

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skill-category {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.cat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px;
  background: var(--bg-input);
  font-size: 11.5px;
  font-weight: 600;
  color: var(--fg-secondary);
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
}

.cat-header:hover {
  background: var(--bg-hover);
  color: var(--fg);
}

.cat-arrow {
  font-size: 9px;
  color: var(--fg-muted);
}

.cat-packages {
  padding: 4px 0;
}

.package-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  cursor: pointer;
  font-size: 11.5px;
  color: var(--fg);
  transition: background 0.15s, color 0.15s;

  &:hover {
    background: var(--accent-soft);
    color: var(--accent);
  }

  &.package-selected {
    background: var(--ok-soft);
    color: var(--ok);
    font-weight: 600;
    border-left: 2px solid var(--ok);
  }
}

.package-icon { font-size: 13px; }

.package-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 600;
}

.file-context-hint {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 6px;
  margin-bottom: 6px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-soft);
  border-radius: 4px;
  font-size: 11px;
  color: var(--accent);
}

.file-icon { font-size: 12px; }
.file-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}


</style>