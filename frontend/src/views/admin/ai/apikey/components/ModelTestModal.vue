<template>
  <a-modal
    v-model:open="visible"
    title="模型测试"
    width="1100px"
    :footer="null"
    :destroy-on-close="true"
    @cancel="handleClose"
  >
    <div class="model-test-container">
      <!-- 模型选择区 -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">选择模型</span>
          <a-tag color="blue">已选 {{ selectedModels.length }} 个</a-tag>
        </div>
        <a-checkbox-group v-model:value="selectedModelIds" class="model-checkbox-group">
          <a-checkbox
            v-for="m in availableModels"
            :key="m.id"
            :value="m.id"
            class="model-checkbox"
          >
            <span class="model-label">
              <span class="model-name">{{ m.name }}</span>
              <span class="model-id">{{ m.model }}</span>
              <a-tag :color="typeTagColor(m.type)" size="small">{{ typeName(m.type) }}</a-tag>
            </span>
          </a-checkbox>
        </a-checkbox-group>
      </div>

      <!-- 输入区 -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">提示词</span>
        </div>
        <a-textarea
          v-model:value="prompt"
          placeholder="输入测试提示词..."
          :rows="3"
          :maxlength="4000"
          show-count
        />
        <a-collapse :bordered="false" ghost class="advanced-collapse">
          <a-collapse-panel key="1" header="高级选项">
            <a-input
              v-model:value="systemPrompt"
              placeholder="系统提示词（可选）"
              :rows="2"
              style="margin-bottom: 8px"
            />
          </a-collapse-panel>
        </a-collapse>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <a-button type="primary" :loading="isRunning" :disabled="!canRun" @click="runTest">
          <SendOutlined /> 开始测试
        </a-button>
        <a-button v-if="isRunning" danger @click="stopTest">
          <StopOutlined /> 停止
        </a-button>
        <a-button @click="clearResults">
          <ClearOutlined /> 清空结果
        </a-button>
      </div>

      <!-- 结果展示区 -->
      <div class="results-section" v-if="Object.keys(results).length > 0">
        <div class="section-header">
          <span class="section-title">测试结果</span>
        </div>
        <div class="results-grid" :class="{ 'multi-grid': Object.keys(results).length > 1 }">
          <div
            v-for="(result, modelId) in results"
            :key="modelId"
            class="result-card"
          >
            <div class="result-header">
              <span class="result-model-name">{{ result.modelName }}</span>
              <a-tag :color="result.status === 'done' ? 'success' : result.status === 'error' ? 'error' : 'processing'" size="small">
                {{ statusText(result.status) }}
              </a-tag>
              <span v-if="result.duration" class="result-meta">{{ result.duration }}ms</span>
              <span v-if="result.tokenCount" class="result-meta">{{ result.tokenCount }} tokens</span>
            </div>

            <!-- 文本输出 -->
            <div v-if="result.type === 'text'" class="result-content">
              <div v-if="result.reasoning" class="reasoning-block">
                <div class="reasoning-label">💭 思考过程</div>
                <div class="reasoning-text">{{ result.reasoning }}</div>
              </div>
              <div class="content-text" v-html="renderMarkdown(result.content)"></div>
              <span v-if="result.status === 'running'" class="cursor-blink">▌</span>
            </div>

            <!-- Embedding 输出 -->
            <div v-else-if="result.type === 'embedding'" class="result-content">
              <a-descriptions :column="2" size="small" bordered>
                <a-descriptions-item label="维度">{{ result.dimensions }}</a-descriptions-item>
                <a-descriptions-item label="Token 数">{{ result.tokenCount || '-' }}</a-descriptions-item>
              </a-descriptions>
              <div class="embedding-preview">
                <div class="embedding-label">向量预览（前 {{ result.preview?.length || 0 }} 维）：</div>
                <div class="embedding-values">
                  <span v-for="(v, i) in result.preview" :key="i" class="embedding-val">
                    [{{ i }}] {{ typeof v === 'number' ? v.toFixed(6) : v }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 错误输出 -->
            <div v-else-if="result.type === 'error'" class="result-content result-error">
              <a-alert type="error" :message="result.errorMessage" show-icon />
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import { SendOutlined, StopOutlined, ClearOutlined } from '@ant-design/icons-vue'
import { fetchModelTestStream, type AiChatModel } from '@/api/ai-apikey'

interface TestResult {
  modelName: string
  status: 'running' | 'done' | 'error'
  type: 'text' | 'embedding' | 'error'
  content: string
  reasoning: string
  errorMessage: string
  dimensions: number
  preview: number[]
  duration: number
  tokenCount: number
}

const props = defineProps<{
  open: boolean
  models: AiChatModel[]
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
})

const availableModels = computed(() => props.models || [])
const selectedModelIds = ref<number[]>([])
const prompt = ref('')
const systemPrompt = ref('')
const isRunning = ref(false)
const results = ref<Record<number, TestResult>>({})

const abortControllers = ref<AbortController[]>([])

const selectedModels = computed(() =>
  availableModels.value.filter(m => selectedModelIds.value.includes(m.id))
)

const canRun = computed(() =>
  selectedModelIds.value.length > 0 && prompt.value.trim().length > 0 && !isRunning.value
)

// 打开时默认选中所有模型
watch(
  () => props.open,
  (val) => {
    if (val) {
      selectedModelIds.value = availableModels.value.map(m => m.id)
      results.value = {}
      prompt.value = ''
      systemPrompt.value = ''
    }
  }
)

function typeName(type?: number): string {
  if (type === 5) return 'Embedding'
  if (type === 3) return '图片'
  if (type === 4) return '语音'
  return '对话'
}

function typeTagColor(type?: number): string {
  if (type === 5) return 'purple'
  if (type === 3) return 'orange'
  if (type === 4) return 'cyan'
  return 'blue'
}

function statusText(status: string): string {
  if (status === 'running') return '响应中...'
  if (status === 'done') return '完成'
  if (status === 'error') return '错误'
  return status
}

function renderMarkdown(text: string): string {
  // 简易 markdown 渲染：代码块 + 换行
  if (!text) return ''
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\n/g, '<br/>')
}

async function runTest() {
  if (!canRun.value) return
  isRunning.value = true
  abortControllers.value = []

  const models = selectedModels.value
  const startTime = Date.now()

  for (const model of models) {
    const controller = new AbortController()
    abortControllers.value.push(controller)

    // 初始化结果
    results.value[model.id] = {
      modelName: `${model.name} (${model.model})`,
      status: 'running',
      type: 'text',
      content: '',
      reasoning: '',
      errorMessage: '',
      dimensions: 0,
      preview: [],
      duration: 0,
      tokenCount: 0,
    }

    // 并行启动所有模型的测试
    processModelStream(model, controller.signal, startTime)
  }
}

async function processModelStream(model: AiChatModel, signal: AbortSignal, startTime: number) {
  try {
    const res = await fetchModelTestStream(
      {
        model_id: model.id,
        prompt: prompt.value,
        system_prompt: systemPrompt.value || undefined,
        stream: true,
      },
      signal
    )

    const reader = res.body?.getReader()
    if (!reader) throw new Error('无法获取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6).trim()
        if (dataStr === '[DONE]') {
          const r = results.value[model.id]
          if (r) {
            r.status = 'done'
            r.duration = Date.now() - startTime
          }
          continue
        }
        try {
          const data = JSON.parse(dataStr)
          const r = results.value[model.id]
          if (!r) continue

          if (data.error) {
            r.status = 'error'
            r.type = 'error'
            r.errorMessage = data.message || '未知错误'
            r.duration = Date.now() - startTime
            continue
          }
          if (data.content) {
            r.content += data.content
          }
          if (data.reasoning) {
            r.reasoning += data.reasoning
          }
          // Embedding 结果
          if (data.type === 'embedding') {
            r.type = 'embedding'
            r.dimensions = data.dimensions || 0
            r.preview = data.preview || []
            r.tokenCount = data.usage?.total_tokens || 0
            r.status = 'done'
            r.duration = Date.now() - startTime
          }
          // Token 统计
          if (data.usage) {
            r.tokenCount = data.usage.total_tokens || data.usage.completion_tokens || 0
          }
        } catch {
          // ignore parse errors
        }
      }
    }

    // 流结束但没收到 [DONE]
    const r = results.value[model.id]
    if (r && r.status === 'running') {
      r.status = 'done'
      r.duration = Date.now() - startTime
    }
  } catch (e: any) {
    if (e.name === 'AbortError') {
      const r = results.value[model.id]
      if (r) {
        r.status = 'done'
        r.duration = Date.now() - startTime
      }
      return
    }
    const r = results.value[model.id]
    if (r) {
      r.status = 'error'
      r.type = 'error'
      r.errorMessage = e.message || '请求失败'
      r.duration = Date.now() - startTime
    }
  }

  // 检查是否所有模型都完成了
  checkAllDone()
}

function checkAllDone() {
  const allResults = Object.values(results.value)
  if (allResults.length > 0 && allResults.every(r => r.status !== 'running')) {
    isRunning.value = false
  }
}

function stopTest() {
  abortControllers.value.forEach(c => c.abort())
  abortControllers.value = []
  isRunning.value = false
  message.info('已停止测试')
}

function clearResults() {
  results.value = {}
}

function handleClose() {
  stopTest()
  visible.value = false
}

onBeforeUnmount(() => {
  abortControllers.value.forEach(c => c.abort())
})
</script>

<style lang="less" scoped>
.model-test-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section {
  .section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .section-title {
      font-weight: 600;
      font-size: 14px;
      color: #1a1a1a;
    }
  }
}

.model-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 120px;
  overflow-y: auto;
  padding: 8px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.model-checkbox {
  margin-right: 0 !important;
}

.model-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  .model-name {
    font-weight: 500;
  }

  .model-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #8c8c8c;
    background: #f0f0f0;
    padding: 1px 4px;
    border-radius: 3px;
  }
}

.advanced-collapse {
  margin-top: 8px;

  :deep(.ant-collapse-header) {
    padding: 4px 0 !important;
    font-size: 13px;
    color: #8c8c8c;
  }
}

.action-bar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.results-section {
  .section-header {
    margin-bottom: 8px;
  }
}

.results-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;

  &.multi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 12px;
  }
}

.result-card {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;

  .result-model-name {
    font-weight: 600;
    font-size: 13px;
    flex: 1;
  }

  .result-meta {
    font-size: 11px;
    color: #8c8c8c;
    font-family: monospace;
  }
}

.result-content {
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
  min-height: 60px;

  .content-text {
    :deep(.code-block) {
      background: #282c34;
      color: #abb2bf;
      padding: 12px;
      border-radius: 4px;
      overflow-x: auto;
      font-size: 12px;
      margin: 8px 0;
    }

    :deep(.inline-code) {
      background: #f0f0f0;
      padding: 2px 4px;
      border-radius: 3px;
      font-size: 12px;
    }
  }
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #1890ff;
  font-weight: bold;
}

@keyframes blink {
  50% { opacity: 0; }
}

.reasoning-block {
  background: #f6f8fa;
  border-left: 3px solid #d1d5db;
  padding: 8px 12px;
  margin-bottom: 12px;
  border-radius: 0 4px 4px 0;
  font-size: 12px;
  color: #6b7280;

  .reasoning-label {
    font-weight: 600;
    margin-bottom: 4px;
    font-size: 12px;
  }

  .reasoning-text {
    white-space: pre-wrap;
    max-height: 150px;
    overflow-y: auto;
  }
}

.result-error {
  padding: 12px;
}

.embedding-preview {
  margin-top: 12px;

  .embedding-label {
    font-weight: 500;
    margin-bottom: 8px;
    font-size: 13px;
  }

  .embedding-values {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    max-height: 200px;
    overflow-y: auto;
    background: #f9f9f9;
    padding: 8px;
    border-radius: 4px;
  }

  .embedding-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #595959;
    background: #fff;
    padding: 2px 6px;
    border-radius: 3px;
    border: 1px solid #e8e8e8;
  }
}
</style>
