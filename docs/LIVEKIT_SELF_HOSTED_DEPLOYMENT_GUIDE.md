# LiveKit 自建部署方案（MinWorkBuddy）

> 版本：2026-11-01。镜像版本已按 GitHub Releases 核实并锁定：
> livekit-server **v1.13.11**（2026-10-25）、livekit-egress **v1.15.0**（2026-10-06），禁止 latest。

## 1. 目标与分期

| 阶段 | 内容 | 说明 |
|------|------|------|
| 一期（本文） | 单节点 livekit-server + 内置 TURN，浏览器/Electron 多人音视频 | 跑通会议核心链路 |
| 二期 | Egress 录制 → 会议录像落存储 → 走知识库入库管线 | compose 已内置 profile `record`（见第 10 节），产物目录 `data/egress/` |
| 三期 | LiveKit Agents（Python）：AI 参会、实时字幕/纪要 | 可与 `docker/speech-to-speech` pipeline 对接 |
| 四期（按需） | Redis 协调多节点 SFU 横向扩展 | 一期已预置 redis 配置 |

## 2. 组件与端口规划

### 2.1 组件清单

| 组件 | 镜像 | 必要性 |
|------|------|--------|
| livekit-server（SFU + 信令 + 内置 TURN） | `livekit/livekit-server:v1.13.11` | 一期必须 |
| Redis | 复用 infra 的 `mwb-redis-stack`（6379） | 单节点可选，多节点必需 |
| livekit-egress（录制） | `livekit/egress:v1.15.0` | 二期再加 |
| livekit-ingress（RTMP/WHIP 拉流进会） | `livekit/ingress:v1.x` | 暂不需要 |

### 2.2 端口占用核对

工程已占用：`3000/3001/5001-5003/5432/6379/7474/7687/8000/8001/8194/8765/8888`。
LiveKit 默认端口段（7880-7882、50000-60000）与之**无冲突**，直接采用默认规划：

| 端口 | 协议 | 用途 | 暴露范围 |
|------|------|------|----------|
| 7880 | TCP | HTTP API（webhook、房间管理）+ WebSocket 信令 | 内网 |
| 7881 | UDP | 单一媒体端口（`rtc.udp_port`，1.5+ 推荐，免开大段） | 客户端可达即可 |
| 7882 | TCP | TURN over TCP / ICE-TCP 兜底 | 内网 |
| 50000-60000 | UDP | 媒体端口段（生产环境若客户端 NAT 严格再启用） | 公网/VPN |

> 单媒体端口（7881/udp）+ TCP 兜底（7882）能覆盖绝大多数场景，防火墙只需放行 3 个端口。

## 3. 镜像中转（接入 `_Common/prepull-images.txt`）

沿用现有"官方源拉取 → retag → push 个人 ACR"流程，在 `prepull-images.txt` 追加：

```text
# ---------- LiveKit 视频会议（docker/livekit 依赖，2026-11 新增）----------
livekit/livekit-server:v1.13.11    base/livekit-server:v1.13.11    docker.m.daocloud.io/livekit/livekit-server:v1.13.11
livekit/egress:v1.15.0             base/livekit-egress:v1.15.0     docker.m.daocloud.io/livekit/egress:v1.15.0
```

> 第三列为大陆可达的 Docker Hub 代理前缀（DaoCloud，2026-10 实测可用）；
> 失效时全局替换为 `docker.1ms.run`。详见 prepull-images.txt 头部说明。

执行 `docker/_Common/prepull.ps1`（或 `.sh`）后即进入
`${BASE_REGISTRY}/livekit-server:v1.13.11`，业务 compose 只引用中转地址。

## 4. `docker/livekit/` 目录与文件

```
docker/livekit/
├── docker-compose.yml      # 服务编排（server + profile "record" 的 egress）
├── livekit.yaml            # server 配置（v1.13.x 无 enable_egress 开关，redis 存在即自动调度 egress）
├── egress.yaml             # 录制配置（redis 总线 / ws_url / 密钥与 server 一致）
├── .env.example            # 密钥模板（.env 不入库）
└── README.md               # 本方案精简版
```

### 4.1 livekit.yaml

```yaml
# LiveKit Server 配置（v1.13.11，字段已按官方 config-sample.yaml 与 pkg/config/config.go 实测校验）
port: 7880                    # HTTP API + WebSocket 信令

rtc:
  udp_port: 7881              # 单一 UDP 媒体端口（避免 50000-60000 大段映射）
  tcp_port: 7882              # ICE-TCP 兜底
  # hostname: 192.168.x.x     # 内网/多网卡部署时显式指定客户端可达的媒体地址，
                              # 否则 server 自动探测的 IP 可能不可达 → 连得上信令收不到流

keys:
  MWBLK_APIKP: <secret>       # keyID: secret，secret ≥ 32 位随机串（必须直写 yaml，见下方注）

room:
  empty_timeout: 300          # 房间无人 5 分钟后自动回收
  max_participants: 50        # 按业务上限收紧

redis:
  address: mwb-redis-stack:6379   # 复用 infra Redis；单节点也建议开启（状态可观测、平滑扩多节点，
                              # 同时是 egress/ingress 任务的消息总线）

logging:
  level: info
```

> **v1.13.x 实测坑（冒烟阶段撞过）**：`rtc.use_websocket`、顶层 `auth` 段、
> `turn.static_auth_secret`、顶层 `enable_egress` 四个字段均已不存在，写错直接
> `could not parse config` 重启循环：WS 信令挂在 port 上始终可用；token TTL 由
> 签发方（后端 livekit-api SDK）决定；内置 TURN 需 TLS 证书+domain 才能开；
> egress 只要配了 redis 就经消息总线自动调度。
>
> 另外 LiveKit **不展开 YAML 里的 `${VAR}`**，`keys` 是 map 也无法用环境变量覆盖，
> 密钥必须直写 `livekit.yaml`/`egress.yaml`（与后端 `.env` 保持一致）。

### 4.2 docker-compose.yml

```yaml
# =============================================================
# LiveKit 视频会议（单节点 SFU + 内置 TURN）
#
# 前置：
#   1. docker compose -f docker-compose.infra.yml up -d   （mwb-infra-network、Redis）
#   2. cp .env.example .env 并填入随机密钥
#   3. 镜像已 prepull 至 BASE_REGISTRY（见 ../_Common/prepull-images.txt）
#
# 端口：7880 HTTP/WS   7881/udp 媒体   7882/tcp TURN-TCP
# =============================================================
name: livekit-local

services:
  livekit-server:
    image: ${BASE_REGISTRY:-crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base}/livekit-server:${LIVEKIT_VERSION:-v1.13.11}
    container_name: mwb-livekit
    command: --config /etc/lk/config.yaml
    env_file:
      - .env
    volumes:
      - ./livekit.yaml:/etc/lk/config.yaml:ro
    ports:
      - "7880:7880"       # HTTP API + WS 信令
      - "7881:7881/udp"   # 单一媒体 UDP 端口
      - "7882:7882"       # TURN over TCP / ICE-TCP
    networks:
      - mwb-infra-network
    restart: unless-stopped
    # 说明：livekit-server 无标准 healthcheck 端点，用日志/接口验证代替：
    #   docker logs mwb-livekit | Select-String "livekit starting"
    #   curl http://localhost:7880   （有 HTTP 响应即存活）

networks:
  mwb-infra-network:
    external: true
```

### 4.3 .env.example

```ini
# LiveKit API Key 对（后端签 token 与 server 校验必须一致）
LIVEKIT_API_KEY=MWBLK_APIKP
LIVEKIT_API_SECRET=<openssl rand -hex 32>
LIVEKIT_TURN_SECRET=<openssl rand -hex 16>
LIVEKIT_VERSION=v1.13.11
BASE_REGISTRY=crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base
```

> Windows 生成随机串：`-join ((48..57)+(97..122) | Get-Random -Count 48 | %{[char]$_})`
> 或 Docker 内执行：`docker run --rm alpine openssl rand -hex 32`。

## 5. 后端集成（FastAPI）

### 5.1 依赖与配置

```powershell
# backend/.venv
pip install livekit-api        # 加入 requirements.txt：livekit-api>=0.x（锁版本）
```

`backend/.env` 追加：

```ini
LIVEKIT_WS_URL=ws://localhost:7880
LIVEKIT_HTTP_URL=http://localhost:7880
LIVEKIT_API_KEY=MWBLK_APIKP
LIVEKIT_API_SECRET=<与 docker/livekit/.env 一致>
```

对应加到 `app/config/` 的 settings（模式同现有 MEM0/GPUStack 配置项），禁止散读 `os.environ`。

### 5.2 签发入会 Token（核心接口）

```python
from livekit import api

async def build_token(room: str, identity: str, name: str) -> str:
    token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)          # 用现有用户体系的 user_id/username
        .with_name(name)
        .with_grants(api.VideoGrants(room_join=True, room=room))
    )
    return token.to_jwt()
```

路由建议放 `backend/app/routers/`（如 `meeting.py`）：

| 接口 | 说明 |
|------|------|
| `POST /meeting/rooms` | 建房（服务端可用 `LiveKitAPI(list_rooms/create_token)` 或直接约定房间名规则） |
| `GET /meeting/rooms/{id}/token` | 按当前登录用户签 token，鉴权走现有 JWT 中间件 |
| `POST /meeting/webhook` | 接收 server 回调（room_started/room_finished/participant_*），落会议审计表 |

webhook 校验：LiveKit 回调带 `Authorization`（对 webhook 单独签发的 JWT），在 FastAPI 里用
`livekit.api.WebhookReceiver` 验证，**不要裸接**。

### 5.3 Alembic 迁移

会议相关新表（如 `meeting_room`、`meeting_participant_log`）遵循
`backend/MIGRATIONS.md` 既有约定新建 revision；注意历史坑：**revision id 不要超 32 字符**
（alembic_version 默认 VARCHAR(32) 会截断）。

## 6. 前端集成（Vue 3 + Electron）—— 已落地

```powershell
cd frontend
npm i livekit-client          # 已安装（2.23.0）
```

已实现文件：

| 文件 | 内容 |
|------|------|
| `src/api/meeting.ts` | `createMeetingToken()` 封装 `POST /api/v1/meeting/tokens`（走统一 axios 拦截器，自动带 JWT） |
| `src/views/meeting/MeetingRoom.vue` | 房间页：入会表单 → 本地预览/远端 `track.attach()` 渲染 → 麦/摄像头开关 → 离会 |
| `src/router/index.ts` | 路由 `/meeting`（name: MeetingRoom，挂 AppLayout 下） |
| `src/layouts/components/AppHeader.vue` | 快捷导航入口（图标 VideoCameraOutlined） |
| `electron/main/index.ts` | `session.setPermissionRequestHandler` 仅对本应用 origin 放行 `media` |

实现要点（与原方案差异）：

- **无需 `VITE_LIVEKIT_WS_URL` 环境变量**：`ws_url` 由后端 token 接口随体下发
  （取自后端 `LIVEKIT_WS_URL` 配置），前端只认接口响应，换地址不用重新打包。
- 媒体渲染用 livekit-client 2.x 经典 `track.attach()/detach()`（该版本无 `TrackRef` 导出）。
- 浏览器访问需安全上下文：本机 `http://localhost` 下 getUserMedia 可用；
  局域网 IP 明文 http 访问会被拒，生产走 nginx https（见 §8）。
- Electron：`electron:dev` 启动即生效（主进程已在 loadURL 前注册权限处理器）。

## 7. 部署步骤

### 7.1 开发机（Windows / Docker Desktop）

```powershell
# 1. 中转镜像
cd D:\projects\MinWorkBuddy\docker\_Common
.\prepull.ps1                       # 已含 livekit 行

# 2. 起 infra（Redis 必须在）
cd D:\projects\MinWorkBuddy
docker compose -f docker-compose.infra.yml up -d

# 3. 起 LiveKit
cd D:\projects\MinWorkBuddy\docker\livekit
Copy-Item .env.example .env         # 填密钥
docker compose up -d
docker logs mwb-livekit --tail 20   # 看到 "livekit starting, address ..." 即成功
```

> Windows 注意：Docker Desktop 是 NAT 网络，**50000-60000 大段 UDP 映射极慢且不稳**，
> 开发环境固定用 `rtc.udp_port: 7881` 单端口方案；浏览器与 server 同机时
> 自动探测即可连通。跨机访问不通时，在 `livekit.yaml` 的 `rtc.hostname` 显式写宿主机局域网 IP。

### 7.2 生产（Linux 服务器）

```bash
# 防火墙/安全组放行：7880/tcp、7881/udp、7882/tcp
sudo ufw allow 7880/tcp && sudo ufw allow 7881/udp && sudo ufw allow 7882/tcp

# 部署目录同开发机；若走 nginx 统一域名（推荐）：
#   wss://meeting.example.com/api  → 7880（含 Upgrade 头转发）
#   RTC 媒体仍直连 7881/udp，TURN 兜底 7882/tcp
docker compose -f docker/livekit/docker-compose.yml up -d
```

容量参考：单台 8C16G 约可承载 500 路视频 / 2000 路音频转发；
带宽按 **每上行一路 720p ≈ 1.5 Mbps** 估算，50 人满员会议约需 100 Mbps 级出口（SFU 下行为 N 路上行、N×(M-1) 下行转发，实际由下行带宽决定）。

## 8. 验证清单（一期完成标准）

1. `docker logs mwb-livekit` 无 ERROR，`curl http://localhost:7880` 有响应；
2. LiveKit 官方 Playground（`https://client.example.com` 或本地 `npx livekit-client-crypto` 均可）
   用后端签发的 token 能连上房间；
3. 两个浏览器标签 + 一个 Electron 窗口三端互见音视频、能开关麦/摄像头；
4. 弱网验证：手机热点（4G）入会可通（验证 TURN 兜底生效）；
5. 后端 webhook 收到 `room_started/room_finished` 并落库；
6. `room.empty_timeout` 生效：全员离开 5 分钟后 `ListRooms` 为空。

## 9. 已知坑与规避

| 坑 | 现象 | 规避 |
|----|------|------|
| 媒体地址探测错误 | 信令连上但收不到流（黑屏无声） | 内网/多网卡机器显式配 `rtc.hostname` |
| Docker Desktop 大段 UDP | 启动映射 1 万端口卡死 | 固定 `rtc.udp_port` 单端口 |
| 严格 NAT 连不上 | ICE 失败 | `turn.enabled: true` + 客户端配置 `iceServers` 指向 7882 |
| Redis 未起就启动 livekit 并配了 redis 段 | server 反复重启 | 文档化启动顺序：infra → livekit |
| latest 标签漂移 | 版本行为不一致、配置字段变更 | 锁 `vX.Y.Z`，升级走灰度验证 |
| token secret 泄露 | 任何人可入任何房 | secret 只存 `.env`（已 gitignore）；token 10 分钟 TTL + 房间级鉴权 |
| Egress 在 Windows 不可用 | 录制容器起不来 | 二期录制只在 Linux 宿主机部署（`network_mode: host`） |

## 10. 后续演进（二、三期摘要）

- **录制入库闭环（已预埋）**：`docker compose --profile record up -d` 起 egress；
  server 配了 `enable_egress: true`，`StartEgress` 请求经共用的 `mwb-redis-stack`
  消息总线派单，egress 作为参会者拉流混录，产物先落 `docker/livekit/data/egress/`
  （容器内 `/tmp/egress`）；接 MinIO/S3 时在 `egress.yaml` 追加 `s3:` 段（支持
  `endpoint`）。录制完成 webhook → 复用现有知识库“文档上传→向量化”管线，
  会议自动沉淀进 KB；音频另走 `docker/speech-to-speech` 的 STT 生成纪要文本，
  进知识图谱抽取流程。⚠ Linux 生产按官方要求改 `network_mode: host`；
  bridge 仅用于本机冒烟（录制起不来但容器健康时优先排查这里）。
- **AI 参会**：`pip install livekit-agents`，Agent 以 participant 身份入房，
  LLM 接 GPUStack OpenAI 兼容口（与 s2s pipeline 同一模型管理），实现"AI 同事旁听/答问/总结"。
- **多节点**：起第二台 livekit-server 指向同一 Redis 即自动组网（node 自动发现 + 房间调度），
  前端无需改动。

---

配套文件落盘清单（实施 PR 时一并提交）：

- `docker/livekit/{docker-compose.yml, livekit.yaml, .env.example, README.md}`（新增）
- `docker/_Common/prepull-images.txt`（追加 livekit 两行）
- `backend/requirements.txt`（+`livekit-api`）、`backend/app/config/`（+3 个配置项）、
  `backend/app/routers/meeting*`（新增路由）、alembic revision（会议表）
- `frontend/package.json`（+`livekit-client`）、`src/components/meeting/`（新增）、
  `.env.*`（+`VITE_LIVEKIT_WS_URL`）
