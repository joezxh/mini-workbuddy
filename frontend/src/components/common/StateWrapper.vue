/**
 * StateWrapper — 三态容器组件
 *
 * 统一处理 loading / empty / error 三种状态，避免重复编写 v-if/v-else 逻辑。
 * 使用插槽机制：默认插槽放内容，命名插槽自定义各状态 UI。
 *
 * 优先级：loading > error > empty > default slot
 */
<template>
  <div class="state-wrapper">
    <!-- Loading 状态 -->
    <div v-if="loading" class="state-wrapper__state">
      <slot name="loading">
        <LoadingSpinner :text="loadingText" />
      </slot>
    </div>

    <!-- Error 状态 -->
    <div v-else-if="error" class="state-wrapper__state">
      <slot name="error" :error="error">
        <div class="state-wrapper__message">
          <div class="state-wrapper__icon state-wrapper__icon--error">
            <ExclamationCircleOutlined />
          </div>
          <div class="state-wrapper__title">{{ errorTitle }}</div>
          <div class="state-wrapper__desc">{{ error }}</div>
          <button v-if="retryable" class="state-wrapper__retry" @click="$emit('retry')">
            {{ retryText }}
          </button>
        </div>
      </slot>
    </div>

    <!-- Empty 状态 -->
    <div v-else-if="empty" class="state-wrapper__state">
      <slot name="empty">
        <div class="state-wrapper__message">
          <div class="state-wrapper__icon state-wrapper__icon--empty">
            <InboxOutlined />
          </div>
          <div class="state-wrapper__title">{{ emptyTitle }}</div>
          <div v-if="emptyDesc" class="state-wrapper__desc">{{ emptyDesc }}</div>
        </div>
      </slot>
    </div>

    <!-- 正常内容 -->
    <div v-else class="state-wrapper__content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ExclamationCircleOutlined, InboxOutlined } from '@ant-design/icons-vue'
import LoadingSpinner from './LoadingSpinner.vue'

interface Props {
  /** 是否加载中 */
  loading?: boolean
  /** 错误信息（非空字符串或 Error 对象触发 error 状态） */
  error?: string | Error | null
  /** 是否为空 */
  empty?: boolean
  /** 加载中文案 */
  loadingText?: string
  /** 错误标题 */
  errorTitle?: string
  /** 空状态标题 */
  emptyTitle?: string
  /** 空状态描述 */
  emptyDesc?: string
  /** 是否可重试 */
  retryable?: boolean
  /** 重试按钮文案 */
  retryText?: string
}

withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
  empty: false,
  loadingText: '加载中...',
  errorTitle: '加载失败',
  emptyTitle: '暂无数据',
  emptyDesc: '',
  retryable: true,
  retryText: '重试',
})

defineEmits<{
  retry: []
}>()
</script>

<style lang="less" scoped>
.state-wrapper {
  width: 100%;

  &__state {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    padding: 40px 20px;
  }

  &__content {
    width: 100%;
  }

  &__message {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    text-align: center;
  }

  &__icon {
    font-size: 48px;
    line-height: 1;

    &--error {
      color: var(--err);
    }

    &--empty {
      color: var(--fg-muted);
    }
  }

  &__title {
    font-size: 16px;
    font-weight: 500;
    color: var(--fg);
  }

  &__desc {
    font-size: 14px;
    color: var(--fg-secondary);
    max-width: 400px;
  }

  &__retry {
    margin-top: 8px;
    padding: 8px 20px;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--fg);
    font-size: 14px;
    cursor: pointer;
    transition: all var(--transition);

    &:hover {
      border-color: var(--accent);
      color: var(--accent);
    }
  }
}
</style>
