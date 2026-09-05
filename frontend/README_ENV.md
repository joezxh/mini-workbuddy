# 前端环境配置说明

## 环境类型

项目支持三种环境配置：

1. **development** - 开发环境（本地开发）
2. **daily** - 日常环境（测试环境）
3. **production** - 生产环境（线上环境）

## 环境变量文件

```
frontend/
├── .env.development      # 开发环境配置
├── .env.daily           # 日常环境配置
├── .env.production      # 生产环境配置
├── .env.example         # 环境变量示例
└── .env.local           # 本地覆盖配置（不提交到 Git）
```

## 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `VITE_API_BASE_URL` | 后端 API 地址 | `http://192.168.100.80:8000` |
| `VITE_APP_TITLE` | 应用标题 | `风险管控系统` |
| `VITE_USE_MOCK` | 是否启用 Mock 数据 | `false` |
| `VITE_LOG_LEVEL` | 日志级别 | `debug/info/warn/error` |

## 使用方法

### 开发环境

```bash
# 启动开发服务器（使用 .env.development）
npm run dev
# 或
pnpm dev
```

后端地址：`http://localhost:8000`

### 日常环境

```bash
# 启动日常环境开发服务器（使用 .env.daily）
npm run dev:daily
# 或
pnpm dev:daily

# 构建日常环境（使用 .env.daily）
npm run build:daily
# 或
pnpm build:daily
```

后端地址：`http://192.168.100.80:8000`

### 生产环境

```bash
# 构建生产环境（使用 .env.production）
npm run build
# 或
pnpm build
```

后端地址：根据 `.env.production` 中的配置

## 本地覆盖配置

如果需要在本地临时修改配置而不影响版本控制，可以创建 `.env.local` 文件：

```bash
# 复制示例文件
cp .env.example .env.local

# 编辑本地配置
vim .env.local
```

`.env.local` 文件会覆盖其他环境配置，且不会被提交到 Git。

## 环境变量优先级

Vite 加载环境变量的优先级（从高到低）：

1. `.env.[mode].local` - 特定模式的本地配置
2. `.env.local` - 通用本地配置
3. `.env.[mode]` - 特定模式配置
4. `.env` - 通用配置

## 在代码中使用环境变量

```typescript
// 获取 API 基础地址
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL

// 获取应用标题
const appTitle = import.meta.env.VITE_APP_TITLE

// 判断是否为生产环境
const isProd = import.meta.env.PROD

// 判断是否为开发环境
const isDev = import.meta.env.DEV

// 获取当前模式
const mode = import.meta.env.MODE
```

## 代理配置

`vite.config.ts` 中已配置开发服务器代理：

```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: env.VITE_API_BASE_URL || 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path
    }
  }
}
```

这样前端请求 `/api/*` 会自动代理到后端服务器。

## 构建产物

不同环境构建的产物会输出到 `dist/` 目录：

```bash
# 开发环境构建（带 sourcemap）
npm run build

# 日常环境构建（带 sourcemap）
npm run build:daily

# 生产环境构建（不带 sourcemap）
npm run build
```

## 注意事项

1. **环境变量必须以 `VITE_` 开头**才能在客户端代码中访问
2. **不要在环境变量中存储敏感信息**（如密钥、密码等）
3. **`.env.local` 文件不应提交到版本控制**
4. 修改环境变量后需要**重启开发服务器**才能生效
5. 生产环境的 API 地址需要根据实际部署情况修改

## 示例：配置日常环境

1. 编辑 `.env.daily` 文件：

```bash
VITE_API_BASE_URL=http://192.168.100.80:8000
```

2. 启动日常环境开发服务器：

```bash
pnpm dev:daily
```

3. 或构建日常环境：

```bash
pnpm build:daily
```

4. 访问 `http://localhost:3000`，前端会自动连接到日常环境后端。

## 故障排查

### 环境变量未生效

- 检查变量名是否以 `VITE_` 开头
- 重启开发服务器
- 清除浏览器缓存

### API 请求失败

- 检查 `VITE_API_BASE_URL` 配置是否正确
- 检查后端服务是否启动
- 检查网络连接和防火墙设置
- 查看浏览器控制台的网络请求

### 代理不工作

- 确认请求路径以 `/api` 开头
- 检查 `vite.config.ts` 中的代理配置
- 查看终端输出的代理日志

