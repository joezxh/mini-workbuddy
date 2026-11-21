<script setup lang="ts">
// Policy 规则：对齐原型 page-config-policy 的展示态页面。
// 后端 superagent.py 未提供 workspace 级 policy 读写端点，此处按原型呈现配置语义并明确标注「展示态」。
import { ref } from 'vue'

const rules = ref(`{
  "source_whitelist": ["http", "manual", "playwright"],
  "sender_whitelist": ["user_admin", "user_ai_lead", "user_marketing_head"],
  "jev_confidence_threshold": 0.6,
  "proactive_auto_accept": true,
  "ignore_after_auto_drop": true
}`)
const confidence = ref(0.6)
const accept = ref(0.85)
const router = ref('jev-first')
</script>

<template>
  <div class="sa-cfg">
    <div class="sa-page-head">
      <h1>🛡️ Policy 规则</h1>
      <p>准入规则 · source 白名单 · Jev 决策阈值 — 每个 Workspace 独立配置，隔离执行</p>
    </div>

    <div class="sa-note-ok">
      ✅ <b>零新表设计</b>：Policy 规则存储于 <code>sa_workspace_config.policy_rules</code>（JSON 字段），Jev 阈值在 <code>jev_confidence_threshold</code> / <code>jev_accept_threshold</code>。
    </div>

    <div class="sa-card cfg-card">
      <div class="cfg-title">🏢 电商营销工作空间 · Policy 绑定</div>
      <div class="cfg-hint">当前 Workspace：<b class="peach">电商营销工作空间</b>（ws_emarketing_01）。切换 Workspace 后配置自动切换。</div>
      <label>policy_rules（JSON）</label>
      <a-textarea v-model:value="rules" :rows="8" readonly class="mono" />
    </div>

    <div class="sa-card cfg-card">
      <div class="cfg-title">🧠 Jev 准入决策</div>
      <div class="cfg-hint">score ≥ 阈值进入 pipeline，jev-first 拒答时回退 LLM。</div>
      <a-row :gutter="16">
        <a-col :span="8"><label>jev_confidence_threshold</label><a-input-number v-model:value="confidence" :min="0" :max="1" :step="0.05" /></a-col>
        <a-col :span="8"><label>jev_accept_threshold</label><a-input-number v-model:value="accept" :min="0" :max="1" :step="0.05" /></a-col>
        <a-col :span="8">
          <label>model_router</label>
          <a-select v-model:value="router" style="width: 100%">
            <a-select-option value="jev-first">jev-first（默认）</a-select-option>
            <a-select-option value="jev-only">jev-only</a-select-option>
            <a-select-option value="llm-only">llm-only</a-select-option>
          </a-select>
        </a-col>
      </a-row>
    </div>

    <div class="sa-note-demo">👀 展示态：当前后端未开放 workspace 级 Policy 读写端点，表单仅呈现原型配置语义，保存功能待后端接口就绪后接入。</div>
  </div>
</template>

<style scoped lang="less">
@import '../manage-shared.less';
</style>
