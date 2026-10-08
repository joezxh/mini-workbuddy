# SQLBot —— Text2SQL 智能问数

| 产物 | 端口 | 说明 |
|------|------|------|
| `sqlbot` | 8000 | UI + REST API（同源） |
| `sqlbot` | 8001 | MCP 服务 |

## 为什么自己构建镜像

官方镜像 `dataease/sqlbot:v1.10.1` 已经能用，但它的构建定义里有一个
`ghcr.io/1panel-dev/maxkb-vector-model` 阶段（762MB，且 ghcr.io 在国内拉取极慢）。
本镜像基于上游 `deploy-offline/Dockerfile.offline`：

- 去掉向量模型阶段 —— 本部署 `EMBEDDING_ENABLED=false`、`TABLE_EMBEDDING_ENABLED=false`，
  embedding 模型是惰性加载，加载失败会优雅降级，运行期根本用不到权重文件。
- 若将来要开启本地向量检索，需要改回包含该阶段的 Dockerfile。

## 目录结构

```
sqlbot/
├── Dockerfile             # 镜像定义（多阶段）
├── patches/
│   ├── start-external-db.sh   # 覆盖镜像内置 start.sh：跳过内置 PG
│   └── serve_ui.py            # 在 main:app 之上挂载前端 SPA
├── docker-compose.yml     # 独立部署
├── build.{ps1,sh}
├── push.{ps1,sh}
├── .env.example
└── README.md
```

## 构建

**`SQLBOT_SECRET_KEY` 是必填构建参数**，缺失时 Dockerfile 会主动失败。

```powershell
# Windows
cd d:\projects\MinWorkBuddy\docker\sqlbot
.\build.ps1 -SourceRoot D:\work\chat-bi\SQLBot -SecretKey <你的密钥>
```

```bash
# Linux
cd /path/to/MinWorkBuddy/docker/sqlbot
./build.sh --source-root /opt/SQLBot --secret-key <你的密钥>
```

未显式传密钥时，脚本会尝试读取本目录 `.env` 中的 `SECRET_KEY`；两者都没有则报错退出。

## 密钥一致性（踩过的坑）

前端 `frontend/src/utils/crypto.ts` 用 `VITE_SECRET_KEY` 对账号口令做 AES-CBC 加密，
后端 `common/utils/crypto.py` 用 `SECRET_KEY[:32]` 解密，**两者必须同源**。

`.env.production` 未定义 `VITE_SECRET_KEY` 时，前端会回退到一个硬编码默认值，
于是出现"页面能打开、接口 200、但登录永远失败"的假故障。

现在 Dockerfile 里加了硬校验：

```dockerfile
RUN test -n "${VITE_SECRET_KEY}" || (echo "ERROR: ..." && false)
```

## 国内化要点

| 层 | 处理 |
|----|------|
| 基础镜像 | `${BASE_REGISTRY}/sqlbot-base`、`${BASE_REGISTRY}/sqlbot-python-pg`（官方已在阿里云青岛公开仓库，这里再中转进个人仓库） |
| npm | `https://registry.npmmirror.com`（前端 + g2-ssr） |
| uv | `--default-index https://mirrors.aliyun.com/pypi/simple`，`UV_HTTP_TIMEOUT=180` |
| torch | 默认走阿里云 PyTorch 镜像的 CPU 索引，避开约 3GB 的 CUDA 依赖 |
| apt | Debian 源在 sqlbot-base 镜像内已可用，本 Dockerfile 不再额外换源 |

两个必须知道的钉子：

1. **torch 必须单独装**：`uv sync --extra cpu` 会连 CUDA 依赖一起拉，约 3GB 且极易中断；
   改用 `--index-url` 指向 CPU 索引单独安装。
2. **mcp 必须降到 2.0 以下**：`mcp>=2.0` 把 `Server.__init__` 第二个位置参数改成仅关键字，
   `fastapi-mcp<0.4.0` 的 `LowlevelMCPServer(name, description)` 调用会 TypeError。
   `uv sync` 不读 pip constraints，只能在 sync 之后用 `uv pip install "mcp<2.0.0"` 覆盖。

## 运行

```bash
cp .env.example .env       # 填入与构建时一致的 SECRET_KEY
docker compose up -d
docker compose logs -f
```

```bash
curl http://localhost:8000        # UI
curl http://localhost:8001/sse    # MCP
```

首次使用：默认管理员口令来自 `DEFAULT_PWD`（`SQLBot@123456`），请及时修改。

## 安全提示

`SECRET_KEY` 同时用于前端加密与后端解密，泄漏等同于知道加密后的明文结构。
请使用随机长字符串，并通过 `.env`（已被 `.gitignore` 忽略）注入，不要写进 Dockerfile 或 compose。
