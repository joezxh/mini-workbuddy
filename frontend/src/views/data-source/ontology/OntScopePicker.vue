<template>
  <div class="ont-scope">
    <a-space class="ont-scope__head" wrap>
      <span class="ont-scope__label">{{ t2('建模作用域（来自资产送数或助手建议）') }}</span>
      <a-tag v-if="scope.source_id" color="blue">{{ t2('数据源') }} #{{ scope.source_id }}</a-tag>
      <a-tag v-if="scope.origin" color="purple">{{ t2('来路') }}: {{ scope.origin }}</a-tag>
      <a-button size="small" :loading="loading" @click="reload">{{ t2('刷新') }}</a-button>
    </a-space>

    <div class="ont-scope__tables">
      <a-tag
        v-for="tb in tables"
        :key="tb"
        closable
        color="geekblue"
        @close="removeTable(tb)"
      >{{ tb }}</a-tag>
      <span v-if="!tables.length" class="ont-scope__hint">{{ t2('作用域为空——请在「元数据」页签勾选表送数，或用右下角助手建议作用域') }}</span>
    </div>

    <a-space class="ont-scope__add">
      <a-input v-model:value="newTable" size="small" style="width: 220px" :placeholder="t2('手动添加表名')" @pressEnter="addTable" />
      <a-button size="small" @click="addTable">{{ t2('添加') }}</a-button>
      <a-button size="small" type="primary" :loading="saving" @click="save">{{ t2('保存作用域') }}</a-button>
      <a-popconfirm :title="t2('确不清空作用域？')" @confirm="clearAll">
        <a-button size="small" danger>{{ t2('清空') }}</a-button>
      </a-popconfirm>
    </a-space>
  </div>
</template>

<script setup lang="ts">
/**
 * 作用域草稿展示/编辑（E33）：只读写 meta_ontology.draft_scope_json，不写结构表（§4.7 约束 1）。
 * 跨源不合并：一个作用域仅一个 source_id（约束 5），手动添加沿用首个 source_id。
 */
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { getDraftScope, putDraftScope, deleteDraftScope } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{ ontologyId: number | null }>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const scope = ref<Record<string, any>>({})
const loading = ref(false)
const saving = ref(false)
const newTable = ref('')

const tables = computed<string[]>(() => scope.value.tables || [])

async function reload() {
  if (!props.ontologyId) return
  loading.value = true
  try {
    scope.value = (await getDraftScope(props.ontologyId)) || {}
  } finally {
    loading.value = false
  }
}

function addTable() {
  const v = newTable.value.trim()
  if (!v) return
  if (tables.value.includes(v)) {
    newTable.value = ''
    return
  }
  scope.value = { ...scope.value, mode: 'tables', tables: [...tables.value, v] }
  newTable.value = ''
}

function removeTable(tb: string) {
  scope.value = { ...scope.value, tables: tables.value.filter((x) => x !== tb) }
}

async function save() {
  if (!props.ontologyId) return
  if (!tables.value.length) {
    message.warning(t2('作用域为空，请使用清空而非保存'))
    return
  }
  saving.value = true
  try {
    await putDraftScope(props.ontologyId, {
      mode: 'tables',
      source_id: scope.value.source_id ?? null,
      db_name: scope.value.db_name ?? null,
      database: scope.value.database ?? null,
      tables: tables.value,
      tag_ids: scope.value.tag_ids || [],
      catalog_ids: scope.value.catalog_ids || [],
      origin: scope.value.origin || 'manual',
    })
    message.success(t2('作用域已保存'))
    emit('changed')
  } finally {
    saving.value = false
  }
}

async function clearAll() {
  if (!props.ontologyId) return
  await deleteDraftScope(props.ontologyId)
  scope.value = {}
  message.success(t2('作用域已清空'))
  emit('changed')
}

watch(() => props.ontologyId, reload, { immediate: true })
defineExpose({ reload })
</script>

<style lang="less" scoped>
.ont-scope {
  &__head {
    margin-bottom: 8px;
  }
  &__label {
    font-weight: 600;
  }
  &__tables {
    min-height: 40px;
    padding: 8px;
    border: 1px dashed var(--border);
    border-radius: 6px;
    margin-bottom: 8px;
  }
  &__hint {
    color: var(--fg-mute, #999);
    font-size: 12px;
  }
}
</style>
