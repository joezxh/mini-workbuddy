<template>
  <div class="attachment-card" :class="{ expandable: expandable }" @click="handleClick">
    <!-- 文件图标 -->
    <div class="card-icon">
      <FileExcelOutlined v-if="isExcel" />
      <FileTextOutlined v-else-if="isText" />
      <FileOutlined v-else />
    </div>

    <!-- 文件信息 -->
    <div class="card-body">
      <div class="card-title">{{ file.name }}</div>
      <div class="card-meta">
        <span class="card-size">{{ formatSize(file.size) }}</span>
        <template v-if="file.sheet_count">
          <span class="meta-sep">·</span>
          <span>{{ file.sheet_count }} 个工作表</span>
        </template>
        <template v-if="file.row_count">
          <span class="meta-sep">·</span>
          <span>{{ file.row_count.toLocaleString() }} 行</span>
        </template>
        <template v-if="file.col_count">
          <span class="meta-sep">·</span>
          <span>{{ file.col_count }} 列</span>
        </template>
      </div>

      <!-- 工作表标签（可点击切换） -->
      <div v-if="file.sheets?.length" class="card-sheets">
        <span
          v-for="(sheet, idx) in file.sheets.slice(0, 3)"
          :key="idx"
          class="sheet-tag"
          :class="{ active: activeSheet === idx }"
          @click.stop="activeSheet = idx"
        >
          {{ sheet }}
        </span>
        <span v-if="file.sheets.length > 3" class="sheet-more">+{{ file.sheets.length - 3 }}</span>
      </div>

      <!-- 数据预览（展开时显示） -->
      <div v-if="expanded && file.preview_data?.length" class="card-preview">
        <table class="preview-table">
          <thead>
            <tr>
              <th v-for="col in previewColumns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in file.preview_data.slice(0, 5)" :key="idx">
              <td v-for="col in previewColumns" :key="col">{{ row[col] ?? '' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="file.preview_data.length > 5" class="preview-more">
          共 {{ file.preview_data.length }} 行，仅显示前 5 行
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="card-actions" @click.stop>
      <a-tooltip v-if="expandable" :title="expanded ? '收起' : '展开'">
        <DownOutlined v-if="!expanded" class="action-btn" @click="expanded = !expanded" />
        <UpOutlined v-else class="action-btn" @click="expanded = !expanded" />
      </a-tooltip>
      <a-tooltip title="下载">
        <DownloadOutlined class="action-btn" @click="handleDownload" />
      </a-tooltip>
      <a-tooltip v-if="removable" title="移除">
        <CloseOutlined class="action-btn danger" @click="$emit('remove', file)" />
      </a-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  FileOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  DownloadOutlined,
  DownOutlined,
  UpOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue'

// ── 类型定义 ─────────────────────────────────────────────────────────────────
interface AttachmentFile {
  file_id: string
  name: string
  size: number
  url?: string
  sheet_count?: number
  row_count?: number
  col_count?: number
  sheets?: string[]
  preview_data?: Record<string, any>[]
}

// ── Props & Emits ─────────────────────────────────────────────────────────────
const props = defineProps<{
  file: AttachmentFile
  expandable?: boolean   // 是否可展开预览
  removable?: boolean    // 是否显示移除按钮
}>()

const emit = defineEmits<{
  (e: 'remove', file: AttachmentFile): void
  (e: 'download', file: AttachmentFile): void
  (e: 'click', file: AttachmentFile): void
}>()

// ── 状态 ─────────────────────────────────────────────────────────────────────
const expanded = ref(false)
const activeSheet = ref(0)

// ── 计算属性 ─────────────────────────────────────────────────────────────────
const isExcel = computed(() => /\.(xlsx?|xlsm|csv)$/i.test(props.file.name))
const isText = computed(() => /\.(txt|md|json)$/i.test(props.file.name))

const previewColumns = computed(() => {
  if (!props.file.preview_data?.length) return []
  return Object.keys(props.file.preview_data[0])
})

// ── 方法 ─────────────────────────────────────────────────────────────────────
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function handleClick() {
  emit('click', props.file)
}

function handleDownload() {
  if (props.file.url) {
    const a = document.createElement('a')
    a.href = props.file.url
    a.download = props.file.name
    a.click()
  }
  emit('download', props.file)
}
</script>

<style scoped lang="less">
.attachment-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  max-width: 480px;
  transition: all 0.2s;

  &:hover {
    background: var(--accent-soft);
    border-color: var(--accent-soft);
    box-shadow: 0 2px 8px rgba(22, 119, 255, 0.1);
  }

  &.expandable {
    cursor: pointer;
  }
}

// ── 文件图标 ─────────────────────────────────────────────────────────────────
.card-icon {
  font-size: 24px;
  color: var(--ok);
  flex-shrink: 0;
  margin-top: 2px;
}

// ── 文件信息 ─────────────────────────────────────────────────────────────────
.card-body {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.card-meta {
  font-size: 11px;
  color: var(--fg-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.meta-sep {
  color: var(--fg-muted);
}

// ── 工作表标签 ───────────────────────────────────────────────────────────────
.card-sheets {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.sheet-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s;

  &:hover, &.active {
    background: var(--accent);
    color: #fff;
  }
}

.sheet-more {
  font-size: 10px;
  color: var(--fg-muted);
  padding: 1px 4px;
}

// ── 数据预览 ─────────────────────────────────────────────────────────────────
.card-preview {
  margin-top: 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;

  th, td {
    padding: 4px 8px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 120px;
  }

  th {
    background: var(--bg-input);
    font-weight: 500;
    color: var(--fg-secondary);
  }

  td {
    color: var(--fg-secondary);
  }
}

.preview-more {
  font-size: 10px;
  color: var(--fg-muted);
  text-align: center;
  padding: 4px;
  background: var(--bg-input);
  border-top: 1px solid var(--border);
}

// ── 操作按钮 ─────────────────────────────────────────────────────────────────
.card-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;

  .attachment-card:hover & {
    opacity: 1;
  }
}

.action-btn {
  font-size: 13px;
  color: var(--fg-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.15s;

  &:hover {
    color: var(--accent);
    background: var(--accent-soft);
  }

  &.danger:hover {
    color: var(--err);
    background: var(--err-soft);
  }
}
</style>
