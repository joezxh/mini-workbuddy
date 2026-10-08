<#
.SYNOPSIS
    构建 Gander 镜像（本地 ASR 变体 / 远端 Thinker 变体）。

.DESCRIPTION
    local  → gander-asr：faster-whisper ASR + Nginx 反代
    remote → gander-thinker：编码器 + Talker TTS

    构建上下文必须是 Omni-Interaction-Agent 仓库根目录（需要 minicpm_ft/ 与 gander_runtime/），
    因此脚本会把本目录下的 Dockerfile 同级资产暂存到源码根的 .docker-build/ 后再构建。

.EXAMPLE
    .\build.ps1 -Variant local
    .\build.ps1 -Variant all -SourceRoot D:\projects\Omni-Interaction-Agent -Force
#>
param(
    [ValidateSet("local", "remote", "all")]
    [string]$Variant = "local",
    [string]$SourceRoot = "D:\projects\Omni-Interaction-Agent",
    [string]$TorchIndexUrl = "https://mirrors.aliyun.com/pytorch-wheels/cu124",
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

if (-not (Test-Path $SourceRoot)) {
    Write-Host "[ERROR] 源码目录不存在：$SourceRoot" -ForegroundColor Red
    exit 1
}
foreach ($required in @("minicpm_ft", "gander_runtime")) {
    if (-not (Test-Path (Join-Path $SourceRoot $required))) {
        Write-Host "[ERROR] 源码目录缺少子目录：$required" -ForegroundColor Red
        exit 1
    }
}

# ------------------------------------------------------------------
# 暂存 Dockerfile 同级资产到构建上下文
# ------------------------------------------------------------------
$staging = Join-Path $SourceRoot ".docker-build"
Write-Host "[PREP] 暂存构建资产 → $staging" -ForegroundColor Yellow
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path (Join-Path $staging "nginx") -Force | Out-Null
Copy-Item (Join-Path $PSScriptRoot "nginx\default.conf.tmpl") (Join-Path $staging "nginx") -Force
Copy-Item (Join-Path $PSScriptRoot "entrypoint_local.sh") $staging -Force

# ------------------------------------------------------------------
# 变体定义
# ------------------------------------------------------------------
$targets = [ordered]@{
    local = @{
        Dockerfile = Join-Path $PSScriptRoot "Dockerfile.local"
        Image      = "gander-asr"
    }
    remote = @{
        Dockerfile = Join-Path $PSScriptRoot "Dockerfile.remote"
        Image      = "gander-thinker"
    }
}

$selected = if ($Variant -eq "all") { @($targets.Keys) } else { @($Variant) }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Gander 构建  tag=$Tag  variant=$Variant" -ForegroundColor Cyan
Write-Host "  源码：$SourceRoot" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$failed = @()
foreach ($name in $selected) {
    $t = $targets[$name]
    $remoteImg = "$registry/$($t.Image):$Tag"
    $localImg  = "$($t.Image):local"

    if (-not $Force -and (docker images -q $remoteImg 2>$null)) {
        Write-Host "[SKIP] $remoteImg 已存在" -ForegroundColor DarkGray
        continue
    }

    Write-Host "[BUILD] $($t.Image)（torch 从国内索引安装，首次较慢）" -ForegroundColor Yellow
    $args = @(
        "build",
        "-f", $t.Dockerfile,
        "--build-arg", "TORCH_INDEX_URL=$TorchIndexUrl",
        "-t", $remoteImg,
        "-t", $localImg
    )
    if ($NoCache) { $args += "--no-cache" }
    $args += @("--progress=plain", $SourceRoot)

    docker @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $($t.Image) 构建失败" -ForegroundColor Red
        $failed += $name
        continue
    }
    Write-Host "[ OK ] $remoteImg" -ForegroundColor Green
}

Write-Host ""
if ($failed.Count -gt 0) { Write-Host "构建失败：$($failed -join ', ')" -ForegroundColor Red; exit 1 }
Write-Host "Gander 构建完成。下一步：.\push.ps1 -Variant $Variant" -ForegroundColor Green
