<template>
  <div class="custom-table-column">
    <a-popover trigger="click" placement="topLeft" :z-index="9999">
      <template #content>
        <div class="column-checkbox-list">
          <a-checkbox-group v-model:value="selected" @change="handleChange">
            <a-checkbox
              v-for="item in fields"
              v-show="item.type !== 'selection' && item.slot !== 'radio'"
              :key="item.id"
              :value="item.id"
            >
              {{ item.title }}
            </a-checkbox>
          </a-checkbox-group>
        </div>
      </template>
      <a-button type="text" class="column-btn">
        <template #icon>
          <UnorderedListOutlined class="column-icon" />
        </template>
        列表自定义
      </a-button>
    </a-popover>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { UnorderedListOutlined } from '@ant-design/icons-vue'

interface Field {
  id: string
  title: string
  checked: boolean
  type?: string
  slot?: string
}

const props = defineProps<{
  fields: Field[]
}>()

const emit = defineEmits<{
  'changeColumns': []
}>()

const selected = ref<string[]>([])

watch(() => props.fields, (val) => {
  selected.value = []
  if (val.length > 0) {
    val.forEach(item => {
      if (item.checked) {
        selected.value.push(item.id)
      }
    })
  }
}, { deep: true, immediate: true })

const handleChange = (val: string[]) => {
  props.fields.forEach((item, index) => {
    props.fields[index].checked = val.includes(item.id)
  })
  emit('changeColumns')
}
</script>

<style lang="less" scoped>
.custom-table-column {
  display: inline-block;
  z-index: 10;
}

.column-btn {
  padding: 0;
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #666;

  &:focus {
    box-shadow: none;
  }
}

.column-icon {
  font-size: 20px;
  font-weight: 700;
}

.column-checkbox-list {
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;

  :deep(.ant-checkbox-wrapper) {
    display: flex;
    align-items: center;
    margin: 4px 0;
    margin-left: 0 !important;
  }

  :deep(.ant-checkbox-group) {
    display: flex;
    flex-direction: column;
  }
}
</style>
