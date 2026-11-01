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
            <span class="asset-cards__name" :title="it.table_name" v-html="hl(it.table_name, kw || '')" />
            <span v-if="it.score" class="score" :class="'s' + it.score">{{ it.score }}</span>
            <span v-if="it.bound_object_code" class="badge b-ok">{{ t2('已映射') + ' ' + it.bound_object_code }}</span>
            <span
              v-if="it.pii_max_level && it.pii_max_level !== 'L0'"
              class="badge"
              :class="piiTone(it.pii_max_level)"
              :title="t2('meta_column.pii_level')"
            >{{ 'PII ' + it.pii_max_level }}</span>
          </div>
          <div class="asset-cards__meta">
            {{ it.db_name || it.database || '-' }}<template v-if="it.table_comment"> · {{ it.table_comment }}</template>
          </div>
          <div
            class="asset-cards__digest"
            :class="{ exp: isExp(it.table_id) }"
            :title="it.column_digest"
            @click="toggleExp(it.table_id)"
          >{{ it.column_digest || t2('（无字段摘要）') }}</div>
          <div class="asset-cards__foot">
            <span>{{ t2('列') }} {{ it.column_count ?? '-' }} · {{ t2('行') }} {{ fmtRows(it.row_count) }}</span>
            <span class="asset-cards__tags">
              <a-tag v-for="tg in it.tags || []" :key="tg.code" :color="tg.color || undefined">{{ tg.name }}</a-tag>
            </span>
          </div>
          <div class="asset-cards__ops">
            <a-button
              size="small"
              :class="['probe', probeView(probe?.[it.table_id]).cls]"
              :loading="probing.has(it.table_id)"
              @click="emit('test', it)"
            >{{ t2(probeView(probe?.[it.table_id]).text) }}</a-button>
            <a-button size="small" @click="emit('edit', it)">{{ t2('编辑') }}</a-button>
            <a-button size="small" @click="emit('tag', it)">{{ t2('＋标签') }}</a-button>
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
 * 资产表卡片清单（AF-05/07/08）：三段得分徽章 + 已映射码 + PII 分级配色 + 关键词高亮 + 摘要展开。
 * 跨源拦截（§4.7 约束5）：已选集合锁定 source_id，异源卡片复选框禁用。
 */
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { t2 } from '../ontology/ontologyText'
import { hl, fmtRows } from './assetText'
import { probeView } from './assetOps'

type ProbeResult = { ok: boolean; code?: string | null }

const props = defineProps<{
  items: any[]
  total: number
  page: number
  size: number
  loading?: boolean
  selected: any[]
  kw?: string
  /** 各表探活结果（table_id → 结果），由父级探活后回填；缺省视为空闲态 */
  probe?: Record<number, ProbeResult>
}>()
const emit = defineEmits<{
  (e: 'toggle', row: any, checked: boolean): void
  (e: 'page-change', page: number): void
  (e: 'test', row: any): void
  (e: 'edit', row: any): void
  (e: 'tag', row: any): void
}>()

/** 正在探活的表 ID（按钮 loading 态，与回填结果独立） */
const probing = ref<Set<number>>(new Set())
defineExpose({
  /** 父级发起探活前置 loading，返回后清除 */
  setProbing(tableId: number, on: boolean) {
    const next = new Set(probing.value)
    next.has(tableId) ? next.delete(tableId) : on && next.add(tableId)
    probing.value = next
  },
})

/** PII 配色（原型口径）：L2/L3 → 错误(红)，其余（L1）→ 告警(黄) */
function piiTone(level: string) {
  return level === 'L2' || level === 'L3' ? 'b-err' : 'b-warn'
}

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

/** 字段摘要默认 2 行截断，点击解除（expanded 态） */
const expanded = ref<Set<number>>(new Set())
function isExp(id: number) {
  return expanded.value.has(id)
}
function toggleExp(id: number) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
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
    flex-wrap: wrap;
  }
  &__name {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    :deep(mark) {
      background: #fff3a3;
      color: inherit;
      padding: 0 1px;
      border-radius: 2px;
    }
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
    cursor: pointer;
    &.exp {
      -webkit-line-clamp: unset;
      display: block;
    }
  }
  &__pager {
    align-self: flex-end;
  }
  &__ops {
    display: flex;
    gap: 6px;
  }
}
// 三段确定性得分徽章（原型 .score.s3/s2/s1 配色）
.score {
  font-family: var(--mono, monospace);
  font-size: 9.5px;
  color: var(--fg-mute, #888);
  border: 1px solid var(--border, #d9d9d9);
  border-radius: 3px;
  padding: 0 4px;
  &.s3 {
    background: #f6ffed;
    border-color: #b7eb8f;
    color: #389e0d;
    font-weight: 600;
  }
  &.s2 {
    background: #e6f4ff;
    border-color: #bcd8ff;
    color: #1677ff;
  }
  &.s1 {
    background: #fffbe6;
    border-color: #ffe58f;
    color: #874d00;
  }
}
.badge {
  border-radius: 10px;
  font-size: 10.5px;
  padding: 0 7px;
  line-height: 18px;
  border: 1px solid;
  &.b-ok {
    background: #f6ffed;
    border-color: #b7eb8f;
    color: #389e0d;
  }
  &.b-warn {
    background: #fffbe6;
    border-color: #ffe58f;
    color: #874d00;
  }
  &.b-err {
    background: #fff1f0;
    border-color: #ffa39e;
    color: #cf1322;
  }
}
// 探活按钮三态（空闲/通过/失败）
.probe {
  &.ok {
    color: #389e0d;
    border-color: #b7eb8f;
    background: #f6ffed;
  }
  &.err {
    color: #cf1322;
    border-color: #ffa39e;
    background: #fff1f0;
  }
}
</style>
