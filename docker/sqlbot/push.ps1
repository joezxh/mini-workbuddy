<#
.SYNOPSIS
    推送 SQLBot 镜像到阿里云 ACR。
#>
param(
    [string]$Tag,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$registryEnv = Join-Path (Split-Path -Parent $PSScriptRoot) "registry.env"
if (-not (Test-Path $registryEnv)) { Write-Host "[ERROR] 找不到 $registryEnv" -ForegroundColor Red; exit 1 }

$envMap = @{}
foreach ($raw in (Get-Content $registryEnv)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    $kv = $line -split "=", 2
    if ($kv.Count -eq 2) { $envMap[$kv[0].Trim()] = $kv[1].Trim() }
}
$registryHost = $envMap["REGISTRY_HOST"]
$registry = $envMap["REGISTRY"]
if (-not $Tag) { $Tag = $envMap["IMAGE_TAG"] }

# PowerShell 5.1 兼容写法（不用 ?: 三元运算符）
$cfgDir = if ($env:DOCKER_CONFIG) { $env:DOCKER_CONFIG } else { Join-Path $HOME ".docker" }
$dockerConfig = Join-Path $cfgDir "config.json"
if (-not ((Test-Path $dockerConfig) -and ((Get-Content $dockerConfig -Raw) -match [regex]::Escape($registryHost)))) {
    Write-Host "[ERROR] 未登录 $registryHost ，请先执行：docker login $registryHost" -ForegroundColor Red
    exit 1
}

$remote = "$registry/sqlbot:$Tag"

if (-not (docker images -q $remote 2>$null)) {
    Write-Host "[FAIL] 本地镜像不存在：$remote，请先 build" -ForegroundColor Red
    exit 1
}

Write-Host "[PUSH] $remote" -ForegroundColor Yellow
if (-not $DryRun) {
    docker push $remote
    if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] 推送失败" -ForegroundColor Red; exit 1 }
}
Write-Host "[ OK ] $remote" -ForegroundColor Green
