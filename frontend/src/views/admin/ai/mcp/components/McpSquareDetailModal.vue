<template>
  <a-modal
    :open="visible"
    :title="t('mcpSquare.detailTitle')"
    width="680px"
    :footer="null"
    @cancel="handleCancel"
  >
    <template v-if="template">
      <!-- 标题与状态 -->
      <div class="detail-header">
        <div class="detail-title">
          <span class="title-text">{{ template.name }}</span>
          <a-tag v-if="template.is_installed" color="green">{{ t('mcpSquare.installed') }}</a-tag>
          <a-tag v-if="template.status === 0" color="default">{{ t('mcpSquare.disabledTag') }}</a-tag>
        </div>
        <div class="detail-subtitle">
          <a-tag :color="serviceTypeColor(template.service_type)">
            {{ serviceTypeLabel(template.service_type) }}
          </a-tag>
          <a-tag v-if="template.category" color="blue">{{ categoryLabel(template.category) }}</a-tag>
          <a-tag v-if="template.platform">{{ template.platform }}</a-tag>
          <a-tag v-if="template.version">v{{ template.version }}</a-tag>
        </div>
      </div>

      <a-divider style="margin: 12px 0" />

      <a-descriptions :column="2" bordered size="small">
        <a-descriptions-item label="ID">{{ template.id }}</a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.sort')">{{ template.sort ?? 0 }}</a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.serviceType')">
          {{ serviceTypeLabel(template.service_type) }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.protocolType')">
          {{ protocolTypeFromService(template.service_type) }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.serviceUrl')" :span="2">
          <span class="url-text">{{ template.service_url || '-' }}</span>
        </a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.accessPath')" :span="2">
          <span class="url-text">{{ template.access_path || '-' }}</span>
        </a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.capabilities')" :span="2">
          <template v-if="template.capabilities && template.capabilities.length">
            <a-tag
              v-for="cap in template.capabilities"
              :key="cap"
              color="purple"
              style="margin-bottom: 4px"
            >{{ cap }}</a-tag>
          </template>
          <span v-else>-</span>
        </a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.icon')" :span="2">
          <span class="url-text">{{ template.icon || '-' }}</span>
        </a-descriptions-item>
        <a-descriptions-item :label="t('skillHub.description')" :span="2">
          <div class="description-text">{{ template.description || t('mcpSquare.noDescription') }}</div>
        </a-descriptions-item>
        <a-descriptions-item :label="t('mcpSquare.defaultClientConfig')" :span="2">
          <pre v-if="defaultClientConfigText" class="json-block">{{ defaultClientConfigText }}</pre>
          <span v-else>-</span>
        </a-descriptions-item>
        <a-descriptions-item v-if="template.created_at" :label="t('skillHub.createdAt')">
          {{ template.created_at }}
        </a-descriptions-item>
        <a-descriptions-item v-if="template.updated_at" :label="t('mcpSquare.updatedAt')">
          {{ template.updated_at }}
        </a-descriptions-item>
      </a-descriptions>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { McpSquareTemplate } from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  template: McpSquareTemplate | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const { t } = useI18n()

const defaultClientConfigText = computed(() => {
  if (!props.template?.default_client_config) return ''
  try {
    return JSON.stringify(props.template.default_client_config, null, 2)
  } catch {
    return String(props.template.default_client_config)
  }
})

// 服务类型/协议类型为代码值，保留原映射
const SERVICE_TYPE_LABEL: Record<string, string> = {
  nacos2: 'Nacos 2.x',
  nacos3: 'Nacos 3.x',
  http: 'HTTP',
  sse: 'SSE',
}
// 与后端 PROTOCOL_TYPE_MAP 保持一致
const PROTOCOL_TYPE_MAP: Record<string, string> = {
  nacos2: 'Nacos Registry',
  nacos3: 'Nacos Registry',
  http: 'Streamable HTTP',
  sse: 'SSE',
}

function serviceTypeLabel(type: string): string {
  return SERVICE_TYPE_LABEL[type] || type || '-'
}
function serviceTypeColor(type: string): string {
  const map: Record<string, string> = {
    nacos2: 'blue',
    nacos3: 'geekblue',
    http: 'cyan',
    sse: 'green',
  }
  return map[type] || 'default'
}
function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    finance: t('mcpSquare.catFinance'),
    sales: t('mcpSquare.catSales'),
    legal: t('mcpSquare.catLegal'),
    office: t('mcpSquare.catOffice'),
    education: t('mcpSquare.catEducation'),
  }
  return map[cat] || cat
}
function protocolTypeFromService(svc: string): string {
  return PROTOCOL_TYPE_MAP[svc] || '-'
}

function handleCancel() {
  emit('update:visible', false)
}
</script>

<style scoped>
.detail-header {
  padding: 0 4px;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.title-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--fg);
}
.detail-subtitle {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.url-text {
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--fg-secondary);
}
.description-text {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--fg-secondary);
  line-height: 1.6;
}
.json-block {
  background: var(--bg-input);
  border-radius: 4px;
  padding: 8px 10px;
  margin: 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--fg);
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
