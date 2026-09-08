<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑专家' : '新建专家'"
    :width="720"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
    ok-text="保存"
    cancel-text="取消"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
      class="agent-form"
    >
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="专家编码" name="agent_code">
            <a-input
              v-model:value="formData.agent_code"
              placeholder="唯一标识，如 risk_analyst"
              :disabled="isEdit"
            />
            <span class="form-hint">系统唯一标识，创建后不可修改</span>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="专家名称" name="name">
            <a-input v-model:value="formData.name" placeholder="专家显示名称" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="实现类型" name="agent_type">
        <a-radio-group v-model:value="formData.agent_type" :disabled="isEdit" button-style="solid">
          <a-radio-button v-for="item in agentTypeDict" :key="item.item_code" :value="item.item_code">
            {{ item.item_name }} ({{ item.item_code }})
          </a-radio-button>
        </a-radio-group>
        <div class="form-hint">
          <span v-for="item in agentTypeDict" :key="item.item_code">
            <span v-if="formData.agent_type === item.item_code">{{ item.remark || item.item_name }}</span>
          </span>
        </div>
      </a-form-item>

      <a-form-item label="用途分类" name="category">
        <a-select
          v-model:value="formData.category"
          placeholder="选择用途分类"
          allow-clear
          show-search
          :filter-option="(input: string, option: any) => option.label?.toLowerCase().includes(input.toLowerCase())"
        >
          <a-select-option
            v-for="item in agentCategoryDict"
            :key="item.item_code"
            :value="item.item_code"
            :label="item.item_name"
          >
            {{ item.item_name }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="描述" name="description">
        <a-textarea
          v-model:value="formData.description"
          placeholder="专家的功能描述"
          :auto-size="{ minRows: 2, maxRows: 4 }"
        />
      </a-form-item>

      <!-- 通用 Agent 可视化配置（system_prompt / 模型 / tools / skills / mcp） -->
      <a-divider>Agent 可视化配置</a-divider>

      <a-form-item label="系统提示词 (System Prompt)">
        <a-textarea
          v-model:value="config.system_prompt"
          placeholder="你是一个专业的风险分析师，请基于给定上下文给出研判结论..."
          :auto-size="{ minRows: 3, maxRows: 8 }"
        />
      </a-form-item>

      <a-form-item label="模型来源">
        <a-radio-group v-model:value="useSystemModel">
          <a-radio :value="true">系统已集成模型（自动调用已存 API Key）</a-radio>
          <a-radio :value="false">自定义（手动填写）</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="useSystemModel ? 24 : 10">
          <a-form-item label="模型供应商">
            <template v-if="useSystemModel">
              <a-select
                v-model:value="selectedModelCode"
                placeholder="选择系统已集成的供应商 / 模型"
                :loading="loadingModels"
                @change="onSystemModelChange"
                show-search
                option-filter-prop="label"
              >
                <a-select-option
                  v-for="m in availableTextModels"
                  :key="m.name"
                  :value="m.name"
                  :label="`${m.platform} / ${m.model}`"
                >
                  <span>{{ m.platform }}</span>
                  <span style="color: var(--fg-muted); margin-left: 8px">{{ m.model }}</span>
                  <a-tag v-if="m.key_name" color="green" style="margin-left: 8px">
                    密钥: {{ m.key_name }}
                  </a-tag>
                </a-select-option>
              </a-select>
              <span class="form-hint">
                所选模型已绑定系统存储的 API Key（{{ selectedModelCode ? config.key_name || '已配置' : '请选择' }}），运行时自动鉴权，无需手动填写密钥。
              </span>
            </template>
            <template v-else>
              <a-select v-model:value="config.provider" placeholder="选择模型供应商">
                <a-select-option value="openai">OpenAI</a-select-option>
                <a-select-option value="dashscope">阿里通义 (DashScope)</a-select-option>
                <a-select-option value="deepseek">DeepSeek</a-select-option>
                <a-select-option value="anthropic">Anthropic</a-select-option>
                <a-select-option value="azure">Azure OpenAI</a-select-option>
                <a-select-option value="ollama">Ollama (本地)</a-select-option>
              </a-select>
            </template>
          </a-form-item>
        </a-col>
        <a-col v-if="!useSystemModel" :span="14">
          <a-form-item label="模型名称">
            <a-input
              v-model:value="config.model"
              placeholder="如 gpt-4o / qwen-max / deepseek-chat"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="温度 (0-2)">
            <a-input-number
              v-model:value="config.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="最大 Token">
            <a-input-number
              v-model:value="config.max_tokens"
              :min="512"
              :max="32768"
              :step="512"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="执行模式">
            <a-select v-model:value="config.execution_mode" placeholder="执行模式">
              <a-select-option value="llm">LLM（对话/ReAct）</a-select-option>
              <a-select-option value="harness">Harness（工具编排）</a-select-option>
              <a-select-option value="react">ReAct（思考-行动）</a-select-option>
              <a-select-option value="plan">ReAct 计划执行</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <!-- ReAct 计划执行配置区域 -->
      <template v-if="config.execution_mode === 'plan'">
        <a-divider>ReAct 模式配置</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="交互模式">
              <a-select v-model:value="reactConfig.interaction_mode">
                <a-select-option value="auto">全自动</a-select-option>
                <a-select-option value="approve">先审批</a-select-option>
                <a-select-option value="confirm_steps">关键步骤确认</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="反思模式">
              <a-select v-model:value="reactConfig.reflection_mode">
                <a-select-option value="lightweight">轻量（自评估）</a-select-option>
                <a-select-option value="deep">深度（独立调用）</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="最大步数">
              <a-input-number v-model:value="reactConfig.max_iters" :min="1" :max="50" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="超时时间（秒）">
              <a-input-number v-model:value="reactConfig.timeout_seconds" :min="30" :max="3600" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </template>

      <a-form-item label="绑定工具 (Tools)">
        <a-select
          v-model:value="config.tools"
          mode="multiple"
          placeholder="选择该 Agent 可调用的工具"
          :loading="loadingTools"
          allow-clear
          show-search
          option-filter-prop="label"
        >
          <a-select-option
            v-for="t in toolList"
            :key="t.toolKey"
            :value="t.toolKey"
            :label="t.displayName"
          >
            {{ t.displayName }} ({{ t.toolKey }})
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="绑定技能 (Skills)">
        <a-select
          v-model:value="config.skills"
          mode="multiple"
          placeholder="选择该 Agent 可调用的技能包"
          :loading="loadingSkills"
          allow-clear
          show-search
          option-filter-prop="label"
        >
          <a-select-option
            v-for="pkg in skillPackages"
            :key="pkg.package_id"
            :value="pkg.package_id"
            :label="pkg.name"
          >
            {{ pkg.name }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="绑定 MCP 服务">
        <a-select
          v-model:value="selectedMcpIds"
          mode="multiple"
          placeholder="选择要绑定的 MCP 服务"
          :loading="loadingMcpServices"
          allow-clear
          show-search
          option-filter-prop="label"
        >
          <a-select-option
            v-for="srv in mcpServiceList"
            :key="String(srv.value)"
            :value="srv.value"
            :label="srv.name"
          >
            <span>{{ srv.name }}</span>
            <a-tag :color="srv.source === 'builtin' ? 'gold' : 'blue'" style="margin-left: 8px">
              {{ srv.source === 'builtin' ? '内置' : srv.service_type }}
            </a-tag>
            <span v-if="srv.source === 'builtin'" style="color: var(--fg-muted); margin-left: 8px">系统内置服务</span>
          </a-select-option>
        </a-select>
        <span class="form-hint">从 MCP 服务管理中选择已创建的服务，可多选</span>
      </a-form-item>

      <!-- WORKFLOW / SKILL 类型保留通用可视化配置即可 -->

      <a-divider>通用设置</a-divider>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="启用状态">
            <a-switch
              v-model:checked="formData.is_active"
              checked-children="启用"
              un-checked-children="禁用"
            />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="排序权重">
            <a-input-number
              v-model:value="formData.sort_order"
              :min="0"
              :max="9999"
              style="width: 100%"
            />
            <span class="form-hint">数字越小排序越靠前</span>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  saveAgentConfig,
  getSkillPackages,
  getToolSimpleList,
  type AgentConfig,
  type SkillPackage,
} from '@/api/agentConfig'
import { getAvailableModels, type AvailableModel } from '@/api/ai-apikey'
import { getMcpServerSelect, installMcpSquare, type McpServerSelectOption } from '@/api/ai-mcp'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'

const props = defineProps<{
  agentId?: number
  agentData?: AgentConfig | null
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })
const submitting = ref(false)
const formRef = ref<any>(null)

const skillPackages = ref<SkillPackage[]>([])
const toolList = ref<Array<{ toolKey: string; displayName: string; category?: string }>>([])
const loadingSkills = ref(false)
const loadingTools = ref(false)

// MCP 服务列表（已安装服务 + 系统内置未安装模板，合并数据源）
const mcpServiceList = ref<McpServerSelectOption[]>([])
const loadingMcpServices = ref(false)
const selectedMcpIds = ref<Array<number | string>>([])

// 系统已集成的模型（绑定已存储的 API Key，自动鉴权）
const availableModels = ref<AvailableModel[]>([])
const loadingModels = ref(false)
// 仅展示文本类模型（过滤 embedding / rerank 等专用类型）
const availableTextModels = computed<AvailableModel[]>(() =>
  availableModels.value.filter((m) => m.type === undefined || m.type === null || m.type === 1)
)
// true: 从系统已集成模型中选择；false: 手动填写（自定义）
const useSystemModel = ref<boolean>(true)
const selectedModelCode = ref<string>('')

// 切换到自定义模式时清除系统模型绑定，避免冗余字段
watch(useSystemModel, (val) => {
  if (!val) {
    selectedModelCode.value = ''
    config.model_code = ''
    config.key_name = ''
  } else if (selectedModelCode.value) {
    onSystemModelChange(selectedModelCode.value)
  }
})

// 字典数据
const agentTypeDict = ref<DictionaryItem[]>([])
const agentCategoryDict = ref<DictionaryItem[]>([])

const isEdit = computed(() => !!props.agentId)

const formData = reactive({
  agent_code: '',
  name: '',
  agent_type: 'CHAT',
  category: undefined as string | undefined,
  description: '',
  is_active: true,
  sort_order: 0,
})

const config = reactive<Record<string, any>>({
  system_prompt: '',
  provider: 'openai',
  model: 'gpt-4o',
  temperature: 0.7,
  max_tokens: 4096,
  execution_mode: 'llm',
  tools: [] as string[],
  skills: [] as string[],
  // 系统模型模式下记录 AiChatModel.code，后端据此解析已存储的 API Key
  model_code: '' as string,
  key_name: '' as string,
})

const reactConfig = reactive({
  interaction_mode: 'auto',
  reflection_mode: 'lightweight',
  max_iters: 10,
  timeout_seconds: 300,
})

const rules = {
  agent_code: [
    { required: true, message: '请输入专家编码' },
    { pattern: /^[a-z][a-z0-9_-]*$/, message: '只能包含小写字母、数字、下划线、连字符（-），且以字母开头' },
    { max: 100, message: '最多 100 个字符' },
  ],
  name: [{ required: true, message: '请输入专家名称' }],
  agent_type: [{ required: true, message: '请选择实现类型' }],
}

watch(() => visible.value, async (val) => {
  if (val) {
    // 先加载 MCP 服务列表，再初始化表单（initForm 需要按 name 匹配 MCP id）
    await loadMcpServices()
    initForm()
    loadModels()
  }
})

watch(() => props.agentData, (val) => {
  if (val) {
    initForm()
  }
})

function initForm() {
  const d = props.agentData
  Object.assign(formData, {
    agent_code: d?.agent_code ?? '',
    name: d?.name ?? '',
    agent_type: d?.agent_type ?? 'CHAT',
    category: d?.category || undefined,
    description: d?.description || '',
    is_active: d?.is_active ?? true,
    sort_order: d?.sort_order || 0,
  })
  const mc = d?.model_config
  // 若已绑定系统已集成模型（存在 model_code），则进入系统模型模式
  const hasSystemModel = !!(mc?.model_code)
  useSystemModel.value = hasSystemModel
  selectedModelCode.value = hasSystemModel ? (mc?.model_code || '') : ''
  Object.assign(config, {
    system_prompt: d?.system_prompt || '',
    provider: mc?.provider || 'openai',
    model: mc?.model || 'gpt-4o',
    temperature: mc?.temperature ?? 0.7,
    max_tokens: mc?.max_tokens ?? 4096,
    model_code: mc?.model_code || '',
    key_name: '',
    execution_mode: d?.execution_mode || 'llm',
    tools: d?.tools || [],
    skills: d?.skills || [],
  })
  // 恢复 ReAct 配置
  const rc = d?.react_config
  if (rc) {
    Object.assign(reactConfig, {
      interaction_mode: rc.interaction_mode || 'auto',
      reflection_mode: rc.reflection_mode || 'lightweight',
      max_iters: rc.max_iters ?? 10,
      timeout_seconds: rc.timeout_seconds ?? 300,
    })
  }
  // 恢复 MCP 服务选中状态（按 name 匹配 value；内置服务以 't'+template_id 形式存在）
  if (d?.mcp_servers?.length) {
    const names = (d.mcp_servers as any[]).map((s: any) => (typeof s === 'string' ? s : s.name))
    selectedMcpIds.value = mcpServiceList.value
      .filter((srv) => names.includes(srv.name))
      .map((srv) => srv.value)
  } else {
    selectedMcpIds.value = []
  }
}

async function loadModels() {
  loadingModels.value = true
  try {
    availableModels.value = await getAvailableModels()
    // 回显：编辑态且已记录 model_code 时，若模型仍在列表中，则恢复系统模型模式并应用选中
    if (selectedModelCode.value) {
      const found = availableModels.value.find((m) => m.name === selectedModelCode.value)
      if (found) {
        useSystemModel.value = true
        applyModelSelection(found)
      } else {
        // 已保存的模型不在当前可用列表中（如被过滤或已下架），回退为自定义模式
        useSystemModel.value = false
      }
    } else if (useSystemModel.value) {
      // 新建态默认进入系统模型模式
      useSystemModel.value = true
    }
  } catch (e) {
    availableModels.value = []
  } finally {
    loadingModels.value = false
  }
}

/** 根据选中的系统模型，自动填充 provider/model 并绑定已存储的 API Key */
function applyModelSelection(m: AvailableModel) {
  selectedModelCode.value = m.name
  config.provider = m.platform
  config.model = m.model
  // 仅记录 model_code（= AiChatModel.code），后端据此解析已存储的 API Key 自动鉴权
  config.model_code = m.name
  config.key_name = m.key_name
}

function onSystemModelChange(code: string) {
  const m = availableModels.value.find((x) => x.name === code)
  if (m) applyModelSelection(m)
}

async function loadMcpServices() {
  loadingMcpServices.value = true
  try {
    const list = await getMcpServerSelect()
    // simple-select 返回合并数据源：已安装服务 + 系统内置未安装模板
    // 统一补充 name/description 字段，兼容回填按 name 匹配的逻辑
    mcpServiceList.value = (list || []).map((item: McpServerSelectOption) => ({
      ...item,
      name: item.label,
      description: item.source === 'builtin' ? '系统内置服务' : '',
    })) as McpServerSelectOption[]
  } catch (e) {
    mcpServiceList.value = []
  } finally {
    loadingMcpServices.value = false
  }
}

async function loadDicts() {
  try {
    const [types, cats] = await Promise.all([
      getDictionaryItems('agent_impl_type'),
      getDictionaryItems('agent_category'),
    ])
    agentTypeDict.value = types || []
    agentCategoryDict.value = cats || []
  } catch (e) {
    console.error('加载字典失败:', e)
  }
}

async function loadSkills() {
  loadingSkills.value = true
  try {
    skillPackages.value = await getSkillPackages()
  } catch (e) {
    skillPackages.value = []
  } finally {
    loadingSkills.value = false
  }
}

async function loadTools() {
  loadingTools.value = true
  try {
    toolList.value = await getToolSimpleList()
  } catch (e) {
    toolList.value = []
  } finally {
    loadingTools.value = false
  }
}

function buildPayload() {
  // 从选中的 MCP 服务 value（已安装为数字 id，内置为 't'+template_id）解析出 name
  const mcpServers = selectedMcpIds.value
    .map((val) => mcpServiceList.value.find((s) => String(s.value) === String(val)))
    .filter((s): s is McpServerSelectOption => !!s)
    .map((s) => ({ name: s.name }))

  return {
    agent_code: formData.agent_code,
    name: formData.name,
    agent_type: formData.agent_type,
    category: formData.category,
    description: formData.description,
    is_active: formData.is_active,
    sort_order: formData.sort_order,
    strategy: {
      execution_mode: config.execution_mode,
      system_prompt: config.system_prompt,
    },
    model_config: useSystemModel.value
      ? {
          // 系统模型模式：后端按 model_code（AiChatModel.code）解析已存储的 API Key 自动鉴权
          provider: config.provider,
          model: config.model,
          temperature: config.temperature,
          max_tokens: config.max_tokens,
          model_code: selectedModelCode.value || undefined,
        }
      : {
          // 自定义模式：手动填写 provider/model（不含 model_code）
          provider: config.provider,
          model: config.model,
          temperature: config.temperature,
          max_tokens: config.max_tokens,
        },
    tools: {
      tools: config.tools,
      skills: config.skills,
      mcp_servers: mcpServers,
    },
    // ReAct 计划执行配置（execution_mode="plan" 时生效）
    ...(config.execution_mode === 'plan' ? {
      react_config: { ...reactConfig },
    } : {}),
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    // 内置 MCP 服务（value 以 't' 开头）需先安装为真实 McpApiKey，再用真实 id 落库
    const builtinSelected = selectedMcpIds.value.filter(
      (v) => typeof v === 'string' && String(v).startsWith('t'),
    ) as string[]
    if (builtinSelected.length) {
      for (const tVal of builtinSelected) {
        const templateId = Number(String(tVal).slice(1))
        await installMcpSquare({ template_id: templateId })
      }
      // 重新拉取合并列表，使内置项变为已安装（拥有真实 id 与 name）
      await loadMcpServices()
      const installedValues = mcpServiceList.value
        .filter((s) => s.source === 'installed')
        .map((s) => s.value)
      // 将已安装的全部选中（含本次新安装的），其余非内置选中项保持不变
      const nonBuiltin = selectedMcpIds.value.filter(
        (v) => !(typeof v === 'string' && String(v).startsWith('t')),
      )
      selectedMcpIds.value = Array.from(new Set([...nonBuiltin, ...installedValues]))
    }

    const payload = buildPayload()
    await saveAgentConfig(payload, isEdit.value ? props.agentId : undefined)
    message.success(isEdit.value ? '更新成功' : '创建成功')
    emit('success')
  } catch (e: any) {
    message.error((isEdit.value ? '更新' : '创建') + '失败：' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
}

onMounted(() => {
  loadDicts()
  loadSkills()
  loadTools()
  loadMcpServices()
})
</script>

<style scoped lang="less">
.agent-form {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 8px;
}

.form-hint {
  display: block;
  font-size: 12px;
  color: var(--fg-muted);
  margin-top: 4px;
}
</style>