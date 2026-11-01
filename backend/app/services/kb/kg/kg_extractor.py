"""图谱抽取器（P3）—— LLM 输出是不可信输入，规整层必须比模型更严格。

设计来源：Yuxi ``extractors/base.py`` 的工程范式 + spec §5.3。

核心立场
--------
**LLM 的输出不可信**：类型会漂移、名字会超长、JSON 会缺字段、端点实体会悬空。
因此本层的所有越界处理都是**丢弃并计数**，而不是抛错——
一次抽取失败不该让整篇文档的摄取挂掉（spec「降级但显式」）。

与 Yuxi 的唯一实质差异：**类型取值受 CDM 约束**（``schema_source=cdm`` 时
把 ``meta_object_standard`` / ``meta_object_relation`` 的 code 注入 prompt），
从源头抑制 Yuxi 报告里指出的类型漂移问题（spec §2.3）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

# ── 长度守卫（越界丢弃，不抛错）──────────────────────────────────────────
MAX_ENTITY_NAME_LENGTH = 512
MAX_ENTITY_LABEL_LENGTH = 128
MAX_RELATION_TYPE_LENGTH = 256

_WS_RE = re.compile(r"\s+")

# 三元组字段的同义拼写（不同抽取器/版本命名不一，统一收敛）
_SUBJECT_KEYS = ("subject", "source", "src", "head", "from", "entity1", "s")
_OBJECT_KEYS = ("object", "target", "tgt", "tail", "to", "entity2", "o")
# ``relation_type`` 是 LLM 通道的约定字段名（prompt 里让模型这么输出），
# 缺了它会把模型给的关系全部当成“无谓词”丢弃。
_PREDICATE_KEYS = ("predicate", "relation", "relationship", "relation_type",
                   "type", "rel", "p")
_NAME_KEYS = ("name", "text", "entity", "value", "label_text")
_LABEL_KEYS = ("label", "type", "category", "entity_type")


def normalize_entity_name(name: str) -> str:
    """归一名：去首尾空白 + 压缩内部空白 + 小写（Yuxi 同款）。"""
    return _WS_RE.sub(" ", (name or "").strip()).lower()


@dataclass
class ExtractionResult:
    """一次抽取的产出（含丢弃计数，供构建详情上报）。"""

    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    dropped_entities: int = 0
    dropped_relations: int = 0
    errors: list[str] = field(default_factory=list)

    def as_details(self, elapsed_ms: int = 0) -> dict:
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "dropped_entities": self.dropped_entities,
            "dropped_relations": self.dropped_relations,
            "errors": self.errors[:5],
            "elapsed_ms": elapsed_ms,
        }


def _pick(d: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _as_text(v: Any) -> str:
    """端点可能是字符串，也可能是 ``{name: ...}`` 结构——两种都要能吃。"""
    if isinstance(v, dict):
        inner = _pick(v, _NAME_KEYS)
        return str(inner) if inner is not None else ""
    return "" if v is None else str(v)


def build_schema_hint(
    db,
    *,
    schema_source: str = "free_text",
    catalog_id: Optional[int] = None,
    free_text: str = "",
    tenant_id: Optional[int] = None,
    limit: int = 200,
) -> str:
    """拼装注入 prompt 的类型约束。

    * ``none``      → 不给约束（LLM 自由发挥，类型可能漂移）
    * ``free_text`` → 直接用用户写的约束文本
    * ``cdm``       → 查 CDM 对象/关系标准，把 code 列表注入（抑制漂移的关键）
    """
    if schema_source == "free_text":
        return (free_text or "").strip()
    if schema_source != "cdm" or db is None:
        return ""

    try:
        from sqlalchemy import select

        from app.models.dataops.standard_cdm import (
            MetaObjectRelation,
            MetaObjectStandard,
            MetaStandardCatalog,
        )

        # 目录子树展开：选中父目录 = 约束其自身 + 所有子孙目录下的标准。
        # 前端 CDM 目录已是树状下拉，若仍按单节点精确匹配，选父节点会
        # 漏掉挂在子目录里的对象/关系标准——与树的直觉相悖，故取闭包。
        scope_ids: Optional[list] = None
        if catalog_id is not None:
            children_map: dict = {}
            cat_stmt = select(MetaStandardCatalog.id, MetaStandardCatalog.parent_id)
            if tenant_id is not None:
                cat_stmt = cat_stmt.where(MetaStandardCatalog.tenant_id == tenant_id)
            for cid, pid in db.execute(cat_stmt).all():
                children_map.setdefault(pid, []).append(cid)
            seen, stack = {catalog_id}, [catalog_id]
            while stack:
                for child_id in children_map.get(stack.pop(), []):
                    if child_id not in seen:
                        seen.add(child_id)
                        stack.append(child_id)
            scope_ids = list(seen)

        obj_stmt = select(MetaObjectStandard.code, MetaObjectStandard.name)
        rel_stmt = select(MetaObjectRelation.code, MetaObjectRelation.name)
        if tenant_id is not None:
            obj_stmt = obj_stmt.where(MetaObjectStandard.tenant_id == tenant_id)
            rel_stmt = rel_stmt.where(MetaObjectRelation.tenant_id == tenant_id)
        if scope_ids is not None:
            obj_stmt = obj_stmt.where(MetaObjectStandard.catalog_id.in_(scope_ids))
            rel_stmt = rel_stmt.where(MetaObjectRelation.catalog_id.in_(scope_ids))

        objects = db.execute(obj_stmt.limit(limit)).all()
        relations = db.execute(rel_stmt.limit(limit)).all()
    except Exception as exc:  # noqa: BLE001 - CDM 不可用退化为无约束，不阻断抽取
        logger.warning(f"[kg] 读取 CDM 类型约束失败，退化为无约束抽取: {exc}")
        return ""

    if not objects and not relations:
        return ""
    obj_part = "、".join(f"{c}({n})" for c, n in objects)
    rel_part = "、".join(f"{c}({n})" for c, n in relations)
    return (
        "请严格使用以下类型集合，不要自造类型。\n"
        f"实体类型: {obj_part or '（无）'}\n"
        f"关系类型: {rel_part or '（无）'}"
    )


def _normalize_entity(raw: Any) -> Optional[dict]:
    """规整单个实体；不合法返回 None（由调用方计入丢弃）。"""
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        return None
    name = _as_text(_pick(raw, _NAME_KEYS)).strip()
    if not name or len(name) > MAX_ENTITY_NAME_LENGTH:
        return None
    label = _as_text(_pick(raw, _LABEL_KEYS)).strip()
    if len(label) > MAX_ENTITY_LABEL_LENGTH:
        return None
    aliases = raw.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    return {
        "name": name,
        "label": label,
        "aliases": [a for a in aliases if isinstance(a, str)][:20],
        "properties": raw.get("properties") if isinstance(raw.get("properties"), dict) else {},
        "normalized": normalize_entity_name(name),
    }


def _normalize_relation(raw: Any, kept: set[str]) -> Optional[dict]:
    """规整单个关系；**端点实体被丢弃则关系一并丢弃**（悬空边不入库）。"""
    if not isinstance(raw, dict):
        return None
    src = _as_text(_pick(raw, _SUBJECT_KEYS)).strip()
    tgt = _as_text(_pick(raw, _OBJECT_KEYS)).strip()
    rtype = _as_text(_pick(raw, _PREDICATE_KEYS)).strip()
    if not src or not tgt or not rtype:
        return None
    if len(rtype) > MAX_RELATION_TYPE_LENGTH:
        return None
    if normalize_entity_name(src) not in kept or normalize_entity_name(tgt) not in kept:
        return None
    return {
        "source": src,
        "target": tgt,
        "relation_type": rtype,
        "text": _as_text(raw.get("text") or raw.get("evidence") or ""),
    }


def extract(
    text: str,
    *,
    client=None,
    schema_hint: str = "",
    tenant_id: Optional[int] = None,
    llm: Optional[Any] = None,
) -> ExtractionResult:
    """从一段文本抽取实体与关系。

    两条通道共用下方同一套**规整层**（长度守卫 / 去重 / 悬空边丢弃），
    避免「LLM 通道少校验一项」的隐性分叉：

    * ``llm`` 不为空 → LLM 通道（:mod:`kg_llm_extractor`，中文长文本唯一可行解）；
    * 否则          → semantica 规则/NER 通道（缺 spaCy 时为英文正则，**中文几乎零召回**）。

    :param client: 规则通道的抽取客户端（默认 ``SemanticaClient``；测试可注入假实现）
    :param llm: 可调用 ``(text, *, schema_hint="") -> (raw_entities, raw_triplets)``
    :return: :class:`ExtractionResult`（含丢弃计数与错误，绝不抛异常）
    """
    result = ExtractionResult()
    if not (text or "").strip():
        return result

    raw_entities: list = []
    raw_triplets: list = []

    if llm is not None:
        try:
            raw_entities, raw_triplets = llm(text, schema_hint=schema_hint)
        except Exception as exc:  # noqa: BLE001 - 单切片失败不中断整批
            # **不回落规则通道**：回落会产出一堆 related_to 全连接弱关系，
            # 比空结果更难发现（前端看起来“抽取成功”）。直接失败 → 阶段标记置
            # False → 模型恢复后可断点续跑。
            result.errors.append(f"LLM 抽取失败: {type(exc).__name__}: {exc}")
        return _assemble(result, raw_entities, raw_triplets)

    if client is None:
        try:
            from app.services.semantica.client import SemanticaClient
            from app.services.semantica.scope import TenantScope

            scope = TenantScope(tenant_id) if tenant_id is not None else None
            client = SemanticaClient(scope)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"抽取器初始化失败: {exc}")
            return result

    try:
        # 类型约束作为抽取选项注入；抽取器不接受该选项时降级为无约束重试
        # （semantica / 自建抽取器的入参约定不一，失败不能让整段文本颗粒无收）
        if schema_hint:
            try:
                raw_entities = list(
                    client.extract_entities(text, schema=schema_hint) or []
                )
            except TypeError:
                raw_entities = list(client.extract_entities(text) or [])
        else:
            raw_entities = list(client.extract_entities(text) or [])
    except Exception as exc:  # noqa: BLE001 - 抽取失败登记后继续（关系可能仍可用）
        result.errors.append(f"实体抽取失败: {type(exc).__name__}: {exc}")
    try:
        raw_triplets = list(client.extract_triplets(text, entities=raw_entities) or [])
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"关系抽取失败: {type(exc).__name__}: {exc}")

    return _assemble(result, raw_entities, raw_triplets)


def _assemble(
    result: ExtractionResult, raw_entities: list, raw_triplets: list
) -> ExtractionResult:
    """两条通道共用的规整层：去重 + 长度守卫 + 悬空边丢弃。"""
    # ── 实体：去重 + 长度守卫 ──
    seen: dict[str, dict] = {}
    for raw in raw_entities:
        ent = _normalize_entity(raw)
        if ent is None:
            result.dropped_entities += 1
            continue
        seen.setdefault(ent["normalized"], ent)
    result.entities = list(seen.values())
    kept = set(seen.keys())

    # ── 关系：悬空丢弃 + 去重 ──
    rel_seen: set[tuple] = set()
    for raw in raw_triplets:
        rel = _normalize_relation(raw, kept)
        if rel is None:
            result.dropped_relations += 1
            continue
        key = (
            normalize_entity_name(rel["source"]),
            rel["relation_type"],
            normalize_entity_name(rel["target"]),
        )
        if key in rel_seen:
            continue
        rel_seen.add(key)
        result.relations.append(rel)

    return result
