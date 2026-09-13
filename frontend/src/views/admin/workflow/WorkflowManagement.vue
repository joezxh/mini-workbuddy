<template>
  <div class="workflow-management">
    <a-tabs v-model:activeKey="activeTab" class="workflow-tabs">
      <a-tab-pane key="flows" tab="工作流列表">
        <WorkflowFlowTable @edit="handleEdit" @test="handleTest" />
      </a-tab-pane>
      <a-tab-pane key="editor" tab="编辑器">
        <WorkflowFlowForm :initial="editingFlow" @saved="refreshFlows" />
      </a-tab-pane>
      <a-tab-pane key="test" tab="测试工作台">
        <WorkflowTestBench :flow-id="testingFlowId" />
      </a-tab-pane>
      <a-tab-pane key="logs" tab="执行日志">
        <WorkflowExecutionTable />
      </a-tab-pane>
      <a-tab-pane key="dashboard" tab="分析仪表板">
        <WorkflowDashboard />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import WorkflowFlowTable from './components/WorkflowFlowTable.vue'
import WorkflowFlowForm from './components/WorkflowFlowForm.vue'
import WorkflowTestBench from './components/WorkflowTestBench.vue'
import WorkflowExecutionTable from './components/WorkflowExecutionTable.vue'
import WorkflowDashboard from './components/WorkflowDashboard.vue'

const activeTab = ref('flows')
const editingFlow = ref<any>(null)
const testingFlowId = ref<number | null>(null)

function handleEdit(flow: any) {
  editingFlow.value = flow
  activeTab.value = 'editor'
}
function handleTest(flowId: number) {
  testingFlowId.value = flowId
  activeTab.value = 'test'
}
function refreshFlows() {
  activeTab.value = 'flows'
}
</script>

<style scoped>
/* 套用 skill 视图顶栏/tab 标题风格：56px 高 + 激活下划线（非 card） */
.workflow-tabs :deep(.ant-tabs-nav) {
  height: 56px;
  margin: 0;
  padding: 0 24px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}
.workflow-tabs :deep(.ant-tabs-nav::before) {
  border-bottom: none;
}
.workflow-tabs :deep(.ant-tabs-tab) {
  height: 56px;
  padding: 0 4px;
  margin-right: 20px;
  font-size: 14px;
  color: var(--fg-secondary);
  background: transparent;
  border: none;
}
.workflow-tabs :deep(.ant-tabs-tab:hover) {
  color: var(--accent);
}
.workflow-tabs :deep(.ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: var(--accent);
  font-weight: 600;
}
.workflow-tabs :deep(.ant-tabs-ink-bar) {
  background: var(--accent);
  height: 2px;
}
</style>
