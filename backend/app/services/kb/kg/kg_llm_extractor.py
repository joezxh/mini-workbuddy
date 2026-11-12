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
* **失败要报名字**：报错抛 :mod:`kg_failure` 的带码异常（仍是 ``ValueError``），
  前端按码取 i18n 文案，而不是把 ``ValueError: ...`` 原样倒给用户。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable, Optional, Tuple

from loguru import logger

from app.services.kb.kg.kg_failure import (
    InvalidResponseError,
    KgExtractionError,
    ModelUnavailableError,
    NoTextResponseError,
    ThinkingOverflowError,
    TruncatedResponseError,
)

# 单切片实体/关系上限：本地小模型一旦放开就会自造一堆无关实体
MAX_ENTITIES = 40
MAX_RELATIONS = 60
# 送进 prompt 的正文上限（字符）：留出输出与指令空间
MAX_TEXT_CHARS = 6000
# 单次抽取的输出 token 预算：抽取通道的**上限**（模型行 max_tokens 比它小则照用更小值）。
# 为什么必须设上限而不是「照抄模型行配置」：小上下文自托管引擎的窗口是并发请求
# 共享的，声明的输出越大等于向引擎预订越多窗口。实测 LM Studio
# （context_length=8192、parallel=4）上，4 路并发时 max_tokens=4096 有 3/4 直接
# 400「Context size has been exceeded」，而 ≤1024 全部通过——这就是 45 段抽取
# 失败 40 段的成因（模型行 max_tokens=8192 + 默认 concurrency_count=8）。
# 抽取响应本身有上限（MAX_ENTITIES/MAX_RELATIONS），预算撞顶被拦腰截断的部分由
# parse_response 的截断修复保住；窗口更小的引擎可经 pipeline_config.graph
# 的 max_output_tokens 继续下调（如 512）。
DEFAULT_MAX_OUTPUT_TOKENS = 1024
# 退避重试的下限与次数：引擎按窗口容量拒绝属可退避问题（并发争用是概率性的），
# 每次把输出预算减半，让单段在窗口紧张时仍能拿到部分结果而不是直接判死。
MIN_OUTPUT_TOKENS = 128
CTX_RETRY_LIMIT = 3

# 引擎「窗口不够用」的文案特征（LM Studio/llama.cpp、vLLM、OpenAI 兼容后端各一套说法）
_CTX_EXCEEDED_MARKERS = (
    "context size has been exceeded",
    "maximum context length",
    "context_length_exceeded",
    "context window",
    "exceeds the model",
    "too many tokens",
)


def is_context_exceeded(exc: BaseException) -> bool:
    """该异常是否是「提示词 + 声明输出超出引擎窗口」一类的容量拒绝（可退避）。"""
    msg = str(exc).lower()
    return any(m in msg for m in _CTX_EXCEEDED_MARKERS)


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
        # 带堆栈：这条分支会把 LLM 通道降级成规则通道，只留一句 warning 时
        # 「表不存在」「连接断开」「类型不匹配」在日志里长得一模一样。
        logger.opt(exception=True).warning(
            f"[kg] 解析图谱抽取模型配置失败: {exc}"
        )
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
        # 输出预算是稀缺资源：text 依据与空字段是 token 大头，压缩单条体积
        # 才能让固定预算装下更多关系（截断丢尾丢的几乎全是关系）
        "4. relations 的 text 只保留支撑该关系的原文片段（不超过 60 字）；"
        "aliases 与 properties 没有内容时省略；",
        "5. 无法确定的字段填空字符串或空对象，不要编造；",
        "6. 只输出 JSON，不要输出解释、前后缀或代码块围栏。",
    ]
    hint = (schema_hint or "").strip()
    if hint:
        parts += ["", "类型约束（优先遵守，不在集合内的类型宁可不标）：", hint]
    body = (text or "")[:MAX_TEXT_CHARS]
    parts += ["", "文本：", '"""', body, '"""']
    return "\n".join(parts)


def build_continuation_prompt(
    text: str,
    *,
    schema_hint: str = "",
    known_entities: list,
    known_relations: list,
    max_entities: int = MAX_ENTITIES,
    max_relations: int = MAX_RELATIONS,
) -> str:
    """续抽指令：首轮输出撞预算被截断后，让模型只补遗漏项。

    截断修复只能保住 JSON 前部（实体在 relations 之前，丢的几乎全是尾部
    关系），续抽是把这些丢掉的关系补回来的唯一手段。已抽取清单随提示下发，
    避免模型整段重输出（重了也会被合并去重，但白花输出预算）。
    """
    parts = [
        "你是知识图谱抽取器。上一轮抽取的输出因长度限制被截断，排在后面的关系没有输出完整。",
        "请继续阅读文本，只输出**上一轮遗漏**的实体与关系（已抽取的不要重复），只输出一个 JSON 对象。",
        "",
        "输出结构（与上一轮相同）：",
        '{"entities": [{"name": "实体名", "label": "类型", '
        '"aliases": ["别名"], "properties": {}}], '
        '"relations": [{"source": "起点实体名", "target": "终点实体名", '
        '"relation_type": "关系", "text": "支撑该关系的原文片段"}]}',
        "",
        f"已抽取的实体名（不要重复输出）：{json.dumps(known_entities, ensure_ascii=False)}",
        f"已抽取的关系（起点|关系|终点，不要重复输出）：{json.dumps(known_relations, ensure_ascii=False)}",
        "",
        "硬性要求：",
        f"1. 新增实体不超过 {max_entities} 个，新增关系不超过 {max_relations} 个；",
        "2. name 必须是原文中出现的表述，不要改写、不要翻译；",
        "3. relations 的 source 与 target 必须出现在实体 name 中；",
        "4. relations 的 text 只保留支撑该关系的原文片段（不超过 60 字）；"
        "aliases 与 properties 没有内容时省略；",
        "5. 只输出 JSON，不要输出解释或代码块围栏。",
    ]
    hint = (schema_hint or "").strip()
    if hint:
        parts += ["", "类型约束（优先遵守，不在集合内的类型宁可不标）：", hint]
    body = (text or "")[:MAX_TEXT_CHARS]
    parts += ["", "文本：", '"""', body, '"""']
    return "\n".join(parts)


def _relation_key(raw: dict) -> tuple:
    """关系去重键：(起点, 关系类型, 终点)——与落库 upsert 的幂等口径一致。

    谓词字段名沿用规整层认的那几个别名（本模块不 import 规整层的
    ``_pick``/``_PREDICATE_KEYS``，保持「解析层不依赖规整层实现细节」）。
    """
    rtype = ""
    for key in ("relation_type", "predicate", "relation", "relationship"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            rtype = val.strip()
            break
    return (
        str(raw.get("source") or "").strip(),
        rtype,
        str(raw.get("target") or "").strip(),
    )


def merge_outputs(first: ParsedOutput, second: ParsedOutput) -> ParsedOutput:
    """首轮与续抽结果的并集（实体按名去重、关系按端点三元组去重）。

    续抽响应可能重复首轮条目、也可能只回 relations——都按同一套键去重即可。
    合并后的留痕沿用首轮 ``truncated_json`` 形态：续抽**又**撞顶时
    ``budget_hit`` 仍为 True（还有遗漏），否则视为已补齐。
    """
    entities: list = list(first[0])
    seen_names = {
        str(e.get("name") or "").strip() for e in entities if isinstance(e, dict)
    }
    for e in second[0]:
        name = str(e.get("name") or "").strip() if isinstance(e, dict) else ""
        if name and name not in seen_names:
            entities.append(e)
            seen_names.add(name)

    relations: list = list(first[1])
    seen_rels = {_relation_key(r) for r in relations if isinstance(r, dict)}
    for r in second[1]:
        if isinstance(r, dict) and _relation_key(r) not in seen_rels:
            relations.append(r)
            seen_rels.add(_relation_key(r))

    n1 = first.notice or {}
    n2 = second.notice or {}
    merged = dict(n1)
    merged.update({
        "continued": True,
        "kept_entities": len(entities),
        "kept_relations": len(relations),
        "dropped_chars": int(n1.get("dropped_chars") or 0)
        + int(n2.get("dropped_chars") or 0),
        "output_tokens": int(n1.get("output_tokens") or 0)
        + int(n2.get("output_tokens") or 0),
        # 续抽自身又顶满预算 = 仍有尾部遗漏，如实上报（前端看到「还有缺口」）
        "budget_hit": bool(n2.get("budget_hit")),
    })
    return ParsedOutput(entities, relations, merged)


def _json_state(text: str) -> Tuple[Optional[list], list]:
    """扫一遍 JSON 前缀（可能不完整），返回 ``(未闭合括号栈或 None, 回退点列表)``。

    * 栈元素为开括号字符；若结尾停在未闭合的字符串字面量里，栈判为 ``None``
      （该前缀不能靠补闭合符变成合法 JSON，必须换回退点）。
    * 回退点 = 每个「已完整产出的值」结束后的下一个位置（闭合的字符串、
      闭合的 ``{…}`` / ``[…]``），降序。在回退点处截断再补齐闭合符，就能
      丢掉末尾残缺项而不误伤前部已完整的条目。
    """
    stack: list = []
    points: list = []
    in_str, esc = False, False
    i = 0
    while i < len(text):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
                points.append(i + 1)      # 一个完整字符串刚结束
        elif c == '"':
            in_str = True
        elif c in "[{":
            stack.append(c)
        elif c in "}]":
            if not stack:
                return None, []           # 括号不配对，不是可修的前缀
            stack.pop()
            points.append(i + 1)          # 一个完整对象/数组刚结束
        i += 1
    if in_str:
        return None, sorted(set(points), reverse=True)
    return stack, sorted(set(points), reverse=True)


def _repair_truncated_json(text: str) -> Tuple[Optional[str], int]:
    """撞输出上限被截断的 JSON → ``(可解析串, 丢弃字符数)``；修无可修返回 ``(None, 0)``。

    实测截断尾部停在对象中途（如 `"relation_type":`）。策略：从「全文直接补
    闭合符」开始，逐个回退到更早的完整值边界试解析 —— 先试保留最多内容的切点，
    因此只丢末尾残缺项，前部完整的实体/关系全部保住（相比整段报「结构失败」，
    部分结果对图谱构建仍有价值且可重跑补齐）。

    丢弃字符数一并回带：上游要往构建详情写「这一段被裁掉了多少」，只在
    调用处重新定位切点会把上面的回退点逻辑拄第二遍。

    两个实测踩过的坑（因此不能拍脑袋取某一个切点）：
    * 尾部已配对的 ``}``/`]`` 被当垃圾剥掉 → 前部完整条目连带丢失；
    * 停在某个刚开的 ``{`` 上却保留它 → 修出 ``[{}]`` 假实体，不报错但零产出。
    """
    stripped = (text or "").strip()
    if not stripped or stripped[0] not in "[{":
        return None, 0
    closers = {"{": "}", "[": "]"}
    _init, points = _json_state(stripped)
    # 先试不截断的全文（末尾已停在完整值上时，一步就能补闭合）；再按回退点由近及远
    for cut in [len(stripped), *points]:
        # 只剥悬挂逗号/冒号/空白：标点之外的字符（尤其引号）一律不动
        cand = re.sub(r'[\s,:]*$', "", stripped[:cut])
        if not cand:
            continue
        stack, _pts = _json_state(cand)
        if stack is None:
            continue
        fixed = cand + "".join(closers[o] for o in reversed(stack))
        try:
            json.loads(fixed)
        except Exception:
            continue
        return fixed, max(0, len(stripped) - cut)
    return None, 0


class ParsedOutput(tuple):
    """``(entities, triplets)`` + 可选的**裁剪留痕**。

    为什么是 ``tuple`` 子类而不是 dataclass：抽取结果在规整层、构建服务与全部
    回归用例里都按 2 元组解包（``entities, triplets = ...``），改返回类型会在每一处
    解包点上炸；继承 tuple 则老用法完全不变，只需额外读 ``.notice``。

    ``notice`` 仅在响应走过截断修复路径时非空：部分结果照常入库，但必须留着
    「被裁掉了多少」，否则前端看到「成功 N 实体」会以为抽全了。
    """

    def __new__(
        cls, entities: list, triplets: list, notice: Optional[dict] = None
    ) -> "ParsedOutput":
        out = super().__new__(cls, (entities, triplets))
        out.notice = notice
        return out


def _truncation_notice(
    data: dict, dropped_chars: int, evidence: Optional[dict]
) -> dict:
    """补齐结果的裁剪留痕：修复层出「丢了多少字」，响应层出「用量/预算/思考」。"""
    ev = evidence or {}
    budget = int(ev.get("budget") or 0)
    used = int(ev.get("output_tokens") or 0)
    ents = data.get("entities") or data.get("nodes") or []
    rels = data.get("relations") or data.get("triplets") or data.get("edges") or []
    return {
        "type": "truncated_json",
        "output_tokens": used,
        "budget": budget,
        # 用量顶满预算＝真的撞在输出上限上；未顶满＝模型自己提前收了笔（另一回事）
        "budget_hit": bool(budget) and used >= budget,
        "had_thinking": bool(ev.get("had_thinking", False)),
        "thinking_chars": int(ev.get("thinking_chars") or 0),
        "kept_entities": len(ents) if isinstance(ents, list) else 0,
        "kept_relations": len(rels) if isinstance(rels, list) else 0,
        "dropped_chars": int(dropped_chars or 0),
    }


def parse_response(raw: str, *, truncation: Optional[dict] = None) -> ParsedOutput:
    """LLM 响应 → :class:`ParsedOutput`（ ``(raw_entities, raw_triplets)`` + 留痕）。

    容错但不静默：剥围栏、截取首个 ``{...}``；仍然解析不了就抛**带码的**异常
    （:class:`kg_failure.KgExtractionError` 子类，也是 ``ValueError``），
    让构建详情里既留着真实返回原文，又能按码给出人话原因。

    ``truncation`` 为调用侧带过来的用量证据（``output_tokens`` / ``budget`` /
    ``thinking_chars``）：只有「补齐后仍有产出」时才会写进结果，撞顶本身不报错。
    """
    text = _FENCE_RE.sub("", (raw or "").strip()).strip()
    notice: Optional[dict] = None
    if not text:
        raise NoTextResponseError("模型返回空响应（可能是端点不可达或超时后被截断）")
    try:
        data = json.loads(text)
    except Exception:
        start = text.find("{")
        if start == -1:
            raise InvalidResponseError(
                f"响应不是 JSON（前 200 字）: {text[:200]!r}"
            ) from None
        end = text.rfind("}")
        data = None
        if end > start:
            try:
                data = json.loads(text[start:end + 1])
            except Exception:  # 进修复分支
                data = None
        if data is None:
            # 输出预算撞顶的拦腰截断（含只开了头、一个闭合 `}` 都没吐出的极端情）：
            # 剥掉残缺尾项、补齐闭合符，保住前部已完整的实体/关系
            repaired, dropped = _repair_truncated_json(text[start:])
            if repaired is None:
                raise InvalidResponseError(
                    f"响应无法解析为 JSON（前 200 字）: {text[:200]!r}"
                ) from None
            data = json.loads(repaired)
            # 修复后只剩空壳 = 一个完整条目都没抽到，与「静默空结果」不可区分；
            # 宁可报错让构建详情留痕，也不让前端看到「成功但 0 实体」。
            # （仅限修复路径：正常响应确实无实体是合法结果，不能报错）
            if not (data.get("entities") or data.get("nodes")
                    or data.get("relations") or data.get("triplets")
                    or data.get("edges")):
                raise TruncatedResponseError(
                    f"响应截断修复后无任何实体/关系（前 200 字）: {text[:200]!r}"
                ) from None
            # 补出来了不等于抽全了：带着「丢了多长 + 是不是撞在预算上」一起上抛
            notice = _truncation_notice(data, dropped, truncation)
    if not isinstance(data, dict):
        raise InvalidResponseError(f"响应顶层不是对象: {type(data).__name__}")

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
    return ParsedOutput(entities if isinstance(entities, list) else [], norm, notice)


# ── 抽取器 ───────────────────────────────────────────────────────────────
def _block_kind(block: Any) -> str:
    if isinstance(block, dict):
        btype = block.get("type")
    else:
        btype = getattr(block, "type", None)
    return str(btype if btype is not None else type(block).__name__)


def _block_field(block: Any, name: str) -> str:
    """取块上的文本字段（块既可能是 dict（openai 兼容返回），也可能是 pydantic 模型）。"""
    for key in (name, "text"):
        val = block.get(key) if isinstance(block, dict) else getattr(block, key, None)
        if isinstance(val, str) and val:
            return val
    return ""


def _response_evidence(resp: Any, budget: int = 0) -> dict:
    """响应里的「有没有思考链、烧掉多少输出 token」——判撞顶与写留痕都要用。

    为什么不用 ``finished_reason``：agentscope 2.x 的 ``FinishedReason`` 只有
    ``COMPLETED`` / ``INTERRUPTED`` 两个值，**不透传** OpenAI 的 ``length``，
    被截断的响应在 SDK 层看起来与正常完成一模一样；只能拿 ``usage.output_tokens``
    对本次的输出预算比对。（``output_tokens`` 即 API 的 ``completion_tokens``。）
    """
    usage = getattr(resp, "usage", None)
    used = int(getattr(usage, "output_tokens", 0) or 0)
    content = getattr(resp, "content", None)
    thinking_chars = 0
    if isinstance(content, list):
        for block in content:
            if _block_kind(block) == "thinking":
                thinking_chars += len(_block_field(block, "thinking"))
    return {
        "output_tokens": used,
        "budget": int(budget or 0),
        "had_thinking": thinking_chars > 0,
        "thinking_chars": thinking_chars,
    }


def _collect_text(resp: Any, *, budget: int = 0) -> str:
    """从 ChatResponse 只取 **text** 块，丢弃 thinking（思考）与工具/音频块。

    不能复用 :func:`app.ai.research.llm._safe_text`：它把 ThinkingBlock 一并
    拼进正文，思考链里出现的 ``{...}`` 会污染 ``parse_response`` 的粗切截取
    （first ``{`` … last ``}``），抽出来的就不是模型的正式 JSON 回答。

    ``budget`` 为本请求实际下发的输出预算：正文为空而用量又顶满了预算，说的
    是「思考链把窗口吃光了」而不是「模型只知思考不知作答」，两者修法不同。
    """
    if isinstance(resp, str):
        return resp
    content = getattr(resp, "content", None)
    if isinstance(content, list):
        parts: list[str] = []
        kinds: list[str] = []
        for block in content:
            btype = _block_kind(block)
            kinds.append(btype)
            if btype == "text":
                text = _block_field(block, "text")
                if text:
                    parts.append(text)
            elif isinstance(block, dict) and block.get("text"):
                # 带额外类型（tool_use/audio）的 dict 块只在显式有 text 时兼容拾回，
                # 保持旧行为：不吃 thinking，也不乱吃未知结构的块
                parts.append(str(block["text"]))
            elif getattr(block, "type", None) is None and isinstance(
                getattr(block, "text", None), str
            ):
                # 不给 type 的自定义块（测试/旁路封装）：沿用旧行为按 text 拾回
                parts.append(block.text)
        if parts:
            return "".join(parts)
        # content 是列表但无文本块（只有思考/工具）：回退 str() 会让 repr 漏进
        # 解析，交给调用方报「空响应」，错误信息更真实。
        # 块类型清单一并带出：「思考链撑满窗口」与「模型转去调工具」的处理方式
        # 完全不同（前者关思考/换模型，后者要禁用工具），只报「没有正文」无法区分。
        ev = _response_evidence(resp, budget)
        if ev["had_thinking"] and ev["budget"] and ev["output_tokens"] >= ev["budget"]:
            # 双证据齐了才改判：思考有内容 + 用量顶满预算。
            # 只拿「有思考块」当撞顶依据会把「模型只想不答」误报成容量问题（调大
            # 预算白花钱）；反过来只拿用量顶满当依据，则无任何思考时结论无据。
            raise ThinkingOverflowError(
                f"思考链占满输出预算，正文为空"
                f"（thinking_chars={ev['thinking_chars']}"
                f" output_tokens={ev['output_tokens']} budget={ev['budget']}"
                f" blocks={kinds or ['<empty>']}）"
            )
        raise NoTextResponseError(
            f"模型只返回了思考/工具块，没有正文文本"
            f"（blocks={kinds or ['<empty>']} resp_type={type(resp).__name__}"
            f" usage={getattr(resp, 'usage', None)}）"
        )
    text = getattr(resp, "text", None)
    if isinstance(text, str) and text:
        return text
    return str(resp)


# 关掉推理模型思考链的两种写法（方言），图谱抽取要的是直接输出 JSON、不要长篇推理：
# * ``chat_template_kwargs``：vLLM / SGLang 约定；
# * ``reasoning_effort``：OpenAI / LM Studio / llama.cpp 约定。
# 本机 LM Studio（unsloth qwen3.5-0.8b GGUF）实测：前者连同顶层 ``enable_thinking``、
# ``thinking:{type:"disabled"}`` 三种写法全被**静默忽略**（不报 400，等于没传，思考照旧
# 吃满 64 token 预算、正文为空），只有 ``reasoning_effort="none"`` 真生效；而 OpenAI
# 官方端点会因未知字段直接 400 拒整条请求。故两种一起发（谁认谁生效），被点名拒绝时
# 只撤被点名的那条。
_THINKING_DIALECTS: Tuple[Tuple[str, dict], ...] = (
    ("chat_template_kwargs", {"chat_template_kwargs": {"enable_thinking": False}}),
    ("reasoning_effort", {"reasoning_effort": "none"}),
)

# ``model_desc``（provider+model+base_url）→ 已被该引擎拒绝的方言键。
# 进程内缓存：45 个切片共用一个引擎，靠第一条把 400 学费交掉，其余不再重复。
_REJECTED_THINKING_DIALECTS: dict = {}

# 「请求体里有非法字段」一类的说法特征。故意不收 "invalid"/"400" 这种泛词：
# 鉴权、容量、工具调用报错都带 400/invalid，无根据撤字段会把排查方向带偏。
_REJECT_HINT_RE = re.compile(
    r"unknown|unrecognized|unrecognised|not permitted|unexpected"
    r"|extra fields|additional properties|unsupported"
    r"|未知参数|非法参数|不支持的参数|未知字段|多余字段"
)


def thinking_off_body(rejected: Optional[set] = None) -> dict:
    """待下发的关思考请求体：跳过已确认被该引擎拒绝的方言。"""
    rej = set(rejected or ())
    body: dict = {}
    for _key, part in _THINKING_DIALECTS:
        if _key not in rej:
            body.update(part)
    return body


def rejected_thinking_dialect(exc: BaseException) -> set:
    """引擎把请求体里的关思考字段当非法字段拒了 → 该撤哪些方言键；不是这种错给空集。

    容量类 400 直接排除：该减半的是输出预算，撤关思考字段既治不了病，还会让
    思考链放开了吃窗口（反而加重同一个错）。
    """
    if is_context_exceeded(exc):
        return set()
    msg = str(exc).lower()
    if not _REJECT_HINT_RE.search(msg):
        return set()
    named = {key for key, _ in _THINKING_DIALECTS if key in msg}
    # 点名字段只撤该字段；只泛泛说「有非法字段」时两条一起撤，先换回裸请求跑通
    return named or {key for key, _ in _THINKING_DIALECTS}


class LLMExtractor:
    """可注入的 LLM 抽取器：``(text, *, schema_hint="")`` → ``(entities, triplets)``。

    :param complete: 补全函数（``prompt -> str``）。测试注入点；
        为 ``None`` 时按 :attr:`cfg` 走 AgentScope ChatModel。
    :param disable_thinking: 抽取时显式关闭推理模型的思考链（默认 True）。
    :param max_output_tokens: 本通道的输出预算上限（默认
        :data:`DEFAULT_MAX_OUTPUT_TOKENS`；0 表示不设上限）。
    :param ctx_retry_limit: 撞引擎窗口后的减半重试次数。
    """

    def __init__(
        self,
        cfg: Optional[dict] = None,
        *,
        complete: Optional[Callable[[str], str]] = None,
        timeout_seconds: int = 60,
        max_entities: int = MAX_ENTITIES,
        max_relations: int = MAX_RELATIONS,
        disable_thinking: bool = True,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        ctx_retry_limit: int = CTX_RETRY_LIMIT,
    ) -> None:
        self.cfg = cfg or {}
        self._complete = complete
        self.timeout_seconds = max(0, int(timeout_seconds or 0))
        self.max_entities = int(max_entities or MAX_ENTITIES)
        self.max_relations = int(max_relations or MAX_RELATIONS)
        self.disable_thinking = bool(disable_thinking)
        self.max_output_tokens = max(0, int(max_output_tokens or 0))
        self.ctx_retry_limit = max(0, int(ctx_retry_limit or 0))

    def _output_budget(self) -> int:
        """本次抽取的输出预算 = min(模型行 max_tokens, 本通道上限)。

        只往下压、绝不放大：模型行配得更小时尊重它；配得比引擎窗口还大时
        （实测 8192）照抄过去就是整条请求被拒，所以由抽取通道封顶。
        """
        declared = int(self.cfg.get("max_tokens") or 0)
        if not self.max_output_tokens:
            return declared
        return min(declared, self.max_output_tokens) if declared else self.max_output_tokens

    @property
    def model_desc(self) -> str:
        return "provider={} model={} base_url={} api_key_configured={}".format(
            self.cfg.get("provider"), self.cfg.get("model"),
            self.cfg.get("base_url"), bool(self.cfg.get("api_key")),
        )

    def _call_model(self, prompt: str) -> str:
        return self._call_model_meta(prompt)[0]

    def _call_model_meta(self, prompt: str) -> Tuple[str, Optional[dict]]:
        """同步驱动一次对话调用，返回 ``(正文, 用量证据)``，并带两类可退避重试。

        ⚠️ ``build_model`` 必须在 ``asyncio.run`` 新建的 loop **内部**执行：
        ``OpenAIChatModel.__init__`` 会立刻构造 ``openai.AsyncClient``（内含
        httpx 连接池），该客户端绑定构造时的 loop。跨 loop 发请求会让连接归属
        错乱，loop 关闭后 GC 触发 ``aclose()`` → ``RuntimeError: Event loop is
        closed``（与 :mod:`app.ai.research.llm` 同一结论）。

        ⚠️ 必须显式 ``stream=False``：agentscope 2.x 各 ChatModel 的 ``stream``
        默认 True，``await model(...)`` 拿到的是 async_generator 而非
        ChatResponse，旧代码把它 ``str()`` 成 repr 再去解 JSON，每一段都报
        「响应不是 JSON」。消费端另保留流式兜底：万一模型类不支持关流式，
        逐块取到 ``is_last`` 的累计响应（增量块拼接会导致 JSON 被截断）。

        重试只有两条，各自不占对方的额度：
        * **方言被拒**（引擎说请求体有非法字段）→ 撤掉被点名的关思考字段重试，
          结论按 ``model_desc`` 缓存；预算不动。
        * **容量被拒**（窗口不够用）→ 减半输出预算重试，关思考字段一个都不撤。
        非这两类（端点不可达/鉴权）一次即抛，重试只是拖垮整批构建。
        """
        from agentscope.message import Msg, TextBlock

        def _msg(text: str) -> "Msg":
            # Msg 是 pydantic v2 BaseModel：必须 kwargs + TextBlock，不能位置传参
            return Msg(name="user", role="user", content=[TextBlock(text=text)])

        async def _drive(budget: int, rejected: set) -> Tuple[str, dict]:
            from app.ai.research.llm import _aclose_model
            from app.ai.strategy.factory_ext import build_model

            cfg = {**self.cfg, "stream": False}
            if budget:
                # 抽取通道的输出预算（已按模型行配置取小）：小上下文引擎的窗口
                # 由并发请求共享，声明得越大越容易被整条请求拒绝
                cfg["max_tokens"] = budget
            if self.disable_thinking:
                # 合并调用方已设的 extra_body，再叠加尚未被拒的关思考方言
                body = {
                    **(self.cfg.get("extra_body") or {}),
                    **thinking_off_body(rejected),
                }
                if body:
                    cfg["extra_body"] = body
            model = build_model(cfg)
            try:
                coro = model([_msg(prompt)])
                if self.timeout_seconds:
                    coro = asyncio.wait_for(coro, timeout=self.timeout_seconds)
                resp = await coro
                import types

                if isinstance(resp, types.AsyncGeneratorType):
                    # 兜底：模型仍返回流式 → 消费到 is_last 的累计响应，
                    # 绝不能让 async_generator 的 repr 漏进下游解析。
                    final = None
                    async for chunk in resp:
                        if getattr(chunk, "is_last", False):
                            final = chunk
                    if final is None:
                        raise NoTextResponseError(f"流式响应无终块（{self.model_desc}）")
                    resp = final
                # 正文与证据分开取：正文为空时 _collect_text 就地抛带码异常，
                # 正文非空但残缺时证据还要带给 parse_response 写留痕
                text = _collect_text(resp, budget=budget)
                return text, _response_evidence(resp, budget)
            finally:
                await _aclose_model(model)

        budget = self._output_budget()
        rejected = _REJECTED_THINKING_DIALECTS.setdefault(self.model_desc, set())
        ctx_attempt = 0
        while True:
            try:
                return asyncio.run(_drive(budget, rejected))
            except Exception as exc:  # noqa: BLE001 - 只拦两类可退避问题，其余原样上抛
                # 只撤「本次确实发出去了、且被报错点名」的字段：rejected 单调变大
                # → 可撤集合单调变小，不可能死循环。
                sent = set(thinking_off_body(rejected))
                dropped = rejected_thinking_dialect(exc) & sent if self.disable_thinking else set()
                if dropped:
                    rejected.update(dropped)
                    logger.warning(
                        f"[kg] 引擎拒绝请求字段 {sorted(dropped)}，撤掉后重试"
                        f"（{self.model_desc}）: {exc}"
                    )
                    continue
                if is_context_exceeded(exc) and ctx_attempt < self.ctx_retry_limit:
                    ctx_attempt += 1
                    halved = max(MIN_OUTPUT_TOKENS, budget // 2)
                    logger.warning(
                        f"[kg] 抽取请求超出模型上下文窗口，输出预算减半重试 "
                        f"({budget} -> {halved})（{self.model_desc}）"
                    )
                    budget = halved
                    continue
                raise

    def complete(self, prompt: str) -> str:
        return self.complete_meta(prompt)[0]

    def complete_meta(self, prompt: str) -> Tuple[str, Optional[dict]]:
        """补全 + 用量证据。证据为 ``None`` 表示本通道拿不到用量（注入的 ``complete=``）。"""
        if self._complete is not None:
            return self._complete(prompt), None
        if not (self.cfg.get("model")):
            raise ModelUnavailableError(
                f"图谱抽取模型未配置，无法调用 LLM 通道（{self.model_desc}）"
            )
        return self._call_model_meta(prompt)

    def __call__(self, text: str, *, schema_hint: str = "") -> ParsedOutput:
        prompt = build_prompt(
            text,
            schema_hint=schema_hint,
            max_entities=self.max_entities,
            max_relations=self.max_relations,
        )
        raw, evidence = self.complete_meta(prompt)
        try:
            # 证据一路带到解析层：「被截断」只有正文（残缺的 JSON）与用量（顶满的预算）
            # 合起来才判得出来，缺一侧就只能盲猜
            out = parse_response(raw, truncation=evidence)
            out = self._continue_if_truncated(text, schema_hint=schema_hint, out=out)
            if out.notice is None and len(text or "") > MAX_TEXT_CHARS:
                # 输入超限是**静默截断**（prompt 里硬切 6000 字符）：尾部实体/关系
                # 根本没进模型。留痕让「这段抽少了」可归因，别和模型抽不动混淆。
                out.notice = {
                    "type": "input_truncated",
                    "text_chars": len(text),
                    "kept_chars": MAX_TEXT_CHARS,
                }
            return out
        except KgExtractionError as exc:
            # 补上模型身份便于定位是哪一个模型行；**码随类型一起重建**，
            # 否则包装成新 ValueError 后前端只能看到句子、按码取文案的链路断在这里。
            raise type(exc)(f"{exc}（{self.model_desc}）", cause=exc) from exc
        except ValueError as exc:
            raise ValueError(f"{exc}（{self.model_desc}）") from exc

    def _continue_if_truncated(
        self, text: str, *, schema_hint: str, out: ParsedOutput
    ) -> ParsedOutput:
        """首轮输出被截断修复丢弃了字符时做**一轮有界续抽**，把丢掉的尾部关系补回来。

        触发条件用 ``dropped_chars`` 而非 ``budget_hit``：注入 ``complete=`` 的
        通道拿不到用量证据（budget=0），按双证据判定会让续抽在这些链路上永远
        不触发；而「修复时丢了字符」本身已说明尾部有内容被裁。只续一轮——
        续抽自己又撞顶时 budget_hit 如实上报，靠「调大 max_output_tokens /
        缩短切片」处理，不做无限续抽（成本失控且收益递减）。续抽任何失败都
        不影响首轮已拿到的部分结果。
        """
        notice = out.notice or {}
        if not notice.get("dropped_chars"):
            return out
        try:
            prompt = build_continuation_prompt(
                text,
                schema_hint=schema_hint,
                known_entities=[
                    str(e.get("name") or "")
                    for e in out[0] if isinstance(e, dict) and e.get("name")
                ],
                known_relations=[
                    "|".join(_relation_key(r))
                    for r in out[1] if isinstance(r, dict)
                ],
                max_entities=self.max_entities,
                max_relations=self.max_relations,
            )
            raw, evidence = self.complete_meta(prompt)
            extra = parse_response(raw, truncation=evidence)
        except Exception as exc:  # noqa: BLE001 - 续抽失败保留首轮部分结果
            logger.warning(f"[kg] 截断续抽失败，保留首轮部分结果: {exc}")
            return out
        merged = merge_outputs(out, extra)
        logger.info(
            f"[kg] 截断续抽完成：首轮 entity={len(out[0])} relation={len(out[1])}"
            f" → 合并后 entity={len(merged[0])} relation={len(merged[1])}"
        )
        return merged


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
            disable_thinking=bool(graph_cfg.get("disable_thinking", True)),
            max_output_tokens=int(
                graph_cfg.get("max_output_tokens") or DEFAULT_MAX_OUTPUT_TOKENS
            ),
        ),
        (cfg or {}).get("model", ""),
    )
