# MinWorkBuddy 容器化资产总览

所有组件的构建与部署资产集中在这里，统一遵循两条原则：

1. **全链路国内源** —— apt / pip / npm / apk / uv / HuggingFace / 模型权重全部走国内镜像，构建不依赖海外网络。
2. **镜像托管在阿里云 ACR** —— 第三方基础镜像先中转进自己的仓库，业务镜像构建后推送到同一命名空间。

## 仓库信息

配置集中在 [`registry.env`](registry.env)，改一处即可整体切换：

| 项 | 值 |
|----|----|
| Registry | `crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com` |
| 命名空间 | `llm-basic` |
| 版本标签 | `1.0.0`（可在构建时用 `-Tag` 覆盖） |
| 业务镜像前缀 | `.../llm-basic/<component>:<tag>` |
| 基础镜像前缀 | `.../llm-basic/base/<name>:<tag>` |

## 前置条件

```bash
# 1) 登录阿里云 ACR（脚本不保存凭据，依赖宿主机登录态）
docker login crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com

# 2) 首次使用必须先把第三方基础镜像中转进自己的仓库
cd _common && ./prepull.sh          # 或 PowerShell: .\prepull.ps1
```

GPU 组件（gander、speech-to-speech）还需要 NVIDIA Driver ≥ 535 与 nvidia-container-toolkit。

## 组件索引

| 目录 | 组件 | 镜像产物 | 类型 |
|------|------|----------|------|
| [`mem0/`](mem0) | 长记忆服务 REST API + Dashboard | `mem0-api`、`mem0-dashboard` | 源码构建 |
| [`nginx/`](nginx) | Dify 网关 + Marketplace 缓存代理 | `mwb-nginx-gateway` | 配置构建 |
| [`remote-dify/`](remote-dify) | Dify 1.17.1 服务端编排 | 仅中转官方镜像 | 编排 |
| [`sqlbot/`](sqlbot) | Text2SQL 问数服务 | `sqlbot` | 源码构建 |
| [`paddleOCR/`](paddleOCR) | PP-OCRv6 CPU 推理 | `pp-ocrv6` | 源码构建 |
| [`speech-to-speech/`](speech-to-speech) | 实时语音对话 pipeline | `s2s-pipeline` | 源码构建（GPU） |
| [`gander/`](gander) | 全双工多模态交互 | `gander-thinker`、`gander-asr` | 源码构建（GPU） |

每个组件目录结构一致：

```
<component>/
├── Dockerfile*            # 构建定义
├── docker-compose.yml     # 本地/服务器编排
├── build.{ps1,sh}         # 构建（Windows / Linux 双端）
├── push.{ps1,sh}          # 打标签并推送到 ACR
├── .env.example           # 环境变量模板（真实值不入库）
└── README.md              # 组件专属说明
```

## 一键命令

```powershell
# Windows —— 构建全部组件
.\build-all.ps1
# 只构建指定组件
.\build-all.ps1 -Component mem0,sqlbot
# 推送到阿里云（需先 docker login）
.\push-all.ps1
# 导出离线 tar 包到 dist/
.\save-all.ps1
# 上传并部署到远端 Ubuntu 服务器
.\deploy-remote.ps1 -Host 192.168.40.30 -User wan
```

```bash
# Linux —— 参数与 PowerShell 版本一一对应
./build-all.sh --component mem0,sqlbot
./push-all.sh
```

## 源码路径

部分组件从外部源码 checkout 构建，路径通过 `-SourceRoot` 注入（Linux 为 `--source-root`），
Dockerfile 内不存在任何硬编码的绝对路径：

| 组件 | 本地源码路径 | 构建上下文 |
|------|-------------|-----------|
| gander | `D:\projects\Omni-Interaction-Agent` | 仓库根 |
| paddleOCR | `D:\projects\github\PaddleOCR` | 仓库根 |
| speech-to-speech | `D:\work\speech-to-speech` | 仓库根 |
| sqlbot | `D:\work\chat-bi\SQLBot` | 仓库根 |
| mem0 | mem0 官方仓库 `server/` | `server/`、`server/dashboard/` |

缺省值写在各组件的 `build.ps1` 顶部，按需修改即可。

## 安全约定

- 脚本**不落任何凭据**，登录由使用者在宿主机完成；`push-*` 检测到未登录即退出。
- 组件密钥一律走 `.env`（已被 `.gitignore` 忽略），仓库只提供 `.env.example` 占位。
- 历史提交中已存在的明文口令请在部署时轮换，参见各组件 README 的安全小节。

## 故障速查

| 现象 | 原因 | 处理 |
|------|------|------|
| `pull access denied` | 未登录或命名空间错 | `docker login` + 检查 `registry.env` |
| `manifest unknown` | base 镜像未中转 | 先跑 `_common/prepull.*` |
| 容器内 `exec format error` | 脚本是 CRLF | Dockerfile 内已加 `sed -i 's/\r$//'`，重新构建即可 |
| pip 卡在下载大 wheel | 源回源慢 | 华为云备源 / paddle 走离线 wheel，见组件 README |
| 语音服务 `trouble responding` | nltk punkt 缺失 | 见 `speech-to-speech/README.md` 补丁说明 |
| 远端 80 端口起不来 | GPUStack 容器占用 | 换个端口，如 8080 |
