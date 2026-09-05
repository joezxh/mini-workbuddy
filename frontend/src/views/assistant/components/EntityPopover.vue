<template>
  <div
    v-if="popover.visible && popover.entityData"
    class="entity-popover"
    :style="{ top: popover.y + 'px', left: popover.x + 'px' }"
    @mouseover="onPopoverEnter"
    @mouseout="onPopoverLeave"
  >
    <!-- 企业实体 -->
    <template v-if="popover.entityType === 'entity'">
      <div class="entity-popover-header">
        <span class="entity-type-badge entity-badge">企业</span>
        <span class="entity-popover-title">{{ popover.entityData.name }}</span>
        <span :class="['risk-tag', `risk-${detail.risk_level}`]">{{ riskLabel(detail.risk_level) }}</span>
      </div>
      <div class="entity-popover-body">
        <div v-if="detail.legal_person" class="entity-row"><span class="label">法定代表人</span><span class="value">{{ detail.legal_person }}</span></div>
        <div v-if="detail.entity_type" class="entity-row"><span class="label">类型</span><span class="value">{{ typeLabel(detail.entity_type) }}</span></div>
        <div v-if="detail.registered_capital" class="entity-row"><span class="label">注册资本</span><span class="value">{{ formatCapital(detail.registered_capital) }}</span></div>
        <div v-if="detail.industry" class="entity-row"><span class="label">行业</span><span class="value">{{ detail.industry }}</span></div>
        <div v-if="detail.risk_score" class="entity-row"><span class="label">风险评分</span><span class="value">{{ detail.risk_score }}</span></div>
        <div v-if="detail.registered_address" class="entity-row"><span class="label">注册地址</span><span class="value address">{{ detail.registered_address }}</span></div>
        <div v-if="detail.business_scope" class="entity-row"><span class="label">经营范围</span><span class="value scope">{{ detail.business_scope }}</span></div>
      </div>
    </template>

    <!-- 人员 -->
    <template v-else-if="popover.entityType === 'person'">
      <div class="entity-popover-header">
        <span class="entity-type-badge person-badge">人员</span>
        <span class="entity-popover-title">{{ popover.entityData.name }}</span>
        <span :class="['risk-tag', `risk-${detail.risk_level}`]">{{ riskLabel(detail.risk_level) }}</span>
      </div>
      <div class="entity-popover-body">
        <div v-if="detail.gender" class="entity-row"><span class="label">性别</span><span class="value">{{ detail.gender }}</span></div>
        <div v-if="detail.age" class="entity-row"><span class="label">年龄</span><span class="value">{{ detail.age }}岁</span></div>
        <div v-if="detail.person_type" class="entity-row"><span class="label">人员类型</span><span class="value">{{ detail.person_type }}</span></div>
        <div v-if="detail.occupation" class="entity-row"><span class="label">职业</span><span class="value">{{ detail.occupation }}</span></div>
        <div v-if="detail.current_region_name" class="entity-row"><span class="label">管辖地区</span><span class="value">{{ detail.current_region_name }}</span></div>
        <div v-if="detail.risk_score" class="entity-row"><span class="label">风险评分</span><span class="value">{{ detail.risk_score }}</span></div>
        <div v-if="detail.tags" class="entity-row"><span class="label">标签</span><span class="value tags">{{ detail.tags }}</span></div>
        <div v-if="detail.is_key_person" class="entity-row"><span class="label">标记</span><span class="value key-person">重点人员</span></div>
      </div>
    </template>

    <!-- 地点 -->
    <template v-else-if="popover.entityType === 'location'">
      <div class="entity-popover-header">
        <span class="entity-type-badge location-badge">地点</span>
        <span class="entity-popover-title">{{ popover.entityData.name }}</span>
        <span :class="['risk-tag', `risk-${detail.risk_level}`]">{{ riskLabel(detail.risk_level) }}</span>
      </div>
      <div class="entity-popover-body">
        <div v-if="detail.location_type" class="entity-row"><span class="label">类型</span><span class="value">{{ locationTypeLabel(detail.location_type) }}</span></div>
        <div v-if="detail.region_name" class="entity-row"><span class="label">行政区划</span><span class="value">{{ detail.region_name }}</span></div>
        <div v-if="detail.address" class="entity-row"><span class="label">地址</span><span class="value address">{{ detail.address }}</span></div>
        <div v-if="detail.risk_score" class="entity-row"><span class="label">风险评分</span><span class="value">{{ detail.risk_score }}</span></div>
        <div v-if="detail.description" class="entity-row"><span class="label">描述</span><span class="value">{{ detail.description }}</span></div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EntityPopoverState } from './useEntityPopover'

const props = defineProps<{
  popover: EntityPopoverState
}>()

const emit = defineEmits<{
  (e: 'enter'): void
  (e: 'leave'): void
}>()

const detail = computed(() => props.popover.entityData?.detail || {})

function onPopoverEnter() { emit('enter') }
function onPopoverLeave() { emit('leave') }

function riskLabel(level: string): string {
  return { high: '高风险', medium: '中风险', low: '低风险' }[level] || level
}

function typeLabel(t: string): string {
  return { enterprise: '企业', institution: '事业单位', organization: '社会组织' }[t] || t
}

function locationTypeLabel(t: string): string {
  return {
    community: '社区', school: '学校', hospital: '医院',
    enterprise: '企业', government: '政府机关', other: '其他',
  }[t] || t
}

function formatCapital(val: number): string {
  if (val >= 10000) return (val / 10000).toFixed(2) + '万元'
  return val.toFixed(2) + '元'
}
</script>

<style scoped lang="less">
.entity-popover {
  position: fixed;
  z-index: 1050;
  max-width: 400px;
  min-width: 260px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
  border: 1px solid #e8e8e8;
  padding: 0;
  pointer-events: auto;
  overflow: hidden;
}

.entity-popover-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fafbfc;
  border-bottom: 1px solid #f0f0f0;
}

.entity-popover-title {
  font-size: 14px;
  font-weight: 700;
  color: #1a1a1a;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entity-type-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
  flex-shrink: 0;
}

.entity-badge { background: #e6f4ff; color: #1677ff; }
.person-badge { background: #f6ffed; color: #52c41a; }
.location-badge { background: #fff7e6; color: #fa8c16; }

.risk-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
  &.risk-high { background: #fff1f0; color: #f5222d; }
  &.risk-medium { background: #fffbe6; color: #faad14; }
  &.risk-low { background: #f6ffed; color: #52c41a; }
}

.entity-popover-body {
  padding: 10px 14px;
  max-height: 280px;
  overflow-y: auto;
}

.entity-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  line-height: 1.6;

  &:not(:last-child) {
    border-bottom: 1px dashed #f5f5f5;
  }
}

.entity-row .label {
  color: #888;
  flex-shrink: 0;
  width: 70px;
  text-align: right;
}

.entity-row .value {
  color: #333;
  flex: 1;
  word-break: break-all;

  &.address, &.scope {
    font-size: 11px;
    color: #666;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &.tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  &.key-person {
    color: #f5222d;
    font-weight: 600;
  }
}
</style>
