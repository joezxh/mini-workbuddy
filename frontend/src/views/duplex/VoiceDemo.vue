<template>
  <div class="voice-demo">
    <a-page-header
      title="调解语音 RTC 演示"
      sub-title="M2 · 能力协商 / 轮次状态机 / 重连 / 工具调用 / 本地管线"
    >
      <template #extra>
        <a-input v-model:value="caseNumber" placeholder="案件编号" style="width: 200px" />
        <a-select
          v-model:value="provider"
          style="width: 180px"
          :options="providerOptions"
        />
        <a-select
          v-model:value="selectedModel"
          style="width: 220px"
          placeholder="语音模型（默认使用数据库配置）"
          :options="modelOptions"
          :loading="modelLoading"
          show-search
          option-filter-prop="label"
        />
        <a-button type="primary" :disabled="!caseNumber" @click="showChannel = true">
          进入语音通道
        </a-button>
      </template>
    </a-page-header>

    <VoiceChannel
      v-if="showChannel"
      :case-number="caseNumber"
      :provider="provider"
      :model-id="selectedModel"
    />
    <a-empty v-else description="输入案件编号并进入语音通道" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import VoiceChannel from '@/components/voice/VoiceChannel.vue'
import type { VoiceModel, VoiceModelDefault, VoiceProvider } from '@/types/voice'
import { listVoiceModels, getVoiceModelDefault } from '@/api/voice'

const caseNumber = ref('1001')
const provider = ref<VoiceProvider>('dashscope')
const showChannel = ref(false)

const providerOptions = [
  { label: 'DashScope（云端）', value: 'dashscope' },
  { label: '本地 S2S（Docker）', value: 's2s' },
  { label: 'Local（本地回退）', value: 'local' },
]

const voiceModels = ref<VoiceModel[]>([])
const selectedModel = ref<number | undefined>(undefined)
const modelLoading = ref(false)

// 后端 listVoiceModels 已过滤不可用模型（DashScope 模型名无效 / 密钥为空），
// 这里再按当前生效的 provider 平台过滤：s2s 只显示本地 Docker 模型，
// 云端 provider 只显示云端模型。
function modelsFor(p: VoiceProvider): VoiceModel[] {
  return voiceModels.value.filter((m) => (p === 's2s' ? m.platform === 's2s' : m.platform !== 's2s'))
}

const modelOptions = computed(() =>
  modelsFor(provider.value).map((m) => ({
    label: m.is_default ? `${m.name}（默认）` : m.name,
    value: m.id,
  })),
)

// 切换 provider 时，若当前选中模型不属于该平台则自动改选该平台第一个可用模型
watch(provider, () => {
  const pool = modelsFor(provider.value)
  if (!pool.some((m) => m.id === selectedModel.value)) {
    selectedModel.value = pool[0]?.id
  }
})

async function loadVoiceModels() {
  modelLoading.value = true
  try {
    const [models, def] = await Promise.all([listVoiceModels(), getVoiceModelDefault()])
    voiceModels.value = models
    // 默认模型自适应：按其平台自动切换 provider（s2s → 本地 Docker，否则云端）
    const applyDefault = (model: VoiceModel) => {
      provider.value = model.platform === 's2s' ? 's2s' : 'dashscope'
      selectedModel.value = model.id
    }
    const defaultModel = def?.configured
      ? models.find((m) => m.id === def.model_id)
      : undefined
    if (defaultModel) applyDefault(defaultModel)
    else if (models.length) applyDefault(models[0])
    else selectedModel.value = undefined
  } finally {
    modelLoading.value = false
  }
}

onMounted(loadVoiceModels)
</script>

<style scoped>
.voice-demo {
  padding: 16px;
}
</style>
