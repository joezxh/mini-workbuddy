<template>
  <div class="file-management">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">文件存储管理</h2>
        <span class="panel-subtitle">统一管理多后端文件存储、浏览与批量导入</span>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="openUpload">
          <UploadOutlined /> 上传文件
        </a-button>
        <a-button @click="openArchiveUpload">
          <CloudUploadOutlined /> 上传压缩包
        </a-button>
        <a-button v-if="activeTab === 'config'" type="primary" ghost @click="openConfigCreate">
          <PlusOutlined /> 新增配置
        </a-button>
      </div>
    </div>

    <div class="stats-row">
      <FileStatsCard
        v-for="s in stats"
        :key="s.configId"
        :stats="s"
        :selected="s.configId === selectedConfigId"
        :master="isMaster(s.configId)"
        @select="onSelectConfig"
      />
      <div v-if="!stats.length && !statsLoading" class="stats-empty">暂无存储配置，请切换到「存储配置」新增</div>
    </div>

    <div class="content-wrapper">
      <a-tabs v-model:activeKey="activeTab">
        <!-- 文件管理 Tab -->
        <a-tab-pane key="files" tab="文件管理">
          <div class="file-toolbar">
            <a-input-search
              v-model:value="searchPath"
              placeholder="按目录路径筛选"
              allow-clear
              class="file-search"
              @search="loadFiles"
            />
            <a-select
              v-model:value="filterType"
              placeholder="文件类型"
              allow-clear
              class="file-type-select"
              :options="[{ value: 'image', label: '图片' }, { value: 'pdf', label: 'PDF' }, { value: 'zip', label: '压缩包' }]"
              @change="loadFiles"
            />
            <a-button-group>
              <a-button :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'">
                <UnorderedListOutlined />
              </a-button>
              <a-button :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'">
                <AppstoreOutlined />
              </a-button>
            </a-button-group>
            <a-button @click="treeOpen = true"><FolderOpenOutlined /> 目录</a-button>
            <a-popconfirm v-if="selectedIds.length" title="确认删除选中的文件？" @confirm="onBatchDelete">
              <a-button danger><DeleteOutlined /> 删除选中 ({{ selectedIds.length }})</a-button>
            </a-popconfirm>
          </div>

          <a-table
            v-if="viewMode === 'list'"
            :columns="columns"
            :data-source="files"
            :loading="filesLoading"
            :pagination="pagination"
            :row-selection="{ selectedRowKeys: selectedIds, onChange: onSelectRows }"
            row-key="id"
            size="middle"
            @change="onTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <span class="file-name-cell">
                  <img v-if="isImage(record)" :src="infraFileApi.previewUrl(record)" class="file-thumb-sm" alt="" />
                  <FileOutlined v-else class="file-icon-sm" />
                  <a @click="openPreview(record)">{{ record.name || fileName(record) }}</a>
                </span>
              </template>
              <template v-if="column.key === 'size'">{{ formatSize(record.size) }}</template>
              <template v-if="column.key === 'createTime'">{{ (record.createTime || '').slice(0, 16) }}</template>
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openPreview(record)">预览</a-button>
                  <a-button type="link" size="small" @click="copyLink(record)">复制链接</a-button>
                  <a-button type="link" size="small" @click="download(record)">下载</a-button>
                  <a-popconfirm title="确认删除该文件？" @confirm="onDelete(record)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>

          <FileGridView
            v-else
            :files="files"
            :selected-ids="selectedIds"
            @preview="openPreview"
            @toggle-select="toggleSelect"
            @copy-link="copyLink"
            @download="download"
            @delete="onDelete"
          />
        </a-tab-pane>

        <!-- 存储配置 Tab -->
        <a-tab-pane key="config" tab="存储配置">
          <div class="config-toolbar">
            <a-popconfirm v-if="selectedConfigIds.length" title="确认删除选中的配置？" @confirm="onBatchDeleteConfig">
              <a-button danger size="small"><DeleteOutlined /> 删除选中 ({{ selectedConfigIds.length }})</a-button>
            </a-popconfirm>
            <a-space>
              <a-button size="small" @click="exportConfigs"><ExportOutlined /> 导出配置</a-button>
              <a-upload :show-upload-list="false" :before-upload="importConfigs" accept=".json">
                <a-button size="small"><ImportOutlined /> 导入配置</a-button>
              </a-upload>
            </a-space>
          </div>
          <a-table
            :columns="configColumns"
            :data-source="configs"
            :loading="configsLoading"
            :pagination="false"
            :row-selection="{ selectedRowKeys: selectedConfigIds, onChange: onSelectConfigRows }"
            row-key="id"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'storage'">
                <a-tag :color="FileStorageColorMap[record.storage] || 'default'">
                  {{ FileStorageLabels[record.storage] || record.storage }}
                </a-tag>
              </template>
              <template v-if="column.key === 'master'">
                <a-tag v-if="record.master" color="gold">主配置</a-tag>
                <span v-else>—</span>
              </template>
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openConfigEdit(record)">编辑</a-button>
                  <a-button type="link" size="small" @click="copyConfig(record)">复制</a-button>
                  <a-button type="link" size="small" @click="testConfig(record)">测试</a-button>
                  <a-popconfirm v-if="!record.master" title="设为主存储？" @confirm="setMaster(record)">
                    <a-button type="link" size="small">设主</a-button>
                  </a-popconfirm>
                  <a-popconfirm v-if="!record.master" title="确认删除该配置？" @confirm="onDeleteConfig(record)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 普通上传弹窗 -->
    <a-modal v-model:open="uploadOpen" title="上传文件" :footer="null" :width="520">
      <div class="upload-zone">
        <a-upload-dragger
          :file-list="[]"
          :before-upload="beforeUpload"
          :show-upload-list="false"
          :multiple="true"
        >
          <UploadOutlined class="upload-zone__icon" />
          <p>点击或拖拽文件到此处上传</p>
          <p class="upload-zone__hint">指定 code 时使用对应存储，留空使用默认主存储</p>
        </a-upload-dragger>
        <a-form-item label="目标目录" class="upload-field">
          <input v-model="uploadDirectory" class="cfg-input" placeholder="可选，例如：kb / assets" />
        </a-form-item>
        <a-form-item label="目标存储" class="upload-field">
          <a-select
            v-model:value="uploadCode"
            placeholder="默认使用主存储"
            allow-clear
            :options="storageSelectOptions"
          />
        </a-form-item>
        <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
          <a-progress :percent="uploadProgress" />
        </div>
      </div>
    </a-modal>

    <!-- 压缩包上传与进度弹窗 -->
    <a-modal v-model:open="archiveOpen" title="上传压缩包（zip / 7z）" :footer="null" :width="680">
      <template v-if="!archiveTaskId">
        <a-upload-dragger :file-list="[]" :before-upload="beforeArchiveUpload" :show-upload-list="false" accept=".zip,.7z">
          <CloudUploadOutlined class="upload-zone__icon" />
          <p>点击或拖拽 zip / 7z 压缩包</p>
          <p class="upload-zone__hint">后台异步解压并逐条入库，最多 100 个文件</p>
        </a-upload-dragger>
      </template>
      <template v-else>
        <div class="archive-progress">
          <div class="archive-progress__head">
            <strong>{{ archiveProgress?.archiveName || '压缩包' }}</strong>
            <a-tag :color="archiveStatusColor">{{ archiveStatusText }}</a-tag>
          </div>
          <a-progress :percent="archivePercent" :status="archiveProgress?.status === 4 ? 'exception' : 'active'" />
          <div class="archive-progress__message">{{ archiveProgress?.message }}</div>
          <div v-if="archiveProgress?.list?.length" class="archive-list">
            <div class="archive-list__title">已上传 ({{ archiveProgress.list.length }})</div>
            <div v-for="item in archiveProgress.list" :key="item.name" class="archive-list__row">
              <CheckCircleOutlined class="archive-ok" /> <span>{{ item.name }}</span>
            </div>
          </div>
          <div v-if="archiveProgress?.failed?.length" class="archive-list">
            <div class="archive-list__title">失败 ({{ archiveProgress.failed.length }})</div>
            <div v-for="item in archiveProgress.failed" :key="item.name" class="archive-list__row">
              <CloseCircleOutlined class="archive-fail" /> <span>{{ item.name }} — {{ item.reason }}</span>
            </div>
          </div>
          <div class="archive-progress__foot">
            <a-button v-if="!isTerminal" danger size="small" @click="onCancelArchive">取消任务</a-button>
            <a-button size="small" @click="resetArchive">关闭</a-button>
          </div>
        </div>
      </template>
    </a-modal>

    <FileTreeDrawer v-model:open="treeOpen" :directories="directories" :selected="searchPath" @select="onTreeSelect" />
    <FilePreviewModal
      v-model:open="previewOpen"
      :file="previewFile"
      :index="previewIndex"
      :total="files.length"
      @download="() => { if (previewFile) download(previewFile) }"
    />
    <FileDropOverlay v-if="activeTab === 'files'" @drop="onGlobalDrop" />
    <FileConfigFormModal
      v-model:open="configFormOpen"
      :config="editingConfig"
      @saved="onConfigSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  UploadOutlined, CloudUploadOutlined, PlusOutlined, FolderOpenOutlined,
  DeleteOutlined, FileOutlined, UnorderedListOutlined, AppstoreOutlined,
  ExportOutlined, ImportOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons-vue'
import type {
  InfraFileVO, FileConfigVO, FileStatistics, DirectoryItem, ArchiveExtractProgressVO,
} from '@/api/file'
import {
  infraFileApi, fileConfigApi, FileStorageLabels, FileStorageColorMap,
} from '@/api/file'
import FileStatsCard from './components/FileStatsCard.vue'
import FileGridView from './components/FileGridView.vue'
import FileTreeDrawer from './components/FileTreeDrawer.vue'
import FilePreviewModal from './components/FilePreviewModal.vue'
import FileDropOverlay from './components/FileDropOverlay.vue'
import FileConfigFormModal from './FileConfigFormModal.vue'
import { useFileView } from './composables/useFileView'

const { viewMode } = useFileView()
const activeTab = ref('files')
const stats = ref<FileStatistics[]>([])
const statsLoading = ref(false)
const configs = ref<FileConfigVO[]>([])
const configsLoading = ref(false)
const selectedConfigId = ref<number | null>(null)
const selectedConfigIds = ref<number[]>([])
const files = ref<InfraFileVO[]>([])
const filesLoading = ref(false)
const searchPath = ref('')
const filterType = ref<string | undefined>(undefined)
const selectedIds = ref<number[]>([])
const directories = ref<DirectoryItem[]>([])
const treeOpen = ref(false)
const currentPage = ref(1)
const pageSize = ref(15)
const total = ref(0)

const columns = [
  { title: '文件名', key: 'name', dataIndex: 'name' },
  { title: '类型', key: 'type', dataIndex: 'type', width: 150 },
  { title: '大小', key: 'size', width: 110 },
  { title: '路径', key: 'path', dataIndex: 'path', ellipsis: true },
  { title: '上传时间', key: 'createTime', width: 160 },
  { title: '操作', key: 'action', width: 320 },
]
const configColumns = [
  { title: '配置名称', dataIndex: 'name', key: 'name' },
  { title: '编码', dataIndex: 'code', key: 'code' },
  { title: '存储器', dataIndex: 'storage', key: 'storage' },
  { title: '状态', dataIndex: 'master', key: 'master' },
  { title: '备注', dataIndex: 'remark', key: 'remark', ellipsis: true },
  { title: '操作', key: 'action', width: 360 },
]
const pagination = computed(() => ({
  current: currentPage.value, pageSize: pageSize.value, total: total.value,
  showSizeChanger: true, showTotal: (t: number) => `共 ${t} 个文件`,
}))

function isMaster(configId: number) {
  return stats.value.find(s => s.configId === configId) && configs.value.find(c => c.id === configId)?.master
}
function isImage(file: InfraFileVO) { return (file.type || '').startsWith('image/') }
function fileName(file: InfraFileVO) { return file.path.split('/').pop() || file.path }
function downloadUrl(file: InfraFileVO) { return infraFileApi.downloadUrl(file) }
function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  return `${(bytes / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${units[i]}`
}

async function loadStats() {
  statsLoading.value = true
  try {
    stats.value = await infraFileApi.getStatistics()
    if (!selectedConfigId.value && stats.value.length) selectedConfigId.value = stats.value[0].configId
  } catch (e: any) {
    message.error(e?.message || '加载统计失败')
  } finally {
    statsLoading.value = false
  }
}
async function loadFiles() {
  filesLoading.value = true
  try {
    const res = await infraFileApi.page({
      page: currentPage.value, pageSize: pageSize.value,
      configId: selectedConfigId.value || undefined,
      path: searchPath.value || undefined, type: filterType.value || undefined,
    })
    files.value = res.data
    total.value = res.total
  } catch (e: any) {
    message.error(e?.message || '加载文件失败')
  } finally {
    filesLoading.value = false
  }
}
async function loadConfigs() {
  configsLoading.value = true
  try {
    configs.value = (await fileConfigApi.page({ page: 1, pageSize: 100 })).data
  } catch (e: any) {
    message.error(e?.message || '加载配置失败')
  } finally {
    configsLoading.value = false
  }
}
async function loadDirectories() {
  try { directories.value = await infraFileApi.getDirectories() } catch { /* 忽略 */ }
}
function refreshAll() {
  loadStats(); loadFiles(); loadConfigs(); loadDirectories()
}
onMounted(refreshAll)

function onTableChange(pag: any) {
  currentPage.value = pag.current || 1
  pageSize.value = pag.pageSize || 15
  loadFiles()
}
function onSelectConfig(id: number) { selectedConfigId.value = id; currentPage.value = 1; loadFiles() }
function onSelectRows(keys: Array<string | number>) { selectedIds.value = keys.map(Number) }
function toggleSelect(id: number) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(x => x !== id) : [...selectedIds.value, id]
}
function onSelectConfigRows(keys: Array<string | number>) { selectedConfigIds.value = keys.map(Number) }
function onTreeSelect(path: string) { searchPath.value = path; currentPage.value = 1; loadFiles() }

function copyLink(file: InfraFileVO) {
  const link = new URL(downloadUrl(file), window.location.origin).href
  navigator.clipboard?.writeText(link)
  message.success('链接已复制')
}
function download(file: InfraFileVO) {
  const link = document.createElement('a')
  link.href = downloadUrl(file)
  link.download = file.name || fileName(file)
  link.click()
}

// ── 预览 ──
const previewOpen = ref(false)
const previewFile = ref<InfraFileVO | null>(null)
const previewIndex = ref(0)
function openPreview(file: InfraFileVO) {
  previewFile.value = file
  previewIndex.value = files.value.findIndex(f => f.id === file.id)
  previewOpen.value = true
}

// ── 删除 ──
async function onDelete(file: InfraFileVO) {
  try { await infraFileApi.delete(file.id); message.success('已删除'); refreshAll() }
  catch (e: any) { message.error(e?.message || '删除失败') }
}
async function onBatchDelete() {
  try { await infraFileApi.deleteList(selectedIds.value); selectedIds.value = []; message.success('批量删除完成'); refreshAll() }
  catch (e: any) { message.error(e?.message || '删除失败') }
}

// ── 普通上传 ──
const uploadOpen = ref(false)
const uploadDirectory = ref('')
const uploadCode = ref<string | undefined>(undefined)
const uploadProgress = ref(0)
/** 已配置存储下拉（普通上传 / 压缩包上传共用） */
const storageSelectOptions = computed(() =>
  configs.value.map(c => ({ value: c.code, label: `${c.name}（${FileStorageLabels[c.storage] || c.storage}）` }))
)
function openUpload() {
  uploadOpen.value = true
  uploadProgress.value = 0
  // 默认选中统计卡当前选中的存储配置
  const current = configs.value.find(c => c.id === selectedConfigId.value)
  uploadCode.value = current?.code ?? undefined
}
async function beforeUpload(file: File) {
  const form = new FormData()
  form.append('file', file)
  form.append('directory', uploadDirectory.value)
  form.append('code', uploadCode.value || '')
  try {
    await infraFileApi.upload(form, (p) => { uploadProgress.value = p })
    message.success(`${file.name} 上传成功`)
    refreshAll()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '上传失败')
  }
  uploadProgress.value = 0
  return false
}
async function onGlobalDrop(fileList: FileList) {
  for (const file of Array.from(fileList)) await beforeUpload(file)
}

// ── 压缩包上传与进度 ──
const archiveOpen = ref(false)
const archiveTaskId = ref('')
const archiveProgress = ref<ArchiveExtractProgressVO | null>(null)
let archiveTimer: number | undefined
function openArchiveUpload() {
  archiveOpen.value = true
  archiveTaskId.value = ''
  archiveProgress.value = null
  const current = configs.value.find(c => c.id === selectedConfigId.value)
  uploadCode.value = current?.code ?? undefined
}
async function beforeArchiveUpload(file: File) {
  const form = new FormData()
  form.append('file', file)
  form.append('directory', uploadDirectory.value)
  form.append('code', uploadCode.value || '')
  try {
    const task = await infraFileApi.uploadArchive(form)
    archiveTaskId.value = task.taskId
    startArchivePolling()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '上传失败')
  }
  return false
}
function startArchivePolling() {
  stopArchivePolling()
  archiveTimer = window.setInterval(async () => {
    if (!archiveTaskId.value) return
    try {
      const prog = await infraFileApi.getArchiveProgress(archiveTaskId.value)
      archiveProgress.value = prog
      if (prog.status >= 2) { stopArchivePolling(); refreshAll() }
    } catch { /* 轮询失败不提示，连续失败可后续增强 */ }
  }, 1000)
}
function stopArchivePolling() { if (archiveTimer) { clearInterval(archiveTimer); archiveTimer = undefined } }
const isTerminal = computed(() => {
  const s = archiveProgress.value?.status
  return s !== undefined && s >= 2
})
const archivePercent = computed(() => {
  const p = archiveProgress.value
  return p && p.total ? Math.round((p.done / p.total) * 100) : 0
})
const archiveStatusText = computed(() => ['等待解压', '解压上传中', '已完成', '部分完成', '解压失败', '已取消'][archiveProgress.value?.status ?? 0] || '—')
const archiveStatusColor = computed(() => {
  const s = archiveProgress.value?.status
  return s === 2 ? 'success' : s === 3 ? 'warning' : s === 4 || s === 5 ? 'error' : 'processing'
})
async function onCancelArchive() {
  if (!archiveTaskId.value) return
  try { await infraFileApi.cancelArchive(archiveTaskId.value); message.success('已取消') } catch { /* ignore */ }
  stopArchivePolling()
}
function resetArchive() { stopArchivePolling(); archiveTaskId.value = ''; archiveProgress.value = null; archiveOpen.value = false }
onBeforeUnmount(stopArchivePolling)

// ── 配置管理 ──
/** 编辑/复制弹窗的目标配置；复制（id 置空）表示新建 */
type EditingConfig = Omit<FileConfigVO, 'id'> & { id?: number }
const configFormOpen = ref(false)
const editingConfig = ref<EditingConfig | null>(null)
function openConfigCreate() { editingConfig.value = null; configFormOpen.value = true }
function openConfigEdit(config: FileConfigVO) { editingConfig.value = config; configFormOpen.value = true }
function copyConfig(config: FileConfigVO) {
  editingConfig.value = { ...config, id: undefined, code: `${config.code}_copy`, master: false, name: `${config.name} 副本` }
  configFormOpen.value = true
}
function onConfigSaved() { loadConfigs(); loadStats() }
async function testConfig(config: FileConfigVO) {
  try { const url = await fileConfigApi.test(config.id); message.success(`连接正常：${url}`) }
  catch (e: any) { message.error(e?.response?.data?.detail || '连接失败') }
}
async function setMaster(config: FileConfigVO) {
  try { await fileConfigApi.setMaster(config.id); message.success('已设为主配置'); onConfigSaved() }
  catch (e: any) { message.error(e?.message || '设置失败') }
}
async function onDeleteConfig(config: FileConfigVO) {
  try { await fileConfigApi.delete(config.id); message.success('已删除'); onConfigSaved() }
  catch (e: any) { message.error(e?.response?.data?.detail || '删除失败') }
}
async function onBatchDeleteConfig() {
  try { await fileConfigApi.deleteList(selectedConfigIds.value); selectedConfigIds.value = []; message.success('已删除'); onConfigSaved() }
  catch (e: any) { message.error(e?.response?.data?.detail || '删除失败') }
}
async function exportConfigs() {
  try {
    const configsJson = await fileConfigApi.exportConfig()
    const blob = new Blob([JSON.stringify(configsJson, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'file-configs.json'
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e: any) { message.error(e?.message || '导出失败') }
}
async function importConfigs(file: File) {
  try {
    const text = await file.text()
    const items = JSON.parse(text)
    const created = await fileConfigApi.importConfig(items)
    message.success(`已导入 ${created.length} 个配置`)
    onConfigSaved()
  } catch (e: any) { message.error('导入失败：' + (e?.message || '格式错误')) }
  return false
}
</script>

<style scoped lang="less">
.file-management { width: 100%; height: 100%; display: flex; flex-direction: column; gap: 16px; }
.panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.panel-title { font-size: 20px; font-weight: 600; color: var(--fg); margin: 0 0 6px 0; }
.panel-subtitle { font-size: 13px; color: var(--fg-secondary); }
.header-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.stats-row { display: flex; gap: 14px; flex-wrap: wrap; }
.stats-empty { padding: 20px; font-size: 13px; color: var(--fg-secondary); }
.content-wrapper {
  flex: 1; min-height: 400px; padding: 20px;
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow-sm); overflow: auto;
}
.file-toolbar, .config-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.file-search { width: 260px; }
.file-type-select { width: 150px; }
.file-name-cell { display: inline-flex; align-items: center; gap: 8px; }
.file-thumb-sm { width: 26px; height: 26px; object-fit: cover; border-radius: 4px; }
.file-icon-sm { font-size: 18px; color: var(--accent); }
.upload-zone__icon { font-size: 40px; color: var(--accent); }
.upload-field { margin-top: 16px; margin-bottom: 0; }
.cfg-input {
  width: 100%; height: 32px; padding: 4px 11px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--bg-surface); color: var(--fg); font-size: 14px; outline: none;
  &:focus { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 16%, transparent); }
}
.upload-progress { margin-top: 16px; }
.archive-progress__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.archive-progress__message { margin: 8px 0 16px; font-size: 13px; color: var(--fg-secondary); }
.archive-list { max-height: 180px; overflow: auto; margin-bottom: 12px; }
.archive-list__title { font-size: 12px; font-weight: 600; color: var(--fg-secondary); margin-bottom: 6px; }
.archive-list__row { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 3px 0; color: var(--fg); }
.archive-ok { color: #52c41a; }
.archive-fail { color: #ff4d4f; }
.archive-progress__foot { display: flex; justify-content: flex-end; gap: 10px; }
.content-wrapper :deep(.ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) { font-weight: 600; color: var(--accent); }
</style>
