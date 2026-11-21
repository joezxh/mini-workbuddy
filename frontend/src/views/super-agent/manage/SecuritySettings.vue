<script setup lang="ts">
// 安全设置：对齐原型 page-config-security 的展示态页面。
import { ref } from 'vue'

const bearer = ref(true)
const audit = ref(true)
const sandbox = ref(true)
const whitelist = ref('127.0.0.1, localhost, *.internal.example.com')
</script>

<template>
  <div class="sa-cfg">
    <div class="sa-page-head">
      <h1>🔒 安全设置</h1>
      <p>Workspace 级安全边界 — 鉴权 · 审计 · 沙箱 · 网络白名单</p>
    </div>

    <div class="sa-note-ok">
      ✅ <b>隔离执行</b>：所有 Worker 在 per-Ticket <code>LocalWorkspace</code> 内运行，工具调用全程审计，敏感操作需 L3 人工确认。
    </div>

    <div class="sa-card cfg-card">
      <div class="cfg-title">🛡️ 执行安全策略</div>
      <div class="sec-row"><span>API Bearer 鉴权（superagent endpoints）</span><a-switch v-model:checked="bearer" /></div>
      <div class="sec-row"><span>全量操作审计日志（sa_audit_log）</span><a-switch v-model:checked="audit" /></div>
      <div class="sec-row"><span>工具沙箱隔离（bash / powershell）</span><a-switch v-model:checked="sandbox" /></div>
      <label>网络访问白名单（逗号分隔）</label>
      <a-textarea v-model:value="whitelist" :rows="3" />
    </div>

    <div class="sa-note-demo">👀 展示态：安全策略服务端强制项不由此前端开关决定，表单仅对齐原型呈现，实际生效以 Workspace 配置为为准。</div>
  </div>
</template>

<style scoped lang="less">
@import '../manage-shared.less';
.sec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px dashed var(--sa-border);
  font-size: 13px;
  color: var(--sa-text-2);
}
</style>
