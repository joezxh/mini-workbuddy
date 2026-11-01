<template>
  <div class="ont-review">
    <a-space wrap class="ont-review__bar">
      <a-select v-model:value="filters.status" style="width: 130px" @change="reload">
        <a-select-option value="suggested">{{ t2('待审') }}</a-select-option>
        <a-select-option value="accepted">{{ t2('已采纳') }}</a-select-option>
        <a-select-option value="rejected">{{ t2('已驳回') }}</a-select-option>
      </a-select>
      <a-select v-model:value="filters.kind" style="width: 130px" allow-clear :placeholder="t2('全部类型')" @change="reload">
        <a-select-option v-for="k in KINDS" :key="k" :value="k">{{ k }}</a-select-option>
      </a-select>
      <a-select v-model:value="filters.origin" style="width: 130px" allow-clear :placeholder="t2('全部来源')" @change="reload">
        <a-select-option value="rule">{{ t2('规则') }}</a-select-option>
        <a-select-option value="llm">{{ t2('LLM') }}</a-select-option>
      </a-select>
      <a-button @click="reload">{{ t2('刷新') }}</a-button>
      <a-divider type="vertical" />
      <template v-if="filters.status === 'suggested'">
        <a-button :disabled="!selected.length" @click="batchAccept">{{ t2('采纳选中') }}</a-button>
        <a-button :disabled="!selected.length" danger @click="batchReject">{{ t2('驳回选中') }}</a-button>
        <a-popconfirm :title="t2('确认采纳全部待审项？')" @confirm="acceptAll">
          <a-button>{{ t2('全部采纳') }}</a-button>
        </a-popconfirm>
      </template>
    </a-space>

    <a-alert v-if="pending.total" type="info" show-icon class="ont-review__pending"
             :message="`${t2('待审')} ${pending.total}：对象 ${pending.object} · 属性 ${pending.property} · 关系 ${pending.relation} · 映射 ${pending.mapping}`" />

    <a-table
      row-key="id"
      size="small"
      :columns="columns"
      :data-source="items"
      :loading="loading"
      :row-selection="filters.status === 'suggested' ? { selectedRowKeys: selected, onChange: (keys: any) => (selected = keys) } : undefined"
      :pagination="{ pageSize: 20, total, showSizeChanger: false }"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'origin'">
          <a-tag :color="record.origin === 'llm' ? 'orange' : 'blue'">{{ record.origin }}</a-tag>
        </template>
        <template v-else-if="column.key === 'confidence'">
          <a-tag :color="confColor(record.confidence)">{{ fmtConf(record.confidence) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'name'">
          {{ record.delta?.display_name || record.delta?.name || '-' }}
        </template>
        <template v-else-if="column.key === 'pii'">
          <a-tag v-if="record.delta?.pii_level" :color="record.delta?.pii_level !== 'L1' ? 'red' : 'default'">
            {{ record.delta?.pii_level }}
          </a-tag>
          <span v-if="record.delta?.pii_level && !record.delta?.mask_rule" class="ont-review__maskwarn">{{ t2('未脱敏') }}</span>
        </template>
        <template v-else-if="column.key === 'verdict_reason'">
          <span :title="record.verdict_reason">{{ clip(record.verdict_reason, 40) }}</span>
        </template>
        <template v-else-if="column.key === 'op'">
          <a-space>
            <a-button v-if="filters.status === 'suggested'" size="small" type="link" @click="act(record, 'accept')">{{ t2('采纳') }}</a-button>
            <a-button v-if="filters.status === 'suggested'" size="small" type="link" danger @click="act(record, 'reject')">{{ t2('驳回') }}</a-button>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
/**
 * 统一审阅台（E9/E10）：对象/属性/关系/映射四类同台，批量采纳/驳回（§4.5 修 R10）。
 * 属性行含 pii_level / mask_rule 红标，使门禁第 5 项在审阅时可见可修（§6.3-6）。
 * 来源徽标 rule|llm 分开计（§5.7 代价：审阅台区分两种候选来源）。
 */
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { reviewQueue, reviewOntology } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{ ontologyId: number | null }>()
const emit = defineEmits<{ (e: 'reviewed'): void }>()

const KINDS = ['object', 'property', 'relation', 'mapping']
const items = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const selected = ref<number[]>([])
const pending = reactive({ object: 0, property: 0, relation: 0, mapping: 0, total: 0 })
const filters = reactive({ status: 'suggested', kind: undefined as string | undefined, origin: undefined as string | undefined, page: 1 })

const columns = computed(() => {
  const base = [
    { title: t2('类型'), dataIndex: 'element_kind', key: 'element_kind', width: 90 },
    { title: t2('Code'), dataIndex: 'element_code', key: 'element_code', width: 180 },
    { title: t2('名称'), key: 'name', width: 140 },
    { title: t2('来源'), key: 'origin', width: 80 },
    { title: t2('置信度'), key: 'confidence', width: 90 },
    { title: t2('校验结论'), key: 'verdict_reason', ellipsis: true },
  ]
  if (filters.kind === 'property' || items.value.some((i) => i.element_kind === 'property')) {
    base.splice(5, 0, { title: t2('PII'), key: 'pii', width: 120 } as any)
  }
  return [...base, { title: t2('操作'), key: 'op', width: 120, fixed: 'right' as const }]
})

function clip(s?: string, n = 40) {
  if (!s) return '-'
  return s.length > n ? `${s.slice(0, n)}…` : s
}
function fmtConf(c?: number) {
  return c == null ? '-' : Number(c).toFixed(2)
}
function confColor(c?: number) {
  if (c == null) return 'default'
  if (c >= 0.85) return 'green'
  if (c >= 0.65) return 'gold'
  return 'red'
}

async function reload() {
  if (!props.ontologyId) return
  loading.value = true
  selected.value = []
  try {
    const resp: any = await reviewQueue(props.ontologyId, {
      status: filters.status, kind: filters.kind, origin: filters.origin, page: filters.page, size: 20,
    })
    items.value = resp?.items || []
    total.value = resp?.total || 0
    Object.assign(pending, resp?.pending || {})
  } finally {
    loading.value = false
  }
}

function onTableChange(pag: any) {
  filters.page = pag?.current || 1
  reload()
}

async function submit(itemsPayload: { id: number; action: string }[]) {
  if (!props.ontologyId) return
  await reviewOntology(props.ontologyId, { items: itemsPayload })
  message.success(t2('审阅已提交'))
  emit('reviewed')
  reload()
}

function act(record: any, action: string) {
  submit([{ id: record.id, action }])
}
function batchAccept() {
  submit(selected.value.map((id) => ({ id, action: 'accept' })))
}
function batchReject() {
  submit(selected.value.map((id) => ({ id, action: 'reject' })))
}
async function acceptAll() {
  if (!props.ontologyId) return
  await reviewOntology(props.ontologyId, { accept_all: true })
  message.success(t2('已全部采纳'))
  emit('reviewed')
  reload()
}

watch(() => props.ontologyId, () => { filters.page = 1; reload() }, { immediate: true })
</script>

<style lang="less" scoped>
.ont-review {
  &__bar {
    margin-bottom: 8px;
  }
  &__pending {
    margin-bottom: 8px;
  }
  &__maskwarn {
    margin-left: 6px;
    color: #cf1322;
    font-size: 12px;
  }
}
</style>
