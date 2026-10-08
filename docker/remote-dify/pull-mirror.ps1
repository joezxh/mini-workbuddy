<#
.SYNOPSIS
    把 Dify 官方镜像中转进个人阿里云仓库。

.DESCRIPTION
    Dify 无本地源码构建，所有镜像都来自 langgenius 官方发布。
    本脚本是 ../_common/prepull.ps1 的快捷入口，幂等：
    远端已存在同名镜像则跳过，-Force 才重新拉取覆盖。

.EXAMPLE
    .\pull-mirror.ps1
    .\pull-mirror.ps1 -Force
#>
param(
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$prepull = Join-Path (Split-Path -Parent $PSScriptRoot) "_common\prepull.ps1"
if (-not (Test-Path $prepull)) {
    Write-Host "[ERROR] 找不到 $prepull" -ForegroundColor Red
    exit 1
}

Write-Host "==> 中转 Dify 官方镜像到个人仓库（幂等，重跑只会补齐缺失项）" -ForegroundColor Cyan
& $prepull -Force:$Force -DryRun:$DryRun
exit $LASTEXITCODE
