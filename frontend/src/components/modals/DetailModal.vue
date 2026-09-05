/**
 * 详情弹窗组件
 */
<template>
  <a-modal
    v-model:open="visible"
    :title="title"
    :width="width"
    :footer="null"
    :destroy-on-close="true"
    wrap-class-name="detail-modal"
  >
    <a-spin :spinning="loading">
      <div class="detail-modal__content">
        <slot></slot>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  modelValue: boolean
  title: string
  width?: string | number
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: '80%',
  loading: false
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})
</script>

<style lang="less">
.detail-modal {
  .ant-modal-content {
    // background: linear-gradient(135deg, rgba(30, 39, 58, 0.98) 0%, rgba(20, 29, 48, 0.98) 100%);
    border: 1px solid rgba(64, 158, 255, 0.3);
  }

  .ant-modal-header {
    background: transparent;
    border-bottom: 1px solid rgba(64, 158, 255, 0.2);

    .ant-modal-title {
      color: #fff;
      font-size: 14px;
      font-weight: 600;
    }
  }

  .ant-modal-close {
    color: rgba(255, 255, 255, 0.7);

    &:hover {
      color: #fff;
    }
  }

  .ant-modal-body {
    padding: 24px;
  }
}

.detail-modal__content {
  min-height: 400px;
  color: rgba(255, 255, 255, 0.85);
}
</style>

