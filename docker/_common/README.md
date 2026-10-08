# 公共层说明

本目录存放被所有组件共享的构建资产：**镜像源清单**、**第三方基础镜像中转**。

## 文件清单

| 文件 | 用途 |
|------|------|
| `../registry.env` | 镜像仓库地址、命名空间、版本标签（唯一配置源） |
| `mirrors.env` | apt / pip / npm / apk / uv / HuggingFace / Paddle 模型 的国内源清单 |
| `prepull-images.txt` | 需要中转的第三方基础镜像白名单（每行 `源镜像 目标名`） |
| `prepull.ps1` / `prepull.sh` | 按白名单拉取 → 改标签 → 推送到个人仓库 `base/*` |

## 为什么要有基础镜像中转

三个现实约束：

1. `nvidia/cuda` 系列镜像走 daemon.json 配置的加速器会**卡死**（实测）；可行做法是先从国内可达的 proxy registry 预拉，再 `docker tag` 成官方名让构建跳过基础层。
2. GPU 服务器往往不配加速器（服务器出来了也没配），`FROM nvidia/cuda:xxx` 直接失败。
3. Docker Hub 限流会随机让 CI 挂掉。

中转之后的效果：**所有 Dockerfile 的 `FROM` 只指向自己的阿里云仓库**，任何一台加了 login 的机器都能原样构建。

## 中转流程

```
海外/公共 registry ──(经 proxy registry 或直连)──► 本地缓存
                                                    │ docker tag
                                                    ▼
                       ${BASE_REGISTRY}/<name>:<tag>  ──docker push──►  阿里云 ACR
```

`prepull-images.txt` 每行两列：

```
nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04  base/nvidia-cuda:12.8.1-cudnn-runtime-ubuntu24.04
```

第二列省略时默认取 `base/<源镜像最后一段的仓库名>:<tag>`。

## 使用方法

```powershell
# Windows
cd d:\projects\MinWorkBuddy\docker\_common
.\prepull.ps1                 # 中转全部（已存在则跳过）
.\prepull.ps1 -Force          # 强制重新拉取并覆盖
```

```bash
# Linux
cd /path/to/MinWorkBuddy/docker/_common
./prepull.sh
./prepull.sh --force
```

前提是宿主机已登录：

```bash
docker login crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com
```

脚本不保存也不接受任何凭据，未登录会直接报错退出。

## 新增一个基础镜像

1. 在 `prepull-images.txt` 追加一行。
2. 在对应组件的 Dockerfile 把 `FROM` 改为 `${BASE_REGISTRY}/base/<name>:<tag>`。
3. 重跑 `prepull` 让新镜像入库后再构建组件。
