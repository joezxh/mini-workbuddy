<#
.SYNOPSIS
    把 dist/ 下的离线镜像包上传到 Ubuntu 服务器并加载 / 启动。

.DESCRIPTION
    通道基于 plink / pscp（默认位于 D:\tools）。SSH 首选密钥搬运(pageant / -i)，
    也可在运行时交互输入口令 —— 口令不会被写入任何文件。

.PARAMETER Host
    目标服务器 IP 或主机名。

.PARAMETER User
    SSH 用户名，默认 root。

.PARAMETER KeyFile
    PuTTY 私钥路径（.ppk），缺省则依赖 pageant 或交互口令。

.PARAMETER RemoteDir
    远端存放目录，默认 ~/mwb-offline。

.PARAMETER ComposeFile
    可选：加载完成后在远端执行的 compose 文件（相对 RemoteDir/stack）。

.EXAMPLE
    .\deploy-remote.ps1 -Host 192.168.40.30 -User wan
    .\deploy-remote.ps1 -Host 192.168.40.30 -User wan -ComposeFile docker-compose.gpustack.yml
#>
param(
    [Parameter(Mandatory = $true)][string]$HostIp,
    [string]$User = "root",
    [string]$KeyFile,
    [string]$RemoteDir = "~/mwb-offline",
    [string]$ComposeFile,
    [string]$ToolDir = "D:\tools"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$plink = Join-Path $ToolDir "plink.exe"
$pscp  = Join-Path $ToolDir "pscp.exe"
foreach ($tool in @($plink, $pscp)) {
    if (-not (Test-Path $tool)) {
        Write-Host "[ERROR] 找不到工具：$tool" -ForegroundColor Red
        Write-Host "        请在 $ToolDir 放置 plink.exe / pscp.exe，或用 -ToolDir 指定。" -ForegroundColor White
        exit 1
    }
}

$distDir = Join-Path $PSScriptRoot "dist"
$tars = @(Get-ChildItem $distDir -Filter "*.tar" -ErrorAction SilentlyContinue)
if ($tars.Count -eq 0) {
    Write-Host "[ERROR] dist/ 下没有 tar 包，请先运行 .\save-all.ps1" -ForegroundColor Red
    exit 1
}

# plink / pscp 的公共参数：默认接受首次连接的主机密钥，自动 Yes 所有交互
$commonArgs = @("-batch")
if ($KeyFile) { $commonArgs += @("-i", $KeyFile) }
else { Write-Host "[INFO] 未指定 -KeyFile，将依赖 pageant 或交互输入口令" -ForegroundColor Gray }

$target = "$User@$HostIp"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  离线部署 → $target" -ForegroundColor Cyan
Write-Host "  远端目录：$RemoteDir" -ForegroundColor Gray
Write-Host "  待上传  ：$($tars.Count) 个镜像包" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor Cyan

# ------------------------------------------------------------------
# 1) 建立目录（顺带接受主机密钥）
# ------------------------------------------------------------------
Write-Host ""
Write-Host "--- [1/3] 准备远端目录 ---" -ForegroundColor Yellow
Write-Host "y" | & $plink @commonArgs $target "mkdir -p $RemoteDir && docker --version"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] SSH 连接失败或远端无 docker" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# 2) 上传全部 tar
# ------------------------------------------------------------------
Write-Host ""
Write-Host "--- [2/3] 上传镜像包 ---" -ForegroundColor Yellow
foreach ($tar in $tars) {
    Write-Host "[PUT ] $($tar.Name)" -ForegroundColor Yellow
    & $pscp @commonArgs $tar.FullName "${target}:${RemoteDir}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] 上传失败：$($tar.Name)" -ForegroundColor Red
        exit 1
    }
}

# ------------------------------------------------------------------
# 3) 逐个 docker load（拆小命令，避免 plink 长输出截断）
# ------------------------------------------------------------------
Write-Host ""
Write-Host "--- [3/3] 远端加载镜像 ---" -ForegroundColor Yellow
foreach ($tar in $tars) {
    Write-Host "[LOAD] $($tar.Name)" -ForegroundColor Yellow
    & $plink @commonArgs $target "cd $RemoteDir && docker load -i $($tar.Name)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] docker load 失败：$($tar.Name)" -ForegroundColor Red
        exit 1
    }
}

# ------------------------------------------------------------------
# 4) 可选：远端启动编排
# ------------------------------------------------------------------
if ($ComposeFile) {
    Write-Host ""
    Write-Host "--- [4/3] 远端启动编排：$ComposeFile ---" -ForegroundColor Yellow
    & $plink @commonArgs $target "cd $RemoteDir/stack && docker compose -f $ComposeFile up -d"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] compose 启动失败" -ForegroundColor Red
        exit 1
    }
    & $plink @commonArgs $target "cd $RemoteDir/stack && docker compose -f $ComposeFile ps"
}

Write-Host ""
Write-Host "部署完成。" -ForegroundColor Green
Write-Host ""
Write-Host "排障提示：" -ForegroundColor White
Write-Host "  - 远端 80 端口常被 GPUStack 占用，映射冲突时改用其它端口" -ForegroundColor Gray
Write-Host "  - 查看日志：plink $target `"docker compose -f <file> logs -f`"" -ForegroundColor Gray
