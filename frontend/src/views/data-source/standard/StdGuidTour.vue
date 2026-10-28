<template>
  <a-card size="small" class="std-tour">
    <div class="std-tour__head">
      <strong>{{ t('kbMgmt.tour.title') }}</strong>
      <span class="std-tour__hint">{{ t('kbMgmt.tour.hint') }}</span>
    </div>
    <a-steps size="small" :current="current" :items="items" />
  </a-card>
</template>

<script setup lang="ts">
/**
 * 建模导览：静态六步（建目录→定义对象→挂属性→连关系→绑定→看统计）。
 * 仅做指路与进度提示，不做 gamified 徽章，也不驱动任何写操作。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

withDefaults(defineProps<{ current?: number }>(), { current: 0 })

const { t } = useI18n()

const items = computed(() => [
  { title: t('kbMgmt.tour.catalog') },
  { title: t('kbMgmt.tour.object') },
  { title: t('kbMgmt.tour.attribute') },
  { title: t('kbMgmt.tour.relation') },
  { title: t('kbMgmt.tour.bind') },
  { title: t('kbMgmt.tour.stats') },
])
</script>

<style scoped>
.std-tour__head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.std-tour__hint {
  color: var(--fg-muted);
  font-size: 12px;
}
</style>
