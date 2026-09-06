<template>
  <div class="profile-panel">
    <div class="panel-header">
      <h2 class="panel-title">{{ t('sys.profile.title') }}</h2>
      <span class="panel-subtitle">{{ t('sys.profile.subtitle') }}</span>
    </div>

    <div class="profile-content">
      <!-- 头像区域 -->
      <div class="avatar-section">
        <a-avatar :size="100" :style="{ backgroundColor: 'var(--accent)', fontSize: '36px' }">
          {{ userInfo?.realName?.charAt(0) || 'U' }}
        </a-avatar>
        <a-button type="link" @click="handleUploadAvatar">{{ t('sys.profile.changeAvatar') }}</a-button>
      </div>

      <!-- 基本信息表单 -->
      <div class="form-section">
        <a-form
          :model="formData"
          :label-col="{ span: 4 }"
          :wrapper-col="{ span: 16 }"
        >
          <a-form-item :label="t('sys.profile.labelUsername')">
            <a-input v-model:value="formData.username" disabled />
          </a-form-item>

          <a-form-item :label="t('sys.profile.labelRealName')">
            <a-input v-model:value="formData.realName" />
          </a-form-item>

          <a-form-item :label="t('sys.profile.labelPhone')">
            <a-input v-model:value="formData.phone" />
          </a-form-item>

          <a-form-item :label="t('sys.profile.labelEmail')">
            <a-input v-model:value="formData.email" />
          </a-form-item>

          <a-form-item :label="t('sys.profile.labelRole')">
            <a-tag v-for="role in (userInfo?.roles || [])" :key="role" color="blue">
              {{ role }}
            </a-tag>
          </a-form-item>

          <a-form-item :wrapper-col="{ offset: 4, span: 16 }">
            <a-space>
              <a-button type="primary" @click="handleSave">{{ t('sys.profile.saveChanges') }}</a-button>
              <a-button @click="handleReset">{{ t('sys.profile.reset') }}</a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </div>

      <!-- 修改密码 -->
      <div class="password-section">
        <h3 class="section-title">{{ t('sys.profile.passwordSection') }}</h3>
        <a-form
          :model="passwordForm"
          :label-col="{ span: 4 }"
          :wrapper-col="{ span: 16 }"
        >
          <a-form-item :label="t('sys.profile.labelOldPassword')">
            <a-input-password v-model:value="passwordForm.oldPassword" />
          </a-form-item>

          <a-form-item :label="t('sys.profile.labelNewPassword')">
            <a-input-password v-model:value="passwordForm.newPassword" />
          </a-form-item>

          <a-form-item :label="t('sys.profile.labelConfirmPassword')">
            <a-input-password v-model:value="passwordForm.confirmPassword" />
          </a-form-item>

          <a-form-item :wrapper-col="{ offset: 4, span: 16 }">
            <a-button type="primary" @click="handleChangePassword">{{ t('sys.profile.changePassword') }}</a-button>
          </a-form-item>
        </a-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { useUserStore } from '@/stores/user'
import { updateUser, changePassword } from '@/api/admin'

const { t } = useI18n()
const userStore = useUserStore()
const userInfo = ref<any>(userStore.userInfo || {})

const formData = reactive({
  username: '',
  realName: '',
  phone: '',
  email: '',
  regionName: ''
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

onMounted(() => {
  formData.username = userInfo.value?.username || ''
  formData.realName = userInfo.value?.realName || ''
  formData.phone = userInfo.value?.phone || ''
  formData.email = userInfo.value?.email || ''
  formData.regionName = userInfo.value?.regionName || ''
})

const handleUploadAvatar = () => {
  message.info(t('sys.profile.avatarUploading'))
}

const handleSave = async () => {
  try {
    const userId = userInfo.value?.userId || userInfo.value?.user_id || userInfo.value?.id
    if (!userId) {
      message.error(t('sys.profile.invalidUserId'))
      return
    }
    const res = await updateUser(userId, {
      realName: formData.realName,
      phone: formData.phone,
      email: formData.email
    })
    if (res.code === 0) {
      message.success(t('sys.profile.saveSuccess'))
      userStore.fetchUserInfo()
    } else {
      message.error(res.message || t('sys.profile.saveFail'))
    }
  } catch (error) {
    message.error(t('sys.profile.requestError'))
  }
}

const handleReset = () => {
  formData.realName = userInfo.value?.realName || ''
  formData.phone = userInfo.value?.phone || ''
  formData.email = userInfo.value?.email || ''
  message.info(t('sys.profile.resetSuccess'))
}

const handleChangePassword = async () => {
  if (!passwordForm.oldPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
    message.warning(t('sys.profile.fillPasswordRequired'))
    return
  }
  if (passwordForm.newPassword.length < 8) {
    message.warning(t('sys.profile.passwordTooShort'))
    return
  }
  
  const strengthPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d\W]{8,}$/
  if (!strengthPattern.test(passwordForm.newPassword)) {
    message.warning(t('sys.profile.passwordWeak'))
    return
  }
  
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    message.error(t('sys.profile.passwordMismatch'))
    return
  }
  
  try {
    const userId = userInfo.value?.userId || userInfo.value?.user_id || userInfo.value?.id
    if (!userId) {
      message.error(t('sys.profile.invalidUserId'))
      return
    }
    
    const res = await changePassword(userId, passwordForm.oldPassword, passwordForm.newPassword)
    
    if (res.code === 0) {
      message.success(t('sys.profile.passwordChangeSuccess'))
      passwordForm.oldPassword = ''
      passwordForm.newPassword = ''
      passwordForm.confirmPassword = ''
      setTimeout(() => {
        userStore.logout()
        window.location.href = '/login'
      }, 1500)
    } else {
      message.error(res.message || t('sys.profile.passwordChangeFail'))
    }
  } catch (error: any) {
    message.error(error?.response?.data?.message || error?.message || t('sys.profile.networkError'))
  }
}
</script>

<style lang="less" scoped>
.profile-panel {
  width: 100%;
  height: 100%;
  overflow-y: auto;
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

.profile-content {
  background: var(--bg-surface);
  backdrop-filter: blur(2px);
  border: 1px solid var(--border-glow);
  border-radius: 4px;
  padding: 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--border-glow);
  margin-bottom: 32px;
}

.form-section {
  margin-bottom: 32px;
}

.password-section {
  padding-top: 32px;
  border-top: 1px solid var(--border-glow);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--fg);
  margin: 0 0 24px 0;
}
</style>
