<template>
  <div class="kg-build-config">
    <a-spin :spinning="loading">
      <a-form layout="vertical" class="kg-build-config__form">
        <a-divider orientation="left">{{ t('kbMgmt.kg.cfgExtractor') }}</a-divider>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgExtractorType')">
              <a-select v-model:value="form.extractor_type">
                <a-select-option value="llm">{{ t('kbMgmt.kg.cfgExtractorLlm') }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgConcurrency')">
              <a-input-number
                v-model:value="form.concurrency_count"
                :min="1" :max="1000" style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgTimeout')">
              <a-input-number
                v-model:value="form.timeout_seconds"
                :min="0" :max="600" style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">{{ t('kbMgmt.kg.cfgSchema') }}</a-divider>
        <a-form-item :label="t('kbMgmt.kg.cfgSchemaSource')">
          <a-radio-group v-model:value="form.schema_source">
            <a-radio value="none">{{ t('kbMgmt.kg.cfgSchemaNone') }}</a-radio>
            <a-radio value="cdm">{{ t('kbMgmt.kg.cfgSchemaCdm') }}</a-radio>
            <a-radio value="free_text">{{ t('kbMgmt.kg.cfgSchemaFree') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="form.schema_source === 'cdm'" :label="t('kbMgmt.kg.cfgCatalog')">
          <a-input-number
            v-model:value="form.catalog_id"
            :min="1" style="width: 220px"
            :placeholder="t('kbMgmt.kg.cfgCatalogPlaceholder')"
          />
          <div class="kg-build-config__tip">{{ t('kbMgmt.kg.cfgCatalogTip') }}</div>
        </a-form-item>
        <a-form-item v-if="form.schema_source === 'free_text'" :label="t('kbMgmt.kg.cfgSchemaText')">
          <a-textarea
            v-model:value="form.schema"
            :rows="4"
            :placeholder="t('kbMgmt.kg.cfgSchemaTextPlaceholder')"
          />
        </a-form-item>

        <a-divider orientation="left">{{ t('kbMgmt.kg.cfgRetrieval') }}</a-divider>
        <a-form-item>
          <a-space direction="vertical">
            <a-switch v-model:checked="form.use_graph_retrieval" />
            <span class="kg-build-config__tip">{{ t('kbMgmt.kg.cfgUseGraphTip') }}</span>
          </a-space>
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgEntityTopK')">
              <a-input-number v-model:value="form.graph_entity_top_k" :min="1" :max="200" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgTripleTopK')">
              <a-input-number v-model:value="form.graph_triple_top_k" :min="1" :max="200" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgGraphTopK')">
              <a-input-number v-model:value="form.graph_top_k" :min="1" :max="200" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgGraphWeight')">
              <a-input-number v-model:value="form.graph_weight" :min="0" :max="10" :step="0.1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgPprDamping')">
              <a-input-number v-model:value="form.ppr_damping" :min="0.1" :max="0.99" :step="0.01" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('kbMgmt.kg.cfgMaxNodes')">
              <a-input-number v-model:value="form.graph_max_nodes" :min="100" :max="100000" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-space>
          <a-button type="primary" :loading="saving" @click="onSave">
            {{ t('common.save') }}
          </a-button>
          <a-button @click="load">{{ t('common.refresh') }}</a-button>
        </a-space>
      </a-form>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgGraphConfig } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)

const form = reactive<KgGraphConfig>({
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

onMounted(load)
</script>

<style scoped>
.kg-build-config__tip {
  color: #999;
  font-size: 12px;
}
</style>
