<template>
  <div class="asset-cards">
    <a-spin :spinning="loading">
      <a-empty v-if="!items.length" :description="t2('无匹配资产，可调整关键词/标签或先执行扫描')" />
      <div v-else class="asset-cards__grid">
        <div
          v-for="it in items"
          :key="it.table_id"
          class="asset-cards__card"
          :class="{ 'asset-cards__card--on': isChecked(it) }"
        >
          <div class="asset-cards__head">
            <a-checkbox
              :checked="isChecked(it)"
              :disabled="lockedOut(it)"
              @change="toggle(it)"
            />
            <span class="asset-cards__name" :title="it.table_name">{{ it.table_name }}</span>
            <a-tag v-if="it.pii_max_level && it.pii_max_level !== 'L0'" color="red">{{ it.pii_max_level }}</a-tag>
            <a-tag v-if="it.bound_object_code" color="green">{{ t2('已映射') }}</a-tag>
          </div>
          <div class="asset-cards__meta">
            {{ it.db_name || it.database || '-' }}<template v-if="it.table_comment"> · {{ it.table_comment }}</template>
          </div>
          <div class="asset-cards__digest" :title="it.column_digest">{{ it.column_digest || t2('（无字段摘要）') }}</div>
          <div class="asset-cards__foot">
            <span>{{ t2('列') }} {{ it.column_count ?? '-' }} · {{ t2('行') }} {{ it.row_count ?? '-' }}</span>
            <span class="asset-cards__tags">
              <a-tag v-for="tg in it.tags || []" :key="tg.code" :color="tg.color || undefined">{{ tg.name }}</a-tag>
            </span>
          </div>
        </div>
      </div>
    </a-spin>
    <div v-if="total > 0" class="asset-cards__pager">
      <a-pagination
        :current="page"
        :page-size="size"
        :total="total"
        size="small"
        :show-total="(n: number) => `${t2('共')} ${n} ${t2('条')}`"
        @change="(p: number) => emit('page-change', p)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产表卡片清单（AF-05/07/08）：column_digest 内联 + pii/已映射标记 + 分页多选。
 * 跨源拦截（§4.7 约束5）：已选集合锁定 source_id，异源卡片复选框禁用。
 */
import { message } from 'ant-design-vue'
import { t2 } from '../ontology/ontologyText'

const props = defineProps<{
  items: any[]
  total: number
  page: number
  size: number
  loading?: boolean
  selected: any[]
}>()
const emit = defineEmits<{
  (e: 'toggle', row: any, checked: boolean): void
  (e: 'page-change', page: number): void
}>()

function isChecked(it: any) {
  return props.selected.some((s) => s.table_id === it.table_id)
}

/** 已选集合限定单一 source_id 后，其他源的卡片禁选 */
function lockedOut(it: any) {
  if (!props.selected.length) return false
  return props.selected[0].source_id !== it.source_id
}

function toggle(it: any) {
  if (lockedOut(it)) {
    message.warning(t2('一个建模作用域仅允许单一数据源，请先清空勾选'))
    return
  }
  emit('toggle', it, !isChecked(it))
}
</script>

<style lang="less" scoped>
.asset-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 10px;
    overflow: auto;
  }
  &__card {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    &--on {
      border-color: var(--ant-primary-color, #1677ff);
      background: rgba(22, 119, 255, 0.04);
    }
  }
  &__head {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  &__name {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &__meta,
  &__foot {
    font-size: 12px;
    color: var(--fg-mute, #888);
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  &__digest {
    font-size: 12px;
    color: var(--fg, #333);
    background: var(--bg-soft, rgba(0, 0, 0, 0.03));
    border-radius: 4px;
    padding: 4px 6px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-all;
  }
  &__pager {
    align-self: flex-end;
  }
}
</style>
