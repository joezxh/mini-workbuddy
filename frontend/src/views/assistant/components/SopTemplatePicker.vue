<script setup lang="ts">
/**
 * SopTemplatePicker —— SOP 模式下的模板选择器。
 *
 * 对接 GET /api/v1/sop/templates?keyword=，选中后把 template_key 回传给父组件，
 * 由父组件随 chat_stream 请求体的 sop_template_id 提交给后端。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { listSopTemplates, type SopTemplateItem } from '@/api/sop'

const props = defineProps<{ modelValue?: string | null }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void
}>()

const keyword = ref('')
const items = ref<SopTemplateItem[]>([])
const loading = ref(false)
const error = ref('')
const open = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = await listSopTemplates(keyword.value.trim())
  } catch (e: any) {
    error.value = e?.message || '模板加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 关键词防抖，避免每键一次请求
let timer: ReturnType<typeof setTimeout> | undefined
watch(keyword, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 250)
})

const selected = computed(
  () => items.value.find(i => i.template_key === props.modelValue) || null
)

function pick(item: SopTemplateItem) {
  emit('update:modelValue', item.template_key)
  open.value = false
}

function clear() {
  emit('update:modelValue', null)
}

const stepCount = (item: SopTemplateItem) => item.definition?.steps?.length ?? 0
const humanCount = (item: SopTemplateItem) =>
  (item.definition?.steps ?? []).filter(s => s.verifier_type === 'human').length
</script>

<template>
  <div class="sop-picker">
    <div class="picker-bar">
      <span class="label">SOP 模板</span>
      <span v-if="selected" class="selected">
        {{ selected.name }}
        <span class="meta">{{ stepCount(selected) }} 步</span>
        <span v-if="humanCount(selected)" class="meta human">
          {{ humanCount(selected) }} 道人工验收
        </span>
      </span>
      <span v-else class="selected muted">未选择（按内置思考流程执行）</span>

      <button class="btn" @click="open = !open">
        {{ open ? '收起' : '选择模板' }}
      </button>
      <button v-if="selected" class="btn ghost" @click="clear">清除</button>
    </div>

    <div v-if="open" class="panel">
      <input
        v-model="keyword"
        class="search"
        placeholder="搜索模板：巴菲特 / 游资 / 自媒体 …"
      />
      <p v-if="loading" class="hint">加载中…</p>
      <p v-else-if="error" class="hint error">{{ error }}</p>
      <p v-else-if="!items.length" class="hint">无匹配模板</p>

      <ul v-else class="list">
        <li
          v-for="item in items"
          :key="item.template_key"
          class="item"
          :class="{ active: item.template_key === modelValue }"
          @click="pick(item)"
        >
          <div class="item-top">
            <span class="name">{{ item.name }}</span>
            <span v-if="item.builtin" class="tag builtin">内置</span>
            <span class="meta">{{ stepCount(item) }} 步</span>
            <span v-if="humanCount(item)" class="meta human">人工验收</span>
          </div>
          <p v-if="item.description" class="desc">{{ item.description }}</p>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.sop-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #2c3040;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
  font-size: 13px;
}
.picker-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.label { font-weight: 600; color: #b6bbc8; }
.selected { color: #d0d4dc; }
.selected.muted { color: #8b90a0; }
.meta { margin-left: 6px; color: #8b90a0; font-size: 12px; }
.meta.human { color: #e0a33c; }

.btn {
  padding: 2px 10px;
  border: 1px solid #3a4055;
  border-radius: 4px;
  background: #242836;
  color: #d0d4dc;
  font-size: 12px;
  cursor: pointer;
}
.btn.ghost { background: transparent; }
.btn:hover { border-color: #3371fc; }

.panel { display: flex; flex-direction: column; gap: 6px; }
.search {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #2c3040;
  border-radius: 4px;
  background: #1b1e28;
  color: inherit;
  font: inherit;
}
.hint { margin: 0; color: #8b90a0; font-size: 12px; }
.hint.error { color: #ef6b6b; }

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 240px;
  overflow-y: auto;
}
.item {
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.item:hover { background: rgba(51, 113, 252, 0.12); }
.item.active { background: rgba(51, 113, 252, 0.2); }
.item-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.name { font-weight: 500; }
.tag {
  padding: 0 5px;
  border-radius: 3px;
  font-size: 11px;
  background: #2c3040;
  color: #b6bbc8;
}
.tag.builtin { background: rgba(51, 113, 252, 0.2); color: #6f9bff; }
.desc {
  margin: 2px 0 0;
  color: #8b90a0;
  font-size: 12px;
}
</style>
