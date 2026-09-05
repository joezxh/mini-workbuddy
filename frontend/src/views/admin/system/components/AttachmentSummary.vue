<template>
  <div class="attachment-summary" :class="{ detailed }">
    <!-- 无附件 -->
    <a-tag v-if="!hasAny" color="default" size="small">
      <PaperClipOutlined /> 无
    </a-tag>

    <!-- db_id + uuid 都有 -->
    <template v-else>
      <div v-if="dbIds.length" class="att-row">
        <a-tag color="blue" size="small">
          <FileTextOutlined /> DB ID × {{ dbIds.length }}
        </a-tag>
        <a-tooltip v-if="detailed" title="复制 db_id 列表">
          <a-tag
            v-for="id in dbIds"
            :key="id"
            color="geekblue"
            size="small"
            class="db-id-tag"
          >
            #{{ id }}
          </a-tag>
        </a-tooltip>
      </div>

      <div v-if="uuidIds.length" class="att-row">
        <a-tag color="purple" size="small">
          <LinkOutlined /> UUID × {{ uuidIds.length }}
        </a-tag>
        <a-tooltip v-if="detailed" title="UUID 字符串">
          <code
            v-for="u in uuidIds.slice(0, 3)"
            :key="u"
            class="uuid-chip"
          >{{ truncate(u, 12) }}</code>
          <a-tag v-if="uuidIds.length > 3" color="default" size="small">
            +{{ uuidIds.length - 3 }}
          </a-tag>
        </a-tooltip>
      </div>

      <!-- 单文件 -->
      <a-tag v-if="singleFileId" color="cyan" size="small">
        <FileExcelOutlined /> {{ singleFileId }}
      </a-tag>

      <!-- 上传场景 -->
      <a-tag v-if="uploadFilename" color="orange" size="small">
        <CloudUploadOutlined /> {{ uploadFilename }}
      </a-tag>
      <a-tag v-if="uploadSize" color="default" size="small">
        {{ formatSize(uploadSize) }}
      </a-tag>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  PaperClipOutlined,
  FileTextOutlined,
  LinkOutlined,
  FileExcelOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons-vue'

const props = withDefaults(defineProps<{
  newData?: {
    attachment_info?: {
      file_db_ids?: number[]
      file_db_id_count?: number
      file_ids?: string[]
      file_id_count?: number
      file_id?: string
    }
  } | null
  requestParams?: Record<string, any> | null
  /** 是否显示完整明细（弹窗内） */
  detailed?: boolean
}>(), {
  detailed: false,
})

const att = computed(() => props.newData?.attachment_info)
const params = computed(() => props.requestParams || {})

const dbIds = computed<number[]>(() =>
  att.value?.file_db_ids
  || (Array.isArray(params.value.file_db_ids) ? params.value.file_db_ids.filter((x: any) => !isNaN(Number(x))).map(Number) : [])
)

const uuidIds = computed<string[]>(() =>
  att.value?.file_ids
  || (Array.isArray(params.value.file_ids) ? params.value.file_ids : [])
)

const singleFileId = computed<string>(() =>
  att.value?.file_id || (params.value.file_id ? String(params.value.file_id) : '')
)

const uploadFilename = computed<string>(() => {
  if (params.value._upload && params.value.filename) return params.value.filename
  return ''
})

const uploadSize = computed<number>(() => {
  if (params.value._upload && params.value.content_length) return Number(params.value.content_length)
  return 0
})

const hasAny = computed(() =>
  dbIds.value.length > 0
  || uuidIds.value.length > 0
  || !!singleFileId.value
  || !!uploadFilename.value
)

function truncate(s: string, n: number): string {
  if (s.length <= n) return s
  return s.slice(0, n) + '…'
}

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped lang="less">
.attachment-summary {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;

  &.detailed {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}

.att-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.db-id-tag {
  font-family: 'SFMono-Regular', Consolas, monospace;
}

.uuid-chip {
  display: inline-block;
  font-size: 10px;
  background: var(--accent-soft);
  border: 1px solid var(--border-strong);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 4px;
  font-family: monospace;
}
</style>