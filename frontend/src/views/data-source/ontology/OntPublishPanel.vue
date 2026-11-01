<template>
  <div class="ont-publish">
    <a-space class="ont-publish__bar">
      <a-button type="primary" @click="openForm">{{ t2('登记发布目标') }}</a-button>
      <a-button @click="reload">{{ t2('刷新') }}</a-button>
      <a-tag color="blue">{{ t2('当前版本') }} v{{ currentVersion }}</a-tag>
    </a-space>

    <a-table row-key="id" size="small" :loading="loading" :columns="columns" :data-source="rows" :pagination="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'target_type'">
          <a-tag>{{ record.target_type }}</a-tag>
        </template>
        <template v-else-if="column.key === 'stale'">
          <a-tag v-if="record.stale" color="orange">{{ t2('版本落后') }}</a-tag>
          <a-tag v-else color="green">{{ t2('最新') }}</a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-switch
            :checked="record.status === 'enabled'"
            :disabled="record.version === 0"
            checked-children="ON"
            un-checked-children="OFF"
            @change="(v: boolean) => toggle(record, v)"
          />
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="formOpen" :title="t2('登记发布目标')" :confirm-loading="submitting" @ok="doRegister">
      <a-form layout="vertical">
        <a-form-item :label="t2('目标类型')" required>
          <a-select v-model:value="form.target_type">
            <a-select-option value="skill">Skill</a-select-option>
            <a-select-option value="http">HTTP</a-select-option>
            <a-select-option value="mcp">MCP</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t2('目标标识 code')" required>
          <a-input v-model:value="form.code" :placeholder="t2('目标侧唯一标识')" />
        </a-form-item>
        <a-form-item :label="t2('名称')">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item :label="t2('描述')">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-alert
          type="info"
          show-icon
          :message="t2('仅钉当前版本；草稿态（v0）登记强制 disabled，发布后方可启用（§4.6）')"
        />
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 应用发布登记（E34 列表 + E35 登记 + E36 启停）：Skill/HTTP/MCP 绑定，运行时复用既有 ai_skill/ai_tools。
 * 版本落后 stale=true 提示重新登记；草稿态 v0 不可启用。
 */
import { reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { listAppPublishes, createAppPublish, toggleAppPublish, getOntology } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{ ontologyId: number | null }>()

const rows = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const formOpen = ref(false)
const currentVersion = ref(0)
const form = reactive({ target_type: 'skill', code: '', name: '', description: '' })

const columns = [
  { title: t2('类型'), key: 'target_type', dataIndex: 'target_type', width: 90 },
  { title: t2('标识'), dataIndex: 'code', key: 'code', width: 160 },
  { title: t2('名称'), dataIndex: 'name', key: 'name' },
  { title: t2('钉定版本'), dataIndex: 'version', key: 'version', width: 90 },
  { title: t2('新鲜度'), key: 'stale', width: 100 },
  { title: t2('启停'), key: 'status', width: 100 },
]

async function reload() {
  if (!props.ontologyId) return
  loading.value = true
  try {
    rows.value = (await listAppPublishes(props.ontologyId)) as any[]
    const ont: any = await getOntology(props.ontologyId)
    currentVersion.value = ont?.current_version ?? 0
  } finally {
    loading.value = false
  }
}

function openForm() {
  form.target_type = 'skill'
  form.code = ''
  form.name = ''
  form.description = ''
  formOpen.value = true
}

async function doRegister() {
  if (!props.ontologyId || !form.code) {
    message.warning(t2('目标标识必填'))
    return
  }
  submitting.value = true
  try {
    await createAppPublish(props.ontologyId, {
      target_type: form.target_type,
      code: form.code,
      name: form.name || undefined,
      description: form.description || undefined,
    })
    message.success(t2('登记成功'))
    formOpen.value = false
    reload()
  } finally {
    submitting.value = false
  }
}

async function toggle(record: any, enabled: boolean) {
  await toggleAppPublish(props.ontologyId!, record.id, enabled ? 'enabled' : 'disabled')
  message.success(enabled ? t2('已启用') : t2('已停用'))
  reload()
}

watch(() => props.ontologyId, reload, { immediate: true })
</script>

<style lang="less" scoped>
.ont-publish {
  &__bar {
    margin-bottom: 12px;
  }
}
</style>
