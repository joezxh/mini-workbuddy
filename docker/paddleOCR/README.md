# PaddleOCR —— OCR / 版面解析服务

| 产物 | 默认端口 | 说明 |
|------|---------|------|
| `pp-ocrv6` | 8011（仅本机） | PP-OCRv6 Medium 34.5M，CPU 推理 |
| `pp-structurev3` | 8012（仅本机，profile 启用） | 版面解析，CPU 推理，较重 |
| 鉴权网关 | 8080（对外） | 校验 `X-API-Key` 后转发 |

调用示例：

```bash
curl -s -X POST http://localhost:8080/api/ocr \
     -H "X-API-Key: $PADDLE_API_KEY" \
     -F "image=@./doc.png" | jq -r '.data[0].text'
```

健康检查不鉴权：

```bash
curl http://localhost:8080/health    # {"status":"ok","gpu_available":false}
```

## 为什么 paddlepaddle 要走离线 wheel

`paddlepaddle` 的 wheel 约 185MB，实测国内回源速率差异极大：

| 源 | 吞吐 |
|----|------|
| 阿里云 PyPI | 84 KB/s |
| 清华（回源） | 1.6 MB/s |
| 华为云 | 6.1 MB/s |
| pypi.org | 7.2 MB/s |

构建期直接 `pip install paddlepaddle` 经常卡死或中断。因此 `wheels/` 目录做本地缓存：
`build.ps1` / `build.sh` 检测到没有 wheel 时会先从华为云下载（一次），Dockerfile 里再 `COPY wheels/ /wheels/` 离线安装。
wheel **不入库**，由 `.gitignore` 排除。

## 构建

```powershell
# Windows
cd d:\projects\MinWorkBuddy\docker\paddleOCR
.\build.ps1 -SourceRoot D:\projects\github\PaddleOCR
.\build.ps1 -Component structurev3 -Force
```

```bash
# Linux
./build.sh --source-root /opt/PaddleOCR
./build.sh --component structurev3 --force
```

首次构建会从 ModelScope 下载 PP-OCRv6 权重到镜像内的 `/models_cache`（这一步刻意放在构建期：
权重源有问题应当立刻暴露，而不是等到线上第一个请求才失败）。运行期把宿主机卷挂到同一路径，重启不再重下。

## 国内化要点

| 层 | 处理 |
|----|------|
| 基础镜像 | `${BASE_REGISTRY}/python:3.10-slim` |
| apt | 清华源；Debian bookworm 的 `sources.list.d/*.sources` 新格式也一并 sed 处理 |
| pip | 华为云主源 + 阿里云备源 |
| paddlepaddle | 离线 wheel |
| 模型权重 | `PADDLE_PDX_MODEL_SOURCE=modelscope` |

## PP-StructureV3 与 PaddleOCR-VL

- PP-StructureV3（本仓库 `structurev3` 变体）是 CPU 版全链路解析，单页可达数秒。
- 若需要更高吞吐，使用官方 GPU 侧的 `paddleocr-vl` 或 HPS 高性能服务化部署，
  这类镜像体积大且依赖 GPU，未纳入本目录的构建流程。

## 安全提示

对外端口默认带 `X-API-Key` 鉴权，**不要直接把 8011 端口暴露到公网**。
`PADDLE_API_KEY` 请从随机值生成并写入 `.env`（已被 `.gitignore` 忽略）。
