<#
.SYNOPSIS
    构建 mem0 的 API 与 Dashboard 镜像。

.DESCRIPTION
    从 mem0 官方源码构建两个镜像，同时打上本地 tag（供 docker-compose.yml 使用）
    与远端 ACR tag（供 push.ps1 推送）。

.PARAMETER SourceRoot
    mem0 源码 checkout 根目录，需包含 server/ 与 server/dashboard/。

.PARAMETER Component
    构建目标：api / dashboard / all，默认 all。

.PARAMETER Tag
    镜像版本标签，缺省取 registry.env 的 IMAGE_TAG。

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Component api -SourceRoot D:\projects\github\mem0 -Force
#>
param(
    [string[]]$Component = @("all"),
    [string]$SourceRoot = "D:\projects\github\mem0",
    [string]$Tag,
    [switch]$Force,
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# 读取 registry.env
# ------------------------------------------------------------------
$registryEnv = Join-Path (Split-Path -Parent $PSScriptRoot) "registry.env"
if (-not (Test-Path $registryEnv)) {
    Write-Host "[ERROR] 找不到 $registryEnv" -ForegroundColor Red
    exit 1
}
$envMap = @{}
foreach ($raw in (Get-Content $registryEnv)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    $kv = $line -split "=", 2
    if ($kv.Count -eq 2) { $envMap[$kv[0].Trim()] = $kv[1].Trim() }
}
$registry = $envMap["REGISTRY"]
if (-not $Tag) { $Tag = $envMap["IMAGE_TAG"] }
if (-not $registry -or -not $Tag) {
    Write-Host "[ERROR] registry.env 缺少 REGISTRY / IMAGE_TAG" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# 目标定义
# ------------------------------------------------------------------
$targets = [ordered]@{
    api = @{
        Context    = Join-Path $SourceRoot "server"
        Dockerfile = Join-Path $PSScriptRoot "api\Dockerfile"
        Image      = "mem0-api"
    }
    dashboard = @{
        Context    = Join-Path $SourceRoot "server\dashboard"
        Dockerfile = Join-Path $PSScriptRoot "dashboard\Dockerfile"
        Image      = "mem0-dashboard"
    }
}

if ($Component -contains "all") { $selected = @($targets.Keys) }
else { $selected = $Component }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  mem0 构建  tag=$Tag" -ForegroundColor Cyan
Write-Host "  源码：$SourceRoot" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$failed = @()

foreach ($name in $selected) {
    if (-not $targets.Contains($name)) {
        Write-Host "[WARN] 未知组件：$name" -ForegroundColor DarkYellow
        continue
    }
    $t = $targets[$name]
    $remote = "$registry/$($t.Image):$Tag"
    $local  = "$($t.Image):local"

    if (-not (Test-Path $t.Context)) {
        Write-Host "[ERROR] 源码目录不存在：$($t.Context)" -ForegroundColor Red
        Write-Host "        请确认 mem0 源码已 clone，或用 -SourceRoot 指定路径。" -ForegroundColor White
        $failed += $name
        continue
    }

    # 幂等：已存在且未加 -Force 则跳过
    if (-not $Force) {
        $existing = docker images -q $remote 2>$null
        if ($existing) {
            Write-Host "[SKIP] $remote 已存在" -ForegroundColor DarkGray
            continue
        }
    }

    Write-Host "[BUILD] $($t.Image)  <-  $($t.Context)" -ForegroundColor Yellow

    $buildArgs = @(
        "build",
        "-f", $t.Dockerfile,
        "-t", $remote,
        "-t", $local
    )
    if ($NoCache) { $buildArgs += "--no-cache" }
    $buildArgs += "--progress=plain"
    $buildArgs += $t.Context

    docker @buildArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $($t.Image) 构建失败" -ForegroundColor Red
        $failed += $name
        continue
    }
    Write-Host "[ OK ] $remote" -ForegroundColor Green
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "mem0 构建失败：$($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "mem0 构建完成。下一步：.\push.ps1" -ForegroundColor Green
