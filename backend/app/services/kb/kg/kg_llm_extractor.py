"""LLM 抽取通道（图谱）—— 中文长文本的唯一可行解。

为什么要新加这一层
------------------
semantica 的 ``TripletExtractor`` 在缺 spaCy 时退化为**面向英文的正则/模式**：
中文切片实测零实体，英文切片只能得到 ``related_to`` 全连接的弱关系。
生产语料以中文为主，规则通道等于没有抽取。

为什么不用 semantica 自带的 LLM provider
-----------------------------------------
它的 :class:`semantica.semantic_extract.llm_extraction.LLMExtraction` 是
「**增强**已有抽取结果」而非主抽取器，且 provider 凭据取 ``OPENAI_API_KEY``
一类独立环境变量 —— 与本项目的**模型管理**（``ai_chat_model`` + ``ai_api_key``，
前端选的模型、本地 GPUStack/llama.cpp 的 base_url）是两套体系。
故本层只做「组 prompt + 解析」，模型一律走
:func:`app.ai.strategy.factory_ext.build_model`（R5：不另起一套模型栈）。

工程立场
--------
* **LLM 输出不可信**：本层只负责把响应变成 raw dict 列表，
  长度守卫 / 去重 / 悬空边丢弃全部复用
  :mod:`app.services.kb.kg.kg_extractor` 的同一套规整层——两条通道共用一份校验，
  避免「LLM 通道少校验一项」的隐性分叉。
* **降级必须显式**：模型不可用 / 响应解析失败一律抛错，由构建服务登记到
  ``graph_extraction_details.errors`` 与文档 ``error_detail``，
  绝不静默返回空结果（静默空结果在前端与「抽不到」不可区分）。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable, Optional, Tuple

from loguru import logger

# 单切片实体/关系上限：本地小模型一旦放开就会自造一堆无关实体
MAX_ENTITIES = 40
MAX_RELATIONS = 60
# 送进 prompt 的正文上限（字符）：留出输出与指令空间
MAX_TEXT_CHARS = 6000

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


# ── 模型配置解析 ─────────────────────────────────────────────────────────
def _row_to_cfg(db, model, api_key) -> dict:
    """``ai_chat_model`` + ``ai_api_key`` → ``build_model`` 可用的配置 dict。

    统一走 :func:`app.ai.strategy.factory_ext.build_config_from_rows`：
    字段名（``platform`` / ``model``）只在这一处映射，避免与技能侧口径分叉。
    OpenAI 兼容平台的 ``base_url`` 需要 ``/v1`` 后缀（与向量化侧同一规则）；
    平台是否属 OpenAI 兼容交给 ``normalize_provider`` 判定，不在此重复平台词典。
    """
    from app.ai.strategy.factory_ext import build_config_from_rows, normalize_provider

    cfg = build_config_from_rows(model, api_key)
    base_url = (cfg.get("base_url") or "").strip().rstrip("/")
    if base_url and normalize_provider(cfg.get("provider")) != "dashscope":
        from app.services.kb.embedding_config import normalize_openai_base_url

        base_url = normalize_openai_base_url(base_url)
    cfg["base_url"] = base_url
    cfg["model_code"] = getattr(model, "code", None) or str(model.id)
    return cfg


def resolve_llm_config(db, model_spec: Any = None) -> Optional[dict]:
    """按 ``pipeline_config.graph.model_spec`` 解析对话模型配置；不可用返回 ``None``。

    ``model_spec`` 兼容三种形态（前端与手工配置都可能写出）：
    ``"编码串"`` / ``{"code": "..."}`` / ``{"model_id": 3}``；
    全空则取模型管理里的**默认对话模型**（``type=1 + is_default + status=1``），
    没有标默认就退化为「启用且 sort 最大」的对话模型 —— 与技能执行侧同一口径。

    租户不参与筛选：``ai_chat_model`` 在现有取模型链路（``registry_bridge`` /
    技能执行）里一律全局取用，此处不自创一套隔离口径。
    """
    from sqlalchemy import select

    from app.models.ai.ai_api_key import AiApiKey, AiChatModel

    spec = model_spec if isinstance(model_spec, dict) else {}
    code = spec.get("code") or spec.get("model_code") or (
        model_spec if isinstance(model_spec, str) else None
    )
    model_id = spec.get("model_id") or spec.get("id")

    try:
        if model_id:
            model = db.get(AiChatModel, int(model_id))
        elif code:
            model = db.execute(
                select(AiChatModel).where(
                    AiChatModel.code == str(code), AiChatModel.status == 1
                )
            ).scalars().first()
        else:
            stmt = select(AiChatModel).where(
                AiChatModel.status == 1, AiChatModel.type == 1
            )
            model = db.execute(
                stmt.where(AiChatModel.is_default.is_(True))
                .order_by(AiChatModel.id.asc())
            ).scalars().first()
            if model is None:
                model = db.execute(
                    stmt.order_by(AiChatModel.sort.desc(), AiChatModel.id.asc())
                ).scalars().first()

        if model is None or getattr(model, "status", 1) != 1:
            logger.warning(f"[kg] 图谱抽取模型不可用: spec={model_spec!r}")
            return None

        key = db.get(AiApiKey, model.key_id)
        if key is None or getattr(key, "status", 1) != 1:
            logger.warning(
                f"[kg] 图谱抽取模型 {model.code or model.id} 关联的 API 密钥缺失/已禁用"
            )
            return None
        return _row_to_cfg(db, model, key)
    except Exception as exc:  # noqa: BLE001 - 查库失败交由调用方降级
        logger.warning(f"[kg] 解析图谱抽取模型配置失败: {exc}")
        # 必须回滚：psycopg2 里查询报错会把事务打成 aborted 状态，不回滚则同
        # Session 后续每一条 SQL 都报 InFailedSqlTransaction ——一个「查不到模型」
        # 的降级分支会把整批构建带崩。
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - 回滚失败不掩盖原始错误
            pass
        return None


# ── prompt 与响应解析 ────────────────────────────────────────────────────
def build_prompt(
    text: str,
    *,
    schema_hint: str = "",
    max_entities: int = MAX_ENTITIES,
    max_relations: int = MAX_RELATIONS,
) -> str:
    """组装抽取指令。

    三条硬约束来自实测踩坑：只输出 JSON（否则解析失败）、
    ``name`` 必须原文出现（否则模型改写出的实体会让关系端点对不上）、
    关系端点必须来自实体表（否则落库时整条被丢弃，白花钱）。
    """
    parts = [
        "你是知识图谱抽取器。阅读文本，抽取其中的实体与关系，只输出一个 JSON 对象。",
        "",
        "输出结构：",
        '{"entities": [{"name": "实体名", "label": "类型", '
        '"aliases": ["别名"], "properties": {}}], '
        '"relations": [{"source": "起点实体名", "target": "终点实体名", '
        '"relation_type": "关系", "text": "支撑该关系的原文片段"}]}',
        "",
        "硬性要求：",
        f"1. 实体不超过 {max_entities} 个，关系不超过 {max_relations} 个；",
        "2. name 必须是原文中出现的表述，不要改写、不要补全缩写、不要翻译；",
        "3. relations 的 source 与 target 必须原样出现在 entities 的 name 中，否则会被丢弃；",
        "4. 无法确定的字段填空字符串或空对象，不要编造；",
        "5. 只输出 JSON，不要输出解释、前后缀或代码块围栏。",
    ]
    hint = (schema_hint or "").strip()
    if hint:
        parts += ["", "类型约束（优先遵守，不在集合内的类型宁可不标）：", hint]
    body = (text or "")[:MAX_TEXT_CHARS]
    parts += ["", "文本：", '"""', body, '"""']
    return "\n".join(parts)


def parse_response(raw: str) -> Tuple[list, list]:
    """LLM 响应 → ``(raw_entities, raw_triplets)``。

    容错但不静默：剥围栏、截取首个 ``{...}``；仍然解析不了就抛
    :class:`ValueError`（带上响应片段），让构建详情里能看到真实返回。
    """
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    if not text:
        raise ValueError("模型返回空响应（可能是端点不可达或超时后被截断）")
    try:
        data = json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"响应不是 JSON（前 200 字）: {text[:200]!r}") from None
        try:
            data = json.loads(text[start:end + 1])
        except Exception as exc:
            raise ValueError(
                f"响应无法解析为 JSON（前 200 字）: {text[:200]!r}"
            ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"响应顶层不是对象: {type(data).__name__}")

    entities = data.get("entities") or data.get("nodes") or []
    triplets = (
        data.get("relations") or data.get("triplets")
        or data.get("edges") or []
    )
    # 关系端点可能以 {name: ...} 结构回来：规整层的 _as_text 能吃，但这里
    # 统一成字符串可让「端点必须来自实体表」的判定与规则通道完全一致。
    norm: list = []
    for item in triplets if isinstance(triplets, list) else []:
        if not isinstance(item, dict):
            norm.append(item)
            continue
        row = dict(item)
        for key in ("source", "target", "subject", "object"):
            val = row.get(key)
            if isinstance(val, dict):
                row[key] = (
                    val.get("name") or val.get("text") or val.get("entity") or ""
                )
        norm.append(row)
    return (entities if isinstance(entities, list) else []), norm


# ── 抽取器 ───────────────────────────────────────────────────────────────
class LLMExtractor:
    """可注入的 LLM 抽取器：``(text, *, schema_hint="")`` → ``(entities, triplets)``。

    :param complete: 补全函数（``prompt -> str``）。测试注入点；
        为 ``None`` 时按 :attr:`cfg` 走 AgentScope ChatModel。
    """

    def __init__(
        self,
        cfg: Optional[dict] = None,
        *,
        complete: Optional[Callable[[str], str]] = None,
        timeout_seconds: int = 60,
        max_entities: int = MAX_ENTITIES,
        max_relations: int = MAX_RELATIONS,
    ) -> None:
        self.cfg = cfg or {}
        self._complete = complete
        self.timeout_seconds = max(0, int(timeout_seconds or 0))
        self.max_entities = int(max_entities or MAX_ENTITIES)
        self.max_relations = int(max_relations or MAX_RELATIONS)

    @property
    def model_desc(self) -> str:
        return "provider={} model={} base_url={} api_key_configured={}".format(
            self.cfg.get("provider"), self.cfg.get("model"),
            self.cfg.get("base_url"), bool(self.cfg.get("api_key")),
        )

    def _call_model(self, prompt: str) -> str:
        """同步驱动一次对话调用。

        ⚠️ ``build_model`` 必须在 ``asyncio.run`` 新建的 loop **内部**执行：
        ``OpenAIChatModel.__init__`` 会立刻构造 ``openai.AsyncClient``（内含
        httpx 连接池），该客户端绑定构造时的 loop。跨 loop 发请求会让连接归属
        错乱，loop 关闭后 GC 触发 ``aclose()`` → ``RuntimeError: Event loop is
        closed``（与 :mod:`app.ai.research.llm` 同一结论）。
        """
        from agentscope.message import Msg, TextBlock

        def _msg(text: str) -> "Msg":
            # Msg 是 pydantic v2 BaseModel：必须 kwargs + TextBlock，不能位置传参
            return Msg(name="user", role="user", content=[TextBlock(text=text)])

        async def _drive() -> Any:
            from app.ai.research.llm import _aclose_model, _safe_text
            from app.ai.strategy.factory_ext import build_model

            model = build_model(self.cfg)
            try:
                coro = model([_msg(prompt)])
                if self.timeout_seconds:
                    coro = asyncio.wait_for(coro, timeout=self.timeout_seconds)
                return _safe_text(await coro)
            finally:
                await _aclose_model(model)

        return asyncio.run(_drive())

    def complete(self, prompt: str) -> str:
        if self._complete is not None:
            return self._complete(prompt)
        if not (self.cfg.get("model")):
            raise ValueError(f"图谱抽取模型未配置，无法调用 LLM 通道（{self.model_desc}）")
        return self._call_model(prompt)

    def __call__(self, text: str, *, schema_hint: str = "") -> Tuple[list, list]:
        prompt = build_prompt(
            text,
            schema_hint=schema_hint,
            max_entities=self.max_entities,
            max_relations=self.max_relations,
        )
        raw = self.complete(prompt)
        try:
            return parse_response(raw)
        except ValueError as exc:
            raise ValueError(f"{exc}（{self.model_desc}）") from exc


def build_llm_extractor(db, graph_cfg: dict, *, complete=None) -> Tuple[
    Optional[LLMExtractor], str
]:
    """按图谱配置构造 LLM 抽取器。

    :return: ``(extractor | None, note)`` —— 为 ``None`` 时 ``note`` 给出**为什么**，
        由调用方写进构建报告：静默退回规则通道会让前端看到「成功但 0 实体」。
    """
    timeout = int(graph_cfg.get("timeout_seconds") or 60)
    if graph_cfg.get("extractor_type") not in (None, "llm"):
        return None, f"extractor_type={graph_cfg.get('extractor_type')} 不走 LLM 通道"
    cfg = resolve_llm_config(db, graph_cfg.get("model_spec"))
    if cfg is None and complete is None:
        return None, (
            "模型管理中无可用的默认对话模型（type=1 + status=1 + 关联密钥可用）"
        )
    return (
        LLMExtractor(
            cfg, complete=complete, timeout_seconds=timeout,
            max_entities=int(graph_cfg.get("max_entities") or MAX_ENTITIES),
            max_relations=int(graph_cfg.get("max_relations") or MAX_RELATIONS),
        ),
        (cfg or {}).get("model", ""),
    )
