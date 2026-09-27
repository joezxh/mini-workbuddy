<!--
  ManualOverrideModal.vue
  PR-3 Task 16: 9 模式通用手动策略覆写 modal

  Props:
    - open?:           boolean         受控显隐(默认 false)
    - sessionId?:      number          默认 session_id
    - initialMode?:    string          默认 mode(9 模式之一,默认 'shared')
    - initialAction?:  string          默认动作(delete_entry / update_entry / add_new_entry / set_priority)
    - isOverriding?:   boolean         加载状态(由父组件控制)

  Emits:
    - update:open(v: boolean)             Ant Design Vue v-model 兼容
    - submit(payload: OverridePayload)    提交手动覆写请求
    - cancel()                            取消

  设计要点:
  - Ant Design Vue + a-modal / a-form / a-select / a-input-number
  - 9 模式全部从 MODE_OPTIONS 数组数据驱动渲染
  - SSR-friendly,不直接调 axios,通过 emit submit 委托父组件
  - 不引入新依赖
-->
<template>
  <div class="manual-override-modal">
    <a-button type="primary" @click="emit('update:open', true)">
      🔧 手动干预上下文
    </a-button>

    <a-modal
      :open="open"
      title="手动干预上下文"
      :footer="null"
      width="640px"
      :destroy-on-close="true"
      @cancel="emit('update:open', false)"
    >
      <a-form layout="vertical">
        <a-form-item label="会话 ID">
          <a-input-number
            v-model:value="form.session_id"
            :min="1"
            style="width: 100%"
          />
        </a-form-item>

        <a-form-item label="目标模式">
          <a-select v-model:value="form.mode">
            <a-select-option
              v-for="m in MODE_OPTIONS"
              :key="m.value"
              :value="m.value"
            >
              {{ m.label }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="上下文件键">
          <a-input
            v-model:value="form.key"
            placeholder="例如:user_preferences, knowledge_base"
          />
        </a-form-item>

        <a-form-item label="干预类型">
          <a-select v-model:value="form.action_type">
            <a-select-option value="delete_entry">🗑️ 删除特定条目</a-select-option>
            <a-select-option value="update_entry">✏️ 更新现有条目</a-select-option>
            <a-select-option value="add_new_entry">➕ 添加新条目</a-select-option>
            <a-select-option value="set_priority">⭐ 设置优先级</a-select-option>
          </a-select>
        </a-form-item>

        <template v-if="form.action_type === 'delete_entry'">
          <a-form-item label="要删除的条目 ID">
            <a-input v-model:value="form.entry_id" placeholder="条目 ID" />
          </a-form-item>
        </template>

        <template v-else-if="form.action_type === 'update_entry' || form.action_type === 'add_new_entry'">
          <a-form-item label="新的数据内容(JSON)">
            <a-textarea
              v-model:value="form.new_data"
              :rows="6"
              placeholder='{"key": "value"}'
            />
          </a-form-item>
        </template>

        <template v-else-if="form.action_type === 'set_priority'">
          <a-form-item label="优先级 (0-10)">
            <a-input-number
              v-model:value="form.priority"
              :min="0"
              :max="10"
              style="width: 100%"
            />
          </a-form-item>
        </template>

        <a-form-item>
          <a-space>
            <a-button @click="emit('update:open', false); emit('cancel')">
              取消
            </a-button>
            <a-button
              type="primary"
              :loading="isOverriding"
              @click="onSubmit"
            >
              执行手动干预
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

export interface OverridePayload {
  session_id: number
  mode: string
  key: string
  action_type: 'delete_entry' | 'update_entry' | 'add_new_entry' | 'set_priority'
  entry_id?: string
  data?: Record<string, any>
  priority?: number
  timestamp: string
}

const MODE_OPTIONS = [
  { value: 'general', label: '通用对话 (general)' },
  { value: 'react', label: 'ReAct 计划 (react)' },
  { value: 'thinking', label: '深度思考 (thinking)' },
  { value: 'deep_research', label: '深度研究 (deep_research)' },
  { value: 'skill', label: '技能执行 (skill)' },
  { value: 'agent', label: '智能体 (agent)' },
  { value: 'team', label: '智能体团队 (team)' },
  { value: 'scheduled', label: '云端调度 (scheduled)' },
  { value: 'shared', label: '共享层 (shared)' },
]

const props = withDefaults(
  defineProps<{
    open?: boolean
    sessionId?: number
    initialMode?: string
    initialAction?: OverridePayload['action_type']
    isOverriding?: boolean
  }>(),
  {
    open: false,
    sessionId: 1,
    initialMode: 'shared',
    initialAction: 'delete_entry',
    isOverriding: false,
  },
)

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'submit', payload: OverridePayload): void
  (e: 'cancel'): void
}>()

const form = reactive<OverridePayload>({
  session_id: props.sessionId,
  mode: props.initialMode,
  key: '',
  action_type: props.initialAction,
  timestamp: '',
})

watch(
  () => props.sessionId,
  (v) => {
    form.session_id = v ?? 1
  },
)

watch(
  () => form.mode,
  () => {
    form.key = ''
  },
)

function onSubmit() {
  const payload: OverridePayload = {
    session_id: form.session_id,
    mode: form.mode,
    key: form.key,
    action_type: form.action_type,
    timestamp: new Date().toISOString(),
  }
  if (form.action_type === 'delete_entry') {
    payload.entry_id = form.entry_id
  } else if (
    form.action_type === 'update_entry' ||
    form.action_type === 'add_new_entry'
  ) {
    try {
      payload.data = form.new_data ? JSON.parse(form.new_data) : {}
    } catch {
      payload.data = { _raw: form.new_data }
    }
  } else if (form.action_type === 'set_priority') {
    payload.priority = form.priority ?? 5
  }
  emit('submit', payload)
}
</script>

<style scoped>
.manual-override-modal {
  display: inline-block;
}
</style>
