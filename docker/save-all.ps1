<#
.SYNOPSIS
    把已构建的镜像导出为离线 tar 包到 dist/ 目录。

.DESCRIPTION
    用于「本地 Windows 构建 → pscp 传到 Ubuntu 服务器 → docker load」的部署链路。
    本地不存在的镜像会自动跳过，不会因为漏构建某个组件而中断。

.PARAMETER Image
    额外追加的镜像名列表。

.PARAMETER OutDir
    输出目录，默认 dist/。

.EXAMPLE
    .\save-all.ps1
    .\save-all.ps1 -OutDir D:\tmp\offline
#>
param(
    [string[]]$Image = @(),
    [string]$Tag,
    [string]$OutDir = (Join-Path $PSScriptRoot "dist")
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$registryEnv = Join-Path $PSScriptRoot "registry.env"
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

# 全部产物清单（与 build-all 的组件一一对应）
$images = @(
    "mem0-api",
    "mem0-dashboard",
    "mwb-nginx-gateway",
    "sqlbot",
    "pp-ocrv6",
    "pp-structurev3",
    "s2s-pipeline",
    "gander-asr",
    "gander-thinker"
) + $Image

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  导出离线镜像包 → $OutDir" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$saved = 0; $missed = 0
foreach ($img in $images) {
    $full = "$registry/${img}:$Tag"
    if (-not (docker images -q $full 2>$null)) {
        Write-Host "[MISS] $full（未构建，跳过）" -ForegroundColor DarkGray
        $missed++
        continue
    }
    $tar = Join-Path $OutDir "$img-$Tag.tar"
    Write-Host "[SAVE] $full" -ForegroundColor Yellow
    docker save $full -o $tar
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] 导出失败：$full" -ForegroundColor Red
        continue
    }
    $size = [math]::Round((Get-Item $tar).Length / 1MB, 1)
    Write-Host "       → $tar (${size} MB)" -ForegroundColor Gray
    $saved++
}

Write-Host ""
Write-Host "导出完成：成功 $saved / 缺失 $missed" -ForegroundColor Cyan
if ($saved -gt 0) {
    Write-Host ""
    Write-Host "上传到服务器：" -ForegroundColor White
    Write-Host "  .\deploy-remote.ps1 -Host <ip> -User <user>" -ForegroundColor Gray
}
