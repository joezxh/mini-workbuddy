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
    <a-select v-model:value="kind" style="width: 100px" @change="emitSearch">
      <a-select-option value="table">{{ t2('表') }}</a-select-option>
      <a-select-option value="column">{{ t2('字段') }}</a-select-option>
    </a-select>
    <a-select v-model:value="tableType" style="width: 120px" @change="emitSearch">
      <a-select-option value="all">{{ t2('全部对象') }}</a-select-option>
      <a-select-option value="BASE TABLE">{{ t2('仅表') }}</a-select-option>
      <a-select-option value="VIEW">{{ t2('仅视图') }}</a-select-option>
    </a-select>
    <a-select v-model:value="sort" style="width: 130px" @change="emitSearch">
      <a-select-option value="score">{{ t2('相关度') }}</a-select-option>
      <a-select-option value="updated">{{ t2('更新时间') }}</a-select-option>
      <a-select-option value="rows">{{ t2('行数') }}</a-select-option>
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
        <a-form-item :label="t2('类别 tag_kind')" required>
          <a-select v-model:value="tagForm.tag_kind" style="width: 100%">
            <a-select-option v-for="k in TAG_KINDS" :key="k" :value="k">{{ kindLabel(k) }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t2('颜色')">
          <div class="asset-search__swatches">
            <span
              v-for="c in COLORS"
              :key="c"
              class="asset-search__swatch"
              :class="{ on: tagForm.color === c }"
              :style="{ background: c }"
              @click="tagForm.color = c"
            />
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产检索条（AF-02/03）：全文检索 + 标签筛选 + 对象类型/排序下拉 + 新建标签（tag_kind 修复 + 色板）。
 * 载荷归一委托纯函数 :func:`buildSearchPayload`/`buildTagPayload`；emit `search` 交父级驱动 E28。
 */
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { createAssetTag, listAssetTags } from '@/api/dataops'
import { t2 } from '../ontology/ontologyText'
import { COLORS, TAG_KINDS, buildSearchPayload, buildTagPayload } from './assetSearch'

const emit = defineEmits<{
  (e: 'search', payload: {
    kw: string; tag_ids: number[]; kind: string
    table_type?: string; sort: string; size: number
  }): void
}>()

defineProps<{ loading?: boolean }>()

const kw = ref('')
const kind = ref('table')
const tableType = ref('all')
const sort = ref('score')
const tagIds = ref<number[]>([])
const tagOptions = ref<{ label: string; value: number }[]>([])
const loadingTags = ref(false)

const tagOpen = ref(false)
const creating = ref(false)
const tagForm = reactive({ code: '', name: '', color: COLORS[0], tag_kind: 'custom' })

function kindLabel(k: string) {
  return { biz: 'biz 主题', security: 'security 安全', quality: 'quality 质量', custom: 'custom 自定义' }[k] || k
}

function emitSearch() {
  emit('search', buildSearchPayload({
    kw: kw.value, tag_ids: tagIds.value, kind: kind.value, table_type: tableType.value, sort: sort.value,
  }))
}

function onReset() {
  kw.value = ''
  tagIds.value = []
  kind.value = 'table'
  tableType.value = 'all'
  sort.value = 'score'
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
  tagForm.color = COLORS[0]
  tagForm.tag_kind = 'custom'
  tagOpen.value = true
}

async function doCreateTag() {
  const payload = buildTagPayload(tagForm)
  if (!payload.code || !payload.name) {
    message.warning(t2('code 与名称必填'))
    return
  }
  creating.value = true
  try {
    await createAssetTag(payload)
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
  &__swatches {
    display: flex;
    gap: 7px;
  }
  &__swatch {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    cursor: pointer;
    border: 2px solid transparent;
    &.on {
      border-color: var(--fg, #333);
      transform: scale(1.12);
    }
  }
}
</style>
