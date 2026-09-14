<template>
  <a-card title="角色语音配置">
    <a-form layout="vertical" :model="form" class="cfg-form">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="角色 ID">
            <a-input v-model:value="form.role_id" placeholder="如 mediator / party_a" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="角色名">
            <a-input v-model:value="form.role_name" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="语言">
            <a-select v-model:value="form.language" :options="languageOptions" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="音色标识">
            <a-input v-model:value="form.voice_identity" placeholder="如 female-1" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="绑定 Agent">
            <a-input v-model:value="form.agent_id" placeholder="可选，关联 Agent 配置" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="开场白">
        <a-textarea v-model:value="form.greeting" :rows="3" placeholder="进入会话时的问候语" />
      </a-form-item>

      <a-space>
        <a-button type="primary" :loading="saving" @click="onSave">保存</a-button>
        <a-button :disabled="!form.greeting" @click="onPreview">试听开场白</a-button>
      </a-space>
    </a-form>

    <a-divider />
    <a-list size="small" bordered :data-source="rows">
      <template #renderItem="{ item }">
        <a-list-item>
          <span>{{ item.role_id }} · {{ item.role_name }}（{{ item.voice_identity || '默认音色' }}）</span>
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
import { listVoiceRoles, upsertVoiceRole } from '@/api/voice'
import type { VoiceRoleConfig } from '@/types/voice'

const saving = ref(false)
const rows = ref<VoiceRoleConfig[]>([])

const empty = (): VoiceRoleConfig => ({
  role_id: '',
  role_name: '',
  greeting: '',
  voice_identity: '',
  language: 'zh-CN',
  agent_id: undefined,
  case_type: undefined,
})

const form = reactive<VoiceRoleConfig>(empty())

const languageOptions = [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' },
]

async function load() {
  try {
    const res = await listVoiceRoles()
    rows.value = res as unknown as VoiceRoleConfig[]
  } catch (e) {
    message.error(`加载失败: ${(e as Error).message}`)
  }
}

async function onSave() {
  if (!form.role_id) {
    message.warning('请填写角色 ID')
    return
  }
  saving.value = true
  try {
    await upsertVoiceRole(form)
    message.success('已保存')
    await load()
  } catch (e) {
    message.error(`保存失败: ${(e as Error).message}`)
  } finally {
    saving.value = false
  }
}

/** 试听：用浏览器语音合成朗读开场白（无需后端 TTS） */
function onPreview() {
  if (!('speechSynthesis' in window)) {
    message.warning('当前浏览器不支持语音合成')
    return
  }
  const u = new SpeechSynthesisUtterance(form.greeting)
  u.lang = form.language
  window.speechSynthesis.speak(u)
}

function onEdit(item: VoiceRoleConfig) {
  Object.assign(form, empty(), item)
}

onMounted(load)
</script>

<style scoped>
.cfg-form {
  max-width: 960px;
}
</style>
