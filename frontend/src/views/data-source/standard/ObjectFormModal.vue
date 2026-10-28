<template>
  <a-modal
    :open="open"
    :title="form.id ? t('kbMgmt.catalog.editObject') : t('kbMgmt.catalog.createObject')"
    :confirm-loading="saving"
    width="640px"
    destroy-on-close
    @ok="save"
    @cancel="close"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item label="code" required><a-input v-model:value="form.code" /></a-form-item>
      <a-form-item :label="t('kbMgmt.common.name')" required>
        <a-input v-model:value="form.name" />
      </a-form-item>
      <a-form-item :label="t('kbMgmt.catalog.parent')">
        <a-tree-select
          v-model:value="form.catalog_id"
          :tree-data="catalogs"
          :field-names="catalogFieldNames"
          :placeholder="t('kbMgmt.catalog.parent')"
          tree-default-expand-all
          allow-clear
        />
      </a-form-item>
      <a-form-item :label="t('kbMgmt.meta.domain')">
        <a-input v-model:value="form.domain" />
      </a-form-item>
      <a-form-item :label="t('kbMgmt.std.aliases')">
        <a-input v-model:value="aliasesText" :placeholder="t('kbMgmt.catalog.aliasesHint')" />
      </a-form-item>
      <a-form-item :label="t('kbMgmt.catalog.attributes')">
        <a-select
          v-model:value="attrIds"
          mode="multiple"
          :options="attrOptions"
          :placeholder="t('kbMgmt.catalog.attributesHint')"
          option-filter-prop="label"
          show-search
          allow-clear
        />
        <a-checkbox-group
          v-if="attrIds.length"
          v-model:value="requiredIds"
          class="obj-form__required"
          :options="requiredOptions"
        />
      </a-form-item>
      <a-form-item :label="t('kbMgmt.catalog.description')">
        <a-textarea v-model:value="form.description" :rows="2" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
/**
 * 对象标准表单：基本信息 + 引用全局属性标准（多选，全量替换）。
 * 编辑时先 `getObject()` 拉已有属性，保存时 `setObjectAttributes()` 覆盖写入。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/dataops'

const props = defineProps<{
  open: boolean
  record: any | null
  catalogs: any[]
  standards: any[]
  defaultCatalogId?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved'): void
}>()

const { t } = useI18n()
const form = ref<any>({})
const aliasesText = ref('')
const attrIds = ref<number[]>([])
const requiredIds = ref<number[]>([])
const saving = ref(false)

const catalogFieldNames = { title: 'name', value: 'id', children: 'children' }

const attrOptions = computed(() =>
  props.standards.map((s) => ({ value: s.id, label: `${s.name}（${s.code}）` })),
)
const requiredOptions = computed(() =>
  attrIds.value.map((id) => ({
    value: id,
    label: props.standards.find((s) => s.id === id)?.code || String(id),
  })),
)

/** 打开时初始化：编辑走详情接口拿 attributes，新增用当前选中目录做默认归属 */
watch(
  () => props.open,
  async (open) => {
    if (!open) return
    const row = props.record
    form.value = row
      ? { ...row }
      : { catalog_id: props.defaultCatalogId ?? null }
    aliasesText.value = (row?.aliases || []).join(',')
    attrIds.value = []
    requiredIds.value = []
    if (row?.id) {
      try {
        const r: any = await api.getObject(row.id)
        const detail = r.data || r
        const attrs = detail.attributes || []
        attrIds.value = attrs.map((a: any) => a.standard_id)
        requiredIds.value = attrs.filter((a: any) => a.required).map((a: any) => a.standard_id)
      } catch {
        message.error(t('kbMgmt.catalog.loadFailed'))
      }
    }
  },
)

function close() {
  emit('update:open', false)
}

async function save() {
  if (!form.value.code || !form.value.name) {
    message.warning(t('kbMgmt.catalog.requiredHint'))
    return
  }
  saving.value = true
  try {
    const payload = {
      code: form.value.code,
      name: form.value.name,
      catalog_id: form.value.catalog_id ?? undefined,
      domain: form.value.domain || undefined,
      description: form.value.description || undefined,
      aliases: aliasesText.value.split(',').map((s) => s.trim()).filter(Boolean),
    }
    let objectId = form.value.id
    if (objectId) await api.updateObject(objectId, payload)
    else {
      const r: any = await api.createObject(payload)
      objectId = (r.data || r).id
    }
    await api.setObjectAttributes(
      objectId,
      attrIds.value.map((standardId, index) => ({
        standard_id: standardId,
        required: requiredIds.value.includes(standardId),
        sort_order: index,
      })),
    )
    message.success(t('kbMgmt.catalog.objectSaved'))
    emit('saved')
    close()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.catalog.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.obj-form__required {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 8px;
}
</style>
