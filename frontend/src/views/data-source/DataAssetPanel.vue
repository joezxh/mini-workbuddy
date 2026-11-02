<template>
  <div class="data-asset">
    <div class="data-asset__header">
      <h2 class="data-asset__title">{{ t('knowledge.menu.dataAsset') }}</h2>
      <span class="data-asset__hint">{{ t2('按类型浏览数据资产，勾选表后送入本体建模作用域') }}</span>
    </div>
    <div class="data-asset__body">
      <AssetPickerPanel ref="pickerRef" class="data-asset__picker" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 数据资产目录页（AF-01~AF-08 独立入口，路由 /admin/data-asset）。
 * 把原先埋在「数据源 › 元数据 › 资产送数」里的 AssetPickerPanel 提升为一等页面：
 * 挂载即 activate() 懒加载目录树与本体清单（与 MetadataExplorer 的 picker 模式一致）。
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AssetPickerPanel from './asset/AssetPickerPanel.vue'
import { t2 } from './ontology/ontologyText'

const { t } = useI18n()
const pickerRef = ref<any>(null)

onMounted(() => {
  pickerRef.value?.activate?.()
})
</script>

<style lang="less" scoped>
.data-asset {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding-bottom: 12px;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }
  &__title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: var(--fg);
  }
  &__hint {
    font-size: 12px;
    color: var(--fg-mute, #888);
  }
  &__body {
    flex: 1;
    min-height: 0;
    display: flex;
  }
  &__picker {
    flex: 1;
    min-height: 0;
  }
}
</style>
