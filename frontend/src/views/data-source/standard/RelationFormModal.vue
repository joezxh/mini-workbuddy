<template>
  <a-modal
    :open="open"
    :title="form.id ? t('kbMgmt.graph.editRelation') : t('kbMgmt.graph.createRelation')"
    :confirm-loading="saving"
    width="600px"
    destroy-on-close
    @ok="save"
    @cancel="close"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item label="code" required><a-input v-model:value="form.code" /></a-form-item>
      <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="form.name" /></a-form-item>
      <a-form-item :label="t('kbMgmt.graph.fromTo')" required>
        <div class="rel-form__pair">
          <a-select
            v-model:value="form.from_object_id"
            :options="objectOptions"
            :disabled="!!form.id"
            :placeholder="t('kbMgmt.graph.fromObject')"
          />
          <span>→</span>
          <a-select
            v-model:value="form.to_object_id"
            :options="objectOptions"
            :disabled="!!form.id"
            :placeholder="t('kbMgmt.graph.toObject')"
          />
        </div>
        <div v-if="form.id" class="rel-form__hint">{{ t('kbMgmt.graph.pairLocked') }}</div>
      </a-form-item>
      <a-form-item :label="t('kbMgmt.graph.relationType')" required>
        <a-select v-model:value="form.relation_type" :options="typeOptions" />
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
      <a-form-item :label="t('kbMgmt.catalog.description')">
        <a-textarea v-model:value="form.description" :rows="2" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
/**
 * 关系标准表单：两端对象 + 关系类型（1:1/1:N/N:1/N:N）。
 * 两端对象创建后不可改（后端 RelationUpdate 不接受 from/to），避免改写既有校验结论语义。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/dataops'

const props = defineProps<{
  open: boolean
  record: any | null
  objects: any[]
  catalogs: any[]
  defaultCatalogId?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved'): void
}>()

const { t } = useI18n()
const form = ref<any>({})
const saving = ref(false)
const catalogFieldNames = { title: 'name', value: 'id', children: 'children' }

const objectOptions = computed(() =>
  props.objects.map((o) => ({ value: o.id, label: `${o.name}（${o.code}）` })),
)
const typeOptions = computed(() =>
  ['1:1', '1:N', 'N:1', 'N:N'].map((v) => ({ value: v, label: v })),
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    form.value = props.record
      ? { ...props.record }
      : { catalog_id: props.defaultCatalogId ?? null, relation_type: 'N:1' }
  },
)

function close() {
  emit('update:open', false)
}

async function save() {
  const f = form.value
  if (!f.code || !f.name || !f.from_object_id || !f.to_object_id || !f.relation_type) {
    message.warning(t('kbMgmt.graph.requiredHint'))
    return
  }
  if (!f.id && f.from_object_id === f.to_object_id) {
    message.warning(t('kbMgmt.graph.sameObject'))
    return
  }
  saving.value = true
  try {
    if (f.id) {
      await api.updateRelation(f.id, {
        code: f.code,
        name: f.name,
        relation_type: f.relation_type,
        catalog_id: f.catalog_id ?? undefined,
        description: f.description || undefined,
      })
      message.success(t('kbMgmt.graph.saved'))
    } else {
      const r: any = await api.createRelation({
        code: f.code,
        name: f.name,
        from_object_id: f.from_object_id,
        to_object_id: f.to_object_id,
        relation_type: f.relation_type,
        catalog_id: f.catalog_id ?? undefined,
        description: f.description || undefined,
      })
      const data = r.data || r
      // 跨场景软提醒：不阻断创建
      if (data.warning) message.warning(data.warning)
      else message.success(t('kbMgmt.graph.saved'))
    }
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
.rel-form__pair {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rel-form__pair > :deep(*) {
  flex: 1;
}
.rel-form__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--fg-muted);
}
</style>
