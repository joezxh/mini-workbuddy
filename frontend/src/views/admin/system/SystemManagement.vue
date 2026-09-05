<template>
  <div class="system-management-container">
    <div class="panel-header">
      <h2 class="panel-title">系统管理</h2>
      <span class="panel-subtitle">集中管理系统权限架构与业务操作日志追溯</span>
    </div>

    <div class="content-wrapper">
      <a-tabs v-model:activeKey="activeTab" @change="onTabChange">
        <a-tab-pane key="users" :tab="t('sys.systemTabs.users')">
          <UserManager @view-logs="handleViewLogs" />
        </a-tab-pane>
        <a-tab-pane key="roles" :tab="t('sys.systemTabs.roles')">
          <RoleManager />
        </a-tab-pane>
        <a-tab-pane key="permissions" :tab="t('sys.systemTabs.permissions')">
          <PermissionManager />
        </a-tab-pane>
        <a-tab-pane key="tenants" :tab="t('sys.systemTabs.tenants')">
          <TenantPanel />
        </a-tab-pane>
        <a-tab-pane key="tenant-packages" :tab="t('sys.systemTabs.tenantPackages')">
          <TenantPackagePanel />
        </a-tab-pane>
        <a-tab-pane key="audit-logs" :tab="t('sys.systemTabs.auditLogs')">
          <AuditLogManager :filter-user-id="selectedUserId" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import UserManager from './components/UserManager.vue'
import RoleManager from './components/RoleManager.vue'
import PermissionManager from './components/PermissionManager.vue'
import AuditLogManager from './components/AuditLogManager.vue'
import TenantPanel from './TenantPanel.vue'
import TenantPackagePanel from './TenantPackagePanel.vue'

const { t } = useI18n()
const activeTab = ref('users')
const selectedUserId = ref<number | null>(null)

const handleViewLogs = (userId: number) => {
  selectedUserId.value = userId
  activeTab.value = 'audit-logs'
}

const onTabChange = () => {
  if (activeTab.value !== 'audit-logs') {
    selectedUserId.value = null
  }
}
</script>

<style lang="less" scoped>
.system-management-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  margin-bottom: 24px;
}

.panel-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--fg);
  margin: 0 0 8px 0;
}

.panel-subtitle {
  font-size: 14px;
  color: var(--fg-secondary);
}

.content-wrapper {
  flex: 1;
  background: var(--bg-surface);
  backdrop-filter: blur(2px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  overflow: auto;
}

/* 深色皮肤下，选中 Tab 仅加粗并使用主题强调色，避免深色配色导致白字不可读 */
.system-management-container :deep(.ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) {
  font-weight: 700;
  color: var(--accent);
}
.system-management-container :deep(.ant-tabs-tab-btn) {
  color: var(--fg-secondary);
}
.system-management-container :deep(.ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn):hover {
  color: var(--accent);
}
</style>
