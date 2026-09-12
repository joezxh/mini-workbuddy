<!-- frontend/src/views/admin/workflow/components/WorkflowTestBench.vue -->
<template>
  <div>
    <a-row :gutter="16">
      <a-col :span="12">
        <h4>输入 (JSON)</h4>
        <a-textarea v-model:value="inputJson" :rows="12" placeholder='{"key": "value"}' />
        <a-button type="primary" :loading="running" style="margin-top: 8px" @click="runTest">执行测试</a-button>
      </a-col>
      <a-col :span="12">
        <h4>结果</h4>
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="状态">
            <a-tag :color="result?.success ? 'green' : 'red'">{{ result?.success ? '成功' : '失败' }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="耗时">{{ result?.latency_ms ?? '-' }} ms</a-descriptions-item>
          <a-descriptions-item label="错误" v-if="result?.error">{{ result.error }}</a-descriptions-item>
        </a-descriptions>
        <h4 style="margin-top: 12px">输出</h4>
        <pre style="background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; max-height: 400px; overflow: auto">{{ JSON.stringify(result?.output, null, 2) }}</pre>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { testFlow } from '@/api/workflow'
import { message } from 'ant-design-vue'

const props = defineProps<{ flowId: number | null }>()
const inputJson = ref('{}')
const result = ref<any>(null)
const running = ref(false)

async function runTest() {
  if (!props.flowId) { message.warning('请先选择工作流'); return }
  let inputs: any = {}
  try { inputs = JSON.parse(inputJson.value) } catch { message.error('输入 JSON 格式错误'); return }
  running.value = true
  try {
    const res = await testFlow(props.flowId, { inputs, user_id: 'test' })
    result.value = res.data
  } catch (e: any) {
    result.value = { success: false, error: e?.response?.data?.detail || '执行失败', output: {} }
  } finally { running.value = false }
}
</script>
