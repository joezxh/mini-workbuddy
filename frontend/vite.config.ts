import { defineConfig, loadEnv } from 'vite'
import type { Plugin, ViteDevServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileViewerRenderers } from '@file-viewer/vite-plugin'
import { resolve } from 'path'
import { createReadStream, existsSync } from 'node:fs'

// ort(onnxruntime-web) 的 emscripten loader/wasm 以运行时拼接 URL 加载，无法走
// vite 模块管道：public 下 .mjs 被模块 import 会被 vite 拒绝，.vite/deps 无旁路产物。
// dev 由本插件（先于 vite 内部 middleware）直接静态服务 node_modules 源文件；
// build 时 public/vad/ 原样拷入 dist 承载同一批文件。
function ortVadAssets(): Plugin {
  const ortDist = resolve(__dirname, 'node_modules/onnxruntime-web/dist')
  const served = new Set(['ort-wasm-simd-threaded.mjs', 'ort-wasm-simd-threaded.wasm'])
  return {
    name: 'ort-vad-assets',
    configureServer(server: ViteDevServer) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url || '').split('?')[0]
        if (!url.startsWith('/vad/')) return next()
        const f = url.slice('/vad/'.length)
        if (!served.has(f)) return next()
        const fp = resolve(ortDist, f)
        if (!existsSync(fp)) {
          res.statusCode = 404
          return res.end()
        }
        res.setHeader('Content-Type', f.endsWith('.wasm') ? 'application/wasm' : 'text/javascript')
        createReadStream(fp).pipe(res)
      })
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [
      vue(),
      fileViewerRenderers(),
      ortVadAssets(),
    ],
    // ort 与 vad-web 一并预打包：exclude 会让 vad-web（CJS）对 ort 子路径的
    // require 退化为运行时 __require（"Dynamic require of ... is not supported"）
    optimizeDeps: {
      include: ['@ricky0123/vad-web', 'onnxruntime-web/wasm'],
    },
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

