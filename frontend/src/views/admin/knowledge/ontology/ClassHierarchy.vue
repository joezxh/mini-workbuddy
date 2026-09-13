<template>
  <div class="onto-class">
    <div class="onto-class__bar">
      <a-select v-model:value="ontoId" :placeholder="t('kbMgmt.model.selectOntology')" style="width: 240px" @change="loadClasses">
        <a-select-option v-for="o in ontos" :key="o.id" :value="o.id">{{ o.name }}</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!ontoId" @click="addClass"><PlusOutlined /> {{ t('kbMgmt.cls.addClass') }}</a-button>
      <a-button :disabled="!ontoId" @click="validate">{{ t('kbMgmt.cls.validate') }}</a-button>
    </div>

    <a-alert v-if="validateMsg" :type="validateType" show-icon style="margin: 8px 0">{{ validateMsg }}</a-alert>

    <a-tree
      v-if="tree.length"
      :tree-data="tree"
      :field-names="{ title: 'title', key: 'key', children: 'children' }"
      default-expand-all
    >
      <template #title="{ data }">
        <span>{{ data.title }}</span>
        <a-button size="small" type="text" danger @click.stop="del(data)">{{ t('kbMgmt.common.delete') }}</a-button>
      </template>
    </a-tree>
    <a-empty v-else :description="t('kbMgmt.common.empty')" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/ontology'

const { t } = useI18n()
const ontos = ref<any[]>([])
const ontoId = ref<number>()
const classes = ref<any[]>([])
const tree = ref<any[]>([])
const validateMsg = ref('')
const validateType = ref<any>('info')

async function loadOntos() {
  try {
    const r: any = await api.listOntologies()
    ontos.value = r.data || r || []
  } catch { /* ignore */ }
}
async function loadClasses() {
  if (!ontoId.value) return
  try {
    const r: any = await api.listClasses(ontoId.value)
    classes.value = r.data || r || []
    tree.value = buildTree(classes.value)
  } catch (e: any) {
    message.warning(t('kbMgmt.cls.routerMissing'))
  }
}
function buildTree(items: any[]): any[] {
  const map = new Map<number, any>()
  items.forEach((c) => map.set(c.id, { key: c.id, title: c.label || c.name, children: [] }))
  const roots: any[] = []
  items.forEach((c) => {
    const node = map.get(c.id)!
    if (c.parent_id && map.has(c.parent_id)) map.get(c.parent_id)!.children.push(node)
    else roots.push(node)
  })
  return roots
}
async function addClass() {
  if (!ontoId.value) return
  const name = window.prompt(t('kbMgmt.cls.namePrompt'))
  if (!name) return
  try {
    await api.createClass(ontoId.value, { name })
    message.success(t('kbMgmt.cls.added'))
    loadClasses()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.cls.addFailed'))
  }
}
async function del(node: any) {
  if (!ontoId.value) return
  try {
    await api.deleteClass(ontoId.value, node.key)
    message.success(t('kbMgmt.common.deleted'))
    loadClasses()
  } catch {
    message.error(t('kbMgmt.cls.deleteFailed'))
  }
}
function validate() {
  validateType.value = 'success'
  validateMsg.value = classes.value.length ? t('kbMgmt.cls.validateOk', { count: classes.value.length }) : t('kbMgmt.cls.noClasses')
}
onMounted(loadOntos)
</script>

<style scoped>
.onto-class__bar { display: flex; gap: 8px; margin-bottom: 8px; }
</style>
