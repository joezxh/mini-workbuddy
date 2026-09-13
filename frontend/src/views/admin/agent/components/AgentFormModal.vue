<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('agentMgmt.editAgent') : t('agentMgmt.createAgent')"
    :width="720"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :ok-text="t('common.save')"
    :cancel-text="t('common.cancel')"
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
          <a-form-item :label="t('agentMgmt.agentCode')" name="agent_code">
            <a-input
              v-model:value="formData.agent_code"
              :placeholder="t('agentMgmt.agentCodePlaceholder')"
              :disabled="isEdit"
            />
            <span class="form-hint">{{ t('agentMgmt.agentCodeHint') }}</span>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('agentMgmt.agentName')" name="name">
            <a-input v-model:value="formData.name" :placeholder="t('agentMgmt.agentNamePlaceholder')" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item :label="t('agentMgmt.implType')" name="agent_type">
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

      <a-form-item :label="t('agentMgmt.category')" name="category">
        <a-select
          v-model:value="formData.category"
          :placeholder="t('agentMgmt.categoryPlaceholder')"
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

      <a-form-item :label="t('skillHub.description')" name="description">
        <a-textarea
          v-model:value="formData.description"
          :placeholder="t('agentMgmt.descPlaceholder')"
          :auto-size="{ minRows: 2, maxRows: 4 }"
        />
      </a-form-item>

      <!-- 通用 Agent 可视化配置（system_prompt / 模型 / tools / skills / mcp） -->
      <a-divider>{{ t('agentMgmt.visConfigFull') }}</a-divider>

      <a-form-item :label="t('agentMgmt.systemPromptFull')">
        <a-textarea
          v-model:value="config.system_prompt"
          :placeholder="t('agentMgmt.promptPlaceholder')"
          :auto-size="{ minRows: 3, maxRows: 8 }"
        />
      </a-form-item>

      <a-form-item :label="t('agentMgmt.modelSource')">
        <a-radio-group v-model:value="useSystemModel">
          <a-radio :value="true">{{ t('agentMgmt.systemModel') }}</a-radio>
          <a-radio :value="false">{{ t('agentMgmt.customModel') }}</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="useSystemModel ? 24 : 10">
          <a-form-item :label="t('agentMgmt.modelProvider')">
            <template v-if="useSystemModel">
              <a-select
                v-model:value="selectedModelCode"
                :placeholder="t('agentMgmt.systemModelPlaceholder')"
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
                    {{ t('agentMgmt.keyLabel', { name: m.key_name }) }}
                  </a-tag>
                </a-select-option>
              </a-select>
              <span class="form-hint">
                {{ t('agentMgmt.systemModelHint', { status: selectedModelCode ? config.key_name || t('agentMgmt.keyConfigured') : t('agentMgmt.pleaseSelect') }) }}
              </span>
            </template>
            <template v-else>
              <a-select v-model:value="config.provider" :placeholder="t('agentMgmt.providerPlaceholder')">
                <a-select-option value="openai">OpenAI</a-select-option>
                <a-select-option value="dashscope">{{ t('agentMgmt.providerDashscope') }}</a-select-option>
                <a-select-option value="deepseek">DeepSeek</a-select-option>
                <a-select-option value="anthropic">Anthropic</a-select-option>
                <a-select-option value="azure">Azure OpenAI</a-select-option>
                <a-select-option value="ollama">{{ t('agentMgmt.providerOllama') }}</a-select-option>
              </a-select>
            </template>
          </a-form-item>
        </a-col>
        <a-col v-if="!useSystemModel" :span="14">
          <a-form-item :label="t('agentMgmt.modelName')">
            <a-input
              v-model:value="config.model"
              :placeholder="t('agentMgmt.modelPlaceholder')"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item :label="t('agentMgmt.temperature')">
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
          <a-form-item :label="t('agentMgmt.maxTokens')">
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
          <a-form-item :label="t('agentMgmt.executionMode')">
            <a-select v-model:value="config.execution_mode" :placeholder="t('agentMgmt.executionMode')">
              <a-select-option value="llm">{{ t('agentMgmt.modeLlm') }}</a-select-option>
              <a-select-option value="harness">{{ t('agentMgmt.modeHarness') }}</a-select-option>
              <a-select-option value="react">{{ t('agentMgmt.modeReact') }}</a-select-option>
              <a-select-option value="plan">{{ t('agentMgmt.modePlan') }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <!-- ReAct 计划执行配置区域 -->
      <template v-if="config.execution_mode === 'plan'">
        <a-divider>{{ t('agentMgmt.reactConfigTitle') }}</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('agentMgmt.interactionMode')">
              <a-select v-model:value="reactConfig.interaction_mode">
                <a-select-option value="auto">{{ t('agentMgmt.interactionAuto') }}</a-select-option>
                <a-select-option value="approve">{{ t('agentMgmt.interactionApprove') }}</a-select-option>
                <a-select-option value="confirm_steps">{{ t('agentMgmt.interactionConfirmSteps') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('agentMgmt.reflectionMode')">
              <a-select v-model:value="reactConfig.reflection_mode">
                <a-select-option value="lightweight">{{ t('agentMgmt.reflectionLight') }}</a-select-option>
                <a-select-option value="deep">{{ t('agentMgmt.reflectionDeep') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('agentMgmt.maxIters')">
              <a-input-number v-model:value="reactConfig.max_iters" :min="1" :max="50" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('agentMgmt.timeoutSeconds')">
              <a-input-number v-model:value="reactConfig.timeout_seconds" :min="30" :max="3600" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </template>

      <a-form-item :label="t('agentMgmt.bindTools')">
        <a-select
          v-model:value="config.tools"
          mode="multiple"
          :placeholder="t('agentMgmt.toolsPlaceholder')"
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

      <a-form-item :label="t('agentMgmt.bindSkills')">
        <a-select
          v-model:value="config.skills"
          mode="multiple"
          :placeholder="t('agentMgmt.skillsPlaceholder')"
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

      <a-form-item :label="t('agentMgmt.bindMcp')">
        <a-select
          v-model:value="selectedMcpIds"
          mode="multiple"
          :placeholder="t('agentMgmt.mcpPlaceholder')"
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
              {{ srv.source === 'builtin' ? t('agentMgmt.builtin') : srv.service_type }}
            </a-tag>
            <span v-if="srv.source === 'builtin'" style="color: var(--fg-muted); margin-left: 8px">{{ t('agentMgmt.builtinService') }}</span>
          </a-select-option>
        </a-select>
        <span class="form-hint">{{ t('agentMgmt.mcpHint') }}</span>
      </a-form-item>

      <!-- WORKFLOW / SKILL 类型保留通用可视化配置即可 -->

      <a-divider>{{ t('agentMgmt.generalSettings') }}</a-divider>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item :label="t('agentMgmt.activeLabel')">
            <a-switch
              v-model:checked="formData.is_active"
              :checked-children="t('skillHub.enabled')"
              :un-checked-children="t('skillHub.disabled')"
            />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('agentMgmt.sortWeight')">
            <a-input-number
              v-model:value="formData.sort_order"
              :min="0"
              :max="9999"
              style="width: 100%"
            />
            <span class="form-hint">{{ t('agentMgmt.sortHint') }}</span>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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
const { t } = useI18n()
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

const rules = computed(() => ({
  agent_code: [
    { required: true, message: t('agentMgmt.ruleAgentCodeRequired') },
    { pattern: /^[a-z][a-z0-9_-]*$/, message: t('agentMgmt.ruleAgentCodePattern') },
    { max: 100, message: t('agentMgmt.ruleMaxChars') },
  ],
  name: [{ required: true, message: t('agentMgmt.ruleNameRequired') }],
  agent_type: [{ required: true, message: t('agentMgmt.ruleTypeRequired') }],
}))

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
      description: item.source === 'builtin' ? t('agentMgmt.builtinService') : '',
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
    message.success(isEdit.value ? t('agentMgmt.updated') : t('agentMgmt.created'))
    emit('success')
  } catch (e: any) {
    message.error(
      (isEdit.value ? t('agentMgmt.updateVerb') : t('agentMgmt.createVerb')) +
      t('agentMgmt.actionFailedSuffix', { msg: e.message || t('agentMgmt.unknownError') })
    )
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