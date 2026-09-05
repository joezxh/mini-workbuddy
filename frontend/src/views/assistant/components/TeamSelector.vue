<template>
  <div class="skill-selector team-selector">
    <div class="skill-header" @click="toggleExpand">
      <span class="skill-icon">👥</span>
      <span class="skill-title">专家团</span>
      <span v-if="selectedTeam" class="selected-badge">
        {{ selectedTeam.name }}
        <span class="selected-remove" @click.stop="clearSelection">×</span>
      </span>
      <span class="expand-icon">{{ isExpanded ? '▼' : '▶' }}</span>
    </div>

    <div v-show="isExpanded" class="skill-content">
      <div v-if="loading" class="skill-loading">
        <a-spin size="small" />
        <span>加载中...</span>
      </div>

      <div v-else-if="error" class="skill-error">
        <span>{{ error }}</span>
        <a-button type="link" size="small" @click="loadTeams">重试</a-button>
      </div>

      <div v-else-if="!allTeams.length" class="skill-empty">
        <span>暂无可用专家团</span>
      </div>

      <div v-else class="skill-list">
        <div
          v-for="(teams, cat) in grouped"
          :key="cat"
          class="skill-category"
        >
          <div class="cat-header" @click="toggleCat(cat)">
            <span>{{ categoryLabel(cat) }} ({{ teams.length }})</span>
            <span class="cat-arrow">{{ collapsedCats.has(cat) ? '▶' : '▼' }}</span>
          </div>
          <div v-show="!collapsedCats.has(cat)" class="cat-packages">
            <div
              v-for="team in teams"
              :key="team.id"
              :class="['script-item', { 'script-selected': isSelected(team.id) }]"
              :title="team.description || team.team_code"
              @click="selectTeam(team)"
            >
              <span class="script-name">{{ team.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { listTeams, type TeamOut } from '@/api/agentTeam'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'

export interface TeamSelectInfo {
  id: number
  code: string
  name: string
  category?: string | null
}

const props = defineProps<{
  /** 当前选中的专家团 id（用于高亮，由父组件回传） */
  selectedId?: number | null
}>()

const emit = defineEmits<{
  (e: 'team-change', info: TeamSelectInfo | null): void
}>()

const isExpanded = ref(false)
const loading = ref(false)
const error = ref('')
const allTeams = ref<TeamOut[]>([])
const collapsedCats = ref<Set<string>>(new Set())
const categoryOptions = ref<DictionaryItem[]>([])

function categoryLabel(cat?: string) {
  return categoryOptions.value.find(o => o.item_code === cat)?.item_name || cat || '其他'
}

async function loadCategoryOptions() {
  try {
    const res = await getDictionaryItems('agent_team_category')
    categoryOptions.value = res || []
  } catch (e) {
    console.error('加载专家团类目字典失败:', e)
    categoryOptions.value = []
  }
}

const grouped = computed<Record<string, TeamOut[]>>(() => {
  const map: Record<string, TeamOut[]> = {}
  for (const t of allTeams.value) {
    const cat = t.category || '其他'
    if (!map[cat]) map[cat] = []
    map[cat].push(t)
  }
  return map
})

const selectedTeam = computed<TeamSelectInfo | null>(() => {
  if (props.selectedId == null) return null
  const t = allTeams.value.find((x) => x.id === props.selectedId)
  if (!t) return null
  return { id: t.id, code: t.team_code, name: t.name || t.team_name || '', category: t.category }
})

function isSelected(id: number): boolean {
  return props.selectedId === id
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function toggleCat(cat: string) {
  if (collapsedCats.value.has(cat)) collapsedCats.value.delete(cat)
  else collapsedCats.value.add(cat)
}

function selectTeam(team: TeamOut) {
  const info: TeamSelectInfo = {
    id: team.id,
    code: team.team_code,
    name: team.name || team.team_name || '',
    category: team.category,
  }
  emit('team-change', info)
}

function clearSelection() {
  emit('team-change', null)
}

async function loadTeams() {
  loading.value = true
  error.value = ''
  try {
    const teams = await listTeams()
    allTeams.value = teams || []
    collapsedCats.value = new Set(Object.keys(grouped.value))
  } catch (e: any) {
    error.value = e?.message || '加载专家团失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCategoryOptions()
  loadTeams()
})
</script>

<!--
  以下样式与 SkillSelector.vue 完全一致（scoped 样式无法跨组件复用，
  故在此完整复制，确保专家团分类的字体、间距、对齐、箭头、选中态等与技能完全统一）。
-->
<style scoped lang="less">
.team-selector {
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

.script-list {
  display: flex;
  flex-direction: column;
  padding: 2px 0;
}

.script-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  cursor: pointer;
  font-size: 11.5px;
  color: var(--fg);
  transition: background 0.15s, color 0.15s;

  &:hover {
    background: var(--accent-soft);
    color: var(--accent);
  }

  &.script-selected {
    background: var(--ok-soft);
    color: var(--ok);
    font-weight: 600;
    border-left: 2px solid var(--ok);
  }
}

.script-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
