"""研究编排用的轻量 LLM 调用封装（复用 AgentScope build_model + DB 模型配置）。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _build_model_config(model_id: Optional[int]) -> Dict[str, Any]:
    """复用 SkillExecutionService 的模型选取逻辑（DB 优先，ENV fallback）。

    model_id 有效时优先使用所选模型；所选模型 404/禁用/无 key 时返回空 dict，
    由调用方降级到 .env 全局兜底模型。
    """
    from app.ai.strategy.factory_ext import resolve_model_config

    if model_id:
        return resolve_model_config(model_id)
    # 未指定 model_id：沿用原逻辑取一个默认可用模型
    from app.db.database import SessionLocal
    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    db = SessionLocal()
    try:
        model = db.query(AiChatModel).filter(AiChatModel.status == 1).order_by(
            AiChatModel.sort.desc(), AiChatModel.id.asc()
        ).first()
        if not model:
            return {}
        api_key = db.query(AiApiKey).filter(
            AiApiKey.id == model.key_id, AiApiKey.status == 1
        ).first()
        if not api_key:
            return {}
        return {
            "provider": model.provider,
            "model": model.model_name,
            "base_url": model.base_url or "",
            "api_key": api_key.api_key,
            "temperature": 0.3,
        }
    except Exception as e:
        logger.warning(f"读取模型配置失败: {e}")
        return {}
    finally:
        db.close()


def _safe_text(obj: Any) -> str:
    """安全地从 AgentScope 响应对象中抽取文本。

    AgentScope 2.0.x 的 ChatResponse.content 是 block 列表（TextBlock / ThinkingBlock），
    且 AiChatModelBase.__call__ 是 async def，必须 await。这里集中处理 str / .text /
    content blocks / OpenAI 风格 choices 四种形态，避免抽到协程 repr 或 KeyError。
    """
    if isinstance(obj, str):
        return obj
    try:
        text = getattr(obj, "text", None)
        if text and isinstance(text, str):
            return text
    except Exception:
        pass
    try:
        content = getattr(obj, "content", None)
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                bt = getattr(block, "text", None)
                if bt and isinstance(bt, str):
                    parts.append(bt)
                    continue
                th = getattr(block, "thinking", None)
                if th and isinstance(th, str):
                    parts.append(th)
                    continue
                if isinstance(block, dict):
                    bt = block.get("text")
                    if bt and isinstance(bt, str):
                        parts.append(bt)
                        continue
                    th = block.get("thinking")
                    if th and isinstance(th, str):
                        parts.append(th)
            if parts:
                return "".join(parts)
    except Exception:
        pass
    try:
        choices = getattr(obj, "choices", None)
        if choices:
            return choices[0].message.content or ""
    except Exception:
        pass
    return str(obj)


async def _aclose_model(model: Any) -> None:
    """关闭 AgentScope ChatModel 持有的底层异步 HTTP 客户端。

    各 provider 的实现形态不统一：
    - OpenAI/DeepSeek/Moonshot/XAI 系：``model.client`` 是 ``openai.AsyncClient``，
      提供 ``close()`` 协程；其内部 ``_client`` 才是 ``httpx.AsyncClient``。
    - 部分 provider 直接持有 ``httpx.AsyncClient``（``aclose()``）。
    - DashScope/Gemini 等可能没有可关闭客户端。

    因此按 ``close`` → ``aclose`` 顺序探测，逐层降级；任何异常都吞掉，
    因为这只是资源清理，不应影响已经拿到的 LLM 结果。
    """
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
            except Exception as e:  # noqa: BLE001 清理失败不影响主流程
                logger.debug(f"[research.llm] 关闭模型客户端 {attr}.{closer_name} 失败: {e}")
            break
        else:
            continue
        break


async def llm_complete(prompt: str, model_id: Optional[int] = None, json_mode: bool = False) -> str:
    """调用 LLM 返回文本。json_mode 时尝试解析并回退原文。"""
    from agentscope.message import Msg, TextBlock
    from app.ai.strategy.factory_ext import build_model


    def _make_msg(name: str, role: str, text: str) -> Msg:
        """构造纯文本 Msg（agentscope 2.0.x 契约：content 为 TextBlock 列表）。

        ⚠️ 关键：agentscope 2.0.7 的 Msg 是 pydantic v2 BaseModel，不能用位置参数
        ``Msg("user", prompt, "user")`` 构造（会报 BaseModel.__init__ takes 1
        positional argument but 4 were given）。必须用 kwargs + TextBlock 工厂，
        与 app.ai.team.msg_utils.text_msg 保持一致。
        """
        return Msg(name=name, role=role, content=[TextBlock(text=text)])

    cfg = _build_model_config(model_id)
    if not cfg:
        cfg = {
            "provider": "openai",
            "model": os.environ.get("DEFAULT_MODEL", "gpt-4o-mini"),
            "base_url": os.environ.get("OPENAI_BASE_URL", ""),
            "api_key_ref": "ENV:OPENAI_API_KEY",
            "temperature": 0.3,
        }

    def _call():
        # AgentScope AiChatModelBase.__call__ 是 async def，必须在子线程内用 asyncio.run 驱动，
        # 让请求与消费处于同一 loop，避免跨 loop 永久挂起（团队编排侧有同类修复）。
        async def _drive() -> Any:
            # ⚠️ 关键：build_model 必须在 _drive 内部（即 asyncio.run 新建的 loop 上）执行。
            # OpenAIChatModel.__init__ 会立即构造 openai.AsyncClient（内含 httpx.AsyncClient
            # 连接池），该客户端会绑定到"构造时所在的 loop"。若在主 loop 里构造、却在子线程
            # 的新 loop 里发请求，连接对象归属错乱；asyncio.run 结束关闭 loop 后，GC 触发
            # AsyncClient.aclose() 时会向已关闭的 loop 提交回调 →
            # RuntimeError('Event loop is closed')（Task exception was never retrieved）。
            model = build_model(cfg)
            try:
                # 原生 ChatModel 接收 Sequence[Msg]，而非裸 dict 列表
                resp = await model([_make_msg("user", "user", prompt)])
                return _safe_text(resp)
            finally:
                # 显式在同一 loop 内关闭底层 HTTP 客户端，不留给 GC 兜底。
                await _aclose_model(model)
        return asyncio.run(_drive())

    logger.info(
        f"[research.llm] 调用模型 provider={cfg.get('provider')} model={cfg.get('model')} "
        f"base_url={cfg.get('base_url')} api_key_set={bool(cfg.get('api_key') or cfg.get('api_key_ref'))}"
    )
    try:
        text = await asyncio.to_thread(_call)
    except Exception as e:
        logger.error(f"研究 LLM 调用失败: {e}")
        raise
    logger.info(f"[research.llm] 模型原始返回(前200字): {text[:200]!r}")
    return text


async def llm_json(prompt: str, model_id: Optional[int] = None) -> Any:
    """调用 LLM 并解析为 JSON（失败抛出，不再静默返回空结构）。"""
    text = await llm_complete(prompt, model_id=model_id)
    if not text or not text.strip():
        raise ValueError("研究 LLM 返回空响应（模型未返回任何内容，可能是配置缺失/超时/连接失败）")
    try:
        return json.loads(text)
    except Exception:
        # 容错：截取首个 {...} 片段
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
        raise ValueError(f"研究 LLM 返回无法解析为 JSON（前200字）: {text[:200]!r}")
