<template>
  <div class="kb-manager">
    <a-tabs v-model:activeKey="activeType">
      <a-tab-pane key="1" :tab="t('kmsWiki.title')" />
      <a-tab-pane key="2" :tab="t('kbMgmt.generalKb')" />
      <a-tab-pane key="3" :tab="t('kbMgmt.externalKb')" />
    </a-tabs>

    <a-row v-if="activeType !== '1'" :gutter="16">
      <a-col :span="6">
        <a-card :title="t('wikiMgmt.tabCategory')" size="small">
          <a-spin v-if="loading" />
          <a-empty v-else-if="!treeData.length" />
          <a-tree
            v-else
            :tree-data="treeData"
            @select="onSelectKnowledge"
          />
        </a-card>
      </a-col>
      <a-col :span="18">
        <KbDocumentPane v-if="activeType === '2' && selectedId" :knowledge-id="selectedId" />
        <a-empty v-else-if="activeType === '2'" :description="t('kbMgmt.selectKbFirst')" />
        <ExternalLinkPane v-else />
      </a-col>
    </a-row>
    <div v-else class="kb-manager__wiki-hint">
      <router-link to="/wiki">{{ t('kmsWiki.openWiki') }}</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listKnowledges } from '@/api/wiki'
import KbDocumentPane from './kb/KbDocumentPane.vue'
import ExternalLinkPane from './kb/ExternalLinkPane.vue'

const { t } = useI18n()
const activeType = ref('2')
const loading = ref(false)
const knowledges = ref<any[]>([])
const selectedId = ref<number | null>(null)

const treeData = ref<any[]>([])

function rebuildTree() {
  treeData.value = knowledges.value
    .filter((k) => String(k.type) === activeType.value)
    .map((k) => ({ key: String(k.id), title: k.name, isLeaf: true }))
}

function onSelectKnowledge(_keys: unknown, info: any) {
  selectedId.value = Number(info.node.key)
}

async function load() {
  loading.value = true
  try {
    const res: any = await listKnowledges()
    knowledges.value = res.items || res || []
    rebuildTree()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kb-manager {
  padding: 8px 0;
}
.kb-manager__wiki-hint {
  padding: 48px;
  text-align: center;
}
</style>
