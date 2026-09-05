<template>
  <div class="unified-timeline" v-if="steps.length || artifacts.length">
    <!-- 步骤时间线 -->
    <div class="ut-section" v-if="steps.length">
      <div class="ut-section-title">
        <span class="ut-dot ut-dot-steps"></span>执行步骤 ({{ steps.length }})
      </div>
      <ul class="ut-steps">
        <li
          v-for="s in orderedSteps"
          :key="s.seq"
          class="ut-step"
          :class="`ut-step-${s.status}`"
        >
          <span class="ut-step-bar"></span>
          <div class="ut-step-body">
            <div class="ut-step-head">
              <span class="ut-step-phase">{{ s.phase }}</span>
              <span class="ut-step-title">{{ s.title }}</span>
              <span class="ut-step-status" :class="`st-${s.status}`">{{ statusText(s.status) }}</span>
            </div>
            <div class="ut-step-detail" v-if="s.detail">{{ s.detail }}</div>
          </div>
        </li>
      </ul>
    </div>

    <!-- 产物画廊 -->
    <div class="ut-section" v-if="artifacts.length">
      <div class="ut-section-title">
        <span class="ut-dot ut-dot-arts"></span>产物 ({{ artifacts.length }})
      </div>
      <div class="ut-artifacts">
        <div
          v-for="a in artifacts"
          :key="a.artifact_id"
          class="ut-artifact"
          :class="`ut-artifact-${a.kind}`"
        >
          <div class="ut-artifact-head">
            <component :is="iconFor(a)" class="ut-artifact-icon" />
            <span class="ut-artifact-title" :title="a.title">{{ a.title }}</span>
            <span class="ut-artifact-status" :class="`st-${a.status}`">{{ statusText(a.status) }}</span>
          </div>

          <!-- 表格类产物 -->
          <div class="ut-artifact-table" v-if="a.kind === 'chart' && a.chart_config?.type === 'table'">
            <table v-if="a.chart_config.records?.length">
              <thead>
                <tr>
                  <th v-for="(h, hi) in tableColumns(a.chart_config.records)" :key="hi">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in a.chart_config.records.slice(0, 20)" :key="ri">
                  <td v-for="(h, hi) in tableColumns(a.chart_config.records)" :key="hi">{{ row[h] }}</td>
                </tr>
              </tbody>
            </table>
            <div class="ut-artifact-sql" v-if="a.chart_config.sql">
              <pre>{{ a.chart_config.sql }}</pre>
            </div>
            <span class="ut-artifact-meta" v-if="a.chart_config.total">共 {{ a.chart_config.total }} 条记录</span>
          </div>

          <!-- 图表类产物（ECharts 配置预览，前端按需渲染） -->
          <div class="ut-artifact-chart" v-else-if="a.kind === 'chart'">
            <span class="ut-artifact-meta">{{ a.chart_config?.title || '图表' }}（{{ a.chart_config?.type }}）</span>
          </div>

          <!-- 报告类（内嵌 markdown 文本） -->
          <div class="ut-artifact-report" v-else-if="a.media_data">
            <pre class="ut-artifact-md">{{ truncate(a.media_data) }}</pre>
          </div>

          <div class="ut-artifact-actions">
            <a-button
              size="small"
              type="link"
              v-if="a.kind === 'file' && a.file_id"
              @click="handleDownload(a)"
            >
              <DownloadOutlined /> 下载
            </a-button>
            <a-button size="small" type="link" v-if="a.error" disabled>{{ a.error }}</a-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  FileTextOutlined,
  FileImageOutlined,
  VideoCameraOutlined,
  BarChartOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import { computed } from 'vue'
import type { UnifiedStep, UnifiedArtifact } from './types'
import { artifactDownloadUrl } from '@/api/skill'

const props = withDefaults(
  defineProps<{
    steps?: UnifiedStep[]
    artifacts?: UnifiedArtifact[]
  }>(),
  {
    steps: () => [],
    artifacts: () => [],
  },
)

const orderedSteps = computed(() =>
  [...(props.steps || [])].sort((a, b) => a.seq - b.seq),
)

function statusText(s: string): string {
  return { running: '执行中', done: '完成', failed: '失败', warn: '提醒' }[s] || s
}

function iconFor(a: UnifiedArtifact) {
  if (a.kind === 'image') return FileImageOutlined
  if (a.kind === 'video') return VideoCameraOutlined
  if (a.kind === 'chart') return BarChartOutlined
  return FileTextOutlined
}

function tableColumns(records: any[]): string[] {
  const rec = records[0] || {}
  return Object.keys(rec)
}

function truncate(text: string, max = 600): string {
  return text.length > max ? text.slice(0, max) + '…（已截断预览，可下载完整文件）' : text
}

function handleDownload(a: UnifiedArtifact) {
  const url = artifactDownloadUrl(a.file_id!)
  const token = localStorage.getItem('token')
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then(r => r.blob())
    .then(blob => {
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = a.title || 'download'
      link.click()
      URL.revokeObjectURL(link.href)
    })
}
</script>

<style scoped>
.unified-timeline { margin: 8px 0; }
.ut-section { margin-bottom: 10px; }
.ut-section-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px;
}
.ut-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.ut-dot-steps { background: #1890ff; }
.ut-dot-arts { background: #52c41a; }

.ut-steps { list-style: none; margin: 0; padding: 0 0 0 4px; }
.ut-step { position: relative; padding: 0 0 10px 18px; }
.ut-step-bar {
  position: absolute; left: 4px; top: 4px; bottom: -4px;
  width: 2px; background: #e8e8e8;
}
.ut-step:last-child .ut-step-bar { display: none; }
.ut-step-body { position: relative; }
.ut-step-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ut-step-phase {
  font-size: 11px; color: #fff; background: #1890ff;
  border-radius: 3px; padding: 0 6px; line-height: 18px;
}
.ut-step-title { font-size: 13px; color: #333; }
.ut-step-status { font-size: 11px; margin-left: auto; }
.st-done { color: #52c41a; }
.st-running { color: #1890ff; }
.st-failed { color: #f5222d; }
.st-warn { color: #faad14; }
.ut-step-detail {
  font-size: 12px; color: #888; margin-top: 2px;
  background: #f7f7f7; border-radius: 4px; padding: 4px 8px;
  max-height: 80px; overflow: auto; white-space: pre-wrap;
}

.ut-artifacts { display: flex; flex-direction: column; gap: 8px; }
.ut-artifact {
  border: 1px solid #eef0f2; border-radius: 6px; padding: 8px 10px; background: #fafcff;
}
.ut-artifact-head { display: flex; align-items: center; gap: 8px; }
.ut-artifact-icon { color: #1890ff; flex-shrink: 0; }
.ut-artifact-title {
  font-size: 13px; color: #333; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ut-artifact-table { margin-top: 6px; overflow: auto; max-height: 220px; }
.ut-artifact-table table { border-collapse: collapse; width: 100%; font-size: 12px; }
.ut-artifact-table th, .ut-artifact-table td {
  border: 1px solid #eee; padding: 3px 6px; text-align: left; max-width: 200px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ut-artifact-sql {
  margin-top: 6px; background: #1e1e1e; color: #d4d4d4;
  border-radius: 4px; padding: 6px 8px; font-size: 11px; overflow: auto;
}
.ut-artifact-sql pre { margin: 0; white-space: pre-wrap; }
.ut-artifact-meta { font-size: 11px; color: #999; margin-left: 6px; }
.ut-artifact-report { margin-top: 6px; }
.ut-artifact-md {
  background: #fff; border: 1px solid #f0f0f0; border-radius: 4px;
  padding: 8px; font-size: 12px; color: #444; max-height: 200px; overflow: auto;
  white-space: pre-wrap; margin: 0;
}
.ut-artifact-actions { margin-top: 6px; }
</style>
