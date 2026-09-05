<template>
  <div class="chat-input-area">
    <!-- 文件上传面板 -->
    <div v-if="fileUploaderVisible" class="file-uploader-section">
      <div class="file-uploader-header">
        <span class="file-uploader-title">上传文件</span>
        <a-button type="text" size="small" @click="fileUploaderVisible = false">
          <template #icon><CloseCircleOutlined /></template>
        </a-button>
      </div>
      <FileUploader
        ref="fileUploaderRef"
        @file-uploaded="handleFileUploaded"
        @file-removed="handleFileRemoved"
      />
    </div>

    <!-- 工具栏 -->
    <div class="input-toolbar">
      <!-- 工作空间选择 -->
      <a-select
        :value="workspaceId"
        @update:value="$emit('update:workspaceId', $event)"
        size="small"
        style="width:140px;flex-shrink:0"
        :disabled="streaming"
        placeholder="工作空间"
        allow-clear
        :options="workspaceOptions"
        :field-names="{ label: 'name', value: 'id' }"
      />

      <a-select :value="sessionType" @update:value="$emit('update:sessionType', $event)" size="small" style="width:120px;flex-shrink:0" :disabled="streaming">
        <a-select-option v-for="opt in sessionTypeOptionsWithFallback" :key="opt.item_code" :value="opt.item_value || opt.item_code">
          {{ opt.item_name }}
        </a-select-option>
      </a-select>

      <!-- 数据源选择（仅数据分析时显示） -->
      <a-select
        v-if="sessionType === 'data'"
        :value="datasourceId"
        @update:value="$emit('update:datasourceId', $event)"
        size="small"
        style="width:180px;flex-shrink:0"
        :disabled="streaming"
        placeholder="选择数据源"
        :loading="datasourceLoading"
      >
        <a-select-option v-for="ds in datasourceOptions" :key="ds.id" :value="ds.id">
          {{ ds.name }}{{ ds.db_type ? ` (${ds.db_type})` : '' }}
        </a-select-option>
      </a-select>

      <!-- 模型选择（技能 / 思考 / 深度研究 / 智能体 / 专家团 / 云端调度 模式显示） -->
      <a-tooltip v-if="sessionType === 'team'" title="专家团模式将使用所选模型执行子 agent 编排（需 ai_chat_model 表已正确配置 API Key）">
        <a-select
          v-if="modelSelectVisible"
          :value="modelId"
          @update:value="$emit('update:modelId', $event)"
          size="small"
          style="width:200px;flex-shrink:0"
          :disabled="streaming"
          placeholder="选择模型"
        >
          <a-select-opt-group v-for="group in groupedModelOptions" :key="group.label" :label="group.label">
            <a-select-option v-for="m in group.models" :key="m.id" :value="m.id">
              {{ m.name }} ({{ m.platform }})
            </a-select-option>
          </a-select-opt-group>
        </a-select>
      </a-tooltip>
      <a-select
        v-else-if="modelSelectVisible"
        :value="modelId"
        @update:value="$emit('update:modelId', $event)"
        size="small"
        style="width:200px;flex-shrink:0"
        :disabled="streaming"
        placeholder="选择模型"
      >
        <a-select-opt-group v-for="group in groupedModelOptions" :key="group.label" :label="group.label">
          <a-select-option v-for="m in group.models" :key="m.id" :value="m.id">
            {{ m.name }} ({{ m.platform }})
          </a-select-option>
        </a-select-opt-group>
      </a-select>

      <a-tooltip v-if="sessionType !== 'data'" title="添加文件">
        <a-button v-if="!currentFileId" type="text" size="small" class="toolbar-icon-btn"
          @click="fileUploaderVisible = !fileUploaderVisible">
          <template #icon><PaperClipOutlined /></template>
        </a-button>
      </a-tooltip>
      <span v-if="currentFileId && sessionType !== 'data'" class="file-context">
        <PaperClipOutlined />
        <span class="file-name">{{ currentFileName }}</span>
        <a-button type="text" size="small" class="file-remove-btn" @click="clearFile">
          <template #icon><CloseCircleOutlined /></template>
        </a-button>
      </span>

      <span v-if="skill" class="skill-context">
        <span class="skill-icon">{{ skillIcon }}</span>
        <span class="skill-name">{{ skill.scriptName }}</span>
        <a-tooltip :title="skill.scriptDescription" placement="top">
          <QuestionCircleOutlined class="skill-tip-icon" />
        </a-tooltip>
      </span>

      <span v-if="agent" class="skill-context">
        <span class="skill-icon">👤</span>
        <span class="skill-name">{{ agent.name }}</span>
      </span>

      <span v-if="team" class="skill-context">
        <span class="skill-icon">👥</span>
        <span class="skill-name">{{ team.name }}</span>
      </span>

      <span class="toolbar-spacer" />
      <span class="input-hint">Shift+Enter 换行，Enter 发送</span>
    </div>
    <div class="input-row">
      <a-textarea
        :value="inputText"
        @update:value="$emit('update:inputText', $event)"
        :placeholder="streaming ? 'AI 正在回复中...' : '输入消息，Enter 发送'"
        :disabled="streaming"
        :auto-size="{ minRows: 2, maxRows: 6 }"
        class="chat-textarea"
        @keydown="handleKeydown"
      />
      <a-button v-if="!streaming" type="primary" class="send-btn" :disabled="!inputText.trim()" @click="$emit('send')">
        <template #icon><SendOutlined /></template>发送
      </a-button>
      <a-button v-else danger class="send-btn" @click="$emit('stop')">
        <template #icon><StopOutlined /></template>停止生成
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  SendOutlined, PaperClipOutlined, CloseCircleOutlined, QuestionCircleOutlined, StopOutlined,
} from '@ant-design/icons-vue'
import FileUploader, { type UploadedFile } from './FileUploader.vue'
import type { SkillInfo } from './types'
import { MODEL_SELECTABLE_TYPES } from './types'
import type { DictionaryItem } from '@/api/dictionary'
import type { SqlbotDatasource } from '@/api/aiSession'
import { useDictionary } from '@/composables/useDictionary'

const props = defineProps<{
  inputText: string
  streaming: boolean
  sessionType: string
  sessionTypeOptions: DictionaryItem[]
  currentFileId: string
  currentFileName: string
  skill: SkillInfo | null
  workspaceId?: number | null
  workspaceOptions?: Array<{ id: number; name: string; [key: string]: any }>
  datasourceId?: number | null
  datasourceOptions?: SqlbotDatasource[]
  datasourceLoading?: boolean
  modelId?: number | null
  modelOptions?: Array<{ id: number; name: string; platform: string; type?: number | null }>
  agent?: { id: number; code: string; name: string; category?: string | null } | null
  team?: { id: number; code: string; name: string; category?: string | null } | null
}>()

const emit = defineEmits<{
  (e: 'update:inputText', val: string): void
  (e: 'update:sessionType', val: string): void
  (e: 'update:workspaceId', val: number | null): void
  (e: 'update:datasourceId', val: number | null): void
  (e: 'update:modelId', val: number | null): void
  (e: 'send'): void
  (e: 'stop'): void
  (e: 'file-uploaded', file: UploadedFile): void
  (e: 'file-removed', file: UploadedFile): void
  (e: 'clear-file'): void
}>()

const fileUploaderVisible = ref(false)
const fileUploaderRef = ref<InstanceType<typeof FileUploader>>()

// 模型类型标签由数据字典（model_type）动态提供，避免硬编码
const { modelTypes, loadModelTypes } = useDictionary()
onMounted(() => {
  loadModelTypes()
})

const skillIcon = computed(() => {
  const icon = props.skill?.packageIcon
  if (icon === 'database') return '📊'
  if (icon === 'chart') return '📈'
  if (icon === 'capture') return '📸'
  return '🔧'
})

/** 是否为可显示模型下拉的会话类别 */
const modelSelectVisible = computed(() => {
  return MODEL_SELECTABLE_TYPES.includes(props.sessionType) && !!props.modelOptions && props.modelOptions.length > 0
})

/** 会话类型下拉项：确保“专家团(team)”“云端调度(scheduled)”始终存在，便于从侧边栏直接切换 */
const sessionTypeOptionsWithFallback = computed<DictionaryItem[]>(() => {
  const list = props.sessionTypeOptions || []
  const exists = (code: string) => list.some(o => (o.item_value || o.item_code) === code)
  const extra: DictionaryItem[] = []
  if (!exists('team')) {
    extra.push({ item_code: 'team', item_value: 'team', item_name: '专家团', color: 'geekblue', is_active: true } as DictionaryItem)
  }
  if (!exists('scheduled')) {
    extra.push({ item_code: 'scheduled', item_value: 'scheduled', item_name: '云端调度', color: 'volcano', is_active: true } as DictionaryItem)
  }
  return extra.length ? [...list, ...extra] : list
})

/** 按模型类型分组，分组标签由数据字典（model_type）动态提供 */
const groupedModelOptions = computed(() => {
  const options = props.modelOptions || []
  const typeLabel = (type: number | null | undefined) => {
    const item = modelTypes.value.find(
      i => Number(i.item_value ?? i.item_code) === (type ?? -1)
    )
    return item?.item_name || `类型${type ?? ''}`
  }
  const groupsMap = new Map<number, Array<{ id: number; name: string; platform: string; type?: number | null }>>()
  for (const m of options) {
    const key = m.type ?? -1
    if (!groupsMap.has(key)) {
      groupsMap.set(key, [])
    }
    groupsMap.get(key)!.push(m)
  }
  return Array.from(groupsMap.entries()).map(([type, models]) => ({
    label: typeLabel(type),
    models
  }))
})

function handleFileUploaded(file: UploadedFile) {
  emit('file-uploaded', file)
  fileUploaderVisible.value = false
}

function handleFileRemoved(file: UploadedFile) {
  emit('file-removed', file)
}

function clearFile() {
  emit('clear-file')
  fileUploaderRef.value?.clearFiles?.()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    emit('send')
  }
}

/** 外部调用：获取文件 ID 列表 */
function getFileIds() { return fileUploaderRef.value?.getFileIds() || [] }
function getFileList() { return fileUploaderRef.value?.fileList || [] }

defineExpose({ getFileIds, getFileList })
</script>

<style scoped lang="less">
.chat-input-area { flex-shrink: 0; padding: 2px 16px 2px; background: var(--bg-surface); border-top: 1px solid var(--border); }
.input-toolbar { display: flex; align-items: center; flex-wrap: nowrap; gap: 8px; margin-bottom: 7px; overflow: hidden; }
.input-hint { font-size: 11px; color: var(--fg-muted); }
.input-row { display: flex; gap: 8px; align-items: flex-end; }
.chat-textarea { flex: 1; border-radius: 8px; font-size: 14px; }
.send-btn { height: 54px; width: 72px; border-radius: 8px; font-size: 14px; flex-shrink: 0; }
.toolbar-spacer { flex: 1; }
.toolbar-icon-btn { padding: 0 4px; color: var(--fg-secondary); transition: color 0.2s; &:hover { color: var(--accent); } }
.file-context {
  font-size: 11px; color: var(--accent); display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 2px; background: var(--accent-soft); border-radius: 10px;
}
.file-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-remove-btn { padding: 0 2px; color: var(--fg-muted); transition: color 0.2s; &:hover { color: var(--err); } }
.skill-context {
  display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--ok);
  padding: 2px 8px; background: var(--ok-soft); border-radius: 10px; border: 1px solid #b7eb8f;
}
.skill-icon { font-size: 12px; }
.skill-name { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.skill-tip-icon { color: var(--fg-muted); font-size: 11px; cursor: help; }
.file-uploader-section {
  margin-bottom: 6px; border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px;
  background: var(--bg-input); max-height: 100px; overflow-y: auto;
}
.file-uploader-section :deep(.file-uploader) {
  .uploader-header { display: none; }
  .drop-zone {
    min-height: 56px; padding: 6px 0;
    .drop-zone-content { gap: 2px; } .drop-icon { font-size: 16px; }
    .drop-text { font-size: 11px; } .drop-hint { font-size: 10px; }
  }
  .file-list { max-height: 50px; overflow-y: auto; .file-item { padding: 4px 0; } }
}
.file-uploader-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.file-uploader-title { font-size: 12px; color: var(--fg-secondary); font-weight: 500; }
</style>
