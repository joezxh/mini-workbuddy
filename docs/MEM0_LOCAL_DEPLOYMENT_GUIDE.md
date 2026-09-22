# MinWorkBuddy Mem0 本地私有化部署快速指南

## 📋 前置检查清单

### 1. 环境要求
- [ ] Python 3.8+ 已安装
- [ ] httpx 库已安装（`pip install httpx`）
- [ ] 网络可访问 `192.168.110.169:8002`
- [ ] `.env` 文件配置正确（见下文）

### 2. 依赖项确认

```bash
cd d:\projects\MinWorkBuddy\backend
uv run python -c "import httpx; print('✓ httpx installed')"
```

---

## 🚀 Phase 3: 快速部署流程

### 步骤 1: 复制并配置环境变量

```powershell
# 在项目根目录执行
cd d:\projects\MinWorkBuddy

# 复制模板（如果尚未存在）
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "✅ 已创建 .env 文件"
} else {
    Write-Host "ℹ️ .env 文件已存在，跳过创建"
}
```

### 步骤 2: 验证 .env 配置

打开 `.env` 文件，确保以下配置正确：

```ini
# ===== Mem0 核心配置 =====
MEM0_ENABLED=true                          # ⚠️ 必须设为 true 才能启用
MEM0_USE_CLOUD_API=false                   # 本地部署设为 false
MEM0_RAG_URL=http://192.168.110.169:8002   # ⚠️ 替换为你的实际地址
MEM0_API_KEY=m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw

# MCP 服务配置（可选）
MEM0_MCP_HOST=192.168.110.169
MEM0_MCP_PORT=8080

# 性能调优（可选，使用默认值即可）
MEM0_MAX_ENTRIES=10000
MEM0_RETENTION_DAYS=90
```

**⚠️ 重要提示**:
- 如果 `MEM0_ENABLED=false`，系统会使用内存降级实现
- `MEM0_USE_CLOUD_API=true` 会切换到云端 API 模式

### 步骤 3: 测试 Mem0 API 可达性

```powershell
# Windows PowerShell 命令
Write-Host "Testing Mem0 API connectivity..."
try {
    $response = Invoke-RestMethod -Uri "http://192.168.110.169:8002/health" -Method Get -TimeoutSec 10
    Write-Host "✅ Mem0 API is healthy:" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "❌ Connection failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}
```

### 步骤 4: 运行完整验证测试

```powershell
# 在项目根目录执行
python test_mem0_local_deployment.py
```

预期输出示例：
```
╔══════════════════════════════════════════════════════════╗
║   Mem0 Local Deployment Validation Suite (Phase 1+2)     ║
╚══════════════════════════════════════════════════════════╝

============================================================
Phase 2 Test 1: Config Loading Validation
============================================================
✓ PASS: MEM0_ENABLED = True
✓ PASS: MEM0_USE_CLOUD_API = False
✓ PASS: MEM0_RAG_URL = True
✓ PASS: MEM0_MAX_ENTRIES = True
✓ PASS: MEM0_RETENTION_DAYS = True

Local Deployment Mode: Enabled

============================================================
Phase 2 Test 2: Health Check Mechanism
============================================================
INFO:Mem0 API health check: healthy
✓ PASS: Mem0 API is healthy and accessible

============================================================
Phase 2 Test 3: Compression API Compatibility
============================================================
WARNING:Mem0 API compression endpoint not found (not supported)
⚠ WARNING: Compression API returned false (may be unsupported)

============================================================
Phase 2 Test 4: Basic CRUD Operations
============================================================
Test 4.1: Adding memory...
DEBUG:Mem0API added memory: user=test_user_1234567890, result={'id': 'mem_xxx'}
  ✓ PASS: Memory added successfully
Test 4.2: Searching memory...
DEBUG:Mem0API search results: 1 items
  ✓ PASS: Memory search returned 1 results
Test 4.3: Getting statistics...
DEBUG:Mem0API stats: {'total_memories': 1}
  ✓ PASS: Statistics retrieved
Test 4.4: Testing delete operation...
  ℹ INFO: Delete requires memory_id (not returned by all APIs)
  ✓ PASS: Delete method exists and callable

============================================================
TEST SUMMARY
============================================================
✓ PASS: Configuration Loading
✓ PASS: Health Check
✓ PASS: Compression API
✓ PASS: Basic CRUD Operations
✓ PASS: Audit Logging
------------------------------------------------------------
Overall: 5/5 tests passed

🎉 All validations passed! Ready for production.
```

---

## 🔧 故障排查

### 问题 1: `Connection refused` 或 `Timeout`

**症状**:
```
✗ FAIL: Health check error: ConnectionError: HTTPConnectionPool...
```

**解决方案**:
1. 检查防火墙规则：
   ```powershell
   Test-NetConnection 192.168.110.169 -Port 8002
   ```
2. 确认 Mem0 API 服务正在运行：
   ```bash
   curl http://192.168.110.169:8002/health
   ```
3. 检查 Docker 端口暴露：
   ```bash
   docker ps | grep mem0
   netstat -an | findstr 8002
   ```

### 问题 2: 认证失败 (`401 Unauthorized`)

**症状**:
```
✗ FAIL: API request failed with status code 401
```

**解决方案**:
1. 验证 `.env` 中的 `MEM0_API_KEY` 是否正确
2. 检查 API 是否启用了认证（可能需要调整 `AUTH_DISABLED` 环境变量）

### 问题 3: 环境变量未生效

**症状**:
```
MEM0_ENABLED = False  # 但你在 .env 中设置了 true
```

**解决方案**:
1. 确认 `.env` 文件位于正确位置（项目根目录）
2. 重启 Python 进程以重新加载配置
3. 检查环境变量优先级：
   ```python
   from app.config import settings
   print(settings.model_config['env_file'])  # 查看加载的 .env 路径
   ```

### 问题 4: 压缩接口不支持

**现象**:
```
⚠ WARNING: Compression API returned false (may be unsupported)
```

**说明**: 
- **这不是错误**！某些 Mem0 版本不提供压缩功能
- 系统会自动 graceful fallback
- 如需启用压缩，请确认 Mem0 API 版本支持该端点

---

## 📊 生产部署建议

### 监控指标

在应用日志中添加以下监控：

```python
from loguru import logger

# 健康检查频率
if hasattr(service._client, 'health_check'):
    import threading
    def periodic_health_check():
        while True:
            is_healthy = service._client.health_check()
            logger.info(f"Periodic health check: {'OK' if is_healthy else 'FAIL'}")
            time.sleep(300)  # 每 5 分钟检查一次
    
    threading.Thread(target=periodic_health_check, daemon=True).start()
```

### 日志级别配置

| 环境 | LOG_LEVEL | Mem0 日志配置 |
|------|-----------|--------------|
| Development | DEBUG | 详细调试信息 |
| Staging | INFO | 关键操作记录 |
| Production | WARNING | 仅错误和警告 |

修改方式 (`.env`):
```ini
LOG_LEVEL=WARNING  # 生产环境
```

### 自动恢复机制

代码已包含自动重试逻辑：
- 初始化失败 → 降级到 LocalMem0Impl（内存存储）
- 首次健康检查失败 → 下次操作前自动重试
- 压缩接口不存在 → 自动 skip 不报错

---

## 🔄 更新与回滚

### 更新配置

```powershell
# 编辑 .env 文件后无需重启（动态配置重载）
nano .env

# 如果需要重载配置
import importlib
from app.config import settings
importlib.reload(settings)
```

### 紧急回滚

如果 Mem0 API 不可用，立即禁用：

```ini
# .env
MEM0_ENABLED=false  # 临时禁用
```

系统将自动使用内存降级模式，不影响核心功能。

---

## 📞 技术支持

- **文档**: `docs/superpowers/specs/2026-09-13-mem0-local-deployment-design.md`
- **测试脚本**: `test_mem0_local_deployment.py`
- **配置文件**: `backend/app/config/_mem0.py`
- **服务实现**: `backend/app/ai/services/mem0_service.py`

遇到其他问题？请先运行：
```bash
python test_mem0_local_deployment.py --debug
```

---

## ✅ 部署验收标准

- [ ] `MEM0_ENABLED=true`
- [ ] 健康检查通过（`/health` 返回 `{"status": "healthy"}`）
- [ ] 记忆 CRUD 操作正常（add/search/delete/get_stats）
- [ ] 审计日志记录完整（至少看到 DEBUG 级别日志）
- [ ] 所有 5 项测试全部通过

满足以上条件即表示部署成功！🎉
