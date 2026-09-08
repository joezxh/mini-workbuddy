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
2. **存在未启用的模块**：`app/routers/wiki/` 下的 `wiki.py` / `wiki_owl.py`
   目前未被注册（`wiki/__init__.py` 为空），自动扫描会把它暴露出去。
3. **`sys/__init__.py` 本身就是 router**（控制台统计/用户/菜单/角色/审计等），
   按「文件」扫描会与同目录 `sys_*.py` 产生归属歧义。
4. **单模块多 router**：`ai_mcp.py` 同时导出 4 个 router
   （router / client_router / square_router / mcp_tools_router）。

因此采用「显式清单」而非「隐式扫描」，保证重构前后路由表完全一致。
"""

from dataclasses import dataclass
from importlib import import_module
from typing import List, Optional

from fastapi import APIRouter, FastAPI
from loguru import logger


API_V1_PREFIX = "/api/v1"


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

    # --- 13~16. 技能 / 密钥 / 工具 ---
    RouterSpec("app.routers.ai.ai_skill", prefix=f"{API_V1_PREFIX}/ai-assistant/skills", tags=["AI技能"]),
    RouterSpec("app.routers.ai.ai_skill_hub", prefix=f"{API_V1_PREFIX}/ai-system/skill-hub", tags=["技能仓库"]),
    RouterSpec("app.routers.ai.ai_api_key", prefix=f"{API_V1_PREFIX}/admin", tags=["AI API密钥管理"]),
    RouterSpec("app.routers.ai.ai_tool", prefix=f"{API_V1_PREFIX}/admin", tags=["AI 工具管理"]),

    # --- 17~20. MCP：单模块导出 4 个 router ---
    RouterSpec("app.routers.ai.ai_mcp", attr="router", prefix=f"{API_V1_PREFIX}/admin", tags=["MCP API Key管理"]),
    RouterSpec(
        "app.routers.ai.ai_mcp",
        attr="client_router",
        prefix=f"{API_V1_PREFIX}/admin",
        tags=["MCP Client管理"],
    ),
    RouterSpec(
        "app.routers.ai.ai_mcp",
        attr="square_router",
        prefix=f"{API_V1_PREFIX}/admin",
        tags=["MCP广场管理"],
    ),
    RouterSpec(
        "app.routers.ai.ai_mcp",
        attr="mcp_tools_router",
        prefix=f"{API_V1_PREFIX}/admin",
        tags=["MCP已注册工具"],
    ),

    # --- 21~24. 搜索 / 规则 / 进化 / 工作空间 ---
    RouterSpec("app.routers.ai.ai_web_search", prefix=f"{API_V1_PREFIX}/admin", tags=["AI 联网搜索"]),
    # 以下 2 个模块自带完整 prefix（含 /api/v1），故此处不叠加
    RouterSpec("app.routers.ai.ai_skill_rule", tags=["Skill规则管理"]),
    RouterSpec("app.routers.ai.ai_skill_evolution", tags=["Skill进化管理"]),
    RouterSpec("app.routers.ai.ai_workspace", prefix=API_V1_PREFIX, tags=["工作空间管理"]),

    # --- 25. ReAct HITL ---
    RouterSpec("app.routers.ai.react", prefix=API_V1_PREFIX, tags=["ReAct HITL"]),

    # --- 26. 通知 ---
    RouterSpec("app.routers.sys.sys_notification", prefix=f"{API_V1_PREFIX}/admin", tags=["通知管理"]),

    # --- 未启用 ---
    # wiki 模块当前未完成（routers/wiki/__init__.py 为空，未导出），
    # 重构前即未注册，故保持 enabled=False 以维持现状；
    # 其 router 自带完整 prefix（/wiki、/wiki/owl），启用时 prefix 留空即可。
    RouterSpec(
        "app.routers.wiki.wiki",
        tags=["LLM-wiki"],
        enabled=False,
        note="未启用：模块未完成，__init__.py 未导出",
    ),
    RouterSpec(
        "app.routers.wiki.wiki_owl",
        tags=["Wiki OWL 本体"],
        enabled=False,
        note="未启用：模块未完成，__init__.py 未导出",
    ),
]


def register_routers(
    app: FastAPI,
    specs: Optional[List[RouterSpec]] = None,
    strict: bool = False,
) -> List[str]:
    """按清单注册所有 router。

    :param app: FastAPI 应用实例
    :param specs: 路由清单，默认使用 ROUTER_SPECS
    :param strict: True 时单个 router 加载失败直接抛异常；False 时记录错误并跳过
    :return: 实际注册成功的 router 标签列表
    """
    specs = ROUTER_SPECS if specs is None else specs
    registered: List[str] = []
    skipped: List[str] = []

    for spec in specs:
        if not spec.enabled:
            skipped.append(f"{spec.label}(未启用)")
            continue

        try:
            module = import_module(spec.module)
        except Exception as exc:  # noqa: BLE001 - 启动期需捕获全部导入异常
            msg = f"路由模块导入失败: {spec.module} -> {exc}"
            if strict:
                raise ImportError(msg) from exc
            logger.error(msg)
            continue

        router = getattr(module, spec.attr, None)
        if not isinstance(router, APIRouter):
            msg = f"模块 {spec.module} 中未找到 APIRouter 属性 '{spec.attr}'"
            if strict:
                raise AttributeError(msg)
            logger.error(msg)
            continue

        app.include_router(router, prefix=spec.prefix, tags=spec.tags)
        registered.append(spec.label)

    logger.info(
        f"路由注册完成: 成功 {len(registered)} 个, 跳过 {len(skipped)} 个"
        + (f" [跳过: {', '.join(skipped)}]" if skipped else "")
    )
    return registered
