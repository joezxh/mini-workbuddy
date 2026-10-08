<#
.SYNOPSIS
    构建 SQLBot 镜像。

.DESCRIPTION
    SQLBot 的前端会把 VITE_SECRET_KEY 内联进构建产物，因此构建必须知道它。
    -SecretKey 未显式传入时，尝试从本目录 .env 的 SECRET_KEY 读取，都没有则报错。

.PARAMETER SourceRoot
    SQLBot 源码根目录（含 backend/、frontend/、g2-ssr/、start.sh）。

.PARAMETER SecretKey
    与运行期 SECRET_KEY 完全一致的前端加密密钥。

.EXAMPLE
    .\build.ps1 -SourceRoot D:\work\chat-bi\SQLBot
    .\build.ps1 -SourceRoot D:\work\chat-bi\SQLBot -SecretKey my-secret -Force
#>
param(
    [string]$SourceRoot = "D:\work\chat-bi\SQLBot",
    [string]$SecretKey,
    [string]$Tag,
    [switch]$Force,
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# 读取 registry.env
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
# 密钥解析：参数 > 本目录 .env
# ------------------------------------------------------------------
if (-not $SecretKey) {
    $dotEnv = Join-Path $PSScriptRoot ".env"
    if (Test-Path $dotEnv) {
        foreach ($raw in (Get-Content $dotEnv)) {
            $line = $raw.Trim()
            if ($line -eq "" -or $line.StartsWith("#")) { continue }
            $kv = $line -split "=", 2
            if ($kv.Count -eq 2 -and $kv[0].Trim() -eq "SECRET_KEY") { $SecretKey = $kv[1].Trim() }
        }
    }
}

if (-not $SecretKey -or $SecretKey -eq "CHANGE_ME_RANDOM_STRING") {
    Write-Host "[ERROR] 缺少 SecretKey。" -ForegroundColor Red
    Write-Host "        前端会把密钥内联进构建产物，必须与运行期 SECRET_KEY 一致。" -ForegroundColor White
    Write-Host "        用法：.\build.ps1 -SecretKey <密钥>  或在 .env 中配置 SECRET_KEY" -ForegroundColor White
    exit 1
}

if (-not (Test-Path $SourceRoot)) {
    Write-Host "[ERROR] 源码目录不存在：$SourceRoot" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# 构建
# ------------------------------------------------------------------
$image = "sqlbot"
$remote = "$registry/${image}:$Tag"
$local  = "${image}:local"

if (-not $Force) {
    if (docker images -q $remote 2>$null) {
        Write-Host "[SKIP] $remote 已存在（重建加 -Force）" -ForegroundColor DarkGray
        exit 0
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SQLBot 构建  tag=$Tag" -ForegroundColor Cyan
Write-Host "  源码：$SourceRoot" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$args = @(
    "build",
    "-f", (Join-Path $PSScriptRoot "Dockerfile"),
    "--build-arg", "SQLBOT_SECRET_KEY=$SecretKey",
    "-t", $remote,
    "-t", $local
)
if ($NoCache) { $args += "--no-cache" }
$args += @("--progress=plain", $SourceRoot)

docker @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] SQLBot 构建失败" -ForegroundColor Red
    exit 1
}

Write-Host "[ OK ] $remote" -ForegroundColor Green
Write-Host "下一步：.\push.ps1"
