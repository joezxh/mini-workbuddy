<template>
  <div class="report">
    <section class="rp-section">
      <header class="rp-h" @click="toggle('summary')">
        <span>📌 摘要</span><CaretDownOutlined class="rp-caret" :class="{ collapsed: !open.summary }" />
      </header>
      <div v-show="open.summary" class="rp-body" v-html="md.render(report.summary)"></div>
    </section>

    <section class="rp-section">
      <header class="rp-h" @click="toggle('findings')">
        <span>🔑 关键发现</span><CaretDownOutlined class="rp-caret" :class="{ collapsed: !open.findings }" />
      </header>
      <div v-show="open.findings" class="rp-body">
        <ul class="rp-findings">
          <li v-for="(f, i) in report.keyFindings" :key="i">{{ f }}</li>
        </ul>
      </div>
    </section>

    <section class="rp-section">
      <header class="rp-h" @click="toggle('analysis')">
        <span>📝 详细分析</span><CaretDownOutlined class="rp-caret" :class="{ collapsed: !open.analysis }" />
      </header>
      <div v-show="open.analysis" class="rp-body" v-html="md.render(report.analysis)"></div>
    </section>

    <section class="rp-section">
      <header class="rp-h" @click="toggle('sources')">
        <span>🔗 引用来源</span><CaretDownOutlined class="rp-caret" :class="{ collapsed: !open.sources }" />
      </header>
      <div v-show="open.sources" class="rp-body">
        <ul class="rp-sources">
          <li v-for="(s, i) in report.sources" :key="i">
            <a :href="s.url" target="_blank" rel="noopener">{{ s.title || s.url }}</a>
            <a-tag size="small" :color="credColor(s.credibility)">可信度 {{ Math.round(s.credibility * 100) }}%</a-tag>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { CaretDownOutlined } from '@ant-design/icons-vue'
import MarkdownIt from 'markdown-it'
import type { ResearchReport } from './../types'

defineProps<{ report: ResearchReport }>()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

// 默认仅展开摘要与关键发现
const open = reactive({ summary: true, findings: true, analysis: false, sources: false })
function toggle(k: keyof typeof open) { open[k] = !open[k] }
function credColor(c: number) {
  if (c >= 0.8) return 'green'
  if (c >= 0.6) return 'blue'
  return 'orange'
}
</script>

<style scoped lang="less">
.report { border: 1px solid #e6e8eb; border-radius: 10px; overflow: hidden; background: #fff; }
.rp-section { border-top: 1px solid #f0f0f0; &:first-child { border-top: none; } }
.rp-h {
  display: flex; align-items: center; justify-content: space-between; padding: 10px 14px;
  font-size: 14px; font-weight: 600; color: #1a1a1a; cursor: pointer; background: #fafbfc;
}
.rp-caret { transition: transform .2s; &.collapsed { transform: rotate(-90deg); } }
.rp-body { padding: 10px 14px; font-size: 13.5px; line-height: 1.7; color: #333; }
.rp-body :deep(p) { margin: 0 0 8px; }
.rp-findings, .rp-sources { margin: 0; padding-left: 18px; }
.rp-findings li { margin-bottom: 6px; }
.rp-sources li { margin-bottom: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
</style>
