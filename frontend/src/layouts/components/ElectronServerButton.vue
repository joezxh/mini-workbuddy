<script setup lang="ts">
// 桌面端专用：查看 / 修改后端服务地址。
//
// 浏览器部署时后端地址在构建期由 VITE_API_BASE_URL 决定，这里不渲染任何内容。
// 桌面端地址存在于主进程 userData/app-config.json，可在运行期修改，改完自动重载，
// 不需要重新打包安装包。
import { onMounted, ref } from 'vue'
import { ApiOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { isElectron } from '@/utils/electron'
import { getApiBase, getDesktopInfo, saveApiBase } from '@/utils/apiBase'

const props = withDefaults(defineProps<{ floating?: boolean }>(), { floating: false })

const visible = ref(false)
const saving = ref(false)
const apiBase = ref('')
const version = ref('')

onMounted(async () => {
  if (!isElectron) return
  apiBase.value = getApiBase()
  const info = await getDesktopInfo()
  if (info?.version) version.value = info.version
})

function open() {
  apiBase.value = getApiBase()
  visible.value = true
}

async function handleSave() {
  const next = apiBase.value.trim()
  if (!next) {
    message.warning('请填写后端服务地址')
    return
  }
  if (!/^https?:\/\//i.test(next)) {
    message.warning('地址需以 http:// 或 https:// 开头')
    return
  }
  saving.value = true
  try {
    await saveApiBase(next)
    message.success('已保存，正在重新加载…')
    setTimeout(() => window.location.reload(), 600)
  } catch (err) {
    console.error('[electron] 保存后端地址失败', err)
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <template v-if="isElectron">
    <button
      class="esb-btn"
      :class="{ 'esb-btn--float': props.floating }"
      type="button"
      title="后端服务地址"
      @click="open"
    >
      <ApiOutlined />
    </button>

    <a-modal
      v-model:open="visible"
      title="后端服务地址"
      ok-text="保存并重载"
      cancel-text="取消"
      :confirm-loading="saving"
      :width="460"
      @ok="handleSave"
    >
      <p class="esb-tip">
        桌面端连接的后端 API 根地址，保存在本机配置文件中，修改后立即生效。
      </p>
      <a-input
        v-model:value="apiBase"
        placeholder="例如 http://192.168.1.10:8000"
        allow-clear
        @press-enter="handleSave"
      />
      <p v-if="version" class="esb-meta">客户端版本 v{{ version }}</p>
    </a-modal>
  </template>
</template>

<style scoped>
.esb-btn {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--fg-secondary);
  cursor: pointer;
  font-size: 15px;
  transition: all var(--transition);
}

.esb-btn:hover {
  color: var(--accent);
  border-color: var(--border-strong);
  background: var(--bg-hover);
}

/* 登录页等没有顶栏的场景，退化成左下角悬浮入口，保证永远能改地址 */
.esb-btn--float {
  position: fixed;
  left: 16px;
  bottom: 16px;
  z-index: 1000;
  width: 30px;
  height: 30px;
  font-size: 13px;
  background: var(--bg-elevated);
  opacity: 0.65;
}

.esb-btn--float:hover {
  opacity: 1;
}

.esb-tip {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--fg-secondary);
  line-height: 1.6;
}

.esb-meta {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--fg-secondary);
}
</style>
