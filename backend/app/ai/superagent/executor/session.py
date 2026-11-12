"""WorkerSession —— per-Ticket 持久化 Worker 会话。

每个 Ticket 分配一个独立的 Worker Session + LocalWorkspace 目录。
接入 AgentScope Worker（如果安装了），否则用简化 Worker 做 stub。
"""
from __future__ import annotations
import asyncio, os, tempfile, subprocess, shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class LocalWorkspace:
    """每个 Ticket 独立的本地工作目录 —— 隔离文件操作。"""
    ticket_id: str
    path: Path
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, ticket_id: str) -> "LocalWorkspace":
        base = Path(tempfile.gettempdir()) / "superagent" / f"ticket-{ticket_id}"
        base.mkdir(parents=True, exist_ok=True)
        ws = cls(ticket_id=ticket_id, path=base, env={
            "SUPERAGENT_TICKET_ID": ticket_id,
            "SUPERAGENT_WORKSPACE": str(base),
        })
        logger.info(f"LocalWorkspace.create · {ticket_id} · {base}")
        return ws

    def cleanup(self) -> None:
        try:
            if self.path.exists():
                shutil.rmtree(self.path)
                logger.info(f"LocalWorkspace.cleanup · {self.ticket_id}")
        except Exception as e:
            logger.warning(f"LocalWorkspace.cleanup failed: {e}")

    async def run_prepare(self, prepare_cmd: str | None = None) -> subprocess.CompletedProcess[str] | None:
        """Prepare 命令 —— 在 workspace 内执行可选初始化脚本。"""
        if not prepare_cmd:
            return None
        logger.info(f"LocalWorkspace.prepare · {self.ticket_id} · {prepare_cmd}")
        proc = await asyncio.create_subprocess_shell(
            prepare_cmd, cwd=self.path, env={**os.environ, **self.env},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        return subprocess.CompletedProcess(args=prepare_cmd, returncode=proc.returncode,
                                            stdout=out.decode(), stderr=err.decode())


class WorkerSession:
    """per-Ticket Worker —— 支持 AgentScope Agent 或简化 stub。"""

    def __init__(self, ticket_id: str, prompt: str | None = None,
                 prepare_cmd: str | None = None, env: dict[str, str] | None = None,
                 model_id: int | None = None):
        self.ticket_id = ticket_id
        self.prompt = prompt or ""
        self.prepare_cmd = prepare_cmd
        self.env = env or {}
        self.model_id = model_id  # ai_chat_model.id —— None 时走 ENV 兜底
        self.ws = LocalWorkspace.create(ticket_id)
        self.session_name = f"worker-{ticket_id}"
        self._agent: Any = None  # AgentScope Agent 实例（可选）
        self._started = False

    async def start(self) -> None:
        """启动 Worker —— 先跑 prepare，再初始化 AgentScope（如果可用）。"""
        await self.ws.run_prepare(self.prepare_cmd)
        self._agent = self._try_agentscope_agent()
        self._started = True
        logger.info(f"WorkerSession.start · {self.session_name} · agent={'AgentScope' if self._agent else 'stub'}")

    def _try_agentscope_agent(self) -> Any:
        """构造 AgentScope 2.x Agent（真实 LLM 推理）—— 可选依赖。

        对齐 agent_factory._create_general_agent 的构造方式：
        ``Agent(name=..., system_prompt=..., model=ChatModelBase, toolkit=Toolkit)``。
        模型走 factory_ext.build_model（DB 配置 → ENV 兜底）。
        任何失败（未安装 / 模型不可用）都降级到 stub。
        """
        try:
            from agentscope.agent import Agent
            from agentscope.tool import Toolkit

            from app.ai.strategy.factory_ext import (
                build_default_model_config,
                build_model,
                resolve_model_config,
            )

            cfg = {}
            if self.model_id:
                cfg = resolve_model_config(int(self.model_id))
            model = build_model(cfg or build_default_model_config())
            sys_prompt = (self.prompt or "").strip()[:2000] or (
                "你是 SuperAgent Worker，负责完成分派给你的 Ticket 任务，"
                "完成后输出结构化的执行报告。"
            )
            agent = Agent(
                name=self.session_name,
                system_prompt=sys_prompt,
                model=model,
                toolkit=Toolkit(),
            )
            logger.info(f"WorkerSession · AgentScope 2.x Agent ready · {self.session_name}")
            return agent
        except Exception as e:
            logger.warning(f"AgentScope agent unavailable — using stub worker: {e}")
            return None

    @staticmethod
    def _extract_text(result: Any) -> str:
        """从 Msg.content 提取文本（content 可能是 str 或 ContentBlock 列表）。"""
        content = getattr(result, "content", result)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                text = (
                    block.get("text") if isinstance(block, dict)
                    else getattr(block, "text", None)
                )
                if isinstance(text, str) and text:
                    parts.append(text)
            return "\n".join(parts)
        return str(content)

    async def run(self, task: str, tools: list[Any] | None = None) -> str:
        """执行一个任务 —— 返回结果文本。"""
        if not self._started:
            await self.start()
        if self._agent is not None:
            return await self._run_agentscope(task, tools)
        return await self._run_stub(task)

    async def _run_agentscope(self, task: str, tools: list[Any] | None) -> str:
        """AgentScope Agent 执行 —— 完整 ReAct 循环。"""
        try:
            from agentscope.message import Msg, TextBlock
            # Msg 是 pydantic v2 BaseModel：必须 kwargs + TextBlock，不能位置传参
            msg = Msg(name="user", role="user", content=[TextBlock(text=task)])
            result = await self._agent.reply(msg)
            return self._extract_text(result)
        except Exception as e:
            logger.error(f"WorkerSession · AgentScope run failed: {e}")
            return f"[AgentScope error] {e}"

    async def _run_stub(self, task: str) -> str:
        """简化 stub —— 模拟 Worker 行为。"""
        await asyncio.sleep(0.5)
        return f"[stub-worker] ticket={self.ticket_id} task={task[:80]}"

    async def stop(self) -> None:
        """停止 Worker + 清理 workspace。"""
        self.ws.cleanup()
        self._started = False
        logger.info(f"WorkerSession.stop · {self.session_name}")
