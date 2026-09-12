<template>
  <div class="diff-view">
    <a-empty v-if="!hasDiff" :description="t('knowledge.common.empty')" />
    <table v-else class="diff-view__table">
      <thead>
        <tr>
          <th class="diff-view__key">字段</th>
          <th>左（旧）</th>
          <th>右（新）</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key" :class="row.cls">
          <td class="diff-view__key">{{ row.key }}</td>
          <td><pre>{{ row.left }}</pre></td>
          <td><pre>{{ row.right }}</pre></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ left: unknown; right: unknown }>()
const { t } = useI18n()

function toObj(v: unknown): Record<string, any> {
  if (v == null) return {}
  if (typeof v === 'string') {
    try {
      return JSON.parse(v)
    } catch {
      return { value: v }
    }
  }
  return v as Record<string, any>
}

const rows = computed(() => {
  const l = toObj(props.left)
  const r = toObj(props.right)
  const keys = Array.from(new Set([...Object.keys(l), ...Object.keys(r)]))
  return keys.map((k) => {
    const lv = l[k]
    const rv = r[k]
    const lvStr = typeof lv === 'object' ? JSON.stringify(lv) : String(lv ?? '')
    const rvStr = typeof rv === 'object' ? JSON.stringify(rv) : String(rv ?? '')
    let cls = ''
    if (lvStr !== rvStr) cls = 'diff-view__row--changed'
    return { key: k, left: lvStr, right: rvStr, cls }
  })
})

const hasDiff = computed(() => rows.value.length > 0)
</script>

<style lang="less" scoped>
.diff-view {
  &__table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
  }

  th,
  td {
    border: 1px solid var(--border);
    padding: 6px 10px;
    text-align: left;
    vertical-align: top;
  }

  th {
    background: var(--bg-hover);
    color: var(--fg-secondary);
    font-weight: 600;
  }

  &__key {
    width: 180px;
    color: var(--fg-secondary);
    font-weight: 600;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    font-family: 'SFMono-Regular', Consolas, monospace;
  }

  &__row--changed {
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }
}
</style>
