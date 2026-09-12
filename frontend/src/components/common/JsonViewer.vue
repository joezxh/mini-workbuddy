<template>
  <div class="json-viewer">
    <div class="json-viewer__bar" v-if="copyable">
      <a-button size="small" type="text" @click="copy">
        <CopyOutlined /> {{ copied ? t('knowledge.common.close') : t('knowledge.common.copy') }}
      </a-button>
    </div>
    <pre class="json-viewer__code" :class="{ 'json-viewer__code--dark': dark }">{{ formatted }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { CopyOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

const props = withDefaults(
  defineProps<{
    value: unknown
    dark?: boolean
    copyable?: boolean
    compact?: boolean
  }>(),
  { dark: false, copyable: true, compact: false },
)

const { t } = useI18n()
const copied = ref(false)

function normalize(v: unknown): string {
  if (typeof v === 'string') {
    try {
      return JSON.stringify(JSON.parse(v), null, props.compact ? 0 : 2)
    } catch {
      return v
    }
  }
  try {
    return JSON.stringify(v, null, props.compact ? 0 : 2)
  } catch {
    return String(v)
  }
}

const formatted = computed(() => normalize(props.value))

async function copy() {
  try {
    await navigator.clipboard.writeText(formatted.value)
    copied.value = true
    message.success('已复制')
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    message.error('复制失败')
  }
}
</script>

<style lang="less" scoped>
.json-viewer {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  overflow: hidden;

  &__bar {
    display: flex;
    justify-content: flex-end;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-hover);
  }

  &__code {
    margin: 0;
    padding: 12px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--fg);
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 480px;
    overflow: auto;

    &--dark {
      background: #0f172a;
      color: #e2e8f0;
    }
  }
}
</style>
