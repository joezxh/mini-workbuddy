<template>
  <div class="asset-search">
    <a-input-search
      v-model:value="kw"
      :placeholder="t2('搜索表名 / 字段名 / 注释')"
      style="width: 280px"
      allow-clear
      @search="emitSearch"
      @press-enter="emitSearch"
    />
    <a-select
      v-model:value="tagIds"
      mode="multiple"
      :placeholder="t2('按标签筛选')"
      style="min-width: 200px; max-width: 320px"
      :loading="loadingTags"
      :options="tagOptions"
      allow-clear
      @change="emitSearch"
    />
    <a-select v-model:value="kind" style="width: 120px" @change="emitSearch">
      <a-select-option value="table">{{ t2('表') }}</a-select-option>
      <a-select-option value="column">{{ t2('字段') }}</a-select-option>
    </a-select>
    <a-button type="primary" :loading="loading" @click="emitSearch">{{ t2('查询') }}</a-button>
    <a-button @click="onReset">{{ t2('重置') }}</a-button>
    <a-button type="link" @click="openCreateTag">{{ t2('新建标签') }}</a-button>

    <a-modal v-model:open="tagOpen" :title="t2('新建标签')" :confirm-loading="creating" @ok="doCreateTag">
      <a-form layout="vertical">
        <a-form-item :label="t2('编码 code')" required>
          <a-input v-model:value="tagForm.code" :placeholder="t2('租户内唯一')" />
        </a-form-item>
        <a-form-item :label="t2('名称')" required>
          <a-input v-model:value="tagForm.name" />
        </a-form-item>
        <a-form-item :label="t2('颜色')">
          <a-input v-model:value="tagForm.color" placeholder="#3371fc" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产检索条（AF-02/03）：全文检索 + 重置 + 标签多选筛选 + 新建标签。
 * 通过 emit `search` 把 {kw, tag_ids, kind} 交给父级驱动 E28 请求。
 */
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { createAssetTag, listAssetTags } from '@/api/dataops'
import { t2 } from '../ontology/ontologyText'

const emit = defineEmits<{
  (e: 'search', payload: { kw: string; tag_ids: number[]; kind: string }): void
}>()

defineProps<{ loading?: boolean }>()

const kw = ref('')
const kind = ref('table')
const tagIds = ref<number[]>([])
const tagOptions = ref<{ label: string; value: number }[]>([])
const loadingTags = ref(false)

const tagOpen = ref(false)
const creating = ref(false)
const tagForm = reactive({ code: '', name: '', color: '#3371fc' })

function emitSearch() {
  emit('search', { kw: kw.value.trim(), tag_ids: tagIds.value, kind: kind.value })
}

function onReset() {
  kw.value = ''
  tagIds.value = []
  kind.value = 'table'
  emitSearch()
}

async function loadTags() {
  loadingTags.value = true
  try {
    const resp: any = await listAssetTags()
    const arr = Array.isArray(resp) ? resp : (resp?.items || [])
    tagOptions.value = arr.map((t: any) => ({ label: t.name || t.code, value: t.id }))
  } finally {
    loadingTags.value = false
  }
}

function openCreateTag() {
  tagForm.code = ''
  tagForm.name = ''
  tagForm.color = '#3371fc'
  tagOpen.value = true
}

async function doCreateTag() {
  if (!tagForm.code || !tagForm.name) {
    message.warning(t2('code 与名称必填'))
    return
  }
  creating.value = true
  try {
    await createAssetTag({ ...tagForm, tag_kind: 'table' })
    message.success(t2('标签已创建'))
    tagOpen.value = false
    await loadTags()
  } catch {
    /* TAG_CODE_DUPLICATED 等已由拦截器按 code 提示 */
  } finally {
    creating.value = false
  }
}

onMounted(loadTags)
defineExpose({ reloadTags: loadTags })
</script>

<style lang="less" scoped>
.asset-search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
