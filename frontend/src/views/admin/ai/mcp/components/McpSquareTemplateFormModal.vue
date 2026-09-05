<template>
  <a-modal
    :open="visible"
    :title="isEdit ? '编辑 MCP 广场模板' : '新增 MCP 广场模板'"
    width="720px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :label-col="{ span: 5 }"
      :wrapper-col="{ span: 18 }"
    >
      <a-form-item label="模板名称" name="name">
        <a-input v-model:value="form.name" placeholder="请输入模板名称" :max-length="100" show-count />
      </a-form-item>

      <a-form-item label="服务类型" name="service_type">
        <a-select v-model:value="form.service_type" placeholder="选择服务类型">
          <a-select-option value="nacos2">Nacos 2.x</a-select-option>
          <a-select-option value="nacos3">Nacos 3.x</a-select-option>
          <a-select-option value="http">HTTP</a-select-option>
          <a-select-option value="sse">SSE</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="分类" name="category">
        <a-select v-model:value="form.category" placeholder="选择分类" allow-clear>
          <a-select-option value="finance">金融投资</a-select-option>
          <a-select-option value="sales">销售营销</a-select-option>
          <a-select-option value="legal">法律合规</a-select-option>
          <a-select-option value="office">办公OA</a-select-option>
          <a-select-option value="education">教育学习</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="平台" name="platform">
        <a-input v-model:value="form.platform" placeholder="如 local / remote" :max-length="50" />
      </a-form-item>

      <a-form-item label="图标" name="icon">
        <a-input v-model:value="form.icon" placeholder="图标标识或 URL" :max-length="200" />
      </a-form-item>

      <a-form-item label="协议版本" name="version">
        <a-input v-model:value="form.version" placeholder="MCP 协议版本" :max-length="20" />
      </a-form-item>

      <a-form-item label="服务地址" name="service_url">
        <a-input v-model:value="form.service_url" placeholder="服务地址模板（可被安装时覆盖）" :max-length="500" />
      </a-form-item>

      <a-form-item label="访问路径" name="access_path">
        <a-input v-model:value="form.access_path" placeholder="如 /mcp/v1" :max-length="500" />
      </a-form-item>

      <a-form-item label="能力列表" name="capabilities">
        <a-select
          v-model:value="form.capabilities"
          mode="multiple"
          placeholder="选择该模板声明的能力"
          allow-clear
        >
          <a-select-option value="tools">Tools</a-select-option>
          <a-select-option value="resources">Resources</a-select-option>
          <a-select-option value="prompts">Prompts</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="描述" name="description">
        <a-textarea
          v-model:value="form.description"
          :rows="3"
          placeholder="模板描述（最多 2000 字）"
          :max-length="2000"
          show-count
        />
      </a-form-item>

      <a-form-item label="默认客户端" name="default_client_config">
        <a-textarea
          v-model:value="defaultClientConfigText"
          :rows="5"
          placeholder='JSON 格式，例如：{ "client_type": "http", "mcp_type": "tool" }'
        />
      </a-form-item>

      <a-form-item label="排序" name="sort">
        <a-input-number v-model:value="form.sort" :min="0" :max="9999" style="width: 160px" />
      </a-form-item>

      <a-form-item label="状态" name="status">
        <a-radio-group v-model:value="form.status">
          <a-radio :value="1">启用</a-radio>
          <a-radio :value="0">禁用</a-radio>
        </a-radio-group>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { Rule } from 'ant-design-vue/es/form'
import {
  createMcpSquare,
  updateMcpSquare,
  type McpSquareTemplate,
} from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  record: McpSquareTemplate | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isEdit = computed(() => !!props.record)
const submitting = ref(false)
const formRef = ref()

const defaultForm = () => ({
  name: '',
  service_type: 'http' as 'nacos2' | 'nacos3' | 'http' | 'sse',
  platform: '',
  category: undefined as string | undefined,
  icon: '',
  version: '',
  service_url: '',
  access_path: '',
  capabilities: [] as string[],
  description: '',
  sort: 0,
  status: 1 as number,
})

const form = reactive(defaultForm())
const defaultClientConfigText = ref('')

const rules: Record<string, Rule[]> = {
  name: [
    { required: true, message: '请输入模板名称', trigger: 'blur' },
    { max: 100, message: '名称不能超过 100 字符', trigger: 'blur' },
  ],
  service_type: [{ required: true, message: '请选择服务类型', trigger: 'change' }],
  sort: [{ type: 'number', message: '排序必须为数字', trigger: 'blur' }],
}

watch(() => props.visible, (val) => {
  if (val && props.record) {
    Object.assign(form, {
      name: props.record.name || '',
      service_type: (props.record.service_type as 'nacos2' | 'nacos3' | 'http' | 'sse') || 'http',
      platform: props.record.platform || '',
      category: props.record.category || undefined,
      icon: props.record.icon || '',
      version: props.record.version || '',
      service_url: props.record.service_url || '',
      access_path: props.record.access_path || '',
      capabilities: props.record.capabilities || [],
      description: props.record.description || '',
      sort: props.record.sort ?? 0,
      status: props.record.status ?? 1,
    })
    defaultClientConfigText.value = props.record.default_client_config
      ? JSON.stringify(props.record.default_client_config, null, 2)
      : ''
  } else if (val) {
    Object.assign(form, defaultForm())
    defaultClientConfigText.value = ''
  }
})

function parseDefaultClientConfig(): Record<string, any> | null {
  const text = defaultClientConfigText.value.trim()
  if (!text) return null
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed
    }
    message.error('默认客户端配置必须是 JSON 对象')
    return undefined as any
  } catch {
    message.error('默认客户端配置 JSON 解析失败')
    return undefined as any
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate?.()
  } catch {
    return
  }
  const cfg = parseDefaultClientConfig()
  if (defaultClientConfigText.value.trim() && cfg === undefined) {
    // 解析失败，终止提交
    return
  }

  submitting.value = true
  try {
    const payload: any = {
      name: form.name,
      service_type: form.service_type,
      platform: form.platform || undefined,
      category: form.category || undefined,
      icon: form.icon || undefined,
      version: form.version || undefined,
      service_url: form.service_url || undefined,
      access_path: form.access_path || undefined,
      capabilities: form.capabilities && form.capabilities.length ? form.capabilities : undefined,
      description: form.description || undefined,
      default_client_config: cfg,
      sort: form.sort,
      status: form.status,
    }

    if (isEdit.value && props.record) {
      await updateMcpSquare({ id: props.record.id, ...payload })
      message.success('更新成功')
    } else {
      await createMcpSquare(payload)
      message.success('创建成功')
    }
    emit('update:visible', false)
    emit('success')
  } catch (e: any) {
    const detail = e?.response?.data?.detail || '操作失败'
    message.error(detail)
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  emit('update:visible', false)
}
</script>
