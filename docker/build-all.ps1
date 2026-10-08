<#
.SYNOPSIS
    一键构建全部（或指定）组件镜像。

.DESCRIPTION
    执行顺序：
      1) 确保第三方基础镜像已中转进个人仓库（_common/prepull.ps1，幂等）
      2) 按依赖顺序调用各组件的 build.ps1

.PARAMETER Component
    组件列表，支持 all（默认）。可选值：
    mem0、nginx、sqlbot、paddleocr、s2s、gander

.PARAMETER SkipPrepull
    跳过基础镜像中转步骤（基础层已就绪时可加速）。

.PARAMETER SourceRoots
    覆盖组件源码路径，形如 @{ mem0='D:\src\mem0'; sqlbot='D:\src\SQLBot' }。

.EXAMPLE
    .\build-all.ps1
    .\build-all.ps1 -Component mem0,sqlbot -SkipPrepull
#>
param(
    [string[]]$Component = @("all"),
    [hashtable]$SourceRoots = @{},
    [string]$Tag,
    [switch]$SkipPrepull,
    [switch]$Force,
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  MinWorkBuddy 组件镜像构建" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# ------------------------------------------------------------------
# Step 1: 基础镜像中转
# ------------------------------------------------------------------
if (-not $SkipPrepull) {
    Write-Host ""
    Write-Host "--- [1/2] 基础镜像中转（幂等，已有则跳过）---" -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "_common\prepull.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 基础镜像中转失败，后续构建大概率会去拉海外源，已中止。" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "--- [1/2] 已跳过基础镜像中转 ---" -ForegroundColor DarkGray
}

# ------------------------------------------------------------------
# Step 2: 组件构建
# ------------------------------------------------------------------
Write-Host ""
Write-Host "--- [2/2] 组件镜像构建 ---" -ForegroundColor Yellow

$components = [ordered]@{
    mem0      = @{ Dir = "mem0";             Args = @() }
    nginx     = @{ Dir = "nginx";            Args = @() }
    sqlbot    = @{ Dir = "sqlbot";           Args = @() }
    paddleocr = @{ Dir = "paddleOCR";        Args = @() }
    s2s       = @{ Dir = "speech-to-speech"; Args = @() }
    gander    = @{ Dir = "gander";           Args = @("-Variant", "all") }
}

if ($Component -contains "all") { $selected = @($components.Keys) } else { $selected = $Component }

$results = @()
foreach ($name in $selected) {
    if (-not $components.Contains($name)) {
        Write-Host "[WARN] 未知组件：$name" -ForegroundColor DarkYellow
        continue
    }

    $dir = $components[$name].Dir
    $script = Join-Path $PSScriptRoot "$dir\build.ps1"
    if (-not (Test-Path $script)) {
        Write-Host "[SKIP] $name 缺少 build.ps1" -ForegroundColor DarkGray
        $results += [pscustomobject]@{ Component = $name; Result = "SKIP" }
        continue
    }

    Write-Host ""
    Write-Host ">>> [$name] $dir" -ForegroundColor Cyan

    $extra = @($components[$name].Args)
    # 源码路径覆盖
    switch ($name) {
        "mem0"      { if ($SourceRoots.ContainsKey("mem0"))      { $extra += @("-SourceRoot", $SourceRoots["mem0"]) } }
        "sqlbot"    { if ($SourceRoots.ContainsKey("sqlbot"))    { $extra += @("-SourceRoot", $SourceRoots["sqlbot"]) } }
        "paddleocr" { if ($SourceRoots.ContainsKey("paddleocr")) { $extra += @("-SourceRoot", $SourceRoots["paddleocr"]) } }
        "s2s"       { if ($SourceRoots.ContainsKey("s2s"))       { $extra += @("-SourceRoot", $SourceRoots["s2s"]) } }
        "gander"    { if ($SourceRoots.ContainsKey("gander"))    { $extra += @("-SourceRoot", $SourceRoots["gander"]) } }
    }
    if ($Tag)                   { $extra += @("-Tag", $Tag) }
    if ($Force)                 { $extra += "-Force" }
    if ($NoCache)               { $extra += "-NoCache" }

    & $script @extra
    if ($LASTEXITCODE -eq 0) {
        $results += [pscustomobject]@{ Component = $name; Result = "OK" }
    } else {
        $results += [pscustomobject]@{ Component = $name; Result = "FAIL" }
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  构建结果汇总" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
$results | Format-Table -AutoSize

if (($results | Where-Object { $_.Result -eq "FAIL" }).Count -gt 0) {
    Write-Host "存在失败组件，详见上方日志。" -ForegroundColor Red
    exit 1
}
Write-Host "全部完成。下一步：.\push-all.ps1" -ForegroundColor Green
