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
        <!-- 主流程：属性就在对象里新建，免得先去字典页签建完再回来选 -->
        <div v-if="attrCreateOpen" class="obj-form__attr-create">
          <a-input v-model:value="attrDraft.code" placeholder="code" size="small" style="width: 120px" />
          <a-input v-model:value="attrDraft.name" :placeholder="t('kbMgmt.common.name')" size="small" style="width: 140px" />
          <a-input
            v-model:value="attrDraft.semantic_type"
            :placeholder="t('kbMgmt.std.semanticType')"
            size="small"
            style="width: 120px"
          />
          <a-button type="primary" size="small" :loading="attrSaving" @click="saveAttribute">
            {{ t('kbMgmt.common.create') }}
          </a-button>
          <a-button size="small" @click="attrCreateOpen = false">{{ t('kbMgmt.common.cancel') }}</a-button>
        </div>
        <a v-else class="obj-form__attr-new" @click="attrCreateOpen = true">
          + {{ t('kbMgmt.catalog.newAttribute') }}
        </a>
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
 * 属性可就地新建（自动勾选），避免「先去字典页签建属性再回来选」的断头动线。
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
  (e: 'attribute-created', std: any): void
}>()

const { t } = useI18n()
const form = ref<any>({})
const aliasesText = ref('')
const attrIds = ref<number[]>([])
const requiredIds = ref<number[]>([])
const saving = ref(false)
const attrCreateOpen = ref(false)
const attrSaving = ref(false)
const attrDraft = ref({ code: '', name: '', semantic_type: '' })
/** 本次会话内新建的属性：父级刷新 standards 前先用它补齐下拉 label */
const localStandards = ref<any[]>([])

// a-tree-select 用 label 取节点文案（a-tree 才是 title/key）
const catalogFieldNames = { label: 'name', value: 'id', children: 'children' }

const attrOptions = computed(() => {
  const seen = new Map<number, string>()
  for (const s of [...props.standards, ...localStandards.value]) {
    if (!seen.has(s.id)) seen.set(s.id, `${s.name}（${s.code}）`)
  }
  return [...seen].map(([value, label]) => ({ value, label }))
})
const requiredOptions = computed(() =>
  attrIds.value.map((id) => ({
    value: id,
    label:
      [...props.standards, ...localStandards.value].find((s) => s.id === id)?.code || String(id),
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
    attrCreateOpen.value = false
    attrDraft.value = { code: '', name: '', semantic_type: '' }
    localStandards.value = []
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

/** 就地新建属性标准并自动勾选；创建失败不关面板也不丢输入 */
async function saveAttribute() {
  const code = attrDraft.value.code.trim()
  const name = attrDraft.value.name.trim()
  if (!code || !name) {
    message.warning(t('kbMgmt.catalog.requiredHint'))
    return
  }
  attrSaving.value = true
  try {
    const r: any = await api.createStandard({
      code,
      name,
      semantic_type: attrDraft.value.semantic_type || undefined,
    })
    const created: any = r.data || r
    localStandards.value.push(created)
    if (!attrIds.value.includes(created.id)) attrIds.value = [...attrIds.value, created.id]
    attrDraft.value = { code: '', name: '', semantic_type: '' }
    attrCreateOpen.value = false
    message.success(t('kbMgmt.catalog.attrCreated'))
    // 父级刷新字典池（含引用计数）；新建项已在本次表单内勾选，保存对象即建立引用
    emit('attribute-created', created)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.catalog.saveFailed'))
  } finally {
    attrSaving.value = false
  }
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
.obj-form__attr-new {
  display: inline-block;
  margin-top: 6px;
  font-size: 12px;
}
.obj-form__attr-create {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  padding: 8px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
}
</style>
