# Dify 远程部署（1.17.1）

服务端编排：API + Worker + Web + Sandbox + Plugin Daemon + Nginx 网关。
镜像不自行构建，全部来自个人阿里云仓库。

| 服务 | 容器名 | 说明 |
|------|--------|------|
| `dify-api` | dify-api | REST API（容器端口 5001，不直接对外） |
| `dify-worker` | dify-worker | 异步任务队列消费 |
| `dify-web` | dify-web | 前端 SSR（容器端口 3000，不直接对外） |
| `dify-sandbox` | dify-sandbox | 代码执行沙箱 |
| `dify-plugin-daemon` | dify-plugin-daemon | 插件运行时（挂载 docker.sock） |
| `dify-gateway` | dify-gateway | 统一入口，复用 `nginx` 组件的镜像 |

对外端口：**8080**（Web 入口）、**8888**（Marketplace 缓存代理）。

## 部署步骤

```bash
# 1) 中转官方镜像到个人仓库（幂等，换机器只需跑一次）
cd ../_common && ./prepull.sh            # Windows: .\prepull.ps1
# 或在本目录执行快捷入口
./pull-mirror.sh                          # Windows: .\pull-mirror.ps1

# 2) 配置环境变量
cp .env.example .env
$EDITOR .env

# 3) 初始化数据库（首次）
psql -h $DB_HOST -U postgres \
  -c "CREATE DATABASE dify;" \
  -c "CREATE DATABASE dify_plugin;" \
  -c "\c dify" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 4) 启动
docker compose up -d
docker compose ps
```

## 国内化要点

- 官方镜像 `langgenius/*` 直连 Docker Hub 在国内不稳定，统一由 `_common/prepull.*`
  中转进 `${REGISTRY}/dify-*`，服务器上**不需要**配置任何加速器。
- Marketplace 走网关内的 Nginx 缓存代理（`MARKETPLACE_API_URL: http://dify-gateway:8888`），
  首次穿透较慢，之后命中本地缓存（毫秒级）。
- 网关配置来自 `docker/nginx` 组件，靠环境变量渲染，
  本地/远端共用同一个镜像，不再维护两份 conf。

## 为什么要避开 80 端口

已部署 GPUStack 的服务器上，宿主 80 端口通常被 GPUStack 容器占用。
本编排默认映射到 8080，如需 80 请先确认端口空闲。

## 安全提示

历史提交中曾包含明文数据库地址与口令、以及固定的 `dify-remote-secret-key-2026`
（同时充当 SECRET_KEY / PLUGIN_DAEMON_KEY / INNER_API_KEY_FOR_PLUGIN / SERVER_KEY）。
**请在部署前轮换密钥**：

```bash
openssl rand -base64 32    # 生成新的 DIFY_SECRET_KEY
```

注意轮换后已安装的插件需要重新初始化。
