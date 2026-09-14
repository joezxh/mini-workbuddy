<template>
  <a-card title="工具调用策略">
    <a-form layout="vertical" :model="form" class="cfg-form">
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="工具名">
            <a-input v-model:value="form.tool_name" placeholder="如 search_law" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="启用">
            <a-switch v-model:checked="form.enabled" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="超时（ms）">
            <a-input-number v-model:value="form.timeout_ms" :min="500" :max="60000" :step="500" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="每轮最大调用次数">
            <a-input-number v-model:value="form.max_calls_per_turn" :min="1" :max="10" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="结果体积上限（bytes）">
            <a-input-number v-model:value="form.max_result_bytes" :min="1024" :step="1024" />
          </a-form-item>
        </a-col>
      </a-row>

      <a-space>
        <a-button type="primary" :loading="saving" @click="onSave">保存</a-button>
        <a-button @click="onReset">重置</a-button>
      </a-space>
    </a-form>

    <a-divider />
    <a-table
      :columns="columns"
      :data-source="rows"
      :pagination="false"
      size="small"
      row-key="tool_name"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'enabled'">
          <a-tag :color="record.enabled ? 'green' : 'red'">
            {{ record.enabled ? '启用' : '停用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="onEdit(record)">编辑</a>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { listToolPolicies, upsertToolPolicy } from '@/api/voice'
import type { ToolPolicy } from '@/types/voice'

const saving = ref(false)
const rows = ref<ToolPolicy[]>([])

const empty = (): ToolPolicy => ({
  tool_name: '',
  enabled: true,
  timeout_ms: 8000,
  max_calls_per_turn: 2,
  max_result_bytes: 32768,
})

const form = reactive<ToolPolicy>(empty())

const columns = [
  { title: '工具名', dataIndex: 'tool_name', key: 'tool_name' },
  { title: '状态', dataIndex: 'enabled', key: 'enabled' },
  { title: '超时(ms)', dataIndex: 'timeout_ms', key: 'timeout_ms' },
  { title: '每轮上限', dataIndex: 'max_calls_per_turn', key: 'max_calls_per_turn' },
  { title: '结果上限(B)', dataIndex: 'max_result_bytes', key: 'max_result_bytes' },
  { title: '操作', key: 'action' },
]

async function load() {
  try {
    const res = await listToolPolicies()
    rows.value = res as unknown as ToolPolicy[]
  } catch (e) {
    message.error(`加载失败: ${(e as Error).message}`)
  }
}

async function onSave() {
  if (!form.tool_name) {
    message.warning('请填写工具名')
    return
  }
  saving.value = true
  try {
    await upsertToolPolicy(form)
    message.success('已保存')
    await load()
  } catch (e) {
    message.error(`保存失败: ${(e as Error).message}`)
  } finally {
    saving.value = false
  }
}

function onEdit(item: ToolPolicy) {
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
