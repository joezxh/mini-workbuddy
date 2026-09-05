<template>
  <div class="system-management-container">
    <div class="panel-header">
      <h2 class="panel-title">系统管理</h2>
      <span class="panel-subtitle">集中管理系统权限架构与业务操作日志追溯</span>
    </div>

    <div class="content-wrapper">
      <a-tabs v-model:activeKey="activeTab" @change="onTabChange">
        <a-tab-pane key="users" tab="用户管理">
          <UserManager @view-logs="handleViewLogs" />
        </a-tab-pane>
        <a-tab-pane key="roles" tab="角色管理">
          <RoleManager />
        </a-tab-pane>
        <a-tab-pane key="permissions" tab="菜单管理">
          <PermissionManager />
        </a-tab-pane>
        <a-tab-pane key="tenants" tab="租户管理">
          <TenantPanel />
        </a-tab-pane>
        <a-tab-pane key="tenant-packages" tab="租户套餐">
          <TenantPackagePanel />
        </a-tab-pane>
        <a-tab-pane key="audit-logs" tab="审查日志管理">
          <AuditLogManager :filter-user-id="selectedUserId" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UserManager from './components/UserManager.vue'
import RoleManager from './components/RoleManager.vue'
import PermissionManager from './components/PermissionManager.vue'
import AuditLogManager from './components/AuditLogManager.vue'
import TenantPanel from './TenantPanel.vue'
import TenantPackagePanel from './TenantPackagePanel.vue'

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
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.panel-subtitle {
  font-size: 14px;
  color: #555555;
}

.content-wrapper {
  flex: 1;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(2px);
  border: 1px solid var(--border-glow);
  border-radius: 4px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  overflow: auto;
}
</style>
