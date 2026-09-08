import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileViewerRenderers } from '@file-viewer/vite-plugin'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [
      vue(),
      fileViewerRenderers(),
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: 3000,
      host: '0.0.0.0', // 允许外部访问
      allowedHosts: [
        '192.168.31.47',
        '192.168.31.47:8080',
        '192.168.31.47:8000',
        'tianque.oicp.net:38082',
        'tianque.oicp.net:38030',
        'tianque.oicp.net',
        'front.rc.hztianque.com',
        'localhost',
        '127.0.0.1'
      ],
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path
        }
      }
    },
    build: {
      outDir: 'dist',
      // 生产构建与桌面端安装包不打 sourcemap（体积优先），其余环境保留便于排查
      sourcemap: mode !== 'production' && mode !== 'electron',
      rollupOptions: {
        output: {
          manualChunks: {
            'vue-vendor': ['vue', 'vue-router', 'pinia'],
            'ant-design': ['ant-design-vue'],
            'echarts': ['echarts', 'vue-echarts']
          }
        }
      }
    }
  }
})

