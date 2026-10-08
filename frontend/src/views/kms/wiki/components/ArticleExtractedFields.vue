<template>
  <a-card v-if="fields.length" size="small" class="extracted">
    <template #title>
      <div class="extracted__title">
        <span>{{ t('kmsWiki.extractedFields') }}</span>
        <a-button type="link" size="small" @click="open = !open">
          {{ open ? t('kmsWiki.collapseFields') : t('kmsWiki.expandFields') }}
        </a-button>
      </div>
    </template>

    <div v-show="open" class="extracted__body">
      <div v-for="field in fields" :key="field.key" class="extracted__item">
        <div class="extracted__label">{{ field.label }}</div>

        <!-- 多行文本 -->
        <a-textarea
          v-if="field.type === 'textarea'"
          :value="values[field.key] ?? ''"
          :rows="3"
          @update:value="set(field.key, $event)"
        />

        <!-- 下拉枚举 -->
        <a-select
          v-else-if="field.type === 'select'"
          :value="values[field.key] ?? undefined"
          :options="(field.options || []).map((o) => ({ value: o, label: field.optionLabels?.[o] || o }))"
          allow-clear
          style="width: 100%"
          @update:value="set(field.key, $event ?? null)"
        />

        <!-- 标签 -->
        <a-select
          v-else-if="field.type === 'tags'"
          :value="values[field.key] || []"
          mode="tags"
          style="width: 100%"
          @update:value="set(field.key, $event || [])"
        />

        <!-- 来源条目（可增删改） -->
        <div v-else-if="field.type === 'sources'" class="sources">
          <div v-for="(src, idx) in (values[field.key] || [])" :key="idx" class="sources__row">
            <a-input
              :value="src.resource"
              readonly
              size="small"
              :title="src.resource"
            >
              <template #addonBefore>{{ t('kmsWiki.resource') }}</template>
            </a-input>
            <a-input
              :value="src.title ?? ''"
              size="small"
              :placeholder="t('kmsWiki.sourceTitle')"
              @update:value="setSource(field.key, idx, 'title', $event)"
            />
            <a-input
              :value="src.author ?? ''"
              size="small"
              :placeholder="t('kmsWiki.sourceAuthor')"
              @update:value="setSource(field.key, idx, 'author', $event)"
            />
            <a-input
              :value="src.last_modified ?? ''"
              size="small"
              :placeholder="t('kmsWiki.sourceLastModified')"
              @update:value="setSource(field.key, idx, 'last_modified', $event)"
            />
            <a-button size="small" danger type="text" @click="removeSource(field.key, idx)">
              {{ t('kmsWiki.removeSource') }}
            </a-button>
          </div>
          <a-button size="small" type="dashed" block @click="addSource(field.key)">
            <plus-outlined /> {{ t('kmsWiki.addSource') }}
          </a-button>
        </div>

        <!-- 普通文本 -->
        <a-input v-else :value="values[field.key] ?? ''" @update:value="set(field.key, $event)" />
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined } from '@ant-design/icons-vue'
import type { DocSource } from '@/api/wiki'

interface FieldDef {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'tags' | 'sources'
  options?: string[]
  /** 选项值 → 展示文案（用于 OKF 类型等需翻译的枚举） */
  optionLabels?: Record<string, string>
}

const props = defineProps<{ fields: FieldDef[]; values: Record<string, any> }>()
const emit = defineEmits<{ 'update:values': [Record<string, any>] }>()

const { t } = useI18n()
const open = ref(true)

function set(key: string, value: unknown) {
  emit('update:values', { ...props.values, [key]: value })
}

function setSource(key: string, idx: number, prop: keyof DocSource, value: string) {
  const list: DocSource[] = [...(props.values[key] || [])]
  list[idx] = { ...list[idx], [prop]: value }
  emit('update:values', { ...props.values, [key]: list })
}

function addSource(key: string) {
  const list: DocSource[] = [...(props.values[key] || []), { resource: '', title: '', author: '' }]
  emit('update:values', { ...props.values, [key]: list })
}

function removeSource(key: string, idx: number) {
  const list: DocSource[] = (props.values[key] || []).filter((_: DocSource, i: number) => i !== idx)
  emit('update:values', { ...props.values, [key]: list })
}
</script>

<style scoped>
.extracted__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.extracted__body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.extracted__label {
  font-size: 13px;
  font-weight: 500;
  color: var(--fg-secondary, #646a73);
  margin-bottom: 6px;
}
.sources {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sources__row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border: 1px solid var(--border, #e5e6eb);
  border-radius: 6px;
  background: var(--bg-subtle, #fafafa);
}
</style>
