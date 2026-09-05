<template>
  <a-modal
    :open="visible"
    title="安装 MCP 服务"
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
        <p class="template-desc">{{ template.description || '暂无描述' }}</p>
      </div>

      <a-divider style="margin: 12px 0" />

      <!-- 安装参数表单 -->
      <a-form :model="form" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="服务名称">
          <a-input v-model:value="form.name" :placeholder="template.name" />
        </a-form-item>

        <!-- HTTP/SSE 字段 -->
        <template v-if="isHttpOrSse">
          <a-form-item label="服务地址" required>
            <a-input v-model:value="form.service_url" :placeholder="template.service_url || 'https://...'" />
          </a-form-item>
          <a-form-item label="访问路径">
            <a-input v-model:value="form.access_path" :placeholder="template.access_path || '/mcp'" />
          </a-form-item>
          <a-form-item label="API Key">
            <a-input-password v-model:value="form.api_key" placeholder="鉴权密钥（选填）" />
          </a-form-item>
        </template>

        <!-- Nacos 字段 -->
        <template v-if="isNacos">
          <a-form-item label="Nacos 地址" required>
            <a-input v-model:value="form.service_url" :placeholder="template.service_url || 'http://nacos:8848'" />
          </a-form-item>
          <a-form-item label="服务名" required>
            <a-input v-model:value="form.service_name" placeholder="Nacos 注册的服务名" />
          </a-form-item>
          <a-form-item label="命名空间">
            <a-input v-model:value="form.namespace" placeholder="namespace（选填）" />
          </a-form-item>
          <a-form-item label="分组">
            <a-input v-model:value="form.group_key" placeholder="group（选填）" />
          </a-form-item>
          <a-form-item label="API Key">
            <a-input-password v-model:value="form.api_key" placeholder="鉴权密钥（选填）" />
          </a-form-item>
        </template>
      </a-form>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
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
  const t = props.template?.service_type
  return t === 'nacos2' || t === 'nacos3'
})
const isHttpOrSse = computed(() => {
  const t = props.template?.service_type
  return t === 'http' || t === 'sse'
})

const SERVICE_TYPE_LABEL: Record<string, string> = {
  nacos2: 'Nacos 2.x',
  nacos3: 'Nacos 3.x',
  http: 'HTTP',
  sse: 'SSE',
}
const CATEGORY_LABEL: Record<string, string> = {
  finance: '金融投资',
  sales: '销售营销',
  legal: '法律合规',
  office: '办公OA',
  education: '教育学习',
}
function serviceTypeLabel(t?: string | null): string {
  if (!t) return '-'
  return SERVICE_TYPE_LABEL[t] || t
}
function categoryLabel(c?: string | null): string {
  if (!c) return ''
  return CATEGORY_LABEL[c] || c
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
    message.warning('请填写服务地址')
    return
  }
  if (isNacos.value && (!form.service_url || !form.service_name)) {
    message.warning('请填写 Nacos 地址和服务名')
    return
  }

  submitting.value = true
  try {
    await installMcpSquare({ ...form })
    message.success('安装成功')
    emit('update:visible', false)
    emit('success')
  } catch {
    message.error('安装失败')
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
  color: #666;
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
