<#
.SYNOPSIS
    推送 mem0 镜像到阿里云 ACR。

.DESCRIPTION
    只做 tag + push，不保存任何凭据。推送前检查宿主机登录态，未登录直接退出。
    若本地没有 <registry>/mem0-api:<tag>，会自动从 mem0-api:local 补打标签。

.PARAMETER Tag
    版本标签，缺省取 registry.env 的 IMAGE_TAG。

.PARAMETER DryRun
    只打印将要执行的 push 命令。
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

# 登录态检查
# PowerShell 5.1 兼容写法（不用 ?: 三元运算符）
$cfgDir = if ($env:DOCKER_CONFIG) { $env:DOCKER_CONFIG } else { Join-Path $HOME ".docker" }
$dockerConfig = Join-Path $cfgDir "config.json"
if (-not ((Test-Path $dockerConfig) -and ((Get-Content $dockerConfig -Raw) -match [regex]::Escape($registryHost)))) {
    Write-Host "[ERROR] 未登录 $registryHost ，请先执行：docker login $registryHost" -ForegroundColor Red
    exit 1
}

$images = @("mem0-api", "mem0-dashboard")
$failed = @()

foreach ($img in $images) {
    $remote = "$registry/${img}:$Tag"
    $local  = "${img}:local"

    if (-not (docker images -q $remote 2>$null)) {
        if (docker images -q $local 2>$null) {
            Write-Host "[TAG ] $local -> $remote" -ForegroundColor Yellow
            if (-not $DryRun) { docker tag $local $remote }
        } else {
            Write-Host "[FAIL] 本地既无 $remote 也无 $local，请先 build" -ForegroundColor Red
            $failed += $img
            continue
        }
    }

    Write-Host "[PUSH] $remote" -ForegroundColor Yellow
    if ($DryRun) { continue }
    docker push $remote
    if ($LASTEXITCODE -ne 0) { $failed += $img } else { Write-Host "[ OK ] $remote" -ForegroundColor Green }
}

if ($failed.Count -gt 0) { Write-Host "推送失败：$($failed -join ', ')" -ForegroundColor Red; exit 1 }
Write-Host "mem0 镜像推送完成。" -ForegroundColor Green
