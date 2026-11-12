<template>
  <a-drawer
    v-model:open="visible"
    :title="isEdit ? t('agentMgmt.editAgent') : t('agentMgmt.createAgent')"
    width="100%"
    destroy-on-close
    class="agent-config-drawer"
  >
    <a-spin :spinning="loadingDetail" class="drawer-spin">
      <a-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        layout="vertical"
        class="agent-form"
      >
        <a-tabs v-model:active-key="activeTab">
          <!-- ── 1. 基础信息 ───────────────────────────────────────────── -->
          <a-tab-pane key="basic" :tab="t('agentMgmt.tabBasic')">
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
                <a-radio-button value="CHAT">{{ t('agentMgmt.typeNameChat') }} (CHAT)</a-radio-button>
                <a-radio-button value="WORKFLOW">{{ t('agentMgmt.typeNameWorkflow') }} (WORKFLOW)</a-radio-button>
                <a-radio-button value="SUPERAGENT">{{ t('agentMgmt.typeNameSuperagent') }} (SUPERAGENT)</a-radio-button>
              </a-radio-group>
              <div class="form-hint">
                <span v-if="formData.agent_type === 'CHAT'">{{ t('agentMgmt.typeNameChatHint') }}</span>
                <span v-else-if="formData.agent_type === 'WORKFLOW'">{{ t('agentMgmt.typeNameWorkflowHint') }}</span>
                <span v-else-if="formData.agent_type === 'SUPERAGENT'">{{ t('agentMgmt.typeNameSuperagentHint') }}</span>
              </div>
            </a-form-item>

            <a-row :gutter="16">
              <a-col :span="12">
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
              </a-col>
              <a-col :span="6">
                <a-form-item :label="t('agentMgmt.activeLabel')">
                  <a-switch
                    v-model:checked="formData.is_active"
                    :checked-children="t('skillHub.enabled')"
                    :un-checked-children="t('skillHub.disabled')"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="6">
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

            <a-form-item :label="t('skillHub.description')" name="description">
              <a-textarea
                v-model:value="formData.description"
                :placeholder="t('agentMgmt.descPlaceholder')"
                :auto-size="{ minRows: 2, maxRows: 4 }"
              />
            </a-form-item>
          </a-tab-pane>

          <!-- ── 2. 模型配置 ───────────────────────────────────────────── -->
          <a-tab-pane key="model" :tab="t('agentMgmt.tabModel')">
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

            <a-form-item :label="t('agentMgmt.temperature')">
              <a-row :gutter="16" align="middle">
                <a-col :span="16">
                  <a-slider
                    v-model:value="config.temperature"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    :tooltip-open="false"
                  />
                </a-col>
                <a-col :span="8">
                  <a-input-number
                    v-model:value="config.temperature"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    style="width: 100%"
                  />
                </a-col>
              </a-row>
            </a-form-item>

            <a-row :gutter="16">
              <a-col :span="12">
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
              <a-col :span="12">
                <a-form-item :label="t('agentMgmt.maxRetries')">
                  <a-input-number
                    v-model:value="config.max_retries"
                    :min="0"
                    :max="10"
                    style="width: 100%"
                  />
                  <span class="form-hint">{{ t('agentMgmt.maxRetriesHint') }}</span>
                </a-form-item>
              </a-col>
            </a-row>
          </a-tab-pane>

          <!-- ── 3. 能力绑定 ───────────────────────────────────────────── -->
          <a-tab-pane key="capability" :tab="t('agentMgmt.tabCapability')">
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
                  v-for="tool in toolList"
                  :key="tool.toolKey"
                  :value="tool.toolKey"
                  :label="tool.displayName"
                >
                  {{ tool.displayName }} ({{ tool.toolKey }})
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

            <a-form-item :label="t('agentMgmt.bindKnowledgeBases')">
              <a-select
                v-model:value="config.knowledge_bases"
                mode="multiple"
                :placeholder="t('agentMgmt.kbPlaceholder')"
                :loading="loadingKnowledgeBases"
                allow-clear
                show-search
                option-filter-prop="label"
              >
                <a-select-option
                  v-for="kb in knowledgeBaseList"
                  :key="kb.id"
                  :value="kb.id"
                  :label="kb.name"
                >
                  {{ kb.name }}
                  <span v-if="kb.description" style="color: var(--fg-muted); margin-left: 8px">{{ kb.description }}</span>
                </a-select-option>
              </a-select>
              <span class="form-hint">{{ t('agentMgmt.kbHint') }}</span>
            </a-form-item>
          </a-tab-pane>

          <!-- ── 4. 执行策略 + 自定义 ReAct ────────────────────────────── -->
          <a-tab-pane key="execution" :tab="t('agentMgmt.tabExecution')">
            <a-form-item :label="t('agentMgmt.systemPromptFull')">
              <a-textarea
                v-model:value="config.system_prompt"
                :placeholder="t('agentMgmt.promptPlaceholder')"
                :auto-size="{ minRows: 3, maxRows: 8 }"
              />
            </a-form-item>

            <a-form-item :label="t('agentMgmt.executionMode')">
              <a-select v-model:value="config.execution_mode" style="max-width: 320px">
                <a-select-option value="llm">{{ t('agentMgmt.modeLlm') }}</a-select-option>
                <a-select-option value="harness">{{ t('agentMgmt.modeHarness') }}</a-select-option>
                <a-select-option value="react">{{ t('agentMgmt.modeReact') }}</a-select-option>
                <a-select-option value="plan">{{ t('agentMgmt.modePlan') }}</a-select-option>
              </a-select>
            </a-form-item>

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

            <a-collapse class="advanced-collapse">
              <a-collapse-panel key="reactAdvanced" :header="t('agentMgmt.reactAdvancedTitle')">
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item :label="t('agentMgmt.graceIters')">
                      <a-input-number
                        v-model:value="reactConfig.structured_output_grace_iters"
                        :min="0"
                        :max="20"
                        style="width: 100%"
                      />
                      <span class="form-hint">{{ t('agentMgmt.graceItersHint') }}</span>
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item :label="t('agentMgmt.stopOnReject')">
                      <a-switch
                        v-model:checked="reactConfig.stop_on_reject"
                        :checked-children="t('skillHub.enabled')"
                        :un-checked-children="t('skillHub.disabled')"
                      />
                      <span class="form-hint">{{ t('agentMgmt.stopOnRejectHint') }}</span>
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-form-item :label="t('agentMgmt.interruptionMessage')">
                  <a-textarea
                    v-model:value="reactConfig.interruption_message"
                    :placeholder="t('agentMgmt.interruptionMessagePlaceholder')"
                    :auto-size="{ minRows: 2, maxRows: 4 }"
                  />
                </a-form-item>
                <a-form-item :label="t('agentMgmt.raiseCancelledError')">
                  <a-switch
                    v-model:checked="reactConfig.interruption_raise_cancelled_error"
                    :checked-children="t('skillHub.enabled')"
                    :un-checked-children="t('skillHub.disabled')"
                  />
                  <span class="form-hint">{{ t('agentMgmt.raiseCancelledErrorHint') }}</span>
                </a-form-item>
              </a-collapse-panel>
            </a-collapse>
          </a-tab-pane>

          <!-- ── 5. HITL（多轮） ───────────────────────────────────────── -->
          <a-tab-pane key="hitl" :tab="t('agentMgmt.tabHitl')">
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.hitlEnabled')">
                  <a-switch
                    v-model:checked="hitlConfig.enabled"
                    :checked-children="t('skillHub.enabled')"
                    :un-checked-children="t('skillHub.disabled')"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.hitlTimeoutSeconds')">
                  <a-input-number
                    v-model:value="hitlConfig.timeout_seconds"
                    :min="30"
                    :max="86400"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item :label="t('agentMgmt.confirmTools')">
              <a-select
                v-model:value="hitlConfig.confirm_tools"
                mode="multiple"
                :placeholder="t('agentMgmt.confirmToolsPlaceholder')"
                allow-clear
                show-search
                option-filter-prop="label"
              >
                <a-select-option
                  v-for="toolKey in config.tools"
                  :key="toolKey"
                  :value="toolKey"
                  :label="toolDisplayName(toolKey)"
                >
                  {{ toolDisplayName(toolKey) }} ({{ toolKey }})
                </a-select-option>
              </a-select>
              <span class="form-hint">{{ t('agentMgmt.confirmToolsHint') }}</span>
            </a-form-item>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item :label="t('agentMgmt.planApproval')">
                  <a-switch
                    v-model:checked="hitlConfig.plan_approval"
                    :checked-children="t('skillHub.enabled')"
                    :un-checked-children="t('skillHub.disabled')"
                  />
                  <span class="form-hint">{{ t('agentMgmt.planApprovalHint') }}</span>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item :label="t('agentMgmt.allowAskUser')">
                  <a-switch
                    v-model:checked="hitlConfig.allow_ask_user"
                    :checked-children="t('skillHub.enabled')"
                    :un-checked-children="t('skillHub.disabled')"
                  />
                  <span class="form-hint">{{ t('agentMgmt.allowAskUserHint') }}</span>
                </a-form-item>
              </a-col>
            </a-row>
            <span class="form-hint">{{ t('agentMgmt.hitlConfigHint') }}</span>
          </a-tab-pane>

          <!-- ── 6. 上下文配置 ─────────────────────────────────────────── -->
          <a-tab-pane key="context" :tab="t('agentMgmt.tabContext')">
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.triggerRatio')">
                  <a-input-number
                    v-model:value="contextConfig.trigger_ratio"
                    :min="0"
                    :max="0.9"
                    :step="0.05"
                    style="width: 100%"
                  />
                  <span class="form-hint">{{ t('agentMgmt.triggerRatioHint') }}</span>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.reserveRatio')">
                  <a-input-number
                    v-model:value="contextConfig.reserve_ratio"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    style="width: 100%"
                  />
                  <span class="form-hint">{{ t('agentMgmt.reserveRatioHint') }}</span>
                </a-form-item>
              </a-col>
            </a-row>
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.toolResultLimit')">
                  <a-input-number
                    v-model:value="contextConfig.tool_result_limit"
                    :min="0"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.maxImageNum')">
                  <a-input-number
                    v-model:value="contextConfig.max_image_num"
                    :min="0"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item :label="t('agentMgmt.compressionToolEnabled')">
                  <a-switch
                    v-model:checked="contextConfig.compression_tool_enabled"
                    :checked-children="t('skillHub.enabled')"
                    :un-checked-children="t('skillHub.disabled')"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-collapse class="advanced-collapse">
              <a-collapse-panel key="compressionPrompt" :header="t('agentMgmt.compressionPromptTitle')">
                <a-form-item :label="t('agentMgmt.compressionPrompt')">
                  <a-textarea
                    v-model:value="contextConfig.compression_prompt"
                    :placeholder="t('agentMgmt.compressionPromptPlaceholder')"
                    :auto-size="{ minRows: 3, maxRows: 8 }"
                  />
                </a-form-item>
                <a-form-item :label="t('agentMgmt.summaryTemplate')">
                  <a-textarea
                    v-model:value="contextConfig.summary_template"
                    :placeholder="t('agentMgmt.summaryTemplatePlaceholder')"
                    :auto-size="{ minRows: 3, maxRows: 8 }"
                  />
                </a-form-item>
              </a-collapse-panel>
            </a-collapse>
          </a-tab-pane>
        </a-tabs>
      </a-form>
    </a-spin>

    <!-- 底部固定操作栏 -->
    <template #footer>
      <div class="drawer-footer">
        <a-space>
          <a-button @click="handleCancel">{{ t('common.cancel') }}</a-button>
          <a-button type="primary" :loading="submitting" @click="handleSubmit">
            {{ t('common.save') }}
          </a-button>
        </a-space>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  saveAgentConfig,
  getAgentDetail,
  getSkillPackages,
  getToolSimpleList,
  type AgentConfig,
  type AgentModelConfig,
  type SkillPackage,
} from '@/api/agentConfig'
import { getAvailableModels, type AvailableModel } from '@/api/ai-apikey'
import { getMcpServerSelect, installMcpSquare, type McpServerSelectOption } from '@/api/ai-mcp'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'
import { listKnowledges } from '@/api/kb'

const props = defineProps<{
  agentId?: number | null
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })
const { t } = useI18n()
const submitting = ref(false)
const loadingDetail = ref(false)
const formRef = ref<any>(null)
const activeTab = ref('basic')

const skillPackages = ref<SkillPackage[]>([])
const toolList = ref<Array<{ toolKey: string; displayName: string; category?: string }>>([])
const loadingSkills = ref(false)
const loadingTools = ref(false)

// MCP 服务列表（已安装服务 + 系统内置未安装模板，合并数据源）
const mcpServiceList = ref<McpServerSelectOption[]>([])
const loadingMcpServices = ref(false)
const selectedMcpIds = ref<Array<number | string>>([])

// 知识库列表（kb 表，id 为数字，与后端 knowledge_bases: List[int] 对齐）
const knowledgeBaseList = ref<Array<{ id: number; name: string; description?: string }>>([])
const loadingKnowledgeBases = ref(false)

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

// 字典数据（用途分类）
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
  max_retries: 0,
  execution_mode: 'llm',
  tools: [] as string[],
  skills: [] as string[],
  knowledge_bases: [] as number[],
  // 系统模型模式下记录 AiChatModel.code，后端据此解析已存储的 API Key
  model_code: '' as string,
  key_name: '' as string,
})

// 执行策略：ReAct 配置（常规 + agentscope ReActConfig 白名单高级项）
const reactConfig = reactive<Record<string, any>>({
  interaction_mode: 'auto',
  reflection_mode: 'lightweight',
  max_iters: 10,
  timeout_seconds: 300,
  // 高级项：空 = 用后端 ReActConfig 默认值
  structured_output_grace_iters: undefined as number | undefined,
  stop_on_reject: false,
  interruption_message: '',
  interruption_raise_cancelled_error: false,
})

// HITL 多轮人机协同配置（execution.hitl_config）
const hitlConfig = reactive<Record<string, any>>({
  enabled: true,
  timeout_seconds: 600,
  confirm_tools: [] as string[],
  plan_approval: false,
  allow_ask_user: false,
})

// 上下文压缩配置（execution.context_config；空 = 用后端 ContextConfig 默认值）
const contextConfig = reactive<Record<string, any>>({
  trigger_ratio: undefined as number | undefined,
  reserve_ratio: undefined as number | undefined,
  tool_result_limit: undefined as number | undefined,
  max_image_num: undefined as number | undefined,
  compression_tool_enabled: false,
  compression_prompt: '',
  summary_template: '',
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
    activeTab.value = 'basic'
    // 先加载 MCP 服务列表，再初始化表单（initForm 需要按 name 匹配 MCP id）
    await loadMcpServices()
    if (props.agentId) {
      await loadAgentForEdit(props.agentId)
    } else {
      resetForm()
    }
    loadModels()
  }
})

/** 编辑态：按 id 拉取完整配置后回显 */
async function loadAgentForEdit(agentId: number) {
  loadingDetail.value = true
  try {
    const detail = await getAgentDetail(agentId)
    initForm(detail)
  } catch (e: any) {
    message.error(t('agentMgmt.loadDetailFailed', { msg: e.message || t('agentMgmt.unknownError') }))
    resetForm()
  } finally {
    loadingDetail.value = false
  }
}

function initForm(d: AgentConfig) {
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
    max_retries: mc?.max_retries ?? 0,
    model_code: mc?.model_code || '',
    key_name: '',
    execution_mode: d?.execution_mode || 'llm',
    tools: d?.tools || [],
    skills: d?.skills || [],
    knowledge_bases: d?.knowledge_bases || [],
  })
  // 恢复 ReAct 配置
  const rc: Record<string, any> = d?.react_config || {}
  Object.assign(reactConfig, {
    interaction_mode: rc.interaction_mode || 'auto',
    reflection_mode: rc.reflection_mode || 'lightweight',
    max_iters: rc.max_iters ?? 10,
    timeout_seconds: rc.timeout_seconds ?? 300,
    structured_output_grace_iters: rc.structured_output_grace_iters,
    stop_on_reject: !!rc.stop_on_reject,
    interruption_message: rc.interruption_message || '',
    interruption_raise_cancelled_error: !!rc.interruption_raise_cancelled_error,
  })
  // 恢复 HITL 多轮配置
  const hc: Record<string, any> = d?.hitl_config || {}
  Object.assign(hitlConfig, {
    enabled: hc.enabled ?? true,
    timeout_seconds: hc.timeout_seconds ?? 600,
    confirm_tools: hc.confirm_tools || [],
    plan_approval: !!hc.plan_approval,
    allow_ask_user: !!hc.allow_ask_user,
  })
  // 恢复上下文压缩配置
  const cc: Record<string, any> = d?.context_config || {}
  Object.assign(contextConfig, {
    trigger_ratio: cc.trigger_ratio,
    reserve_ratio: cc.reserve_ratio,
    tool_result_limit: cc.tool_result_limit,
    max_image_num: cc.max_image_num,
    compression_tool_enabled: !!cc.compression_tool_enabled,
    compression_prompt: cc.compression_prompt || '',
    summary_template: cc.summary_template || '',
  })
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

function resetForm() {
  Object.assign(formData, {
    agent_code: '',
    name: '',
    agent_type: 'CHAT',
    category: undefined,
    description: '',
    is_active: true,
    sort_order: 0,
  })
  Object.assign(config, {
    system_prompt: '',
    provider: 'openai',
    model: 'gpt-4o',
    temperature: 0.7,
    max_tokens: 4096,
    max_retries: 0,
    execution_mode: 'llm',
    tools: [],
    skills: [],
    knowledge_bases: [],
    model_code: '',
    key_name: '',
  })
  Object.assign(reactConfig, {
    interaction_mode: 'auto',
    reflection_mode: 'lightweight',
    max_iters: 10,
    timeout_seconds: 300,
    structured_output_grace_iters: undefined,
    stop_on_reject: false,
    interruption_message: '',
    interruption_raise_cancelled_error: false,
  })
  Object.assign(hitlConfig, {
    enabled: true,
    timeout_seconds: 600,
    confirm_tools: [],
    plan_approval: false,
    allow_ask_user: false,
  })
  Object.assign(contextConfig, {
    trigger_ratio: undefined,
    reserve_ratio: undefined,
    tool_result_limit: undefined,
    max_image_num: undefined,
    compression_tool_enabled: false,
    compression_prompt: '',
    summary_template: '',
  })
  selectedModelCode.value = ''
  useSystemModel.value = true
  selectedMcpIds.value = []
}

function toolDisplayName(toolKey: string): string {
  return toolList.value.find((tool) => tool.toolKey === toolKey)?.displayName || toolKey
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

async function loadKnowledgeBases() {
  loadingKnowledgeBases.value = true
  try {
    const res: any = await listKnowledges()
    const items = res?.items || res || []
    knowledgeBaseList.value = items
      .filter((kb: any) => kb && kb.id != null)
      .map((kb: any) => ({ id: Number(kb.id), name: kb.name, description: kb.description }))
  } catch (e) {
    knowledgeBaseList.value = []
  } finally {
    loadingKnowledgeBases.value = false
  }
}

async function loadDicts() {
  try {
    agentCategoryDict.value = (await getDictionaryItems('agent_category')) || []
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

  // 模型配置：系统模型模式额外携带 model_code（后端解析已存 API Key）
  const modelConfig: AgentModelConfig = {
    provider: config.provider,
    model: config.model,
    temperature: config.temperature,
    max_tokens: config.max_tokens,
    max_retries: config.max_retries ?? 0,
  }
  if (useSystemModel.value && selectedModelCode.value) {
    modelConfig.model_code = selectedModelCode.value
  }

  // ReAct 配置：plan/react 模式或 SUPERAGENT 常规提交；高级项仅在设置过时携带
  const reactAdvanced: Record<string, any> = {}
  if (reactConfig.structured_output_grace_iters != null) {
    reactAdvanced.structured_output_grace_iters = reactConfig.structured_output_grace_iters
  }
  if (reactConfig.stop_on_reject) {
    reactAdvanced.stop_on_reject = true
  }
  if (reactConfig.interruption_message) {
    reactAdvanced.interruption_message = reactConfig.interruption_message
  }
  if (reactConfig.interruption_raise_cancelled_error) {
    reactAdvanced.interruption_raise_cancelled_error = true
  }
  const includeReact =
    ['plan', 'react'].includes(config.execution_mode) ||
    formData.agent_type === 'SUPERAGENT' ||
    Object.keys(reactAdvanced).length > 0
  const reactPayload = includeReact
    ? {
        interaction_mode: reactConfig.interaction_mode,
        reflection_mode: reactConfig.reflection_mode,
        max_iters: reactConfig.max_iters,
        timeout_seconds: reactConfig.timeout_seconds,
        ...reactAdvanced,
      }
    : undefined

  // 上下文压缩配置：仅携带用户设置过的键（空 = 后端 ContextConfig 默认值）
  const contextPayload: Record<string, any> = {}
  if (contextConfig.trigger_ratio != null) contextPayload.trigger_ratio = contextConfig.trigger_ratio
  if (contextConfig.reserve_ratio != null) contextPayload.reserve_ratio = contextConfig.reserve_ratio
  if (contextConfig.tool_result_limit != null) contextPayload.tool_result_limit = contextConfig.tool_result_limit
  if (contextConfig.max_image_num != null) contextPayload.max_image_num = contextConfig.max_image_num
  if (contextConfig.compression_tool_enabled) contextPayload.compression_tool_enabled = true
  if (contextConfig.compression_prompt) contextPayload.compression_prompt = contextConfig.compression_prompt
  if (contextConfig.summary_template) contextPayload.summary_template = contextConfig.summary_template

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
    model_config: modelConfig,
    tools: {
      tools: config.tools,
      skills: config.skills,
      mcp_servers: mcpServers,
      knowledge_bases: config.knowledge_bases || [],
    },
    execution: {
      hitl_config: { ...hitlConfig },
      ...(reactPayload ? { react_config: reactPayload } : {}),
      ...(Object.keys(contextPayload).length ? { context_config: contextPayload } : {}),
    },
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    // 校验失败时定位到第一个错误所在 tab 附近（简单起见回到基础信息）
    activeTab.value = 'basic'
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
    await saveAgentConfig(payload, isEdit.value ? props.agentId! : undefined)
    message.success(isEdit.value ? t('agentMgmt.updated') : t('agentMgmt.created'))
    emit('success')
    visible.value = false
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
  visible.value = false
}

onMounted(() => {
  loadDicts()
  loadSkills()
  loadTools()
  loadKnowledgeBases()
})
</script>

<style scoped lang="less">
.drawer-spin {
  display: block;
  width: 100%;
}

.agent-form {
  padding-bottom: 16px;
}

.form-hint {
  display: block;
  font-size: 12px;
  color: var(--fg-muted);
  margin-top: 4px;
}

.advanced-collapse {
  margin-top: 8px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
