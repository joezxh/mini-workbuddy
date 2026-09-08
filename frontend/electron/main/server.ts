import http from 'node:http'
import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import type { AddressInfo } from 'node:net'

/**
 * 打包后用于承载渲染产物的本地静态服务器。
 *
 * 为什么不用 file:// 直接加载 dist/index.html：
 *   - file:// 下 history 路由无法 pushState，Web Worker（PDF 预览等）也会被同源策略拦掉；
 *   - 走 http://127.0.0.1:<随机端口> 后，渲染层与浏览器里运行的语义完全一致，
 *     Worker、SSE、history 路由全部照常工作，跨域只依赖后端既有的 CORS 配置。
 *
 * 只在 127.0.0.1 上监听，不对外暴露，不占用固定端口（port 0 由系统分配）。
 */

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.cjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.eot': 'application/vnd.ms-fontobject',
  '.wasm': 'application/wasm',
  '.pdf': 'application/pdf',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.xml': 'application/xml',
  '.bcmap': 'application/octet-stream',
  '.properties': 'text/plain; charset=utf-8',
}

export interface StaticServer {
  readonly port: number
  readonly origin: string
  close(): Promise<void>
}

function resolveSafe(rootDir: string, urlPath: string): string | null {
  const target = path.normalize(path.join(rootDir, urlPath))
  if (target !== rootDir && !target.startsWith(rootDir + path.sep)) return null
  return target
}

async function handle(req: http.IncomingMessage, res: http.ServerResponse, rootDir: string) {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405, { Allow: 'GET, HEAD' })
    res.end()
    return
  }

  let pathname: string
  try {
    pathname = decodeURIComponent(new URL(req.url || '/', 'http://127.0.0.1').pathname)
  } catch {
    res.writeHead(400).end()
    return
  }

  let filePath = resolveSafe(rootDir, pathname)
  if (!filePath) {
    res.writeHead(403).end('Forbidden')
    return
  }

  let stat = await fsp.stat(filePath).catch(() => null)
  if (stat?.isDirectory()) {
    filePath = path.join(filePath, 'index.html')
    stat = await fsp.stat(filePath).catch(() => null)
  }
  if (!stat) {
    // SPA 回退：任意未知路径都交给前端路由处理
    filePath = path.join(rootDir, 'index.html')
    stat = await fsp.stat(filePath).catch(() => null)
  }
  if (!stat) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('未找到 dist/index.html，请先执行 npm run build 或 npm run electron:build')
    return
  }

  const ext = path.extname(filePath).toLowerCase()
  const headers: Record<string, string> = {
    'Content-Type': MIME[ext] || 'application/octet-stream',
    'Accept-Ranges': 'bytes',
    'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=31536000, immutable',
  }

  const range = req.headers.range
  if (range) {
    const matched = /^bytes=(\d*)-(\d*)$/.exec(range.trim())
    if (matched) {
      const start = matched[1] ? Number(matched[1]) : 0
      const end = matched[2] ? Number(matched[2]) : stat.size - 1
      if (Number.isNaN(start) || Number.isNaN(end) || start > end || start >= stat.size) {
        res.writeHead(416, { 'Content-Range': `bytes */${stat.size}` })
        res.end()
        return
      }
      res.writeHead(206, {
        ...headers,
        'Content-Range': `bytes ${start}-${end}/${stat.size}`,
        'Content-Length': String(end - start + 1),
      })
      if (req.method === 'HEAD') {
        res.end()
        return
      }
      fs.createReadStream(filePath, { start, end }).pipe(res)
      return
    }
  }

  res.writeHead(200, { ...headers, 'Content-Length': String(stat.size) })
  if (req.method === 'HEAD') {
    res.end()
    return
  }
  fs.createReadStream(filePath).pipe(res)
}

export function startStaticServer(rootDir: string, host = '127.0.0.1'): Promise<StaticServer> {
  const root = path.resolve(rootDir)
  const server = http.createServer((req, res) => {
    void handle(req, res, root).catch((err) => {
      console.error('[electron] 静态服务器异常:', err)
      if (!res.headersSent) res.writeHead(500)
      res.end()
    })
  })
  // SPA 场景下不应为 keep-alive 拖慢退出
  server.keepAliveTimeout = 5000

  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, host, () => {
      const port = (server.address() as AddressInfo).port
      resolve({
        port,
        origin: `http://${host}:${port}`,
        close: () =>
          new Promise<void>((done) => {
            server.closeAllConnections?.()
            server.close(() => done())
          }),
      })
    })
  })
}
