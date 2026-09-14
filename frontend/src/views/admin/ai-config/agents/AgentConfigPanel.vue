<template>
  <a-card title="语音 Agent 配置">
    <a-form layout="vertical" :model="form" class="cfg-form">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="Agent ID">
            <a-input v-model:value="form.agent_id" placeholder="如 duplex-agent-1" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="名称">
            <a-input v-model:value="form.name" placeholder="展示名" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="类型">
            <a-select v-model:value="form.type" :options="typeOptions" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="模型">
            <a-input v-model:value="form.model" placeholder="如 qwen-plus" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="最大 ReAct 轮次">
            <a-input-number v-model:value="form.max_react_iters" :min="1" :max="20" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="系统提示词">
        <a-textarea v-model:value="form.system_prompt" :rows="4" placeholder="角色设定/约束" />
      </a-form-item>

      <a-form-item label="启用任务规划">
        <a-switch v-model:checked="form.enable_plan" />
      </a-form-item>

      <a-space>
        <a-button type="primary" :loading="saving" @click="onSave">保存</a-button>
        <a-button @click="onReset">重置</a-button>
      </a-space>
    </a-form>

    <a-divider />
    <a-list size="small" bordered :data-source="rows">
      <template #renderItem="{ item }">
        <a-list-item>
          <span>{{ item.agent_id }} · {{ item.name }}（{{ item.type }} / {{ item.model }}）</span>
          <template #actions>
            <a @click="onEdit(item)">载入</a>
          </template>
        </a-list-item>
      </template>
    </a-list>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { listAgentConfigs, upsertAgentConfig } from '@/api/voice'
import type { AgentConfig } from '@/types/voice'

const saving = ref(false)
const rows = ref<AgentConfig[]>([])

const empty = (): AgentConfig => ({
  agent_id: '',
  name: '',
  type: 'agentscope',
  model: 'qwen-plus',
  system_prompt: '',
  tool_bindings: [],
  mcp_bindings: [],
  max_react_iters: 5,
  enable_plan: true,
})

const form = reactive<AgentConfig>(empty())

const typeOptions = [
  { label: 'AgentScope', value: 'agentscope' },
  { label: 'Dify', value: 'dify' },
  { label: '直连 LLM', value: 'direct' },
]

async function load() {
  try {
    const res = await listAgentConfigs()
    rows.value = res as unknown as AgentConfig[]
  } catch (e) {
    message.error(`加载失败: ${(e as Error).message}`)
  }
}

async function onSave() {
  if (!form.agent_id) {
    message.warning('请填写 Agent ID')
    return
  }
  saving.value = true
  try {
    await upsertAgentConfig(form)
    message.success('已保存')
    await load()
  } catch (e) {
    message.error(`保存失败: ${(e as Error).message}`)
  } finally {
    saving.value = false
  }
}

function onEdit(item: AgentConfig) {
  Object.assign(form, empty(), item)
}

function onReset() {
  Object.assign(form, empty())
}

onMounted(load)
</script>

<style scoped>
.cfg-form {
  max-width: 960px;
}
</style>
