<template>
  <div class="profile-panel">
    <div class="panel-header">
      <h2 class="panel-title">个人信息</h2>
      <span class="panel-subtitle">管理您的个人资料和账户设置</span>
    </div>

    <div class="profile-content">
      <!-- 头像区域 -->
      <div class="avatar-section">
        <a-avatar :size="100" :style="{ backgroundColor: '#1677ff', fontSize: '36px' }">
          {{ userInfo?.realName?.charAt(0) || 'U' }}
        </a-avatar>
        <a-button type="link" @click="handleUploadAvatar">更换头像</a-button>
      </div>

      <!-- 基本信息表单 -->
      <div class="form-section">
        <a-form
          :model="formData"
          :label-col="{ span: 4 }"
          :wrapper-col="{ span: 16 }"
        >
          <a-form-item label="用户名">
            <a-input v-model:value="formData.username" disabled />
          </a-form-item>

          <a-form-item label="真实姓名">
            <a-input v-model:value="formData.realName" />
          </a-form-item>

          <a-form-item label="手机号">
            <a-input v-model:value="formData.phone" />
          </a-form-item>

          <a-form-item label="邮箱">
            <a-input v-model:value="formData.email" />
          </a-form-item>

          <a-form-item label="角色">
            <a-tag v-for="role in (userInfo?.roles || [])" :key="role" color="blue">
              {{ role }}
            </a-tag>
          </a-form-item>

          <a-form-item :wrapper-col="{ offset: 4, span: 16 }">
            <a-space>
              <a-button type="primary" @click="handleSave">保存修改</a-button>
              <a-button @click="handleReset">重置</a-button>
            </a-space>
          </a-form-item>
        </a-form>
      </div>

      <!-- 修改密码 -->
      <div class="password-section">
        <h3 class="section-title">修改密码</h3>
        <a-form
          :model="passwordForm"
          :label-col="{ span: 4 }"
          :wrapper-col="{ span: 16 }"
        >
          <a-form-item label="当前密码">
            <a-input-password v-model:value="passwordForm.oldPassword" />
          </a-form-item>

          <a-form-item label="新密码">
            <a-input-password v-model:value="passwordForm.newPassword" />
          </a-form-item>

          <a-form-item label="确认密码">
            <a-input-password v-model:value="passwordForm.confirmPassword" />
          </a-form-item>

          <a-form-item :wrapper-col="{ offset: 4, span: 16 }">
            <a-button type="primary" @click="handleChangePassword">修改密码</a-button>
          </a-form-item>
        </a-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useUserStore } from '@/stores/user'
import { updateUser, changePassword } from '@/api/admin'

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
  message.info('头像上传功能开发中...')
}

const handleSave = async () => {
  try {
    const userId = userInfo.value?.userId || userInfo.value?.user_id || userInfo.value?.id
    if (!userId) {
      message.error('无法获取有效用户ID')
      return
    }
    const res = await updateUser(userId, {
      realName: formData.realName,
      phone: formData.phone,
      email: formData.email
    })
    if (res.code === 0) {
      message.success('个人信息保存成功')
      userStore.fetchUserInfo()
    } else {
      message.error(res.message || '保存失败')
    }
  } catch (error) {
    message.error('请求出错')
  }
}

const handleReset = () => {
  formData.realName = userInfo.value?.realName || ''
  formData.phone = userInfo.value?.phone || ''
  formData.email = userInfo.value?.email || ''
  message.info('已重置为原始信息')
}

const handleChangePassword = async () => {
  if (!passwordForm.oldPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
    message.warning('请填写完整的密码信息')
    return
  }
  if (passwordForm.newPassword.length < 8) {
    message.warning('新密码长度不能小于8位')
    return
  }
  
  const strengthPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d\W]{8,}$/
  if (!strengthPattern.test(passwordForm.newPassword)) {
    message.warning('密码强度较弱: 必须包含大小写字母和数字')
    return
  }
  
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    message.error('两次输入的新密码不一致')
    return
  }
  
  try {
    const userId = userInfo.value?.userId || userInfo.value?.user_id || userInfo.value?.id
    if (!userId) {
      message.error('无法获取有效用户ID')
      return
    }
    
    const res = await changePassword(userId, passwordForm.oldPassword, passwordForm.newPassword)
    
    // API throws 400 with "原密码不正确" natively handled or it returns {code: 400, message: ...}
    if (res.code === 0) {
      message.success('密码修改成功，请重新登录')
      passwordForm.oldPassword = ''
      passwordForm.newPassword = ''
      passwordForm.confirmPassword = ''
      setTimeout(() => {
        userStore.logout()
        window.location.href = '/login'
      }, 1500)
    } else {
      message.error(res.message || '修改密码失败')
    }
  } catch (error: any) {
    message.error(error?.response?.data?.message || error?.message || '网络请求出错')
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
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.panel-subtitle {
  font-size: 14px;
  color: #555555;
}

.profile-content {
  background: rgba(255, 255, 255, 0.9);
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
  color: #1a1a1a;
  margin: 0 0 24px 0;
}
</style>

