<template>
  <a-modal
    :open="visible"
    :title="t('mcpSquare.installTitle')"
    width="600px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <template v-if="template">
      <!-- 模板信息摘要 -->
      <div class="install-template-info">
        <div class="template-header">
          <span class="template-name">{{ template.name }}</span>
          <a-tag>{{ serviceTypeLabel(template.service_type) }}</a-tag>
          <a-tag v-if="template.category">{{ categoryLabel(template.category) }}</a-tag>
        </div>
        <p class="template-desc">{{ template.description || t('mcpSquare.noDescription') }}</p>
      </div>

      <a-divider style="margin: 12px 0" />

      <!-- 安装参数表单 -->
      <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('mcpSquare.serviceName')">
          <a-input v-model:value="form.name" :placeholder="template.name" />
        </a-form-item>

        <!-- HTTP/SSE 字段 -->
        <template v-if="isHttpOrSse">
          <a-form-item :label="t('mcpSquare.serviceUrl')" required>
            <a-input v-model:value="form.service_url" :placeholder="template.service_url || 'https://...'" />
          </a-form-item>
          <a-form-item :label="t('mcpSquare.accessPath')">
            <a-input v-model:value="form.access_path" :placeholder="template.access_path || '/mcp'" />
          </a-form-item>
          <a-form-item label="API Key">
            <a-input-password v-model:value="form.api_key" :placeholder="t('mcpSquare.authKeyOptional')" />
          </a-form-item>
        </template>

        <!-- Nacos 字段 -->
        <template v-if="isNacos">
          <a-form-item :label="t('mcpSquare.nacosUrl')" required>
            <a-input v-model:value="form.service_url" :placeholder="template.service_url || 'http://nacos:8848'" />
          </a-form-item>
          <a-form-item :label="t('mcpSquare.serviceName')" required>
            <a-input v-model:value="form.service_name" :placeholder="t('mcpSquare.nacosServiceNamePlaceholder')" />
          </a-form-item>
          <a-form-item :label="t('mcpSquare.namespace')">
            <a-input v-model:value="form.namespace" :placeholder="t('mcpSquare.namespaceOptional')" />
          </a-form-item>
          <a-form-item :label="t('mcpSquare.group')">
            <a-input v-model:value="form.group_key" :placeholder="t('mcpSquare.groupOptional')" />
          </a-form-item>
          <a-form-item label="API Key">
            <a-input-password v-model:value="form.api_key" :placeholder="t('mcpSquare.authKeyOptional')" />
          </a-form-item>
        </template>
      </a-form>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  installMcpSquare,
  type McpSquareTemplate,
  type McpSquareInstallData,
} from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  template: McpSquareTemplate | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const { t } = useI18n()
const submitting = ref(false)

const defaultForm = (): McpSquareInstallData => ({
  template_id: 0,
  name: '',
  service_url: '',
  api_key: '',
  access_path: '',
  service_name: '',
  namespace: '',
  group_key: '',
})

const form = reactive<McpSquareInstallData>(defaultForm())

const isNacos = computed(() => {
  const st = props.template?.service_type
  return st === 'nacos2' || st === 'nacos3'
})
const isHttpOrSse = computed(() => {
  const st = props.template?.service_type
  return st === 'http' || st === 'sse'
})

// 服务类型为代码值，保留原映射
const SERVICE_TYPE_LABEL: Record<string, string> = {
  nacos2: 'Nacos 2.x',
  nacos3: 'Nacos 3.x',
  http: 'HTTP',
  sse: 'SSE',
}
function serviceTypeLabel(type?: string | null): string {
  if (!type) return '-'
  return SERVICE_TYPE_LABEL[type] || type
}
function categoryLabel(c?: string | null): string {
  if (!c) return ''
  const map: Record<string, string> = {
    finance: t('mcpSquare.catFinance'),
    sales: t('mcpSquare.catSales'),
    legal: t('mcpSquare.catLegal'),
    office: t('mcpSquare.catOffice'),
    education: t('mcpSquare.catEducation'),
  }
  return map[c] || c
}

watch(() => props.visible, (val) => {
  if (val && props.template) {
    const tpl = props.template
    Object.assign(form, {
      template_id: tpl.id,
      name: '',
      service_url: tpl.service_url || '',
      api_key: '',
      access_path: tpl.access_path || '',
      service_name: '',
      namespace: '',
      group_key: '',
    })
  } else {
    Object.assign(form, defaultForm())
  }
})

async function handleSubmit() {
  if (!props.template) return

  // 校验必填
  if (isHttpOrSse.value && !form.service_url) {
    message.warning(t('mcpSquare.serviceUrlRequired'))
    return
  }
  if (isNacos.value && (!form.service_url || !form.service_name)) {
    message.warning(t('mcpSquare.nacosRequired'))
    return
  }

  submitting.value = true
  try {
    await installMcpSquare({ ...form })
    message.success(t('mcpSquare.installSuccess'))
    emit('update:visible', false)
    emit('success')
  } catch {
    message.error(t('mcpSquare.installFailed'))
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  emit('update:visible', false)
}
</script>

<style scoped>
.install-template-info {
  padding: 0 4px;
}
.template-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.template-name {
  font-size: 15px;
  font-weight: 600;
}
.template-desc {
  color: var(--fg-secondary);
  font-size: 13px;
  margin: 0;
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
