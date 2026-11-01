<template>
  <div class="mask" :class="{ on: show }" v-if="show">
    <div class="modal" style="width:660px">
      <div class="mh">⇄ 分支对比 · 末态差异<div class="spacer"></div><span class="pill">{{ summary.length }} 个分支</span></div>
      <div class="mb">
        <table style="width:100%;border-collapse:collapse;font-size:11.5px;font-family:var(--mono)">
          <thead>
            <tr style="color:var(--fg3);text-align:left">
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">分支</th>
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">末 Tick</th>
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">末 health</th>
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">health Δ</th>
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">达成目标</th>
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">命中规则</th>
              <th style="padding:4px 8px;border-bottom:1px solid var(--divider)">行动数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in summary" :key="b.branch_id">
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider);color:var(--fg)">{{ b.name }}</td>
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider)">{{ b.final_tick }}</td>
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider)">{{ b.final_health ?? '—' }}</td>
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider)" :style="{ color: deltaColor(b.health_delta) }">{{ b.health_delta ?? '—' }}</td>
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider)">{{ b.goal_reached_count }}</td>
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider)">{{ b.rule_fired_count }}</td>
              <td style="padding:5px 8px;border-bottom:1px dashed var(--divider)">{{ b.action_count }}</td>
            </tr>
          </tbody>
        </table>
        <div class="note" style="font-size:10.5px;color:var(--fg3);margin-top:8px">
          health Δ 相对首个被选中分支的末态 health 计算；沙箱分支互不影响，可回放审计。
        </div>
      </div>
      <div class="mf"><button class="btn" @click="emit('close')">关闭</button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BranchSummary } from '@/api/sandbox'

// 分支对比模态：数据源为 compare() 返回的 branch_summary（G1 富差异表）。
defineProps<{
  show: boolean
  summary: BranchSummary[]
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const deltaColor = (d: string | null): string =>
  d == null ? 'var(--fg3)' : Number(d) > 0 ? 'var(--ok)' : Number(d) < 0 ? 'var(--err)' : 'var(--fg2)'
</script>
