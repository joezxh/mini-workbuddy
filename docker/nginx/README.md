# 统一网关 / Marketplace 代理

一个镜像 `mwb-nginx-gateway` 同时承载两件事：

1. **Dify 网关**：把浏览器请求分流到 Web（页面）与 API（REST + WebSocket）。
2. **Marketplace 缓存代理**：代理 `marketplace.dify.ai` 并落盘缓存，解决国内首次访问慢的问题。

## 为什么只有一份配置

早先存在 `remote-dify/nginx/*.conf`、`nginx/dify-gateway.conf`、`nginx/remote/gateway.conf`
三份几乎一样的配置，改动其中一份就会与其它两份漂移。

现在统一改成 **官方 nginx 镜像的模板机制**：

```
templates/*.template  ──(容器启动，20-envsubst-on-templates.sh)──►  /etc/nginx/conf.d/*.conf
```

地址与端口全部由环境变量注入，**同一个镜像可以同时服务本地容器名拓扑和远端 127.0.0.1 拓扑**。
所有重复的老 conf 已删除。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `GATEWAY_LISTEN_PORT` | `80` | 网关监听端口 |
| `DIFY_API_UPSTREAM` | `dify-api:5001` | 后端 API 地址 |
| `DIFY_WEB_UPSTREAM` | `dify-web:3000` | 前端 Web 地址 |
| `MARKETPLACE_LISTEN_PORT` | `8888` | Marketplace 代理端口 |
| `MARKETPLACE_UPSTREAM` | `marketplace.dify.ai` | 上游域名 |
| `MARKETPLACE_RESOLVER` | `127.0.0.11` | DNS 解析器（Docker 内嵌 DNS） |

## 用法

单独验证：

```bash
cd docker/nginx
./build.sh --tag 1.0.0          # Windows: .\build.ps1
docker compose up -d            # 端口 3000 / 8888
./push.sh                       # Windows: .\push.ps1
```

被其它编排引用时直接写镜像地址即可，无需挂载任何 conf：

```yaml
dify-gateway:
  image: .../llm-basic/mwb-nginx-gateway:1.0.0
  environment:
    - GATEWAY_LISTEN_PORT=80
    - DIFY_API_UPSTREAM=dify-api:5001
    - DIFY_WEB_UPSTREAM=dify-web:3000
    - MARKETPLACE_LISTEN_PORT=8888
```

## 缓存行为

- 只缓存 GET；API 响应（`200`）缓存 1 小时，重定向 10 分钟，其它 1 分钟。
- 缓存键含 `$request_method`，避免写请求污染。
- 响应头带 `X-Cache-Status`（`HIT` / `MISS` / `BYPASS`）可直接判断命中情况。

```bash
curl -I http://localhost:8888/api/v1/plugins/index | grep -i x-cache
```

## 国内化要点

- 基础镜像 `${BASE_REGISTRY}/nginx:alpine`（已中转）。
- alpine apk 源换成阿里云。
- Marketplace 上游使用 Docker 内嵌 DNS（`127.0.0.11`），不写死公共 DNS，便于跨环境复用。
