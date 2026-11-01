<template>
  <div class="ont-dock">
    <a-button shape="circle" size="large" type="primary" class="ont-dock__fab" @click="open = !open">
      <template #icon><robot-outlined /></template>
    </a-button>

    <div v-if="open" class="ont-dock__panel">
      <div class="ont-dock__head">
        <span>{{ t2('建模助手') }}</span>
        <a-button size="small" type="text" @click="open = false">✕</a-button>
      </div>

      <a-tabs v-model:activeKey="intent" size="small" class="ont-dock__tabs">
        <a-tab-pane key="ask" :tab="t2('询问')" />
        <a-tab-pane key="explain" :tab="t2('解释')" />
        <a-tab-pane key="propose_scope" :tab="t2('圈定')" />
        <a-tab-pane key="build" :tab="t2('草拟')" />
      </a-tabs>

      <div class="ont-dock__body">
        <!-- explain 需要元素定位 -->
        <a-space v-if="intent === 'explain'" class="ont-dock__ctx">
          <a-select v-model:value="ctxKind" style="width: 100px" size="small">
            <a-select-option value="object">object</a-select-option>
            <a-select-option value="relation">relation</a-select-option>
          </a-select>
          <a-input v-model:value="ctxCode" size="small" style="width: 160px" :placeholder="t2('元素 code')" />
        </a-space>

        <a-textarea v-model:value="utterance" :rows="2" size="small" :placeholder="placeholder" />

        <!-- build 两步：预览 → 确认 -->
        <div v-if="intent === 'build' && preview.length" class="ont-dock__preview">
          <div class="ont-dock__preview-head">
            {{ t2('候选预览') }}（{{ preview.length }}）
            <a-tag v-if="dropped" color="orange">{{ t2('幻觉丢弃') }} {{ dropped }}</a-tag>
          </div>
          <div v-for="(c, i) in preview" :key="i" class="ont-dock__cand">
            <a-tag :color="c.element_kind === 'relation' ? 'purple' : 'blue'">{{ c.element_kind }}</a-tag>
            <span>{{ c.element_code }}</span>
            <span class="ont-dock__conf">{{ c.confidence ?? '-' }}</span>
          </div>
        </div>

        <a-alert v-if="resultText" type="info" class="ont-dock__result" :message="resultText" />
        <a-alert v-if="degraded" type="warning" class="ont-dock__degraded" :message="t2('AI 不可用，已降级')" />
      </div>

      <div class="ont-dock__foot">
        <template v-if="intent === 'build'">
          <a-button size="small" :loading="busy" @click="previewBuild">{{ t2('① 预览') }}</a-button>
          <a-button size="small" type="primary" :disabled="!preview.length" :loading="busy" @click="commitBuild">{{ t2('② 确认提交') }}</a-button>
        </template>
        <template v-else>
          <a-button size="small" type="primary" :loading="busy" @click="run">{{ t2('执行') }}</a-button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 右下角常驻建模助手（E37 四档，§5.6）：ask/explain/propose_scope/build。
 * build 两步提交（§5.7 防线②）：commit=false 预览零写入 → 回传指纹 commit=true 才落 build_item。
 * 助手绝不建 build_job / 不调 review / 不调 publish；未知 intent 后端直接拒绝。
 */
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { RobotOutlined } from '@ant-design/icons-vue'
import { ontologyAssistant } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{
  ontologyId: number | null
  scopeContext?: Record<string, any>
}>()
const emit = defineEmits<{ (e: 'committed'): void }>()

const open = ref(false)
const intent = ref<'ask' | 'explain' | 'propose_scope' | 'build'>('ask')
const utterance = ref('')
const busy = ref(false)
const resultText = ref('')
const degraded = ref(false)

const ctxKind = ref('object')
const ctxCode = ref('')

const preview = ref<any[]>([])
const fingerprint = ref<string | null>(null)
const dropped = ref(0)

const placeholder = computed(() => ({
  ask: t2('这个本体里有什么 / 某对象映射到哪些表'),
  explain: t2('为何该元素只有此置信度？'),
  propose_scope: t2('把销售相关的表都建进来'),
  build: t2('把 sales_order 建成订单对象，关联到客户'),
}[intent.value]))

function resetOutcome() {
  resultText.value = ''
  degraded.value = false
}

function buildContext(extra: Record<string, any> = {}) {
  const ctx: Record<string, any> = { scope: props.scopeContext || {}, ...extra }
  if (intent.value === 'explain') {
    ctx.element_kind = ctxKind.value
    ctx.element_code = ctxCode.value
  }
  return ctx
}

async function run() {
  if (!props.ontologyId) return
  busy.value = true
  resetOutcome()
  try {
    const resp: any = await ontologyAssistant(props.ontologyId, {
      intent: intent.value, utterance: utterance.value, context: buildContext(), commit: false,
    })
    degraded.value = !!resp?.degraded
    if (intent.value === 'ask') {
      resultText.value = JSON.stringify(resp?.result ?? resp?.manifest ?? resp, null, 2).slice(0, 1500)
    } else if (intent.value === 'explain') {
      resultText.value = resp?.review_hint || t2('暂无 AI 提示')
    } else if (intent.value === 'propose_scope') {
      const tabs = (resp?.tables || []).map((t: any) => t.table).join(', ')
      dropped.value = resp?.hallucination_dropped || 0
      resultText.value = resp?.written
        ? `${t2('已写入作用域')}: ${tabs}`
        : `${t2('未写入')}${tabs ? `: ${tabs}` : ''}`
      if (resp?.written) emit('committed')
    }
  } finally {
    busy.value = false
  }
}

async function previewBuild() {
  if (!props.ontologyId) return
  busy.value = true
  resetOutcome()
  preview.value = []
  try {
    const resp: any = await ontologyAssistant(props.ontologyId, {
      intent: 'build', utterance: utterance.value, context: buildContext(), commit: false,
    })
    degraded.value = !!resp?.degraded
    preview.value = resp?.preview || []
    fingerprint.value = resp?.fingerprint ?? null
    dropped.value = resp?.hallucination_dropped || 0
    if (!preview.value.length) resultText.value = resp?.code === 'ASSISTANT_BUILD_EMPTY' ? t2('模型未产出可解析候选') : t2('无候选')
  } finally {
    busy.value = false
  }
}

async function commitBuild() {
  if (!props.ontologyId || !preview.value.length) return
  busy.value = true
  resetOutcome()
  try {
    const resp: any = await ontologyAssistant(props.ontologyId, {
      intent: 'build',
      utterance: utterance.value,
      context: buildContext({ candidates: preview.value, fingerprint: fingerprint.value }),
      commit: true,
    })
    resultText.value = `${t2('已提交')} ${resp?.committed ?? 0} ${t2('条，规则去重跳过')} ${resp?.skipped_duplicated_by_rule ?? 0} ${t2('条')}`
    message.success(t2('候选已落入审阅台（未采纳态）'))
    emit('committed')
    preview.value = []
    fingerprint.value = null
  } catch {
    /* 指纹不符 / 空候选 → 拦截器提示 ASSISTANT_BUILD_PREVIEW_STALE / ASSISTANT_BUILD_EMPTY */
  } finally {
    busy.value = false
  }
}
</script>

<style lang="less" scoped>
.ont-dock {
  &__fab {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 900;
    width: 48px;
    height: 48px;
  }
  &__panel {
    position: fixed;
    right: 24px;
    bottom: 84px;
    z-index: 900;
    width: 380px;
    max-height: 60vh;
    overflow: auto;
    background: var(--bg, #fff);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
    padding: 12px;
  }
  &__head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    margin-bottom: 4px;
  }
  &__body {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  &__ctx {
    margin-bottom: 4px;
  }
  &__preview {
    border: 1px dashed var(--border);
    border-radius: 6px;
    padding: 8px;
    max-height: 160px;
    overflow: auto;
  }
  &__preview-head {
    font-size: 12px;
    margin-bottom: 6px;
  }
  &__cand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    padding: 2px 0;
  }
  &__conf {
    margin-left: auto;
    color: var(--fg-mute, #999);
  }
  &__result,
  &__degraded {
    margin-top: 4px;
  }
  &__foot {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 8px;
  }
}
</style>
