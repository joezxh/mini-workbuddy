import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import App from './App.vue'
import router from './router'
import { permissionDirective } from './directives/permission'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import autoScale from './directives/autoScale'
import i18n from './i18n'
import { useAppStore } from './stores/app'

dayjs.locale('zh-cn')

// 科技感字体。仅拉丁子集：Orbitron 与 Chakra Petch 不含中日韩字形，中文会
// 回退到 --font-* 中声明的系统字体栈（HarmonyOS Sans SC / PingFang SC /
// Microsoft YaHei）。
import '@fontsource/orbitron/latin-500.css'
import '@fontsource/orbitron/latin-700.css'
import '@fontsource/chakra-petch/latin-400.css'
import '@fontsource/chakra-petch/latin-600.css'

import 'ant-design-vue/dist/reset.css'
// 顺序很重要：tokens 定义变量，global.css 消费变量，legacy.css 做存量兼容映射。
import './styles/tokens.css'
import './styles/global.css'
import './styles/legacy.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(Antd)
app.use(i18n)
app.directive('auto-scale', autoScale)

app.directive('permission', permissionDirective)

// 首屏绘制前应用已保存的皮肤，避免闪白
useAppStore().hydrate()

app.mount('#app')
