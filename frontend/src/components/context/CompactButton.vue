<!--
  CompactButton.vue
  PR-3 Task 15: 9 模式通用跨模式上下文压缩按钮(Ant Design Vue 版)

  Props:
    - mode:           string               必填,9 模式之一(general / react / thinking /
                                            deep_research / skill / agent / team / scheduled / shared)
    - contextKey:     string               必填,context_key
    - isCompacting?:  boolean              受控加载状态(由 useCrossModeCompaction 提供)
    - lastResult?:    CompactionResponse | null  最近一次成功结果
    - lastError?:     string | null        最近一次错误消息
    - targetTokens?:  number               目标 token 数(默认 8000)

  Emits:
    - compact(req: CompactionRequest)   请求压缩(由父组件 useCrossModeCompaction 监听执行)
    - open-custom()                      打开自定义配置 modal

  设计要点:
  - 使用 Ant Design Vue(`a-button` / `a-dropdown` / `a-modal` / `a-menu` / `a-form`),
    与项目技术栈统一;沿用 useCrossModeCompaction(PR-3 Task 12) 进行实际 API 调用。
  - 组件本身不直接调用 axios,保持 SSR-friendly(避免 vue-router / window 依赖)。
  - 不引入新依赖。
-->
<template>
  <div class="compact-button-container">
    <a-dropdown trigger="click">
      <a-button
        type="warning"
        size="small"
        :loading="isCompacting"
        :disabled="isCompacting"
      >
        <span v-if="lastResult?.success">优化上下文</span>
        <span v-else>压缩上下文</span>
        <span class="mode-chip">{{ mode }}</span>
        <DownOutlined />
      </a-button>
      <template #overlay>
        <a-menu @click="onMenuClick">
          <a-menu-item key="sliding_window" :disabled="isCompacting">
            滑动窗口 (保留最近 5 条)
          </a-menu-item>
          <a-menu-item key="priority_eviction" :disabled="isCompacting">
            优先级驱逐 (保留最高 5 个)
          </a-menu-item>
          <a-menu-item key="access_based" :disabled="isCompacting">
            按访问频率 (保留最频繁的 3 个)
          </a-menu-item>
          <a-menu-item key="summary_and_keep_latest" :disabled="isCompacting">
            摘要并保留最新 (推荐)
          </a-menu-item>
          <a-menu-divider />
          <a-menu-item key="custom" :disabled="isCompacting">
            ⚙️ 自定义设置...
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>

    <a-modal
      v-model:open="showCustomDialog"
      title="自定义压缩配置"
      :footer="null"
      width="500px"
    >
      <a-form layout="vertical">
        <a-form-item label="上下文件键">
          <a-input v-model:value="customConfig.key" placeholder="例如:user_preferences" />
        </a-form-item>
        <a-form-item label="压缩策略">
          <a-select v-model:value="customConfig.strategy">
            <a-select-option value="sliding_window">滑动窗口</a-select-option>
            <a-select-option value="priority_eviction">优先级驱逐</a-select-option>
            <a-select-option value="access_based">访问频率</a-select-option>
            <a-select-option value="summary_and_keep_latest">摘要并保留最新</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="目标 Token 数">
          <a-input-number
            v-model:value="customConfig.target_tokens"
            :min="1000"
            :max="32000"
            :step="1000"
          />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button @click="showCustomDialog = false">取消</a-button>
            <a-button type="primary" :loading="isCompacting" @click="confirmCustom">
              执行压缩
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-modal>

    <div v-if="lastError" class="error-banner">
      <a-alert :message="lastError" type="error" show-icon />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { DownOutlined } from '@ant-design/icons-vue'
import type { CompactionRequest, CompactionResponse } from '@/api/aiContext.types'

const props = withDefaults(
  defineProps<{
    mode: string
    contextKey: string
    isCompacting?: boolean
    lastResult?: CompactionResponse | null
    lastError?: string | null
    targetTokens?: number
  }>(),
  {
    isCompacting: false,
    lastResult: null,
    lastError: null,
    targetTokens: 8000,
  },
)

const emit = defineEmits<{
  (e: 'compact', req: CompactionRequest): void
  (e: 'open-custom'): void
}>()

const showCustomDialog = ref(false)
const customConfig = ref({
  key: props.contextKey ?? 'default',
  strategy: 'summary_and_keep_latest' as CompactionRequest['strategy'],
  target_tokens: props.targetTokens ?? 8000,
})

function buildRequest(strategy: CompactionRequest['strategy']): CompactionRequest {
  return {
    mode: props.mode,
    key: customConfig.value.key || props.contextKey || 'default',
    strategy,
    target_tokens: customConfig.value.target_tokens,
  }
}

function onMenuClick(info: { key: string | number }) {
  const key = String(info.key)
  if (key === 'custom') {
    showCustomDialog.value = true
    emit('open-custom')
    return
  }
  emit('compact', buildRequest(key as CompactionRequest['strategy']))
}

function confirmCustom() {
  showCustomDialog.value = false
  emit('compact', {
    mode: props.mode,
    key: customConfig.value.key,
    strategy: customConfig.value.strategy,
    target_tokens: customConfig.value.target_tokens,
  })
}
</script>

<style scoped>
.compact-button-container {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
}
.mode-chip {
  margin-left: 6px;
  font-family: monospace;
  font-size: 11px;
  color: #fff;
  background: rgba(255, 255, 255, 0.2);
  padding: 0 6px;
  border-radius: 6px;
}
.error-banner {
  margin-top: 8px;
}
</style>
