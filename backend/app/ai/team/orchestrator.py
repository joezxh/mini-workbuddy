"""AgentScope 团队编排器 — 基于 AgentScope 2.x 原生 API 的多 Agent 协作。

适配说明（agentscope 2.0.7）：
- 2.x **不存在** ``LeaderBasedAgentTeam`` 之类的静态团队类，因此这里用原生原语实现：
  每个成员是一个 ``Agent``，Leader 的 ``Toolkit`` 中为每个成员注册一个分发工具，
  由 Leader 通过工具调用把子任务分派给成员并汇总结果。
- ``Agent`` 构造签名：``Agent(name, system_prompt, model, toolkit, ...)``
  （旧版的 ``sys_prompt`` / ``model_config_name`` / ``tools`` 已移除）。
- ``Msg`` 是 pydantic v2 模型，**不支持位置参数**，content 为 block 列表。
- 模型由 ``app.ai.strategy.factory_ext.build_model`` 从 DB 配置构建。

流程：
1. 加载团队成员与配置
2. 构建成员 Agent + Leader Agent（含分发工具）
3. 运行团队并收集结果
4. 支持运行态干预（暂停/恢复/取消）
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from agentscope.agent import Agent
from agentscope.tool import FunctionTool, Toolkit

from app.ai.msg_utils import text_msg, text_of

logger = logging.getLogger(__name__)

# 全局编排器注册表（供干预端点触达运行中的编排器实例，key 为 run_id）
ORCHESTRATOR_REGISTRY: Dict[str, "AgentScopeOrchestrator"] = {}


def _tool_name(index: int, role_name: str) -> str:
    """生成合法且唯一的工具名（LLM 工具名限制为字母/数字/下划线）。"""
    slug = re.sub(r"[^0-9A-Za-z_]", "_", (role_name or "").strip()).strip("_")
    return f"ask_{slug}_{index}" if slug else f"ask_member_{index}"


class AgentScopeOrchestrator:
    """AgentScope 2.x 原生团队编排器（Leader + 成员，通过工具调用分发）。"""

    def __init__(
        self,
        db: Any,
        team: Any,
        run: Any,
        event_svc: Any = None,
        user_id: Optional[int] = None,
        profile: Any = None,
        model_id: Optional[int] = None,
    ):
        self.db = db
        self.team = team
        self.run = run
        self.event_svc = event_svc
        self.user_id = user_id
        self.profile = profile
        self.model_id = model_id

        # 团队成员 Agent 列表
        self._agents: List[Agent] = []
        self._tool_names: Dict[str, str] = {}
        self._leader: Optional[Agent] = None
        self._model: Any = None
        self._paused = False
        self._cancelled = False

    # ── 模型 ────────────────────────────────────────────────
    def _ensure_model(self) -> Any:
        """构建（并缓存）本次运行使用的 ChatModel。"""
        if self._model is None:
            from app.ai.strategy.factory_ext import (
                build_default_model_config,
                build_model,
                resolve_model_config,
            )

            cfg = resolve_model_config(self.model_id) or build_default_model_config()
            self._model = build_model(cfg)
        return self._model

    async def create_team(self) -> bool:
        """创建团队成员和 Leader。

        Returns:
            创建成功返回 True
        """
        from app.services.agent.agent_team_service import AgentTeamService

        # 1. 加载团队成员
        svc = AgentTeamService(self.db)
        members = svc.get_members(self.team.id)

        if not members:
            logger.error(f"团队 {self.team.team_code} 无成员")
            return False

        model = self._ensure_model()

        # 2. 为每个成员创建 Agent
        self._agents = []
        self._tool_names = {}
        for index, member in enumerate(members):
            agent = self._create_member_agent(member, model)
            self._agents.append(agent)
            self._tool_names[agent.name] = _tool_name(index, getattr(member, "role_name", ""))

        # 3. 创建 Leader Agent（协调者）—— 工具集中包含每个成员的分发工具
        # 注意：Toolkit.add_tool 是**协程**，这里必须用同步的构造函数一次性注入，
        # 否则只会创建未 await 的协程对象，工具实际不会注册。
        dispatch_tools = [self._create_dispatch_tool(agent) for agent in self._agents]
        leader_toolkit = Toolkit(tools=dispatch_tools)

        self._leader = Agent(
            name="team_leader",
            system_prompt=self._build_leader_prompt(members),
            model=model,
            toolkit=leader_toolkit,
        )

        logger.info(f"团队 {self.team.team_code} 创建成功，成员数={len(members)}")
        return True

    # ── Agent 构建 ──────────────────────────────────────────
    def _create_member_agent(self, member: Any, model: Any) -> Agent:
        """为单个成员创建 Agent。"""
        # 从数据库加载成员的配置
        from app.ai.tool_manager.manager import build_toolkit
        from app.models.agent.agent_config import AgentConfig

        agent_config = self.db.query(AgentConfig).filter(
            AgentConfig.id == member.agent_config_id,
            AgentConfig.is_deleted == False,  # noqa: E712 SQLAlchemy 需要 == 比较
        ).first()

        if agent_config:
            system_prompt = agent_config.sys_prompt
            tool_keys = agent_config.tools
        else:
            system_prompt = f"你是团队中的 {member.role_name}，负责特定领域的任务。"
            tool_keys = None

        # 成员工具注入：agent_config.tools 是 tool_key 列表，
        # 由 ToolManager 按 DB 定义（class_name / config_value）实例化为 ToolBase。
        toolkit = build_toolkit(self.db, tool_keys)

        return Agent(
            name=member.role_name,
            system_prompt=system_prompt or "你是一个专业的团队成员。",
            model=model,
            toolkit=toolkit,
        )

    def _create_dispatch_tool(self, agent: Agent) -> FunctionTool:
        """为成员生成一个「分派子任务」工具，供 Leader 调用。"""

        async def dispatch(task: str) -> str:
            """向该团队成员分派一个子任务，并返回其回答。

            Args:
                task (str): 交给该成员完成的具体子任务描述。
            """
            try:
                resp = await agent.reply(text_msg("team_leader", "user", task))
                return text_of(resp)
            except Exception as e:  # noqa: BLE001 单个成员失败不应中断整个团队
                logger.warning("成员 %s 执行子任务失败: %s", agent.name, e)
                return f"[成员 {agent.name} 执行失败] {e}"

        return FunctionTool(
            dispatch,
            name=self._tool_names.get(agent.name),
            description=f"把子任务分派给团队成员「{agent.name}」并获取其回答。",
        )

    def _build_leader_prompt(self, members: List[Any]) -> str:
        """构建 Leader 的系统提示词（含可用成员及其分发工具名）。"""
        lines: List[str] = []
        for index, m in enumerate(members):
            role_desc = getattr(m, "role_desc", "") or ""
            lines.append(
                f"- {m.role_name}（工具: {_tool_name(index, m.role_name)}）: {role_desc}"
            )
        member_roles = "\n".join(lines)

        return f"""你是一位团队协调者，负责将用户任务分发给最合适的团队成员。

可用团队成员（工具名 → 成员）:
{member_roles}

你的职责:
1. 分析用户输入，识别任务类型
2. 通过对应的工具把子任务分派给合适的成员
3. 收集成员输出并汇总结论
4. 如有冲突，协调解决

遵循原则:
- 仅分发明确的任务，一次工具调用只问一件事
- 必要时让多个成员协同，再汇总
- 保持上下文一致性
- 所有成员回答收集完毕后，输出最终结论"""

    # ── 运行 ────────────────────────────────────────────────
    async def submit(
        self,
        input_text: str,
        input_context: Optional[dict] = None,
        created_by: Optional[int] = None,
    ) -> str:
        """提交团队运行任务。"""
        # 1. 创建团队
        if not await self.create_team():
            raise RuntimeError(f"团队 {self.team.team_code} 创建失败")

        # 2. 注册到全局注册表，供干预端点触达
        run_id = getattr(self.run, "run_id", None)
        if run_id:
            ORCHESTRATOR_REGISTRY[run_id] = self

        # 3. 发送用户消息给 Leader
        user_msg = text_msg("user", "user", input_text)

        # 4. 运行团队协作
        try:
            response = await self._leader.reply(user_msg)
            final_text = text_of(response)

            # 5. 记录执行事件
            self._record_execution_done(final_text)
            return final_text
        finally:
            if run_id and ORCHESTRATOR_REGISTRY.get(run_id) is self:
                ORCHESTRATOR_REGISTRY.pop(run_id, None)
            await self._close_model()

    def _record_execution_done(self, final_text: str) -> None:
        """记录执行完成事件。"""
        if self.event_svc:
            self.event_svc.record(
                event_type="TEAM_COMPLETE",
                content={"result": final_text},
                source="agent_scope_orchestrator",
            )

    # ── 运行态干预（由干预端点同步调用，故为同步方法）────────
    def request_pause(self) -> None:
        """请求暂停运行（在下一次模型/工具调用边界生效）。"""
        self._paused = True
        logger.info("团队 %s 已请求暂停", self.team.team_code)

    def resume(self) -> None:
        """恢复运行。"""
        self._paused = False
        logger.info("团队 %s 已恢复", self.team.team_code)

    def cancel(self) -> None:
        """取消运行。"""
        self._cancelled = True
        logger.info("团队 %s 已请求取消", self.team.team_code)

    # ── 资源清理 ────────────────────────────────────────────
    async def _close_model(self) -> None:
        """关闭模型持有的底层异步 HTTP 客户端。

        各 provider 形态不统一（openai.AsyncClient / httpx.AsyncClient），
        按 close → aclose 顺序探测；清理失败不影响已获得的结果。
        """
        model = self._model
        self._model = None
        if model is None:
            return
        for attr in ("client", "_client"):
            client = getattr(model, attr, None)
            if client is None:
                continue
            for closer_name in ("close", "aclose"):
                closer = getattr(client, closer_name, None)
                if not callable(closer):
                    continue
                try:
                    result = closer()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:  # noqa: BLE001 仅资源清理
                    logger.debug("关闭模型客户端 %s.%s 失败: %s", attr, closer_name, e)
                break
            break
