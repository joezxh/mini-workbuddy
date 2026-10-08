<#
.SYNOPSIS
    推送 PaddleOCR 镜像到阿里云 ACR。
#>
param(
    [string[]]$Component = @("ppocrv6"),
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

$map = @{ ppocrv6 = "pp-ocrv6"; structurev3 = "pp-structurev3" }
if ($Component -contains "all") { $names = @($map.Keys) } else { $names = $Component }

$failed = @()
foreach ($name in $names) {
    $img = $map[$name]
    $remote = "$registry/${img}:$Tag"
    if (-not (docker images -q $remote 2>$null)) {
        Write-Host "[SKIP] 本地无 $remote（未构建则跳过）" -ForegroundColor DarkGray
        continue
    }
    Write-Host "[PUSH] $remote" -ForegroundColor Yellow
    if ($DryRun) { continue }
    docker push $remote
    if ($LASTEXITCODE -ne 0) { $failed += $name } else { Write-Host "[ OK ] $remote" -ForegroundColor Green }
}

if ($failed.Count -gt 0) { Write-Host "推送失败：$($failed -join ', ')" -ForegroundColor Red; exit 1 }
Write-Host "PaddleOCR 镜像推送完成。" -ForegroundColor Green
