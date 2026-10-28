<template>
  <div class="src-mgr">
    <!-- 工具栏常驻：StateWrapper 在 loading/error/empty 时会隐藏默认插槽，
         若包在插槽内，空数据状态下将看不到「新建」按钮 -->
    <div class="src-mgr__toolbar">
      <a-button type="primary" @click="openForm()">
        <PlusOutlined /> {{ t('kbMgmt.common.create') }}
      </a-button>
      <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
    </div>

    <StateWrapper :loading="loading" :error="error" :empty="!loading && !error && !sources.length" @retry="load">
      <DataTable
        :columns="columns"
        :data-source="sources"
        :loading="loading"
        row-key="id"
        :page-visible="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'source_type'">
            <!-- 显示与下拉同源：均取自字典 data_source_type 启用项 -->
            <a-tag :color="typeMeta(record.source_type).color || 'default'">
              {{ typeMeta(record.source_type).item_name || record.source_type }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'addr'">
            <span v-if="isExcel(record.source_type)" class="muted">{{ t('kbMgmt.ds.excelLocal') }}</span>
            <span v-else>{{ record.host }}:{{ record.port }}</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'online' ? 'success' : 'default'">
              {{ record.status === 'online' ? t('kbMgmt.common.online') : t('kbMgmt.common.offline') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'has_password'">
            <a-tag v-if="record.has_password" color="blue">●</a-tag>
            <span v-else class="muted">—</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" @click="testRow(record)"><ThunderboltOutlined /> {{ t('kbMgmt.ds.testConn') }}</a-button>
            <a-button v-if="isExcel(record.source_type)" size="small" @click="pickFile(record)">
              <UploadOutlined /> {{ t('kbMgmt.ds.uploadFile') }}
            </a-button>
            <a-button size="small" @click="openImport(record)"><ImportOutlined /> {{ t('kbMgmt.ds.importMeta') }}</a-button>
            <a-dropdown>
              <a-button size="small">{{ t('kbMgmt.ds.more') }} <DownOutlined /></a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="edit" @click="openForm(record)">{{ t('kbMgmt.common.edit') }}</a-menu-item>
                  <a-menu-item key="del">
                    <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
                      <span style="color:#d4380d">{{ t('kbMgmt.common.delete') }}</span>
                    </a-popconfirm>
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>
        </template>
      </DataTable>
    </StateWrapper>

    <!-- 新建 / 编辑：字段随类型（字典 extra_data.fields）动态渲染；
         水平布局（label 与输入框同行）+ 行高压缩，降低弹窗整体高度 -->
    <a-modal
      v-model:open="formOpen"
      :title="form.id ? t('kbMgmt.common.edit') : t('kbMgmt.common.create')"
      :confirm-loading="saving"
      @ok="save"
    >
      <a-form
        :model="form"
        layout="horizontal"
        :label-col="{ style: { width: '96px' } }"
        :wrapper-col="{ flex: 1 }"
        class="ds-form"
      >
        <a-form-item :label="t('kbMgmt.common.name')" required>
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.common.type')" required>
          <a-select
            v-model:value="form.source_type"
            :disabled="!!form.id"
            :placeholder="t('kbMgmt.ds.selectType')"
            @change="onTypeChange"
          >
            <a-select-option v-for="ty in types" :key="ty.code" :value="ty.code">
              {{ ty.item_name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <template v-if="!isExcel(form.source_type)">
          <a-form-item
            v-for="f in currentFields"
            :key="f.key"
            :label="fieldLabel(f)"
            :required="!!f.required"
          >
            <a-input
              v-if="f.type === 'string'"
              :value="fieldValue(f)"
              @update:value="(v: any) => setFieldValue(f, v)"
            />
            <a-input-number
              v-else-if="f.type === 'number'"
              :value="fieldValue(f)"
              style="width:100%"
              @update:value="(v: any) => setFieldValue(f, v)"
            />
            <a-input-password
              v-else-if="f.type === 'password'"
              :value="fieldValue(f)"
              :placeholder="form.id ? t('kbMgmt.ds.passwordKeepHint') : t('kbMgmt.ds.passwordHint')"
              @update:value="(v: any) => setFieldValue(f, v)"
            />
            <a-select
              v-else-if="f.type === 'select'"
              :value="fieldValue(f)"
              @update:value="(v: any) => setFieldValue(f, v)"
            >
              <a-select-option v-for="opt in f.options || []" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-select-option>
            </a-select>
            <a-switch
              v-else-if="f.type === 'switch'"
              :checked="!!fieldValue(f)"
              @update:checked="(v: any) => setFieldValue(f, v)"
            />
            <a-input v-else :value="fieldValue(f)" @update:value="(v: any) => setFieldValue(f, v)" />
          </a-form-item>
        </template>
        <a-alert v-else type="info" show-icon :message="t('kbMgmt.ds.excelCreateTip')" />

        <div v-if="!isExcel(form.source_type)" class="ds-form__actions">
          <a-button size="small" :loading="testing" @click="draftTest"><ThunderboltOutlined /> {{ t('kbMgmt.ds.testConn') }}</a-button>
        </div>
      </a-form>
    </a-modal>

    <!-- 元数据导入：Excel 型上传落库；其余类型远端浏览选表导入（SQLBot 式） -->
    <a-modal v-model:open="importOpen" :title="t('kbMgmt.ds.importMeta')" width="720px" :footer="null">
      <template v-if="importTarget && isExcel(importTarget.source_type)">
        <a-upload-dragger
          :file-list="[]"
          :before-upload="onExcelUpload"
          :accept="'.csv,.xlsx,.xls'"
        >
          <p class="ant-upload-drag-icon"><UploadOutlined /></p>
          <p class="ant-upload-text">{{ t('kbMgmt.ds.excelDropHint') }}</p>
          <p class="ant-upload-hint">{{ t('kbMgmt.ds.excelDropSub') }}</p>
        </a-upload-dragger>
      </template>
      <template v-else>
        <div class="imp-bar">
          <a-select
            v-model:value="selectedDb"
            style="width:220px"
            :placeholder="t('kbMgmt.ds.selectDb')"
            :loading="loadingDbs"
            @change="onDbChange"
          >
            <a-select-option v-for="db in databases" :key="db" :value="db">{{ db }}</a-select-option>
          </a-select>
          <!-- PG 族三级：数据库→schema→表；其余族保持数据库→表 -->
          <a-select
            v-if="needsSchema"
            v-model:value="selectedSchema"
            style="width:180px"
            :placeholder="t('kbMgmt.ds.selectSchema')"
            :loading="loadingSchemas"
            @change="onSchemaChange"
          >
            <a-select-option v-for="s in schemas" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
          <a-checkbox v-model:checked="withProfile">{{ t('kbMgmt.ds.withProfile') }}</a-checkbox>
          <a-button
            type="primary"
            :disabled="!selectedTables.length || !selectedDb || (needsSchema && !selectedSchema)"
            :loading="importing"
            @click="doImport"
          >{{ t('kbMgmt.ds.importSelected', { n: selectedTables.length }) }}</a-button>
        </div>
        <a-table
          :columns="tablePickColumns"
          :data-source="remoteTables"
          :loading="loadingTables"
          row-key="name"
          size="small"
          :pagination="false"
          :scroll="{ y: 360 }"
          :row-selection="{ selectedRowKeys: selectedTables, onChange: (keys: any) => (selectedTables = keys) }"
        />
      </template>
    </a-modal>

    <input ref="fileInputRef" type="file" accept=".csv,.xlsx,.xls" style="display:none" @change="onPickedFile" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, ReloadOutlined, ThunderboltOutlined,
  UploadOutlined, ImportOutlined, DownOutlined,
} from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import StateWrapper from '@/components/common/StateWrapper.vue'
import * as api from '@/api/dataops'

const { t } = useI18n()

/** 顶层列（走 DataSourceCreate 直接字段）；其余字段进 config 字典 */
const TOP_LEVEL_KEYS = new Set(['host', 'port', 'username', 'password', 'database', 'charset'])

const sources = ref<any[]>([])
const types = ref<any[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const formOpen = ref(false)
const saving = ref(false)
const testing = ref(false)
const form = ref<any>({ config: {} })

// 类型字典 {item_code: 元数据}
const typeIndex = computed<Record<string, any>>(() => {
  const m: Record<string, any> = {}
  for (const ty of types.value) m[ty.code] = ty
  return m
})
function typeMeta(code: string) {
  return typeIndex.value[code] || {}
}
function isExcel(code: string) {
  return typeMeta(code).family === 'excel' || code === 'excel'
}

const columns = computed(() => [
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.common.type'), dataIndex: 'source_type', key: 'source_type', width: 130 },
  { title: t('kbMgmt.ds.address'), key: 'addr' },
  { title: t('kbMgmt.ds.defaultDb'), dataIndex: 'database', key: 'database' },
  { title: t('kbMgmt.common.status'), key: 'status', width: 90 },
  { title: t('kbMgmt.ds.password'), key: 'has_password', width: 70 },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 320 },
])

/** 当前类型的动态字段（剔除 upload：Excel 走独立上传链路） */
const currentFields = computed(() =>
  (typeMeta(form.value.source_type).fields || []).filter((f: any) => f.type !== 'upload')
)

function fieldLabel(f: any) {
  return f.label_key ? t(f.label_key) : (f.label || f.key)
}
function fieldValue(f: any) {
  if (TOP_LEVEL_KEYS.has(f.key)) return form.value[f.key]
  return form.value.config?.[f.key]
}
function setFieldValue(f: any, val: any) {
  if (TOP_LEVEL_KEYS.has(f.key)) form.value[f.key] = val
  else form.value.config[f.key] = val
}

async function loadTypes() {
  try {
    const r: any = await api.listSourceTypes()
    types.value = r.data || r || []
  } catch (e: any) {
    // 类型字典加载失败不阻断列表；保存时后端仍有兜底校验
    console.error('load source types failed', e)
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const r: any = await api.listSources()
    sources.value = r.data || r || []
  } catch (e: any) {
    error.value = e?.message || t('kbMgmt.common.error')
  } finally {
    loading.value = false
  }
}

/** 依据类型默认端口与字段默认值初始化连接参数 */
function applyTypeDefaults(code: string) {
  const meta = typeMeta(code)
  form.value.port = meta.default_port ?? 0
  const cfg: Record<string, any> = {}
  for (const f of meta.fields || []) {
    if (!TOP_LEVEL_KEYS.has(f.key) && f.default !== undefined) cfg[f.key] = f.default
  }
  form.value.config = cfg
}

function onTypeChange(code: string) {
  applyTypeDefaults(code)
}

function openForm(row?: any) {
  if (row) {
    form.value = { ...row, config: { ...(row.config || {}) }, password: '' }
  } else {
    const first = types.value[0]?.code || 'mysql'
    form.value = { name: '', source_type: first, host: '', port: 0, username: '', database: '', charset: 'utf8mb4', config: {} }
    applyTypeDefaults(first)
  }
  formOpen.value = true
}

function buildPayload() {
  const f = form.value
  const payload: any = {
    name: f.name,
    source_type: f.source_type,
    host: isExcel(f.source_type) ? '' : (f.host || ''),
    port: isExcel(f.source_type) ? 0 : (Number(f.port) || 0),
    username: f.username || null,
    database: f.database || null,
    charset: f.charset || 'utf8mb4',
    config: f.config || {},
  }
  if (f.password) payload.password = f.password
  return payload
}

async function save() {
  if (!(form.value.name || '').trim()) {
    message.warning(t('kbMgmt.ds.nameRequired'))
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (form.value.id) await api.updateSource(form.value.id, payload)
    else await api.createSource(payload)
    message.success(t('kbMgmt.ds.saveSuccess'))
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('kbMgmt.ds.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function draftTest() {
  testing.value = true
  try {
    const r: any = await api.testSourceDraft(buildPayload())
    if (r?.ok) message.success(t('kbMgmt.ds.testOk'))
    else message.error(r?.error || t('kbMgmt.ds.testFailed'))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('kbMgmt.ds.testFailed'))
  } finally {
    testing.value = false
  }
}

async function testRow(row: any) {
  try {
    const r: any = await api.testSource(row.id)
    if (r?.ok) message.success(t('kbMgmt.ds.testOk'))
    else message.error(r?.error || t('kbMgmt.ds.testFailed'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.ds.testFailed'))
  }
}

async function remove(row: any) {
  try {
    await api.deleteSource(row.id)
    message.success(t('kbMgmt.common.deleted'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

// ── Excel 快捷上传（行按钮：先选源，再触发隐藏 input） ──────────────
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadTarget = ref<any>(null)
function pickFile(row: any) {
  uploadTarget.value = row
  fileInputRef.value?.click()
}
async function onPickedFile(evt: Event) {
  const input = evt.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !uploadTarget.value) return
  await runIngest(uploadTarget.value, file)
}

// ── 导入元数据弹窗 ──────────────────────────────────────────────────
const importOpen = ref(false)
const importTarget = ref<any>(null)
const databases = ref<string[]>([])
const loadingDbs = ref(false)
const selectedDb = ref<string | undefined>(undefined)
const schemas = ref<string[]>([])
const loadingSchemas = ref(false)
const selectedSchema = ref<string | undefined>(undefined)
const remoteTables = ref<any[]>([])
const loadingTables = ref(false)
const selectedTables = ref<string[]>([])
const withProfile = ref(false)
const importing = ref(false)

/** PG 族（postgresql/kingbase）才有“物理库→schema→表”三级作用域 */
const needsSchema = computed(() => {
  const code = importTarget.value?.source_type || ''
  return typeMeta(code).family === 'pg' || code === 'postgresql' || code === 'kingbase'
})

const tablePickColumns = computed(() => [
  { title: t('kbMgmt.ds.tableName'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.ds.tableType'), dataIndex: 'table_type', key: 'table_type', width: 120 },
  { title: t('kbMgmt.ds.tableComment'), dataIndex: 'comment', key: 'comment' },
  { title: t('kbMgmt.ds.rowCount'), dataIndex: 'row_count', key: 'row_count', width: 100 },
])

async function openImport(row: any) {
  importTarget.value = row
  selectedDb.value = undefined
  selectedSchema.value = undefined
  databases.value = []
  schemas.value = []
  remoteTables.value = []
  selectedTables.value = []
  withProfile.value = false
  importOpen.value = true
  if (isExcel(row.source_type)) return
  loadingDbs.value = true
  try {
    const r: any = await api.listRemoteDatabases(row.id)
    databases.value = r.data || r || []
    if (databases.value.length === 1) {
      selectedDb.value = databases.value[0]
      onDbChange()
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.ds.remoteFail'))
  } finally {
    loadingDbs.value = false
  }
}

/** 选库：PG 族去重连列 schema（表列表等选完 schema 再载）；其余族直接列表 */
async function onDbChange() {
  selectedSchema.value = undefined
  schemas.value = []
  selectedTables.value = []
  remoteTables.value = []
  if (!selectedDb.value || !importTarget.value) return
  if (needsSchema.value) {
    loadingSchemas.value = true
    try {
      const r: any = await api.listRemoteSchemas(importTarget.value.id, selectedDb.value)
      schemas.value = r.data || r || []
      if (schemas.value.length === 1) {
        selectedSchema.value = schemas.value[0]
        onSchemaChange()
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('kbMgmt.ds.remoteFail'))
    } finally {
      loadingSchemas.value = false
    }
  } else {
    await loadRemoteTables()
  }
}

async function onSchemaChange() {
  selectedTables.value = []
  remoteTables.value = []
  await loadRemoteTables()
}

async function loadRemoteTables() {
  if (!selectedDb.value || !importTarget.value) return
  loadingTables.value = true
  try {
    const r: any = await api.listRemoteTables(
      importTarget.value.id, selectedDb.value, needsSchema.value ? selectedSchema.value : undefined)
    remoteTables.value = r.data || r || []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.ds.remoteFail'))
  } finally {
    loadingTables.value = false
  }
}

async function doImport() {
  if (!importTarget.value || !selectedDb.value || !selectedTables.value.length) return
  importing.value = true
  try {
    const r: any = await api.importTables(importTarget.value.id, {
      database: selectedDb.value,
      schema: needsSchema.value ? selectedSchema.value : undefined,
      tables: selectedTables.value,
      with_profile: withProfile.value,
    })
    const stat = r.data || r || {}
    message.success(t('kbMgmt.ds.importDone', { n: stat.imported ?? 0 }))
    importOpen.value = false
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.ds.importFailed'))
  } finally {
    importing.value = false
  }
}

/** Excel 上传入库（落隔离 schema）：成功后可继续走选表导入 */
async function onExcelUpload(file: File) {
  if (importTarget.value) await runIngest(importTarget.value, file)
  return false // 阻止 a-upload 自带请求
}

async function runIngest(row: any, file: File) {
  try {
    const r: any = await api.ingestExcel(row.id, file)
    const stat = r.data || r || {}
    const n = (stat.tables || []).length
    message.success(t('kbMgmt.ds.uploadOk', { n }))
    if (importOpen.value && importTarget.value?.id === row.id) openImport(row)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.ds.uploadFailed'))
  }
}

onMounted(() => {
  loadTypes()
  load()
})
</script>

<style scoped>
.src-mgr__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.muted { color: var(--fg-muted); }
.imp-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
/* 表单行高压缩：label 与输入框同行后进一步降低弹窗高度 */
.ds-form :deep(.ant-form-item) { margin-bottom: 10px; }
.ds-form :deep(.ant-form-item-label) { flex: 0 0 96px; }
.ds-form :deep(.ant-form-item-label > label) { height: auto; }
.ds-form__actions { margin-top: 2px; }
</style>
