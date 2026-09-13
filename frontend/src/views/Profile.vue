<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { LOCALE_OPTIONS } from '@/i18n'
import { BellOutlined, CheckOutlined } from '@ant-design/icons-vue'
import {
  getNotifications, markNotificationsRead, cleanExpiredNotifications,
  type NotificationItem,
} from '@/api/notification'
import { getAvailableModels, type AvailableModel } from '@/api/ai-apikey'
import ApiKeyManagement from '@/views/admin/ai/apikey/ApiKeyManagement.vue'
import { message } from 'ant-design-vue'

const userStore = useUserStore()
const appStore = useAppStore()
const { t } = useI18n()
const activeTab = ref('profile')

const loading = ref(false)
const passwordFormRef = ref()
const passwordState = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

function validateConfirmPassword(_rule: unknown, val: string): Promise<void> {
  if (val !== passwordState.value.newPassword) {
    return Promise.reject(t('profile.passwordMismatch'))
  }
  return Promise.resolve()
}

const handlePasswordChange = async () => {
  try {
    await passwordFormRef.value.validate()
    loading.value = true
    await userStore.changePassword({
      old_password: passwordState.value.oldPassword,
      new_password: passwordState.value.newPassword,
    })
  } finally {
    loading.value = false
  }
}

// ── 我的模型模块 ───────────────────────────────────────────
const modelsLoading = ref(false)
const availableModels = ref<AvailableModel[]>([])
const modelColumns = [
  { title: t('profile.colModelName'), dataIndex: 'name', key: 'name', width: 160, ellipsis: true },
  { title: t('profile.colModelId'), dataIndex: 'model', key: 'model', width: 200, ellipsis: true },
  { title: t('profile.colPlatform'), dataIndex: 'platform', key: 'platform', width: 120, align: 'center' as const },
  { title: t('profile.colKeyName'), dataIndex: 'key_name', key: 'key_name', width: 160, ellipsis: true },
  { title: t('profile.colType'), dataIndex: 'type', key: 'type', width: 80, align: 'center' as const },
]
async function loadModels() {
  modelsLoading.value = true
  try {
    availableModels.value = await getAvailableModels()
  } catch (e: any) {
    message.error(e.message || t('profile.loadModelsFailed'))
  } finally {
    modelsLoading.value = false
  }
}

// ── 站内通知模块 ───────────────────────────────────────────
const notifOpen = ref(false)
const notifList = ref<NotificationItem[]>([])
const notifTotal = ref(0)
const notifUnread = ref(0)
const notifPage = ref(1)
const notifSize = ref(10)
const notifLoading = ref(false)

async function loadNotifications() {
  notifLoading.value = true
  try {
    const res = await getNotifications({ page: notifPage.value, size: notifSize.value })
    notifList.value = res.items
    notifTotal.value = res.total
    notifUnread.value = res.unread
  } finally {
    notifLoading.value = false
  }
}
function openNotif() {
  notifOpen.value = true
  notifPage.value = 1
  loadNotifications()
}
async function markAllRead() {
  await markNotificationsRead()
  message.success(t('profile.markAllRead'))
  await loadNotifications()
}
async function markOneRead(id: number) {
  await markNotificationsRead([id])
  await loadNotifications()
}
async function cleanExpired() {
  const res = await cleanExpiredNotifications()
  message.success(t('profile.clearedNotifications', { count: res.removed }))
  await loadNotifications()
}
onMounted(() => {
  loadNotifications()
  loadModels()
})

</script>

<template>
  <div class="profile-container">
    <!-- 通知入口：未读角标 -->
    <div class="notif-trigger" @click="openNotif">
      <a-badge :count="notifUnread" :offset="[-2, 4]">
        <a-button shape="circle" size="large"><BellOutlined /></a-button>
      </a-badge>
    </div>

    <a-tabs v-model:activeKey="activeTab" class="profile-tabs">
      <a-tab-pane key="profile" :tab="t('profile.tabProfile')">
        <a-row :gutter="[24, 24]">
      <a-col :xs="24" :lg="8">
        <!-- User Info Card -->
        <a-card :title="t('profile.cardTitle')" :bordered="false">
          <div class="user-info">
            <a-avatar :size="80" class="user-avatar">
              {{ userStore.userInfo?.realName?.charAt(0) || 'U' }}
            </a-avatar>
            <h3 class="user-name">{{ userStore.userInfo?.realName }}</h3>
            <p class="user-role">{{ userStore.userInfo?.roles?.[0] || t('profile.defaultRole') }}</p>
          </div>

          <a-divider />

          <div class="info-list">
            <div class="info-item">
              <UserOutlined class="info-icon" />
              <span class="info-label">{{ t('profile.labelUsername') }}</span>
              <span class="info-value">{{ userStore.userInfo?.username }}</span>
            </div>
            <div class="info-item">
              <MailOutlined class="info-icon" />
              <span class="info-label">{{ t('profile.labelEmail') }}</span>
              <span class="info-value">{{ userStore.userInfo?.email || '-' }}</span>
            </div>
            <div class="info-item">
              <PhoneOutlined class="info-icon" />
              <span class="info-label">{{ t('profile.labelPhone') }}</span>
              <span class="info-value">{{ userStore.userInfo?.phone || '-' }}</span>
            </div>
            <div class="info-item">
              <CalendarOutlined class="info-icon" />
              <span class="info-label">{{ t('profile.labelRegisterTime') }}</span>
              <span class="info-value">{{ userStore.userInfo?.createTime || '-' }}</span>
            </div>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :lg="16">
        <!-- Settings Card -->
        <a-card :title="t('profile.cardChangePassword')" :bordered="false">
          <a-form
            ref="passwordFormRef"
            :model="passwordState"
            layout="vertical"
            @finish="handlePasswordChange"
          >
            <a-form-item
              :label="t('profile.labelOldPassword')"
              name="oldPassword"
              :rules="[{ required: true, message: t('profile.oldPasswordRequired') }]"
            >
              <a-input-password v-model:value="passwordState.oldPassword" />
            </a-form-item>

            <a-form-item
              :label="t('profile.labelNewPassword')"
              name="newPassword"
              :rules="[
                { required: true, message: t('profile.newPasswordRequired') },
                { min: 6, message: t('profile.passwordMinLength') },
              ]"
            >
              <a-input-password v-model:value="passwordState.newPassword" />
            </a-form-item>

            <a-form-item
              :label="t('profile.labelConfirmPassword')"
              name="confirmPassword"
              :rules="[
                { required: true, message: t('profile.confirmPasswordRequired') },
                { validator: validateConfirmPassword, trigger: 'change' },
              ]"
            >
              <a-input-password v-model:value="passwordState.confirmPassword" />
            </a-form-item>

            <a-form-item>
              <a-button type="primary" html-type="submit" :loading="loading">
                {{ t('common.save') }}
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>

        <!-- Preferences Card -->
        <a-card :title="t('profile.cardPreferences')" :bordered="false" class="mt-16">
          <a-form layout="vertical">
            <a-form-item :label="t('profile.uiLanguage')">
              <a-select :value="appStore.locale" @change="(v: any) => appStore.setAppLocale(v)">
                <a-select-option v-for="opt in LOCALE_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item :label="t('profile.cardTheme')">
              <a-radio-group default-value="light">
                <a-radio value="light">{{ t('profile.themeLight') }}</a-radio>
                <a-radio value="dark">{{ t('profile.themeDark') }}</a-radio>
                <a-radio value="auto">{{ t('profile.themeAuto') }}</a-radio>
              </a-radio-group>
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>
        </a-row>
      </a-tab-pane>

      <a-tab-pane key="models" :tab="t('profile.tabModels')">
        <a-card :bordered="false" :title="t('profile.modelsTitle')">
          <a-table
            :columns="modelColumns"
            :data-source="availableModels"
            :loading="modelsLoading"
            row-key="id"
            size="small"
            :pagination="{ pageSize: 10, showTotal: (total: number) => t('common.total', { total }) }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'type'">{{ record.type ?? '-' }}</template>
              <template v-else-if="column.key === 'platform'">
                <a-tag color="blue">{{ record.platform }}</a-tag>
              </template>
            </template>
            <template #emptyText>
              <a-empty :description="t('profile.modelsEmpty')" />
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="keys" :tab="t('profile.tabKeys')">
        <ApiKeyManagement />
      </a-tab-pane>
    </a-tabs>

    <!-- 通知抽屉 -->
    <a-drawer
      v-model:open="notifOpen"
      :title="t('profile.notificationTitle')"
      width="420"
      :footer="null"
    >
      <template #extra>
        <a-space>
          <a-button size="small" @click="markAllRead"><CheckOutlined /> {{ t('profile.markAllRead') }}</a-button>
          <a-button size="small" @click="cleanExpired">{{ t('profile.cleanExpired') }}</a-button>
        </a-space>
      </template>
      <a-spin :spinning="notifLoading">
        <a-list
          :data-source="notifList"
          :pagination="notifTotal > notifSize ? { current: notifPage, pageSize: notifSize, total: notifTotal, onChange: (p: number) => { notifPage = p; loadNotifications() } } : false"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta>
                <template #title>
                  <span :style="{ fontWeight: item.isRead ? 400 : 700 }">{{ item.title }}</span>
                  <a-tag v-if="!item.isRead" color="red" style="margin-left:8px">{{ t('profile.unread') }}</a-tag>
                </template>
                <template #description>
                  <div>{{ item.content }}</div>
                  <div style="font-size:12px;color:#999;margin-top:4px">{{ item.createdAt }}</div>
                </template>
              </a-list-item-meta>
              <template #actions>
                <a v-if="!item.isRead" @click="markOneRead(item.id)">{{ t('profile.markRead') }}</a>
              </template>
            </a-list-item>
          </template>
          <template #empty><a-empty :description="t('profile.noNotifications')" /></template>
        </a-list>
      </a-spin>
    </a-drawer>
  </div>
</template>

<style scoped>
.profile-container {
  padding: 0;
  position: relative;
}

.profile-tabs {
  margin-top: 8px;
}

.user-info {
  text-align: center;
  padding: 16px 0;
}

.user-avatar {
  background: var(--primary-color, #1677ff);
  margin-bottom: 16px;
}

.user-name {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 4px;
}

.user-role {
  color: #999;
  margin: 0;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-icon {
  color: #999;
}

.info-label {
  color: #666;
  min-width: 60px;
}

.info-value {
  color: #333;
}

.mt-16 {
  margin-top: 16px;
}

.notif-trigger {
  position: absolute;
  top: 16px;
  right: 24px;
  z-index: 10;
  cursor: pointer;
}
</style>
