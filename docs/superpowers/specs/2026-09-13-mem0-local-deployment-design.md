# Mem0 内存服务本地部署设计（Phase 1+2 更新版）

## 概述

在私有化服务器（`192.168.110.169`）上部署 Mem0 RAG API 服务，为 MinWorkBuddy 提供 AI 长期记忆能力。本设计支持以下三种模式：

1. **本地私有化部署**（默认推荐）: `MEM0_RAG_URL=http://192.168.110.169:8002`
2. **云端 API**: `MEM0_USE_CLOUD_API=true` (需配置 API Key)
3. **本地测试模式**: 纯内存实现（fallback）

### 核心参数
- **Restful API 地址**: `http://192.168.110.169:8002`
- **MCP 服务地址**: `192.168.110.169:8080`  
- **API Key**: `m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw`

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    MinWorkBuddy Application                       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │        ai/services/mem0_service.py                    │      │
│  │  ┌────────────────────────────────────────────────┐   │      │
│  │  │  Mem0Service                                    │   │      │
│  │  │  ├─ _init_mem0_client()                         │   │      │
│  │  │  ├─ record() / retrieve() / delete()           │   │      │
│  │  │  ├─ get_stats() / compress_memories()          │   │      │
│  │  │  └─ health_check()                              │   │      │
│  │  └────────────────────────────────────────────────┘   │      │
│  └─────────────────────┬──────────────────────────────────┘      │
│                        │                                          │
└────────────────────────┼──────────────────────────────────────────┘
                         │
    ═════════════════════╧═══════════════════════════════════════
                         │
         优先级选择逻辑:
         1. MEM0_ENABLED=false → LocalMem0Impl (内存存储)
         2. is_local_deployment → LocalMem0APIImpl (私有化)
         3. use_cloud_api=true → MemoryClient (云端)
         4. 否则 → LocalMem0Impl (降级 fallback)
                         │
    ═════════════════════╧═══════════════════════════════════════
                         │
┌─────────────────────────────────────────────────────────────────┐
│              Deployment Mode Selection                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Local Private Deployment (Recommended)                  │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  HTTP REST API Server                           │   │   │
│  │  │  http://192.168.110.169:8002                    │   │   │
│  │  │                                                 │   │   │
│  │  │  Endpoints:                                     │   │   │
│  │  │  • POST /memories       - Add memory entry      │   │   │
│  │  │  • POST /search         - Semantic search       │   │   │
│  │  │  • DELETE /memories     - Delete by ID          │   │   │
│  │  │  • GET  /memories/stats - Statistics            │   │   │
│  │  │  • GET  /health         - Health check          │   │   │
│  │  │  • POST /memories/compress - Compress memories  │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  │         ↑ Bearer Token Auth                             │   │
│  │         m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  MCP Service                                              │   │
│  │  http://192.168.110.169:8080                             │   │
│  │  (Optional - for real-time events)                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Cloud API (Fallback Option)                             │   │
│  │  mem0.ai                                                │   │
│  │  Requires: MEM0_USE_CLOUD_API=true, MEM0_API_KEY        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 组件详细设计

### 1. 配置文件 (`app/config/_mem0.py`)

```python
class Mem0Settings(BaseModel):
    """Mem0 配置字段 - 支持本地私有化部署"""
    
    # Connection Configuration
    MEM0_RAG_URL: str = Field(default="")
    MEM0_API_KEY: str = Field(default="")
    MEM0_MCP_HOST: str = Field(default="localhost")
    MEM0_MCP_PORT: int = Field(default=8080)
    
    # Feature Switches
    MEM0_ENABLED: bool = Field(default=False)
    MEM0_USE_CLOUD_API: bool = Field(default=False)
    
    # Storage & Retrieval
    MEM0_MAX_ENTRIES: int = Field(default=10000)
    MEM0_RETENTION_DAYS: int = Field(default=90)
    MEM0_EMBEDDING_MODEL: str = Field(default="all-MiniLM-L6-v2")
    MEM0_VECTOR_DIMENSION: int = Field(default=384)
    
    # Performance & Caching
    MEM0_CACHE_TTL: int = Field(default=3600)
    MEM0_SEARCH_LIMIT: int = Field(default=10)
    MEM0_RETRIEVE_TOP_K: int = Field(default=5)
    
    # Compression & Optimization
    MEM0_ENABLE_COMPRESSION: bool = Field(default=False)
    MEM0_COMPLETION_TOKEN_LIMIT: int = Field(default=10000)
```

### 2. 服务实现 (`ai/services/mem0_service.py`)

#### 客户端初始化逻辑

```python
def _init_mem0_client(self) -> Any:
    if not self.config.enabled:
        return LocalMem0Impl(...)
    
    if self.config.is_local_deployment:  # has RAG URL && !use_cloud_api
        return self._init_local_deployment_client()
    
    if self.config.use_cloud_api and self.config.api_key:
        return self._init_cloud_client()
    
    return LocalMem0Impl(...)  # fallback
```

#### LocalMem0APIImpl（本地私有化部署客户端）

```python
class LocalMem0APIImpl:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
    
    def add(self, user_id: str, message: str, metadata: Dict) -> Union[Dict, bool]:
        # POST /memories
        payload = {"user_id": user_id, "message": message, "metadata": metadata}
        
    def search(self, query: str, user_id: str, limit: int) -> List[Dict]:
        # POST /search
        payload = {"query": query, "user_id": user_id, "limit": limit}
        
    def delete(self, memory_id: str, user_id: str) -> bool:
        # DELETE /memories
        payload = {"memory_id": memory_id, "user_id": user_id}
    
    def health_check(self) -> bool:
        # GET /health
        response = client.get(f"{base_url}/health")
        return response.json().get("status", False)
    
    def compress_memories(self, user_id: str, token_limit: int) -> bool:
        # POST /memories/compress (optional)
        try:
            payload = {"user_id": user_id, "token_limit": token_limit}
            response = client.post(..., json=payload)
            return True
        except HTTPError as e:
            if e.response.status_code == 404:
                return False  # Endpoint not supported
```

---

## Phase 1: 上下文管理基础架构

### 文件清单

| 文件 | 修改内容 |
|------|---------|
| `backend/app/config/_mem0.py` | **新建**: Mem0Settings 配置模块 |
| `backend/app/config/__init__.py` | 导入并注册 `Mem0Settings` mixin |
| `backend/app/ai/services/mem0_service.py` | 重写 `LocalMem0APIImpl` 和初始化逻辑 |
| `.env.example` | **新建**: 包含所有 Mem0 环境变量示例 |

### 环境变量规范

```bash
# .env 文件配置
MEM0_RAG_URL=http://192.168.110.169:8002
MEM0_API_KEY=m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw
MEM0_ENABLED=true
MEM0_USE_CLOUD_API=false
MEM0_MAX_ENTRIES=10000
MEM0_RETENTION_DAYS=90
MEM0_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

---

## Phase 2: 生命周期管理与干预能力

### 健康检查机制

```python
# 初始化时执行一次
if isinstance(self._client, LocalMem0APIImpl):
    if not self._client.health_check():
        logger.warning("Mem0 health check failed, will retry on next operation")

# 每次操作前自动重试（仅首次未检查时）
if not self._health_checked and isinstance(self._client, LocalMem0APIImpl):
    if not self._client.health_check():
        logger.error("Mem0 API health check failed during operation")
        return False
```

### 压缩接口兼容性验证

```python
def compress_memories(self) -> bool:
    if not getattr(self.config, 'enable_compression', False):
        return False
    
    if isinstance(self._client, LocalMem0APIImpl):
        return self._client.compress_memories(
            user_id=self.user_id,
            token_limit=getattr(self.config, 'completion_token_limit', 10000)
        )
```

### 审计日志集成点

```python
# 在 record、retrieve、delete 方法中已添加详细日志
logger.debug(f"Mem0Service recorded memory: user={self.user_id}, result={result}")
logger.error(f"Mem0Service record failed: {type(e).__name__}: {e}")
```

---

## 安全规范

### 敏感信息处理

✅ **遵循**
- API Key 通过环境变量传递：`MEM0_API_KEY=m0sk_...`
- 不在代码中硬编码凭证
- 使用 JWT Bearer Token 认证（如果 Mem0 API 支持）
- `.env` 文件不应提交到 git

❌ **避免**
- 硬编码在源代码中的密钥
- 使用弱加密算法
- 将生产凭证放入开发环境

---

## 部署步骤

### 1. 验证 Mem0 API 可用性

```bash
# 健康检查端点
curl http://192.168.110.169:8002/health

# 添加记忆测试
curl -X POST http://192.168.110.169:8002/memories \
  -H "Authorization: Bearer m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "message": "测试记忆条目"}'

# 搜索记忆测试
curl -X POST http://192.168.110.169:8002/search \
  -H "Authorization: Bearer m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw" \
  -H "Content-Type: application/json" \
  -d '{"query": "测试", "user_id": "test_user"}'

# 压缩接口测试（如果存在）
curl -X POST http://192.168.110.169:8002/memories/compress \
  -H "Authorization: Bearer m0sk_ta2xhQeKvdmorEFuBsMdyKKW_YG2XeJqd2SGHFPJ2dw" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "token_limit": 10000}'
```

### 2. 启动 MinWorkBuddy 应用

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，设置正确的配置
nano .env  # 或 vim .env

# 启动应用
cd backend
uv run uvicorn app.ai.platform.app_factory:create_app() --factory --host 0.0.0.0 --port 8000
```

---

## 监控与运维

### 健康检查脚本

```python
from app.ai.services.mem0_service import Mem0Service, Mem0Config
from app.config import settings

config = Mem0Config.from_settings()
service = Mem0Service(config, user_id="health_check")

is_healthy = service._client.health_check()
print(f"Mem0 Status: {'✓ Healthy' if is_healthy else '✗ Unhealthy'}")
```

### 日志级别建议

| 环境 | LOG_LEVEL | Mem0 日志级别 |
|------|-----------|--------------|
| Development | DEBUG | DEBUG |
| Staging | INFO | INFO |
| Production | WARNING | WARNING |

---

## 故障排查

### 常见问题

1. **连接失败**: 检查网络连通性和防火墙规则
2. **认证失败**: 验证 MEM0_API_KEY 是否正确
3. **端口错误**: 确认 MEM0_MCP_PORT 和 MEM0_RAG_URL 端口匹配

### 调试命令

```bash
# 检查容器端口监听
netstat -an | grep 8002

# 测试 TCP 连接
telnet 192.168.110.169 8002

# 查看 Mem0 容器日志
docker logs mem0-api
```

---

## 参考资料

- [Mem0 官方文档](https://docs.mem0.ai)
- [AgentScope MemoryBase 接口](https://github.com/modelscope/agentscope)
- [MinWorkBuddy Architecture Design](../../architecture-design.md)
