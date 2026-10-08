<#
.SYNOPSIS
    构建 speech-to-speech pipeline 镜像。

.DESCRIPTION
    会自动把本地准备好的 Silero VAD 仓库搬运进构建上下文
    （容器内连不上 github.com，必须离线预置，否则 VAD 加载失败、8765 无人监听）。

.PARAMETER SourceRoot
    speech-to-speech 源码根目录。

.PARAMETER SileroVadDir
    snakers4/silero-vad 仓库内容目录，需含 hubconf.py。缺省取本目录下 silero-vad/。

.PARAMETER SkipTorchReinstall
    跳过 torch/torchaudio 的 cu128 重装（默认会重装，否则 CUDA 不可用）。

.EXAMPLE
    .\build.ps1 -SourceRoot D:\work\speech-to-speech
    .\build.ps1 -SkipTorchReinstall
#>
param(
    [string]$SourceRoot = "D:\work\speech-to-speech",
    [string]$SileroVadDir = (Join-Path $PSScriptRoot "silero-vad"),
    [string]$TorchIndexUrl = "https://mirrors.aliyun.com/pytorch-wheels/cu128",
    [string]$Tag,
    [switch]$SkipTorchReinstall,
    [switch]$Force,
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# registry.env
# ------------------------------------------------------------------
$registryEnv = Join-Path (Split-Path -Parent $PSScriptRoot) "registry.env"
if (-not (Test-Path $registryEnv)) { Write-Host "[ERROR] 找不到 $registryEnv" -ForegroundColor Red; exit 1 }

$envMap = @{}
foreach ($raw in (Get-Content $registryEnv)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    $kv = $line -split "=", 2
    if ($kv.Count -eq 2) { $envMap[$kv[0].Trim()] = $kv[1].Trim() }
}
$registry = $envMap["REGISTRY"]
if (-not $Tag) { $Tag = $envMap["IMAGE_TAG"] }

# ------------------------------------------------------------------
# 前置校验
# ------------------------------------------------------------------
if (-not (Test-Path $SourceRoot)) {
    Write-Host "[ERROR] 源码目录不存在：$SourceRoot" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $SileroVadDir "hubconf.py"))) {
    Write-Host "[ERROR] Silero VAD 仓库未就位：$SileroVadDir" -ForegroundColor Red
    Write-Host ""
    Write-Host "  VAD/vad_handler.py 使用 torch.hub.load('/opt/silero-vad', source='local')，" -ForegroundColor White
    Write-Host "  容器内连不上 github.com，必须离线预置。请在能访问 GitHub 的机器上执行一次：" -ForegroundColor White
    Write-Host ""
    Write-Host "    git clone --depth 1 https://github.com/snakers4/silero-vad.git" -ForegroundColor Cyan
    Write-Host "    cp -r silero-vad\* $SileroVadDir" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# ------------------------------------------------------------------
# 搬运 Silero VAD 到构建上下文（构建上下文是源码根目录）
# ------------------------------------------------------------------
$staging = Join-Path $SourceRoot ".docker-build\silero-vad"
Write-Host "[PREP] 准备 Silero VAD → $staging" -ForegroundColor Yellow
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
Copy-Item (Join-Path $SileroVadDir "*") $staging -Recurse -Force

# ------------------------------------------------------------------
# 构建
# ------------------------------------------------------------------
$image = "s2s-pipeline"
$remote = "$registry/${image}:$Tag"
$local  = "${image}:local"

if (-not $Force -and (docker images -q $remote 2>$null)) {
    Write-Host "[SKIP] $remote 已存在（重建加 -Force）" -ForegroundColor DarkGray
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  speech-to-speech 构建  tag=$Tag" -ForegroundColor Cyan
Write-Host "  源码：$SourceRoot" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$args = @(
    "build",
    "-f", (Join-Path $PSScriptRoot "Dockerfile"),
    "--build-arg", "TORCH_INDEX_URL=$TorchIndexUrl",
    "--build-arg", "SKIP_TORCH_REINSTALL=$([int]$SkipTorchReinstall.IsPresent)",
    "-t", $remote,
    "-t", $local
)
if ($NoCache) { $args += "--no-cache" }
$args += @("--progress=plain", $SourceRoot)

docker @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] 构建失败" -ForegroundColor Red
    exit 1
}

Write-Host "[ OK ] $remote" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：.\push.ps1    启动：docker compose -f docker-compose.gpustack.yml up -d" -ForegroundColor Gray
