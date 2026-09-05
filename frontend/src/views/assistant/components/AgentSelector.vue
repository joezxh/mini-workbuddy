<template>
  <div class="skill-selector agent-selector">
    <div class="skill-header" @click="toggleExpand">
      <span class="skill-icon">👤</span>
      <span class="skill-title">专家</span>
      <span v-if="selectedAgent" class="selected-badge">
        {{ selectedAgent.name }}
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
        <a-button type="link" size="small" @click="loadAgents">重试</a-button>
      </div>

      <div v-else-if="!allAgents.length" class="skill-empty">
        <span>暂无可用专家</span>
      </div>

      <div v-else class="skill-list">
        <div
          v-for="(agents, cat) in grouped"
          :key="cat"
          class="skill-category"
        >
          <div class="cat-header" @click="toggleCat(cat)">
            <span>{{ categoryLabel(cat) }} ({{ agents.length }})</span>
            <span class="cat-arrow">{{ collapsedCats.has(cat) ? '▶' : '▼' }}</span>
          </div>
          <div v-show="!collapsedCats.has(cat)" class="cat-packages">
            <div
              v-for="agent in agents"
              :key="agent.id"
              :class="['script-item', { 'script-selected': isSelected(agent.id) }]"
              :title="agent.description || agent.agent_code"
              @click="selectAgent(agent)"
            >
              <span class="script-name">{{ agent.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getAgentRegistry, type AgentItem, type AgentInfo } from '@/api/agent'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'

const props = defineProps<{
  /** 当前选中的 Agent id（用于高亮，由父组件回传） */
  selectedId?: number | null
}>()

const emit = defineEmits<{
  (e: 'agent-change', info: AgentInfo | null): void
}>()

const isExpanded = ref(false)
const loading = ref(false)
const error = ref('')
const allAgents = ref<AgentItem[]>([])
const collapsedCats = ref<Set<string>>(new Set())
const categoryOptions = ref<DictionaryItem[]>([])

function categoryLabel(cat?: string) {
  return categoryOptions.value.find(o => o.item_code === cat)?.item_name || cat || '其他'
}

async function loadCategoryOptions() {
  try {
    const res = await getDictionaryItems('agent_category')
    categoryOptions.value = res || []
  } catch (e) {
    console.error('加载专家类目字典失败:', e)
    categoryOptions.value = []
  }
}

const grouped = computed<Record<string, AgentItem[]>>(() => {
  const map: Record<string, AgentItem[]> = {}
  for (const a of allAgents.value) {
    const cat = a.category || '其他'
    if (!map[cat]) map[cat] = []
    map[cat].push(a)
  }
  return map
})

const selectedAgent = computed<AgentInfo | null>(() => {
  if (props.selectedId == null) return null
  const a = allAgents.value.find((x) => x.id === props.selectedId)
  if (!a) return null
  return { id: a.id, code: a.agent_code, name: a.name, category: a.category }
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

function selectAgent(agent: AgentItem) {
  const info: AgentInfo = {
    id: agent.id,
    code: agent.agent_code,
    name: agent.name,
    category: agent.category,
  }
  emit('agent-change', info)
}

function clearSelection() {
  emit('agent-change', null)
}

async function loadAgents() {
  loading.value = true
  error.value = ''
  try {
    const data = await getAgentRegistry()
    allAgents.value = data.agents || []
    collapsedCats.value = new Set(Object.keys(grouped.value))
  } catch (e: any) {
    error.value = e?.message || '加载专家失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCategoryOptions()
  loadAgents()
})
</script>

<!--
  以下样式与 SkillSelector.vue 完全一致（scoped 样式无法跨组件复用，
  故在此完整复制，确保专家分类的字体、间距、对齐、箭头、选中态等与技能完全统一）。
-->
<style scoped lang="less">
.agent-selector {
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
  color: #555;

  &:hover {
    color: #1677ff;
  }
}

.skill-icon { font-size: 13px; }
.skill-title { flex: 1; }
.expand-icon { font-size: 10px; color: #999; }

.selected-badge {
  flex: 1;
  font-size: 11px;
  font-weight: 500;
  color: #52c41a;
  background: #f6ffed;
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
  color: #999;
  line-height: 1;
  &:hover { color: #ff4d4f; }
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
  color: #888;
}

.skill-error { color: #ff4d4f; }

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skill-category {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  overflow: hidden;
}

.cat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px;
  background: #fafafa;
  font-size: 11.5px;
  font-weight: 600;
  color: #666;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid #f0f0f0;
}

.cat-header:hover {
  background: #f0f0f0;
  color: #333;
}

.cat-arrow {
  font-size: 9px;
  color: #999;
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
  color: #333;
  transition: background 0.15s, color 0.15s;

  &:hover {
    background: #eff6ff;
    color: #1677ff;
  }

  &.script-selected {
    background: #f6ffed;
    color: #52c41a;
    font-weight: 600;
    border-left: 2px solid #52c41a;
  }
}

.script-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
