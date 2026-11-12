"""WorkbenchService + ChatService —— SuperAgent 工作台服务层（Task 4.6）。

Feed / Ideas / Goals 三块业务 + 对话流（AgentScope）。
对齐 demo.html（docs/super-agent-demo/super-agent-demo.html）语义契约：
  - feed 5 kind（system/ai_batch/reminder/approval/goal_updated）
  - quiet 事件去抖 + 无 SSE 推送
  - ideas fingerprint = sha1(workspace_id + kind + pitch) 去重，LLM 失败回落 STARTER
  - goals steps 五态（done/pending/in_progress/blocked/skipped）
  - 全部 steps done/skipped → goal 自动 done + feed goal_updated
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

from loguru import logger
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.superagent_workbench import SaFeedPost, SaGoal, SaIdea
from app.ai.superagent.sse_bus import SSEBus


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _fingerprint(workspace_id: int, kind: str, pitch: str) -> str:
    return hashlib.sha1(f"{workspace_id}:{kind}:{pitch.strip()}".encode("utf-8")).hexdigest()


# ============ STARTER 预置 Idea（LLM 不可用时的回落） ============

STARTER_IDEAS = [
    {
        "emo": "🧹",
        "kind": "chat",
        "pitch": "整理本周 GitHub 提醒，合并为一份清单",
        "detail": "把本周的 issue 提醒去重汇总，标出需要优先处理的 3 项。",
        "prompt": "帮我把本周的 GitHub 提醒整理成一份清单，标出优先处理的项。",
        "src": "starter",
    },
    {
        "emo": "🎯",
        "kind": "goal",
        "pitch": "两周内把周报流程自动化",
        "detail": "拆解：梳理周报数据源 → 模板化 → 定时生成 → 人工复核。",
        "prompt": "帮我制定一个两周内把周报流程自动化的目标计划。",
        "src": "starter",
    },
    {
        "emo": "⏰",
        "kind": "routine",
        "pitch": "每天早上 9 点汇总昨日未读消息",
        "detail": "固定例行任务：拉取昨日未读，按群分类，给出一句话摘要。",
        "prompt": "建立例行任务：每天早上汇总昨日未读消息并分类摘要。",
        "src": "starter",
    },
]


class WorkbenchService:
    """Feed / Ideas / Goals 业务服务 —— 直接持有 Session factory。"""

    def __init__(self, db_factory: callable = SessionLocal):
        self._db_factory = db_factory
        self._bus = SSEBus.instance()

    # ============ Feed ============

    def publish_feed(
        self, workspace_id: int, kind: str, title: str,
        body: str = "", prompt: str | None = None, goal_id: str | None = None,
        ref_type: str | None = None, ref_id: str | None = None,
        quiet: bool = True,
    ) -> int:
        """发布一条 Feed。quiet=True 时不推 SSE（demo.html 去抖契约）。"""
        with self._db_factory() as db:
            post = SaFeedPost(
                workspace_id=workspace_id, kind=kind, title=title[:300],
                body=body, prompt=(prompt[:1000] if prompt else None),
                goal_id=goal_id, ref_type=ref_type, ref_id=ref_id, quiet=quiet,
            )
            db.add(post)
            db.commit()
            db.refresh(post)
            post_id = post.id
        if not quiet:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._bus.publish("feed_post", {
                    "id": post_id, "workspace_id": workspace_id, "kind": kind,
                    "title": title, "body": body, "prompt": prompt, "goal_id": goal_id,
                    "created_at": _now_iso(),
                }))
            except RuntimeError:
                # 无运行中 event loop（同步上下文调用）—— DB 已写入，跳过实时推送
                pass
        return post_id

    def list_feed(self, workspace_id: int, kind: str | None = None, limit: int = 200) -> list[dict]:
        with self._db_factory() as db:
            q = select(SaFeedPost).where(SaFeedPost.workspace_id == workspace_id)
            if kind:
                q = q.where(SaFeedPost.kind == kind)
            q = q.order_by(SaFeedPost.created_at.desc(), SaFeedPost.id.desc()).limit(min(limit, 200))
            return [self._post_dict(p) for p in db.scalars(q)]

    def mark_feed_read(self, post_id: int, workspace_id: int) -> bool:
        with self._db_factory() as db:
            post = db.get(SaFeedPost, post_id)
            if post is None or post.workspace_id != workspace_id:
                return False
            post.read = True
            db.commit()
            return True

    @staticmethod
    def _post_dict(p: SaFeedPost) -> dict:
        return {
            "id": p.id, "workspace_id": p.workspace_id, "kind": p.kind,
            "title": p.title, "body": p.body, "prompt": p.prompt,
            "goal_id": p.goal_id, "ref_type": p.ref_type, "ref_id": p.ref_id,
            "quiet": p.quiet, "read": p.read,
            "created_at": p.created_at.isoformat() + "Z" if p.created_at else None,
        }

    # ============ Ideas ============

    def list_ideas(self, workspace_id: int) -> list[dict]:
        with self._db_factory() as db:
            q = (
                select(SaIdea)
                .where(SaIdea.workspace_id == workspace_id)
                .order_by(SaIdea.pinned.desc(), SaIdea.created_at.desc())
            )
            return [self._idea_dict(i) for i in db.scalars(q)]

    def create_idea(
        self, workspace_id: int, emo: str, pitch: str, detail: str = "",
        kind: str = "chat", prompt: str | None = None, src: str = "manual",
    ) -> dict | None:
        """创建 Idea（fingerprint 去重）—— 重复返回 None。"""
        fp = _fingerprint(workspace_id, kind, pitch)
        with self._db_factory() as db:
            exists = db.scalar(select(SaIdea).where(
                SaIdea.workspace_id == workspace_id, SaIdea.fingerprint == fp))
            if exists:
                return None
            idea = SaIdea(
                workspace_id=workspace_id, emo=emo[:10] or "💡", pitch=pitch[:300],
                detail=detail, kind=kind, prompt=prompt, src=src[:64], fingerprint=fp,
            )
            db.add(idea)
            db.commit()
            db.refresh(idea)
            return self._idea_dict(idea)

    def pin_idea(self, idea_id: int, workspace_id: int) -> bool:
        with self._db_factory() as db:
            idea = db.get(SaIdea, idea_id)
            if idea is None or idea.workspace_id != workspace_id:
                return False
            idea.pinned = not idea.pinned
            db.commit()
            return True

    async def refresh_ideas(self, workspace_id: int, count: int = 3) -> list[dict]:
        """AI 批量生成 Idea —— LLM 失败回落 STARTER 预置卡。"""
        cards = await self._llm_ideas(workspace_id, count)
        src = "ai"
        if not cards:
            cards = [dict(c) for c in STARTER_IDEAS[:count]]
            src = "starter"
        created = []
        for c in cards:
            item = self.create_idea(
                workspace_id=workspace_id,
                emo=str(c.get("emo") or "💡"),
                pitch=str(c.get("pitch") or ""),
                detail=str(c.get("detail") or ""),
                kind=str(c.get("kind") or "chat"),
                prompt=c.get("prompt"), src=src,
            )
            if item:
                created.append(item)
        return created

    async def _llm_ideas(self, workspace_id: int, count: int) -> list[dict] | None:
        """用 AgentScope Agent 生成 Idea JSON 数组；任何失败返回 None。"""
        try:
            from agentscope.agent import Agent
            from agentscope.message import Msg, TextBlock
            from agentscope.tool import Toolkit
            from app.ai.strategy.factory_ext import (
                build_default_model_config, build_model,
            )

            cfg = build_default_model_config()
            model = build_model(cfg)
            sys_prompt = (
                "你是 MinWorkBuddy 工作台的 Idea 生成器。根据工作台上下文，"
                f"生成 {count} 条可执行的灵感卡片。只输出 JSON 数组，每条形如 "
                '{"emo": "emoji", "kind": "chat|goal|routine", "pitch": "一句话卖点(<=60字)",'
                ' "detail": "补充说明(<=120字)", "prompt": "可直接发给助手的指令"}，不要输出其他内容。'
            )
            agent = Agent(name="idea-generator", system_prompt=sys_prompt, model=model, toolkit=Toolkit())
            msg = Msg(name="user", role="user", content=[TextBlock(
                text=f"为 workspace_id={workspace_id} 的工作台生成 {count} 条灵感卡片。")])
            result = await agent.reply(msg)
            text = self._extract_text(result)
            # 提取 JSON 数组（容忍 ```json 包裹）
            start, end = text.find("["), text.rfind("]")
            if start < 0 or end <= start:
                return None
            cards = json.loads(text[start:end + 1])
            return cards if isinstance(cards, list) else None
        except Exception as e:
            logger.warning(f"refresh_ideas LLM failed — fallback STARTER: {e}")
            return None

    @staticmethod
    def _extract_text(result: Any) -> str:
        content = getattr(result, "content", result)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
                if isinstance(text, str) and text:
                    parts.append(text)
            return "\n".join(parts)
        return str(content)

    @staticmethod
    def _idea_dict(i: SaIdea) -> dict:
        return {
            "id": i.id, "workspace_id": i.workspace_id, "emo": i.emo,
            "pitch": i.pitch, "detail": i.detail, "kind": i.kind,
            "prompt": i.prompt, "src": i.src, "pinned": i.pinned,
            "created_at": i.created_at.isoformat() + "Z" if i.created_at else None,
        }

    # ============ Goals ============

    _STEP_DONE = {"done", "skipped"}

    def list_goals(self, workspace_id: int) -> list[dict]:
        with self._db_factory() as db:
            q = (
                select(SaGoal)
                .where(SaGoal.workspace_id == workspace_id)
                .order_by(SaGoal.created_at.desc())
            )
            return [self._goal_dict(g) for g in db.scalars(q)]

    def get_goal(self, goal_id: str, workspace_id: int) -> dict | None:
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            return self._goal_dict(goal)

    def create_goal(
        self, workspace_id: int, title: str, context: str = "",
        steps: list[str] | None = None, source: str = "manual",
        cron: str | None = None, due: str | None = None,
    ) -> dict:
        """创建 Goal —— steps 接收文本数组，初始化五态为 pending。"""
        step_objs = [
            {"idx": i, "text": s, "status": "pending"}
            for i, s in enumerate(steps or [])
        ]
        goal = SaGoal(
            id=uuid.uuid4().hex[:12], workspace_id=workspace_id,
            title=title[:300], context=(context[:300] or None),
            status="active", progress=0, cron=cron, due=due, source=source[:64],
            version=0, steps=step_objs, proposals=[], notes=[],
        )
        with self._db_factory() as db:
            db.add(goal)
            db.commit()
        self.publish_feed(
            workspace_id, "system", f"新目标：{title}", quiet=True,
            goal_id=goal.id, ref_type="goal", ref_id=goal.id,
        )
        return self.get_goal(goal.id, workspace_id)  # type: ignore[return-value]

    def patch_goal(self, goal_id: str, workspace_id: int, status: str) -> dict | None:
        if status not in {"active", "paused", "done", "cancelled"}:
            return None
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            goal.status = status
            db.commit()
        if status == "done":
            self.publish_feed(
                workspace_id, "goal_updated", f"目标完成：{goal.title}",
                quiet=False, goal_id=goal_id, ref_type="goal", ref_id=goal_id,
            )
        return self.get_goal(goal_id, workspace_id)

    def toggle_step(self, goal_id: str, workspace_id: int, step_idx: int) -> dict | None:
        """勾选/取消勾选 step（checkbox 语义：勾选 → done，取消 → pending）。

        全部 done/skipped 时自动完案。
        """
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            # JSON 列变更检测：必须 deep-copy（原地改 dict + 浅拷贝 list 会被
            # SQLAlchemy flush 判定 old == new 而跳过 UPDATE）
            steps = copy.deepcopy(goal.steps or [])
            for s in steps:
                if s.get("idx") == step_idx and s.get("status") != "skipped":
                    s["status"] = "pending" if s.get("status") == "done" else "done"
            goal.steps = steps
            goal.progress = self._calc_progress(steps)
            completed = self._auto_complete(goal, steps)
            db.commit()
        if completed:
            self.publish_feed(
                workspace_id, "goal_updated", f"目标完成：{goal.title}",
                quiet=False, goal_id=goal_id, ref_type="goal", ref_id=goal_id,
            )
        return self.get_goal(goal_id, workspace_id)

    def skip_step(self, goal_id: str, workspace_id: int, step_idx: int) -> dict | None:
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            steps = copy.deepcopy(goal.steps or [])
            for s in steps:
                if s.get("idx") == step_idx:
                    s["status"] = "skipped"
            goal.steps = steps
            goal.progress = self._calc_progress(steps)
            completed = self._auto_complete(goal, steps)
            db.commit()
        if completed:
            self.publish_feed(
                workspace_id, "goal_updated", f"目标完成：{goal.title}",
                quiet=False, goal_id=goal_id, ref_type="goal", ref_id=goal_id,
            )
        return self.get_goal(goal_id, workspace_id)

    async def propose(self, goal_id: str, workspace_id: int) -> dict | None:
        """Agent 基于目标上下文提出下一步建议（L4 proposal）。"""
        goal = self.get_goal(goal_id, workspace_id)
        if goal is None:
            return None
        suggestion = await self._llm_propose(goal)
        proposal = {
            "idx": len(goal.get("proposals") or []),
            "kind": "suggestion",
            "message": suggestion,
            "payload": {},
            "status": "pending",
            "created_at": _now_iso(),
        }
        with self._db_factory() as db:
            g = db.get(SaGoal, goal_id)
            props = list(g.proposals or [])
            props.append(proposal)
            g.proposals = props
            db.commit()
        await self._bus.publish("proposal_created", {
            "goal_id": goal_id, "workspace_id": workspace_id,
            "message": suggestion, "proposal_idx": proposal["idx"],
        })
        return self.get_goal(goal_id, workspace_id)

    def accept_proposal(self, goal_id: str, workspace_id: int, proposal_idx: int) -> dict | None:
        """接受建议 —— 按 payload 追加 step，version +1。"""
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            props = copy.deepcopy(goal.proposals or [])
            if proposal_idx >= len(props) or props[proposal_idx].get("status") != "pending":
                return None
            props[proposal_idx]["status"] = "accepted"
            payload = props[proposal_idx].get("payload") or {}
            new_step_text = payload.get("step") or props[proposal_idx].get("message", "")[:200]
            steps = list(goal.steps or [])
            steps.append({
                "idx": len(steps), "text": new_step_text, "status": "pending",
            })
            goal.steps = steps
            goal.proposals = props
            goal.version = (goal.version or 0) + 1
            goal.progress = self._calc_progress(steps)
            db.commit()
        return self.get_goal(goal_id, workspace_id)

    def dismiss_proposal(self, goal_id: str, workspace_id: int, proposal_idx: int) -> dict | None:
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            props = copy.deepcopy(goal.proposals or [])
            if proposal_idx >= len(props) or props[proposal_idx].get("status") != "pending":
                return None
            props[proposal_idx]["status"] = "dismissed"
            goal.proposals = props
            db.commit()
        return self.get_goal(goal_id, workspace_id)

    def add_note(self, goal_id: str, workspace_id: int, text: str) -> dict | None:
        with self._db_factory() as db:
            goal = db.get(SaGoal, goal_id)
            if goal is None or goal.workspace_id != workspace_id:
                return None
            notes = copy.deepcopy(goal.notes or [])
            notes.append({"ts": _now_iso(), "text": text[:500]})
            goal.notes = notes
            db.commit()
        return self.get_goal(goal_id, workspace_id)

    # --- 内部工具 ---

    @staticmethod
    def _calc_progress(steps: list[dict]) -> int:
        if not steps:
            return 0
        done = sum(1 for s in steps if s.get("status") in WorkbenchService._STEP_DONE)
        return int(round(done * 100 / len(steps)))

    def _auto_complete(self, goal: SaGoal, steps: list[dict]) -> bool:
        """全部 steps done/skipped → 自动完案（demo.html 契约）。"""
        if steps and goal.status == "active" and all(
            s.get("status") in self._STEP_DONE for s in steps
        ):
            goal.status = "done"
            goal.progress = 100
            goal.notes = list(goal.notes or []) + [{
                "ts": _now_iso(), "text": "所有步骤完成，目标自动完结。",
            }]
            return True
        return False

    async def _llm_propose(self, goal: dict) -> str:
        try:
            from agentscope.agent import Agent
            from agentscope.message import Msg, TextBlock
            from agentscope.tool import Toolkit
            from app.ai.strategy.factory_ext import (
                build_default_model_config, build_model,
            )

            model = build_model(build_default_model_config())
            steps_desc = "；".join(
                f"[{s.get('status')}] {s.get('text')}" for s in (goal.get("steps") or [])
            ) or "（暂无步骤）"
            agent = Agent(
                name="goal-advisor",
                system_prompt="你是目标管理顾问。基于目标当前进度给出下一步行动建议，只输出一句话建议（<=80字），不要输出其他内容。",
                model=model, toolkit=Toolkit(),
            )
            msg = Msg(name="user", role="user", content=[TextBlock(text=(
                f"目标：{goal.get('title')}\n当前步骤：{steps_desc}\n请给出下一步建议。"))])
            result = await agent.reply(msg)
            return self._extract_text(result).strip()[:200] or "建议：继续推进当前未完成的步骤。"
        except Exception as e:
            logger.warning(f"propose LLM failed — fallback: {e}")
            return "建议：继续推进当前未完成的步骤，优先处理 pending 状态的项。"

    @staticmethod
    def _goal_dict(g: SaGoal) -> dict:
        return {
            "id": g.id, "workspace_id": g.workspace_id, "title": g.title,
            "context": g.context, "status": g.status, "progress": g.progress,
            "cron": g.cron, "next_checkin": g.next_checkin, "due": g.due,
            "source": g.source, "version": g.version,
            "steps": g.steps or [], "proposals": g.proposals or [],
            "notes": g.notes or [],
            "created_at": g.created_at.isoformat() + "Z" if g.created_at else None,
            "updated_at": g.updated_at.isoformat() + "Z" if g.updated_at else None,
        }


# ============ ChatService —— 工作台对话（内存 session + AgentScope） ============

class ChatService:
    """工作台对话服务 —— session 在内存（重启丢失，prototype 语义）。"""

    def __init__(self, db_factory: callable = SessionLocal):
        self._sessions: dict[str, dict] = {}
        self._agents: dict[str, Any] = {}
        self._runs: dict[str, dict] = {}  # run_id → {"cancelled": bool}

    # --- Session 管理 ---

    def list_sessions(self, workspace_id: int) -> list[dict]:
        return [
            {"id": s["id"], "title": s["title"], "created_at": s["created_at"],
             "message_count": len(s["messages"])}
            for s in self._sessions.values()
            if s["workspace_id"] == workspace_id
        ]

    def create_session(self, workspace_id: int, title: str = "新对话") -> dict:
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = {
            "id": session_id, "workspace_id": workspace_id,
            "title": title[:100] or "新对话", "created_at": _now_iso(),
            "messages": [],
        }
        return self._sessions[session_id]

    def get_session(self, session_id: str, workspace_id: int | None = None) -> dict | None:
        s = self._sessions.get(session_id)
        if s is None or (workspace_id is not None and s["workspace_id"] != workspace_id):
            return None
        return s

    def abort(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        run["cancelled"] = True
        return True

    # --- Agent 构造（复用 executor/session.py 模式） ---

    def _get_agent(self, session_id: str) -> Any | None:
        if session_id in self._agents:
            return self._agents[session_id]
        try:
            from agentscope.agent import Agent
            from agentscope.tool import Toolkit
            from app.ai.strategy.factory_ext import (
                build_default_model_config, build_model,
            )

            model = build_model(build_default_model_config())
            agent = Agent(
                name=f"workbench-chat-{session_id}",
                system_prompt=(
                    "你是 MinWorkBuddy 工作台助手，帮用户处理日常工作：回答问题、"
                    "拆解目标、整理提醒。回答保持简洁、可执行。"
                ),
                model=model,
                toolkit=Toolkit(),
            )
            self._agents[session_id] = agent
            return agent
        except Exception as e:
            logger.warning(f"ChatService agent unavailable — stub: {e}")
            self._agents[session_id] = None
            return None

    # --- 流式回复（SSE 生成器） ---

    async def stream_reply(
        self, session_id: str, message: str, run_id: str,
    ) -> AsyncGenerator[str, None]:
        """SSE 流：text_delta* → done / interrupted。

        POST /chat/send 返回 StreamingResponse（fetch 读取流）。
        """
        session = self._sessions.get(session_id)
        if session is None:
            yield f"event: error\ndata: {json.dumps({'message': 'session not found'})}\n\n"
            return

        run = {"cancelled": False}
        self._runs[run_id] = run
        session["messages"].append({"role": "user", "text": message, "ts": _now_iso()})

        try:
            agent = self._get_agent(session_id)
            if agent is None:
                full_text = f"[stub] 已收到消息：{message[:100]}（AgentScope 不可用，降级回复）"
            else:
                from agentscope.message import Msg, TextBlock
                msg = Msg(name="user", role="user", content=[TextBlock(text=message)])
                result = await agent.reply(msg)
                full_text = WorkbenchService._extract_text(result)

            # 模拟打字机：按 6 字符切块 yield text_delta
            pos = 0
            while pos < len(full_text):
                if run["cancelled"]:
                    session["messages"].append({"role": "assistant", "text": full_text[:pos] + "…", "ts": _now_iso()})
                    yield f"event: interrupted\ndata: {json.dumps({'run_id': run_id})}\n\n"
                    return
                chunk = full_text[pos:pos + 6]
                pos += 6
                yield f"event: text_delta\ndata: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            session["messages"].append({"role": "assistant", "text": full_text, "ts": _now_iso()})
            yield f"event: done\ndata: {json.dumps({'run_id': run_id, 'session_id': session_id})}\n\n"
        except Exception as e:
            logger.error(f"ChatService.stream_reply failed: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            self._runs.pop(run_id, None)


# ============ 单例工厂 ============

_workbench_instance: WorkbenchService | None = None
_chat_instance: ChatService | None = None


def get_workbench() -> WorkbenchService:
    global _workbench_instance
    if _workbench_instance is None:
        _workbench_instance = WorkbenchService()
    return _workbench_instance


def get_chat() -> ChatService:
    global _chat_instance
    if _chat_instance is None:
        _chat_instance = ChatService()
    return _chat_instance
