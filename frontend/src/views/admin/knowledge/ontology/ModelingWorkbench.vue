<template>
  <div class="onto-model">
    <div class="onto-model__bar">
      <a-select v-model:value="ontoId" :placeholder="t('kbMgmt.model.selectOntology')" style="width: 240px">
        <a-select-option v-for="o in ontos" :key="o.id" :value="o.id">{{ o.name }}</a-select-option>
      </a-select>
    </div>
    <a-tabs v-model:activeKey="sub">
      <a-tab-pane key="obj" :tab="t('kbMgmt.model.objTab')">
        <a-button type="primary" size="small" @click="addObj"><PlusOutlined /> {{ t('kbMgmt.model.add') }}</a-button>
        <a-list :data-source="objTypes" :locale="{ emptyText: t('kbMgmt.common.empty') }" style="margin-top:8px">
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta :title="item.name" :description="item.description" />
              <template #actions v-if="item.source === 'rule'"><a-tag color="blue">{{ t('kbMgmt.model.suggested') }}</a-tag></template>
            </a-list-item>
          </template>
        </a-list>
      </a-tab-pane>
      <a-tab-pane key="prop" :tab="t('kbMgmt.model.propTab')">
        <a-empty :description="t('kbMgmt.model.propPending')" />
      </a-tab-pane>
      <a-tab-pane key="rel" :tab="t('kbMgmt.model.relTab')">
        <a-list :data-source="relations" :locale="{ emptyText: t('kbMgmt.common.empty') }" style="margin-top:8px">
          <template #renderItem="{ item }">
            <a-list-item>{{ item.source_type }} → {{ item.target_type }} <a-tag v-if="item.overlap_ratio != null" color="purple">overlap {{ item.overlap_ratio }}</a-tag></a-list-item>
          </template>
        </a-list>
      </a-tab-pane>
      <a-tab-pane key="cq" :tab="t('kbMgmt.model.cqTab')">
        <a-list :data-source="cqs" :locale="{ emptyText: t('kbMgmt.common.empty') }" style="margin-top:8px">
          <template #renderItem="{ item }">
            <a-list-item>{{ item.question }} <a-tag>{{ item.object_type }}</a-tag></a-list-item>
          </template>
        </a-list>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/ontology'

const { t } = useI18n()
const ontos = ref<any[]>([])
const ontoId = ref<number>()
const sub = ref('obj')
const objTypes = ref<any[]>([])
const relations = ref<any[]>([])
const cqs = ref<any[]>([])

async function loadOntos() {
  try {
    const r: any = await api.listOntologies()
    ontos.value = r.data || r || []
  } catch { /* ignore */ }
}
async function refresh() {
  if (!ontoId.value) return
  try {
    const [o, rel, cq] = await Promise.all([
      api.listObjectTypes(ontoId.value),
      api.listRelations(ontoId.value),
      api.listCqs(ontoId.value),
    ])
    objTypes.value = o.data || o || []
    relations.value = rel.data || rel || []
    cqs.value = cq.data || cq || []
  } catch {
    message.warning(t('kbMgmt.model.routerMissing'))
  }
}
async function addObj() {
  if (!ontoId.value) return
  const name = window.prompt(t('kbMgmt.model.objNamePrompt'))
  if (!name) return
  try {
    await api.createObjectType(ontoId.value, { name })
    message.success(t('kbMgmt.model.added'))
    refresh()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.model.addFailed'))
  }
}
watch(ontoId, refresh)
onMounted(loadOntos)
</script>

<style scoped>
.onto-model__bar { margin-bottom: 8px; }
</style>
