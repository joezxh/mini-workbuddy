<template>
  <div class="workflow-management">
    <a-tabs v-model:activeKey="activeTab" type="card">
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
