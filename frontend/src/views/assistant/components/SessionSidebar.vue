<template>
  <div class="session-sidebar">
    <div class="session-sidebar-header">
      <span class="sidebar-label">AI 对话</span>
      <a-button type="primary" size="small" @click="$emit('new-session')">
        <template #icon><PlusOutlined /></template>新建
      </a-button>
    </div>
    <div class="session-search">
      <a-input :value="searchText" @update:value="$emit('update:searchText', $event)" placeholder="搜索会话..." allow-clear size="small">
        <template #prefix><SearchOutlined /></template>
      </a-input>
    </div>
    <div class="session-scroll">
      <a-spin :spinning="loading" size="small">
        <div class="session-list">
          <div
            v-for="s in sessions" :key="s.session_id"
            :class="['session-item', { active: currentSessionId === s.session_id, pinned: s.is_pinned }]"
            @click="$emit('switch-session', s)"
          >
            <div class="session-item-icon">
              <PushpinFilled v-if="s.is_pinned" class="pin-icon" />
              <MessageOutlined v-else />
            </div>
            <div class="session-item-body">
              <div class="session-item-title" v-if="editingTitleId !== s.session_id">
                <span @dblclick.stop="$emit('edit-title-start', s)">{{ s.session_title || '新对话' }}</span>
              </div>
              <a-input v-else :value="editingTitleValue" @update:value="$emit('update:editingTitleValue', $event)"
                size="small" class="title-input"
                @blur="$emit('edit-title-submit', s)" @keydown.enter="$emit('edit-title-submit', s)"
                @keydown.esc="$emit('edit-title-cancel')" @click.stop />
              <div class="session-item-meta">
                <span class="session-type-tag" :class="s.session_type">{{ typeLabel(s.session_type) }}</span>
                <span class="session-msg-count">{{ s.message_count }}条</span>
              </div>
            </div>
            <div class="session-item-actions" @click.stop>
              <a-tooltip title="置顶/取消">
                <PushpinOutlined :class="['action-btn', { 'pinned-active': s.is_pinned }]" @click="$emit('toggle-pin', s)" />
              </a-tooltip>
              <a-popconfirm title="确认删除该会话？" @confirm="$emit('delete-session', s.session_id)">
                <DeleteOutlined class="action-btn danger" />
              </a-popconfirm>
            </div>
          </div>
          <a-empty v-if="!sessions.length" description="暂无会话" :image-size="40" style="margin-top:36px" />
        </div>
      </a-spin>
    </div>
    <!-- 资源选择器（技能 / Agent 可切换） -->
    <div class="resource-selector-wrap">
      <a-tabs v-model:activeKey="resourceTab" size="small" class="resource-tabs">
        <a-tab-pane key="skill" tab="技能">
          <SkillSelector
            @script-change="(info: any) => $emit('skill-change', info)"
            :file-id="fileId"
            :file-name="fileName"
            :session-id="currentSessionId"
          />
        </a-tab-pane>
        <a-tab-pane key="agent" tab="专家">
          <AgentSelector
            :selected-id="selectedAgentId"
            @agent-change="(info: any) => $emit('agent-change', info)"
          />
        </a-tab-pane>
        <a-tab-pane key="team" tab="专家团">
          <TeamSelector
            :selected-id="selectedTeamId"
            @team-change="(info: any) => $emit('team-change', info)"
          />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  PlusOutlined, SearchOutlined, MessageOutlined, PushpinOutlined, PushpinFilled,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { ref } from 'vue'
import SkillSelector from './SkillSelector.vue'
import AgentSelector from './AgentSelector.vue'
import TeamSelector from './TeamSelector.vue'
import type { AiChatSession } from '@/api/aiSession'

defineProps<{
  sessions: AiChatSession[]
  currentSessionId?: number
  searchText: string
  loading: boolean
  editingTitleId: number | null
  editingTitleValue: string
  fileId: string
  fileName: string
  /** 当前选中的 Agent id（来自父组件，用于高亮） */
  selectedAgentId?: number | null
  /** 当前选中的专家团 id（来自父组件，用于高亮） */
  selectedTeamId?: number | null
  typeLabel: (t: string) => string
}>()

const resourceTab = ref<'skill' | 'agent' | 'team'>('skill')

defineEmits<{
  (e: 'new-session'): void
  (e: 'switch-session', s: AiChatSession): void
  (e: 'delete-session', id: number): void
  (e: 'toggle-pin', s: AiChatSession): void
  (e: 'edit-title-start', s: AiChatSession): void
  (e: 'edit-title-submit', s: AiChatSession): void
  (e: 'edit-title-cancel'): void
  (e: 'update:searchText', val: string): void
  (e: 'update:editingTitleValue', val: string): void
  (e: 'skill-change', info: any): void
  (e: 'agent-change', info: any): void
  (e: 'team-change', info: any): void
}>()
</script>

<style scoped lang="less">
.session-sidebar {
  width: 230px; flex-shrink: 0; display: flex; flex-direction: column;
  background: var(--bg-surface); border-right: 1px solid var(--border); min-height: 0;
}
.session-sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 12px 10px; border-bottom: 1px solid var(--border);
}
.sidebar-label { font-size: 14px; font-weight: 700; color: var(--fg); }
.session-search { padding: 8px 10px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.session-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 4px 0; }
.session-list { display: flex; flex-direction: column; }
.session-item {
  display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px;
  cursor: pointer; transition: background .15s; border-left: 3px solid transparent;
  &:hover { background: var(--accent-soft); .session-item-actions { opacity: 1; } }
  &.active { background: var(--accent-soft); border-left-color: var(--accent); }
  &.pinned { background: var(--warn-soft); border-left-color: var(--warn); }
}
.session-item-icon { font-size: 15px; color: var(--fg-secondary); margin-top: 2px; flex-shrink: 0; .pin-icon { color: var(--warn); } }
.session-item-body { flex: 1; min-width: 0; }
.session-item-title {
  font-size: 13px; color: var(--fg); font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 3px;
}
.title-input { font-size: 12px; }
.session-item-meta { display: flex; align-items: center; gap: 6px; }
.session-type-tag {
  font-size: 10px; padding: 0 5px; border-radius: 3px; font-weight: 500;
  &.general { background: var(--accent-soft); color: var(--accent); }
  &.dispute { background: #f9f0ff; color: #722ed1; }
  &.data    { background: var(--warn-soft); color: var(--accent-2); }
}
.session-msg-count { font-size: 10px; color: var(--fg-muted); }
.session-item-actions {
  display: flex; gap: 4px; opacity: 0; transition: opacity .15s; margin-top: 2px; flex-shrink: 0;
}
.action-btn {
  font-size: 13px; color: var(--fg-secondary); cursor: pointer;
  &:hover { color: var(--accent); }
  &.danger:hover { color: var(--err); }
  &.pinned-active { color: var(--warn); }
}
.skill-selector-wrap { flex-shrink: 0; padding: 6px 8px; border-top: 1px solid var(--border); background: var(--bg-input); }
.resource-selector-wrap { flex-shrink: 0; border-top: 1px solid var(--border); background: var(--bg-input); }
.resource-tabs { :deep(.ant-tabs-nav) { margin: 0; padding: 0 8px; }
  :deep(.ant-tabs-tab) { padding: 8px 4px; font-size: 13px; }
  :deep(.ant-tabs-content-holder) { padding: 0; } }
</style>
