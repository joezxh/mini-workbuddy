"""路由注册表 —— 集中声明所有 APIRouter 的挂载方式。

设计目标
--------
将 `main.py` 中写死的 `include_router` 调用改为「数据驱动」的清单式注册：

* 新增/下线模块只改本文件，不动 `main.py`；
* 保留对每个 router 的 prefix / tags / 启停的显式控制；
* **顺序即路由匹配顺序**（Starlette 按注册顺序匹配，先命中先执行），
  因此清单顺序与重构前 `main.py` 的注册顺序严格一致，不可随意调整。

为什么不用「扫描目录全自动注册」
------------------------------
当前工程存在若干会让自动扫描改变线上行为的情况：

1. **prefix 语义不统一**：部分 router 在自身声明了含 `/api/v1` 的 prefix
   （如 `agent.py` 的 `/api/v1/agent`、`agent_config.py` 的 `/api/v1/agent-config`），
   另一些则是相对 prefix（如 `agent_team.py` 的 `/ai-team`）依赖外部拼接。
   自动扫描无法判断哪些该再叠加 `/api/v1`，会直接改坏 URL。
2. **存在刻意不注册的模块**：`wiki/__init__.py` 为空；自研本体层
   （`routers/ontology`、`routers/wiki/wiki_owl.py`）已随 `ontology_*` 九表一并删除，
   语义/本体能力改由 `routers/semantica` 提供。
3. **`sys/__init__.py` 本身就是 router**（控制台统计/用户/菜单/角色/审计等），
   按「文件」扫描会与同目录 `sys_*.py` 产生归属歧义。
4. **单模块多 router**：`ai_mcp.py` 同时导出 4 个 router
   （router / client_router / square_router / mcp_tools_router）。

因此采用「显式清单」而非「隐式扫描」，保证重构前后路由表完全一致。
"""

import os
import time
from dataclasses import dataclass
from importlib import import_module, invalidate_caches
from typing import List, Optional

from fastapi import APIRouter, FastAPI
from loguru import logger


API_V1_PREFIX = "/api/v1"

IMPORT_ATTEMPTS = 2
"""单个路由模块的导入尝试次数。"""

IMPORT_RETRY_DELAY = 0.2
"""重试前的等待秒数（秒）。"""


def _strict_from_env() -> bool:
    """严格模式开关：ROUTER_STRICT=1 时任一路由模块加载失败即启动失败。"""
    return os.getenv("ROUTER_STRICT", "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class RouterSpec:
    """单个 router 的挂载声明。"""

    module: str
    """router 所在模块的完整导入路径，如 'app.routers.sys.sys_tenant'。"""

    attr: str = "router"
    """模块中 router 对象的属性名（ai_mcp.py 等单模块多 router 时需要指定）。"""

    prefix: str = ""
    """额外叠加的前缀。router 自身若已声明完整 prefix，此处应留空。"""

    tags: Optional[List[str]] = None
    """OpenAPI 分组标签；为 None 时沿用 router 自身声明的 tags。"""

    enabled: bool = True
    """设为 False 可临时下线该模块，无需删除配置。"""

    note: str = ""
    """备注（如已知问题、下线原因），仅用于文档说明。"""

    @property
    def label(self) -> str:
        return f"{self.module}:{self.attr}"


# ---------------------------------------------------------------------------
# 路由清单
#
# 顺序与重构前 main.py 的注册顺序严格一致，请勿随意调整：
# Starlette 按注册顺序匹配路由，顺序变化可能改变优先级
# （典型风险：/users/{id} 注册在 /users/me 之前时会遮蔽后者）。
# ---------------------------------------------------------------------------
ROUTER_SPECS: List[RouterSpec] = [
    # --- 1. 认证（router 未声明 prefix）---
    RouterSpec("app.routers.auth", prefix=f"{API_V1_PREFIX}/auth", tags=["认证"]),

    # --- 2~5. 系统管理 ---
    # 注意：app.routers.sys 指向 sys/__init__.py，该文件本身就是 router
    # （控制台统计、用户、菜单、角色、审计日志等），并非普通包初始化文件。
    RouterSpec("app.routers.sys", prefix=f"{API_V1_PREFIX}/admin", tags=["管理员"]),
    RouterSpec("app.routers.sys.sys_dictionary", prefix=f"{API_V1_PREFIX}/dictionary", tags=["字典管理"]),
    RouterSpec("app.routers.sys.sys_tenant", prefix=f"{API_V1_PREFIX}/admin/tenant", tags=["租户管理"]),
    RouterSpec(
        "app.routers.sys.sys_tenant_package",
        prefix=f"{API_V1_PREFIX}/admin/tenant-package",
        tags=["租户套餐管理"],
    ),

    # --- 6~7. AI（router 自带 /ai-agent、无 prefix）---
    RouterSpec("app.routers.ai.ai_agent", prefix=API_V1_PREFIX, tags=["AI Agent 统一执行"]),
    RouterSpec("app.routers.ai.ai_chat", prefix=f"{API_V1_PREFIX}/admin", tags=["AI会话管理"]),

    # --- 8~12. Agent ---
    RouterSpec(
        "app.routers.agent.agent",
        prefix=API_V1_PREFIX,
        tags=["Agent"],
        # 已知问题：该 router 自身已声明 prefix="/api/v1/agent"，此处再叠加 /api/v1，
        # 实际对外路径为 /api/v1/api/v1/agent（前端并未调用该组接口，故长期未被发现）。
        # 此处刻意保持与重构前一致；修复需同步改 agent.py 的 prefix，建议单独处理。
        note="router 自带 /api/v1/agent，叠加后为 /api/v1/api/v1/agent（既有行为，待单独修复）",
    ),
    # 以下 3 个模块自带完整 prefix（含 /api/v1），故此处不叠加
    RouterSpec("app.routers.agent.agent_config", tags=["Agent配置管理"]),
    RouterSpec("app.routers.agent.agent_execution", tags=["Agent执行查询"]),
    RouterSpec("app.routers.agent.agent_scheduled_task", tags=["Agent定时任务"]),
    RouterSpec("app.routers.agent.agent_team", prefix=API_V1_PREFIX, tags=["AI Team 多智能体团队"]),
    # agent_run 自带相对 prefix /agents/executions，此处叠加 /api/v1
    RouterSpec("app.routers.agent.agent_run", prefix=API_V1_PREFIX, tags=["Agent 运行控制"]),

    # --- 13~16. 技能 / 密钥 / 工具 ---
    RouterSpec("app.routers.ai.ai_skill", prefix=f"{API_V1_PREFIX}/ai-assistant/skills", tags=["AI技能"]),
    # 该模块已在自身声明完整前缀 /api/v1/ai-assistant，此处不叠加，否则路径会重复
    RouterSpec("app.routers.ai.ai_assistant", tags=["AI助手"]),
    RouterSpec("app.routers.ai.ai_skill_hub", prefix=f"{API_V1_PREFIX}/ai-system/skill-hub", tags=["技能仓库"]),
    RouterSpec("app.routers.ai.ai_api_key", prefix=f"{API_V1_PREFIX}/admin", tags=["AI API密钥管理"]),
    RouterSpec("app.routers.ai.ai_tool", prefix=f"{API_V1_PREFIX}/admin", tags=["AI 工具管理"]),

    # --- 17~20. MCP：单模块导出 4 个 router ---
    RouterSpec("app.routers.ai.ai_mcp", attr="router", prefix=f"{API_V1_PREFIX}/admin", tags=["MCP API Key 管理"]),
    RouterSpec(
        "app.routers.ai.ai_mcp",
        attr="client_router",
        prefix=f"{API_V1_PREFIX}/admin",
        tags=["MCP Client 管理"],
    ),
    RouterSpec(
        "app.routers.ai.ai_mcp",
        attr="square_router",
        prefix=f"{API_V1_PREFIX}/admin",
        tags=["MCP 广场管理"],
    ),
    RouterSpec(
        "app.routers.ai.ai_mcp",
        attr="mcp_tools_router",
        prefix=f"{API_V1_PREFIX}/admin",
        tags=["MCP 已注册工具"],
    ),
    
    # --- 21. AI Context Management (T1.4) ---
    RouterSpec("app.routers.ai.ai_context", tags=["AI Context Management"]),

    # --- 21~24. 搜索 / 规则 / 进化 / 工作空间 ---
    RouterSpec("app.routers.ai.ai_web_search", prefix=f"{API_V1_PREFIX}/admin", tags=["AI 联网搜索"]),
    # 以下 2 个模块自带完整 prefix（含 /api/v1），故此处不叠加
    RouterSpec("app.routers.ai.ai_skill_rule", tags=["Skill规则管理"]),
    RouterSpec("app.routers.ai.ai_skill_evolution", tags=["Skill进化管理"]),
    RouterSpec("app.routers.ai.ai_workspace", prefix=API_V1_PREFIX, tags=["工作空间管理"]),

    # --- 25. ReAct HITL ---
    RouterSpec("app.routers.ai.react", prefix=API_V1_PREFIX, tags=["ReAct HITL"]),

    # --- 26. DataOps（router 自带完整 prefix /api/v1/dataops，故 prefix 留空）---
    RouterSpec("app.routers.dataops.dataops", tags=["DataOps 数据源"]),

    # --- 26.1 外部知识库连接器（自带完整 prefix /api/v1/connectors）---
    # 2026-09-27 统一化：此前未注册（启用即 import 崩溃），现补齐实例/日志模型后上线
    RouterSpec("app.routers.connectors.connector", tags=["外部知识库连接器"]),

    # --- 26.2.1 Semantica 语义层（自带完整 prefix /api/v1/semantic，替代原本体治理）---
    RouterSpec("app.routers.semantica.semantica", tags=["语义/Semantica"]),

    # --- 26.3 Wiki 管理后台（自带 /wiki/admin，叠加 /api/v1）---
    RouterSpec("app.routers.wiki.wiki_admin", prefix=API_V1_PREFIX, tags=["Wiki 管理后台"]),

    # --- 27. 通知 ---
    RouterSpec("app.routers.sys.sys_notification", prefix=f"{API_V1_PREFIX}/admin", tags=["通知管理"]),

    # --- 28. LLM-wiki（router 自带 /wiki、/wiki/owl 相对前缀，此处叠加 /api/v1）---
    RouterSpec(
        "app.routers.wiki.wiki",
        prefix=API_V1_PREFIX,
        tags=["LLM-wiki"],
    ),


    # --- 28.1 通用知识库认证路由（spec §10.5；子应用仅内核间调用）---
    RouterSpec("app.routers.kb.kb", tags=["通用知识库"]),
    # --- 28.2 外部知识库检索代理（spec §10.2 proxy；SSRF 防护）---
    RouterSpec("app.routers.kb.kb_proxy", tags=["外部知识库代理"]),
    # --- 28.3 外部知识库文档导入向导（飞书/钉钉/语雀/企微/Notion）---
    RouterSpec("app.routers.kb.kb_external_source", tags=["外部知识库文档导入"]),
    # --- 28.4 通用知识库管理（知识库/分类 CRUD；2026-10 由 wiki.py 迁移，前缀 /api/v1/kb）---
    RouterSpec("app.routers.kb.knowledge_mgnt", tags=["知识库管理"]),
    # --- 28.5 图谱知识库（type=4 实例层；router 自带完整 prefix /api/v1/kb/knowledges/{kid}/graph）---
    RouterSpec("app.routers.kb.kg", tags=["图谱知识库"]),
    # --- 28.6 图谱构建管理（独立前缀 /graph-build，与查询端点分离）---
    RouterSpec("app.routers.kb.kg", attr="build_router", tags=["图谱构建"]),

    # --- 30. 工作流管理 ---
    RouterSpec("app.routers.workflow.workflow", tags=["工作流管理"]),

    # --- 30.1 SOP 模板库（自带完整 prefix /api/v1/sop，故 prefix 留空）---
    RouterSpec("app.routers.sop", tags=["SOP 模板"]),

    # --- 31~32. 调解语音 RTC（迁移自 risk_control）---
    # voice_gateway 自带 prefix /duplex/voice，此处叠加 /api/v1
    RouterSpec("app.duplex.voice.websocket_gateway", prefix=API_V1_PREFIX, tags=["调解语音"]),
    # admin_voice_config 自带 prefix /duplex/config，此处叠加 /api/v1/admin
    RouterSpec("app.routers.admin_voice_config", prefix=f"{API_V1_PREFIX}/admin", tags=["语音配置"]),

    # --- 33. 孪生应用（自带完整 prefix /api/v1/twins，故此处不叠加）---
    # Task 8 会在同一模块再加一条 attr="publish_router"（先例：app.routers.kb.kg 的
    # router + build_router 两条目，:202/:204），本期先不声明尚未存在的 publish_router。
    RouterSpec("app.routers.twin.twin", attr="router", tags=["孪生应用"]),
]


def _load_router(spec: RouterSpec) -> APIRouter:
    """导入并取出 router；对导入异常做一次重试。

    重试的必要性：同进程内并发/重复初始化 C 扩展（典型报错
    ``cannot load module more than once per process``）会让首个模块导入失败，
    而失败后 Python 会把半初始化的包从 ``sys.modules`` 清掉，导致其后整组
    接口静默 404（历史事故：``app.routers.kb.kb`` 失败使 /api/v1/kb/chunkers 等 52 条路由丢失）。
    """
    last_exc: Optional[BaseException] = None
    for attempt in range(IMPORT_ATTEMPTS):
        try:
            module = import_module(spec.module)
        except Exception as exc:  # noqa: BLE001 - 启动期需捕获全部导入异常
            last_exc = exc
            if attempt + 1 < IMPORT_ATTEMPTS:
                invalidate_caches()
                time.sleep(IMPORT_RETRY_DELAY)
                logger.warning(f"路由模块导入失败，重试 {spec.module} -> {exc}")
            continue

        router = getattr(module, spec.attr, None)
        if not isinstance(router, APIRouter):
            raise AttributeError(f"模块 {spec.module} 中未找到 APIRouter 属性 '{spec.attr}'")
        return router

    raise last_exc if last_exc is not None else ImportError(spec.module)


def register_routers(
    app: FastAPI,
    specs: Optional[List[RouterSpec]] = None,
    strict: Optional[bool] = None,
) -> List[str]:
    """按清单注册所有 router。

    :param app: FastAPI 应用实例
    :param specs: 路由清单，默认使用 ROUTER_SPECS
    :param strict: True 时单个 router 加载失败直接抛异常；None 时取环境变量
        ``ROUTER_STRICT``；False 时记录 CRITICAL 并跳过
    :return: 实际注册成功的 router 标签列表

    失败清单会写入 ``app.state.router_failures``（供 /health 与排障使用），
    避免「启动成功但整组接口 404」再次无声发生。
    """
    specs = ROUTER_SPECS if specs is None else specs
    strict = _strict_from_env() if strict is None else strict
    registered: List[str] = []
    skipped: List[str] = []
    failures: List[dict] = []

    for spec in specs:
        if not spec.enabled:
            skipped.append(f"{spec.label}(未启用)")
            continue

        try:
            router = _load_router(spec)
        except Exception as exc:  # noqa: BLE001 - 启动期需捕获全部加载异常
            failures.append({"module": spec.module, "attr": spec.attr, "error": str(exc)})
            msg = f"路由模块加载失败: {spec.label} -> {exc}"
            if strict:
                raise ImportError(msg) from exc
            logger.critical(msg)
            continue

        app.include_router(router, prefix=spec.prefix, tags=spec.tags)
        registered.append(spec.label)

    app.state.router_failures = failures

    logger.info(
        f"路由注册完成: 成功 {len(registered)} 个, 跳过 {len(skipped)} 个"
        + (f" [跳过: {', '.join(skipped)}]" if skipped else "")
    )
    if failures:
        # 这里必须 CRITICAL：受影响模块的所有接口都会返回 404，
        # 而服务本身仍显示「启动成功」，此前正是因此长时间误判为前端调错地址。
        logger.critical(
            f"有 {len(failures)} 个路由模块未注册，其接口将全部返回 404: "
            f"{', '.join(f['module'] for f in failures)}"
            "（常见原因：同进程重复初始化 C 扩展、解释器/虚拟环境混用；"
            "可置 ROUTER_STRICT=1 让启动直接失败）"
        )
    return registered
