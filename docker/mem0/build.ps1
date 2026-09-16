# =============================================================
# Mem0 本地构建启动脚本
#
# 用法：.\build.ps1
# =============================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Mem0 本地部署 - 构建启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------
# 1. 检查 mem0 源码
# -----------------------------------------------------------
$mem0Source = "D:\projects\github\mem0"
if (-not (Test-Path "$mem0Source\server\dashboard")) {
    Write-Host "[1/4] 错误：mem0 源码不存在于 $mem0Source" -ForegroundColor Red
    Write-Host "  请先克隆：git clone https://github.com/mem0ai/mem0.git $mem0Source" -ForegroundColor Red
    exit 1
} else {
    Write-Host "[1/4] mem0 源码已就绪：$mem0Source" -ForegroundColor Green
}

# -----------------------------------------------------------
# 2. 检查 PostgreSQL 数据库
# -----------------------------------------------------------
Write-Host "[2/4] 检查 PostgreSQL 数据库..." -ForegroundColor Yellow
$pgReady = docker exec mwb-postgres-pgvector pg_isready -U postgres -d mem0 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> mem0 数据库不存在，请先创建：" -ForegroundColor Red
    Write-Host ""
    Write-Host "  docker exec -it mwb-postgres-pgvector psql -U postgres \" -ForegroundColor White
    Write-Host '    -c "CREATE DATABASE mem0;" \' -ForegroundColor White
    Write-Host '    -c "\c mem0" \' -ForegroundColor White
    Write-Host '    -c "CREATE EXTENSION IF NOT EXISTS vector;"' -ForegroundColor White
    Write-Host ""
    Write-Host "  创建完成后重新运行此脚本。" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  -> mem0 数据库就绪" -ForegroundColor Green
}

# -----------------------------------------------------------
# 3. 构建并启动
# -----------------------------------------------------------
Write-Host "[3/4] 构建并启动容器..." -ForegroundColor Yellow
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误：docker compose 启动失败" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------
# 4. 等待服务就绪并验证
# -----------------------------------------------------------
Write-Host "[4/4] 等待服务就绪..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Mem0 部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  API Docs   : http://localhost:8888/docs" -ForegroundColor White
Write-Host "  Dashboard  : http://localhost:3001" -ForegroundColor White
Write-Host ""
Write-Host "  查看日志   : docker compose logs -f" -ForegroundColor Gray
Write-Host "  停止服务   : docker compose down" -ForegroundColor Gray
Write-Host ""
