<template>
  <div class="ont-workspace">
    <!-- 顶部：本体选择器 + 新建 + 状态 -->
    <div class="ont-workspace__bar">
      <a-space>
        <a-select
          v-model:value="filterDomainId"
          style="width: 160px"
          :placeholder="t2('全部领域')"
          :options="domainOptions"
          allow-clear
          @change="onDomainFilter"
        />
        <a-select
          v-model:value="currentId"
          style="min-width: 260px"
          :loading="loadingList"
          :placeholder="t2('选择本体')"
          show-search
          option-filter-prop="label"
          @change="onSwitch"
        >
          <a-select-option v-for="o in ontologies" :key="o.id" :value="o.id" :label="`${o.name} (${o.code})`">
            <span>{{ o.name }}</span>
            <span v-if="o.domain_name" class="ont-workspace__domain">{{ o.domain_name }}</span>
            <a-tag :color="statusColor(o.status)" style="margin-left: 8px">{{ o.status }}</a-tag>
            <span class="ont-workspace__ver">v{{ o.current_version }}</span>
          </a-select-option>
        </a-select>
        <a-button v-if="current" @click="openEdit">{{ t2('编辑') }}</a-button>
        <a-button type="primary" @click="openCreate">{{ t2('新建本体') }}</a-button>
      </a-space>
    </div>

    <!-- 五步链路拓扑（只读步骤条，AF-10） -->
    <OntPipelineBar v-if="currentId" ref="pipelineRef" :ontology-id="currentId" />

    <a-empty v-if="!currentId" :description="t2('请选择或新建一个本体开始建模')" class="ont-workspace__empty" />

    <template v-else>
      <a-tabs v-model:activeKey="tab" class="ont-workspace__tabs">
        <a-tab-pane key="overview" :tab="t2('总览')">
          <OntOverview :ontology="current" @refresh="reloadAll" />
        </a-tab-pane>
        <a-tab-pane key="build" :tab="t2('构建')">
          <OntBuildPanel :ontology-id="currentId" @built="reloadAll" />
        </a-tab-pane>
        <a-tab-pane key="review" :tab="t2('审阅台')">
          <OntReviewQueue :ontology-id="currentId" @reviewed="reloadAll" />
        </a-tab-pane>
        <a-tab-pane key="graph" :tab="t2('图谱')">
          <OntGraphView :ontology-id="currentId" @node-click="onNodeClick" />
        </a-tab-pane>
        <a-tab-pane key="inspector" :tab="t2('检视')">
          <OntInspector ref="inspectorRef" :ontology-id="currentId" :focus="inspectorFocus" @adopted="reloadAll" />
        </a-tab-pane>
        <a-tab-pane key="version" :tab="t2('版本')">
          <OntVersionPanel :ontology-id="currentId" @published="reloadAll" />
        </a-tab-pane>
        <a-tab-pane key="publish" :tab="t2('应用发布')">
          <OntPublishPanel :ontology-id="currentId" />
        </a-tab-pane>
      </a-tabs>

      <!-- 右下角常驻建模助手（四档，AF-16） -->
      <OntAssistantDock :ontology-id="currentId" :scope-context="assistantScope" @committed="reloadAll" />
    </template>

    <!-- 新建本体弹窗 -->
    <a-modal v-model:open="createOpen" :title="t2(editingId ? '编辑本体' : '新建本体')" :confirm-loading="creating" @ok="doCreate">
      <a-form layout="vertical">
        <a-form-item :label="t2('编码 code')" required>
          <a-input v-model:value="createForm.code" :placeholder="t2('租户内唯一，如 sales_ontology')" />
        </a-form-item>
        <a-form-item :label="t2('名称')" required>
          <a-input v-model:value="createForm.name" />
        </a-form-item>
        <a-form-item :label="t2('描述')">
          <a-textarea v-model:value="createForm.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t2('所属领域')">
          <a-select
            v-model:value="createForm.domain_id"
            style="width: 100%"
            :placeholder="t2('未分类')"
            :options="domainOptions"
            allow-clear
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 本体工作台容器（OntoFlow 第 6 页签）：本体选择 + 7 子视图 + 助手 Dock + 链路拓扑。
 * 单一 `ontologyId` 状态下发，各子视图自持数据请求（api/dataops 本体段）。
 * P0 外壳：文案以中文直显（与后端中文域一致），错误提示交由 request 拦截器 code→文案统一处理。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  listOntologies, createOntology, updateOntology, listDomains,
} from '@/api/dataops'
import { t2 } from './ontologyText'
import OntPipelineBar from './OntPipelineBar.vue'
import OntOverview from './OntOverview.vue'
import OntBuildPanel from './OntBuildPanel.vue'
import OntReviewQueue from './OntReviewQueue.vue'
import OntGraphView from './OntGraphView.vue'
import OntInspector from './OntInspector.vue'
import OntVersionPanel from './OntVersionPanel.vue'
import OntPublishPanel from './OntPublishPanel.vue'
import OntAssistantDock from './OntAssistantDock.vue'

const ontologies = ref<any[]>([])
const currentId = ref<number | null>(null)
const loadingList = ref(false)
const creating = ref(false)
const createOpen = ref(false)
const createForm = reactive<{ code: string; name: string; description: string; domain_id: number | null }>({
  code: '', name: '', description: '', domain_id: null,
})
const editingId = ref<number | null>(null)
const domains = ref<any[]>([])
const filterDomainId = ref<number | null>(null)
const domainOptions = computed(() => [
  { label: t2('未分类'), value: null },
  ...domains.value.map((d) => ({ label: d.name, value: d.id })),
])
const tab = ref('overview')
const pipelineRef = ref<any>(null)
const inspectorRef = ref<any>(null)
const inspectorFocus = ref<{ kind: string; code: string } | null>(null)

const current = computed(() => ontologies.value.find((o) => o.id === currentId.value) || null)

/** 助手上下文：把当前作用域（草稿表集合）透出，供 propose_scope/build 参考 */
const assistantScope = computed(() => current.value?.draft_scope_json || {})

function statusColor(s: string) {
  return ({ published: 'green', draft: 'blue', archived: 'default', stopped: 'orange' } as Record<string, string>)[s] || 'default'
}

async function loadList(selectFirst = false) {
  loadingList.value = true
  try {
    const resp: any = await listOntologies({
      sort: 'updated_at_desc',
      domain_id: filterDomainId.value ?? undefined,
    })
    ontologies.value = Array.isArray(resp) ? resp : (resp?.items || [])
    if (selectFirst && !currentId.value && ontologies.value.length) {
      currentId.value = ontologies.value[0].id
    }
  } finally {
    loadingList.value = false
  }
}

function onSwitch() {
  tab.value = 'overview'
  refreshPipeline()
}

async function onDomainFilter() {
  currentId.value = null
  await loadList()
}

async function loadDomains() {
  try {
    const resp: any = await listDomains({ status: 'active' })
    domains.value = Array.isArray(resp) ? resp : (resp?.items || [])
  } catch {
    domains.value = []
  }
}

function refreshPipeline() {
  pipelineRef.value?.reload?.()
}

async function reloadAll() {
  await loadList()
  refreshPipeline()
}

function openCreate() {
  editingId.value = null
  createForm.code = ''
  createForm.name = ''
  createForm.description = ''
  createForm.domain_id = null
  createOpen.value = true
}

function openEdit() {
  if (!current.value) return
  editingId.value = current.value.id
  createForm.code = current.value.code || ''
  createForm.name = current.value.name || ''
  createForm.description = current.value.description || ''
  createForm.domain_id = current.value.domain_id ?? null
  createOpen.value = true
}

async function doCreate() {
  if (!createForm.code || !createForm.name) {
    message.warning(t2('code 与名称必填'))
    return
  }
  creating.value = true
  try {
    const payload = { ...createForm, domain_id: createForm.domain_id ?? null }
    const obj: any = editingId.value
      ? await updateOntology(editingId.value, payload)
      : await createOntology(payload)
    message.success(t2(editingId.value ? '本体已更新' : '本体已创建'))
    createOpen.value = false
    await loadList()
    currentId.value = obj.id
  } finally {
    creating.value = false
  }
}

/** 图谱节点点击 → 跳检视页签并定位 */
function onNodeClick(payload: { kind: string; code: string }) {
  inspectorFocus.value = { ...payload }
  tab.value = 'inspector'
}

onMounted(async () => {
  await loadDomains()
  await loadList(true)
})
</script>

<style lang="less" scoped>
.ont-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;

  &__bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
  &__domain {
    margin-left: 8px;
    color: var(--primary-color, #1677ff);
    font-size: 12px;
  }
  &__ver {
    margin-left: 8px;
    color: var(--fg-mute, #999);
    font-size: 12px;
  }
  &__empty {
    margin-top: 80px;
  }
  &__tabs {
    flex: 1;
    min-height: 0;
    :deep(.ant-tabs-content) {
      height: 100%;
    }
  }
}
</style>
