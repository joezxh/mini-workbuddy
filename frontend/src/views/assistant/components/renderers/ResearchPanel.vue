<template>
  <div class="research-panel">
    <div class="rp-header">
      <span class="rp-icon"><SearchOutlined /></span>
      <span class="rp-title">深度研究中</span>
      <span class="rp-stage">{{ stageLabel }}</span>
      <span class="rp-percent">{{ progress }}%</span>
    </div>
    <a-progress :percent="progress" :show-info="false" size="small" stroke-color="#1677ff" />
    <div class="rp-list">
      <div v-for="q in plan" :key="q.id" class="rp-item" :class="'st-'+q.status">
        <span class="rp-dot">
          <LoadingOutlined v-if="q.status==='searching'" spin />
          <CheckCircleOutlined v-else-if="q.status==='done'" />
          <CloseCircleOutlined v-else-if="q.status==='failed'" />
          <ClockCircleOutlined v-else />
        </span>
        <div class="rp-q">
          <div class="rp-q-text">{{ q.question }}</div>
          <div class="rp-q-meta" v-if="q.sources.length">
            <span class="rp-src-count">{{ q.sources.length }} 个来源</span>
            <span v-for="s in q.sources.slice(0,3)" :key="s.url" class="rp-src">
              <a :href="s.url" target="_blank" rel="noopener">{{ s.title || s.url }}</a>
              <a-tag size="small" :color="credColor(s.credibility)">可信度 {{ Math.round(s.credibility*100) }}%</a-tag>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  SearchOutlined, LoadingOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons-vue'
import type { ResearchSubQuestion } from './../types'

const props = defineProps<{
  plan: ResearchSubQuestion[]
  stage?: string
  progress?: number
  active?: boolean
}>()

const stageLabel = computed(() => {
  const map: Record<string, string> = {
    decompose: '拆解主题', search: '检索资料', evaluate: '评估可信度', synthesize: '生成报告', done: '完成',
  }
  return map[props.stage || ''] || props.stage || '进行中'
})
function credColor(c: number) {
  if (c >= 0.8) return 'green'
  if (c >= 0.6) return 'blue'
  return 'orange'
}
</script>

<style scoped lang="less">
.research-panel {
  border: 1px solid #e6e8eb; border-radius: 10px; background: #fff; padding: 12px 14px;
}
.rp-header { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #333; margin-bottom: 8px; }
.rp-icon { color: #1677ff; }
.rp-stage { color: #888; font-weight: 400; }
.rp-percent { margin-left: auto; color: #1677ff; }
.rp-list { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
.rp-item { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; }
.rp-dot { margin-top: 2px; color: #999; }
.rp-item.st-searching .rp-dot { color: #1677ff; }
.rp-item.st-done .rp-dot { color: #52c41a; }
.rp-item.st-failed .rp-dot { color: #ff4d4f; }
.rp-q-text { color: #333; line-height: 1.5; }
.rp-q-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 3px; align-items: center; }
.rp-src-count { font-size: 11px; color: #999; }
.rp-src { font-size: 11px; display: inline-flex; align-items: center; gap: 4px; }
</style>
