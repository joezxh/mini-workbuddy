<#
.SYNOPSIS
    一键推送所有组件镜像到阿里云 ACR。

.DESCRIPTION
    先校验宿主机登录态，再按依赖顺序调用各组件的 push.ps1。
    脚本不保存任何凭据，未登录直接退出。

.PARAMETER Component
    组件列表，支持 all（默认）。mem0、nginx、sqlbot、paddleocr、s2s、gander

.EXAMPLE
    .\push-all.ps1
    .\push-all.ps1 -Component mem0 -DryRun
#>
param(
    [string[]]$Component = @("all"),
    [string]$Tag,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ------------------------------------------------------------------
# 读取 registry.env + 登录态校验
# ------------------------------------------------------------------
$registryEnv = Join-Path $PSScriptRoot "registry.env"
if (-not (Test-Path $registryEnv)) { Write-Host "[ERROR] 找不到 $registryEnv" -ForegroundColor Red; exit 1 }

$envMap = @{}
foreach ($raw in (Get-Content $registryEnv)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    $kv = $line -split "=", 2
    if ($kv.Count -eq 2) { $envMap[$kv[0].Trim()] = $kv[1].Trim() }
}
$registryHost = $envMap["REGISTRY_HOST"]
if (-not $Tag) { $Tag = $envMap["IMAGE_TAG"] }

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  推送到 $registryHost（tag=$Tag）" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# PowerShell 5.1 兼容写法（不用 ?: 三元运算符）
$cfgDir = if ($env:DOCKER_CONFIG) { $env:DOCKER_CONFIG } else { Join-Path $HOME ".docker" }
$dockerConfig = Join-Path $cfgDir "config.json"
if (-not ((Test-Path $dockerConfig) -and ((Get-Content $dockerConfig -Raw) -match [regex]::Escape($registryHost)))) {
    Write-Host ""
    Write-Host "[ERROR] 未检测到 $registryHost 的登录凭据。" -ForegroundColor Red
    Write-Host "        请先执行：docker login $registryHost" -ForegroundColor White
    Write-Host "        （脚本不保存密码，凭据由 Docker 凭据管理器托管）" -ForegroundColor Gray
    exit 1
}

$components = [ordered]@{
    nginx     = "nginx"
    mem0      = "mem0"
    sqlbot    = "sqlbot"
    paddleocr = "paddleOCR"
    s2s       = "speech-to-speech"
    gander    = "gander"
}

if ($Component -contains "all") { $selected = @($components.Keys) } else { $selected = $Component }

$results = @()
foreach ($name in $selected) {
    if (-not $components.Contains($name)) { Write-Host "[WARN] 未知组件：$name" -ForegroundColor DarkYellow; continue }

    $script = Join-Path $PSScriptRoot "$($components[$name])\push.ps1"
    if (-not (Test-Path $script)) {
        $results += [pscustomobject]@{ Component = $name; Result = "SKIP" }
        continue
    }

    Write-Host ""
    Write-Host ">>> [$name]" -ForegroundColor Cyan
    $extra = @()
    if ($Tag) { $extra += @("-Tag", $Tag) }
    if ($DryRun) { $extra += "-DryRun" }

    & $script @extra
    if ($LASTEXITCODE -eq 0) { $results += [pscustomobject]@{ Component = $name; Result = "OK" } }
    else { $results += [pscustomobject]@{ Component = $name; Result = "FAIL" } }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  推送结果汇总" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
$results | Format-Table -AutoSize

if (($results | Where-Object { $_.Result -eq "FAIL" }).Count -gt 0) { exit 1 }
Write-Host "全部推送完成。" -ForegroundColor Green
