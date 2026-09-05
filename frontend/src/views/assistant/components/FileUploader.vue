<template>
  <div class="file-uploader">
    <!-- 标题栏 -->
    <div class="uploader-header">
      <span class="uploader-label">
        <PaperClipOutlined /> 附件 ({{ fileList.length }})
      </span>
      <a-button type="link" size="small" @click="triggerFileInput">
        <UploadOutlined /> 上传
      </a-button>
    </div>

    <!-- 拖拽上传区 -->
    <div
      v-show="fileList.length === 0"
      class="drop-zone"
      :class="{ 'drag-over': isDragOver }"
      @dragenter.prevent="isDragOver = true"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <div class="drop-zone-content">
        <CloudUploadOutlined class="drop-icon" />
        <span class="drop-text">拖拽文件到此处，或 <span class="drop-link">选择文件</span></span>
        <span class="drop-hint">支持 .xlsx, .xls, .csv（单文件 ≤ 10MB）</span>
      </div>
    </div>

    <!-- 文件列表 -->
    <div v-if="fileList.length > 0" class="file-list">
      <div
        v-for="file in fileList"
        :key="file.uid"
        class="file-item"
        :class="{ uploading: file.status === 'uploading', error: file.status === 'error' }"
      >
        <FileExcelOutlined class="file-icon" />
        <div class="file-info">
          <div class="file-name">{{ file.name }}</div>
          <div class="file-meta">
            <span class="file-size">{{ formatSize(file.size ?? 0) }}</span>
            <template v-if="file.preview">
              <span class="meta-sep">·</span>
              <span class="file-sheets">{{ file.preview.sheet_count }} 个工作表</span>
              <span class="meta-sep">·</span>
              <span class="file-rows">{{ file.preview.row_count?.toLocaleString() }} 行</span>
            </template>
            <template v-if="file.status === 'uploading'">
              <span class="meta-sep">·</span>
              <span class="upload-progress">上传中...</span>
            </template>
            <template v-if="file.status === 'error'">
              <span class="meta-sep">·</span>
              <span class="upload-error">上传失败</span>
            </template>
          </div>
        </div>
        <div class="file-actions">
          <a-tooltip v-if="file.preview" title="预览">
            <EyeOutlined class="action-icon" @click="showPreview(file)" />
          </a-tooltip>
          <a-tooltip v-if="file.file_id" title="下载">
            <DownloadOutlined class="action-icon" @click="downloadFile(file)" />
          </a-tooltip>
          <a-tooltip title="移除">
            <CloseOutlined class="action-icon danger" @click="removeFile(file)" />
          </a-tooltip>
        </div>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <a-modal
      v-model:open="previewVisible"
      :title="previewFile?.name || '文件预览'"
      width="640px"
      :footer="null"
    >
      <div v-if="previewFile?.preview" class="preview-content">
        <div class="preview-stats">
          <a-tag color="blue">{{ previewFile.preview.sheet_count }} 个工作表</a-tag>
          <a-tag color="green">{{ previewFile.preview.row_count?.toLocaleString() }} 行</a-tag>
          <a-tag color="orange">{{ previewFile.preview.col_count }} 列</a-tag>
        </div>

        <div class="preview-sheets">
          <span class="preview-label">工作表：</span>
          <a-tag
            v-for="(sheet, idx) in previewFile.preview.sheets"
            :key="idx"
            :color="previewActiveSheet === idx ? 'blue' : 'default'"
            class="sheet-tag"
            @click="previewActiveSheet = idx"
          >
            {{ sheet }}
          </a-tag>
        </div>

        <div class="preview-table">
          <a-table
            :columns="previewColumns"
            :data-source="previewFile.preview.data"
            :pagination="{ pageSize: 5 }"
            size="small"
            bordered
          />
        </div>
      </div>
      <div v-else class="preview-empty">
        <a-empty description="暂无预览数据" />
      </div>
    </a-modal>

    <!-- Skill 快捷选择区（当有文件上传时显示） -->
    <div v-if="fileList.length > 0 && hasExcelFile" class="skill-shortcuts">
      <div class="skill-shortcuts-label">
        <ThunderboltOutlined /> 快捷分析
      </div>
      <div class="skill-shortcuts-btns">
        <a-tag
          v-for="skill in excelSkills"
          :key="skill.id"
          class="skill-tag"
          @click="$emit('skill-click', skill)"
        >
          <FileExcelOutlined /> {{ skill.name }}
        </a-tag>
      </div>
    </div>

    <!-- 隐藏的文件输入框 -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".xlsx,.xls,.csv"
      multiple
      style="display: none"
      @change="handleFileChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { getToken } from '@/utils/auth'
import {
  PaperClipOutlined,
  UploadOutlined,
  CloudUploadOutlined,
  FileExcelOutlined,
  EyeOutlined,
  DownloadOutlined,
  CloseOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import type { UploadFile } from 'ant-design-vue'

// ── 类型定义 ─────────────────────────────────────────────────────────────────
// 注意：UploadFile.preview 在 ant-design-vue 中为 string|undefined，
// 但本组件给 preview 扩展为对象（包含 sheet/row/col 等结构化预览数据）。
// 用 Omit<UploadFile, 'preview'> 移除基类的 preview 定义，避免类型冲突。
// 另外 a-upload 的 beforeUpload 回调给到原生 File，需要在 UploadedFile 上扩展保存，
// 供 uploadFile() 内部构造 FormData 时回取。
export interface UploadedFile extends Omit<UploadFile, 'preview'> {
  file_id?: string          // UUID 字符串（用于 GET /files/{uuid}）
  db_id?: number            // infra_file.id 整数（用于关联消息）
  file?: File               // a-upload beforeUpload 给到的原生 File 对象
  preview?: {
    sheet_count: number
    row_count?: number
    col_count: number
    sheets: string[]
    data: Record<string, any>[]
  }
}

interface ExcelSkill {
  id: string
  package_id: string
  script_id: string
  name: string
  icon?: string
}

// ── Props & Emits ─────────────────────────────────────────────────────────────
const props = defineProps<{
  skills?: ExcelSkill[]
}>()

const emit = defineEmits<{
  (e: 'file-uploaded', file: UploadedFile): void
  (e: 'file-removed', file: UploadedFile): void
  (e: 'skill-click', skill: ExcelSkill): void
}>()

// ── 状态 ─────────────────────────────────────────────────────────────────────
const fileList = ref<UploadedFile[]>([])
const fileInputRef = ref<HTMLInputElement>()
const isDragOver = ref(false)
const previewVisible = ref(false)
const previewFile = ref<UploadedFile | null>(null)
const previewActiveSheet = ref(0)

// ── 计算属性 ─────────────────────────────────────────────────────────────────
const hasExcelFile = computed(() => fileList.value.some(f => f.status === 'done'))

// 可用的 Excel Skill（过滤支持 Excel 分析的 Skill）
const excelSkills = computed<ExcelSkill[]>(() => {
  if (props.skills?.length) return props.skills
  // 默认的内置 Excel Skill
  return [
    { id: 'claude-xlsx', package_id: 'anthropics', script_id: 'xlsx', name: 'Claude XLSX' },
    { id: 'minimax-xlsx', package_id: 'minimax', script_id: 'minimax-xlsx', name: 'MiniMax XLSX' },
    { id: 'sensenova-excel', package_id: 'sensenova', script_id: 'sn-da-excel-workflow', name: 'SenseNova Excel' },
  ]
})

// 预览表格列
const previewColumns = computed(() => {
  if (!previewFile.value?.preview?.data?.length) return []
  const firstRow = previewFile.value.preview.data[0]
  return Object.keys(firstRow).map(key => ({
    title: key,
    dataIndex: key,
    key,
    width: 150,
    ellipsis: true,
  }))
})

// ── 方法 ─────────────────────────────────────────────────────────────────────
function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) {
    addFiles(Array.from(input.files))
    input.value = '' // 清空，以便重复选择同一文件
  }
}

function handleDrop(e: DragEvent) {
  isDragOver.value = false
  const files = e.dataTransfer?.files
  if (files) {
    addFiles(Array.from(files))
  }
}

function addFiles(files: File[]) {
  for (const file of files) {
    // 校验文件类型
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['xlsx', 'xls', 'csv'].includes(ext || '')) {
      message.warning(`不支持的文件类型: ${file.name}`)
      continue
    }
    // 校验文件大小（10MB）
    if (file.size > 10 * 1024 * 1024) {
      message.warning(`文件超过 10MB 限制: ${file.name}`)
      continue
    }

    const uid = `file-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const uploadedFile: UploadedFile = {
      uid,
      name: file.name,
      size: file.size,
      status: 'uploading',
      file,
    }

    fileList.value.push(uploadedFile)
    uploadFile(uploadedFile)
  }
}

async function uploadFile(file: UploadedFile) {
  const formData = new FormData()
  if (file.file) {
    formData.append('file', file.file)
  }

  try {
    const token = getToken() || ''
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

    const res = await fetch(`${baseUrl}/api/v1/ai-assistant/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    })

    if (!res.ok) throw new Error(`上传失败: ${res.status}`)

    const json = await res.json()
    if (json.code !== 0) throw new Error(json.message || '上传失败')

    // 更新文件状态
    const idx = fileList.value.findIndex(f => f.uid === file.uid)
    if (idx !== -1) {
      fileList.value[idx] = {
        ...fileList.value[idx],
        status: 'done',
        file_id: json.data.file_id,
        db_id: json.data.db_id,
        preview: json.data.preview,
        url: `${baseUrl}/api/v1/ai/files/${json.data.file_id}`,
      }
      emit('file-uploaded', fileList.value[idx])
      message.success(`${file.name} 上传成功`)
    }
  } catch (e: any) {
    const idx = fileList.value.findIndex(f => f.uid === file.uid)
    if (idx !== -1) {
      fileList.value[idx].status = 'error'
    }
    message.error(e.message || '上传失败')
  }
}

function removeFile(file: UploadedFile) {
  const idx = fileList.value.findIndex(f => f.uid === file.uid)
  if (idx !== -1) {
    const removed = fileList.value.splice(idx, 1)[0]
    emit('file-removed', removed)
  }
}

function showPreview(file: UploadedFile) {
  previewFile.value = file
  previewActiveSheet.value = 0
  previewVisible.value = true
}

function downloadFile(file: UploadedFile) {
  if (file.url) {
    const a = document.createElement('a')
    a.href = file.url
    a.download = file.name
    a.click()
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── 暴露给父组件的方法 ───────────────────────────────────────────────────────
defineExpose({
  fileList,
  getFirstUploadedFile: () => fileList.value.find(f => f.status === 'done'),
  getFileIds: () => fileList.value.filter(f => f.status === 'done' && f.file_id).map(f => f.file_id!),
  clearFiles: () => { fileList.value = [] },
})
</script>

<style scoped lang="less">
.file-uploader {
  border: 1px solid #e8eaed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

// ── 标题栏 ──────────────────────────────────────────────────────────────────
.uploader-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.uploader-label {
  font-size: 13px;
  color: #555;
  display: flex;
  align-items: center;
  gap: 6px;
}

// ── 拖拽区 ──────────────────────────────────────────────────────────────────
.drop-zone {
  padding: 24px 16px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover, &.drag-over {
    background: #f0f7ff;
    .drop-icon { color: #1677ff; transform: translateY(-4px); }
    .drop-zone-content { border-color: #1677ff; }
  }
}

.drop-zone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  transition: border-color 0.2s;
}

.drop-icon {
  font-size: 32px;
  color: #bbb;
  transition: all 0.2s;
}

.drop-text {
  font-size: 13px;
  color: #666;
}

.drop-link {
  color: #1677ff;
  &:hover { text-decoration: underline; }
}

.drop-hint {
  font-size: 11px;
  color: #aaa;
}

// ── 文件列表 ────────────────────────────────────────────────────────────────
.file-list {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid transparent;
  transition: all 0.15s;

  &:hover {
    background: #f5f7ff;
    border-color: #e0e4ec;
    .file-actions { opacity: 1; }
  }

  &.uploading { opacity: 0.7; }
  &.error { background: #fff2f0; border-color: #ffccc7; }
}

.file-icon {
  font-size: 20px;
  color: #52c41a;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 13px;
  color: #333;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 11px;
  color: #888;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.meta-sep { color: #ccc; }
.upload-error { color: #ff4d4f; }

// ── 操作按钮 ────────────────────────────────────────────────────────────────
.file-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.action-icon {
  font-size: 14px;
  color: #888;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.15s;

  &:hover { color: #1677ff; background: #e6f7ff; }
  &.danger:hover { color: #ff4d4f; background: #fff2f0; }
}

// ── 预览弹窗 ────────────────────────────────────────────────────────────────
.preview-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-stats {
  display: flex;
  gap: 8px;
}

.preview-sheets {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-label {
  font-size: 13px;
  color: #666;
}

.sheet-tag {
  cursor: pointer;
}

.preview-table {
  max-height: 300px;
  overflow: auto;
}

.preview-empty {
  padding: 40px 0;
  text-align: center;
}

// ── Skill 快捷选择区 ────────────────────────────────────────────────────────
.skill-shortcuts {
  padding: 10px 12px;
  border-top: 1px solid #f0f0f0;
  background: #fafbfc;
}

.skill-shortcuts-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.skill-shortcuts-btns {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.skill-tag {
  cursor: pointer;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  transition: all 0.15s;

  &:hover {
    background: #1677ff;
    color: #fff;
    border-color: #1677ff;
  }
}
</style>
