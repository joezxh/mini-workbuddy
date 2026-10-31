<template>
  <div class="kb-graph-pane">
    <!-- 面板头：知识库名 + 类型 + 副标题（库备注/统计） + 三态徽标 + 重建/对账/构建 -->
    <div class="kb-graph-pane__header">
      <div class="kb-graph-pane__heading">
        <h2 class="kb-graph-pane__title">
          <PartitionOutlined class="kb-graph-pane__icon" />
          <span class="kb-graph-pane__name">{{ knowledgeName || t('kbMgmt.typeGraph') }}</span>
          <a-tag color="purple">{{ t('kbMgmt.kg.typeLabel') }}</a-tag>
        </h2>
        <div class="kb-graph-pane__sub">{{ subtitle }}</div>
      </div>
      <div class="kb-graph-pane__ops">
        <span class="kg-badge" :class="badgeClass">
          <span v-if="status?.state === 'running'" class="kg-dot" />
          {{ badgeText }}
        </span>
        <a-button
          size="small"
          :loading="submitting === 'rebuild'"
          :disabled="!canBuild || submitting !== null"
          @click="onBuild('rebuild')"
        >
          {{ t('kbMgmt.kg.actionRebuild') }}
        </a-button>
        <a-button
          size="small"
          :loading="submitting === 'reconcile'"
          :disabled="!canBuild || submitting !== null"
          @click="onBuild('reconcile')"
        >
          {{ t('kbMgmt.kg.actionReconcile') }}
        </a-button>
        <a-button
          type="primary"
          size="small"
          :loading="submitting === 'build'"
          :disabled="!canBuild || submitting !== null"
          @click="onBuild('build')"
        >
          ▶ {{ t('kbMgmt.kg.actionBuild') }}
        </a-button>
      </div>
    </div>

    <!-- 降级告警：Neo4j 不可用时显式提示（降级但可见） -->
    <div v-if="degraded" class="kg-alert kg-alert--warn">
      {{ t('kbMgmt.kg.neo4jDegradedAlert') }}
    </div>

    <a-tabs v-model:activeKey="activeTab" class="kb-graph-pane__tabs">
      <a-tab-pane key="overview">
        <template #tab>{{ t('kbMgmt.kg.tabOverview') }}</template>
        <KgOverview :key="`ov-${reloadKey}`" :knowledge-id="knowledgeId" />
      </a-tab-pane>

      <a-tab-pane key="documents">
        <template #tab>
          {{ t('kbMgmt.kg.tabDoc') }}
          <span class="kg-tab-count">{{ overview.documents }}</span>
        </template>
        <KgDocumentList :key="`doc-${reloadKey}`" :knowledge-id="knowledgeId" />
      </a-tab-pane>

      <a-tab-pane key="graph">
        <template #tab>{{ t('kbMgmt.kg.tabGraph') }}</template>
        <!-- 未构建空态：无切片时图谱无从谈起，直接引导上传/配置 -->
        <div v-if="notBuilt" class="kg-empty">
          <div class="kg-empty__title">{{ t('kbMgmt.kg.graphNotBuilt') }}</div>
          <div class="kg-empty__desc">{{ t('kbMgmt.kg.graphNotBuiltDesc') }}</div>
          <div class="kg-empty__ops">
            <a-button type="primary" size="small" @click="activeTab = 'documents'">
              {{ t('kbMgmt.kg.uploadDoc') }}
            </a-button>
            <a-button size="small" @click="activeTab = 'config'">
              {{ t('kbMgmt.kg.goConfig') }}
            </a-button>
          </div>
        </div>
        <KgGraphView
          v-else
          ref="graphViewRef"
          :knowledge-id="knowledgeId"
          @provenance="onProvenance"
        />
      </a-tab-pane>

      <a-tab-pane key="entities">
        <template #tab>
          {{ t('kbMgmt.kg.tabEntity') }}
          <span class="kg-tab-count">{{ overview.entities }}</span>
        </template>
        <KgEntityTable
          :key="`ent-${reloadKey}`"
          :knowledge-id="knowledgeId"
          @inspect-entity="onInspectEntity"
          @provenance="onProvenance"
        />
      </a-tab-pane>

      <a-tab-pane key="relations">
        <template #tab>
          {{ t('kbMgmt.kg.tabRelation') }}
          <span class="kg-tab-count">{{ overview.relations }}</span>
        </template>
        <KgTripleTable
          :key="`rel-${reloadKey}`"
          :knowledge-id="knowledgeId"
          @inspect-entity="onInspectEntity"
          @inspect-edge="onInspectEdge"
          @provenance="onProvenance"
        />
      </a-tab-pane>

      <a-tab-pane key="provenance">
        <template #tab>{{ t('kbMgmt.kg.tabProvenance') }}</template>
        <KgProvenance :knowledge-id="knowledgeId" />
      </a-tab-pane>

      <a-tab-pane key="search">
        <template #tab>{{ t('kbMgmt.kg.tabSearchTest') }}</template>
        <KgSearchTester :knowledge-id="knowledgeId" />
      </a-tab-pane>

      <a-tab-pane key="config">
        <template #tab>{{ t('kbMgmt.kg.tabConfig') }}</template>
        <KgBuildConfig :knowledge-id="knowledgeId" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PartitionOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import KgOverview from './KgOverview.vue'
import KgEntityTable from './KgEntityTable.vue'
import KgTripleTable from './KgTripleTable.vue'
import KgBuildConfig from './KgBuildConfig.vue'
import KgGraphView from './KgGraphView.vue'
import KgProvenance from './KgProvenance.vue'
import KgSearchTester from './KgSearchTester.vue'
import KgDocumentList from './KgDocumentList.vue'
import * as api from '@/api/kg'
import * as kbApi from '@/api/kb'
import type { KgBuildAction, KgBuildStatus } from '@/api/kg'

const props = defineProps<{
  knowledgeId: number
  knowledgeName?: string
  /** 知识库备注：面板副标题首段（为空时不显示） */
  knowledgeDescription?: string
}>()

const { t } = useI18n()

/** 默认落在「图谱」页：原型中图谱是该库的主视图 */
const activeTab = ref('graph')
/** 当前提交中的构建动作（同时用于按钮 loading 与防重复提交） */
const submitting = ref<KgBuildAction | null>(null)
const graphViewRef = ref<InstanceType<typeof KgGraphView> | null>(null)
/** 递增以强制子组件重建（子组件 watch(immediate) 随之重载数据） */
const reloadKey = ref(0)
const status = ref<KgBuildStatus | null>(null)
/** 面板统计口径：文档数取自文档列表，实体/关系取自图谱统计 */
const overview = ref({ documents: 0, segments: 0, entities: 0, relations: 0 })
let pollTimer: ReturnType<typeof setInterval> | null = null

/** Neo4j 不可用：图通道降级（显式提示，不静默） */
const degraded = computed(() => status.value?.neo4j_available === false)
const notBuilt = computed(() => status.value?.state === 'not_built')

/** 三态徽标：构建中 / 已降级 / 就绪（未构建或待构建归入「就绪」前的默认态） */
const badgeClass = computed(() => {
  if (status.value?.state === 'running') return 'kg-badge--warn'
  if (degraded.value || status.value?.state === 'partial_failed') return 'kg-badge--err'
  if (status.value?.state === 'ready') return 'kg-badge--ok'
  return ''
})

const badgeText = computed(() => {
  const { entities, relations } = overview.value
  const counts = `${entities} ${t('kbMgmt.kg.badgeEntity')} / ${relations} ${t('kbMgmt.kg.badgeRelation')}`
  if (status.value?.state === 'running') return `${t('kbMgmt.kg.stateRunning')} · ${counts}`
  if (degraded.value) return t('kbMgmt.kg.badgeDegraded')
  if (status.value?.state === 'partial_failed') {
    return `${t('kbMgmt.kg.statePartialFailed')} · ${counts}`
  }
  if (status.value?.state === 'ready') return `${t('kbMgmt.kg.badgeReady')} · ${counts}`
  if (status.value?.state === 'pending') return `${t('kbMgmt.kg.statePending')} · ${counts}`
  return t('kbMgmt.kg.stateNotBuilt')
})

/** 副标题：库备注（可选） · 类型 · 形态 · 索引模式 · 共 N 个文档 / M 个切片 */
const subtitle = computed(() => {
  const parts: string[] = []
  if (props.knowledgeDescription) parts.push(props.knowledgeDescription)
  parts.push(t('kbMgmt.typeGraph'), t('kbMgmt.kg.formatGraph'), t('kbMgmt.kg.indexQuality'))
  const docs = t('kbMgmt.kg.paneSubDocs', { count: overview.value.documents })
  const segs = t('kbMgmt.kg.paneSubSegments', {
    count: status.value?.segments ?? overview.value.segments,
  })
  parts.push(`${docs} / ${segs}`)
  return parts.join(' · ')
})

/** Neo4j 不可用时禁止构建（否则图结构投影必失败，用户白等一次抽取） */
const canBuild = computed(() => status.value?.neo4j_available !== false)

async function loadStatus() {
  try {
    status.value = await api.getGraphBuildStatus(props.knowledgeId)
  } catch {
    status.value = null
  }
}

/** 副标题统计：文档数/切片数取自文档列表，实体/关系取自图谱统计（任一失败不阻塞） */
async function loadOverview() {
  const [statsRes, docsRes] = await Promise.allSettled([
    api.getGraphStats(props.knowledgeId),
    kbApi.listDocuments(props.knowledgeId),
  ])

  if (statsRes.status === 'fulfilled' && statsRes.value) {
    overview.value.entities = Number((statsRes.value as any).entities) || 0
    overview.value.relations = Number((statsRes.value as any).relations) || 0
  }

  if (docsRes.status === 'fulfilled') {
    const raw: any = docsRes.value
    const docs: any[] = Array.isArray(raw) ? raw : Array.isArray(raw?.data) ? raw.data : []
    overview.value.documents = docs.length
    overview.value.segments = docs.reduce(
      (sum, d) => sum + (Number(d?.segment_count) || 0),
      0,
    )
  }
}

/** 记录列表与统计同时重载（构建/对账结束后调用） */
async function reloadAll() {
  await Promise.all([loadStatus(), loadOverview()])
}

/** 轮询：仅在构建中轮询，终态即停（R17：定时器必须随组件卸载清理） */
function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    await loadStatus()
    if (status.value && status.value.state !== 'running') {
      stopPolling()
      // 终态：实体/关系与文档切片统计已变化，同步刷新统计
      await loadOverview()
      reloadKey.value += 1
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function onBuild(action: KgBuildAction) {
  submitting.value = action
  try {
    await api.submitGraphBuild(props.knowledgeId, action)
    message.success(
      action === 'reconcile'
        ? t('kbMgmt.kg.reconcileSubmitted')
        : t('kbMgmt.kg.buildSubmitted'),
    )
    await reloadAll()
    startPolling()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    submitting.value = null
  }
}

/** 表格里的「检视」：切到图谱 Tab 并在画布与检视面板中选中该实体 */
async function onInspectEntity(entityId: number) {
  activeTab.value = 'graph'
  await nextTick()
  await graphViewRef.value?.selectEntity(entityId)
}

/** 关系表的「检视」：切到图谱 Tab 并在检视面板中选中该关系 */
async function onInspectEdge(relationId: number) {
  activeTab.value = 'graph'
  await nextTick()
  await graphViewRef.value?.selectEdge(relationId)
}

/** 跳到溯源 Tab（实体 id 由溯源页自行加载） */
function onProvenance(_entityId: number) {
  activeTab.value = 'provenance'
}

watch(
  () => props.knowledgeId,
  async () => {
    await reloadAll()
    if (status.value?.state === 'running') startPolling()
  },
  { immediate: true },
)

onUnmounted(stopPolling)
</script>

<style scoped>
.kb-graph-pane__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.kb-graph-pane__heading {
  min-width: 0;
}
.kb-graph-pane__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--kg-text);
  font-size: 15px;
  font-weight: 600;
}
.kb-graph-pane__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-graph-pane__sub {
  margin-top: 2px;
  color: var(--kg-text-3);
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-graph-pane__icon {
  color: #722ed1;
}
.kb-graph-pane__ops {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.kb-graph-pane__tabs {
  background: transparent;
}

/* 未构建空态 */
.kg-empty {
  padding: 56px 20px;
  border: 1px dashed var(--kg-border);
  border-radius: var(--kg-r);
  background: var(--kg-subtle);
  text-align: center;
}
.kg-empty__title {
  color: var(--kg-text);
  font-size: 14px;
  font-weight: 600;
}
.kg-empty__desc {
  margin-top: 6px;
  color: var(--kg-text-3);
  font-size: 12px;
}
.kg-empty__ops {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 14px;
}
</style>

<!-- 作用域皮肤：图谱工作台共用（标准中心亦引入），仅在 .kb-graph-pane 内生效，不污染全局 antd -->
<style src="@/components/common/graph/graph-tokens.css"></style>
