# 工作流管理系统设计规格（外部平台代理层）

> **版本**: v1.0  
> **日期**: 2026-09-12  
> **状态**: 设计已确认，待实施  
> **适用范围**: `MinWorkBuddy` 工程 — 多平台工作流统一接入与管理  
> **关联文档**: [ReAct 模式设计](./2026-09-06-react-mode-design.md) · [Wiki 模块总览](./2026-09-12-wiki-module-standardization-design.md)

---

## 目录

1. [设计决策摘要](#1-设计决策摘要)
2. [数据模型与数据库变更](#2-数据模型与数据库变更)
3. [平台适配器层](#3-平台适配器层)
4. [执行引擎与网关层](#4-执行引擎与网关层)
5. [AgentConfig 集成](#5-agentconfig-集成)
6. [API 路由与前端界面](#6-api-路由与前端界面)
7. [示例场景](#7-示例场景)
8. [数据库迁移脚本](#8-数据库迁移脚本)
9. [测试用例设计](#9-测试用例设计)
10. [实施计划](#10-实施计划)

---

## 1. 设计决策摘要

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 系统定位 | **外部平台代理层** | MinWorkBuddy 不内置编排引擎，而是作为 Dify / Coze 等外部平台的统一代理与管控层 |
| 架构方案 | **方案 C — 完整网关** | 在代理层基础上增加限流、熔断、重试、执行日志、链式编排等企业级治理能力 |
| 多租户 | 所有新表继承 `TenantMixin` | 与现有 `agent_config` 等表保持一致的行级隔离策略 |
| API Key 存储 | 加密存储（`pgcrypto` / Fernet） | risk_control 原方案明文存储存在安全隐患 |
| 平台扩展 | 策略模式 + 运行时注册 | 新增平台只需实现 `PlatformAdapter` 并注册到 `AdapterFactory` |

### 1.1 参考实现分析（risk_control）

risk_control 项目已实现 Dify 工作流接入：

```
DifyFlow (Model)  →  DifyFlowService (按 flow_type 分发)  →  DifyWorkflowEngine (BaseEngine 适配)
```

**关键发现**：
- `DifyFlow` 表以 `flow_code` 为业务键，每流程独立 `api_key`
- `DifyFlowService.run_flow()` 按 `dify_flow_type` 分 5 种 API 端点
- `DifyWorkflowEngine` 薄包装 `DifyFlowService`，适配输出格式
- **缺陷**：无多租户、无执行日志、Coze 仅预留字段未实现、API Key 明文

本设计在 risk_control 模式基础上全面升级。

---

## 2. 数据模型与数据库变更

### 2.1 新增表：`workflow_flow`（工作流定义表）

```python
class WorkflowFlow(Base, TenantMixin):
    """多平台工作流定义表"""
    __tablename__ = "workflow_flow"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    flow_code       = Column(String(100), nullable=False, comment="业务唯一标识码")
    flow_name       = Column(String(200), nullable=False, comment="工作流名称")
    platform_type   = Column(String(50), nullable=False, default="dify",
                             comment="平台类型: dify / coze / custom_http")
    flow_type       = Column(String(50), nullable=False,
                             comment="流程类型: Workflow / Chatflow / Chatbot / Agent / Completion")
    base_url        = Column(String(500), nullable=False, comment="平台 API 基地址")
    api_key_enc     = Column(Text, nullable=False, comment="加密后的 API Key")
    input_schema    = Column(JSONB, nullable=False, default=dict, comment="入参 JSON Schema")
    output_schema   = Column(JSONB, nullable=True, comment="出参 JSON Schema")
    config          = Column(JSONB, nullable=True, comment="平台扩展配置（超时/重试/自定义 headers 等）")
    description     = Column(Text, nullable=True)
    is_active       = Column(Boolean, nullable=False, server_default="true")
    sort_order      = Column(Integer, nullable=False, server_default="0")
    created_by      = Column(BigInteger, nullable=True)
    created_at      = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at      = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted      = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("uq_workflow_flow_code_tenant", "flow_code", "tenant_id", unique=True),
        Index("idx_workflow_flow_platform", "platform_type"),
    )
```

**与 risk_control `dify_flow` 对比**：
- 新增 `tenant_id`（多租户）、`base_url`（每流程独立端点）、`output_schema`
- `api_key` → `api_key_enc`（加密存储）
- `flow_code + tenant_id` 联合唯一（跨租户可复用 code）

### 2.2 新增表：`workflow_execution_log`（执行日志表）

```python
class WorkflowExecutionLog(Base, TenantMixin):
    """工作流执行日志"""
    __tablename__ = "workflow_execution_log"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    flow_id         = Column(BigInteger, nullable=False, comment="FK → workflow_flow.id")
    execution_id    = Column(String(64), nullable=True, comment="关联 agent_execution.execution_id")
    status          = Column(String(20), nullable=False, default="pending",
                             comment="pending / running / success / failed / timeout / cancelled")
    input_data      = Column(JSONB, nullable=True, comment="实际输入")
    output_data     = Column(JSONB, nullable=True, comment="实际输出")
    error_message   = Column(Text, nullable=True)
    latency_ms      = Column(Integer, nullable=True)
    retry_count     = Column(Integer, nullable=False, default=0)
    platform_trace  = Column(JSONB, nullable=True, comment="平台返回的原始响应（task_id / message_id 等）")
    started_at      = Column(TIMESTAMP, nullable=True)
    completed_at    = Column(TIMESTAMP, nullable=True)
    created_at      = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_wf_exec_log_flow", "flow_id"),
        Index("idx_wf_exec_log_status", "status"),
        Index("idx_wf_exec_log_created", "created_at"),
    )
```

### 2.3 新增表：`workflow_chain`（链式编排表）

```python
class WorkflowChain(Base, TenantMixin):
    """工作流链式编排定义"""
    __tablename__ = "workflow_chain"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    chain_code      = Column(String(100), nullable=False, comment="链唯一标识码")
    chain_name      = Column(String(200), nullable=False)
    steps           = Column(JSONB, nullable=False, default=list,
                             comment="步骤列表 [{step_order, flow_code, input_mapping, output_key, condition, error_strategy}]")
    description     = Column(Text, nullable=True)
    is_active       = Column(Boolean, nullable=False, server_default="true")
    created_by      = Column(BigInteger, nullable=True)
    created_at      = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at      = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted      = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("uq_workflow_chain_code_tenant", "chain_code", "tenant_id", unique=True),
    )
```

**steps JSONB 结构**：
```json
[
  {
    "step_order": 1,
    "flow_code": "data-extraction",
    "input_mapping": {"query": "$.user_input"},
    "output_key": "extracted_data"
  },
  {
    "step_order": 2,
    "flow_code": "analysis-report",
    "input_mapping": {"data": "$.steps[0].output.extracted_data"},
    "output_key": "report",
    "condition": "$.steps[0].status == 'success'",
    "error_strategy": "skip"
  }
]
```

### 2.4 AgentConfig 变更

`agent_config` 表新增 `workflow_id` 字段：

```python
workflow_id = Column(BigInteger, nullable=True, comment="FK → workflow_flow.id")
```

- 当 `execution_mode == ExecutionMode.WORKFLOW` 且 `workflow_id` 非空时，走新网关路径
- 当 `workflow_id` 为空时，走旧路径（从 `config` 中读 `WorkflowConfig.dify_flow_code`，调用 `DifyClient`）

### 2.5 执行状态机

```
                  ┌──────────────────────────────┐
                  │                              │
  pending ──→ running ──→ success                 │
                │                                 │
                ├──→ failed ──→ (retry) ──→ pending
                │                                 │
                ├──→ timeout ─────────────────────┘
                │
                └──→ cancelled
```

| 状态 | 含义 | 终态 |
|------|------|------|
| `pending` | 已创建，等待调度 | 否 |
| `running` | 平台调用中 | 否 |
| `success` | 执行成功 | 是 |
| `failed` | 执行失败 | 是 |
| `timeout` | 超时终止 | 是 |
| `cancelled` | 用户取消 | 是 |

---

## 3. 平台适配器层

### 3.1 策略模式：`PlatformAdapter` 抽象基类

```python
# backend/app/services/workflow/platform_adapter.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class PlatformResponse:
    """适配器统一输出"""
    success: bool
    output: Dict[str, Any]
    error: Optional[str] = None
    latency_ms: int = 0
    platform_trace: Optional[Dict[str, Any]] = None  # 原始响应


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    def __init__(self, base_url: str, api_key: str, config: Optional[Dict] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    async def invoke(
        self,
        flow_type: str,
        inputs: Dict[str, Any],
        user_id: str,
        timeout: float = 600.0,
        **kwargs,
    ) -> PlatformResponse:
        """调用平台 API"""

    @abstractmethod
    def extract_output(self, result: Dict[str, Any], flow_type: str) -> str:
        """从平台响应中提取最终文本"""

    async def health_check(self) -> bool:
        """平台连通性检查（可选实现）"""
        return True
```

### 3.2 三个具体适配器

#### DifyAdapter

```python
class DifyAdapter(PlatformAdapter):
    """Dify 平台适配器 — 封装 5 种 API 端点"""

    ENDPOINT_MAP = {
        "Workflow":    "/v1/workflows/run",
        "Chatflow":    "/v1/chat-messages",
        "Chatbot":     "/v1/chat-messages",
        "Agent":       "/v1/agent/chat",
        "Completion":  "/v1/completions",
    }

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        endpoint = self.ENDPOINT_MAP.get(flow_type)
        if not endpoint:
            return PlatformResponse(success=False, output={}, error=f"不支持的 flow_type: {flow_type}")

        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = self._build_payload(flow_type, inputs, user_id)

        # httpx 调用 + 异常捕获
        ...

    def _build_payload(self, flow_type, inputs, user_id) -> dict:
        if flow_type == "Workflow":
            return {"inputs": inputs, "user": user_id}
        if flow_type in ("Chatflow", "Chatbot"):
            query = inputs.pop("query", inputs.pop("prompt", ""))
            return {"query": query, "inputs": inputs, "user": user_id, "response_mode": "blocking"}
        if flow_type == "Agent":
            query = inputs.pop("query", inputs.pop("prompt", ""))
            return {"query": query, "user": user_id, "response_mode": "blocking"}
        if flow_type == "Completion":
            prompt = inputs.pop("prompt", "")
            return {"prompt": prompt, "user": user_id, **inputs}
        return {}

    def extract_output(self, result, flow_type):
        if flow_type == "Workflow":
            outputs = result.get("data", {}).get("outputs", {})
            for key in ("result", "output", "answer", "text", "response"):
                if key in outputs and outputs[key]:
                    return str(outputs[key])
            return str(outputs) if outputs else ""
        # Chatflow / Chatbot / Agent / Completion
        return result.get("answer", "") or result.get("content", "") or ""
```

#### CozeAdapter

```python
class CozeAdapter(PlatformAdapter):
    """Coze 平台适配器"""

    ENDPOINT_MAP = {
        "Workflow":   "/api/v1/workflow/run",
        "Chatflow":   "/api/v1/conversation/chat",
        "Chatbot":    "/api/v1/conversation/chat",
        "Agent":      "/api/v1/conversation/chat",
        "Completion": "/api/v1/completion",
    }

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        # Coze API 认证方式：Bearer token
        # 请求体结构与 Dify 不同，需适配
        ...

    def extract_output(self, result, flow_type):
        # Coze 响应格式适配
        return result.get("data", {}).get("output", "") or result.get("messages", [{}])[-1].get("content", "")
```

#### CustomHTTPAdapter

```python
class CustomHTTPAdapter(PlatformAdapter):
    """通用 HTTP 适配器 — 用于其他 LLM 编排平台"""

    async def invoke(self, flow_type, inputs, user_id, timeout=600.0, **kw):
        # 从 self.config 读取 method / headers / body_template
        method = self.config.get("method", "POST")
        headers = {**self.config.get("headers", {}), "Authorization": f"Bearer {self.api_key}"}
        body_template = self.config.get("body_template", {})

        # 简单模板替换
        payload = self._render_template(body_template, inputs=inputs, user_id=user_id)
        ...

    def extract_output(self, result, flow_type):
        # 从 config 读取 output_path（JMESPath 风格）
        output_path = self.config.get("output_path", "$.output")
        return self._json_path_extract(result, output_path)
```

### 3.3 适配器工厂

```python
# backend/app/services/workflow/adapter_factory.py

class AdapterFactory:
    """适配器工厂 — 支持运行时注册"""

    _registry: Dict[str, Type[PlatformAdapter]] = {
        "dify":      DifyAdapter,
        "coze":      CozeAdapter,
        "custom_http": CustomHTTPAdapter,
    }

    @classmethod
    def create(cls, platform_type: str, base_url: str, api_key: str,
               config: Optional[Dict] = None) -> PlatformAdapter:
        adapter_cls = cls._registry.get(platform_type)
        if not adapter_cls:
            raise ValueError(f"不支持的平台类型: {platform_type}，已注册: {list(cls._registry.keys())}")
        return adapter_cls(base_url=base_url, api_key=api_key, config=config)

    @classmethod
    def register(cls, platform_type: str, adapter_cls: Type[PlatformAdapter]):
        """运行时注册新适配器"""
        cls._registry[platform_type] = adapter_cls
```

---

## 4. 执行引擎与网关层

### 4.1 网关三件套

#### 4.1.1 令牌桶限流（Redis）

```python
# backend/app/services/workflow/rate_limiter.py

class WorkflowRateLimiter:
    """基于 Redis 的令牌桶限流器

    粒度：tenant_id + flow_code
    默认配置：每流程 10 req/min，可通过 workflow_flow.config.rate_limit 覆盖
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def acquire(self, tenant_id: int, flow_code: str, max_tokens: int = 10,
                      refill_rate: float = 0.167) -> bool:
        """尝试获取令牌

        Args:
            max_tokens: 桶容量（默认 10）
            refill_rate: 每秒补充速率（默认 0.167 ≈ 10/min）
        """
        key = f"wf:rl:{tenant_id}:{flow_code}"
        # Lua 脚本保证原子性
        ...
```

#### 4.1.2 三态熔断器

```python
# backend/app/services/workflow/circuit_breaker.py

class CircuitState(str):
    CLOSED = "closed"        # 正常
    OPEN = "open"            # 熔断中（拒绝请求）
    HALF_OPEN = "half_open"  # 探测中（放行一个请求）


class CircuitBreaker:
    """三态熔断器

    规则：
    - CLOSED: 正常放行，记录失败次数
    - 失败次数 >= threshold (默认 5) → 切换 OPEN
    - OPEN: 拒绝所有请求，等待 recovery_seconds (默认 60) → 切换 HALF_OPEN
    - HALF_OPEN: 放行一个探测请求
      - 成功 → CLOSED（重置计数器）
      - 失败 → OPEN（重新计时）

    粒度：tenant_id + flow_code
    存储：Redis（跨进程共享）
    """

    def __init__(self, redis_client, threshold: int = 5, recovery_seconds: int = 60):
        self.redis = redis_client
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds

    async def can_execute(self, tenant_id: int, flow_code: str) -> bool: ...
    async def record_success(self, tenant_id: int, flow_code: str): ...
    async def record_failure(self, tenant_id: int, flow_code: str): ...
```

#### 4.1.3 指数退避重试

```python
# backend/app/services/workflow/retry_policy.py

class RetryPolicy:
    """指数退避重试策略

    配置：max_retries (默认 3), base_delay (默认 1.0s), max_delay (默认 30s), jitter (默认 True)
    仅对可重试错误（HTTP 429 / 502 / 503 / 504 / 连接超时）生效
    """

    async def execute_with_retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except RetriableError as e:
                if attempt == self.max_retries:
                    raise
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                if self.jitter:
                    delay *= random.uniform(0.5, 1.5)
                await asyncio.sleep(delay)
```

### 4.2 网关编排器

```python
# backend/app/services/workflow/gateway.py

class WorkflowGateway:
    """工作流网关 — 统一入口

    执行路径：
    1. 查找 workflow_flow 定义
    2. 解密 api_key
    3. 限流检查 → 熔断检查
    4. 创建 execution_log（status=running）
    5. 通过 AdapterFactory 创建适配器
    6. RetryPolicy 包装调用
    7. 成功/失败 → 更新 execution_log + 熔断器计数
    8. 触发 Webhook 回调（如配置）
    """

    async def execute(
        self,
        flow_code: str,
        tenant_id: int,
        inputs: Dict[str, Any],
        user_id: str,
        timeout: float = 600.0,
        execution_id: Optional[str] = None,
    ) -> PlatformResponse:
        ...
```

### 4.3 Webhook 回调

```python
# backend/app/services/workflow/webhook.py

class WebhookDispatcher:
    """异步 Webhook 回调

    事件类型：on_success / on_failure / on_timeout
    签名方式：HMAC-SHA256（使用 flow.config.webhook_secret）
    投递方式：ARQ 异步任务，不阻塞主流程
    """

    async def dispatch(self, event_type: str, flow: WorkflowFlow,
                       execution_log: WorkflowExecutionLog):
        webhook_url = flow.config.get("webhook_url") if flow.config else None
        if not webhook_url:
            return
        # 构造签名 payload
        ...
```

### 4.4 链式编排执行器

```python
# backend/app/services/workflow/chain_executor.py

class ChainExecutor:
    """链式编排执行器

    按 workflow_chain.steps 顺序执行多个工作流：
    - 每步通过 WorkflowGateway 执行
    - 支持 output 引用：`$.steps[0].output.xxx`
    - 支持条件跳过：`condition` 表达式为 false 时跳过
    - 支持 error_strategy：`stop`（默认）/ `skip` / `retry`
    """

    async def execute_chain(
        self,
        chain: WorkflowChain,
        tenant_id: int,
        initial_inputs: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        context = {"user_input": initial_inputs, "steps": []}

        for step in sorted(chain.steps, key=lambda s: s["step_order"]):
            # 1. 条件检查
            if not self._evaluate_condition(step.get("condition"), context):
                continue

            # 2. 输入映射
            step_inputs = self._resolve_mapping(step["input_mapping"], context)

            # 3. 通过网关执行
            try:
                result = await self.gateway.execute(
                    flow_code=step["flow_code"],
                    tenant_id=tenant_id,
                    inputs=step_inputs,
                    user_id=user_id,
                )
                context["steps"].append({
                    "status": "success",
                    "output": result.output,
                })
            except Exception as e:
                strategy = step.get("error_strategy", "stop")
                if strategy == "stop":
                    raise
                context["steps"].append({"status": "failed", "output": {}, "error": str(e)})

        return context
```

---

## 5. AgentConfig 集成

### 5.1 新增引擎：`WorkflowPlatformEngine`

```python
# backend/app/ai/engines/workflow_platform.py

class WorkflowPlatformEngine(BaseEngine):
    """工作流网关引擎 — 通过 WorkflowGateway 调用外部平台

    与旧 DifyWorkflowEngine 的区别：
    - 旧引擎：直接调用 DifyClient，全局 API Key，无治理
    - 新引擎：通过 WorkflowGateway，每流程独立 Key，有限流/熔断/重试/日志
    """

    def __init__(self, db, workflow_id: int = None, flow_code: str = None):
        super().__init__(db)
        self.workflow_id = workflow_id
        self.flow_code = flow_code
        self._gateway = WorkflowGateway(db)

    async def invoke(self, request: EngineRequest) -> EngineResponse:
        # 1. 从 workflow_id 查找 flow_code（或直接使用 flow_code）
        flow_code = self.flow_code
        if self.workflow_id:
            flow = self.db.query(WorkflowFlow).get(self.workflow_id)
            flow_code = flow.flow_code

        # 2. 参数映射
        inputs = self._apply_input_mapping(request)

        # 3. 通过网关执行
        result = await self.gateway.execute(
            flow_code=flow_code,
            tenant_id=request.context.get("tenant_id"),
            inputs=inputs,
            user_id=normalize_user_id(request.context.get("user_id")),
        )

        # 4. 输出映射
        output = self._apply_output_mapping(result)

        return EngineResponse(
            status="success" if result.success else "failed",
            output=output,
            error=result.error,
            latency_ms=result.latency_ms,
            engine_code="workflow_platform",
            metadata={"flow_code": flow_code},
        )
```

### 5.2 参数映射规则

采用 JMESPath 风格路径表达式：

| 路径 | 含义 |
|------|------|
| `$.user_input` | 用户原始输入文本 |
| `$.agent_kwargs.xxx` | AgentConfig.to_agent_kwargs() 中的字段 |
| `$.config.xxx` | AgentConfig.config JSONB 中的字段 |
| `$.output.xxx` | 上游步骤的输出字段 |
| `$.steps[N].output.xxx` | 链式编排中第 N 步的输出 |
| 字面量 `"string"` | 直接传递常量 |

**input_mapping 示例**：
```json
{
  "query": "$.user_input",
  "user_name": "$.agent_kwargs.agent_code",
  "mode": "\"analysis\""
}
```

**output_mapping 示例**：
```json
{
  "result": "$.output.answer",
  "summary": "$.output.data.summary"
}
```

### 5.3 降级兼容策略

```
AgentConfig.execution_mode == "workflow"
    │
    ├── workflow_id 非空 ──→ 新路径：WorkflowPlatformEngine → WorkflowGateway
    │
    └── workflow_id 为空 ──→ 旧路径：DifyClient（从 config.dify_flow_code 读取）
```

- 旧数据零改动：已有 AgentConfig 记录 `workflow_id = NULL`，继续走 `DifyClient`
- 新数据走网关：创建 AgentConfig 时选择工作流，自动填入 `workflow_id`
- 迁移窗口：未来可在管理界面批量将旧 `dify_flow_code` 迁移为 `workflow_flow` 记录

### 5.4 引擎注册

在引擎工厂中注册新引擎：

```python
# backend/app/ai/engines/__init__.py 或引擎注册处

ENGINE_CODE_WORKFLOW_PLATFORM = "workflow_platform"

# 在 get_engine() 工厂中：
if execution_mode == ExecutionMode.WORKFLOW:
    if workflow_id:
        return WorkflowPlatformEngine(db, workflow_id=workflow_id)
    else:
        return DifyWorkflowEngine(db, flow_code=config.get("dify_flow_code"))
```

---

## 6. API 路由与前端界面

### 6.1 RESTful API 路由

```
# backend/app/routers/workflow.py

router = APIRouter(prefix="/api/workflow", tags=["工作流管理"])

# ── 工作流定义 CRUD ──────────────────────────────
GET    /api/workflow/flows              # 分页列表（支持 platform_type / flow_type 筛选）
POST   /api/workflow/flows              # 创建工作流
GET    /api/workflow/flows/{id}         # 详情
PUT    /api/workflow/flows/{id}         # 更新
DELETE /api/workflow/flows/{id}         # 软删除
POST   /api/workflow/flows/{id}/test    # 测试执行（传入 inputs，返回结果）
GET    /api/workflow/flows/{id}/health  # 连通性检查

# ── 执行日志 ──────────────────────────────────────
GET    /api/workflow/executions          # 分页列表（支持 flow_id / status 筛选）
GET    /api/workflow/executions/{id}     # 详情（含 input_data / output_data / platform_trace）

# ── 链式编排 ──────────────────────────────────────
GET    /api/workflow/chains             # 链列表
POST   /api/workflow/chains             # 创建链
PUT    /api/workflow/chains/{id}        # 更新链
DELETE /api/workflow/chains/{id}        # 删除链
POST   /api/workflow/chains/{id}/test   # 测试执行链

# ── 平台管理 ──────────────────────────────────────
GET    /api/workflow/platforms           # 已注册平台类型列表
GET    /api/workflow/platforms/types     # 支持的平台类型枚举 + flow_type 枚举
```

### 6.2 前端界面设计

**入口**：管理后台左侧菜单「工作流管理」（图标 `ApiOutlined`）

**单页面 5 Tab 布局**：

| Tab | 名称 | 功能 |
|-----|------|------|
| 1 | 工作流列表 | 表格展示所有 flow，支持筛选 / 搜索 / 创建 / 编辑 / 删除 / 测试 |
| 2 | 可视化编辑器 | 表单式配置：基本信息 → 平台配置 → Schema 编辑 → 高级设置 |
| 3 | 测试工作台 | 左右分栏：左侧输入 JSON 编辑器，右侧执行结果 + 耗时 + 原始响应 |
| 4 | 执行日志 | 表格展示 execution_log，支持按 flow / status / 时间范围筛选 |
| 5 | 分析仪表板 | 成功率 / 平均延迟 / 平台分布 / 流程热度（图表） |

**品牌规范**（遵循 DESIGN.md）：
- 主色 Indigo `#4F6EF7`（按钮/链接/选中态）
- 辅色 Teal `#22D3AE`（成功状态/正向指标）
- 警告 Amber `#F5A623`（超时/降级状态）
- 暗色科技风 + 磨砂玻璃面板

**关键组件**：
- `WorkflowFlowForm.vue` — 工作流创建/编辑表单（含平台类型切换联动）
- `WorkflowTestBench.vue` — 测试工作台（JSON 编辑器 + 结果面板）
- `WorkflowExecutionTable.vue` — 执行日志表格
- `WorkflowChainEditor.vue` — 链式编排步骤编辑器（拖拽排序）
- `WorkflowDashboard.vue` — 分析仪表板（ECharts 图表）

---

## 7. 示例场景

### 7.1 场景 A：ReAct Agent 调用 Dify 工作流

**需求**：创建一个「数据分析报告」Agent，使用 Dify Workflow 处理数据。

**配置步骤**：
1. 创建 `workflow_flow` 记录：
   - `flow_code`: "data-analysis"
   - `platform_type`: "dify"
   - `flow_type`: "Workflow"
   - `base_url`: "https://dify.example.com"
   - `api_key_enc`: 加密存储
   - `input_schema`: `{"type": "object", "properties": {"dataset": {"type": "string"}, "query": {"type": "string"}}}`

2. 创建 `agent_config` 记录：
   - `agent_code`: "data-analyst"
   - `execution_mode`: "workflow"
   - `workflow_id`: 上一步的 flow.id
   - `config`: `{"input_mapping": {"dataset": "$.agent_kwargs.agent_code", "query": "$.user_input"}}`

3. 执行路径：
   ```
   用户输入 → AgentExecutionEngine
     → WorkflowPlatformEngine.invoke()
       → WorkflowGateway.execute(flow_code="data-analysis")
         → 限流检查 → 熔断检查 → DifyAdapter.invoke()
           → POST /v1/workflows/run
         → 记录 execution_log → Webhook 回调
   ```

### 7.2 场景 B：Coze Chatflow + HITL 审批流

**需求**：「合同审批」流程使用 Coze Chatflow，关键步骤需人工确认。

**配置步骤**：
1. 创建 `workflow_flow`：
   - `flow_code`: "contract-review"
   - `platform_type`: "coze"
   - `flow_type`: "Chatflow"
   - `config`: `{"webhook_url": "https://minworkbuddy.internal/webhook/hitl", "webhook_secret": "..."}`

2. 链式编排 `workflow_chain`：
   - Step 1: "contract-extract" → 提取合同关键条款
   - Step 2: "risk-assessment" → 风险评估（condition: step1 success）
   - Step 3: "human-approval" → HITL 审批（error_strategy: "stop"）

3. HITL 交互：
   - 网关执行到 Step 3 时，通过 Webhook 通知前端
   - 前端弹出审批面板，用户审批/拒绝
   - 审批结果通过 API 回传，链继续/终止

---

## 8. 数据库迁移脚本

```python
# alembic/versions/xxxx_add_workflow_tables.py

def upgrade():
    # 1. workflow_flow
    op.create_table(
        "workflow_flow",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
        sa.Column("flow_code", sa.String(100), nullable=False),
        sa.Column("flow_name", sa.String(200), nullable=False),
        sa.Column("platform_type", sa.String(50), nullable=False, server_default="dify"),
        sa.Column("flow_type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("api_key_enc", sa.Text, nullable=False),
        sa.Column("input_schema", JSONB, nullable=False, server_default="{}"),
        sa.Column("output_schema", JSONB, nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("created_at", sa.TIMESTAMP, server_default=func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("uq_workflow_flow_code_tenant", "workflow_flow", ["flow_code", "tenant_id"], unique=True)
    op.create_index("idx_workflow_flow_platform", "workflow_flow", ["platform_type"])

    # 2. workflow_execution_log
    op.create_table(
        "workflow_execution_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
        sa.Column("flow_id", sa.BigInteger, nullable=False),
        sa.Column("execution_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("error_message", sa.Text),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("platform_trace", JSONB, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP),
        sa.Column("completed_at", sa.TIMESTAMP),
        sa.Column("created_at", sa.TIMESTAMP, server_default=func.now()),
    )
    op.create_index("idx_wf_exec_log_flow", "workflow_execution_log", ["flow_id"])
    op.create_index("idx_wf_exec_log_status", "workflow_execution_log", ["status"])
    op.create_index("idx_wf_exec_log_created", "workflow_execution_log", ["created_at"])

    # 3. workflow_chain
    op.create_table(
        "workflow_chain",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
        sa.Column("chain_code", sa.String(100), nullable=False),
        sa.Column("chain_name", sa.String(200), nullable=False),
        sa.Column("steps", JSONB, nullable=False, server_default="[]"),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("created_at", sa.TIMESTAMP, server_default=func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("uq_workflow_chain_code_tenant", "workflow_chain", ["chain_code", "tenant_id"], unique=True)

    # 4. agent_config 新增 workflow_id
    op.add_column("agent_config", sa.Column("workflow_id", sa.BigInteger, nullable=True,
                                             comment="FK → workflow_flow.id"))
    op.create_index("idx_agent_config_workflow", "agent_config", ["workflow_id"])
```

---

## 9. 测试用例设计

### 9.1 单元测试

| ID | 测试目标 | 验证点 |
|----|----------|--------|
| UT-1 | `DifyAdapter._build_payload()` | 5 种 flow_type 生成正确的请求体结构 |
| UT-2 | `DifyAdapter.extract_output()` | Workflow / Chatflow / Agent / Completion 响应正确提取 |
| UT-3 | `CircuitBreaker` 状态转换 | CLOSED→OPEN（5 次失败）→HALF_OPEN（60s 后）→CLOSED（探测成功） |
| UT-4 | `RetryPolicy` 退避计算 | 指数延迟 + jitter 范围校验；不可重试错误不重试 |
| UT-5 | `ChainExecutor` 条件跳过 | condition 为 false 时步骤被跳过 |
| UT-6 | `ChainExecutor` 错误策略 | `stop` 抛异常 / `skip` 继续 / `retry` 重试 |
| UT-7 | 参数映射解析 | `$.user_input` / `$.agent_kwargs.xxx` / 字面量 正确替换 |

### 9.2 集成测试

| ID | 测试目标 | 验证点 |
|----|----------|--------|
| IT-1 | `WorkflowGateway` 端到端 | 限流拒绝 → 返回 429；熔断打开 → 返回 503 |
| IT-2 | `WorkflowPlatformEngine` → Gateway | AgentConfig.workflow_id 关联 → 正确调用 → EngineResponse |
| IT-3 | 链式编排全流程 | 3 步链，中间步 condition false → 跳过 → 最终结果正确 |
| IT-4 | Webhook 回调 | 执行完成后 Webhook 收到 HMAC 签名正确的 payload |

---

## 10. 实施计划

### 14 天分阶段交付

| 阶段 | 天数 | 交付物 | 依赖 |
|------|------|--------|------|
| **P1: 数据层** | D1-D2 | 3 张新表 Model + Alembic 迁移 + AgentConfig 变更 | 无 |
| **P2: 适配器层** | D3-D4 | PlatformAdapter ABC + DifyAdapter + CozeAdapter + AdapterFactory + 单元测试 | P1 |
| **P3: 网关层** | D5-D7 | RateLimiter + CircuitBreaker + RetryPolicy + WorkflowGateway + WebhookDispatcher | P2 |
| **P4: 引擎集成** | D8-D9 | WorkflowPlatformEngine + 引擎工厂注册 + 参数映射 + 降级兼容 | P3 |
| **P5: 链式编排** | D10 | ChainExecutor + 条件/错误策略 | P3 |
| **P6: API 路由** | D11-D12 | workflow.py router（CRUD + 测试执行 + 日志查询） | P4 |
| **P7: 前端** | D12-D13 | 5 Tab 管理界面（列表/编辑器/测试台/日志/仪表板） | P6 |
| **P8: 集成测试 + 文档** | D14 | 集成测试 + API 文档更新 + 用户指南 | P7 |

### 交付物清单

| 类型 | 文件 |
|------|------|
| Model | `models/workflow/workflow_flow.py`, `workflow_execution_log.py`, `workflow_chain.py` |
| Schema | `schemas/workflow/workflow.py` |
| Service | `services/workflow/platform_adapter.py`, `adapter_factory.py`, `gateway.py`, `rate_limiter.py`, `circuit_breaker.py`, `retry_policy.py`, `webhook.py`, `chain_executor.py` |
| Engine | `ai/engines/workflow_platform.py` |
| Router | `routers/workflow.py` |
| Frontend | `views/admin/workflow/` 目录下 5 个 Vue 组件 |
| Migration | `alembic/versions/xxxx_add_workflow_tables.py` |
| Test | `tests/workflow/` 目录下 7 个单元测试 + 4 个集成测试 |
