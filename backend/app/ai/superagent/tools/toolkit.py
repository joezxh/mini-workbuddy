"""MCPToolkitFactory —— 为每个 Workspace 构建 Playwright + Windows Desktop Toolkit。

Task 2.4：安全边界 —— Playwright 只允许在 playwright_domain_whitelist 内导航，
windows-mcp / kira-mcp 只在 require_hitl_for_high_risk=False 时自动执行。
Task 2.4/2.5：LocalTool（Knowledge/Ontology/Sandbox 进程内工具）+ build_ticket_toolkit 组装。
"""
from __future__ import annotations
import asyncio
import inspect
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

from .mcp_adapter import MCPClient, MCPTool
from .mcp_config import MCPServerConfig


@dataclass
class LocalTool:
    """本地（非 MCP）工具 —— Knowledge/Ontology/Sandbox 等进程内能力的薄封装。

    handler 接收 arguments dict，同步/异步均可；调用错误由 handler 折叠为
    {"error": ...} 返回（Agent 友好），与 app/ai/tools 的模式一致。
    """
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    handler: Callable[..., Any] | None = None

    async def call(self, arguments: dict[str, Any] | None = None) -> Any:
        args = arguments or {}
        result = self.handler(args) if self.handler is not None else None
        if inspect.isawaitable(result):
            result = await result
        return result

    def as_dict(self) -> dict[str, Any]:
        """Agent 侧工具描述（与 MCPTool 字段同形）。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def resolve_workspace_tenant(db: Any, workspace_id: int | None) -> int | None:
    """由 AiWorkspace 解析 tenant_id —— 失败一律返回 None（不抛）。"""
    if db is None or workspace_id is None:
        return None
    try:
        from app.models.ai.ai_workspace import AiWorkspace

        ws = db.get(AiWorkspace, int(workspace_id))
        return getattr(ws, "tenant_id", None) if ws is not None else None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"resolve_workspace_tenant ws={workspace_id} failed: {e}")
        return None


def run_with_session(db: Any, fn: Callable[[Any], Any]) -> Any:
    """fn(session) —— db 已注入则复用，否则临时开 SessionLocal 并关闭。"""
    if db is not None:
        return fn(db)
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        return fn(session)
    finally:
        session.close()


@dataclass
class Toolkit:
    """一个 Workspace 的完整工具集。"""
    workspace_id: int
    clients: dict[str, MCPClient] = field(default_factory=dict)
    tools: dict[str, MCPTool] = field(default_factory=dict)
    extra_tools: dict[str, LocalTool] = field(default_factory=dict)

    async def connect_all(self) -> None:
        for name, client in self.clients.items():
            try:
                tools = await client.connect()
                for t in tools:
                    self.tools[f"{name}:{t.name}"] = t
                logger.info(f"Toolkit ws={self.workspace_id} · {name} · {len(tools)} tools")
            except Exception as e:
                logger.error(f"Toolkit ws={self.workspace_id} · {name} connect failed: {e}")

    async def call(self, tool_ref: str,
                   arguments: dict[str, Any] | None = None) -> Any:
        """MCP 工具 ref 格式 'playwright:browser_navigate'；本地工具直接 'kb_search'。"""
        if ":" not in tool_ref:
            tool = self.extra_tools.get(tool_ref)
            if tool is None:
                raise KeyError(f"No local tool '{tool_ref}' in toolkit")
            return await tool.call(arguments)
        server, _, tool = tool_ref.partition(":")
        client = self.clients.get(server)
        if client is None:
            raise KeyError(f"No MCP server '{server}' in toolkit")
        return await client.call_tool(tool, arguments)

    def tool_descriptions(self) -> list[dict[str, Any]]:
        """全部工具描述（已连接的 MCP 工具 + 本地 extra_tools），供 Worker 组装。"""
        mcp = [
            {"name": ref, "description": t.description, "input_schema": t.input_schema}
            for ref, t in self.tools.items()
        ]
        return mcp + [t.as_dict() for t in self.extra_tools.values()]

    async def close_all(self) -> None:
        for client in self.clients.values():
            try:
                await client.close()
            except Exception:
                pass


class MCPToolkitFactory:
    """按 ai_workspace.config.mcp_ids(JSON) 构建 Toolkit。"""

    PLAYWRIGHT_CMD = "npx"
    PLAYWRIGHT_ARGS = ["-y", "@playwright/mcp@latest"]
    WINDOWS_MCP_CMD = "windows-mcp"
    # windows-mcp>=0.8 是 click 多命令入口，需显式 `serve` 子命令（默认 stdio 传输）
    WINDOWS_MCP_ARGS = ["serve"]
    KIRA_MCP_CMD = "kira-mcp"

    @classmethod
    async def build(cls, workspace_id: int,
                    mcp_ids: list[str] | None = None,
                    domain_whitelist: list[str] | None = None) -> Toolkit:
        """构建 Toolkit —— 根据 mcp_ids(JSON) 确定要启动哪些 MCP Server。"""
        toolkit = Toolkit(workspace_id=workspace_id)
        enabled = set(mcp_ids or ["playwright"])  # 默认启 Playwright
        if "playwright" in enabled:
            toolkit.clients["playwright"] = MCPClient(
                cls.PLAYWRIGHT_CMD, list(cls.PLAYWRIGHT_ARGS)
            )
        if "windows-mcp" in enabled:
            toolkit.clients["windows-mcp"] = MCPClient(
                cls.WINDOWS_MCP_CMD, list(cls.WINDOWS_MCP_ARGS)
            )
        if "kira-mcp" in enabled:
            toolkit.clients["kira-mcp"] = MCPClient(cls.KIRA_MCP_CMD)
        await toolkit.connect_all()
        if domain_whitelist:
            logger.info(
                f"Toolkit ws={workspace_id} · Playwright domain whitelist: {domain_whitelist}"
            )
        return toolkit

    @classmethod
    async def build_ticket_toolkit(cls, ticket: Any, db: Any = None) -> Toolkit:
        """规格 2.5 —— 按 Ticket 配置组合 MCP Toolkit + Knowledge/Ontology/Sandbox 本地工具。

        ticket 可以是 dict 或 ORM 对象；kb_ids / mcp_ids / domain_whitelist 宽松读取
        （顶层字段或 config/payload 内）。任一路构建失败均降级为空，不阻断 Toolkit 创建
        （MCPClient.connect 失败已被 Toolkit.connect_all 捕获，本地工具 build 内部降级）。

        兼容映射（spec 步骤二）：mcp_ids 经统一登记装配路径解析（内置三件套 →
        ai_mcp_client 表），与 build_agent_toolkit 共用一套 MCP 归一逻辑。
        """

        def _field(name: str) -> Any:
            if isinstance(ticket, dict):
                return ticket.get(name)
            return getattr(ticket, name, None)

        config = _field("config") or _field("payload") or {}
        if not isinstance(config, dict):
            config = {}

        def _cfg(name: str) -> Any:
            v = _field(name)
            return v if v is not None else config.get(name)

        workspace_id = _field("workspace_id")
        tenant_id = _field("tenant_id")
        if tenant_id is None:
            tenant_id = resolve_workspace_tenant(db, workspace_id)

        toolkit = Toolkit(workspace_id=workspace_id if workspace_id is not None else 0)
        # 旧契约：mcp_ids 缺省时默认启 Playwright
        mcp_ids = _cfg("mcp_ids") or ["playwright"]
        entries = _resolve_mcp_server_entries(mcp_ids, db)
        domain_whitelist = _cfg("domain_whitelist")
        _fill_toolkit_clients(toolkit, entries)
        await toolkit.connect_all()
        if domain_whitelist:
            logger.info(
                f"Toolkit ws={workspace_id} · Playwright domain whitelist: {domain_whitelist}"
            )

        # 延迟导入防循环依赖；各 build() 内部已保证降级不抛
        from .knowledge import KnowledgeTools
        from .ontology import OntologyTools
        from .sandbox import SandboxTools

        for tools in (
            KnowledgeTools.build(workspace_id, collection_ids=_cfg("kb_ids"),
                                 db=db, tenant_id=tenant_id),
            OntologyTools.build(workspace_id, db=db, tenant_id=tenant_id),
            SandboxTools.build(workspace_id),
        ):
            for tool in tools:
                toolkit.extra_tools[tool.name] = tool

        logger.info(
            f"build_ticket_toolkit ws={workspace_id} ticket={_field('id')} · "
            f"mcp_tools={len(toolkit.tools)} · local_tools={len(toolkit.extra_tools)}"
        )
        return toolkit


# ===========================================================================
# 统一登记装配（spec 步骤二）—— mcp_servers 三态归一 + build_agent_toolkit
# ===========================================================================

# 内置三件套（与 MCPToolkitFactory 类常量保持一致）
_BUILTIN_MCP_SERVERS: dict[str, dict] = {
    "playwright": {
        "name": "playwright",
        "command": MCPToolkitFactory.PLAYWRIGHT_CMD,
        "args": list(MCPToolkitFactory.PLAYWRIGHT_ARGS),
        "env": {},
    },
    "windows-mcp": {
        "name": "windows-mcp",
        "command": MCPToolkitFactory.WINDOWS_MCP_CMD,
        # windows-mcp>=0.8 是 click 多命令入口，需显式 `serve` 子命令
        "args": list(MCPToolkitFactory.WINDOWS_MCP_ARGS),
        "env": {},
    },
    "kira-mcp": {
        "name": "kira-mcp",
        "command": MCPToolkitFactory.KIRA_MCP_CMD,
        "args": [],
        "env": {},
    },
}


def _is_windows_mcp_cmd(command: str) -> bool:
    """命令是否指向 windows-mcp 入口（兼容 .cmd/.exe 后缀与路径写法）。"""
    base = os.path.basename(str(command or "").strip().strip('"'))
    stem = os.path.splitext(base)[0].lower()
    return stem == "windows-mcp"


def _normalize_inline_mcp(entry: dict) -> dict | None:
    """内联 dict 配置归一为 {name, command, args, env}；缺 command 返回 None。"""
    command = entry.get("command") or entry.get("cmd")
    if not command:
        return None
    name = str(entry.get("name") or entry.get("server") or command)
    args = [str(a) for a in (entry.get("args") or []) if str(a).strip()]
    env = {str(k): str(v) for k, v in (entry.get("env") or {}).items()}
    # 保留 WINDOWS_MCP_ARGS 定制：windows-mcp 入口缺 serve 子命令时自动补齐
    if _is_windows_mcp_cmd(command) and "serve" not in args:
        args = ["serve", *args]
    return {"name": name, "command": str(command), "args": args, "env": env}


def _lookup_mcp_client_entry(ref: Any, db: Any) -> dict | None:
    """按 id 或 name 查 ai_mcp_client 表，提取 stdio 启动配置。

    tools_config 存储形状（宽松兼容）：
      1. 顶层 {command/cmd, args, env}
      2. mcp 官方 client-config 形状 {"mcpServers": {name: {command, args, env}}}
    非 stdio（http/sse）或缺 command 的记录跳过（自研 MCPClient 仅支持 stdio）。
    """
    if db is None:
        return None
    try:
        from sqlalchemy import or_

        from app.models.ai.ai_mcp_client import AiMcpClient

        query = db.query(AiMcpClient)
        text = str(ref).strip()
        if isinstance(ref, int) or text.isdigit():
            query = query.filter(or_(AiMcpClient.id == int(text), AiMcpClient.name == text))
        else:
            query = query.filter(AiMcpClient.name == text)
        row = query.first()
    except Exception as e:  # noqa: BLE001 —— DB 不可用只降级该条目
        logger.warning(f"ai_mcp_client 查询失败 ref={ref}: {e}")
        return None
    if row is None:
        return None

    cfg = row.tools_config if isinstance(row.tools_config, dict) else {}
    command = cfg.get("command") or cfg.get("cmd")
    args = [str(a) for a in (cfg.get("args") or []) if str(a).strip()]
    env = {str(k): str(v) for k, v in (cfg.get("env") or {}).items()}
    if not command and isinstance(cfg.get("mcpServers"), dict):
        for _, scfg in cfg["mcpServers"].items():
            if isinstance(scfg, dict) and (scfg.get("command") or scfg.get("cmd")):
                command = scfg.get("command") or scfg.get("cmd")
                args = [str(a) for a in (scfg.get("args") or []) if str(a).strip()]
                env = {str(k): str(v) for k, v in (scfg.get("env") or {}).items()}
                break
    if not command:
        logger.warning(f"ai_mcp_client {row.name}(id={row.id}) 缺少 stdio 启动命令，跳过")
        return None
    if _is_windows_mcp_cmd(command) and "serve" not in args:
        args = ["serve", *args]
    return {"name": str(row.name), "command": str(command), "args": args, "env": env}


def _resolve_mcp_server_entries(raw: Any, db: Any = None) -> dict[str, dict]:
    """mcp_servers 登记列表 → {server_name: {name, command, args, env}}。

    三态兼容：
      - dict：内联配置 {name, command/cmd, args, env, transport?}
      - int / 数字 str：ai_mcp_client.id
      - 其它 str：内置三件套（playwright/windows-mcp/kira-mcp）→ ai_mcp_client.name
    """
    entries: dict[str, dict] = {}
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return entries
    for item in raw:
        entry: dict | None = None
        if isinstance(item, dict):
            entry = _normalize_inline_mcp(item)
        else:
            key = str(item).strip()
            if not key:
                continue
            entry = _BUILTIN_MCP_SERVERS.get(key) or _lookup_mcp_client_entry(key, db)
        if entry and entry.get("command"):
            entries[entry["name"]] = entry
        elif item not in (None, ""):
            logger.warning(f"mcp_servers 条目不可解析，已跳过: {item!r}")
    return entries


def _fill_toolkit_clients(toolkit: "Toolkit", entries: dict[str, dict]) -> None:
    """按归一配置实例化 MCPClient（32MB limit / Windows .cmd 解析在 connect 内）。"""
    for name, entry in entries.items():
        if name in toolkit.clients:
            continue  # 同名 server 不重复实例化
        toolkit.clients[name] = MCPClient(
            entry["command"], list(entry.get("args") or []),
            env=entry.get("env") or None,
        )


def _normalize_agent_keys(raw: Any) -> list[str]:
    """tools/skills/knowledge_bases 登记列表 → 字符串 key 列表（兼容 dict/单值形态）。"""
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = raw.get("tools") or raw.get("skills") or raw.get("knowledge_bases") or []
    if isinstance(raw, (str, int)):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return []
    return [str(x).strip() for x in raw if str(x).strip() and str(x).strip() != "None"]


def _load_tool_definition(db: Any, key: str):
    """按 tool_key（兼容主键 id）查 ai_tool_definition；不可用返回 None。"""
    if db is None:
        return None
    try:
        from sqlalchemy import or_

        from app.models.ai.ai_tool_definition import AiToolDefinition

        query = db.query(AiToolDefinition).filter(AiToolDefinition.tool_key == key)
        if key.isdigit():
            query = query.filter(or_(
                AiToolDefinition.tool_key == key,
                AiToolDefinition.id == int(key),
            ))
        return query.first()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"ai_tool_definition 查询失败 key={key}: {e}")
        return None


def _mcp_tool_server_ref(defn: Any) -> tuple[Any, list[str] | None]:
    """tool_type=mcp 的 ai_tool_definition → (server 引用, 工具白名单)。

    config_value 存储形状：{mcp_server|server|mcp_server_id|server_id: <引用>,
    tools?: [工具名白名单]}。
    """
    cfg = defn.config_value if isinstance(defn.config_value, dict) else {}
    ref = (cfg.get("mcp_server") or cfg.get("server")
           or cfg.get("mcp_server_id") or cfg.get("server_id"))
    whitelist = cfg.get("tools") or cfg.get("tool_names") or None
    if whitelist and not isinstance(whitelist, (list, tuple, set)):
        whitelist = [str(whitelist)]
    return ref, list(whitelist) if whitelist else None


def _wrap_toolbase_as_local(tool: Any) -> "LocalTool | None":
    """把 ai 包 ToolBase 实例桥接为 superagent LocalTool（错误折叠为 error 字段）。"""
    name = getattr(tool, "name", None) or tool.__class__.__name__
    if not name:
        return None

    async def _handler(args: dict[str, Any]) -> Any:
        try:
            chunk = await tool.call(**(args or {}))
            content = getattr(chunk, "content", None)
            if content is not None:  # ToolChunk → 提取首个文本块
                for block in content:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        try:
                            return json.loads(text)
                        except (json.JSONDecodeError, ValueError):
                            return text
                return {"result": str(chunk)}
            return chunk
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    return LocalTool(
        name=str(name),
        description=str(getattr(tool, "description", "") or ""),
        input_schema=getattr(tool, "input_schema", {}) or {},
        handler=_handler,
    )


def _build_skill_tool(skill_name: str) -> "LocalTool":
    """登记 skill → LocalTool（lazy 调 SkillExecutionService，事件流聚合为文本）。"""

    async def _handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            from app.ai.skills.execution import SkillExecutionService

            user_message = ""
            if isinstance(args, dict):
                user_message = str(args.get("task") or args.get("query")
                                   or args.get("input") or "")
            parts: list[str] = []
            async for ev in SkillExecutionService().execute(
                skill_name=skill_name, user_message=user_message,
            ):
                data = ev.data if isinstance(ev.data, dict) else {}
                for key in ("text", "content", "message", "result"):
                    v = data.get(key)
                    if isinstance(v, str) and v:
                        parts.append(v)
                        break
            output = "\n".join(parts).strip()
            if output:
                return {"skill": skill_name, "output": output}
            return {"error": f"技能 {skill_name} 无输出"}
        except Exception as e:  # noqa: BLE001
            return {"error": f"技能 {skill_name} 执行失败: {e}"}

    return LocalTool(
        name=f"skill_{skill_name}",
        description=f"执行已登记技能 {skill_name}",
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "技能执行的任务描述"},
            },
        },
        handler=_handler,
    )


async def build_agent_toolkit(agent_kwargs: dict, db: Any = None,
                              workspace_id: int = 0,
                              tenant_id: int | None = None) -> Toolkit:
    """按 agent_config.to_agent_kwargs() 形状装配 superagent Toolkit（spec 步骤二）。

    能力唯一来源为登记数据：
      - mcp_servers 三态 → MCPClient 实例（connect 失败降级，不阻断）
      - tools（tool_key）→ ai_tool_definition 解析；tool_type=mcp 映射到
        mcp_servers 对应实例（不重复实例化），custom 经 ToolManager 解析桥接
      - knowledge_bases → kb_search 本地工具
      - skills → skill_<name> 本地工具
    返回物与 build_ticket_toolkit 同型（superagent Toolkit）。
    """
    kwargs = agent_kwargs or {}
    toolkit = Toolkit(workspace_id=workspace_id)

    entries = _resolve_mcp_server_entries(kwargs.get("mcp_servers"), db)

    # tools 分类：mcp 型并入 server 解析（避免重复实例化），其余走 ToolManager
    custom_keys: list[str] = []
    mcp_whitelists: dict[str, list[str]] = {}
    for key in _normalize_agent_keys(kwargs.get("tools")):
        defn = _load_tool_definition(db, key)
        if defn is not None and (defn.tool_type or "") == "mcp":
            ref, whitelist = _mcp_tool_server_ref(defn)
            if ref is None:
                logger.warning(f"mcp 型工具 {key} 未关联 mcp_server，跳过")
                continue
            entry = (ref if isinstance(ref, dict) else None) \
                or _BUILTIN_MCP_SERVERS.get(str(ref).strip()) \
                or _lookup_mcp_client_entry(ref, db)
            if entry and entry.get("command"):
                entries.setdefault(entry["name"], entry)
                if whitelist:
                    merged = set(mcp_whitelists.get(entry["name"], [])) | set(whitelist)
                    mcp_whitelists[entry["name"]] = sorted(merged)
            else:
                logger.warning(f"mcp 型工具 {key} 的 server 引用不可解析: {ref!r}")
            continue
        custom_keys.append(key)

    _fill_toolkit_clients(toolkit, entries)
    await toolkit.connect_all()

    # mcp 工具白名单过滤（config_value.tools 指定仅暴露哪些工具）
    for server, whitelist in mcp_whitelists.items():
        toolkit.tools = {
            ref: t for ref, t in toolkit.tools.items()
            if ref.partition(":")[0] != server or ref.partition(":")[2] in whitelist
        }

    # 本地工具：Knowledge（登记 kb_ids）+ Ontology + Sandbox（与 ticket 同款组合）
    from .knowledge import KnowledgeTools
    from .ontology import OntologyTools
    from .sandbox import SandboxTools

    kb_ids = _normalize_agent_keys(kwargs.get("knowledge_bases"))
    for tools in (
        KnowledgeTools.build(workspace_id, collection_ids=kb_ids or None,
                             db=db, tenant_id=tenant_id),
        OntologyTools.build(workspace_id, db=db, tenant_id=tenant_id),
        SandboxTools.build(workspace_id),
    ):
        for tool in tools:
            toolkit.extra_tools.setdefault(tool.name, tool)

    # custom tools → ToolManager 解析后桥接
    if custom_keys:
        from app.ai.tool_manager.manager import _resolve_tool

        for key in custom_keys:
            tool = _resolve_tool(db, key) if db is not None else None
            if tool is None:
                logger.warning(f"工具 {key} 不可用，未注入 SUPERAGENT toolkit")
                continue
            bridged = _wrap_toolbase_as_local(tool)
            if bridged is not None:
                toolkit.extra_tools.setdefault(bridged.name, bridged)

    # skills → skill_<name> 本地工具
    for skill_name in _normalize_agent_keys(kwargs.get("skills")):
        toolkit.extra_tools.setdefault(
            f"skill_{skill_name}", _build_skill_tool(skill_name))

    logger.info(
        f"build_agent_toolkit agent={kwargs.get('agent_code')} · "
        f"servers={list(toolkit.clients)} · mcp_tools={len(toolkit.tools)} · "
        f"local_tools={list(toolkit.extra_tools)}"
    )
    return toolkit


def build_agent_toolkit_sync(agent_kwargs: dict, db: Any = None,
                             workspace_id: int = 0,
                             tenant_id: int | None = None) -> Toolkit:
    """build_agent_toolkit 的同步包装 —— AgentFactory 等同步上下文消费。

    已处于运行事件循环（FastAPI 请求内）时，切换到独立线程执行，避免嵌套 loop。
    """
    coro = build_agent_toolkit(agent_kwargs, db=db, workspace_id=workspace_id,
                               tenant_id=tenant_id)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
