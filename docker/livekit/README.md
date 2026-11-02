# LiveKit 自建（视频会议 SFU）

单节点 `livekit-server` + 内置 TURN，为 MinWorkBuddy 提供多人音视频能力。
完整设计与后端/前端集成见 [docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md](../../docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md)。

## 端口

| 端口 | 协议 | 用途 |
|------|------|------|
| 7880 | TCP | HTTP API（webhook/房间管理）+ WebSocket 信令 |
| 7881 | UDP | 单一媒体端口（多路复用，避开 50000-60000 大段映射） |
| 7882 | TCP | TURN over TCP / ICE-TCP 兜底 |

与工程已占用端口（3000/5432/6379/7474/7687/8000/8001/8194/8765/8888）无冲突。

## 前置：镜像中转

已写入 `docker/_Common/prepull-images.txt`（2026-11，版本经 GitHub Releases 核实，
第三列为大陆可达的 DaoCloud 代理前缀）：

```text
livekit/livekit-server:v1.13.11    base/livekit-server:v1.13.11    docker.m.daocloud.io/livekit/livekit-server:v1.13.11
livekit/egress:v1.15.0             base/livekit-egress:v1.15.0     docker.m.daocloud.io/livekit/egress:v1.15.0
```

执行 `docker/_Common/prepull.ps1`（或 `.sh`）后镜像即入库
`${BASE_REGISTRY}/livekit-server:v1.13.11`。DaoCloud 代理失效时，
全局替换为 `docker.1ms.run` 前缀重跑即可。

## 启动

```powershell
# 1. 先起 infra（提供 mwb-infra-network 与 mwb-redis-stack）
cd D:\projects\MinWorkBuddy
docker compose -f docker-compose.infra.yml up -d

# 2. 起 LiveKit
cd D:\projects\MinWorkBuddy\docker\livekit
Copy-Item .env.example .env           # 改版本号；默认用 devkey/secret 可直接跑通本机验证
docker compose up -d
```

## 验证

```powershell
docker logs mwb-livekit --tail 20                       # 看到 "livekit starting" 即成功
curl http://localhost:7880                              # 有 HTTP 响应即存活
docker exec mwb-livekit /livekit-server ports           # 打印实际占用的 TCP/UDP 端口
```

三端互通（两个浏览器标签 + 一个 Electron 窗口）需先完成后端签 token、前端接入
（见部署指南第 5/6 节）。可用 LiveKit 官方 Playground 配 `devkey/secret` 快速自检。

## 录制（Egress）

录制服务走 compose profile `record`，默认不随 `up` 启动：

```powershell
docker compose --profile record up -d      # server + egress 一起起
docker logs -f mwb-livekit-egress
```

工作方式：后端/CLI 调 `StartEgress` → server（v1.13.x 无 `enable_egress` 开关，
配了 `redis:` 即自动派单）通过共用的 `mwb-redis-stack` 消息总线派单 →
egress 作为参会者拉流混录 → 产物写到宿主机 `docker/livekit/data/egress/`（容器内 `/tmp/egress`）。

触发录制（冒烟用 livekit-cli，或后端 `livekit-api` SDK 的 `EgressStartRoomComposite`）：

```powershell
docker exec mwb-livekit-egress /egress --version   # 仅验镜像可运行
# CLI 方式需先安装 livekit-cli；SDK 方式见 docs 指南第 5 节
```

配置在 `egress.yaml`（redis 总线地址 / ws_url / 与 livekit.yaml 一致的密钥 /
`enable_chrome_sandbox: false`）。要接对象存储（MinIO/S3）时在 egress.yaml
追加 `s3:` 段（支持 `endpoint`），见部署指南第 10 节。

⚠ 已知限制：官方文档建议 egress 用 `network_mode: host`（它会自开高位端口拉媒体流）。
本机冒烟先走 bridge，若录制任务起不来但容器健康，大概率就是这个原因；
Linux 生产直接换 host 网络（egress.yaml 的 `ws_url` 同步改 `ws://localhost:7880`），
Docker Desktop ≥ 4.34 可选开 hostNetworking 后同理。

## 生产注意

- **换密钥**：`docker run --rm livekit/livekit-server:<ver> generate-keys`，
  改 `livekit.yaml` 的 `keys`（同步 `egress.yaml`），并同步 `backend/.env`。
- **防火墙/安全组**：放行 `7880/tcp`、`7881/udp`、`7882/tcp`。
- **内网/多网卡黑屏无声**：在 `livekit.yaml` 的 `rtc.hostname` 显式写客户端可达的宿主机 IP。
- **单端口 vs 端口段**：默认单 `udp_port: 7881`；若客户端 NAT 严格连通率低，
  再改回 `port_range_start/end: 50000-60000`（仅 Linux 生产建议，Windows 映射慢）。
- **录制**：Linux 生产将 egress 改 `network_mode: host`；bridge 仅用于本机冒烟。

## 已知坑（详见指南第 9 节）

| 现象 | 原因 / 规避 |
|------|-------------|
| 启动即 `could not parse config` 重启循环 | 写了 v1.13.x 已删字段（`use_websocket`/`auth`/`static_auth_secret`/`enable_egress`）→ 以官方 config-sample.yaml 对应版本为准 |
| 连上信令但黑屏无声 | 媒体地址探测错误 → 配 `rtc.hostname` |
| Redis 未起就启动 | 配了 `redis:` 段但 `mwb-redis-stack` 不在 → server 反复重启；先起 infra |
| `${VAR}` 未生效 | LiveKit 不展开 YAML 变量，`keys` 必须直接写在 `livekit.yaml` |
| 生产用 `--dev` | 会开 debug 日志与 pprof，扩大攻击面；本编排用 `--config`，勿加 `--dev` |

## 文件

- `docker-compose.yml` —— 服务编排与端口映射（含 profile `record` 的 egress）
- `livekit.yaml` —— server 配置（密钥写在此，生产必须替换；egress 经 redis 总线自动调度，无需开关）
- `egress.yaml` —— 录制服务配置（密钥须与 livekit.yaml 一致）
- `.env.example` —— compose 变量模板（版本/仓库前缀/密钥对照）
- `data/egress/` —— 录制产物输出目录（运行时自动创建，已 gitignore）
