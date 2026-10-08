<#
.SYNOPSIS
    把第三方基础镜像中转（拉取 → 改标签 → 推送）到阿里云个人仓库。

.DESCRIPTION
    读取 registry.env 与 prepull-images.txt，逐条把海外/公共 registry 上的基础镜像
    同步到自己的 ACR，之后所有组件的 FROM 只依赖个人仓库，构建不再需要访问海外网络。

    幂等：目标仓库中已存在同名镜像时跳过，-Force 才会重新拉取覆盖。

.PARAMETER Force
    忽略"目标已存在"判断，强制重新拉取并推送。

.PARAMETER DryRun
    只打印将要执行的动作，不实际 pull/tag/push。

.PARAMETER ListFile
    指定白名单文件，默认 prepull-images.txt。

.EXAMPLE
    .\prepull.ps1
    .\prepull.ps1 -Force
#>
param(
    [switch]$Force,
    [switch]$DryRun,
    [string]$ListFile = (Join-Path $PSScriptRoot "prepull-images.txt")
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# 读取 registry.env
# ------------------------------------------------------------------
$registryEnv = Join-Path (Split-Path -Parent $PSScriptRoot) "registry.env"
if (-not (Test-Path $registryEnv)) {
    Write-Host "[ERROR] 找不到配置文件：$registryEnv" -ForegroundColor Red
    exit 1
}

$envMap = @{}
foreach ($raw in (Get-Content $registryEnv)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    $kv = $line -split "=", 2
    if ($kv.Count -eq 2) { $envMap[$kv[0].Trim()] = $kv[1].Trim() }
}

$registryHost  = $envMap["REGISTRY_HOST"]
$registry      = $envMap["REGISTRY"]
$baseRegistry  = $envMap["BASE_REGISTRY"]

if (-not $registryHost -or -not $registry) {
    Write-Host "[ERROR] registry.env 缺少 REGISTRY_HOST / REGISTRY" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# 检查 docker login 登录态（凭据由宿主机保管，本脚本不接受密码）
# ------------------------------------------------------------------
Write-Host "==> 检查 $registryHost 登录态..." -ForegroundColor Yellow
# PowerShell 5.1 兼容写法（不用 ?: 三元运算符）
$cfgDir = if ($env:DOCKER_CONFIG) { $env:DOCKER_CONFIG } else { Join-Path $HOME ".docker" }
$dockerConfig = Join-Path $cfgDir "config.json"
$loggedIn = $false
if (Test-Path $dockerConfig) {
    $cfgRaw = Get-Content $dockerConfig -Raw
    if ($cfgRaw -and $cfgRaw.Contains($registryHost)) { $loggedIn = $true }
}
if (-not $loggedIn) {
    Write-Host "[ERROR] 未检测到 $registryHost 的登录凭据。" -ForegroundColor Red
    Write-Host "        请先执行：docker login $registryHost" -ForegroundColor White
    exit 1
}

# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
if (-not (Test-Path $ListFile)) {
    Write-Host "[ERROR] 白名单文件不存在：$ListFile" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  基础镜像中转 → $registry" -ForegroundColor Cyan
Write-Host "  白名单：$ListFile" -ForegroundColor Gray
Write-Host "  Force  ：$($Force.IsPresent)" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$total = 0; $skipped = 0; $ok = 0
$failed = @()

foreach ($raw in (Get-Content $ListFile)) {
    $line = $raw.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }

    $fields = @($line -split '\s+' | Where-Object { $_ -ne "" })
    if ($fields.Count -lt 2) {
        Write-Host "[WARN] 忽略无效行：$line" -ForegroundColor DarkYellow
        continue
    }

    $src  = $fields[0]
    $dst  = $fields[1]
    $from = if ($fields.Count -ge 3) { $fields[2] } else { $src }

    # dst 以 base/ 开头的落到 BASE_REGISTRY，否则落到业务 REGISTRY
    if ($dst.StartsWith("base/")) {
        $target = "$registry/$dst"
    } else {
        $target = "$registry/$dst"
    }

    $total++

    # 幂等判断：远端已存在则跳过
    if (-not $Force) {
        docker manifest inspect $target 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SKIP] $target 已存在" -ForegroundColor DarkGray
            $skipped++
            continue
        }
    }

    Write-Host "[PULL] $from" -ForegroundColor Yellow
    if ($DryRun) { $ok++; continue }

    docker pull $from
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] 拉取失败：$from" -ForegroundColor Red
        $failed += $src
        continue
    }

    docker tag $from $target
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] 打标签失败：$from -> $target" -ForegroundColor Red
        $failed += $src
        continue
    }

    docker push $target
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] 推送失败：$target" -ForegroundColor Red
        $failed += $src
        continue
    }

    Write-Host "[ OK ] $target" -ForegroundColor Green
    $ok++
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  中转完成：总计 $total / 成功 $ok / 跳过 $skipped / 失败 $($failed.Count)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($failed.Count -gt 0) {
    Write-Host "失败的源镜像：" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "提示：Docker Hub 卡顿时，可在白名单第三列换其它 proxy registry。" -ForegroundColor DarkYellow
    exit 1
}
