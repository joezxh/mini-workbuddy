/**
 * 桌面端（Electron）开发 / 预览 / 打包入口。
 *
 * 用法:
 *   node scripts/electron.cjs dev      # 启动 Vite dev server + Electron（主进程代码改动后需重启）
 *   node scripts/electron.cjs preview  # 用已有 dist/ 直接启动桌面端（不打包）
 *   node scripts/electron.cjs build    # 构建渲染层 + 打包当前平台安装包
 *   node scripts/electron.cjs build --win --x64
 *   node scripts/electron.cjs build --mac
 *   node scripts/electron.cjs build --linux
 *   node scripts/electron.cjs build --dir   # 只产出未打包目录，便于排查
 *
 * 环境变量:
 *   ELECTRON_DEFAULT_API_BASE_URL  打包时写入的默认后端地址（留空则为 http://localhost:8000）
 *   VITE_PORT                      dev 模式下的 dev server 端口（默认 3000）
 */
const fs = require('fs')
const path = require('path')
const { spawn, spawnSync } = require('child_process')

const ROOT = path.resolve(__dirname, '..')
const DIST_ELECTRON = path.join(ROOT, 'dist-electron')
/** 顶层 package.json 是 "type": "module"，这里声明产物为 CommonJS，否则主进程 require 会失败。 */
const CJS_MARKER = { type: 'commonjs' }

const DEFAULT_API_BASE = process.env.ELECTRON_DEFAULT_API_BASE_URL || 'http://localhost:8000'

const children = []
let closing = false

function log(msg) {
  console.log(`[electron] ${msg}`)
}

function fail(msg) {
  console.error(`[electron] ${msg}`)
  process.exit(1)
}

/** 解析 node_modules/.bin 下的可执行文件（Windows 需要 .cmd）。 */
function binPath(name) {
  const ext = process.platform === 'win32' ? '.cmd' : ''
  const p = path.join(ROOT, 'node_modules', '.bin', name + ext)
  return fs.existsSync(p) ? p : null
}

function runBin(name, args, opts = {}) {
  const bin = binPath(name)
  if (!bin) fail(`未找到 ${name}，请先执行 npm install`)
  // Windows 下 .cmd 必须借助 shell 才能 spawn（否则 EINVAL）；
  // POSIX 下用 detached 起新进程组，退出时可以整组回收（tsc --watch 之类）。
  const useShell = process.platform === 'win32'
  const child = spawn(useShell ? `"${bin}"` : bin, args, {
    stdio: 'inherit',
    cwd: ROOT,
    shell: useShell,
    detached: !useShell,
    ...opts,
  })
  children.push(child)
  return new Promise((resolve, reject) => {
    child.on('error', reject)
    child.on('exit', (code) => (code === 0 ? resolve(code) : reject(new Error(`${name} 退出码 ${code}`))))
  })
}

function cleanup() {
  if (closing) return
  closing = true
  for (const child of children) {
    if (child.exitCode !== null || child.signalCode) continue
    try {
      if (process.platform === 'win32') {
        spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
      } else {
        process.kill(-child.pid, 'SIGTERM')
      }
    } catch {
      /* 进程可能已经退出 */
    }
  }
}

process.on('SIGINT', () => {
  cleanup()
  process.exit(0)
})
process.on('SIGTERM', () => {
  cleanup()
  process.exit(0)
})
process.on('exit', cleanup)

/** 编译主进程 + 预加载脚本，并写出运行所需的辅助文件。 */
async function buildMainProcess() {
  log('编译主进程/预加载脚本 (tsc)...')
  await runBin('tsc', ['-p', 'electron/tsconfig.json'])

  fs.mkdirSync(DIST_ELECTRON, { recursive: true })
  fs.writeFileSync(path.join(DIST_ELECTRON, 'package.json'), JSON.stringify(CJS_MARKER, null, 2))
  fs.writeFileSync(
    path.join(DIST_ELECTRON, 'defaults.json'),
    JSON.stringify({ apiBaseUrl: DEFAULT_API_BASE }, null, 2),
  )
  log(`主进程产物就绪 -> ${path.relative(ROOT, DIST_ELECTRON)}`)
}

/** 以子进程方式启动 Electron。mode=dev 时把 dev server 地址传给主进程。 */
function startElectron(devServerUrl) {
  let electronBin
  try {
    electronBin = require('electron')
  } catch {
    fail('未找到 electron，请先执行 npm install')
  }
  if (typeof electronBin !== 'string') fail('electron 模块未返回可执行文件路径')

  const env = { ...process.env }
  if (devServerUrl) env.VITE_DEV_SERVER_URL = devServerUrl
  else delete env.VITE_DEV_SERVER_URL

  const child = spawn(electronBin, ['.'], { stdio: 'inherit', cwd: ROOT, env })
  children.push(child)
  return new Promise((resolve, reject) => {
    child.on('error', reject)
    child.on('exit', (code) => {
      log(`Electron 已退出 (code=${code})`)
      resolve()
    })
  })
}

async function dev() {
  await buildMainProcess()

  log('启动 Vite dev server (mode=electron)...')
  const vite = await import('vite')
  const server = await vite.createServer({ root: ROOT, mode: 'electron' })
  await server.listen()
  const local = (server.resolvedUrls && server.resolvedUrls.local) || []
  const devUrl = (local[0] || 'http://localhost:3000/').replace(/\/+$/, '')

  log('监听主进程源码变更 (tsc --watch)...')
  runBin('tsc', ['-p', 'electron/tsconfig.json', '--watch', '--preserveWatchOutput']).catch(() => {
    /* 退出时忽略 */
  })

  log(`启动 Electron -> ${devUrl}`)
  await startElectron(devUrl)
  await server.close()
}

async function preview() {
  if (!fs.existsSync(path.join(ROOT, 'dist', 'index.html'))) {
    fail('未找到 dist/index.html，请先执行 npm run electron:build（或 npm run build）')
  }
  await buildMainProcess()
  log('以 dist/ 启动桌面端（内置静态服务器）...')
  await startElectron(null)
}

async function build(flags) {
  await buildMainProcess()

  log('构建渲染层 (vite build)...')
  // 桌面端不烘焙后端地址：运行时从 userData/app-config.json 读取，可在客户端里随时改。
  // 这里直接调 vite build 而不走 scripts/build.cjs：后者会先跑全量 vue-tsc，
  // 不该让 Web 侧的存量类型问题阻塞桌面端出包（类型门禁仍在 npm run build 中保留）。
  // 若需要连同类型检查一起打包，执行 npm run build && npm run electron:build。
  // mode=electron 走 .env.electron：后端地址留空，由运行时配置决定。
  await runBin('vite', ['build', '--mode', 'electron'], {
    env: { ...process.env, ELECTRON: '1' },
  })

  log(`打包安装包 (electron-builder ${flags.length ? flags.join(' ') : '当前平台'})...`)
  await runBin('electron-builder', flags.length ? flags : [])
  log('打包完成，产物输出在 release/ 目录')
}

async function main() {
  const [mode, ...rest] = process.argv.slice(2)
  switch (mode) {
    case 'dev':
      return dev()
    case 'preview':
      return preview()
    case 'build':
    case 'dist':
      return build(rest)
    default:
      console.log(`未知模式: ${mode || '(空)'}
用法:
  node scripts/electron.cjs dev
  node scripts/electron.cjs preview
  node scripts/electron.cjs build [--win|--mac|--linux] [--dir]`)
      return undefined
  }
}

main().catch((err) => {
  console.error(err)
  cleanup()
  process.exit(1)
})
