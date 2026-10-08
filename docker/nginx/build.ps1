<#
.SYNOPSIS
    构建统一网关镜像（mwb-nginx-gateway）。

.DESCRIPTION
    镜像内所有配置均为模板，运行时靠环境变量渲染下游地址与端口，
    因此构建阶段不需要任何外部参数。

.PARAMETER Tag
    版本标签，缺省取 registry.env 的 IMAGE_TAG。
#>
param(
    [string]$Tag,
    [switch]$Force,
    [switch]$NoCache
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
$registry = $envMap["REGISTRY"]
if (-not $Tag) { $Tag = $envMap["IMAGE_TAG"] }

$image = "mwb-nginx-gateway"
$remote = "$registry/${image}:$Tag"
$local  = "${image}:local"

if (-not $Force) {
    if (docker images -q $remote 2>$null) {
        Write-Host "[SKIP] $remote 已存在" -ForegroundColor DarkGray
        Write-Host "如需重建请加 -Force" -ForegroundColor Gray
        exit 0
    }
}

Write-Host "[BUILD] $remote" -ForegroundColor Yellow
$args = @("build", "-t", $remote, "-t", $local)
if ($NoCache) { $args += "--no-cache" }
$args += @("--progress=plain", $PSScriptRoot)

docker @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] 网关镜像构建失败" -ForegroundColor Red
    exit 1
}
Write-Host "[ OK ] $remote" -ForegroundColor Green
Write-Host "下一步：.\push.ps1"
