<#
.SYNOPSIS
    构建 PaddleOCR 的 OCR 服务镜像。

.DESCRIPTION
    支持两个变体：
      ppocrv6      PP-OCRv6 CPU 文本识别（默认）
      structurev3  PP-StructureV3 版面解析（较重）

    paddlepaddle 的 wheel 约 185MB，直连 PyPI 在国内极易抖动。
    脚本会先检查 wheels/ 目录，缺 wheel 时自动从华为云镜像源下载，
    再由 Dockerfile 以 COPY 方式离线安装。

.PARAMETER SourceRoot
    PaddleOCR 源码仓库根目录。

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Component structurev3 -Force
#>
param(
    [string[]]$Component = @("ppocrv6"),
    [string]$SourceRoot = "D:\projects\github\PaddleOCR",
    [string]$PaddleVersion = "3.3.0",
    [string]$Tag,
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
# 源码检查
# ------------------------------------------------------------------
if (-not (Test-Path $SourceRoot)) {
    Write-Host "[ERROR] 源码目录不存在：$SourceRoot" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# paddlepaddle wheel 准备（离线化，避免构建期抖动）
# ------------------------------------------------------------------
$wheelDir = Join-Path $PSScriptRoot "wheels"
if (-not (Test-Path $wheelDir)) { New-Item -ItemType Directory -Path $wheelDir -Force | Out-Null }

$wheels = @(Get-ChildItem $wheelDir -Filter "paddlepaddle*.whl" -ErrorAction SilentlyContinue)
if ($wheels.Count -eq 0) {
    Write-Host "[PREP] 下载 paddlepaddle==$PaddleVersion wheel 到 wheels/（华为云源）..." -ForegroundColor Yellow
    pip download -i https://repo.huaweicloud.com/repository/pypi/simple --no-deps -d $wheelDir "paddlepaddle==$PaddleVersion"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] wheel 下载失败，可手动下载后放入 wheels/ 目录" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[PREP] 复用已有 wheel：$($wheels[0].Name)" -ForegroundColor Gray
}

# ------------------------------------------------------------------
# 变体定义
# ------------------------------------------------------------------
$targets = [ordered]@{
    ppocrv6 = @{
        Dockerfile = Join-Path $PSScriptRoot "Dockerfile.ppocrv6"
        Image      = "pp-ocrv6"
    }
    structurev3 = @{
        Dockerfile = Join-Path $PSScriptRoot "Dockerfile.structurev3"
        Image      = "pp-structurev3"
    }
}

if ($Component -contains "all") { $selected = @($targets.Keys) } else { $selected = $Component }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PaddleOCR 构建  tag=$Tag" -ForegroundColor Cyan
Write-Host "  源码：$SourceRoot" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$failed = @()
foreach ($name in $selected) {
    if (-not $targets.Contains($name)) { Write-Host "[WARN] 未知变体：$name" -ForegroundColor DarkYellow; continue }
    $t = $targets[$name]
    $remote = "$registry/$($t.Image):$Tag"
    $local  = "$($t.Image):local"

    if (-not $Force -and (docker images -q $remote 2>$null)) {
        Write-Host "[SKIP] $remote 已存在" -ForegroundColor DarkGray
        continue
    }

    Write-Host "[BUILD] $($t.Image)（首次构建会下载 PP-OCRv6 权重，耗时较长）" -ForegroundColor Yellow
    $args = @("build", "-f", $t.Dockerfile, "-t", $remote, "-t", $local)
    if ($NoCache) { $args += "--no-cache" }
    $args += @("--progress=plain", $SourceRoot)

    docker @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $($t.Image) 构建失败" -ForegroundColor Red
        $failed += $name
        continue
    }
    Write-Host "[ OK ] $remote" -ForegroundColor Green
}

Write-Host ""
if ($failed.Count -gt 0) { Write-Host "构建失败：$($failed -join ', ')" -ForegroundColor Red; exit 1 }
Write-Host "PaddleOCR 构建完成。下一步：.\push.ps1" -ForegroundColor Green
