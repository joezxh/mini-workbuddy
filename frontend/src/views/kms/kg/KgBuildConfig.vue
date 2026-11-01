<template>
  <div class="kg-build-config">
    <a-spin :spinning="loading">
      <!-- ① 抽取器 -->
      <section class="kg-card">
        <header class="kg-card__hd">{{ t('kbMgmt.kg.cfgExtractor') }}</header>
        <div class="kg-card__bd">
          <div class="kg-frm">
            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgExtractorType') }}</label>
            <div class="kg-frm__ctrl">
              <a-select v-model:value="form.extractor_type" size="small" class="kg-frm__inp">
                <a-select-option value="llm">{{ t('kbMgmt.kg.cfgExtractorLlm') }}</a-select-option>
              </a-select>
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgExtractorTip') }}</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgExtractorModel') }}</label>
            <div class="kg-frm__ctrl">
              <a-select
                v-model:value="modelId"
                size="small"
                show-search
                allow-clear
                option-filter-prop="label"
                :options="modelOptions"
                class="kg-frm__inp"
                :placeholder="t('kbMgmt.kg.cfgExtractorModel')"
              />
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgExtractorModelTip') }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ② Schema 约束 -->
      <section class="kg-card">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.cfgSchema') }}
          <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.cfgSchemaTip') }}</span>
        </header>
        <div class="kg-card__bd">
          <div class="kg-frm">
            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgSchemaSource') }}</label>
            <div class="kg-frm__ctrl">
              <a-radio-group v-model:value="form.schema_source" size="small">
                <a-radio value="none">{{ t('kbMgmt.kg.cfgSchemaNone') }}</a-radio>
                <a-radio value="cdm">{{ t('kbMgmt.kg.cfgSchemaCdm') }}</a-radio>
                <a-radio value="free_text">{{ t('kbMgmt.kg.cfgSchemaFree') }}</a-radio>
              </a-radio-group>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgCatalogSelect') }}</label>
            <div class="kg-frm__ctrl">
              <a-tree-select
                v-model:value="form.catalog_id"
                size="small"
                show-search
                allow-clear
                tree-node-filter-prop="name"
                :tree-data="catalogs"
                :field-names="{ children: 'children', label: 'name', value: 'id' }"
                class="kg-frm__inp"
                :disabled="form.schema_source !== 'cdm'"
                :placeholder="t('kbMgmt.kg.cfgCatalogPlaceholder')"
              />
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgCatalogCdmTip') }}</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgSchemaFreeLabel') }}</label>
            <div class="kg-frm__ctrl">
              <a-textarea
                v-model:value="form.schema"
                :rows="4"
                class="kg-frm__inp kg-frm__inp--area"
                :disabled="form.schema_source !== 'free_text'"
                :placeholder="t('kbMgmt.kg.cfgSchemaTextPlaceholder')"
              />
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgSchemaFreeTip') }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ③ 抽取参数 -->
      <section class="kg-card">
        <header class="kg-card__hd">{{ t('kbMgmt.kg.cfgExtractParams') }}</header>
        <div class="kg-card__bd">
          <div class="kg-frm">
            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgConcurrency') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.concurrency_count"
                :min="1"
                :max="1000"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgConcurrencyTip') }}</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgTimeout') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.timeout_seconds"
                :min="0"
                :max="600"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgTimeoutTip') }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ④ 检索参数：写入 pipeline_config.graph -->
      <section class="kg-card">
        <header class="kg-card__hd">
          {{ t('kbMgmt.kg.cfgRetrieval') }}
          <span class="kg-card__hd-sub">{{ t('kbMgmt.kg.cfgRetrievalTip') }}</span>
        </header>
        <div class="kg-card__bd">
          <div class="kg-frm">
            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgUseGraphRetrieval') }}</label>
            <div class="kg-frm__ctrl">
              <a-checkbox v-model:checked="form.use_graph_retrieval">
                {{ t('kbMgmt.kg.cfgUseGraphRetrieval') }}
              </a-checkbox>
              <div class="kg-frm__hint">{{ t('kbMgmt.kg.cfgUseGraphTip') }}</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgEntityTopK') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.graph_entity_top_k"
                :min="1"
                :max="200"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">graph_entity_top_k</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgTripleTopK') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.graph_triple_top_k"
                :min="1"
                :max="200"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">graph_triple_top_k</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgGraphTopK') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.graph_top_k"
                :min="1"
                :max="200"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">graph_top_k</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgMaxNodes') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.graph_max_nodes"
                :min="100"
                :max="100000"
                :step="1000"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">graph_max_nodes</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgGraphWeight') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.graph_weight"
                :min="0"
                :max="10"
                :step="0.1"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">graph_weight</div>
            </div>

            <label class="kg-frm__label">{{ t('kbMgmt.kg.cfgPprDamping') }}</label>
            <div class="kg-frm__ctrl">
              <a-input-number
                v-model:value="form.ppr_damping"
                :min="0.1"
                :max="0.99"
                :step="0.01"
                size="small"
                class="kg-frm__inp"
              />
              <div class="kg-frm__hint">ppr_damping ∈ [0.1, 0.99]</div>
            </div>
          </div>

          <div class="kg-build-config__ops">
            <a-button type="primary" size="small" :loading="saving" @click="onSave">
              {{ t('kbMgmt.kg.saveConfig') }}
            </a-button>
            <a-button size="small" @click="onRestoreDefault">
              {{ t('kbMgmt.kg.restoreDefault') }}
            </a-button>
          </div>
        </div>
      </section>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
/**
 * 图谱构建配置：抽取 / 类型约束 / 检索 / 融合 四张卡。
 *
 * 配置存于 kms_knowledge.pipeline_config.graph（与 clean/chunker/index 并列），
 * 「恢复默认」只重置表单，仍需保存才落库——避免误触即改线上检索行为。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgGraphConfig } from '@/api/kg'
import { getAvailableModels } from '@/api/ai-apikey'
import { listCatalogs } from '@/api/dataops'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const models = ref<{ id: number; name: string; model: string; platform: string }[]>([])
// CDM 目录：保留后端 list_tree 返回的原始嵌套树（每节点带 children），供 a-tree-select 直接消费
interface CatalogNode {
  id: number
  name: string
  children?: CatalogNode[]
}
const catalogs = ref<CatalogNode[]>([])

/** 与后端 kg_config.DEFAULTS 同源 */
const DEFAULTS: KgGraphConfig = {
  extractor_type: 'llm',
  model_spec: null,
  schema_source: 'free_text',
  catalog_id: null,
  schema: '',
  concurrency_count: 8,
  timeout_seconds: 60,
  use_graph_retrieval: true,
  graph_entity_top_k: 10,
  graph_triple_top_k: 10,
  graph_max_nodes: 10000,
  graph_top_k: 20,
  graph_weight: 1.0,
  ppr_damping: 0.85,
}

const form = reactive<KgGraphConfig>({ ...DEFAULTS })

const modelOptions = computed(() =>
  models.value.map((m) => ({ label: `${m.name} · ${m.model}`, value: m.id })),
)

/** 抽取模型：以 model_spec.model 反查模型 id（未命中则为空，不臆造） */
const modelId = computed<number | undefined>({
  get() {
    const spec = form.model_spec as { model?: string } | null
    if (!spec?.model) return undefined
    return models.value.find((m) => m.model === spec.model)?.id
  },
  set(id) {
    const hit = models.value.find((m) => m.id === id)
    form.model_spec = hit ? { provider: hit.platform, model: hit.model } : null
  },
})

async function load() {
  loading.value = true
  try {
    const cfg = await api.getGraphConfig(props.knowledgeId)
    Object.assign(form, cfg)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.loadFailed'))
  } finally {
    loading.value = false
  }
}

/** 模型 / 目录下拉：任一失败不阻塞配置编辑 */
async function loadOptions() {
  const [modelRes, catalogRes] = await Promise.allSettled([getAvailableModels(), listCatalogs()])
  if (modelRes.status === 'fulfilled') {
    const raw: any = modelRes.value
    models.value = Array.isArray(raw) ? raw : Array.isArray(raw?.data) ? raw.data : []
  }
  if (catalogRes.status === 'fulfilled') {
    const raw: any = catalogRes.value
    const list = Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : []
    // 保留完整 children 树：拍平会让 a-tree-select 只剩根级目录，子目录丢失
    catalogs.value = list
  }
}

async function onSave() {
  saving.value = true
  try {
    const cfg = await api.saveGraphConfig(props.knowledgeId, { ...form })
    Object.assign(form, cfg)
    message.success(t('common.success'))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.saveFailed'))
  } finally {
    saving.value = false
  }
}

function onRestoreDefault() {
  Object.assign(form, DEFAULTS)
  message.info(t('kbMgmt.kg.restoreDefault'))
}

onMounted(async () => {
  await Promise.all([load(), loadOptions()])
})
</script>

<style scoped>
.kg-build-config .kg-card + .kg-card {
  margin-top: 12px;
}
/* 原型 .frm：112px 右对齐标签 + 控件列 */
.kg-frm {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 11px 14px;
  align-items: start;
}
.kg-frm__label {
  padding-top: 6px;
  color: var(--kg-text-2);
  font-size: 12.5px;
  text-align: right;
}
.kg-frm__ctrl {
  min-width: 0;
}
.kg-build-config .kg-frm__ctrl .kg-frm__inp {
  width: 100%;
  max-width: 340px;
}
.kg-frm__inp--area {
  min-height: 74px;
  resize: vertical;
}
.kg-frm__hint {
  margin-top: 4px;
  color: var(--kg-text-3);
  font-size: 11.5px;
  line-height: 1.55;
}
.kg-build-config__ops {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}
</style>
