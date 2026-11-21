<script setup lang="ts">
// 执行参数：对齐原型 page-config-exec 的展示态页面。
import { ref } from 'vue'

const maxIters = ref(5)
const isolation = ref('PER_TICKET')
const chunk = ref(4)
const timeout = ref(120)
const permission = ref('confirm')
</script>

<template>
  <div class="sa-cfg">
    <div class="sa-page-head">
      <h1>⚙️ 执行参数</h1>
      <p>Worker / GoalPipeline 执行参数 — 与 Workspace 绑定，控制迭代、隔离与确认策略</p>
    </div>

    <div class="sa-note-ok">
      ✅ <b>零新表设计</b>：执行参数存于 <code>sa_workspace_config.exec_params</code>，Worker 启动时载入只读副本。
    </div>

    <div class="sa-card cfg-card">
      <div class="cfg-title">🏢 电商营销工作空间 · 执行参数</div>
      <a-row :gutter="16">
        <a-col :span="8"><label>max_iters（GoalPipeline）</label><a-input-number v-model:value="maxIters" :min="1" :max="20" style="width: 100%" /></a-col>
        <a-col :span="8"><label>stream_batch_sentences（TTS chunk）</label><a-input-number v-model:value="chunk" :min="1" :max="10" style="width: 100%" /></a-col>
        <a-col :span="8"><label>单 Ticket 超时（秒）</label><a-input-number v-model:value="timeout" :min="30" style="width: 100%" /></a-col>
      </a-row>
      <a-row :gutter="16">
        <a-col :span="8">
          <label>AgentScope 隔离粒度</label>
          <a-select v-model:value="isolation" style="width: 100%">
            <a-select-option value="PER_TICKET">PER_TICKET（每 Ticket 独立）</a-select-option>
            <a-select-option value="PER_SESSION">PER_SESSION</a-select-option>
            <a-select-option value="PER_USER">PER_USER</a-select-option>
          </a-select>
        </a-col>
        <a-col :span="8">
          <label>default_permission</label>
          <a-select v-model:value="permission" style="width: 100%">
            <a-select-option value="confirm">confirm（默认需确认）</a-select-option>
            <a-select-option value="auto">auto（自动执行）</a-select-option>
            <a-select-option value="deny">deny（默认拒绝）</a-select-option>
          </a-select>
        </a-col>
      </a-row>
    </div>

    <div class="sa-note-demo">👀 展示态：执行参数写入端点待后端开放，表单当前仅呈现原型配置语义。</div>
  </div>
</template>

<style scoped lang="less">
@import '../manage-shared.less';
</style>
