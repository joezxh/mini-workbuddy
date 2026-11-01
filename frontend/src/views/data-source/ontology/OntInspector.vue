<template>
  <div class="ont-inspector">
    <a-empty v-if="!focus" :description="t2('在图谱页点击对象节点，或从审阅台选择元素进行检视')" />
    <template v-else>
      <a-descriptions size="small" bordered :column="1" class="ont-inspector__head">
        <a-descriptions-item :label="t2('元素类型')">{{ focus.kind }}</a-descriptions-item>
        <a-descriptions-item :label="t2('Code')">{{ focus.code }}</a-descriptions-item>
      </a-descriptions>

      <a-tabs v-model:activeKey="panel" size="small">
        <a-tab-pane key="evidence" :tab="t2('证据链')">
          <a-spin :spinning="loadingEv">
            <a-empty v-if="!evidence.length" :description="t2('该元素暂无留痕证据')" />
            <a-collapse v-else accordion>
              <a-collapse-panel v-for="e in evidence" :key="e.id" :header="`${e.evidence_kind} · conf ${e.confidence ?? '-'}`">
                <pre class="ont-inspector__payload">{{ pretty(e.payload) }}</pre>
              </a-collapse-panel>
            </a-collapse>
          </a-spin>
        </a-tab-pane>

        <a-tab-pane key="ai" :tab="t2('AI 语义建议')">
          <a-space direction="vertical" style="width: 100%">
            <a-button :loading="loadingSug" @click="genSuggest">{{ t2('为此元素生成语义补全') }}</a-button>
            <a-alert v-if="suggestNote" type="info" show-icon :message="suggestNote" />
            <a-table
              v-if="suggestItems.length"
              row-key="field"
              size="small"
              :pagination="false"
              :columns="sugCols"
              :data-source="suggestItems"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'action'">
                  <a-button
                    v-if="record.semantic_id && record.status !== 'accepted'"
                    size="small"
                    type="primary"
                    :loading="adoptingId === record.semantic_id"
                    @click="adopt(record)"
                  >{{ t2('采纳') }}</a-button>
                  <a-tag v-else-if="record.status === 'accepted'" color="green">{{ t2('已采纳') }}</a-tag>
                  <span v-else>-</span>
                </template>
              </template>
            </a-table>
            <p v-if="suggestItems.length" class="ont-inspector__hint">
              {{ t2('采纳（E22）才把文本值回写已存在元素并改写 source=human；LLM 值不自动进发布快照（D3）') }}
            </p>
          </a-space>
        </a-tab-pane>
      </a-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * 检视面板（E17 证据链 + E21 语义补全 + E22 采纳闭环）：属性 / 证据 / AI 建议。
 * suggest 响应的 items 现在回传 semantic_id，此处直接调 E22 adopt 完成采纳。
 */
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { ontologyEvidence, semanticsAdopt, semanticsSuggest } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{
  ontologyId: number | null
  focus: { kind: string; code: string } | null
}>()
const emit = defineEmits<{ (e: 'adopted'): void }>()

const panel = ref('evidence')
const evidence = ref<any[]>([])
const loadingEv = ref(false)
const loadingSug = ref(false)
const adoptingId = ref<number | null>(null)
const suggestItems = ref<any[]>([])
const suggestNote = ref('')

const sugCols = [
  { title: t2('字段'), dataIndex: 'field', key: 'field', width: 120 },
  { title: t2('建议值'), dataIndex: 'value', key: 'value' },
  { title: t2('操作'), key: 'action', width: 90 },
]

function pretty(v: any) {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

async function loadEvidence() {
  evidence.value = []
  if (!props.ontologyId || !props.focus) return
  loadingEv.value = true
  try {
    const resp: any = await ontologyEvidence(props.ontologyId, {
      element_kind: props.focus.kind, element_code: props.focus.code,
    })
    evidence.value = resp?.items || []
  } finally {
    loadingEv.value = false
  }
}

async function genSuggest() {
  suggestItems.value = []
  suggestNote.value = ''
  if (!props.ontologyId || !props.focus) return
  loadingSug.value = true
  try {
    const resp: any = await semanticsSuggest(props.ontologyId, {
      element_kind: props.focus.kind === 'relation' ? 'relation' : 'object',
      element_codes: [props.focus.code],
    })
    suggestItems.value = (resp?.items || []).filter((i: any) => i.element_code === props.focus!.code)
    if (!suggestItems.value.length) suggestNote.value = resp?.note || t2('无可用建议')
  } catch {
    // 503 SEMANTIC_UNAVAILABLE 已由拦截器提示
  } finally {
    loadingSug.value = false
  }
}

/** E22 采纳：把单条文本建议回写已存在元素（source → human），成功后标记行内状态 */
async function adopt(record: any) {
  if (!props.ontologyId || !record.semantic_id) return
  adoptingId.value = record.semantic_id
  try {
    const resp: any = await semanticsAdopt(props.ontologyId, record.semantic_id)
    record.status = resp?.status || 'accepted'
    message.success(t2('语义建议已采纳'))
    emit('adopted')
  } catch {
    /* 404/400 已由拦截器按 code 提示 */
  } finally {
    adoptingId.value = null
  }
}

watch(() => props.focus, (f) => {
  suggestItems.value = []
  suggestNote.value = ''
  panel.value = 'evidence'
  if (f) loadEvidence()
}, { deep: true, immediate: true })

defineExpose({ show: (kind: string, code: string) => { void kind; void code; } })
</script>

<style lang="less" scoped>
.ont-inspector {
  &__head {
    margin-bottom: 12px;
  }
  &__payload {
    margin: 0;
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-all;
  }
  &__hint {
    color: var(--fg-mute, #999);
    font-size: 12px;
  }
}
</style>
